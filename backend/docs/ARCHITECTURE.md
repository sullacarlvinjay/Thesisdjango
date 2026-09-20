# Architecture

A single Django app, `api`, serving server-rendered HTML to four portals plus a
Django REST Framework API. There is no separate frontend build beyond a
Tailwind stylesheet that is generated locally and committed.

---

## Request flow

```
browser
  │
  ├─ SecurityMiddleware            HTTPS redirect, HSTS, nosniff
  ├─ WhiteNoiseMiddleware          static files, pre-minified
  ├─ SelectiveGZipMiddleware       compresses text, skips already-compressed media
  ├─ ConditionalGetMiddleware      304s on unchanged pages
  ├─ CorsMiddleware
  ├─ SessionMiddleware
  ├─ CsrfViewMiddleware
  ├─ AuthenticationMiddleware
  ├─ ReleaseVerifiedAccountMiddleware   signs in an account the office just approved
  ├─ ApiCacheHeadersMiddleware          no-store on /api/ responses
  │
  └─ view  ──▶  template  ──▶  HTML
```

`SelectiveGZipMiddleware` and `ApiCacheHeadersMiddleware` are in
[`api/middleware.py`](../api/middleware.py).

---

## View modules

`student_views.py` used to hold all four portals in 6,176 lines. It is now a
re-export surface; the code lives in modules that each cover one area. Imports
run strictly downward in this list, so there are no cycles.

| Module | Lines | Holds |
|---|---|---|
| `views_shared.py` | ~490 | Role decorators, term helpers, column pickers, spreadsheet readers used by more than one portal |
| `views_auth.py` | ~590 | Landing page, sign-in, registration, email confirmation |
| `views_student.py` | ~545 | Student dashboard, application, renewal, profile |
| `views_staff.py` | ~425 | Employee application, renewal, profile |
| `views_partner.py` | ~455 | Partner-office scholar lists and imports |
| `views_declarations.py` | ~315 | Review of scholarships declared during registration |
| `views_archives.py` | ~1080 | Scholar records, term rollover, spreadsheet import and export |
| `views_analytics.py` | ~560 | The SDSO analytics dashboard |
| `views_reports.py` | ~420 | Masterlist report rendering, PDF and Excel download |
| `views_ranking.py` | ~235 | Eligibility recommendation and ranking pages |
| `views_vpsea.py` | ~1230 | The rest of the SDSO portal: accounts, students, scholarships, partners |

Why a re-export surface rather than rewriting every import: `api/urls.py` and
73 test modules imported from `student_views`. Keeping the name resolvable let
the split land without touching any of them, and the tests then proved the move
was behaviour-preserving. New code should import from the specific module.

---

## Domain model

The models are in one file, [`api/models.py`](../api/models.py). The shapes
worth knowing before reading it:

### Two record types, deliberately distinct

**`Application`** is a student applying through the portal for a scholarship
that exists in the catalogue. It points at a `StudentProfile` and a
`Scholarship`.

**`ApplicantRecord`** is a person in a programme the office administers
directly — Affirmative Action, the Staff Scholarship, or anything arriving by
spreadsheet import. It carries its own name and email rather than requiring a
portal account, because most of these people never had one.

They are not merged because a scholar imported from a partner's spreadsheet has
no account, no profile and no application, and forcing one into existence is
what produced phantom student records in earlier versions.

### Detail rows

`ApplicantRecord` and `StudentProfile` spread their fields across satellite
tables — `ApplicantEnrollment`, `ApplicantStaffEligibility`,
`ApplicantEmployment`, `ApplicantAffirmativeEligibility` and so on — reached
through the `DetailField` descriptor:

```python
is_nsu_staff = DetailField('staff_eligibility', 'is_nsu_staff')
```

Reading or assigning `record.is_nsu_staff` works as if it were a local field.
**It is a Python property, not a model field**, so it cannot be used in a
queryset. Filter through the relation instead:

