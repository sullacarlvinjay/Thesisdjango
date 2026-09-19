# Optimization checklist

The SEO and performance list, audited against this codebase and then worked
through, on 2026-09-19.

Your 35 lines fold to 32 distinct items. Of those:

- **18 changed this pass** — items 2, 3, 5, 6, 7, 9, 11, 12, 15, 17, 19, 21,
  22, 23, 26, 28, 29, 30
- **7 were already in place** — 1, 4, 10, 14, 20, 31, 32
- **5 cannot be done from code** — 8, 13, 18, 24, 27
- **1 is partial** — 16, mobile, which needs a real handset rather than more code
- **1 is deliberately not done** — 25, pagination. The reason is measured, not
  assumed, and it is set out in full below.

Your list had 35 lines. Two pairs are duplicates and are folded below:
"compress all images" with "compress image", and "cache API response" with
"cache expensive queries" and "server side caching".

---

## Read this first: only three pages are public

This is the fact that decided half the SEO work. `landing_view` at
[api/student_views.py:73](api/student_views.py:73) carries no decorator, and
neither do the login or register views. Everything else — all of `/student/`,
`/vpsea/`, `/nsu-staff/`, `/partner/` — sits behind one of the 58
`login_required` / role checks in that same file.

So a search engine can only ever reach `/`, `/login/` and `/register/`. Those
three got descriptions, canonical tags and structured data. The other 56
templates got the opposite: a `noindex`, so a portal page never turns up in a
search for a student's name.

---

## Status

### SEO

| # | Item | Status | Where |
|---|---|---|---|
| 1 | Meta titles | Already done | 39 templates, all distinct |
| 2 | Meta description | **Done** | landing, login, register |
| 3 | noindex | **Done** | `_noindex.html`, 3 includes |
| 4 | Alt text on images | Already done | all 16 — the audit was wrong |
| 5 | Core Web Vitals | **Done** | Tailwind CDN replaced by a build |
| 6 | Remove broken links | **Done** | two, both confirmed by resolver |
| 7 | Fix header hierarchy | **Done** | 56 headings, 22 templates |
| 8 | Backlink strategy | Not here | off-site work |
| 9 | Canonical tags | **Done** | context processor + 3 templates |
| 10 | Enforce HTTPS | Already done | settings.py:237 |
| 11 | Compress images | **Done** | 7.86 MB to 1.46 MB |
| 12 | Schema markup | **Done** | JSON-LD on the landing page |
| 13 | Verify Search Console | Not here | needs your account |
| 14 | One h1 per page | Already done | base.html:104 |
| 15 | robots.txt | **Done** | `api/seo.py` + route |

### Performance

| # | Item | Status | Where |
|---|---|---|---|
| 16 | Mobile responsiveness | Partial | built, still needs a real device |
| 17 | Cache API responses | **Done** | headers + analytics caching |
| 18 | Load balancer | Not here | free plan, one instance |
| 19 | Index the database | **Done** | 7 new indexes, migration 0092 |
| 20 | Loading skeleton | Already done | skeleton.js |
| 21 | Remove N+1 queries | **Done** | profiled — none left |
| 22 | Debounce input handlers | **Done** | 2 of 3; the third shouldn't be |
| 23 | Split code into chunks | **Done** | CSS is two files now |
| 24 | Add a CDN | Not here | free plan |
| 25 | Paginate large lists | **NOT DONE** | see below — deliberate |
| 26 | Compress API payloads | **Done** | GZipMiddleware |
| 27 | Remove re-renders | Not here | no client framework |
| 28 | Minify JS and CSS | **Done** | at collectstatic, api/storage.py |
| 29 | Lazy loading | **Done** | 4 landing images |
| 30 | Defer non-critical scripts | **Done** | 2 more deferred |
| 31 | Remove unused dependencies | Already done | all 19 were in use |
| 32 | Connection pooling | Already done | settings.py:118 |

---

## The one that is not done

### 25. Paginate large lists

