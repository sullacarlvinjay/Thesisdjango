# Requested changes

A record of what was asked for and why, so nothing here gets "tidied away" later
by someone who reads it as an accident. **Do not undo any of these unless you
decide you want the behaviour gone** — each one was a deliberate request, and
several of them removed something that used to work.

---

## Student record split into detail tables

`StudentProfile` had grown to about forty columns covering six unrelated
subjects. They moved onto one table per subject, each keyed back to the student:
`EnrollmentData`, `PersonalInformation`, `AffirmativeEligibility`,
`SocioEconomicProfile`, `TESEligibility`, `EducationalBackground`,
`FamilyBackground`.

New fields collected at the same time: Level, Department, Curriculum, Learner
Ref. No., Entry Period, Entry Date, Exam Score, Birth Place.

`profile.gwa`, `profile.course` and the rest still read and write from the
profile through the `DetailField` proxies — see `api/models.py`. **A queryset
cannot**: `filter(enrollment__gwa__lte=1.5)`, not `filter(gwa__lte=1.5)`.

Migrations `0049`–`0051`.

## Every submission records its semester

Registration, applications, renewals, link requests, TES applications and staff
applications all carry `term_label` / `school_year` / `semester` through
`TermStamped`, filled from the active term when the caller sets none. The office
can ask "which renewals are for 26-1?" as a column filter rather than inferring
it from a submission date.

## Staff registration picks its school from the BiPSU list

Staff typed it free-hand, which matches nothing in a report. Posted as
`staff_school`, because the student block on the same form posts a `school` of
its own and `request.POST` keeps only the last value.

## Archive tables are built from a column choice

Each scholarship names the columns its archive table shows, on its own form
under **Archive Table Columns**, plus columns the office adds itself and types a
value into per scholar. See `api/scholar_columns.py`.

This replaced seven hand-written tables in `vpsea/archives.html` and two in
`unifast/archives.html`. **The defaults are not decorative** — they are read off
the tables they replaced, per programme and in one case per office (UniFAST
reported TES against an award number, the SDSO archive did not). Changing
`DEFAULT_COLUMNS_BY_TYPE` changes what an unconfigured programme shows.

## Scholars per school, on Analytics

A "Scholars by School" chart and tally. The count reads the school where it is
recorded and works it out from the course where it is not, because imported rows
and rollover spreadsheets have no school column at all. A course matching none
of BiPSU's is reported as **Not recorded** rather than filed under a guess.

## Removed: the queue summary card

It was asked for, built, refined, and then removed — the counts and the
one-breakdown-at-a-time picker are gone from Applications, Renewal Applications,
Account Verification and Link Requests. **Deliberate.** Deleted with it:
`api/queue_summary.py`, `templates/_queue_summary.html`,
`static/js/queue-summary.js`, its styles and its tests.

What came in alongside it is **not** part of the card and stays:

- the **School** column on the Applications table
- the **Semester** column on the Applications table, and **Registered** on
  Account Verification — which semester each row was applied for or registered in

## Sortable columns, and filter schemes

Any `<table data-sortable>` sorts by a clicked heading —
`static/js/table-sort.js`. It reads terms as terms and dates as dates, so
"2025-2026 2nd Semester" does not sort after "2026-2027 1st", and "Aug 29" does
not sort before "Aug 13" alphabetically. A column marked `data-no-sort` is
skipped; that is what the actions column is.

Any `<table data-filterable>` gets a filter bar — `static/js/table-filter.js`.
Each `<th data-filter>` becomes a dropdown **built from the values actually in
that column**, so it can never offer a choice that matches nothing, and a column
where every row says the same thing is skipped. Filters stack, compose with the
search box and with the sort, and the bar says "Showing 2 of 3".

This replaced the Applications page's hand-written status menu, which listed
four statuses someone had typed into the template. Link Requests is left alone
on purpose: it lists cards, not rows, so there are no columns to sort or narrow.

## Removed: BiPSU Staff from Student Ranking

**Deliberate.** The programme has no merit test — a regular appointment
qualifies and nothing is scored — so the ranked list was sorted by a constant.
Staff applications are reviewed on the Applications page instead.

## Removed: the Affirmative tab from Applications

**Deliberate.** Nobody applies for Affirmative Action. Eligibility is worked out
from the student's own profile by `AffirmativeRecommendation.evaluate_and_sync`
and endorsed on Student Ranking, so an application queue for it listed records
the office never acted on from there. The `AffirmativeStaffApplication` rows
still exist; only that tab is gone.

## Removed: the Draft status

**Deliberate.** A draft was invisible to the office and unchaseable for the
applicant — it sat between "not applied" and "applied" and neither side could
act on it. Replaced by the next item. Migration `0053` moved any row still in it
to Pending Validation.

## Added: a student can correct an undecided submission

An academic application, a TES application and a renewal stay editable while
they are waiting on the office, and while the office has sent one back as
**Needs Revision** — which is exactly the case of "you uploaded the wrong
document, send it again". Re-uploading replaces the document on file rather than
adding a second copy, and re-sending a Needs Revision application puts it back
in the queue and clears the remark that asked for it.

Approved and Rejected are final: a student can no more edit those than a
reviewer can overwrite them. The two halves of that line are
`EDITABLE_APPLICATION_STATUSES` and `DECIDED_APPLICATION_STATUSES` in
`api/constants.py`.

## Fixed: student numbers printed as `23-1-00286`

`|escapejs` was applied to HTML `data-` attributes on the Applications page. It
escapes for JavaScript's string grammar, so a hyphen became `-`; a browser
un-escapes that when it parses a JS string, but an HTML attribute is not a JS
string and the text stayed literal. Django autoescapes attribute values already.
**Do not put `|escapejs` on an attribute** — only inside a `<script>`.

## Fixed: template comments printed onto the page

Django's `{# ... #}` is a **single-line** comment. With the opener and closer on
different lines the lexer never matches it and the prose is rendered to the
reader. Multi-line comments must be `{% comment %} ... {% endcomment %}`.
`api/test_template_comments.py` fails if one comes back.

## Added: the CHED Annex 1 report — the list of TES applicants

