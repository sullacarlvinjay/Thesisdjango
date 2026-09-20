# Quality reports

Generated, not hand-written. Regenerate everything here with:

```bash
python tools/quality_report.py
```

| File | What it is |
|---|---|
| `SUMMARY.md` | Headline coverage, complexity and lint figures |
| `coverage/report.txt` | Statement and branch coverage per file |
| `coverage/html/index.html` | Line-by-line coverage, including partial branches — **generated locally, not committed** |
| `coverage/coverage.xml` | Cobertura XML, for CI tooling |
| `coverage/coverage.json` | Machine-readable totals — **generated locally, not committed** |
| `complexity.txt` | Cyclomatic complexity per block, worst first |
| `maintainability.txt` | Maintainability index per module |
| `lint.txt` | Every `ruff` finding |

The raw `.coverage` database is machine-local and is not committed. Neither is
the HTML report or the JSON: together they are about 7 MB that git would store
again in full every time they are regenerated. Run the command above to build
them. The text reports are committed, because those are what a reviewer reads
first and they diff sensibly.