There is still no `Paginator` in `api/`. This is the only item left, and it is
left on purpose. Here is the measurement behind that.

The archives page renders every row of `ImportedScholar` into the HTML:

| rows | HTML | gzipped |
|---|---|---|
| 456 (today, dev) | 247 KB | **20 KB** |
| 1,000 | ~0.5 MB | ~40 KB |
| 5,000 | ~2.6 MB | ~210 KB |
| 20,000 | ~10.6 MB | ~840 KB |

About 555 bytes of HTML per row. Two things follow.

**It is not a query problem.** Profiled against the real 456-row database, the
archives page runs **13 queries in 27 ms**, and that is the same count it runs
against an empty database. The row count does not move it. Pagination would not
save a single query.

**Gzip already absorbs the current size.** Item 26 added `GZipMiddleware`, so
that 247 KB page now goes over the wire at 20 KB.

**What pagination would cost.** `table-filter.js` and the inline `filterArch()`
at [archives.html:448](templates/vpsea/archives.html:448) both assume every row
is already in the DOM. They filter and sort across the whole set instantly.
Paginate the queryset and both silently become wrong — a search would only find
matches on the page you happen to be looking at, which is worse than slow. The
filter dropdowns are built from the visible rows, so they would narrow to
whatever 100 rows were on screen.

Doing this properly means moving search, filtering and sorting server-side at
the same time, adding page controls, and re-testing the SDSO's main daily
workflow. That is a feature redesign, not an optimization, and at 456 rows it
would make the page worse to use rather than better.

**When to do it.** Past roughly 2,000 rows in one scholarship type, the HTML
cost starts to outweigh the instant-filter benefit. At that point paginate and
move filtering to the server together, in one change. Not before.

---

## What changed

### 2, 9, 12. Descriptions, canonical tags, structured data

`landing.html`, `login.html` and `register.html` each carry a
`<meta name="description">` and a canonical link. The landing page also carries
an `EducationalOrganization` JSON-LD block.

Canonical URLs come from `canonical_url` in
[api/context_processors.py](api/context_processors.py), built by
[api/seo.py](api/seo.py) off `SITE_URL` with `request.build_absolute_uri` as the
fallback. Every tag is wrapped in `{% if canonical_url %}`, so nothing renders
an empty href when `SITE_URL` is unset locally.

The JSON-LD claims only what the repository can prove — the university's name
and its URL. It does not name the SDSO as a department, because nothing in the
codebase states what SDSO expands to, and structured data is the wrong place to
guess.

### 3. noindex

[templates/_noindex.html](templates/_noindex.html) is one line, included from
`base.html` (so all 39 portal templates), `registration_received.html` (which
shows an applicant their own decision) and `errors/_shell.html`.

Deliberately absent from `landing.html`, `login.html` and `register.html`.

### 5. Core Web Vitals — Tailwind is a real stylesheet now

`cdn.tailwindcss.com` is gone from all six standalone templates. It was the
in-browser JIT compiler: render-blocking, shipping the whole engine to every
visitor and recompiling the stylesheet on each page load.

In its place, `static/css/tailwind.css` — **16.6 KB minified, 3.8 KB gzipped**.
[tailwind.config.js](tailwind.config.js) reproduces the theme extension that
used to sit inline in `base.html`, which was also removed (it would have thrown
a `ReferenceError` with the CDN gone).

**Verified, not assumed.** 642 distinct class tokens were extracted from every
template and JS file and checked against the generated CSS. Thirteen did not
match, and every one is either a JS behaviour hook (`arch-row`, `app-row`,
`unawarded-row`) or the static prefix of a class the template builds from a
variable (`badge-{{ status }}`). **No Tailwind utility is missing.** All three
custom-theme utilities actually used — `hover:bg-muted`, `hover:border-primary`,
`text-muted-foreground` — are present.

**Render still needs no Node.** `static/css/tailwind.css` is committed, so
`build.sh` stays pure Python. Regenerate with `npm run build:css` after changing
a template's classes, and commit the result — nothing on the server will do it
for you. `npm run watch:css` rebuilds on save while you work.