The UniFAST office's own Annex 1 workbook is bundled at
`templates/xlsx/tes_annex1_applicants_template.xlsm` and filled in, the same way
`tes_report.py` fills the Annex 2 one: the General Instructions tab, the hidden
`Registry_Courses` / `Sex_Code` / `Disability_List` lookup sheets, the three
dropdown validations and the sheet's own macros all survive, so the download is
the form as CHED issues it apart from the applicant rows. **It is loaded and
saved with `keep_vba=True`** — dropping that turns the .xlsm into a workbook
whose sequence-number macro is gone.

Generated from **TES Applications**, not Reports, because it lists everyone who
applied whether or not a decision has been made — the opposite of Annex 2, which
lists only approved grantees. Three of its columns are computed rather than
copied: sex as CHED's `0`/`1` code, a mobile number with its leading zero
dropped (the form wants ten digits starting with 9), and blank disability or IP
group as the literal `NO` both of those columns use for "not applicable".

PhilSys and 4Ps ID numbers export blank. Neither is collected anywhere in this
system — `TESEligibility` holds a 4Ps yes/no, not the household's ID — and both
are optional on the form. **Do not fill the 4Ps column from the boolean**: it
would turn a flag into an ID number the office would then sign for.

## Added: both TES reports are generated for one school year

A **School Year** picker on the Reports page and on TES Applications. It scopes
the list on screen and the workbook that comes out of it, and it is the year
stamped into the Annex 1 title row and the Annex 2 headers.

The default is **All school years**, not the active term. TES applications
created before migration `0049` have no `school_year`, and defaulting to the
active term would have hidden them from a page that used to show them.

## Changed: the Annex 1 controls sit on the TES Applications table

They had a card of their own above the list. The school year, the download and
the preview now sit in the head of the card holding the table they act on — the
list an officer is reading and the list they export are the same list, so the
controls belong on it.

## Added: the SDSO filter scheme on the TES Applications table

`data-filterable` / `data-sortable` with `data-filter` on Program, Year, Term
and Status, and the search box wired through the bar's `data-filter-search` —
the same contract `api/test_table_controls.py` guards on the SDSO tables.

**The old `filterTes()` is gone on purpose.** It hid rows with
`style.display`, `table-filter.js` hides them with `hidden`, and two scripts
hiding the same rows by different means leave rows the other cannot bring back.

## Removed: the TES Batch field on the Reports page

CHED's batch is a bookkeeping label, not something the office filters its own
reports by, and the workbook's header already reads 'On-going' when none is
given. The download endpoint still honours `?batch=` for anyone who needs to
stamp one, and the BATCH column of the form is untouched.

## Added: a TDP report beside the TES one

The Reports page now carries one section per programme UniFAST administers,
each with its own summary boxes, its own download and its own preview frame,
both scoped by the school year in the toolbar:

* **TES** — CHED's Annex 2 workbook, as before.
* **TDP** — the Tulong Dunong scholars masterlist, split by gender.

Both TDP files come from `_unifast_report_sections`, the same rows the combined
masterlist uses, so the section on screen and the file that downloads cannot
drift. The preview converts that workbook when LibreOffice is installed and
falls back to `report_pdf.programme_masterlist_pdf` when it is not — the same
two-step the TES frame uses.

## Added: registrants confirm their email address

The registration form took any string with an `@` in it. Nothing checked the
address was well formed, and nothing checked the person filling in the form
could read mail at it — so a mistyped address produced an account nobody could
ever reach, and somebody else's address produced one too. Every message the
system sent after that, the SDSO's own decision included, went to a stranger or
to nowhere.

Two checks now, in `api/email_verify.py`:

* `address_error()` runs on the posted form and refuses what cannot be an
  address. It is deliberately narrow — Django's own validator already catches a
  dotless domain, a one-letter TLD and a leading hyphen. What this adds is the
  two holes Django leaves open on purpose: `localhost`, which it allowlists,
  and an IP literal like `juan@[127.0.0.1]`.
* a signed link emailed to the address. `TimestampSigner` signs the account id
  and the address together, so it expires on its own, cannot be forged without
  the SECRET_KEY, and **stops working the moment the address on the account
  changes** — a link mailed to the old address must not confirm the new one.

**No DNS or MX lookup, on purpose.** It reads like the stronger check and is
not: a domain serving mail through MX alone resolves no A record, a nameserver
that is briefly down looks exactly like a domain that does not exist, and either
one turns into a real student refused registration for an address that works.

**Confirmation is not a sign-in gate.** Mail is optional here (`EMAIL_ENABLED`),
so a gate would strand every applicant on an installation with no SMTP. It is a
fact the SDSO is shown while deciding — an unconfirmed address is one nobody has
been able to reach. `User.email_verified` defaults to True for the same reason
`verification_status` defaults to approved: the office's own accounts are not
asked to prove an address the office already had. Migration `0054`.

## Changed: the approve/reject email says something

It was the office's one-line note and nothing else — no greeting, no statement
of what had been decided, no idea what to do next. That reads fine in the portal,
where the screen supplies all of it, and reads like a fragment in an inbox,
which is where it lands for the half of recipients who cannot sign in at all.

`notify.account_decision()` writes both halves from one call, so they cannot
contradict: the bell keeps the office's own words, the email wraps them in the
context an inbox does not supply. `notify.notify()` grew an `email_body` for it.

Confirmation links are absolute — `SITE_URL` first because it is the only source
a proxy cannot rewrite, otherwise built from the request. **A relative path in an
email is not a link**; nobody can click it.

## Fixed: 'they have been emailed' when nothing was sent

With no `EMAIL_HOST` the console backend accepts every message and reports
success, so the office was told an applicant had been emailed when the message
had been printed to a log nobody reads. The accounts page now carries a standing
warning when no mail server is configured, claims delivery only where mail
actually leaves the server, and says so in red when a configured server refuses
or times out — the decision itself is saved either way.

## Changed: the TES form offers CHED's own lists

Complete Program and Disability Type are dropdowns now, and the options are read
out of the bundled Annex 1 workbook's hidden `Registry_Courses` and
`Disability_List` sheets — the same lists the sheet's own dropdown validation
points at. Cached on first read. Drop in a newer template and the form follows
it; nothing to edit in code.

