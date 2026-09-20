"""Produce the evidence pack for the white-box evaluation.

Runs one command chain and leaves every artefact under ``docs/quality``:

==========================  ====================================================
Report                      Answers
==========================  ====================================================
``coverage/``               statement and branch coverage, per file and per line
``complexity.txt``          cyclomatic complexity, which bounds path coverage
``maintainability.txt``     the maintainability index per module
``lint.txt``                data-flow anomalies: unused, shadowed, unbound names
``SUMMARY.md``              the headline figures, regenerated on every run
==========================  ====================================================

Usage::

    python tools/quality_report.py            # everything
    python tools/quality_report.py --no-tests # reuse the last coverage data

The test pass is by far the slowest part. ``--no-tests`` re-reports from the
existing ``.coverage`` data so the static analysis can be iterated quickly.
"""

import argparse
import datetime
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / 'docs' / 'quality'
COVERAGE_DIR = OUT / 'coverage'
PY = sys.executable


def run(args, capture=True, check=False):
    """Run one tool, returning its combined output."""
    done = subprocess.run(
        [PY, '-m', *args], cwd=ROOT, text=True, check=check,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None)
    return done.returncode, (done.stdout or '')


def write(name, body):
    path = OUT / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding='utf-8')
    return path


def measure_tests():
    """Run the suite under branch coverage."""
    print('running the test suite under coverage — this takes a while...')
    for stale in ROOT.glob('.coverage*'):
        stale.unlink()
    code, _ = run(['coverage', 'run', 'manage.py', 'test', 'api', '-v', '1'],
                  capture=False)
    run(['coverage', 'combine'])
    return code


def coverage_reports():
    """Emit the coverage reports and pull out the headline totals."""
    COVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    _, text = run(['coverage', 'report'])
    write('coverage/report.txt', text)
    run(['coverage', 'html', '-q'])
    run(['coverage', 'xml', '-q'])
    run(['coverage', 'json', '-q'])

    totals = {}
    data = COVERAGE_DIR / 'coverage.json'
    if data.exists():
        totals = json.loads(data.read_text(encoding='utf-8')).get('totals', {})
    return text, totals


def complexity():
    """Cyclomatic complexity, worst first, plus the rank distribution."""
    _, text = run(['radon', 'cc', 'api', 'config', '-s', '-a',
                   '--exclude', '*/migrations/*,api/test_*.py'])
    write('complexity.txt', text)

    _, raw = run(['radon', 'cc', 'api', 'config', '-j',
                  '--exclude', '*/migrations/*,api/test_*.py'])
    ranks, worst = {}, []
    try:
        for path, blocks in json.loads(raw).items():
            if not isinstance(blocks, list):
                continue
            for block in blocks:
                ranks[block['rank']] = ranks.get(block['rank'], 0) + 1
                worst.append((block['complexity'], path, block['name']))
    except (ValueError, TypeError, KeyError):
        pass
    worst.sort(reverse=True)
    return ranks, worst[:10]


def maintainability():
    _, text = run(['radon', 'mi', 'api', 'config', '-s',
                   '--exclude', '*/migrations/*,api/test_*.py'])
    write('maintainability.txt', text)
    return text


def lint():
    _, text = run(['ruff', 'check', '.', '--output-format', 'concise'])
    write('lint.txt', text)
    _, stats = run(['ruff', 'check', '.', '--statistics'])
    return stats


def summarise(totals, ranks, worst, lint_stats):
    stamp = datetime.date.today().isoformat()
    statements = totals.get('num_statements', 0)
    branches = totals.get('num_branches', 0)
    covered = totals.get('covered_lines', 0)
    partial = totals.get('num_partial_branches', 0)
    covered_branches = totals.get('covered_branches', 0)

    def pct(part, whole):
        return f'{(100.0 * part / whole):.2f}%' if whole else 'n/a'

    rows = '\n'.join(
        f'| {rank} | {count} |'
        for rank, count in sorted(ranks.items()))
    worst_rows = '\n'.join(
        f'| {name} | `{path}` | {score} |' for score, path, name in worst)

    return f"""# Quality report

Generated {stamp} by `tools/quality_report.py`. Every figure here comes from a
tool run, not from an estimate; the raw output sits beside this file.

## Coverage

| Measure | Value |
|---|---|
| Statements | {statements} |
| Statements covered | {covered} ({pct(covered, statements)}) |
| Branches | {branches} |
| Branches covered | {covered_branches} ({pct(covered_branches, branches)}) |
| Partially covered branches | {partial} |
| Overall (statement + branch) | {totals.get('percent_covered_display', 'n/a')}% |

Per-file figures are in `coverage/report.txt`. `coverage/html/index.html` shows
every line and every branch outcome, and is the artefact to open when checking
a specific claim.

## Cyclomatic complexity

Complexity bounds path coverage: a function scoring *n* has at least *n*
independent paths, so the score is the number of cases full path coverage of it
would need.

| Rank | Blocks |
|---|---|
{rows}

Ranks are radon's: A is 1–5, B 6–10, C 11–20, D 21–30, E 31–40, F above 40.

### Highest-complexity blocks

| Block | File | Complexity |
|---|---|---|
{worst_rows}

## Lint

`ruff` over the whole project, covering unused and shadowed names, undefined
bindings, loop-variable capture and exception-chaining defects.

```
{lint_stats.strip()}
```

Full list in `lint.txt`.
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-tests', action='store_true',
                        help='reuse the existing coverage data')
    args = parser.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    if not args.no_tests:
        measure_tests()

    text, totals = coverage_reports()
    print(text.strip()[-800:])

    ranks, worst = complexity()
    maintainability()
    lint_stats = lint()

    path = write('SUMMARY.md', summarise(totals, ranks, worst, lint_stats))
    print(f'\nwrote {path.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
