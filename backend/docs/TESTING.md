# Testing

How this system is tested, and where to find the evidence for each claim.
Organised against ISO/IEC/IEEE 29119-4:2021 so a reviewer can check each
technique against real output rather than taking a description on trust.

---

## Running everything

```bash
python manage.py test api
```

Around 1,600 cases, roughly 10–20 minutes. Do **not** pass `--parallel` on
Python 3.14: the runner dies with `TypeError: cannot pickle 'traceback' object`
the moment any case errors, which hides the actual failure behind a
serialisation crash.

To regenerate every report referenced below:

```bash
python tools/quality_report.py
```

Output lands in [`quality/`](quality/). `quality/SUMMARY.md` carries the
current headline figures; the numbers quoted in this document come from there
and are regenerated, not hand-maintained.

---

## How these tests are written

Two conventions are worth knowing before reading them.

**Tests assert behaviour, not markers.** Checking that an attribute or a CSS
class is present passes just as happily against a dead feature. Where it
matters, a test asserts the thing that *implements* the behaviour, and that
only one thing does. `api/test_filters_actually_filter.py` is the clearest
example: it does not check that a filter control is rendered, it checks that
the rows change.

**Test names are sentences.** `test_last_terms_application_does_not_block_this_terms`
states a rule about the system. A failure list therefore reads as a list of
broken rules rather than a list of broken functions.

---

## 29119-4 techniques

### Statement coverage — clause 5.2.1

Measured with branch mode on, over `api` and `config`, excluding migrations
and the test modules themselves.

```bash
python -m coverage run manage.py test api
python -m coverage report
```

Per-file figures in `quality/coverage/report.txt`, which is committed.
Line-by-line detail — the artefact to open to check any individual claim about
a statement being reached — is `quality/coverage/html/index.html`, which is
built by the command above rather than committed.

Deliberately uncovered, and why:

- `config/wsgi.py`, `config/asgi.py` — process entry points with no logic.
- Migration files — generated, and exercised by every test run's schema build.
- Storage and email branches that only execute against Supabase or Brevo. They
  are covered by `test_check_storage.py` and `test_brevo_backend.py` at the
  seam rather than against the live service.

### Branch and decision coverage — clause 5.2.2

`branch = true` in [`pyproject.toml`](../pyproject.toml), so every decision is
recorded for both outcomes and any branch taken only one way is reported as
partial. The HTML report marks those partial branches directly.

The decision points that carry real consequence have named tests either side:

| Decision | True | False |
|---|---|---|
| Employee already applied this term | `test_a_pending_application_for_this_term_still_blocks` | `test_last_terms_application_does_not_block_this_terms` |
| Sign-in throttle tripped | `test_the_ninth_wrong_password_is_refused_outright` | `test_a_handful_of_wrong_passwords_are_still_answered_normally` |
| Account may hold a second scholarship | `api/test_second_scholarship.py` | same module |
| Application window open | `api/test_application_window.py` | same module |
| Decision already final | `api/test_decision_is_final.py` | same module |

### Condition coverage — clause 5.2.3

Compound conditions are tested per operand where the operands are independent.
The eligibility rules are where this matters, because each is a conjunction of
criteria that must each be able to fail on its own:

- `api/test_tes_ranking.py` — Listahanan, 4Ps, solo-parent and income tested
  separately, including the boundaries.
- `api/test_affirmative_target_groups.py` — each of the four target groups
  admits and excludes independently.
- `api/test_staff_recommender.py` — appointment type, years of service and
  existing qualification each gate on their own.
- `api/test_qualification.py` — the combined verdict.

Boundary values are tested at the edge and one step either side, rather than
only in the middle of each range. `api/test_analytics_charts.py` does the same
for the GWA bands: every ceiling is tested at the value and one step past it.

What this is **not**: `coverage.py` measures branch coverage, not condition or
MC/DC coverage. Nothing here is a measurement of clause 5.2.3 — these are
table-driven cases chosen to exercise each operand, which is evidence of a
different kind. Claiming otherwise would be claiming a number nobody computed.

### Path coverage — clause 5.2.4

Full path coverage is not achievable for every function and it would be
dishonest to claim it. Cyclomatic complexity sets the floor on how many paths
exist, so it is measured and reported instead:

```bash
python -m radon cc api config -s -a --exclude "*/migrations/*,api/test_*.py"
```

Results in `quality/complexity.txt`, ranked worst first in
`quality/SUMMARY.md`. A block scoring *n* has at least *n* independent paths;
that number is the size of the job, and publishing it is more useful than an
unqualified claim of coverage.

The independent paths **are** enumerated and tested for the modules where a
wrong answer changes who receives money — `tes_ranking.py`,
`affirmative_ranking.py`, `staff_ranking.py` and the window and eligibility
guards. Those modules are deliberately small and low-complexity for exactly
this reason.

The same reasoning now applies to the analytics dashboard.
`_build_analytics_context` ran at cyclomatic complexity 101 with every chart's
logic in a closure nothing could reach; stating one case for one chart meant
building a request and reading a rendered page. The chart logic is in
`api/analytics_charts.py` as plain functions, and `api/test_analytics_charts.py`
walks their paths directly — 38 cases in 0.03 seconds, against a builder that
now scores 22.

