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
| `backup` | Writes a restorable dump of the database plus a manifest of every upload it refers to. |
| `restore` | Loads a dump back. Refuses without `--yes`. |
| `find_duplicate_awards` | Lists students holding two benefits in one term, and award numbers recorded twice. |

---

## Backup and restore

This system is the record of who was awarded what. Losing it loses students'
Listahanan status, household income and disability records, and there is no
second copy anywhere in the university.

### What is backed up, and by what

| | Held by | Covered by |
|---|---|---|
| Database | Supabase Postgres | Supabase's own free-tier backups, **plus** `manage.py backup` |
| Uploaded documents | Supabase Storage bucket | The bucket's own retention, **not** by `manage.py backup` |
| Code and migrations | GitHub | Git |

`manage.py backup` deliberately does not copy the documents. It writes a
manifest instead — every stored filename the database expects to find, with
its size — so a restore can say which documents are missing rather than the
office discovering it one scholar at a time.

### Targets

| | Target | Why |
|---|---|---|
| RPO — how much data a failure may lose | **24 hours** | Supabase's free tier takes a daily snapshot. A term's intake is weeks of work, so a day is the most that may go. |
| RTO — how long a restore may take | **4 hours** | Restore is one command over a dump of a few megabytes; the hours are for noticing, deciding and verifying, not for the transfer. |

Both are stated so they can be missed visibly. Neither is met by Supabase's
free tier on its own, because a daily snapshot nobody has restored from is not
a tested recovery path — which is what the rest of this section is for.

### Taking a backup

```bash
python manage.py backup --label before-rollover
```

Writes two files into `backups/`:

- `srms-<timestamp>-<label>.json.gz` — every application table, gzipped JSON.
  Portable between SQLite and Postgres, which matters because the deployed
  database is Postgres and every rehearsal happens on SQLite. `pg_dump` is not
  in the deploy container.
- `srms-<timestamp>-<label>.manifest.txt` — one line per uploaded file:
  model, field, stored name, size. A size of `-1` means the database expects a
  file the bucket does not have.

Take one **before every migration that changes data**, and before a term
rollover. Render's disk does not survive a redeploy, so copy the file off the
instance — this is why the command writes a small, single file.

### Restoring

```bash
python manage.py restore backups/srms-20260920-214456-before-rollover.json.gz --yes
```

- Without `--yes` it prints which database it would overwrite and stops. That
  guard exists because the realistic moment for this is an operator under
  pressure typing quickly at a production shell.
- `--flush` empties every table first. Without it, rows whose primary key is
  not in the backup stay where they are — which is what you want when
  recovering one bad migration, and not what you want when rebuilding from
  scratch.
- Uploaded documents are not in the file. Check the matching `.manifest.txt`
  against the bucket before telling the office it is back.

### Rehearsing it

The restore is exercised on every CI run: `api/test_backup_restore.py` writes
a real backup, deletes the student records and the awards, restores them, and
asserts a household income and an approved award come back with the values
they went in with. A procedure nobody has run is a hope, not a recovery plan.

To rehearse by hand against a copy of production data:

```bash
python manage.py backup --label rehearsal
python manage.py restore backups/srms-<timestamp>-rehearsal.json.gz --yes --flush
python manage.py find_duplicate_awards
```

The last line is the check that the restore is coherent, not merely loaded.

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