### 6. Broken links

- [vpsea/dashboard.html:51](templates/vpsea/dashboard.html:51) pointed at
  `/vpsea/uploads/`, which has no urlpattern — a hard 404 behind the "Import
  Excel Records" button. Now `/vpsea/archives/`, which is where the upload modal
  lives; `vpsea_archive_import` is POST-only and redirects a GET there anyway.
- [base.html:91](templates/base.html:91) pointed at `/logout` with no trailing
  slash. `APPEND_SLASH` rescued it with a 301 on every sign-out from every page.
  Now `/logout/`.

All 39 hardcoded hrefs resolve through Django's own resolver.

**The cause underneath is still there** — see *Still open* below.

### 7. Header hierarchy

56 headings promoted from `h3` to `h2` across 22 templates. The project went
from 6 h1 / 15 h2 / 61 h3 to **6 h1 / 71 h2 / 5 h3**, and no template jumps from
h1 straight to h3 any more.

`register.html` was deliberately skipped: its `<h3>` inside `.terms-section` is
styled by an element selector at [srms.css:586](static/css/srms.css:586), so
promoting it would have dropped the styling. It has its own h2s already.

### 11. Images — 6.40 MB saved

The audit missed the worst of this. `media/logos/` is gitignored except for the
branding, which **is** committed, and those five files were enormous for images
displayed at 40–80 px.

| file | before | after | dimensions |
|---|---|---|---|
| `media/logos/BiPSU.png` | 3631.6 KB | **247.5 KB** | 1563² to 512² |
| `media/logos/UniFAST.png` | 1458.6 KB | **92.4 KB** | 1563² to 512² |
| `media/logos/SDSO.png` | 780.1 KB | **187.6 KB** | 719² to 512² |
| `media/logos/CHED.png` | 530.4 KB | **84.0 KB** | 840² to 512² |
| `media/logos/DOST.png` | 79.2 KB | **17.8 KB** | 840w to 512w |
| `static/img/apple-touch-icon.png` | 72.9 KB | **51.0 KB** | 180² unchanged |
| `static/img/backgrounds/Student.JPG` | 853.5 KB | **318.5 KB** | 4032w to 2048w |
| `.../registration-campus.jpg` | 404.9 KB | **259.8 KB** | 2400w to 1920w |
| `.../Facade.jpg` | 238.1 KB | 238.1 KB | left alone |
| **total** | **7.86 MB** | **1.46 MB** | **81% smaller** |

`BiPSU.png` alone was 3.6 MB, and it loads on the landing page, both auth pages,
the error shell and every portal page. That was the single heaviest thing the
site served — heavier than the Tailwind CDN.

The PNGs were resized then quantized to a 256-colour palette. RMS error against
the originals is 2.6–6.8 out of 255, which is invisible on a logo.

**`Facade.jpg` was reverted and left at its original size.** Re-encoding it at
quality 78 produced a *larger* file (259 KB against 238 KB) — it was already
well compressed. Worth remembering before running a blanket "compress
everything" pass again.

512 px still leaves `make_favicon` plenty to work from; it needs 180 px at most.

### 15. robots.txt

[api/seo.py](api/seo.py) serves it from a route rather than a static file,
because it has to disallow the gated prefixes:

```
User-agent: *
Disallow: /student/
Disallow: /nsu-staff/
Disallow: /vpsea/
Disallow: /partner/
Disallow: /api/
Disallow: /admin/
Disallow: /media/
```

`/media/` matters most: `media_views.serve_media` is the guarded route for
uploaded student certificates and grade reports.

No `Sitemap:` line, and no sitemap. Three public URLs do not need one, and a
`Sitemap:` pointing at nothing would have been a new broken link.

### 17. API caching

Two changes. `ApiCacheHeadersMiddleware` in
[api/middleware.py](api/middleware.py) sets `Cache-Control: private, no-cache`
on `/api/` GETs and `private, no-store` on everything else under `/api/`.

