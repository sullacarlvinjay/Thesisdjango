# Quality report

Generated 2026-09-20 by `tools/quality_report.py`. Every figure here comes from a
tool run, not from an estimate; the raw output sits beside this file.

## Coverage

| Measure | Value |
|---|---|
| Statements | 0 |
| Statements covered | 0 (n/a) |
| Branches | 0 |
| Branches covered | 0 (n/a) |
| Partially covered branches | 0 |
| Overall (statement + branch) | n/a% |

Per-file figures are in `coverage/report.txt`. `coverage/html/index.html` shows
every line and every branch outcome, and is the artefact to open when checking
a specific claim.

## Cyclomatic complexity

Complexity bounds path coverage: a function scoring *n* has at least *n*
independent paths, so the score is the number of cases full path coverage of it
would need.

| Rank | Blocks |
|---|---|
| A | 490 |
| B | 89 |
| C | 40 |
| D | 6 |
| E | 3 |
| F | 5 |

Ranks are radon's: A is 1–5, B 6–10, C 11–20, D 21–30, E 31–40, F above 40.

### Highest-complexity blocks

| Block | File | Complexity |
|---|---|---|
| _build_analytics_context | `api\views_analytics.py` | 86 |
| student_profile | `api\views_student.py` | 55 |
| nsu_staff_apply | `api\views_staff.py` | 55 |
| vpsea_report_download_excel | `api\views_reports.py` | 46 |
| vpsea_archive_add | `api\views_archives.py` | 42 |
| _rollover_fields | `api\views_archives.py` | 40 |
| vpsea_accounts | `api\views_vpsea.py` | 36 |
| vpsea_student_edit | `api\views_vpsea.py` | 32 |
| register_view | `api\views_auth.py` | 29 |
| vpsea_partners | `api\views_vpsea.py` | 27 |

## Lint

`ruff` over the whole project, covering unused and shadowed names, undefined
bindings, loop-variable capture and exception-chaining defects.

```
warning: The following rules have been removed and ignoring them has no effect:
    - UP038

11	E701 	multiple-statements-on-one-line-colon
 9	C901 	complex-structure
 6	DJ012	django-unordered-body-content-in-model
 4	E702 	multiple-statements-on-one-line-semicolon
 4	UP031	printf-string-formatting
Found 34 errors.
No fixes available (4 hidden fixes can be enabled with the `--unsafe-fixes` option).
```

Full list in `lint.txt`.