**The programme list is not `BIPSU_COURSES`.** That one holds the university's
abbreviations — `BSCS`, `BSEd - English` — and CHED reads the Annex 1 against
its registry of full names. Typing the short form is exactly what put `BSHM` in
a submitted list. The two vocabularies cover the same programmes; only one of
them is the one CHED checks.

Disability Type also carries **Other**, which reveals a box to type in
(`static/js/reveal-on-select.js`). The hidden box is `disabled` while it is out
of sight — a hidden input still posts, and a stale value from a choice the
student changed their mind about would go to CHED as their answer. Re-opening a
saved application that used Other comes back on Other with the text intact,
rather than silently dropping what they wrote.

## Added: PhilSys and 4Ps ID numbers on the TES form

The last two Annex 1 columns nothing collected. Optional on CHED's form and
optional here. Still never derived from the 4Ps flag on `TESEligibility` — that
is a yes/no and the column wants a household's ID. Migration `0055`.

## Fixed: a student with an empty profile could submit an unusable TES form

Sex, year level and both parents' names are read off the profile and shown
read-only, so a student who never filled in their profile had **no box on the
page** that could supply them. The form took the submission anyway and produced
an Annex 1 with a blank mother's name — a column CHED marks Required.

Submission is now refused, naming the missing fields and linking to My Profile,
with the submit button replaced by that link. `TES_PROFILE_REQUIREMENTS` in
`api/student_views.py` is the list. **The father's names are deliberately not on
it**: CHED marks them optional, and a student raised by one parent should not be
stopped by a box they cannot honestly fill.

## Changed: the programme list can be searched, and is alphabetical

Forty options that all begin "BACHELOR OF SCIENCE IN" is not a list anyone can
scan. Two changes, both small:

* the form sorts them A-Z rather than using the sheet's own order, which groups
  by college and tells a student nothing;
* a box above the dropdown narrows it as you type
  (`static/js/searchable-select.js`). Words match in any order and anywhere in
  the name, so "comp sci" finds BACHELOR OF SCIENCE IN COMPUTER SCIENCE, which
  typing it in order would not.

Options are hidden rather than removed, so the select still submits normally and
**the currently selected option is never hidden** — it would vanish from the
closed select while still being the answer that gets sent. With JavaScript off
the box does nothing and the whole list is there, which is what it was before.

The submitted programme is now checked against the registry server-side, so a
hand-made post cannot put a name in the Annex 1 that CHED's registry does not
hold. Skipped when the workbook is missing, or it would reject everything.

## Fixed: srms.css was cached at ?v=9 across several sessions of edits

The stylesheet link carries a hand-written `?v=` cache-buster and it had not
moved while CSS was added to it, so a returning browser kept a stale copy and
new rules simply did not apply — which is what made the programme-search count
render as unstyled text below its box. Bumped to `?v=10` in all six templates
that link it. **Bump it whenever srms.css changes.**

## Changed: pick the school, then the programme

Two dropdowns, the same pair the registration form makes of School and Course:
choosing a school shows that school's programmes alone. Six options under your
own school can be read; forty that all open with "BACHELOR OF SCIENCE IN"
cannot, and nobody should have to remember how their course is spelled to find
it in a list.

The School box takes its choices from the programme select's own `<optgroup>`
labels, so there is no second list to keep in step, and switching schools clears
a programme left over from the last one — it would still be the answer that gets
submitted while no longer being visible to change. Editing an application opens
on the school its programme belongs to.

**The school is not stored.** It is worked out from the programme by
`school_for_registry_program()`, so keeping a copy would be a second record of
one fact. The box has no `name`, so the browser never posts it.

This replaced a type-to-search box added an hour earlier, which asked the
student to know the wording before they could find it. `searchable-select.js`
and the `.program-search` CSS went with it rather than being left dead.

`school_for_registry_program()` in `api/constants.py` matches on keywords rather
than a name-by-name table, so a newer Annex 1 template can add programmes without
an edit here. Order matters in that list — 'COMPUTER SCIENCE' rather than
'COMPUTER' so COMPUTER ENGINEERING lands under Engineering, and 'INDUSTRIAL
TECHNOLOGY' before 'EDUCATION' so TECHNOLOGY AND LIVELIHOOD EDUCATION is read as
the teaching degree it is. Anything unmatched groups under **Other programmes**,
which is visible rather than wrong; today that is Marine Transportation, which
BiPSU's school list has no home for.

**The grouping is navigation only.** The value submitted is the registry name
either way, so a debatable heading costs a moment's looking and never a wrong
name on a CHED submission.

## Changed: nothing on the TES form is read-only

Student ID, both names, middle name, ext. name, sex, year level and both
parents' names were locked. They still fill themselves in from the profile —
that part was the point and it stays — but they are editable now and **saved
back to the profile**. There is still exactly one copy of each fact; the form is
another window onto it rather than a second record of it, which is why
`TESApplication` still carries no name columns.

On the profile page these lock after the first save, because an edit there would
quietly change a record the office has already reviewed. **That reason does not
hold here**: this form only opens while the application is undecided, so nothing
has been reviewed yet. Same rule, applied where it means something — a decided
application is still closed, and posting to it still changes nothing.

This replaces the "finish your profile first" block added earlier the same day:
the fields it sent students away to fill in are now fillable where they are
standing. What survives is the validation — CHED's required columns are still
refused blank, year level must be 1-6, and a Student ID belonging to another
account is refused rather than raising an IntegrityError.

## Changed: the photo washes are no longer pure blue

`--wash-strong` and `--wash-soft` were `rgba(0, 0, 255, …)` — the brand blue at
full saturation, which is the most saturated thing a screen can show. Over a
photograph it flattened the campus into one electric field of colour and left
the yellow call to action fighting it. They are a deep indigo now: same hue
family, much less shouting, and the picture underneath reads as a picture.

**The brand blue itself is untouched.** `--brand` is still `#0000ff` everywhere
it is the interface — sidebar, buttons, headings. Only the wash over a
photograph changed.

The soft end sits at 0.66 rather than as light as it could go: white body text
runs across the middle of these photographs and the campus buildings are pale
concrete, so at 0.56 the hero subtitle was fighting the wall behind it.