Every API endpoint is behind `IsAuthenticated` and returns per-user data, so
nothing there may be cached publicly. `no-cache` does not mean "do not cache" —
it means "revalidate first", which lets the ETags that `ConditionalGetMiddleware`
already generates turn repeat requests into empty 304s. Without an explicit
header browsers apply heuristic caching, which on authenticated data risks
serving stale records.

`VPSEAAnalyticsView` now caches its payload under `ANALYTICS_CACHE_SECONDS`.
It was running seven uncached aggregates on every call while the *page* version
of the same analytics at [student_views.py:3588](api/student_views.py:3588) was
already cached — that gap is closed.

### 19. Database indexes

Seven added in `0092_optimization_indexes`, chosen from a profile of what the
pages actually filter on rather than from reading the models:

| model | index | filtered |
|---|---|---|
| `ScholarListImport` | `(scholarship_type, term_label)` | 130× |
| `AcademicRenewal` | `(status, term_label)` | 3× |
| `Scholarship` | `type` | 50× |
| `User` | `verification_status` | 12× |
| `ApplicantRecord` | `qualified_for`, `status` | 11× |
| `ScholarshipLinkRequest` | `status` | 10× |

`ScholarListImport` was the clear win: 130 filters on `(scholarship_type,
term_label)` against an index on `term_label` alone.

`ImportedScholar` needed nothing — its existing
`(scholarship_type, term_label, claimed_by)` composite already leads with the
columns its 107 filters use.

`User.verification_status` is worth its write cost because
`_pending_accounts()` in the context processor runs it on **every request from
an office account**.

### 21. N+1 queries

Profiled rather than grepped, against the real 456-row database:

| page | queries | ms |
|---|---|---|
| `/vpsea/archives/?type=Academic` | 13 | 27 |
| `/vpsea/` | 13 | 6 |
| `/vpsea/students/` | 8 | 7 |
| `/vpsea/ranking/` | 16 | 18 |
| `/vpsea/analytics/` | 11 | 7 |
| `/vpsea/reports/` | 38 | 44 |

**No N+1 remains.** The counts are identical against an empty database, which is
the signature of correct prefetching — the 45 `select_related` /
`prefetch_related` calls in `student_views.py` are doing their job. The repeats
that do show up (13 on reports, 8 on ranking) are per-scholarship-type loops
with a small fixed bound, not per-row.

### 22. Debounce

[table-filter.js:168](static/js/table-filter.js:168) and
[search.js:78](static/js/search.js:78) now debounce at 150 ms. The first is the
one that mattered: its `apply()` walked every row and lowercased its text on
every keystroke.

The `change` listeners on the filter selects, the `search` event, and the
initial call all stay immediate — debouncing those would only add lag.

**[account-choice.js:43](static/js/account-choice.js:43) was left alone on
purpose.** Its handler retitles one note from one field. Debouncing it would
delay live feedback and save nothing.

### 26, 28. Compression and minification

`SelectiveGZipMiddleware` in [api/middleware.py](api/middleware.py) sits after
WhiteNoise and before `ConditionalGetMiddleware`, so static files never reach it
twice and ETags are still computed on the uncompressed entity.

It subclasses Django's `GZipMiddleware` to **skip content that is already
compressed** — PDF, xlsx, docx, zip, and any `image/`, `video/`, `audio/` or
`font/` type, with SVG and BMP excepted because those do compress. Plain
`GZipMiddleware` would have re-compressed every Excel export and every uploaded
document for nothing, and `media_views.serve_media` returns a `FileResponse`,
so gzipping it would also have stripped `Content-Length` and with it the
browser's download progress. Measured after the change: the archives page ships
gzipped at 20.8 KB, the Excel export and the PNG logos are left alone.

Minification happens **during `collectstatic`**, in
`MinifiedManifestStaticFilesStorage` at [api/storage.py](api/storage.py). This
matters: there are no committed minified files to drift out of sync with their
sources, no build step to forget, and no template changes. Edit
`static/js/foo.js` and the next deploy ships it minified.

