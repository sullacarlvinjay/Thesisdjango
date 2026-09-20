# Operations

Deploying and running BiPSU SRMS. [`render.yaml`](../render.yaml) and
[`build.sh`](../build.sh) are annotated in full; this is the summary and the
things that are not obvious from reading them.

---

## Deployment

Render reads `render.yaml` from the repository root. `build.sh` runs at build
time and does, in order:

1. `pip install -r requirements.txt`
2. `collectstatic` — gathers and minifies CSS and JS (see `api/storage.py`)
3. `migrate`
4. `bootstrap` — creates the office account from the environment
5. `check` — configuration warnings that would otherwise surface as 500s
6. `check_storage` — one round trip against the upload bucket

`set -o errexit` is at the top for a reason: without it a failed
`collectstatic` or a half-applied migration would still be followed by a
"successful" deploy.

The service starts with:

```
gunicorn config.wsgi:application --workers 1 --threads 8 --timeout 120
```

One worker, several threads — not two workers. Each worker loads Django,
reportlab, lxml, pillow and docxtpl into its own memory, and two of those do
not fit in the free plan's 512 MB once a masterlist render starts allocating.
Threads share that memory and the workload is I/O-bound on Postgres anyway.
Raise the worker count only together with the instance size, and set
`REDIS_URL` when you do — the rate limiter's tally is per-process otherwise.

---

## The cold start

The free plan suspends the container after roughly 15 minutes without traffic.
The next request waits about 50 seconds while it restarts. This is the single
largest observable performance problem with the deployment and it is a property
of the plan, not of the code.

What the application does about it:

- `/healthz/` is a dependency-free endpoint that returns in a few milliseconds.
  Point an external uptime monitor at it on a 10-minute interval and the
  container never idles long enough to be suspended.
- Pages show a loading state rather than appearing to hang.

What would remove it properly: the Starter plan, which does not suspend.

---

## Environment variables

[`.env.example`](../.env.example) documents every variable with its reasoning.
The ones that matter most:

| Variable | Needed when | Note |
|---|---|---|
| `SECRET_KEY` | always in production | Rotating it signs everyone out |
| `DEBUG` | always | `False` in production |
| `DATABASE_URL` | production | Supabase **pooler** host, session mode, port 5432 |
| `USE_SUPABASE_STORAGE` | production | Free plan has no persistent disk |
| `SUPABASE_S3_*` | when the above is on | Endpoint, region, key, secret, bucket |
| `BREVO_API_KEY` | to send mail | HTTPS API; Render blocks SMTP ports |
| `EMAIL_HOST_USER` | to send mail | Must be a Brevo-verified sender address |
| `SITE_URL` | to send mail | Builds the links inside messages |
| `SDSO_EMAIL`, `SDSO_PASSWORD` | first deploy | Read by `bootstrap` |
| `REDIS_URL` | multi-worker only | Makes cache and throttling shared |
| `TRUST_FORWARDED_FOR` | behind a proxy | Defaults on when `DEBUG` is off |

### Why Brevo rather than SMTP

Render blocks outbound traffic on ports 25, 465 and 587 from free web services.
A perfectly correct Gmail SMTP configuration therefore connects to nothing:
every send waits out `EMAIL_TIMEOUT` and is swallowed, and the site looks like
it is emailing people while it is not.

Brevo was chosen because it verifies a single sender *address* by emailing it a
link, where most providers verify a whole *domain* by DNS record — and nobody
on this project can add records to `bipsu.edu.ph`. Free tier is 300 messages a
day.

These credentials have to be typed into the Render dashboard by hand. Render
never prompts for them.

---

## Management commands

| Command | Does |
|---|---|
| `bootstrap` | Creates office accounts from the environment. Idempotent; never overwrites an existing password. |
| `seed` | Loads sample scholarships, students and applications for local work. |
| `seed_load --students 500` | Loads a large realistic dataset for load testing. |
| `check_storage` | One round trip against the upload bucket. Turns a mistyped secret into a build failure instead of a broken upload later. |
| `check_email` | Sends a test message through the configured backend. |
| `make_favicon` | Regenerates favicons from `media/logos/BiPSU.png`. |
| `prune_staff_student_profiles` | Removes student profiles mistakenly attached to employee accounts. |

---

## Regenerating the stylesheet

Tailwind is a real stylesheet, not the browser-compiled CDN script, and
`static/css/tailwind.css` is **committed**. The build stays pure Python and
Render never needs Node.

```bash
npm run build:css
```

Run that after changing the classes used in a template, and commit the result.
Nothing on the server will do it for you.

When you change `static/css/srms.css` or anything in `static/js/`, bump the
`?v=` on every `<link>` or `<script>` that loads it. Those query strings are
hand-written; browsers will serve a stale copy otherwise.

---

## Database notes

The `DATABASE_URL` must point at the Supabase **pooler** host
(`aws-0-<region>.pooler.supabase.com`), session mode, port 5432.

Not the direct host `db.<ref>.supabase.co`: it publishes an AAAA record and no
A record, and Render's free tier has no IPv6 egress, so that host is simply
unreachable from the deployed service. The failure looks like a hang, not a
DNS error.

---

## Local versus deployed

| | Local | Deployed |
|---|---|---|
| Database | SQLite | Supabase PostgreSQL |
| Uploads | `media/` on disk | Supabase Storage (S3 API) |
| Email | console | Brevo HTTPS API |
| Cache | LocMem | LocMem, or Redis if configured |
| Static | served by Django | WhiteNoise, minified |

Bugs that appear only in production almost always come from this table:
case-sensitive ordering in Postgres that SQLite tolerates, and file paths that
assume a disk which does not survive a redeploy.


---

## Background jobs — not done, and why

The evaluators asked for report generation, email sending and large
spreadsheet imports to move into background jobs. They are right that those
are the three slow paths. It has not been done, and the reason is
infrastructure rather than reluctance.

A background job needs two things this deployment does not have: a **worker
process** separate from the web service, and a **broker** for them to talk
through. Render's free plan gives one web service, no worker service and no
managed Redis. Running a worker inside the web container would not survive the
container being suspended after fifteen minutes idle, which is the normal state
of this deployment — jobs would be accepted and then silently lost, which is
worse than a slow request that at least finishes.

What has been done instead, within that constraint:

- **Email already does not block a decision.** Sends go through Brevo's HTTPS
  API with a timeout, and `api/notify.py` swallows a failure rather than
  rolling back the approval that triggered it. The office's action completes
  whether or not the message goes out.
- **Reports are scoped and cached.** Every masterlist query is now filtered to
  one term, so the work is bounded by a semester's scholars rather than by
  every record ever entered. Analytics results are cached for ten minutes.
- **Volume is tested rather than assumed.** `api/test_report_volume.py`
  renders the report, the spreadsheet and the PDF against sixty scholars and
  asserts the query count does not grow with the list.

What it would take to do properly: a Render Starter plan or equivalent, a
second service running `celery -A config worker`, and `REDIS_URL` pointing at
a shared instance. That last variable is already read by `config/settings.py`
for the cache and the rate limiter, so the configuration seam exists.