```python
ApplicantRecord.objects.exclude(staff_eligibility__is_nsu_dependent=True)
```

This is the single easiest mistake to make in this codebase. A filter on the
descriptor name raises `FieldError` rather than failing quietly, so the tests
catch it, but it is worth knowing before you write the query.

### Terms

Anything that happens in a semester inherits `TermStamped`: `term_label`
(`'26-1'`), `school_year` (`'2026-2027'`) and `semester`. `fill_term()` stamps
a new row with whatever `SystemSettings.academic_year` says at the time.

**Any query that decides whether someone may act now must filter on the term.**
A lookup that matches on identity alone will keep finding last semester's row.
That was the cause of employees being told they had already applied when they
had not; see `_staff_application_for` in
[`api/views_staff.py`](../api/views_staff.py).

---

## The recommender

Rule-based filtering. Each programme has a module that reads the applicant data
already on file, applies the published criteria, and returns a ranked list with
a stated reason per row.

| Programme | Module | Ranks by |
|---|---|---|
| Tertiary Education Subsidy | [`api/tes_ranking.py`](../api/tes_ranking.py) | Listahanan, 4Ps, solo-parent dependency, income |
| Affirmative Action | [`api/affirmative_ranking.py`](../api/affirmative_ranking.py) | SHS GPA and SUC entrance exam, within target groups |
| BiPSU Staff Scholarship | [`api/staff_ranking.py`](../api/staff_ranking.py) | Appointment type, years of service, existing qualifications |

Each returns rows plus an excluded count and the reason for each exclusion, so
the office can see who was filtered out and why rather than only who survived.
No approval, rejection or disbursement happens here.

---

## Reports

[`api/masterlist_report.py`](../api/masterlist_report.py) builds one context
covering every scholarship slot for a term. Two renderers consume it:

- [`api/report_pdf.py`](../api/report_pdf.py) — ReportLab, for print
- `views_reports.py` — openpyxl, for the Excel download

[`api/doc_convert.py`](../api/doc_convert.py) fills `.docx` templates from
`templates/docx/` for the forms the office has to submit on paper.

---

## Storage

| | Local | Deployed |
|---|---|---|
| Database | SQLite | Supabase PostgreSQL (pooler host) |
| Uploads | `media/` on disk | Supabase Storage over the S3 API |
| Static | `staticfiles/` | WhiteNoise, minified at build |

[`api/storage.py`](../api/storage.py) selects the backend and minifies CSS and
JS during `collectstatic`. `media/logos` is served from disk in both
environments — scholarship seals are committed, not uploaded.

The gap between the two columns is where environment-specific bugs live. A file
path that works locally may not survive a redeploy in production, because the
container's disk does not.


---

## Paging

Nothing returns a whole table any more. Two mechanisms, because the two
surfaces need different things.

**HTML tables** use `paginate()` from
[`api/views_shared.py`](../api/views_shared.py). It takes a queryset and
returns the page's rows plus the `Page`, the parameter name and the rest of
the query string already encoded — so the links keep the caller's search, tab
and filters instead of silently resetting them. The parameter is named per
table (`?pending_page=`, `?decided_page=`), so two tables on one screen do not
move each other. Controls render from `templates/_pagination.html`.

**REST endpoints** use `SRMSPagination` from
[`api/pagination.py`](../api/pagination.py): 50 rows by default, `?page_size=`
up to 200. List responses are therefore `{count, next, previous, results}`
rather than a bare array — **a breaking change** for anything reading the old
shape; the rows are under `results`.

The one exception is `/api/vpsea/ranking/`. Its response is an envelope — the
ranking plus the counts the office reads beside it — and DRF's envelope would
replace that one and take the summary with it. So it pages by hand with
`?limit=` and `?offset=`, keeps every count, and reports
`recommendation_count` for the total.

The reason any of this matters is not elegance. The container has 512 MB, and
an unbounded list has to be serialised entirely into it before a single byte
reaches the client.
