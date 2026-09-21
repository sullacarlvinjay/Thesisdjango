# BiPSU SRMS — Scholarship Record Management System

A web application for Biliran Province State University that centralises
scholarship information, scholar records and eligibility recommendation for the
Student Development and Services Office (SDSO), students, employees and partner
offices.

Built for the thesis *Scholarship Record Management with Eligibility Recommender
for Higher Education Institution*.

**Live:** <https://backend-vb5d.onrender.com/>

> The deployment runs on Render's free plan, which suspends the container after
> about 15 minutes without traffic. The first request after an idle period waits
> roughly 50 seconds for the container to start; every request after that is
> served in well under a second. If your first page load is slow, that is the
> cold start, not the application.

---

## Contents

| Document | What is in it |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Module map, request flow, data model |
| [docs/TESTING.md](docs/TESTING.md) | Test design and coverage, mapped to ISO/IEC/IEEE 29119-4 |
| [docs/SECURITY.md](docs/SECURITY.md) | Authentication, authorisation, throttling, audit trail |
| [docs/OPERATIONS.md](docs/OPERATIONS.md) | Deployment, environment variables, management commands |
| [OPTIMIZATION.md](OPTIMIZATION.md) | Performance work already carried out |
| [CHANGES.md](CHANGES.md) | Development log |

---

## Requirements

| | Version | Note |
|---|---|---|
| Python | 3.13 | Pinned on Render via `PYTHON_VERSION`. 3.14 also works locally. |
| Node | 20+ | Only to regenerate Tailwind CSS. Not needed to run the app. |
| Database | SQLite (local) / PostgreSQL (deployed) | No local Postgres required. |

---

## Running it locally

```bash
git clone <this repository>
cd backend
python -m venv venv
```

Activate the environment — `venv\Scripts\activate` on Windows, or
`source venv/bin/activate` on macOS and Linux — then:

```bash
pip install -r requirements-dev.txt
```

Create a `.env` from the annotated template. Every variable is optional for a
local run; the defaults give you SQLite, local file uploads and a console email
backend:

```bash
cp .env.example .env
```

Apply the schema and create the office account:

```bash
python manage.py migrate
```

```bash
python manage.py bootstrap
```

Load a realistic sample of scholarships, students and applications:

```bash
python manage.py seed
```

Start the server:

```bash
python manage.py runserver
```

Then open <http://127.0.0.1:8000/>.

`bootstrap` reads `SDSO_EMAIL` and `SDSO_PASSWORD` from the environment and
skips any office whose password is unset rather than inventing a guessable one.
Set both in `.env` before running it, or create an account yourself with
`python manage.py createsuperuser`.

---

## Running the tests

```bash
python manage.py test api
```

The suite is large — around 1,600 cases — and takes roughly 10–20 minutes on a
typical laptop. To run one area while working:

```bash
python manage.py test api.test_tes_ranking api.test_staff_recommender
```

Do **not** pass `--parallel` on Python 3.14: the runner fails with
`TypeError: cannot pickle 'traceback' object` whenever a case errors, which
hides the real failure.

Every push runs the suite, the linter, `mypy`, the OpenAPI schema check, a
missing-migration check and branch coverage on GitHub Actions — see
[.github/workflows/tests.yml](.github/workflows/tests.yml). All of them are
gates; none is advisory.

`mypy` is scoped to the modules that decide money plus the ones written with
annotations from the start — see `[tool.mypy]` in `pyproject.toml`. Widening
that file list is how the rest of the codebase gets adopted.

### Coverage and static analysis

```bash
python tools/quality_report.py
```

That one command runs the suite under branch coverage, measures cyclomatic
complexity and maintainability, lints the source, and writes everything to
`docs/quality/`. See [docs/TESTING.md](docs/TESTING.md) for what each report
answers and the current figures.

---

## Roles

The application serves four kinds of account. A signed-in user is routed to
their own portal; the decorators guarding each area are in
[`api/views_shared.py`](api/views_shared.py).

| Role | Portal | Who |
|---|---|---|
| `student` | `/student/` | Enrolled students applying for and renewing scholarships |
| `nsu_staff` | `/nsu-staff/` | Faculty and employees applying for the BiPSU Staff Scholarship |
| `vpsea` | `/vpsea/` | The SDSO office — records, review, reports, analytics |
| `partner` | `/partner/` | External partner offices with their own scholar lists |

Only VPSEA and UniFAST have portals of their own. Every other funder's data
arrives as a spreadsheet import.

---

## What the eligibility recommender does