Every hard-coded `rgba(0, 0, 255, 0.50), rgba(9, 9, 169, 0.84)` pair now goes
through the two tokens, so the next tune is one edit rather than four.

## Changed: the sign-in photograph is fixed, and the sky is gone

`media/backgrounds/registration-campus.jpg` is the old `registration.jpg` with
the top 42% cropped away and the file re-encoded. The sky was the top 46% of the
frame: `background-position` could never crop that, because `cover` only
overflows the viewport by a fraction of the height — it had to come out of the
file. **The same crop took the sign-in page's background from 5.99 MB to
0.41 MB**, which is the larger win of the two.

`background-attachment: fixed` from 768px up, so the campus stays put while the
card scrolls over it. Phones keep `scroll` on purpose: a fixed background on a
touch device either stutters against the scroll or is quietly ignored, and the
registration form is taller than a phone screen.

The page's `background-color` is a deep indigo now rather than `--brand`. It is
what shows before the image loads and in any strip a viewport-sized fixed
background cannot reach, and pure `#0000ff` flashing behind a sign-in card is
the one place that blue does the identity no favours.

`registration.jpg` (5.99 MB) and `Gymnasium.jpg` (3.27 MB) were left referenced
by nothing and have been **deleted** at the office's request. `Gymnasium.jpg`
was already unused before any of this. Both were git-tracked, so both are still
in the history if either is ever wanted back:

    git checkout <commit-before-deletion> -- media/backgrounds/registration.jpg

`media/backgrounds/` is down from 10.4 MB to 1.5 MB.

## Changed: Renewal appears with the scholarship it renews

It showed from the day an account was created, so a student with nothing to
renew could walk into a page whose only job was to tell them so. It is now gated
on `enrolled`, the same context-processor answer the Apply pages already used.

The reason that survived so long: the student nav had been **copied into ten
templates**, so a change had to be made ten times to be made at all. It lives in
`templates/student/_nav.html` now, and `api/test_student_nav.py` fails if a copy
ever comes back.

Link Scholarship still goes when a scholarship is held — a decided rule guarded
by `api/test_link_flow.py`. Worth knowing what that costs: the student's own
record of the request, proof and all, is unreachable once it is approved. Left
as decided rather than changed in passing.

## Changed: the SDSO link requests page is a table, and says what it is holding

Every decided request was always kept, with its proof, its reviewer and the
reason. But the page opened on the pending queue — empty most of the time —
beside four tabs carrying no counts, and an empty list under unlabelled tabs
reads as *there is no history*.

* Each tab now carries its count: Pending 2, Approved 14, Rejected 1, All 17.
* An empty pending queue says where the decided ones went, and links to them.
* The card list is a table with the Applications page's filter scheme —
  sortable, narrowable by Course, Type, Term and Status, with a search box wired
  through the same bar so one script hides rows rather than two.

The review form did not survive as an inline block: it moved into a per-request
dialog. **Rendered by the server, not assembled in JavaScript** — the
imported-row choices are built per request from a live query, and the
Applications page's one-shared-modal-from-data-attributes trick cannot carry
them. `report-preview.js` became `modal-open.js` now that a second page uses it.

## Fixed: the sign-in background 404'd on Render

