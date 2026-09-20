# Security

What the application does to protect scholar data, and where the limits are.
Organised against the ISO/IEC 25010 security sub-characteristics so an
evaluator can check each one against the code.

---

## Confidentiality

**Role separation.** Four roles — `student`, `nsu_staff`, `vpsea`, `partner` —
each with a decorator that runs before the view body. `_vpsea_required` and
`_safe_next` are in [`api/views_shared.py`](../api/views_shared.py);
`_nsu_staff_required` in [`api/views_staff.py`](../api/views_staff.py);
`_partner_required` in [`api/views_partner.py`](../api/views_partner.py). An
unauthenticated or wrongly-roled request is redirected to `/login/` before any
query runs.

**Uploaded documents are not public URLs.** Everything under `media/` except
logos and backgrounds is served by
[`api/media_views.py`](../api/media_views.py), which resolves the owner of each
file from the model that references it and refuses anyone who is neither the
owner nor the office. Path traversal is rejected in `_normalise` before a
lookup happens. Tests: `api/test_media_access.py`.

**No user enumeration.** The sign-in form answers every credential failure with
one message, whether the address is unknown, the password is wrong, or the
account is closed. Distinguishing them would turn the form into a lookup
service for finding out which addresses belong to scholars. The register
prompt is attached to every refusal for the same reason — an invitation that
appeared only for unknown addresses would restore the signal. See
`_sign_in_error` in [`api/views_auth.py`](../api/views_auth.py) and
`api/test_account_verification.py`.

The one exception is the deactivation notice, and it is safe because it is
reached only after the supplied password has been verified against the account.

---

## Integrity

**Server-side validation is the only validation that counts.** Client-side
checks exist for feedback, not enforcement. Every upload passes
`validate_document` or `validate_spreadsheet` from
[`api/validators.py`](../api/validators.py) — extension allow-list plus a size
ceiling read from `SystemSettings` — and every form re-derives its own required
fields on the server, in `_unanswered`, `_missing_certificates` and the
`_REQUIRED_*` tuples in [`api/views_auth.py`](../api/views_auth.py).

**CSRF** on every state-changing form, with a dedicated failure page
(`templates/errors/403_csrf.html`) that offers a retry rather than a dead end.

**Transport.** `SECURE_SSL_REDIRECT`, HSTS, `SECURE_CONTENT_TYPE_NOSNIFF`,
`SECURE_REFERRER_POLICY = 'same-origin'`, `X_FRAME_OPTIONS = 'SAMEORIGIN'`, and
`Secure` + `HttpOnly` + `SameSite=Lax` cookies whenever `DEBUG` is off. See
[`config/settings.py`](../config/settings.py).

**Decisions are final.** Once an application is decided it cannot be silently
re-decided; see `api/test_decision_is_final.py`.

---

## Non-repudiation and accountability

`ActivityLog` records who did what, when, to which record, and what changed.
Each entry carries:

| Field | Holds |
|---|---|
| `user` | the account that acted |
| `verb` | one of approve, reject, create, update, delete, import, export, sign-in, other |
| `action` | the human-readable summary |
| `target_type`, `target_id`, `target_label` | the record acted on |
| `changes` | field-level before/after, as JSON |
| `ip_address` | where the request came from |
| `created_at` | when |

`ActivityLog.record()` is the single way entries are written, so every call
site produces the same shape. `ActivityLog.diff()` computes the `changes`
payload by comparing a model instance against its stored row before a save.

Approvals, rejections, edits, deletions, imports and exports are all recorded.
Entries are never updated or deleted by application code.

---

## Authenticity

Registration requires confirming the email address before the account is
usable ([`api/email_verify.py`](../api/email_verify.py)), and the SDSO office
reviews every new student and employee account before it can sign in.
Passwords go through Django's validators and PBKDF2 hashing.

---

## Resistance

**Throttling.** [`api/ratelimit.py`](../api/ratelimit.py) counts attempts in a
fixed window against every credential endpoint:

| Endpoint | Limit | Window |
|---|---|---|
| Sign-in | 8 failures | 15 minutes |
| Registration | 5 submissions | 1 hour |
| Resend confirmation | 4 requests | 1 hour |
| Change own password | 6 failures | 15 minutes |

Every attempt is counted twice: once against the caller's address and once
against the account being named. The address counter slows one machine working
through many accounts; the account counter slows many machines working through
one account, which no address counter can see. Whichever trips first returns
`429`. A successful sign-in clears the tally.

Registration counts *every* submission rather than only the failures, because
the abuse worth stopping there is a script that succeeds — minting accounts and
sending university mail to arbitrary addresses.

Tests: `api/test_rate_limiting.py`.

**Known limit.** With no `REDIS_URL` configured the cache is per-process, so
each gunicorn worker keeps its own tally and the effective limit is the
configured one times the worker count. The Render deployment runs a single
worker (`render.yaml`), so the figures above hold as written. Any multi-worker
deployment should set `REDIS_URL`.

**`X-Forwarded-For` is trusted only behind a proxy.** `TRUST_FORWARDED_FOR`
defaults to on when `DEBUG` is off and off otherwise, because the header is
trivially forged against a server that is not actually behind a proxy. A caller
who forges it still only escapes their own address counter; the per-account
counter does not read the request.

---

## What is out of scope

- **No fund disbursement or payment handling.** The system records decisions;
  money is handled by the offices and agencies outside it.
- **No integration with CHED or DOST systems.** Data arrives by spreadsheet.
- **No multi-factor authentication.** Worth adding before the system holds
  live production data for the whole university.
- **No automated dependency scanning.** `requirements.txt` is pinned, which
  makes builds reproducible but means updates are a manual decision.