### Loop testing — clause 5.2.5

Loops are tested at zero, one and many iterations. Zero is the case that
actually breaks in practice, because a report or ranking over an empty set is
what happens on a fresh deployment and at the start of every term:

- `api/test_analytics_empty_charts.py` — every chart with no data at all.
- `api/test_unawarded_students.py` — empty, single and populated lists.
- `api/test_import_all_sheets.py` — workbooks of one sheet and of many.
- `api/test_report_volume.py` — reports over a large scholar list, which is the
  "many" end and the case the office asked to see proved.

### Data flow testing — clause 5.2.6

Definition–use anomalies are caught statically rather than by inspection:

```bash
python -m ruff check .
```

Covers unused bindings (`F841`), undefined names (`F821`), unused imports
(`F401`), shadowed definitions, loop variables captured by closures (`B023`),
loop control variables never read (`B007`), and `zip` over sequences of
unequal length (`B905`). Current output in `quality/lint.txt`.

Data crossing a module boundary is tested at the boundary:
`api/test_import_fills_custom_columns.py`, `api/test_scholar_columns.py` and
`api/test_registration_data_flow.py` each assert that what one component wrote
is what the next one reads.

`api/fixtures_registration.py` was cited here as a third piece of evidence and
is not one. It builds the registration payload the tests above post; it
contains no assertions and proves nothing on its own. It was named
`test_registration_payload.py`, which is what made it look like a test.

### Error and exception handling — clause 5.2.7

Custom handlers for 400, 403, 404, 500 and CSRF failure live in
[`api/error_views.py`](../api/error_views.py) with templates in
`templates/errors/`. The CSRF page offers a retry rather than a dead end.
Tested in `api/test_error_pages.py`.

Invalid input is tested rather than assumed: every upload path is given an
oversized file and a disallowed extension, and every form is submitted empty.
`api/test_media_access.py` additionally asserts that a document request from
the wrong account is refused rather than merely unlinked.

Exception chaining (`raise ... from`) is enforced by `ruff`'s `B904`, so a
re-raise cannot silently discard the original cause.

**A handler must not leak what it caught, and must not leave half a write
behind.** `api/test_import_atomicity.py` covers both on the spreadsheet import:

- It makes `ScholarListImport.save` throw and asserts zero scholar rows
  survive — the import either files completely or files nothing.
- It raises an exception whose text contains a password-failure message, a
  Supabase hostname and a server path, and asserts none of them reach the
  redirect URL while all of them reach the log. A generic sentence is what the
  office is shown.
- It asserts a failed import for one term does not delete another term's rows.

`api/test_award_integrity.py` covers the constraints that stop a duplicate
benefit at the database rather than in whichever view remembered to check.

---

## Coverage of things Python cannot reach

Backend tests cannot prove that a dialog opens or that a table filters in a
browser. Two layers address this:

**Source-level assertions.** `api/test_analytics_js_syntax.py` parses the
page scripts, `api/test_stylesheet.py` and `api/test_brand_colours.py` check
the stylesheet, and `api/test_site_chrome.py` checks that every page carries
the navigation it should. These catch a broken script or a missing include,
but not a broken interaction.

**Browser tests.** See [`tests_browser/README.md`](../tests_browser/README.md). These drive a
real browser over form submission, confirmation dialogs, mobile navigation,
file upload, search and filtering, keyboard navigation and modal behaviour —
the list the evaluators asked for. They are kept out of `manage.py test`
because they need a browser installed, and are run separately.

---

## Known gaps

Stated rather than papered over:

- **No load testing in CI.** `python manage.py seed_load --students 500`
  generates a realistic dataset and `api/test_report_volume.py` asserts the
  report still renders, but sustained concurrent load is not measured.
- **No mutation testing.** Coverage says a line ran, not that a test would have
  noticed it being wrong.
- **Email and object storage are tested at the seam**, not against the live
  services.
- **Condition and MC/DC coverage are not measured.** `coverage.py` measures
  statement and branch coverage and nothing finer, so the condition-coverage
  claims above rest on table-driven cases rather than on a tool. They are real
  cases, but they are evidence of a different kind and should not be read as a
  measurement.
- **`_build_analytics_context` is still the largest function here.** It was
  cyclomatic complexity 101 and is now 22, with the chart logic extracted to
  `api/analytics_charts.py` where each piece is a plain function with a test
  of its own (`api/test_analytics_charts.py`, 38 cases, 0.03 s). What is left
  is the term selection and the orchestration, which is the part that genuinely
  needs a database.
- **Type coverage is partial.** `mypy` runs in CI over the modules that decide
  money plus the ones written with annotations from the start — see
  `[tool.mypy]` in `pyproject.toml`. The rest of the codebase is unannotated
  and unchecked. Widening that file list is how the rest gets adopted; it
  already found one real defect, a `None` rule dereferenced in
  `staff_ranking.Evaluation.permanent_verdict`.