`media/` is gitignored. The exception under it —

    media/
    !media/logos/
    !media/backgrounds/**

— **never worked**. Git will not descend into an excluded *directory*, so a
negation for anything inside it can never take effect. The branding already in
the repo was there only because it had been force-added, and `git check-ignore`
reports tracked paths as un-ignored, so the rule looked correct from every angle.

That is how commit `4fd6e6a` shipped: it removed `media/backgrounds/registration.jpg`
and its replacement was silently unstageable, so the deploy had neither file and
the login and registration pages asked for a background that was not there.

Two changes, and the second is the one that matters:

* `media/*` rather than `media/` — excluding the children leaves the directory
  itself visible, which is what lets a negation in. The logos are genuinely
  re-includable now.
* **The page backgrounds moved to `static/img/backgrounds/`,** which is where
  assets of this kind belong. They are part of the application, not something a
  user uploaded. In `static/` they are committed by a plain `git add`, hashed and
  compressed by `collectstatic`, served by WhiteNoise with far-future caching,
  and need no hole punched in the permission view that guards `/media/`.

The CSS references them relatively (`url('../img/backgrounds/…')`) so
ManifestStaticFilesStorage rewrites them to the hashed names — verified: the
manifest maps `css/srms.css` to a hashed file whose three background URLs all
resolve to files that exist.

`api/media_views.PUBLIC_PREFIXES` still lists `backgrounds/`. Harmless, and left
alone: it is the hole that let an anonymous visitor see a login background at
all, and an old path may yet point at it.

## Added: `manage.py check_email <address>`

The one place in this system that is allowed to be loud about mail. Everywhere
else is quiet on purpose — `notify.send_email` catches and logs so a review
screen cannot fail over SMTP, and settings.py falls back to the console backend
so a laptop and the test suite never touch a mail server. Together those mean a
misconfigured deployment is **indistinguishable from a working one**: messages
go to the service log, every caller is told 'sent', and nobody is emailed.

This prints the configuration it is about to use, opens the connection, sends
one real message with `fail_silently=False`, and names the cause when it fails:

    python manage.py check_email you@example.com

* The console backend is reported as the non-delivery it is, never as success.
* `SMTPAuthenticationError` says to use a Gmail **App Password**, which is what
  that error nearly always means here.
* `SMTPSenderRefused` points at `DEFAULT_FROM_EMAIL` not being an address the
  account may send as.
* A host that does not resolve, a blocked port and a timeout each say so.
* Success says **accepted**, not delivered — a server taking a message is not
  anyone receiving it — and points at the spam folder and the provider's log.
* `EMAIL_HOST_PASSWORD` is reported as `set`, never printed. This runs in a
  shell whose scrollback gets pasted into chats.

Verified against a real socket, not just mocks: all four paths — unset host,
unresolvable host, refused credentials, and a successful send to a throwaway
SMTP server that confirmed the From, To and Subject that arrived.

## Fixed: a rejected registration held its email address for ever

Register, get rejected, try again with the correction — 'Email already
registered'. The student number was claimed the same way. So the one person who
could fix the mistake was the only one who could not: they could not
re-register, and could not edit an account they were locked out of either.

Rejections are usually *those details do not match our records* — a mistyped
student number, the wrong course. The answer to that is a corrected
registration, so a **rejected** account no longer claims either the address or
the student number. Registering again deletes it and starts a fresh submission:
pending, unconfirmed address, back in the SDSO queue.

Only rejected ones. A **pending** registration still blocks — it is waiting on
the office, not finished with — and an **approved** one is somebody's live
account.

The row is deleted rather than rewritten because a second attempt can change the
account type, which would leave a StaffProfile hanging off what is now a
student. What survives is an ActivityLog line naming the address, the student
number and the original reason: `ActivityLog.user` is SET_NULL, so the entry
outlives the account it describes. That matters when the rejection was for
something worse than a typo — the office can still see this address has been
through here before.

**The office's own route is unaffected**: verifying a rejected account from the
Account Verification page still lets that person straight in, for anyone who has
not re-registered over it.

The login page and the waiting room now say so, rather than sending everyone to
the office: *'If a detail was wrong, register again with the correction — this
address is free to use.'*

## Changed: the applicants report is a plain table, not CHED's form filled in

I had read the Annex 1 workbook as the template to fill. It is the **guide** —
it says which columns a TES applicant record carries, and nothing more. The
report is generated: one title line, one header row, one row per applicant.

What that changes:

* A `.xlsx` of one sheet, `TES Applicants`, instead of a `.xlsm` carrying CHED's
  four tabs, three dropdown validations and a VBA project none of which belong
  in a list the office reads. 6 KB rather than 358 KB.
* No 2,000-row ceiling and no overflow to report — that was the pre-formatted
  range in the template, and there is no template. `build_workbook` returns
  `(BytesIO, written)`.
* It builds whether or not the guide file is present. The guide is still read
  for `registry_programs()` and `disability_types()`, which drive the apply
  form's dropdowns, so a missing file costs those and not the report. The
  'Annex 1 template missing' badge is gone from both pages.
* Frozen headings and an autofilter, because thirty columns are unreadable
  without them, and `yyyy-mm-dd` on BIRTHDATE so Excel does not render it in
  whatever the reader's locale prefers.

`api/tes_report.py` is untouched and still fills CHED's Annex 2 in place — that
one *is* submitted on the form, and its formulas and signatory blocks have to
survive. This one is not submitted on any form, so it does not need one.

## Changed: the From address is derived from the account that sends

`DEFAULT_FROM_EMAIL` used to be a plain environment variable falling back to a
literal `no-reply@bipsu.edu.ph`. That invited a configuration which reads
correctly and is not true: **a mail server will not honour a From address the
sending account does not own.** Set it to `no-reply@bipsu.edu.ph` while signing
in as a Gmail account and Gmail rewrites it to the Gmail address and delivers
under that — recipients see one thing, the configuration claims another.

Unset, it is now `BiPSU SRMS <EMAIL_HOST_USER>`: the one address the sending
account is certain to be allowed to use, so the two cannot disagree. Taken from
the pattern the office already had working elsewhere.

An explicit `DEFAULT_FROM_EMAIL` still wins, for the cases where it is honoured — an
institutional mailbox, or an alias verified under Gmail's 'Send mail as'. A
value set to whitespace counts as unset rather than sending from nobody.

One less variable to get right in the Render dashboard: `DEFAULT_FROM_EMAIL` is
optional now, and `render.yaml` and `.env.example` both say so.

## Added: the deploy says so when no mail server is configured

`api/checks.py` — a Django system check, run by `python manage.py check` in
`build.sh` alongside `check_storage`. With `DEBUG=False` and no `EMAIL_HOST` it
prints, in the build log:

    (api.W001) EMAIL_HOST is not set, so no email will be sent.

A **warning**, deliberately, not an error. The site is genuinely usable without
mail — the office still reviews applications, students still read decisions in
their portal — so failing a whole deploy over it would be the wrong trade. But
it should be impossible to deploy without being told, which until now it was
not: the console backend accepts every message, writes it to the service log and
reports success.

That is the third and last place this is surfaced. The other two only speak when
somebody goes looking: the SDSO accounts page banner, and `check_email`.

**The locmem exclusion is load-bearing.** Django's test runner forces
`DEBUG=False` *and* swaps the backend for locmem, so without it the warning
printed on every single `manage.py test` — and one that cries wolf that often is
one nobody reads on the day it matters.

## Added: a Billing tab in the UniFAST portal

The Annex 2 workbook bills on two per-grantee figures — the TES benefit and the
TES-3A top-up for a grantee with a disability — and computes everything else
from them: the two column totals, the 1% management fee, the whole Form 1
statement. Nothing in the portal surfaced any of it, and both columns exported
blank for the office to type into Excel by hand.

`/unifast/billing/` is where an officer records what CHEDRO advised for a term.
The workbook then downloads filled, and the page shows the same arithmetic Form
1 does, so the total can be read before the file is opened.

**The rule that predates the tab is unchanged.** The amounts are still not the
system's to choose: with no `TESBilling` row for a year the columns export
blank, exactly as every year did before. What changed is that an officer now has
somewhere to put the figure CHED gave them, instead of a workbook they must
finish in Excel. A rate this system invented would still be a guess with a
signature under it — the difference is who typed it.

Three things worth knowing:

* **One row per school year.** CHED revises the rate, and last year's figure
  must not quietly bill this year's grantees. There is no 'all school years'
  option here for the same reason.
* **The top-up lands only on rows that record a disability.** Billing every
  grantee for a disability allowance is the expensive mistake available here,
  and CHEDRO reconciles it.
* **The 1% management fee is one percent of the TES benefits alone**, not of the
  subtotal — Form 2's own formula is `=SUM(N1101)*0.01`, so the top-ups sit
  outside it. The page computes it the same way rather than guessing.

The reference number and statement date Form 1 prints are stored here too, and
written into the sheet on download. Amounts are `null`, never `0`: zero is a
rate of nothing, which is a claim; null is 'we have not been told'.

Migration `0056`.

## Staff record and staff applications split into detail tables

The same treatment `StudentProfile` got. `StaffProfile` had grown to
twenty-four columns and `AffirmativeStaffApplication` to forty, and both now
keep only identity, address and outcome as columns of their own.

`StaffProfile` → `StaffEmployment` (the appointment, including separation),
`StaffPersonalInformation`, `StaffEducation`.

`AffirmativeStaffApplication` → `ApplicantInformation`, `ApplicantEnrollment`,
`ApplicantStaffEligibility`, `ApplicantEmployment`,
`ApplicantAffirmativeEligibility`.

Both proxy their columns through the same `DetailField` machinery the student
record uses, so `staff.position`, `app.course` and
`staff.save(update_fields=['school'])` mean exactly what they did before. **A
queryset still cannot**: `filter(enrollment__course='BSCS')`, not
`filter(course='BSCS')`. `STAFF_APPLICATION_DETAILS` spells the select_related
paths, beside `STUDENT_DETAILS`.

The application is the case the student record did not have. One table serves
two programmes, and which half of the columns a row fills depends on
`qualified_for`: a Staff row fills employment and staff eligibility and leaves
affirmative eligibility blank, an Affirmative row does the reverse. Half the
columns on any given row were always empty, which is a stronger case for the
split than the student record had.

Three columns had to be softened before they could move —
`contact_number`, `course` and `date_of_birth` were declared with no
`blank=True` and no default. They are softened in `0057`, before the copy,
rather than beside the drops in `0059`. A reversal replays `0059`, then `0058`,
then `0057`, so the tightening has to be the *last* step back or it meets a
column `0058`'s reverse has not filled yet. `0051` got away with putting its
`AlterField` beside the drops because a `CharField` re-adds as `''`, which
satisfies NOT NULL; a `DateField` does not.

`date_of_birth` is nullable now for the same reason, which incidentally removes
the need for the `'2000-01-01'` the apply view was inventing to get past the old
constraint. The fabrication is still there — nothing depends on it either way.

Migrations `0057`–`0059`.

## Fixed: a student could not open their own SHS or SUC certificate

`media_views` resolves an uploaded file back to its owner with a queryset —
`StudentProfile.objects.filter(shs_gpa_cert=path)`. `shs_gpa_cert` moved onto
`AffirmativeEligibility` in `0049`–`0051`, so that lookup had been raising
`FieldError` ever since: a 500 on `/media/profile/shs_cert/…` and
`/media/profile/suc_cert/…` for the person the document belongs to.

It went unnoticed because `_may_read` lets an office role through before
ownership is ever resolved, and the office is who normally opens these. The
same trap was waiting for `staff/appointment/` and the two `affirmative/`
prefixes in this change.

Both are lookup paths now (`affirmative_eligibility__shs_gpa_cert`), and
`test_staff_record_split.py` walks every entry in `_OWNER_RESOLVERS` and
`_EMAIL_OWNED` as an owner rather than as an officer, which is the only way this
class of break shows up in testing.

## Removed: the Affirmative applicant list, and Endorse with it

**Nobody applies for Affirmative Action.** Eligibility is worked out from the
student's own profile by `AffirmativeRecommendation.evaluate_and_sync` — SHS GPA
against the passing threshold, SUC entrance exam at 50%, not already a TES
beneficiary — and Student Ranking is where that is read. The page nevertheless
opened on an **Applicants** tab that ranked `AffirmativeStaffApplication` rows,
which is a submission that cannot be made.

It was dead in the strict sense as well. No form has ever written `shs_gpa`,
`suc_exam_score`, `suc_exam_total` or `is_tes_beneficiary` onto an application —
only `seed.py` does — so `_aff_score` returned 0 for every row and
`_applicant_rules` marked every one ineligible. The tab was a permanently empty
ranking of a permanently empty score. The numbers the office actually decides on
are on `AffirmativeEligibility`, which is what the remaining table reads.

Gone with it:

* The tab bar. One table, so there is nothing to switch between.
* **Endorse and Disqualify**, and with them the whole Actions column. The award
  is recorded on the Archives page like every other programme's, so a status set
  here was a second, private answer to a question already written down somewhere
  the reports read. What a recommendation says is now decided only by the rules.
  **Re-evaluate** stays — it is the one thing the page can be told to do.

  `Disqualified` remains a status: `evaluate_and_sync` still writes it itself
  when a student stops passing, which is the difference between a rule and an
  opinion. `AffirmativeRecommendation.notes` is now written by nothing — it was
  only ever filled by the disqualify form. The column is left in place rather
  than dropped, because whatever an officer typed into it is still a record of
  why somebody was set aside.
* The `applicants` array on `/api/vpsea/ranking/`, which mirrored the page and
  would otherwise have disagreed with it about what the page is.
* The `('Endorsed', 'Endorsed')` choice on `AffirmativeRecommendation.status`.

Migration `0061` moves any row still saying `Endorsed` back to `Recommended`
before the choices change. Changing the choices alone would leave those rows
holding a value the field no longer offers — valid in the database, invalid to
every form and to `get_status_display`. There were none in the working database;
the migration is for whatever production holds.

**What did not change:** the Affirmative Action programme itself. It is still a
scholarship type, still an archive category, still a masterlist section, and the
office still records approved scholars against it. What went is the pretence
that somebody applies for it.

## Fixed: the masterlist called Affirmative Action 'An Waray'

Both masterlists — the document and the spreadsheet — headed the Affirmative
Action block `AN WARAY (*)`. An Waray is a different scholarship programme, not
another name for this one, so every masterlist printed one programme's scholars
under another's heading.

The section now reads `AFFIRMATIVE ACTION (*)`, matching `BiPSU STAFF (@)` above
it. The `(*)` is the document's own footnote marker and stays.

## The whole student record is collected at registration

The signup form used to ask for a name, an email, a student number, a course and
a year level. Everything else waited on My Profile, which a student had no
reason to open and the office had no way to make them open — so the SDSO were
verifying registrations against their enrolment list with five fields to check,
and the TES form, the masterlists and the Affirmative ranking all read columns
nobody had filled in.

`templates/register.html` now carries the same groups My Profile does: Personal
Information (including address, birth place, civil status and disability),
Academic Information, Educational Background, Scholarship Eligibility
Information, TES Eligibility Information and Socioeconomic Information. Only the
email and the password belong to the account; the rest is the student record, and
My Profile is the window onto it afterwards.

The account verification queue shows all of it — see below — because a queue
showing six of forty fields is asking an officer to verify a registration they
cannot read.

**The lock rules are unchanged and now bite at registration.** Birth place,
civil status, educational background and the address lock once filled, which is
the first save either way. Family background is *not* asked here, so it is still
entered on My Profile.

## Removed: Person with Disability as a checkbox. Ask which disability instead

`is_pwd` was a checkbox in Socioeconomic Information. The same student was
separately asked, on the TES application, to name their disability from CHED's
own `Disability_List` — so the system held two answers to one question and
nothing kept them in step.

The question is asked once now, in the shape CHED asks it: a **Disability Type**
dropdown in the **Personal Information** card, the same list and the same
`Other` box the TES form uses. `StudentProfile.is_pwd` is a property read off
it (`states_a_disability`), so everything that read the flag still does.

Migration `0062` adds `PersonalInformation.disability_type` and carries a ticked
box across — to the disability already named on that student's TES application
when there is one, and to `Unspecified Disability` when there is not. That
records the declaration without inventing a condition to go with it, and the
profile form shows it under `Other` where the student can replace it.

## Removed: three socio-economic checkboxes

Dropped in migration `0063`:

* **University Athlete** and **From Coconut Farmer Family**. Collected, and then
  read by nothing that decides anything — Sports and CoScho are awarded off the
  office's own lists, not off a box a student ticks. `Scholarship.match_score`
  lost its `is_athlete` clause with them.
* **Has Other Scholarship**. It said a student holds something else without
  saying what, which is a question the office could not act on and the TES rules
  could not settle: ongoing government assistance disqualifies, one-time
  emergency help does not, and a bare boolean cannot tell them apart. Replaced by
  the declaration below.

## Link Scholarship moved into registration

**Gone:** `/student/link-scholarship/`, its nav entry, `/vpsea/link-requests/`,
its nav entry and its badge, and `static/js/link-scholarship.js`.

A student who already holds a scholarship says so on the registration form: a
checkbox in Socioeconomic Information, a dropdown naming *which* scholarship, and
a **Scholarship Data** card — revealed by the checkbox — holding the CHED tier,
the award number, the proof document and any notes. It is stored as the same
`ScholarshipLinkRequest` as before.

The SDSO decides it **on the account verification queue**, in the same action
that releases the account. Verifying writes the Approved Application, claims the
matching imported row, and backfills the profile from it, exactly as approving a
link request did — `approve_declared_scholarship` in `api/student_views.py` is
that code, moved rather than rewritten. Rejecting the account turns the
declaration down in the same words. The queue offers the archive candidates and
the CHED tier correction it used to offer, next to Verify.

`ScholarshipLinkRequest` itself stays: it is still the record of what was
claimed, who verified it and what the proof was.

**What the student sees instead:** a read-only **Scholarship Data** card on My
Profile, listing approved awards, an approved TES subsidy, and a declaration the
office is still checking or has turned down — with the reason. A student holding
nothing sees no card at all.

## Dual scholarships: TES and Academic, and nothing else

TES is a UniFAST subsidy and an Academic scholarship is BiPSU's own recognition
of a grade, so neither is the "other government assistance" that would
disqualify the other. Every remaining programme is exclusive.

`held_scholarship_types` reads what a student holds from all three records that
can say so — the awards ledger, an approved `TESApplication` (UniFAST decides
those on their own screen and writes no Application), and an approved
declaration for the active term — and `can_hold_alongside` answers whether one
more may be added.

What changed as a result:

* The nav offers each Apply page per programme, not per student. An Academic
  scholar still sees **Apply: TES**; a TES grantee still sees **Apply:
  Academic**; anyone holding TDP, DOST, CHED or the rest sees neither.
  `can_apply_academic` and `can_apply_tes` are answered by
  `api/context_processors.py`, so every page agrees.
* Both Apply pages refuse a submission the rule would not allow, and say which
  programmes are in the way. `apply_tes.html` gained the blocked panel
  `apply_academic.html` already had.
* `enrolled` still means "holds anything at all" and still drives Renewal and
  the Scholarship Data card.


## Added: a Liquidation tab in the UniFAST portal

Billing states what the office asked CHEDRO for. Nothing recorded what happened
to the money after it arrived, so the account of it lived in a spreadsheet
beside the system rather than in it.

`/unifast/liquidation/` is the other half of the pair: the remittance CHED
actually sent, what the cashier released to each grantee, and the balance the
office is still holding. `TESLiquidation` carries the remittance, one row per
school year; `TESDisbursement` carries what became of one grantee's share.

**The grantee list is not maintained here.** It is exactly the list the billing
and the CHED workbook use — `tes_report.grantee_rows` — so the liquidation can
only ever account for the people the office actually billed for, and a row
posted for anyone else records nothing. The list is re-read from the database on
every save rather than trusted from the form.

Four things worth knowing:

* **Nothing is assumed from the billed rate.** A liquidation that fills itself
  in at the billed amount reconciles perfectly every time and therefore cannot
  detect the thing it exists to detect. A grantee with no row is reported as
  *unaccounted for* — not as paid, and not as zero. The "Fill in the billed
  amount" button fills the boxes in the browser and saves nothing; an officer
  still reads the rows and submits them.
* **Unclaimed is its own status, and its money is not subtracted.** A grantee
  who never collected is the ordinary reason a liquidation does not balance.
  That money is still the office's to hold, so it sits inside the balance by
  construction and is counted separately rather than netted off.
* **Only a release carries an amount.** A row moved back to Unclaimed drops its
  amount and date, or the totals go on counting a payment that was retracted.
* **Releasing more than arrived is flagged, not printed as a negative.** A
  balance below zero is not an unusual balance, it is a mistake somewhere — a
  mistyped amount or a credit advice entered short — and the page says so.

The balance is `None`, shown as an em dash, until a remittance is recorded. A
page reporting "nothing received, everything owed back" on a term nobody has
touched is worse than one that says the remittance is not in yet.

Migration 0064.

## Fixed: scholarship cards showed the university's seal for every funder

The landing page put `media/logos/BiPSU.png` on all three card sections and in
every modal, including the programmes BiPSU does not fund. A DOST scholarship
advertised under the university's own logo is not a cosmetic slip — it is a
claim about who pays for it, made on the first page a prospective student sees.

`Scholarship.logo_url` resolves the funder's seal from the programme type
through `SCHOLARSHIP_LOGOS` in `api/constants.py`, following the university's
own programme chart: DOST runs the S&T undergraduate scholarships and JLSS, CHED
runs CHED-Merit and CoScho, and TES and TDP are UniFAST's however often the two
are spoken of together. A property rather than a column — the answer follows
from the type and nothing about it is per-row, so storing it would mean a
migration, an admin field, and a way for one card to disagree with the rest of
the system about who funds a programme.

A type with no agency logo on file falls back to BiPSU's seal, which is what
every card showed before. **GSIS is the one programme still in that fallback**:
there is no GSIS logo in `media/logos/`. Drop one in and add the line to
`SCHOLARSHIP_LOGOS` when the office supplies it.

The navbar keeps the BiPSU seal. That one really is the university's.

## Fixed: the registration page printed a template comment at readers

`templates/register.html` opened a `{# ... #}` on one line and closed it on the
next, which Django does not treat as a comment at all — so two lines of prose
about StaffProfile were rendered onto the form. `api/test_template_comments.py`
has guarded against exactly this since the archive table did it; the test was
failing on `master`. Now a `{% comment %}` block, like every other multi-line
comment in the templates.


## Registration asks about eligibility last, and only of a student who holds nothing

**Scholarship Eligibility Information** and **TES Eligibility Information** used
to sit in the middle of the registration form, above the box that asks whether
the applicant already holds a scholarship. Both now come last, after Scholarship
Data, and both close the moment that box is ticked.

They ask what someone might qualify for. A student who has just declared an
award has already answered that, and asking anyway collected two accounts of the
same fact that could disagree — somebody could declare "I already hold a
scholarship: TES" and, further up the same form, leave "I am a current TES
beneficiary" unticked, and both were recorded.

The order change is the point, not decoration: whether you hold something
already decides whether the rest of the questions are worth asking, so it is
asked first.

Three things worth knowing:

* **The `hidden` attribute is rendered by the server**, not only toggled by
  `static/js/register-scholarship.js`. A form coming back from a validation
  error is right before any script runs, and a reader without JavaScript is
  never shown a question the form has stopped asking.
* **The fields are disabled, not merely hidden.** A hidden input still posts, so
  a student who typed a GPA and then ticked the box would have recorded an
  answer to a question that was no longer on screen.
* **"Hidden" is not simply "not declaring".** On a staff registration nothing is
  declared either, and reading it the short way revealed two student cards on
  the staff form. The script asks whether it is on a student form *and* the box
  is clear.

One consequence to be aware of: **`is_tes_beneficiary` lives in the Scholarship
Eligibility card**, so a student who declares any scholarship no longer posts it
and it stores as False. That is the intended reading — a held award is declared
once, in Scholarship Data, where the proof goes — and nothing in the system
currently branches on that column. If a report ever needs "is a TES beneficiary"
it should read the declared award, not this flag.

Every eligibility field was already optional server-side, which is what makes
closing the cards safe: a post without them records nothing rather than failing.


## Registration marks every field it does not need

The form asks for around forty things and refuses a registration over six of
them. Nothing said which, so the only safe reading was that all of it mattered —
and a form that long, with no way to tell what can be skipped, is one people
abandon halfway.

Every optional field now carries a quiet **Optional** marker beside its label
(`.label-optional` in `srms.css`, written against `--text-muted` so it follows
dark mode without a patch).

**The marker is only worth anything if it is applied to all of them.** If some
optional fields carry it and others do not, its absence stops meaning
"required" and the whole device becomes decoration. So the rule is exact, and
`api/test_register_optional_labels.py` checks it in both directions: every field
`register_view` can refuse a registration over is unmarked, and every field it
cannot is marked.

What stays unmarked, and why:

* **first name, last name, email, password, confirm password** — the five the
  form has always marked `required`.
* **student ID** — required for a student registration and always was
  (`'Student ID is required.'`), though the input never said so to the browser.
  **It does now.** It sits in a `data-student-only` card, so `setBlocksHidden`
  lifts the attribute again on the staff form; a required field inside a hidden
  block blocks the submit with a message nobody can see.
* **scholarship type, proof document, CHED award tier, and the "please specify"
  box under Disability Type** — required only once the thing they belong to is
  chosen. `register-scholarship.js` marks them required as it reveals them.
* **Checkboxes.** An unticked box is an answer rather than an omission, and
  "Optional" beside one reads as a question about the box instead of the fact.

The form also used to say "(optional)" in two places and "(if applicable)" in a
third. Three spellings of one idea read as three different rules, so all of them
are now the single marker.

## Fixed: two tests that had gone stale against the code they cover

Both were failing on `master` and neither was testing anything that had actually
broken — the code moved and the assertions did not follow.

* `test_tes_ranking` called `StudentProfile.objects.create(is_pwd=True)`.
  `is_pwd` stopped being a column when the PWD checkbox was replaced by the
  disability the student names; it is a derived property with no setter, so the
  call raised `AttributeError`. The test now names a disability, which is what
  the form asks and what `tes_ranking` reads.
* `test_editable_submissions` looked for `'cannot apply to another scholarship'`,
  a string that is not in `student_views.py` at all. Approving the Academic
  application puts `Academic` in `held`, which is `scholarship_block_reason`'s
  *"you already hold this one"* branch — `'You already hold the Academic
  Scholarship. There is nothing to apply for.'` — not the "enrolled in something
  else" branch the old wording came from.

A third failure, in `test_check_email`, is **not** fixed and is not a code fault:
it asserts the fallback From address for a deployment with no mail configured,
and a developer whose `.env` has `EMAIL_HOST_USER` set will always see their own
address instead. It passes where mail is unconfigured and fails on a working
laptop.
