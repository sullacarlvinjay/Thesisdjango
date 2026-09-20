# Browser tests

Behaviour the Django suite cannot reach, because it lives in JavaScript: a
dialog opening, a table filtering, a sidebar closing on Escape, a focus ring
appearing. A page whose scripts have silently stopped working still renders
perfectly and still passes every backend test, which is the gap these close.

## Running them

```bash
pip install -r requirements-dev.txt
```

```bash
python -m playwright install chromium
```

```bash
python manage.py test tests_browser
```

Watch them run in a visible browser:

```bash
HEADED=1 python manage.py test tests_browser
```

They are outside the `api` package on purpose, so `python manage.py test api`
still runs on a machine with no browser installed. Without Playwright the
whole suite skips with an instruction rather than erroring.

## What is covered

| File | Covers |
|---|---|
| `test_forms.py` | Form submission, validation, the address surviving a refusal, no script errors on load |
| `test_dialogs.py` | Confirmation dialogs intercepting destructive actions, cancel, Escape, focus handling; preview modals |
| `test_navigation.py` | Mobile sidebar open/close, `aria-expanded`, Escape, backdrop, no sideways scroll at 390px; Tab order, visible focus ring, Enter-to-submit |
| `test_tables.py` | Search narrowing rows, clearing restoring them, empty-result message, column filters, the action column staying on screen |
| `test_uploads.py` | File attaching, `accept` advertised, oversized upload refused by the **server** with the page's own check disabled |

## How these are written

**They assert what the user gets, not what the markup says.** The search test
counts rows that are actually visible before and after typing, and fails if the
number does not change. Asserting that a search box exists would pass against a
box wired to nothing.

**They skip rather than fail when a control is absent.** A test that cannot
find the thing it tests reports "no filter on this page" instead of a red
failure that looks like a regression. Read a run's skip list — a control that
has quietly disappeared shows up there.

**Server-side enforcement is tested with the client-side check removed.** The
oversized-upload test strips the `accept` attribute before submitting, because
the point is whether the server refuses, not whether the browser does.
