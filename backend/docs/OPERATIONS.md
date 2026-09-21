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
5. `find_duplicate_awards` — reports anything predating migration `0096`
6. `check` — configuration warnings that would otherwise surface as 500s
7. `check_storage` — one round trip against the upload bucket

`set -o errexit` is at the top for a reason: without it a failed
`collectstatic` or a half-applied migration would still be followed by a
"successful" deploy.

### When a migration refuses to apply

Migration `0096_award_integrity` checks for repeated award numbers before it
adds the unique constraints, and stops the build if it finds any. Read the
list in the build log: it names the table, the programme, the term and the
number, and how many rows carry it. Nothing on the server can settle these —
which of two rows is the real award is a question for the office.

Note the ordering above. Steps 5 to 7 are *after* `migrate`, so a build that
stops at step 3 never reaches them, and Render's free plan has no shell to run
them by hand. That is why the refusal prints the rows instead of naming a
command; do not move the report earlier to compensate, because it queries
through the current models and would crash on any column a pending migration
has not added yet.

To see the same rows without waiting for a deploy, run these in the Supabase
SQL editor. They are what the constraints key on, exactly:

```sql
select a.scholarship_id, s.name, a.school_year, a.semester, a.award_number,
       count(*)
from api_application a join api_scholarship s on s.id = a.scholarship_id
where a.award_number <> ''
group by a.scholarship_id, s.name, a.school_year, a.semester, a.award_number
having count(*) > 1;

select scholarship_type, term_label, award_number, count(*)
from api_scholarshiplinkrequest
where status = 'Approved' and award_number <> ''
group by scholarship_type, term_label, award_number
having count(*) > 1;
```

The imported archive is not one of them. It is a copy of a funder's
spreadsheet, so it holds whatever the funder sent and no constraint is built
over it — `find_duplicate_awards` reports the repeats and the build carries
on. This query finds them, but nothing it returns will ever stop a deploy:

```sql
select scholarship_type, term_label, award_number, count(*)
from api_importedscholar
where award_number <> ''
group by scholarship_type, term_label, award_number
having count(*) > 1;
```

A blank `school_year` or `semester` counts as a value, not as a wildcard, so a
batch of imported rows stamped with no term all share one group and collide
with each other. The build log prints those as `(blank)`. Where that is the
cause, stamping the term is the fix, not deleting the awards.

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

## Background jobs

[`api/jobs.py`](../api/jobs.py) is a thread pool inside the web process. Mail
and spreadsheet imports go on it; report downloads deliberately do not.

**Why not Celery.** A broker-backed queue needs a worker service and a broker,
and Render's free plan gives one web service, no worker service and no managed
Redis. Celery configured here would be configuration that cannot run. The pool
needs neither: `render.yaml` already starts gunicorn `--workers 1 --threads 8`,
so threads are this deployment's concurrency model, and putting work on one
hands the request thread straight back.

**What it does not do is survive a restart.** Render suspends the container
after fifteen minutes idle and replaces it on every deploy, and the queue goes
with it. So anything whose loss would otherwise be silent writes a
`BackgroundJob` row *before* it is queued. A row still marked `running` long
after the process came back is one nobody is going to finish, and the archive
page says so rather than spinning. Nothing retries by itself; the office does,
from a row it can see.

| Setting | Default | What it is |
|---|---|---|
| `BACKGROUND_WORKERS` | `2` | Threads draining the queue. Each can be holding a workbook, and the instance has 512 MB for all of it |
| `BACKGROUND_QUEUE_LIMIT` | `50` | How many may be waiting. Past it, a job runs inline — only as bad as it was before the pool existed |
| `BACKGROUND_JOBS_SYNCHRONOUS` | on under tests | Runs every job on the calling thread, so a test asserts against a finished state rather than a race |

### What moved, and what did not

- **Mail.** Every send but one now leaves on the pool. The exception is the
  account decision, which reports its outcome in the response — it warns the
  office when the applicant could not be reached, and a queued send has no
  outcome to give it. The win is on the public registration path: a student
  registering with declarations used to pay for a confirmation email *plus* one
  message per office account, in series, before their own page loaded.
- **Spreadsheet imports.** `/vpsea/archives/import/` files a `BackgroundJob`,
  queues the read and redirects with the job id. The archive page shows a
  progress banner and polls `/vpsea/archives/import/<id>/status/` until it is
  done. This is the one that needed it: a workbook large enough to take longer
  than gunicorn's 120-second timeout used to have the request killed out from
  under it mid-read.
- **Report downloads stay in the request, on purpose.** The response *is* the
  file, so backgrounding one converts a download into a two-step wait for a
  link. Measured on this machine at 1,000 approved scholars: docx 2.7s, xlsx
  0.6s, pdf 1.4s — nowhere near the timeout. Revisit it if a term ever gets an
  order of magnitude bigger.

Tests: `api/test_background_jobs.py` for the pool itself, including the
threaded path the rest of the suite deliberately does not run, and
`api/test_import_in_background.py` for the import and its status endpoint.