A rule-based filter, not a model. It reads the applicant data already on file,
tests it against the published criteria for a programme, and returns a ranked
list with the reason for each placement. It covers three programmes:

- **Tertiary Education Subsidy (TES)** — [`api/tes_ranking.py`](api/tes_ranking.py)
- **Affirmative Action Scholarship** — [`api/affirmative_ranking.py`](api/affirmative_ranking.py)
- **BiPSU Staff Scholarship** — [`api/staff_ranking.py`](api/staff_ranking.py)

It recommends and ranks. It does not approve, reject or disburse — those stay
with the office.

---

## The REST API

Token-authenticated, under `/api/`. **List endpoints are paged**: responses are
`{count, next, previous, results}`, 50 rows by default, `?page_size=` up to
200. `/api/vpsea/ranking/` is the exception — it carries a summary alongside
the rows, so it pages with `?limit=` and `?offset=` and keeps its counts. See
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#paging).

**The contract is published, not described.** An OpenAPI 3.0 schema is
generated from the views themselves by `drf-spectacular`:

| Path | What |
|---|---|
| `/api/schema/` | The OpenAPI document |
| `/api/docs/` | Swagger UI, for trying a call |
| `/api/redoc/` | ReDoc, for reading |

All three need a token, like everything else under `/api/`.

**Rate limits.** `/api/auth/login/` and `/api/auth/register/` share their
allowance with the `/login/` and `/register/` forms rather than keeping a
second one — eight wrong passwords on either refuses the ninth on both.
Everything else under `/api/` has a looser ceiling, 60/hour anonymous and
1000/hour per token. See [docs/SECURITY.md](docs/SECURITY.md#resistance).

Generating it in CI is a gate: `manage.py spectacular --fail-on-warn` fails the
build on an endpoint with no declared response shape, so a new endpoint cannot
ship undocumented. `api/test_openapi_schema.py` goes further and compares the
documented shape against what each view actually returns, because a schema that
has drifted from the API is worse than none.

---

## Layout

```
api/                     the single Django app
  views_auth.py          landing, sign-in, registration, email confirmation
  views_student.py       student portal
  views_staff.py         employee portal
  views_partner.py       partner-office portal
  views_vpsea.py         SDSO portal
  views_archives.py      scholar records, term rollover, spreadsheet import
  views_analytics.py     SDSO analytics dashboard
  views_reports.py       masterlist reports
  views_ranking.py       eligibility recommendation and ranking
  views_declarations.py  review of scholarships declared at registration
  views_shared.py        helpers used by more than one portal
  student_views.py       re-export surface kept for existing imports
  views.py               the REST API (Django REST Framework)
  api_schema.py          response shapes for the hand-written API views
  analytics_charts.py    the chart logic, with no database in it
  jobs.py                the background thread pool
  ratelimit.py           throttling, shared by the forms and the REST API
  mfa.py                 time-based one-time passwords (RFC 6238)
  models.py              every model
  fixtures_*.py          shared setup for the tests, not tests themselves
  test_*.py              the test suite, one module per behaviour
config/                  settings, URLs, WSGI
templates/               server-rendered HTML, one directory per role
static/css, static/js    stylesheet and page scripts
tools/                   quality reporting
docs/                    architecture, testing, security, operations
```

Styling rule: CSS belongs in `static/css/srms.css` and JavaScript in
`static/js/`. Templates carry structure only. When you change either, bump the
`?v=` query on the `<link>` or `<script>` that loads it, or browsers will serve
the old copy.

That rule is now enforced by the Content-Security-Policy rather than by
convention: `style-src` is `'self'`, so a `style="…"` attribute added to a
template will simply not be applied by the browser. Reach for one of the
`u-*` utility classes at the foot of `srms.css`, or add one. A value the
template only knows at render time goes in a `data-` attribute and is set from
JavaScript — `static/js/meter.js` is the worked example.

---

## Deployment

Render reads [`render.yaml`](render.yaml) and runs [`build.sh`](build.sh). Both
are commented in full. The short version:

- **Database** — Supabase Postgres over the *pooler* host. The direct host
  publishes no A record and Render's free tier has no IPv6 egress.
- **Uploads** — Supabase Storage over the S3 API. The free plan has no
  persistent disk, so anything written to the container is lost on redeploy.
- **Email** — Brevo's HTTPS API. Render blocks outbound SMTP ports on free web
  services, so a correct SMTP configuration silently sends nothing.
- **Static files** — WhiteNoise, minified during `collectstatic`.

See [docs/OPERATIONS.md](docs/OPERATIONS.md) for the full environment variable
list and the management commands.