The implementation has one non-obvious part. Django's `HashedFilesMixin` hashes
each file by reading it from the **source** storage, not from `STATIC_ROOT`, so
minifying the copy in `STATIC_ROOT` had no effect on the hashed file that
actually gets served. `post_process` therefore rewrites the `paths` mapping to
point at the already-minified copy before handing off to `super()`.

`rcssmin` and `rjsmin` do whitespace-only minification — they never rename
identifiers, so they cannot break working JS. All 115 minified JS files in
`staticfiles/` were checked with `node --check`: **zero syntax errors**.

| file | source | served | gzipped |
|---|---|---|---|
| `css/srms.css` | 83.6 KB | 67.6 KB | 13.1 KB |
| `css/tailwind.css` | 16.3 KB | 16.1 KB | 3.8 KB |
| `js/excel-charts.js` | 18.3 KB | 13.1 KB | 4.0 KB |
| `js/chrome.js` | 7.8 KB | 6.2 KB | 2.1 KB |
| `js/table-filter.js` | 5.7 KB | 4.2 KB | 1.5 KB |

`esbuild` was measured as an alternative and rejected. It minifies about 40%
harder because it renames identifiers, but the extra saving is roughly 3 KB
gzipped across the whole site — not worth the risk of a mangler meeting code it
does not understand. It was uninstalled rather than left sitting in
`devDependencies`, which would have re-opened item 31.

### 29, 30. Lazy loading and deferred scripts

`loading="lazy" decoding="async"` on the four below-the-fold images on the
landing page — the three card-logo loops and the modal logo. The other twelve
images are all above the fold, where lazy loading hurts.

`mobile-nav.js` and `confirm-dialog.js` now carry `defer`. Both gate everything
behind `DOMContentLoaded`, and deferred scripts run before that event fires, so
nothing changed about when they execute.

`skeleton.js` is still render-blocking, deliberately — the skeleton has to be up
before the first paint.

---

## Still open

**16. Mobile responsiveness.** The groundwork is all there: viewport meta on all
six standalone heads, 99 responsive breakpoint classes, 24 media queries, three
`overflow-x` rules for table scrolling, a dedicated `mobile-nav.js`. What has
not happened is testing on a real handset. The wide tables — archives, ranking,
students — are where it will break if it breaks. This needs measuring, not
building.

**25. Pagination.** See above.

**Named URL patterns.** Not on your list, but it is the cause under item 6.
`api/urls.py` gives no pattern a `name=`, and no template uses `{% url %}` — all
39 links are hardcoded strings. Naming them would have turned both broken links
into errors at render time instead of 404s in front of a user, and would stop
the next one happening. It is a mechanical change across 93 patterns and 39
template links, large enough to want its own pass and its own review.

---

## Cannot be done from code

**8. Backlink strategy.** Getting bipsu.edu.ph and partner agencies to link to
the portal. Nothing in this repository affects it.

**13. Verify Search Console.** An external account, verified by a DNS record or
a meta tag. If you take the meta-tag route the tag goes in `landing.html` and
takes one line — the same situation as the SMTP credentials, which have to be
typed into the Render dashboard by hand.

**18. Load balancer** and **24. CDN.** [render.yaml:11](render.yaml:11) is
`plan: free` — one instance, one gunicorn worker with eight threads on 512 MB,
singapore region. Both are paid-plan features and neither is a code change.
Render already fronts the app with its own edge.

**27. Remove unnecessary re-renders.** A React and Vue concern. This project is
server-rendered Django templates with vanilla JS; there is no virtual DOM.
The nearest real equivalent was item 22.

---

## Regenerating assets

```bash
npm run build:css
```

Run it after changing the Tailwind classes in any template, and commit
`static/css/tailwind.css`. Nothing on the server regenerates it.

Everything else — minification, compression, hashing — happens automatically
during `collectstatic` on deploy. There is nothing else to remember.
