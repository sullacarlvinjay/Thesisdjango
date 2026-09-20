# Quality reports

Generated, not hand-written. Regenerate everything here with:

```bash
python tools/quality_report.py
```

| File | What it is |
|---|---|
| `SUMMARY.md` | Headline coverage, complexity and lint figures |
| `coverage/report.txt` | Statement and branch coverage per file |
| `coverage/html/index.html` | Line-by-line coverage, including partial branches |
| `coverage/coverage.xml` | Cobertura XML, for CI tooling |
| `complexity.txt` | Cyclomatic complexity per block, worst first |
| `maintainability.txt` | Maintainability index per module |
| `lint.txt` | Every `ruff` finding |

The raw `.coverage` database these are built from is machine-local and is not
committed; the reports are, because they are the evidence a reviewer opens.
