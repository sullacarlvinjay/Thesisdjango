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

### Two-step sign-in for office accounts

A password alone was the whole of the authentication on accounts that read
Listahanan status, disability and household income — thin under RA 10173.
Office accounts can now carry a second factor.

[`api/mfa.py`](../api/mfa.py) implements TOTP to RFC 6238 against the standard
library. It is checked against the RFC's own test vectors in
`api/test_mfa.py`, rather than against itself.

| | |
|---|---|
| Algorithm | HMAC-SHA1, 6 digits, 30-second step |
| Drift allowed | one step either way |
| Code attempts | 6 per 15 minutes, per address and per account |
| Challenge window | 5 minutes from the password step |
| Recovery codes | 8, single-use, stored as SHA-256 |

**A correct password alone does not produce a signed-in session.** The account
is held by id in the session while the code is asked for, and
`django.contrib.auth.login` is not called until the code checks out —
`api/test_mfa.py` asserts the client is unauthenticated after the password
step, rather than asserting the page mentioned a code.

Enrolment lives on the office's own profile page, not on a page of its own.
It shows the base32 setup key in the grouped form every authenticator accepts
under "enter a setup key", plus the `otpauth://` URI for apps that take a
pasted link. No QR code is drawn: rendering one needs a Reed-Solomon encoder
this project has no other use for.

Turning it off requires the current password, so a session left open on a
shared machine cannot strip the second factor.

**Enforcement is opt-in.** `MFA_ENFORCED` defaults to off. Turned on, an
office account that has not enrolled is redirected to its own profile to do
so — not signed out, because locking the office out of its own records is not
a privacy improvement. `MFA_REQUIRED_ROLES` defaults to `vpsea`.

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
| Two-step sign-in code | 6 failures | 15 minutes |

Every attempt is counted twice: once against the caller's address and once
against the account being named. The address counter slows one machine working
through many accounts; the account counter slows many machines working through
one account, which no address counter can see. Whichever trips first returns
`429`. A successful sign-in clears the tally.

Registration counts *every* submission rather than only the failures, because
the abuse worth stopping there is a script that succeeds — minting accounts and
sending university mail to arbitrary addresses.

**The REST endpoints spend the same allowance as the forms.** `/api/auth/login/`
and `/api/auth/register/` used to be counted by nothing at all, which made them
a second, unguarded allowance on every account the forms protect — and the
published OpenAPI schema is a map straight to them. They now read and write the
same cache keys through `ratelimit.LoginThrottle` and `ratelimit.RegisterThrottle`,
so eight wrong passwords at `/login/` refuse the ninth at `/api/auth/login/` and
the other way round. The refusal carries the portal's own wording and a
`Retry-After`.

A throttle only refuses; it never counts. Counting stays in the view, which is
the only place that can tell a wrong password from a right one.

**Everything else under `/api/` has a ceiling too.** `REST_FRAMEWORK` in
`config/settings.py` configured no throttle class at all, so every other endpoint
was limited only by how fast a token holder could ask. `AnonRateThrottle` and
`UserRateThrottle` now default to 60/hour and 1000/hour, tunable with
`API_ANON_RATE` and `API_USER_RATE`. These are a floor under the whole surface,
not a substitute for the credential throttles above, which are far stricter.

Tests: `api/test_rate_limiting.py`, including cases that spend the allowance on
one surface and assert the other refuses.

**Known limit.** With no `REDIS_URL` configured the cache is per-process, so
each gunicorn worker keeps its own tally and the effective limit is the
configured one times the worker count. The Render deployment runs a single
worker (`render.yaml`), so the figures above hold as written. Any multi-worker
deployment should set `REDIS_URL`.

**Browser policy headers.** `api.middleware.SecurityHeadersMiddleware` sends
a Content-Security-Policy and a Permissions-Policy on every HTML response —
document policies, so they are not put on a spreadsheet download or a PDF the
browser renders in its own viewer.

| Directive | Value | Stops |
|---|---|---|
| `default-src` | `'self'` | Anything loaded from another origin by default |
| `script-src` | `'self' 'unsafe-inline' cdn.jsdelivr.net` | A script from a host the university does not control |
| `style-src` | `'self'` | A style attribute written into the page by anything at all |
| `object-src` | `'none'` | Flash/Java-style plugin content |
| `base-uri` | `'self'` | An injected `<base>` repointing every relative URL |
| `form-action` | `'self'` | A form posting a scholar's data off-site |
| `frame-ancestors` | `'self'` | Clickjacking, alongside `X-Frame-Options` |

Permissions-Policy denies camera, microphone, geolocation, payment, USB and
the rest outright; `fullscreen` is allowed to the page itself. Neither header
has a Django setting, which is why the middleware exists. `CSP_REPORT_ONLY=1`
switches the policy to report-only while a change is being tried.

**`style-src` no longer needs `'unsafe-inline'`.** It did until the templates
stopped carrying inline styles. There were 1,186 static declarations across 40
templates and thirteen more that interpolated a value; all of them are now
classes in the utility layer at the foot of `static/css/srms.css`, except four
percentage widths that `static/js/meter.js` sets through the CSSOM — which is not
a style attribute and is not what the directive governs. A page can no longer be
repainted by anything that manages to write into an attribute.

`script-src` still carries `'unsafe-inline'`: several templates hold a `<script>`
block of their own, and moving those out is a separate job.

The one third-party script had to be checked rather than assumed: Chart.js 4.4.0
draws to a `<canvas>` and contains no `createElement('style')`, `insertRule`,
`cssText` or `adoptedStyleSheets` anywhere in its 205 KB, so the analytics page
does not need the directive loosened. It sets `canvas.style` through the CSSOM,
which `style-src` does not govern.

Tests: `api/test_security_headers.py`, which reads the headers off real
responses rather than off the settings module.

**HSTS is a year, not an hour.** `SECURE_HSTS_SECONDS` defaults to `31536000`.
It was `3600`, which is too short to be meaningful: a browser that has not
visited in an hour is back to trusting a plaintext first request.

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
- **No hardware keys or SMS codes.** The second factor is an authenticator
  app or a recovery code; WebAuthn and SMS are not implemented.
- **The Content-Security-Policy still allows inline script and style.** The
  templates carry 28 inline `<script>` blocks, about 1,200 inline `style`
  attributes and some 69 inline event handlers, and `'unsafe-inline'` is what
  lets them run. The policy is real and enforced — it still stops a script
  from a host the university does not control, and `object-src 'none'`,
  `base-uri`, `form-action` and `frame-ancestors` all hold — but it is not a
  strict CSP and should not be described as one. Removing the inline handlers
  is what would allow nonces to replace `'unsafe-inline'`.
- **No automated dependency scanning.** `requirements.txt` is pinned, which
  makes builds reproducible but means updates are a manual decision.
