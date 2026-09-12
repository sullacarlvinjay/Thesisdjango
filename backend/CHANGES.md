# Requested changes

A record of what was asked for and why, so nothing here gets "tidied away" later
by someone who reads it as an accident. **Do not undo any of these unless you
decide you want the behaviour gone** — each one was a deliberate request, and
several of them removed something that used to work.

---

## A scholarship won after registration can be added from My Profile

The registration form asks what a student already holds, and that was the only
time anybody was ever asked. A student who registered in first year holding
nothing and won DOST in second had nowhere to say so — the question lived on a
form only a new account could reach, and they already had one. Their portal went
on showing no scholarship, offered no renewal, and counted them among the
unserved on every report, while their name sat unclaimed in the office's
imported list.

**My Profile now carries the registration form's Scholarship Data card.** Not a
page of its own: My Profile is already where a student answers "what is true
about me now", and it already listed what they hold. The card is the same card —
the same `I hold a scholarship…` checkbox, the same three cards behind it, the
same field names, and `static/js/register-scholarship.js` itself driving them,
so "+ I hold another scholarship" and **Remove** behave exactly as on
registration. It is read by the same `_declared_scholarships`, so the two doors
cannot drift apart in what they accept or in the words they refuse it with.

The read-only list of held awards did not go anywhere; it is now the top of that
card rather than a card of its own, and it no longer vanishes for a student
holding nothing — which was exactly the student with something to declare.

One form, one save: a proof document the office would refuse takes the whole
page back rather than letting half of it through. `declaration_blocked_reason`
closes the question — with a sentence saying why — when there is no student
record yet, one already waiting, or an award already held.

**The SDSO decides it on Account Verification**, in a section of its own —
*Scholarships added by verified students* — below the registrations. Not a queue
of its own: the office decides scholarships in one place. It cannot ride on an
account decision the way a registration's declaration does, because that account
was released terms ago, so each is verified or refused on its own with the same
two buttons, the same archive matching and the same CHED tier correction.
Verifying calls `approve_declared_scholarship`, exactly as the registration cards
do — nothing about the award it writes differs by which door the claim came
through.

The **Account Verification badge** now counts these as well as waiting
registrations. They carry no other signal at all — no new account, no
application — so an officer with an empty registration queue would have read a
clear sidebar with awards sitting undecided behind it. `notify.scholarship_added`
emails the office when one arrives, for the same reason.

`ScholarshipLinkRequest.filed_in_portal` (migration `0086`) is only which door a
row came through, so Account Verification can tell a registration still waiting
to be released from an account released terms ago. Existing rows are `False`,
which is correct: all of them came from registration forms.

Guarded by `api/test_add_scholarship.py`.

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


## The catalogue lists what the university's own chart says BiPSU offers

Four programmes on BiPSU's scholarship chart had no entry, so the landing page
advertised a shorter list than the university actually runs: **FHE**, **SUC-TDP**,
**JLSS**, and the **RA 7687** track of the DOST undergraduate scholarship.

The catalogue goes from 10 programmes to 13. Migration 0065 — a `choices` change
only, no new tables and no data touched.

Two decisions worth not undoing:

* **RA 7687 and Merit are two tracks of one programme, not a stored tier.** The
  existing entry was named "DOST Merit Scholarship", which is one of the two, so
  RA 7687 was represented nowhere. It is now "DOST S&T Undergraduate
  Scholarship" and names both tracks in its eligibility list. It did **not**
  gain an `award_tier` the way CHED has one: CHED carries a tier because every
  masterlist prints CHED in two separate blocks, and nothing reports DOST that
  way — a tier column here would be a field nothing reads. `type` stays `DOST`,
  which is what the approval routes, the archive tabs and
  `DEFAULT_COLUMNS_BY_TYPE` all match on.
* **FHE is listed but not declarable.** `SCHOLARSHIP_TYPE_CHOICES` is the list of
  awards a student can say they *already hold*, and it feeds
  `held_scholarship_types`. Free Higher Education under RA 10931 is not awarded
  to a shortlist — it is the tuition every qualified SUC student already has —
  so there is nothing for the SDSO to verify, and listing it there would make it
  *exclusive*: `can_hold_alongside` would then refuse a TES or DOST application
  from a student for holding what all of them hold. TES is absent from that same
  list for the related reason that it is applied for in this portal.

SUC-TDP and JLSS **are** declarable: both are awarded by an agency and
verifiable against the office's records, which is what that list is for.

Seals follow the chart's funding lines — JLSS wears DOST's, FHE and SUC-TDP wear
UniFAST's. GSIS remains the one programme falling back to BiPSU's seal, because
there is still no GSIS logo in `media/logos/`; a test now pins that so a future
programme cannot join it silently.

**The copy is the office's to confirm.** The descriptions, eligibility lines and
benefits for the three new entries were written from the programme names on the
chart and general knowledge of the schemes, not from an office document. What is
structural — `type`, `group`, the seal, and whether a programme is declarable —
is what the tests hold.

Three tests in `test_bootstrap` asserted `Scholarship.objects.count() == 10`.
They now compare against `len(SCHOLARSHIPS)`: what each of them means is
"seeding produces the catalogue and nothing extra", and the office adding a
programme should not fail three tests that are not about how many there are.


## A programme the office adds can say whose seal it wears

`Scholarship.logo_url` resolved the seal from the programme type alone. That
covers every programme in the catalogue and nothing else — and
`/vpsea/scholarships/add/` exists precisely to create programmes with types the
funding map has never heard of, so anything the office added wore BiPSU's seal
whoever funded it. The fault the mapping was written to fix, reintroduced
through the one route that can outrun it.

The programme form has a **Logo** picker now, and `Scholarship.logo` stores the
choice. Migration 0066.

Three things worth knowing:

* **Blank still means "work it out from the type."** The column is an override,
  not a replacement: every catalogue programme resolves exactly as before, and
  clearing the box returns a programme to its type's default. `logo_url` reads
  the column, then `SCHOLARSHIP_LOGOS`, then BiPSU's seal.
* **It is a picker, not an upload.** `media/logos/` is served straight off the
  filesystem — `api.media_views` reads it through `FileSystemStorage`,
  deliberately *not* the uploads bucket — and Render's disk does not survive a
  deploy, so an uploaded seal would be gone at the next one. The options come
  from `constants.available_logos()`, which lists the directory, so a seal
  committed to the repo is offered without a code change. Supporting upload
  means answering the storage question first.
* **The posted value is validated, not trusted.** It is rendered straight into
  an `<img src>`, so `_posted_logo` keeps it only if it is one of the names that
  listing returned; a path, a URL or a deleted file is discarded and the
  programme falls back to its type's default.

## Fixed: JLSS appeared as a tab in the UniFAST office's archive

Both archive screens build their tabs from the programmes actually in the
database, which is what makes a newly added programme appear without a code
change. UniFAST's list is "its own, plus anything added since that is not the
SDSO's" — and that second test was an inline literal listing the SDSO's
programmes. Adding JLSS, DOST's junior-level scholarship, therefore put a DOST
tab in the wrong office.

The list is `SDSO_TYPES` now, named once beside `UNIFAST_TYPES` instead of
written out inline.

`UNIFAST_ARCHIVE_TYPES` is separate from `UNIFAST_TYPES` on purpose. FHE and
SUC-TDP are UniFAST's and belong in its archive, but `UNIFAST_TYPES` also scopes
the dashboard counts and the analytics charts — adding them there would have
given both a permanently empty series. What an office *archives* and what it
*reviews* are different questions, and they now have different lists.

A test asserts every catalogue programme is named in one list or the other.
Without it, the next programme added falls through the same default and lands in
whichever office that default happens to point at — which is exactly how JLSS
got there.


## Benefits for the UniFAST programmes come from the 2026 guidelines

The benefit lists on the landing page were written from the programme names.
Against the UniFAST 2026 guidelines (Board Resolution No. 2026-012, 08 July
2026) one of them was simply wrong: **Tulong Dunong** promised "a monthly
stipend for living expenses", a tuition subsidy and a book allowance, where
Section 3 makes it a single flat grant of PhP 7,500 a semester. **TES** quoted
only an annual ceiling and named none of its three additional grants.

TES, TDP, SUC-TDP and FHE now carry the figures the guidelines state:

* **TES** — PhP 10,000 a semester / PhP 20,000 the academic year, plus TES-3A
  (PhP 5,000 a semester for a grantee with a disability), the same again for a
  dependent of a solo parent or a member of an ICC/IP community, TES-3B (up to
  PhP 8,000 reimbursed once towards licensure costs) and SARDO (a one-off PhP
  10,000 after a sudden disruption).
* **TDP and SUC-TDP** — PhP 7,500 a semester / PhP 15,000 the academic year,
  released within 15 working days of the university receiving the funds.
* **FHE** — no tuition and no other school fees, with the deck's one
  qualification: the *first* copy of the school ID, library ID and handbook is
  free and repeat copies are charged.

**The SUC rate is the one quoted, and the private-HEI rate is deliberately
left out.** No BiPSU student is paid on it, and printing both invites a grantee
to expect the larger figure. A test asserts it stays out.

**One line needs the office's confirmation before it is trusted.** The deck's
Section 4 appears to show the PhP 5,000 top-up twice — once headed "PWD
(TES-3A) Additional" and once "Dependent of Solo Parent / IP" — but slide text
extraction flattens layout, and the CHED Annex 2 column is named "TES-3A (PWD)
AMOUNT". Either the guidelines widened the top-up beyond PWD and the billing
under-bills, or the two headings are one block and the second benefit line
should go. It is written as the deck presents it.

Nothing was quoted for DOST, JLSS, CHED, CoScho, GSIS or the internal
programmes — those decks cover TES, TDP and FHE only — and a test asserts no
peso figure leaked into them.


## Eligibility and background follow the benefits into the 2026 guidelines

The benefit figures came over first; the prose around them still described the
programmes in general terms, so a card could quote an exact peso amount beside a
background paragraph written from the programme name. TES, TDP, SUC-TDP and FHE
now take all three fields from the same source.

What the guidelines added that the old copy did not say:

* **TES ranks rather than grants.** Priority 1 is a household in the current
  DSWD Listahanan; solo-parent dependents and NCIP-recognised ICC/IP members are
  Priority 2 and explicitly *subject to available funds*; the 4Ps list stands in
  only if the Listahanan is discontinued. The background carries the sentence
  the guidelines are emphatic about — applying is **in no way automatic
  eligibility**, being subject to validation and to funds. A student reading the
  old card had no way to know any of that.
* **TDP is funded a year at a time.** A new grantee for AY 2026-2027 becomes a
  continuing grantee *only if similar funding is provided in the following
  fiscal years*. A first award is not a promise of support to graduation, and
  the background now says so.
* **The disqualifiers are eligibility too** — no second undergraduate degree, no
  other national StuFAP, enrolment in at least two terms an academic year,
  completion within the maximum residency rule plus a year, and telling CHEDRO
  about a drop-out, deferment or transfer.

**FHE is the least evidenced of the four and is marked as such.** Its two
eligibility slides — "Who may avail for FHE" and "Exceptions to FHE" — are
images, so there is no text to quote. What is listed comes from the parts stated
in text elsewhere in the deck, and the background says plainly that the office
should read those slides beside it.

Nothing was rewritten for DOST, JLSS, CHED, CoScho, GSIS or the internal
programmes. Those decks cover TES, TDP and FHE only.

### A test for prose that compiled wrong

These entries are written as adjacent string literals wrapped across source
lines, which Python concatenates with nothing in between. Drop the space the
wrap consumed and `'no other'` compiles to `'noother'` — invisible in the
source, plainly wrong on the page. It happened twice while this was being
written: once on a space, and once *inside* `DSWD-certified`, because the
wrapper broke on the hyphen too.

`CatalogueProseTest` now checks every catalogue string for words run together,
spaces inserted inside hyphenated words, and stray or doubled whitespace. Worth
having: proofreading catches this only if you happen to read the one line it
landed on.


## The No Scholarship tab counts only verified students, and can delete one

Two complaints about the same table, `templates/vpsea/archives_unawarded.html`.

**It listed people who had not been let in yet.** The tab excluded accounts the
office had rejected at registration but kept the ones still sitting in the
verification queue — the reasoning being that once approved they would be
exactly the student to invite. In practice that put a registration submitted two
days ago, with an email address nobody has confirmed, in a table headed "students
the system has not served", marked *Never applied*. It cannot have applied: the
account cannot sign in until the office decides on it. The row read as a
follow-up the office owed the student when the thing actually owed was a decision
one screen over, on Account Verification, where the same person was already
queued. Both listings now take `verification_status='approved'` — the archives
tab and the No Scholarship tab of the students screen, which have to agree.

An **unconfirmed email address is not a reason to hide anyone**. It does not gate
signing in, only whether mail reaches them, and the accounts screen is the one
that warns about it. A verified student who never opened the link still appears
here, and a test says so.

**There was no way to remove a row.** Edit was the only action, so a duplicate
registration — the office had two for the same person — could be corrected but
not deleted. `/vpsea/archives/student/<pk>/delete/` takes the account and
everything that cascades off it, which is the only thing that would take the row
off the tab; the other archive tabs delete an award and leave the student behind,
and there is no award here to delete. POST only, so no crawler or mistyped URL
can remove anybody, and it asks first through the portal's own confirm dialog
rather than `window.confirm()`.

### A stale display name in the viewer test

`test_declared_scholarship_proof_uses_the_overlay` spelled the overlay label out
as `DOST Scholarship — proof`. Splitting DOST into the S&T Undergraduate and
Junior Level Science programmes renamed the choice to `DOST S&T Undergraduate
Scholarship`, and the test had been failing since — for a rename, not for
anything about the overlay it exists to check. It now builds the label from
`get_scholarship_type_display()`, the same source the template reads, and runs it
through `escape()` because the new name carries an ampersand.

## A TES Validation tab: award numbers and release batches

CHED issues two labels *after* the decision, and neither had a home.

**The award number** could only be typed on one grantee's review form, so
stamping a term's worth of numbers meant opening every applicant in turn.

**The batch was not stored at all.** It was a parameter of the *download* —
`?batch=` on the URL, printed onto every row of the Official List alike — so an
office that released half its grantees in one batch and half in the next had no
way to say so. It is a column on CHED's form describing a group of grantees, not
a property of a report, and it is now a field on `TESApplication`
(migration `0067`).

`/unifast/tes-validation/` lists the approved grantees for a school year with an
award-number box on every row, a checkbox beside each, and one batch box that
applies to everything ticked. Only approved grantees appear: CHED issues a
number against a grantee, not an applicant, and a number typed before the
decision is a number for an award that may never be made. A hand-made POST
naming a pending application is refused on the same ground.

**Both buttons save the award numbers.** Reading those boxes only under their
own button would mean an officer who typed a column of numbers and then pressed
Assign lost them without being told — the two jobs share a screen because they
are done in one sitting.

An empty batch box is a value, not a missing field: it takes the ticked
grantees back out of a batch, because one typed by mistake has to be removable.
Blank still prints as **On-going**, and `grantee_rows(batch=...)` still stamps
the argument on grantees who have no batch of their own, so an existing
`?batch=` download is unchanged for a list nobody has batched yet. A stored
batch wins over it.

Both actions are written to the activity log. Money follows these two labels
into CHED's billing, so who stamped what is worth being able to answer.

**This screen is expected to change.** It was asked for alongside a note that
validation, liquidation and billing are all still being worked out, so nothing
here should be read as the settled shape of TES validation.

## The two CHED liquidation forms, generated

The office works from a spreadsheet (`TDP-Batch-21.1-127500.xlsx`) whose
`Reminders` sheet lists what goes back to CHEDRO. Two of those are forms this
system had the data for and no way to produce:

* **TES-5 Form — Fund Utilization**: what arrived, what went out, what is left.
* **TES-4 Form — Report of Checks Issued**: every cheque, certified by the cashier.

Both download from the Liquidation tab, which is where they belong — it already
held the remittance, the credit advice and the report number, which is most of
the TES-5's heading. `api/tes_liquidation_forms.py` builds them; migration `0068`
carries the new columns.

### A cheque is not a grantee

The forms are keyed on cheques, and the system only knew about grantees.
`TESDisbursement` records what reached each *person*, which is what the office
needs to chase an unclaimed share — but one cheque pays a whole payroll. The
office's own sheet describes seventeen grantees in a single line: *"17 TDP 21.1
grantees 2025-2026 1st Sem Arandia, Sheila Mae et al"*.

Grouping disbursements by date would have printed seventeen rows where the form
has one, and would still have had nowhere to put the cheque number, the DV
number or the payee — none of which is a fact about a grantee. So `TESCheckIssued`
records them, and the two models answer their own questions: disbursements say
who was paid, cheques say what left the account. Both forms read the same cheque
list, which is why the TES-4 the cashier certifies and the TES-5's disbursement
block cannot come to disagree.

### Signatories are data, not code

Five named officers sign these — a focal person, a finance officer, the
president, an audit team leader, and the cashier who swears the TES-4
certification alone. They are fields on the liquidation row, entered on the
page. A name compiled into the generator is a name nobody in the office can
correct without a deploy, and blank prints an empty line above the caption —
a form waiting for a signature, never somebody else's name on somebody's
certification.

### What is reproduced, and what is not

The **form**: the same headings, column order, certification wording and
signature blocks, with the totals and the balance as live formulas so the sheet
still reconciles if an officer corrects a cell before signing — which is why
CHED asks for a workbook and not a PDF. Both were rendered through LibreOffice
and recalculate with no formula errors.

Not reproduced: the office's own file is eight sheets, six of them past
submissions kept for reference, with two rounds of disbursements stacked down
the TES-5 page because that is how that batch was paid. One remittance block and
one disbursement block is the faithful shape of the form itself.

The remittance line's *Particulars* is written as `TES funds for <year>` and
expected to be edited. The office writes a batch reference there — 'OG TDP
(Batch 21.1) for the first semester AY 2025-2026' — and nothing recorded here
can reconstruct that wording. A guess dressed up as a batch reference would be
worse than a line the officer overwrites.

**Both forms are titled TES-4 and TES-5 whatever the money paid for.** The
sample is a TDP batch on TES-numbered forms, because these are UniFAST's
liquidation forms, not the TES programme's.

**This screen is expected to change**, for the reason recorded above the TES
Validation entry.

## The masterlist gained tables for the three programmes it was missing

SUC-TDP, JLSS and FHE were added to the catalogue, given seals, and made
archivable — but nobody added them to `PROGRAM_SLOTS`, so the SDSO masterlist
had no table for any of them. A scholar under one of those three was on file,
visible in the archives, and absent from the document the office actually files.

The office template carries sixteen program blocks and only eleven were filled;
the three take `program13`, `program14` and `program15`. `program11` stays
unused for the reason already recorded there — its table has only a female loop,
so anything placed in it silently loses half its scholars.

None of the three is reviewed in this portal, so they fill from the office's
Excel import, which `apps()` already folds in alongside portal applications.

`MasterlistCoversEveryProgrammeTest` now walks `SCHOLARSHIP_TYPE_CHOICES` and
fails if any programme has no slot. This omission was invisible precisely
because an empty table and a missing table look identical until somebody counts,
and the next programme added would have repeated it.

## The student profile no longer shows the derived middle initial

It was a read-only box directly under the Middle Name it is derived from: not
editable, and saying nothing the field above it does not already say.

**The staff profile keeps its own.** Only the student profile was asked for.

`middle_initial` itself is untouched. The Staff, GSIS, CoScho and Sports
masterlist columns ask for an initial rather than a middle name, and
`format_full_name` builds 'Dela Cruz Jr., Juan R.' out of it.

## The TES Validation tab was removed, and the Liquidation page cut back

Both were asked for and then asked to be taken out again. Recorded here so
neither is re-derived as an improvement later.

### TES Validation is gone entirely

The screen, its route, its nav link, its JavaScript, its tests, and the `batch`
column it added to `TESApplication` (migration `0069` drops it). `grantee_rows()`
is back to stamping the `?batch=` argument onto every row of the Official List,
which is what it did before — so the BATCH column again carries one string for
the whole download, and an office releasing grantees in two batches again has no
way to say so. That limitation is known and accepted.

Award numbers are once more entered one at a time on the TES review form.

### The Liquidation page keeps only what generates the two forms

The remittance card and the Statement of account came off. What is left is the
year summary, the cheque list, and the per-grantee table.

**The consequence worth knowing.** `TESLiquidation` still holds
`funds_received`, `received_date`, `credit_advice_no`, `report_no`,
`report_date` and the five signatories, and both forms still print them — but
nothing in the portal writes them any more. On a term where they were never
set, the TES-5 prints its remittance line and all four signature blocks blank,
and the TES-4 prints no report number and no cashier. The workbooks are
editable, so those are filled in Excel before signing. The columns are kept
rather than dropped so that a term where the office already entered them still
prints them, and so re-adding an entry form later is a template change rather
than a migration.

The two download buttons carry their own school-year picker and name the year
they will produce — `TES-5 Fund Utilization (2026-2027)`. The remittance card
used to supply that context, and a workbook downloaded for the wrong term is not
obviously wrong until CHEDRO reads it.

## The TES batch came back, on the review form

Removed with the Validation tab, then asked for again — this time beside the
award number on the TES Applications review screen, which is where it belongs:
CHED issues both labels once a grantee is approved, and they arrive together.

`TESApplication.batch` returns in migration `0071`, and `grantee_rows()` again
prefers a grantee's own batch over the `?batch=` argument, which stays as the
fallback for rows nobody has set. Both labels stay editable after the status is
locked, for the reason the award number always was: CHED issues them *after* the
decision, so locking them away would strand a typo the office cannot otherwise
fix. A batch is stripped of surrounding whitespace, because ' 1' and '1' printing
as two batches on the Official List is not noticed until CHEDRO asks.

## Every programme can be given an application period

The office sets when a programme accepts applications, on the programme's own
form. Stored as an opening date and a length rather than a start and an end,
because that is how a window is announced — "open from the 3rd, for two weeks" —
and a length cannot be typed the wrong way round. The closing date is derived,
and both ends are inclusive: one day open means the opening day only.

**Blank means always open**, which is deliberately not the same as a window of
zero days. Every programme predates this field, and a default that closed them
all would have shut the portal the moment the migration ran.

The three apply flows all honour it. Academic and TES reach it through
`scholarship_block_reason`, which checks the window *first*: a programme that is
not open yet is shut to everybody, and telling a student they are ineligible
when the truth is that nobody can apply until Monday sends them to the office
with the wrong question. The staff form holds no `StudentProfile` and never went
through that function, so it asks the window directly.

A student outside the window is told the date, not just refused, and the two
closures say different things — one is a date to wait for, the other a date that
passed. Posting anyway is refused too; the template's absence of a form is
advisory.

A length with no opening date is refused rather than guessed at: "open for 14
days" from when is a question only the office can answer.

Migrations `0070`–`0071`.

## External partners get accounts of their own

An outside funder — DOST, GSIS, a foundation — can now have an account here.
UniFAST has a portal because BiPSU administers TES and TDP *for* it; a partner
has the same standing and a different job, so it gets a different portal: it
reads the archive of its own scholars and takes a list away. It reviews nothing
and edits nothing.

**This is the first stage of a larger request.** The custom application-form
builder the office also asked for is not here; the account model is proven
first.

### What a partner sees is data, not code

`PartnerOffice` records it, one partner at a time. There is no second hard-coded
portal and no rule that a partner sees "its own type", because neither survives
contact with the facts: a partner may fund two programmes, or share one with
another body. The SDSO ticks the programmes on `/vpsea/partners/`.

**A partner with nothing ticked sees an empty portal, never everyone's.** The
failure worth guarding against is one funder reading another funder's scholars,
so the default is nothing, and every partner page filters through
`visible_types()` rather than deciding for itself. A partner asking for a
programme it does not hold lands on one it does; the report download refuses
outright.

Creating a partner makes the office **and** the account that signs in as it, in
one step — an office nobody can log into is not something the office ever wants,
and doing it in two leaves a window where one exists with no way in. The
password is set by the SDSO and told to the partner directly; nothing emails it.

Suspending a partner keeps the account and shuts the portal. Deleting the office
uses `SET_NULL`, so the people who signed in as it survive, unable to reach the
portal, and the SDSO decides what to do with them.

### The portal itself

Three pages — Dashboard, Scholars, Reports — and that is deliberate. The
Scholars table is the partner's own rather than the office's shared partial,
because that partial ends every row with Edit and Delete and this account
administers nothing. The columns still come from the programme's own archive
settings, so what a partner reads matches what the office sees, and the workbook
downloads in those same columns.

`may_add_scholarships` is recorded and off by default, and nothing acts on it
yet: a programme a partner adds would appear in the SDSO's archives and reports
too, so it is the SDSO lending out part of its own catalogue and wants its own
screen rather than a checkbox that quietly works.

Migration `0072`.

## The archive-column picker shows the table, and partners get their own copy

Three things asked for together, all about the same table.

### The selection no longer runs off the page

`.partner-access__option` is a flex row, and its label `<span>` inherited the
default `min-width: auto` — so a long programme name refused to shrink and
pushed the option, its card and the whole page sideways. The text wraps now.
A flex item that will not shrink is the usual cause of a page that scrolls
horizontally for no visible reason.

### A partner can be managed, not just created

Rename, reset an account's password, and delete. Deleting takes the accounts
with it: a login whose office is gone reaches nothing, and leaving it behind is
an account that exists and does nothing. **The scholars are untouched** — they
belong to the programme, not to the funder reading them. The model keeps
`SET_NULL` as the safety net for every other path.

An absent `name` on the access form means "not renaming" and the current name
stands; present-but-blank is somebody clearing the box, which is a mistake worth
naming rather than a rename to nothing.

### The picker shows the table's own order, numbered

It listed the catalogue alphabetically with no indication of position, which
could not answer "what does this table look like" — the question an officer
opening the form is actually asking. Now the columns in use come first, in their
own order and numbered, with the rest below; arrows move one, and the numbers
recompute as you go.

**`clean_choice` keeps the order it is given.** It used to re-sort into catalogue
order on the stated grounds that the office was choosing *which* columns appear
rather than rearranging them. That was a smaller claim than the office wanted,
and two tests asserting the old sort were inverted rather than worked around.

An unconfigured programme now opens with its **default table already ticked**,
because those defaults are what the archive prints today — sixteen empty boxes
misrepresented the table being edited.

### A partner's layout cannot reach the office's

`PartnerTableColumns` holds one partner's choice for one programme. Writing a
partner's edit onto `Scholarship` would rearrange the SDSO's archive from
outside the university, which is exactly the failure to prevent — so
`/partner/columns/` has no path to a `Scholarship` row at all, rather than
being trusted to remember not to take one.

No row means "follow the office", which is why a reset **deletes** the row
instead of storing an empty list: an empty list would mean "show nothing", and
those are different answers. The partner's workbook reads the same override, so
a download matches the page it came from.

Migration `0073`.

## Partners can design the form students fill in

The second stage of the partner work, and the one thing in that portal that is
not read-only. A funder that wants its own questions asked can ask them, without
the SDSO writing a page per funder.

### A form collects answers. It does not award anything.

The line the whole feature rests on. A submission records what a student wrote
and nothing else; the award is still recorded by the office that administers the
programme, on the archive, exactly as before. So a form filling up cannot
quietly enrol anybody, and a test asserts no `Application` row appears.

### Two switches, because they answer to two people

A form is live only when the partner has opened it **and** the programme is
inside the application window the SDSO set. The partner decides whether its form
is finished; the office decides whether the programme is accepting applications
at all. Neither should be able to override the other by accident, and the pages
say which one is shut rather than a single unhelpful "closed".

### Answers are a snapshot

Each stored answer carries the question's label as it read when the student
answered, beside their value and the field's key. Keying answers to field ids
alone would mean a partner renaming a question silently rewrote every answer
already given, and deleting one would leave values nobody could label. The key
is what lines a row up with its column, so a question **added** later exports
blank for earlier applicants rather than shifting their answers left — the
failure a positional export invites.

### What a partner may ask

Short text, paragraph, dropdown, number, date, Yes/No. Every kind renders as one
plain control, validates on the server without a library, and exports as one
column. **A file upload is the deliberate omission** — it needs storage, a size
limit, a virus story and a way to read it back, none of which a text box needs.

The questions are typed by an outside partner and the answers by a student, so
neither is trusted: a number is normalised through `Decimal` so `007` and `7.0`
are one answer, a date must parse, and a dropdown refuses anything off its own
list — otherwise the options would be decorative. An error names the question,
because "this field is required" on a form somebody else wrote says nothing
about which one.

A question is always **appended**. Inserting one mid-form would move every
question after it for anybody part-way through applying.

One submission per student per form per term: a student correcting an answer
replaces their own rather than filing a second, because the partner reading the
list wants one row per applicant.

Migration `0074`.

## Removed: the UniFAST portal and the TES application. The recommender moved.

BiPSU no longer administers TES in this system, so the office that did has no
job here. The whole portal is gone — dashboard, archives, analytics,
announcements, reports, TES applications, the CHED billing claim and the
liquidation that answered for it — along with the `unifast` role, the student's
**Apply: TES** page, and the five tables behind all of it (`TESApplication`,
`TESBilling`, `TESLiquidation`, `TESDisbursement`, `TESCheckIssued`).

**Migration `0075` drops those tables and the rows in them. It cannot be
undone.** Reversing it restores the schema, never the data.

The one thing that did not go with the portal is the recommender. See
*The TES recommender is the SDSO's now*, below.

### The scholarship programmes stay

This is the line the removal was cut along. TES, TDP, SUC-TDP and FHE are still
in the catalogue and still on the landing page with their descriptions,
benefits and agency seals: the university offers them, so saying so is still
true. What went is the machinery for applying, reviewing and paying — not the
statement that the programme exists.

TES is therefore a catalogue entry with no Apply button, the way FHE has always
been. It is also not in `SCHOLARSHIP_TYPE_CHOICES`, so a student cannot declare
it at registration either: nothing here awards or verifies TES, and a
declaration the office has no record to check against is not worth collecting.
Any TES award already recorded is an ordinary `Application` row, and the
masterlist, the archives and the reports go on reading it.

### What the SDSO inherits

One office portal is left, so a few things that existed only to keep two offices
apart are gone with the second one:

* `VPSEA_EXCLUDED_TYPES` — the SDSO reviews every programme now.
* The split archive lists. `SDSO_TYPES` is one list covering every programme,
  and the archive still adds anything in the catalogue that is not named there.
* `data-portal='unifast'` and its orange palette in `srms.css`. Every portal
  wears the university's blue and yellow; the attribute stays because it is what
  lets one of them differ without a template knowing.
* The per-portal column defaults, which are keyed `'partner'` rather than
  `'unifast'` now. That default outlived the office it was written for: a funder
  reports its scholars against the award number it issued, and the SDSO archive
  lists the same scholars without one.

### Two scholarship rules changed with it

* **`can_hold_alongside`.** TES and an Academic scholarship were the one pair a
  student could hold together — a UniFAST subsidy beside BiPSU's own recognition
  of a grade. With TES no longer awarded here, every programme is exclusive, and
  the check is simply whether the student holds anything yet.
* **`is_tes_beneficiary` stays.** It is a self-declaration that Affirmative
  Action disqualifies on, not an award this system records, so it is still asked
  at registration and still read by the Affirmative rules.

### The Disability Type dropdown survives the report it came from

Disability is kept on `PersonalInformation` and outlived the form it arrived
with. Its values are still CHED's own, read from the `Disability_List` sheet of
the bundled Annex 1 workbook — `api/annex1_report.py` is now
`api/disability_list.py`, holding that lookup and nothing else, so the module
name says what it does.


## The TES recommender is the SDSO's now

The rules in `api/tes_ranking.py` are the one part of the UniFAST portal worth
keeping, so they stayed and changed hands. **TES Recommendation** is a second
tab on **Student Ranking**, beside Affirmative Action, and both tabs answer the
same shape of question: which students the rules put forward, and why.

### It recommends. It does not award.

The line the move rests on. UniFAST awards TES, outside this system entirely, so
nothing here writes a status onto a student — the page produces a list the SDSO
can send onward and an explanation for every row of it. Opening **Why?** on a
row gives the rule-by-rule verdict and names the field each one was read from,
which is what makes the ranking defensible rather than merely produced.

### It ranks students, because nobody applies

The old version screened pending TES applications. There is no such form now, so
the population is every student on file. Two lists come out of that: the ranked
one, and *On file, but not yet rankable* — students whose record cannot answer a
rule, held out with what is missing named beside them rather than given a
position their record cannot support.

Missing data has always meant **For Verification**, never **Not Eligible**, and
that is still the rule the module exists to enforce. A student whose citizenship
was never recorded has not failed the citizenship test; nobody has run it.

### Where the answers come from

`TESEligibility` is therefore **not** dropped, and registration and My Profile go
on asking for it — citizenship, Listahanan, 4Ps, previous degree, year first
enrolled. A rule that could only be answered by a form nobody can fill in would
report For Verification forever.

One field moved rather than died. `is_solo_parent_dependent` was on the TES
application form and is a Priority 1 marker the rules read, so it is a column on
the student's own record now. It is three-state there where the form's version
defaulted to `False`: a group nobody asked about is not a group the student was
found not to be in, and a False default would have quietly answered it for every
student in the university. Migration `0075` copies across the answers already
given on a TES application before that table goes.

The three-state selects on both forms are what that care looks like from the
student's side: *Yes*, *No*, and *Not answered yet* — and the page says outright
that leaving one unanswered never counts against them, but guessing does.

## Changed: a declaration has to land in the ledger its programme keeps

Two changes to "I already hold a scholarship" on the registration form, and one
reason behind both.

A student's award is an `Application`, which hangs off a `StudentProfile`. The
BiPSU Staff Scholarship's award is an `AffirmativeStaffApplication`, which does
not. So a student declaring **Staff** left the office holding a claim it could
approve into the wrong ledger, or not at all.

### The student list is narrower

`DECLARABLE_SCHOLARSHIP_TYPES` is what the student dropdown offers now — every
type except `Staff` and `Affirmative`. `SCHOLARSHIP_TYPE_CHOICES` is untouched:
that is still every award this system records, whoever holds it, and the
archives, the catalogue and `Scholarship.type` all go on reading it.

`Affirmative` is out for the same structural reason plus one of its own —
nobody applies for it, so nobody can hold one this system has not itself
decided.

The server refuses what the dropdown no longer offers. A posted `Staff` is
turned down in the same words as an unrecognised value, because the list is not
the control.

### The staff half of the form asks it instead

A staff registration now carries its own Scholarship Data card: **I already hold
the BiPSU Staff Scholarship**, a proof document, and a note. A checkbox rather
than a dropdown, because one programme is on offer there and a select with a
single option is a question that answers itself.

There is no award number, either, and that is not an oversight: BiPSU runs the
programme, so no funding agency issued one, and the Staff archive has no column
for it.

### Approving the account records the award

Decided with the account on the Account Verification queue, exactly as a
student's declaration is — the office is checking one registration, and the
proof arrived with it. Approving writes an **Approved
`AffirmativeStaffApplication`** for the active term, so the scholar flows into
the Staff archive, the masterlist and the reports like every other Staff
scholar. Rejecting turns the declaration down in the same words and writes no
award.

The applicant's own details are copied off the `StaffProfile` the registration
just built rather than asked for a second time — same facts, and a form that
asked twice would be two records that could disagree.

Two consequences worth knowing:

* **They are not asked to apply again.** `nsu_staff_apply` already blocks anyone
  with an Approved or Pending Staff application, matched on email, so the award
  this writes closes that form for them.
* **Re-approving does not double-count.** The term's row is reused, the same way
  `approve_declared_scholarship` reuses a student's.

`StaffScholarshipDeclaration` is the record that holds it while it waits — the
staff counterpart of `ScholarshipLinkRequest`, with no `scholarship_type` column
because there is only ever one. Migration `0076`.

## Fixed: no email was leaving Render, and nothing said so

Registrations were being told to check their inbox for a confirmation link that
never arrived. Nothing was misconfigured.

**Render blocks outbound SMTP on free web services** — ports 25, 465 and 587,
since September 2025. The Gmail settings in the dashboard were correct and
complete; the connection simply never left the container. Every send waited out
`EMAIL_TIMEOUT` and was then swallowed by `notify.send_email`, which catches
everything on purpose so that a mail server cannot take the office's review
screen down with it. The two behaviours are individually right and together they
produced a site that looked like it was emailing people and was not.

### It goes out over HTTPS now

`api/email_backends.py` holds a Django email backend that posts to **Brevo**'s
transactional API on port 443, which nothing blocks. A backend rather than a
call bolted onto `notify`, because every sender in this system already goes
through `django.core.mail` — so not one caller changed, and the test suite's
locmem backend keeps working for the same reason.

Brevo was chosen on one criterion: it verifies a single sender **address** by
emailing it a link, where Resend and most others verify a whole **domain** by
DNS record. Nobody here can add records to `bipsu.edu.ph`. Its free tier is 300
messages a day, against a load of one confirmation per registration and one
notice per decision.

Stdlib `urllib`, not `requests`. It is one POST of a small JSON body, and the
free plan's 512 MB is already spoken for.

### Both routes stay, and the deployment picks

`BREVO_API_KEY` set → Brevo. Else `EMAIL_HOST` set → SMTP. Else the console
backend, as before. Brevo wins when both are set: it is the one that works where
this is deployed, and a half-configured SMTP left over from before should not
quietly outrank the route someone deliberately turned on.

SMTP is not deprecated — it is right on a laptop, on any paid instance, and
wherever the university runs this with its own mail server.

`EMAIL_HOST_USER` is now read outside that branch, because both routes need it:
on SMTP it is the login, on Brevo it is the verified sender, and
`DEFAULT_FROM_EMAIL` is derived from it either way.

### A refusal is never reported as a send

The property the backend is built around, because getting it wrong reproduces
the original bug over a different transport. Brevo answers 201; anything else
raises `BrevoSendError` carrying **the response body**, which is the actual
diagnosis — "sender not valid" and "key not found" are both a 4xx otherwise, and
they are fixed in completely different places.

### Telling the two apart from outside

`manage.py check_email` now reports whichever route is live and names Brevo's
own refusals alongside the SMTP ones. Its instruction to run it from the Render
shell was wrong — the free plan has no shell — so it now says to run it against
the same credentials from a laptop, which tests the key and the sender
verification, the two things that actually go wrong.

`api/checks.py` keys on `EMAIL_ENABLED` rather than `EMAIL_HOST`, so it stops
warning when either route is configured, and its hint explains why Render cannot
use the SMTP one.

### One test was lying

`test_with_no_mail_configured_it_is_still_a_valid_address` failed on any machine
with a `.env`. Its helper deleted the mail variables before reloading settings —
but reloading settings re-runs `load_dotenv`, which fills in any key *missing*
from the environment and leaves alone one already there. Deleting them handed
the developer's own `.env` straight back, so "nothing configured" quietly meant
"whatever is in .env". Setting them to `''` instead makes it hermetic.

## Added: a mail panel, because the deployment has no shell

Diagnosing why no email was arriving took several rounds of reading the Render
dashboard, and the one tool built for it — `manage.py check_email` — needs a
shell that Render's free plan does not have. Meanwhile the sends that fail are
exactly the ones nobody is watching: a confirmation link goes out while a
student is registering, and `notify.send_email` swallows the failure on purpose,
so that a mail server cannot take a review screen down with it.

**Account Verification** now carries an *Email* panel. It says which route is
live, what it sends as, what became of the last message, and it will send a test
and report what actually happened. That is `check_email`, on a page.

It sits there rather than on a page of its own because that is where the office
already asks whether somebody was told — the "they have been emailed" line is a
few inches above it. It is collapsed when mail is working and open when it is
not: a panel that is always open becomes furniture, and this one has to be
noticed on the day it matters.

### Secrets are reported, never printed

`BREVO_API_KEY` and `EMAIL_HOST_PASSWORD` show as *Set* or *Not set*. The sender
address is shown in full, because it is not a secret and it is the thing that is
usually wrong — Brevo refuses any address but the one verified in its dashboard,
and that refusal was previously the only place that ever said so.

### The last attempt is recorded

Four columns on `SystemSettings`, which is a row that already exists:
`last_mail_attempt_at`, `last_mail_to`, `last_mail_subject`, `last_mail_error`.
A blank error against a timestamp means the message left.

`notify.send_email` writes them on both paths, and the write is itself
best-effort — it runs on the failure path of a function that must not raise, so
a database that is down while mail is also down must not turn a logged warning
into a 500. The service log stays the durable record; this is the copy somebody
can read without one.

What is stored is `str(exception)`, not its class, because the useful half of a
`BrevoSendError` is the provider's own wording and of an SMTP error the server's.
"Sender not valid" and "key not found" are both a 4xx otherwise, and they are
fixed in completely different places.

Migration `0077`.

## Registration asks for the whole record, and takes no less

The form collected the whole student record and refused a registration over
almost none of it: first and last name, email, the two passwords, and the
student number. Everything else could be skipped, and was — so the SDSO
verified accounts against an enrolment list using a name and a number, and the
TES recommender ranked students whose household size, Listahanan status and
first year of enrolment nobody had ever supplied. The office collected the rest
afterwards, by hand, one student at a time, which is the work this form exists
to save.

Every question on it is answered now, in the browser and again on the server.
`required` on the input is a convenience for somebody filling the form in;
`_unanswered` in `api/student_views.py` is the rule, and it is what a curl post
meets.

**Seven questions stay optional**, and they are the ones a truthful person can
have no answer to:

| | |
|---|---|
| Indigenous Group | asked of everybody, answered by few |
| Suffix | most people have none |
| SHS GPA and SUC Exam certificates | the form says they can be uploaded later under My Profile, and a student without a scanner is still a student |
| Award / Scholar Number | "if your award letter has one" — not every letter does |
| the two Additional Notes boxes | "anything the office should know" is by definition something there may be nothing of |

Making one of those mandatory does not collect an answer. It collects `N/A`,
which is worse than a blank because it looks like one.

### Three questions that `required` alone could not have caught

A `<select>` whose first option carries a value is not a question — the browser
sees something chosen and lets the form go. Three of these were rendering as
answers nobody had given:

* **Year Level** opened on *1st Year* and posted it for anybody who never
  looked at it.
* The four TES three-state questions — Listahanan, 4Ps, solo parent, previous
  degree — opened on *Not answered yet*, which was a value of its own.
* **Disability Type** and **Citizenship** opened on *Not answered yet* as well.

All of them now open on an empty *— Select —*, and the server refuses anything
but Yes or No on the four three-states. `_tristate` is untouched: everywhere
other than registration — My Profile, the office forms, a scholar imported from
a spreadsheet — an unanswered question still reads as unanswered, because those
records may predate anybody asking. Registration is the asking.

The TES card used to tell students to leave anything they were unsure of as
*Not answered yet*. It no longer can, so it says where to find the answer
instead.

### One registration payload for the tests

`api/test_registration_payload.py` holds it — `a_student()`, `a_staff_member()`
and `a_declared_scholar()`, the last being what arrives when the eligibility
cards are closed and their fields disabled. Seven test modules posted their own
thirty-line dict before, and thirty-line dicts copied seven times drift: one
keeps passing about a form nobody has.

`api/test_register_optional_labels.py` still checks both directions of the
marker — nothing unmarked is optional, nothing marked is required — against the
rendered page rather than against a list.

## Reports says which school year the masterlist is for

The masterlist was built for the active term and nothing else. Producing last
semester's list — the one an auditor asks for — meant changing the active term
in Settings, generating the document, and changing it back, with every other
screen in the office following along while somebody remembered to.

The Reports tab carries a **School year** picker now. It offers every term the
office has imported scholars into, plus the active one, and it travels on `?sy=`
from the page into the preview frame and all three downloads — so the document
that opens is the document that was on screen. `sy` rather than a name of its
own because that is what Archives already calls it.

The heading, the file name and the rows all follow it: *LIST OF SCHOLARS FOR 1st
Semester SY: 2025-2026*, `BiPSU_List_of_Scholars_25_1.docx`.

### What the term does and does not scope

**Imported scholars are scoped by it.** They carry a term because they arrived
in one spreadsheet for one semester.

**Awards are not, and must not be.** An `Application` carries the term it was
*granted* in and is renewed term by term against that same row, so which
semesters it has been current in is written down nowhere to filter on. Scoping
applications by their own `term_label` would drop every scholar awarded before
this semester out of the list — the picker would appear to work and quietly
empty the document.

### A term other than the active one says so

A masterlist downloaded from the wrong year is not obviously wrong once it is a
file on somebody's desk, so choosing a past term puts an amber banner above the
preview naming both terms. That banner is `.page-alert-warn`, the third of a set
that had only `-error` and `-ok`.

### The spreadsheet's heading was reading the raw label

`Download XLSX` stamped *SY: 26-1* while the Word document stamped *SY:
2026-2027* — one term, spelled two ways, on two files of the same list. It goes
through `parse_label` now like everything else.

**Still outstanding, and older than this change:** the XLSX export builds its own
queries rather than going through `masterlist_report`, and never includes
imported scholars at all. Its rows are portal applications only. The term picker
cannot fix that; the export needs to be moved onto `build_context` like the DOCX
and the PDF preview already are.

## An external scholarship is not applied for in this system

TDP, TES, GSIS, FHE and SUC-TDP are decided by UniFAST, CHED or GSIS. The
student applies to the agency, the agency grants the award, and the office
receives the awarded list afterwards — which arrives here as a spreadsheet
import, not as a submission. The Academic Scholarship is the only programme this
system takes an application for; BiPSU Staff and Affirmative have their own form
in the staff portal.

Every page in the student portal already worked that way. Two things behind them
did not.

**The recommendation card offered to start one.** `student/recommendations.html`
showed **Start Application** for any programme marked
`category='application'` — which is five external ones — and pointed all of them
at `/student/apply/tdp/`, a path with no route and no view. The button 404'd for
every programme but Academic. The card now offers an application for Academic
alone; an external programme reads *Applied for externally* and carries the
locked button that recommendation-only programmes already had.

`templates/student/apply_tdp.html`, the form that path would have rendered, is
deleted. Nothing referenced it and nothing ever routed to it.

**The JSON endpoint accepted one.** `POST /api/student/applications/` took any
programme in the catalogue. No page in the portal posts to it, but an
`Application` created there is indistinguishable from a real award — it counts
on the dashboard, prints on the masterlist and files in the archives. So the
rule lives on `ApplicationSerializer.validate_scholarship` rather than in a
template: an externally funded programme is refused with the reason, and
Academic is unaffected.

What is **not** refused is an award the office already holds. Imported scholars
and approved link requests write Application rows on external programmes and
must keep doing so — that is the whole reason those programmes are in the
catalogue. The rule stops a submission, not a record.

See `api/test_external_not_applied_for.py`.

## Removed: the partner application form

An external partner's portal is a window onto the archive of its own scholars.
It is not a second place to apply, and the SDSO decided it never should have
been: a funder that wants its own questions asked asks them on its own site, and
the office records the award here once the agency grants it — which is what
every other externally funded programme already does.

So the whole feature goes. **Deliberate.** Deleted with it:

- `api/partner_forms.py` and `api/test_partner_form_builder.py`
- `templates/partner/form_builder.html`, `templates/partner/submissions.html`,
  `templates/student/apply_partner.html`
- `static/js/partner-form-builder.js` and the `.pf-*` block in `srms.css`
- the **Application form** and **Applications** links in `templates/partner/_nav.html`
- `partner_form_builder`, `partner_submissions`, `partner_submissions_download`,
  `student_apply_partner` and `_partner_form` in `api/student_views.py`
- their four routes in `api/urls.py`
- `PARTNER_FIELD_KINDS` and `PARTNER_FIELD_KINDS_WITH_CHOICES` in `api/constants.py`
- the models `PartnerApplicationForm`, `PartnerFormField` and
  `PartnerFormSubmission` — migration `0078`, which **drops data**

What stays is the reading half: `PartnerOffice` (who a partner is and which
programmes it may see) and `PartnerTableColumns` (how it lays its own table
out). Nothing removed here ever created an award — a submission was answers and
nothing more — so no `Application`, `ImportedScholar` or archive row depended on
it.

`api/test_partner_offices.py` now checks that the four routes 404 and that the
sidebar offers neither, because a nav link to a route that 404s is worse than no
link.

## A registration may declare more than one scholarship

Some students hold two — CHED and a private foundation, DOST and a local
government grant — and the form asked once. The second award reached the office
as an email, a phone call, or not at all.

The form asks up to three times now. `DECLARATION_SLOTS` in
`api/student_views.py` is the list of them, and everything else is read off it:
the cards `_declaration_slots` draws, the fields `_declared_scholarships` reads,
and the names `api/test_register_optional_labels.py` expects. The first card
keeps the bare field names it has always had — `has_scholarship`,
`scholarship_type` — because every test, cached page and office script names
them; only the cards after it are numbered.

**Each declaration is its own `ScholarshipLinkRequest`.** Two awards are two
things to check, against two sets of records, with two proof documents, so the
account verification queue draws a card each and every control on it names the
request it belongs to: `award_tier_<pk>`, `archive_id_<pk>`. A single
`archive_id` would have offered a student's DOST row as the answer to their CHED
award.

**The same programme twice is refused.** Nobody holds CHED twice; that is one
award typed into two cards. The unique constraint on `Application` would catch
it — at the point where the officer had already approved it.

**The SDSO is told.** `notify.office` is the first thing in `api/notify.py` that
writes *to* the office rather than to an applicant, and it exists because the
office's only standing signal is a badge counting accounts, which says nothing
about what is inside any of them. It emails every active VPSEA account and
writes an `ActivityLog` line, because delivery is best-effort here as everywhere
and a warning nobody can find afterwards was never given.
`notify.multiple_declarations` is the wording, raised only at two or more — a
warning sent for every registration is a warning nobody reads.

**A numbered card is rendered `disabled` by the server, not only `hidden`.** A
hidden input still posts, so a closed card would have declared a scholarship
nobody named and refused the registration over it — for every visitor whose
browser never ran the script. The first card has no such input at all: the
checkbox above is its flag, and a second input under the same name would have
declared one for everybody.

See `api/test_second_scholarship.py`.

## The two windows moved to the queues they govern

Whether a programme takes applications was a pair of boxes on its own form under
Scholarship Programs — three clicks from the queue, on the page an officer opens
least and never while reviewing. Renewals had no window at all: nothing could
close them.

Both are now cards above the table they govern. **Application Period** sits on
the Applications tab and sets the window for that tab's programme — Academic on
one tab, BiPSU Staff on the other. **Renewal Period** sits on the Renewal
Applications tab and sets the Academic programme's, which is the only renewal
this system takes.

Each is a switch and a window, read in that order:

| switch | dates | result |
| --- | --- | --- |
| off | anything | closed, and the message offers no date it cannot stand behind |
| on | none | always open — how every programme behaved before this |
| on | set | open inside them, both ends inclusive |

The switch is the state a window could not express. "Not yet" and "no longer"
are dates; "not this semester" is not, and the office used to say it by
inventing a window that had already passed.

Migration `0079` adds `accepting_applications`, `accepting_renewals`,
`renewals_open_on` and `renewals_open_days`. Both switches default to True for
the same reason the dates default to blank: every programme that existed before
them was open.

`Scholarship._window_end`, `_window_open` and `_window_reason` carry the
arithmetic once, and the two pairs of methods on either side of them only say
which columns to read. Two copies is how two windows start disagreeing about
what "1 day open" means.

**`vpsea_scholarship_edit` no longer writes either window**, and the boxes are
gone from `vpsea/scholarship_form.html`. That is the failure the move invites: a
form that stopped asking but kept saving would have closed every programme the
first time somebody corrected a typo in its name. `api/test_application_window.py`
checks it.

`_posted_window` now returns a real `date` rather than the string it was typed
as. Assigning a string to a `DateField` works — Django coerces it on save — but
the card reports its own closing date straight after saving, and a string cannot
be added to a `timedelta`.

## A staff member's School may be an office that teaches nobody

The staff registration form and My Profile both offered `BIPSU_SCHOOLS`, which
is the list a **student** enrols in. Non-teaching personnel are not in any of
them: they are assigned to the four vice-presidential clusters, the two offices
under Academic Affairs, or the library. Nor were the graduate and professional
schools, the Biliran campus's own teacher-education unit, or NSTP.

The staff side reads `BIPSU_STAFF_UNITS` now — `BIPSU_SCHOOLS` plus
`BIPSU_TEACHING_UNITS` plus `BIPSU_OFFICES` — drawn as two `<optgroup>`s,
Academic units and Administrative offices. `StaffProfile.school` validates
against it (migration `0080`, choices only, nothing in the database moves), and
the field is labelled **School / Office** on both pages and in the error it
raises.

**`BIPSU_SCHOOLS` is deliberately untouched.** Every entry on it has courses
under it in `BIPSU_COURSES`, and the Course dropdown on the student half of the
registration form is built from them and is `required` — so a school with no
courses is one a student can pick and then be unable to finish the form. That is
what merging the two lists, the obvious tidy-up, would do. Graduate Studies, Law
and Governance and Agri-Industries stay off the student list until somebody
supplies their programmes.

See `api/test_staff_school_units.py`.

## A partner keeps its own scholar list, and the layout picker becomes a dialog

Two changes to the same page, `partner/archives.html`.

### The column picker moved into a dialog

**Columns — lay this table out your own way** was a `<details>` card sitting
between the tabs and the table, pushing the scholars down the page for a setting
nobody opens twice a year. It is a **Table layout** button now, off the same row
as the download, opening a `.modal-overlay` through `static/js/modal-open.js`.
The form is unchanged and still posts to `/partner/columns/`.

### A partner may add, correct and remove its own scholars

The portal was read-only, and for the awards it shows it still is. What changed
is the other half of the table: the rows that reached this system as a
spreadsheet, which is how every programme without a portal arrives. Those are
the funder's own list, and a funder correcting a misspelt name had to email the
SDSO and wait.

`partner_scholars` in `api/student_views.py` is the one endpoint for add, edit
and delete — they share every check that matters, and three views would have
been three places to forget one. Three rules decide what a partner may touch:

1. **Its own programmes only** — `office.visible_types()`, the same list every
   other partner page filters on.
2. **Imported rows only.** An award row is a BiPSU student's own record: they
   typed it, the office verified it, and they read it in their own portal.
3. **Unclaimed rows only.** A claimed row was merged into a student's award once
   the office checked the two were the same person.

**None of the three is enforced by remembering to check.** The row is *found* by
a query carrying all of them (`filter(pk=…, scholarship_type=stype,
claimed_by__isnull=True).first()`), so a pk from another programme's list simply
is not there — a permission check written as a lookup cannot be skipped by a
later branch. The refusal names none of the three misses: which one it was is
not the account's business to learn by trying.

`scholarship_type` and `term_label` are **not** editable. Moving a scholar into
another programme's list is the one edit that reaches outside a partner's own
scope, so the form does not ask and the view does not read it. Award rows show
*BiPSU account* in the actions cell rather than a button that would be refused.

Every action writes an `ActivityLog` line naming the office. The SDSO lent out
part of its own archive; it should be able to see what was done with it without
asking. A row a partner adds carries `imported_from = 'Added by <office>'`, the
same column an uploaded sheet fills with its filename.

See `api/test_partner_scholars.py`.

## Every template carried a byte order mark, and every page was in quirks mode

The symptom was a **gap at the top of every signed-in page**, and a page that
kept scrolling a little past the end of its own content. It was in all three
portals, for every role, which is what pointed at `base.html` rather than at any
one screen.

Fifty-two templates began with a UTF-8 BOM — invisible in an editor, added by
Windows editors on save without saying so. A BOM is not whitespace to an HTML
parser, so a document that begins with one begins with **content**:

* `<!DOCTYPE html>` is no longer the first thing read, so it is ignored and the
  page renders in **quirks mode**.
* The parser closes `<head>` before it has opened it, and every `<meta>`,
  `<title>`, `<link>` and `<script>` is inserted into the `<body>` instead.
* The mark itself lays out as an ordinary character and reserves a line box —
  **24 pixels** of empty band above the page, scrolling with it.

Every template is now saved without one. `api/test_template_encoding.py` checks
the bytes of every template file, because that is the only place the mark can be
seen at all, and also checks the login page's response actually starts with its
doctype. Partials are checked too: `{% include %}` splices the mark into the
middle of a document, where it is a stray zero-width character inside a nav or a
table rather than a parse error, and just as invisible.

**If a template ever renders wrong for no visible reason, check this first.**

## The landing cards are justified, and their prose is sentence-cased

Two requests about the same text.

`.card-desc` is `text-align: justify` with `hyphens: auto` — the hyphenation is
not decoration: the three-column grid puts this text in a 17rem column, and
justifying a column that narrow without it opens rivers of white space between
the words.

The capitalisation is a filter, `sentence_case` in
`api/templatetags/srms_text.py`, applied to descriptions, backgrounds,
eligibility lines and benefits. **Deliberately not `|capitalize` or `|title`**:
both rewrite the rest of the line, and this catalogue is full of things already
spelled the way they are meant to be — CHED, DOST, TES, BiPSU, UniFAST, RA 7687.
Only a lowercase letter in a sentence-opening position is touched. Nothing edits
what the office typed; the data is untouched and the filter runs on the way out.

An abbreviation mid-sentence ("e.g. this one") will capitalise after the full
stop. That is the cost of not keeping a dictionary of abbreviations, and it is
the smaller of the two errors.

See `api/test_landing_page.py`.

## The landing navbar links to the two lists

**Internal Scholarships** and **External Scholarships**, each with the dot its
card strip wears, each taking the reader down to the list it names.

They were briefly a marquee of every programme name scrolling past the brand.
That was a misreading of the request — what was asked for was two labels that
scroll the page when clicked, not text that scrolls by itself — and it was the
worse idea anyway: a reader wants to reach a list, not read a moving one.

Plain anchors, so this works with scripting off. Two pieces of CSS make them
land properly, and both are guarded by `api/test_stylesheet.py`:

* `scroll-padding-top: var(--nav-h)` on `.page-landing`, so the heading arrives
  *below* the sticky navbar rather than behind it.
* `scroll-snap-align: start` on each list, so `mandatory` snapping treats the
  target as a resting place instead of dragging the jump back out.

**`scroll-behavior: smooth` was removed from `.page-landing`, and must not come
back while the page uses `scroll-snap-type: mandatory`.** Chrome cancels a
smooth scroll outright inside a mandatory snap container: the snap re-targets
mid-animation and the page never moves at all. The declaration had been sitting
there doing nothing — every smooth scroll it asked for was already being
discarded — and it only became visible when the two links needed to reach the
lists and silently went nowhere. The `prefers-reduced-motion` block that existed
solely to switch it off went with it.

The word "Scholarships" is dropped from both links below 640px, where there is
no room for it twice; the gap in front of it is a CSS margin rather than a
character, so each link carries an `aria-label` and is announced in full either
way.

### The brace that ate the facade

Removing the marquee's CSS left one extra `}` behind, six hundred lines above
`.hero-landing`. A stray brace is not an error anybody sees: the browser treats
it as the end of a block that was never opened, discards rules until it can
recover, and renders the page with a piece of the design simply gone. Here that
piece was the hero's `min-height`, so the campus facade — meant to fill the
first screen exactly — collapsed to a 225-pixel strip.

`api/test_stylesheet.py` now parses `srms.css` for balanced braces and checks
the hero rule by name, because balance alone would not have caught it: the rule
was still in the file, just unreachable.

## A scholar holding two awards renews each of them separately

The renewal page was Academic's alone. It asked Academic's renewal window, wrote
an `AcademicRenewal` carrying nothing that said which programme it was for, and
`vpsea_renewals` approved every one of them into an **Academic** award. For a
student holding two scholarships — two declared at registration and both
approved, which is the ordinary way it happens — that is three failures:

* the second award could not be renewed at all;
* both renewals reached the office as identical rows;
* approving a DOST scholar's renewal silently awarded them Academic.

`AcademicRenewal.scholarship_type` says which (migration `0082`). The rules
around it:

* **A student on one award is never asked.** A question with one possible answer
  is not a question; the view fills it in and the form shows what is being
  renewed.
* **Only programmes whose renewal window is open are offered**, and a shut one
  cannot be posted past the form either.
* **One closed window is not a closed page.** The page is blocked only when
  *every* programme the student holds is shut; the others are listed beside the
  form with the reason.
* **A replacement stays inside its own programme.** The pending-renewal lookup
  is scoped to the programme as well as the term, so re-uploading for the second
  award cannot overwrite the first one's documents.

The office's table gained a **Programme** column, approval creates the award
against the renewal's own programme, and the decision notification names it.

See `api/test_renewal_programmes.py`.

## The SDSO and external partners can change their own password

Neither could. The SDSO could reset a *student's* password from Account
Verification and a *partner's* from External Partners; a partner could change
nothing at all, so the office had to type a new password into a form and read it
back down the phone.

Both roles now have a profile page — `/vpsea/profile/` and `/partner/profile/` —
carrying their name and the shared password card in `templates/_password_card.html`.

The **current password is asked for**. This is not the office resetting somebody
else's; it is an account changing its own, and a session left open on a shared
office machine must not be enough on its own to lock the owner out of it. Empty
fields mean "leave it alone" — the card sits on the same form as the account's
name, and saving a corrected surname must not blank a password. A refused change
saves neither half, so nobody is left guessing which one went through.
`update_session_auth_hash` keeps the person signed in to the tab they did it in.

The email address is shown and not editable in either portal: it is what the
account signs in with. Which programmes a partner may read is shown read-only
too — that is the SDSO's decision, recorded on External Partners, and a partner
should be able to see what it was given without having to ask.

See `api/test_own_password.py`.

## The staff unit is typed, not picked, and reads as Office / College / Unit

**This partly reverses "Staff registration picks its school from the BiPSU
list"** above, and on purpose. That change was right about the problem — free
text matches nothing in a report — and the fix keeps its benefit: the field is
an `<input list=…>` over a `<datalist>` built from `BIPSU_STAFF_UNIT_GROUPS`, so
the canonical names are still offered, still filtered as you type, and still
what almost everybody selects.

What it no longer does is *refuse everything else*. A university reorganises
faster than a hard-coded list can be migrated, and an employee whose unit was
renamed last year had to pick the nearest wrong thing. `StaffEmployment.school`
dropped its `choices` (migration `0081`); the label is **Office / College /
Unit** on both the registration form and My Profile, and the required-field
error names it the same way.

`<datalist>` has no `<optgroup>`, so the two groups arrive flat. Nothing is
lost — the browser filters the list as you type, which is what the grouping was
there to spare a reader from doing by eye.

The label is **Office / College / Unit** in both places an employee sets it:
the **Employment Information** card on the registration form, and the same card
on My Profile. The field above it still reads **School / Employee ID** — that
one is an ID number rather than a place, so it was left alone.

Course / Program on the staff apply page gained the same treatment: suggestions
from `BIPSU_COURSES`, and anything else typed in full, because an
employee-scholar may be enrolled in a graduate programme and that list is the
undergraduate catalogue.

See `api/test_staff_school_units.py`.

## A recommender for the Faculty and Staff Scholars programme

The Ranking page's docstring used to say this programme had no tab because it
has no merit test. It still has no merit test — nothing here is scored — but it
does have **three qualifications**, and until now nobody could see them applied:

> a. All faculty and employees of the University with permanent appointment.
> b. All qualified and legitimate dependents of faculty and staff with permanent
>    appointment.
> c. Staff dependents who have already graduated a baccalaureate degree are
>    disqualified from enjoying the scholarship.

`api/staff_ranking.py` reads them off the application and states a verdict with
its reason, the way `api/tes_ranking.py` does for TES. **Nothing is written to
the database**, so re-running it cannot change a record and the answer cannot go
stale. Three readings it gets right, each of which is a way to get it wrong:

* **(c) is about dependents.** Reading it onto employees would disqualify most
  of the faculty, who hold a degree as a condition of being employed at all.
* **(b) turns on the employee's appointment, not the dependent's.** A dependent
  has no appointment; the one that matters belongs to the parent they claim
  through, and it is looked up by employee ID on `StaffProfile`.
* **Not knowing is not failing.** A dependent whose parent's ID matches no staff
  record is *For Verification*, with the ID named, not *Not Qualified*. Turning
  somebody away over a filing gap is the error that matters here.

'Permanent' and 'Regular' are both accepted — the first is the Board's wording,
the second is what `EMPLOYMENT_STATUSES` stores, and nobody should have to learn
which one the screen wants.

See `api/test_staff_recommender.py`.

### Fixed on the way past

`nsu_staff_apply` created a first-time application with `status=new_status` — a
name from the office's review view that has never existed in that one. A staff
member's **first** application raised `NameError`; only a re-application, which
takes the other branch, ever went through. It is `'Pending Validation'` now, the
same status the update branch sets.

## Affirmative Action ranks on its mandate, not on grades

The PASUC-8 proposal behind this programme has two halves, and only one of them
was in the system. Section 2 says who is **eligible** — SHS GPA of 75%, at least
50% in the SUC-administered admission exam, not already a TES beneficiary — and
`AffirmativeRecommendation.evaluate_and_sync` has always tested exactly those
three, correctly. The mandate paragraph says who the programme is **for**:

> 1. coming from the indigenous groups;
> 2. person with disabilities;
> 3. students from public schools; and
> 4. students from depressed areas

None of that reached the ranking. Two of the four groups were on every student
record already — collected for TES, which reads them as priority markers — and
invisible to this programme; the other two were not collected at all. So the
Student Ranking page ordered the shortlist by a fit score of 50% SHS GPA + 50%
admission exam, and an affirmative action programme handed the Board of Regents
a **merit list** — the one thing §1 of its own proposal says it is not:

> The grades will not be the only factor to qualify. Qualifiers may not
> necessarily be indigent nor excellent academic performers. They may be outside
> the 4Ps of the DSWD.

`api/affirmative_ranking.py` now reads the four groups off the student's record,
and the page, the workbook and the DRF endpoint order the shortlist by them —
most groups first, the fit score demoted to a **tie-break** between students the
mandate reaches equally. The three eligibility rules are untouched.

**The groups order the list. They do not gate it.** A student in none of the four
is still eligible and still ranked; a student in all four who fails a §2 rule is
still turned down. Reading the mandate as a fourth rule would turn a description
of who the programme is for into a bar to clear, which is what §1 forbids.

### Two questions nobody was asking

Public-school origin and depressed area could not be derived from anything on
file, so both are now asked:

* `EducationalBackground.highschool_is_public` — no reading of a school's *name*
  tells you whether it is public.
* `SocioEconomicProfile.is_from_depressed_area` — **the proposal never defines
  "depressed area"**, so nothing tries to. It is declared by the student and
  verified by the office, the way Listahanan and 4Ps already are. Deliberately
  not derived from the address: classifying a barangay would mean holding a list
  this system has no source for, and a stale list would quietly drop students out
  of a mandate.

Both are three-state — Yes / No / not yet asked — and **required at
registration**, of every student rather than only of applicants, because the
whole design turns on the difference between an answered "no" and a question
nobody put. An unanswered one is reported as unanswered on the page ("2
unanswered") and named in the workbook's *Unanswered Group Questions* column, so
the office can go and ask rather than a student silently losing a place.

They are answerable on My Profile **after the school names lock**. Locking them
alongside `highschool` would have shut every student registered before today
permanently out of a group the mandate may well reach them through.

Migration `0084`. See `api/test_affirmative_target_groups.py`.

### Fixed on the way past

* `0032_user_photo.py` was an uncommitted, unapplied migration branching off
  `0031_staff_scholarship_group_internal`, which left the graph with two leaf
  nodes — `makemigrations` and `migrate` both refused to run at all. `User.photo`
  is on the committed model and no other migration adds it, so the file is
  needed: it is `0083_user_photo` now, on the tip.
* The DRF ranking endpoint ran its own query rather than
  `_affirmative_ranking_data`. Survivable only while both sorted on the same
  column; it would have answered "who are the top five?" differently from the
  page the moment the page started sorting on groups. It goes through the same
  function now.

## The office REST endpoints check the role

`settings.REST_FRAMEWORK` sets `IsAuthenticated` as the default permission,
which asks one question: is there an account behind this request. Every
`/api/vpsea/` view inherited that and narrowed nothing, so a **student's own
token reached all eleven** — the applicant list is every applicant's data, and
`/api/vpsea/applications/<pk>/` was a `PATCH` away from approving your own
application. The web portal never had the hole; `student_views._vpsea_required`
checks the role on every page.

`views.IsOfficeStaff` is that same check in DRF's vocabulary, on all eleven.
A Django superuser passes it whatever `role` column it carries, because a
superuser administers this site and may never have been given one.

Do not remove `permission_classes` from these views to "let the frontend read
them". See `api/test_api_permissions.py`, which checks both halves — the
refusals, and that an officer still gets through.

## The API registration door proves its address too

`User.email_verified` defaults to `True` because an account the office creates
itself is not asked to prove an address the office already had. `RegisterSerializer`
inherited that default and sent no confirmation link, so an account made through
`/api/auth/register/` reached the SDSO's queue reading **address confirmed**
beside an address nobody had ever written to — the one fact that column exists
to keep honest.

It sets `email_verified = False` now and `RegisterView` sends the link, exactly
as the web form does. Still no token, and still `pending`: confirming an address
is not the SDSO's decision. See `api/test_email_verification.py`.

### Fixed on the way past

* `_unawarded_rows` used `date.min` with no `date` imported — a `NameError`
  waiting for the first application with no `submitted_at`.
* `vpsea_report_download` carried **391 lines of an older Word builder after its
  `return`**. None of it could run; every name in it was undefined at that point.
* The Excel archive upload endpoint gave a blank year-level cell a value of
  `2024`, in a column that holds 1 to 4.
* `VPSEAReportsView` answered `200` with four invented report filenames and
  sizes — "Scholarship Master List A.Y. 2024-2025", "2.4 MB" — for documents no
  code here has ever produced. It lists the masterlists the office can actually
  build now, one per term on file.
* `vpsea_student_add` and `vpsea_student_edit` defaulted the term to
  `'2025-2026'` / `'1st Semester'` written into the view. They read the active
  term through `_active_term()` now — the same fault the student apply page had
  already fixed.
* `vpsea_student_edit`'s context wrote `v_elementary`, `v_highschool`,
  `v_last_school` and `v_father_name` twice each in one dict literal. Python
  keeps the last, so the first four were dead.
* The `?next=` on the office student form went straight into an `href`. A
  crafted link handed to a signed-in officer put an off-site destination on a
  button inside the office's own page. `_safe_next` validates it against the
  request host.
* `vpsea_archive_import` pasted the raw exception into a query string, so a
  message containing `&` or a newline reached the officer truncated or not at
  all. Percent-encoded.
* `nsu_staff_apply` guarded its whole validation block with `if True:` under a
  comment about a draft this page never had; `nsu_staff_renewal` guarded its
  save with `if not errors:` over a list nothing appended to, leaving the render
  below it unreachable. Both flattened.
* `api/views.py` and `api/student_views.py` both carried a UTF-8 BOM, and
  `views.py` had been round-tripped through cp1252 — 212 rule characters read as
  `â”€`. In `student_views.py` the damage was in *output*: `2Ã—2 ID Photo` on
  three forms and `VICTOR C. CAÃ‘EZO, JR.` in the footer of the Excel report the
  office files.
* `split_ched` and all six gender splits in the Excel report used `x not in list`,
  a scan per row. One pass against a set of primary keys instead — the pattern
  is gone from the codebase.
* `vpsea_scholarship_toggle` read the row back with `.get()` to negate it, so a
  programme deleted in another tab answered with a 500.
* `vpsea_archive_add` and `nsu_staff_apply` still wrote `or '2000-01-01'` for a
  missing birth date. `ApplicantInformation.date_of_birth` has been nullable
  since the record split, and that fallback is the one the model's own docstring
  names as the thing it replaced.

### Removed as dead

Nothing here did anything. `templates/vpsea/archives_backup.html` (762 lines, no
view rendered it); `static/js/select-by-group.js` (no template loaded it — its
only consumer was the TES form, gone); Django's empty `api/tests.py` stub;
`SDSO_TYPES`, `TARGET_GROUPS`, `DECIDED_REVIEW_STATUSES` and
`EDITABLE_REVIEW_STATUSES`; a fifth column in `PROGRAM_SLOTS` nothing unpacked;
a duplicated `@login_required` and a `u.save()` that rewrote every `User` column
unchanged; 33 unused imports and 7 unused locals; and 68 lines of `srms.css`
matching no class in any template or script — **every selector in that file now
matches something.**

The two `<style>` blocks in `register.html` and `registration_received.html`
moved into `srms.css`, and the hand-written cache-buster — which had drifted to
`?v=44` in five templates while `base.html` was on `?v=46` — is `?v=47`
everywhere.

## An unclassified CHED scholar is a Full one

CHED is the one programme reported in two blocks, and splitting the archive into
a tab per tier turned a question nobody had needed to answer into one that shows
on screen: **which block does a scholar carry no tier belong in?**

The two halves of the system had answered it differently. `ImportedScholar` read
a blank `award_tier` as **Full**; `split_ched` read a blank `ched_tier()` as
**Half**. So one unclassified scholar landed on a different tab according to
which table they had arrived in — and an officer who recorded an award number on
the Full tab was redirected back to Full to find the scholar gone.

**Unclassified is Full**, on both sides. Only a row that reads as 'half' is half.
`split_ched` was the side that moved.

The reason it used to be the other way is real and no longer applies: this code
had always put anything not named 'full' in half, which was fine while CHED was
one page with two stacked bands and nobody could add to a particular one. A tab
per tier is a place the office *adds* scholars from, and a row added on the Full
tab has to be on the Full tab.

**This changes the filed masterlist.** An unclassified CHED award now prints in
the CHED FULL MERIT block of the Word document rather than CHED HALF MERIT — the
same rule the archive tabs and the Excel report follow, which is the point:
three reports of one programme cannot disagree about where a scholar is.

Two tests moved with it. `test_ched_still_reports_in_two_tier_blocks` read both
bands off one page and compared their heading rows; it is
`test_both_ched_tiers_report_the_one_programme_the_same_way` now and asserts the
same thing across the two tabs. And `test_archive_tabs.py` gained
`test_an_untiered_award_prints_under_full_like_an_untiered_import` — the award
side of the rule the imported side already had a test for, and the side that was
wrong.

## A BiPSU employee is not a student of this system

Approving a **BiPSU Staff** application on the Affirmative/Staff queue used to
build a Django account with `role='student'`, a `StudentProfile` numbered
`AFF-<id>` where the employee had no student number, and an `Application`
nothing reads.

A Staff scholar's record *is* the `AffirmativeStaffApplication` — the Staff
archive tab, the masterlist's BiPSU STAFF block and the reports all read it
directly. The student record was surplus, and it put a BiPSU employee on **My
Students**, on the **No Scholarship** archive tab, and on the **TES
recommendation the SDSO sends onward to UniFAST**, which is where it was
spotted.

**Affirmative Action still builds one, and should.** That programme's scholars
are students: the four target groups are read off a student's own record and
`AffirmativeRecommendation` hangs off `StudentProfile`. The two programmes share
one branch and only Staff is excluded from it — `api/test_staff_are_not_students.py`
asserts both halves side by side so neither can be changed without the other
being considered.

The TES list had a second fault of its own: it ranked **every** `StudentProfile`
with no filter at all, so a registrant the office had rejected, or had not
decided on yet, was on a list that leaves the building. It covers verified
accounts only now — the same rule the No Scholarship tab and the Students screen
already applied.

### Clearing up what the old branch already made

    python manage.py prune_staff_student_profiles            # show, change nothing
    python manage.py prune_staff_student_profiles --delete    # act

Deployments that ran the old code still carry those records, and Render's free
plan has no shell — so this is written to be safe run against a production
database from a laptop, the way `check_email` is. Nothing is written without
`--delete`.

It removes only a profile whose address owns a Staff application the employee
filed **for themselves** (`is_nsu_staff`) *and* which has never been used as a
student. A **dependent's** claim is reported and never touched: a dependent is a
different person from the employee and may be a genuine BiPSU student.

Deliberately **not** the rule: "the student number starts `AFF-`". Approving an
Affirmative application still mints one, and those scholars are real — an
earlier draft pruned on the prefix alone and would have deleted them. There is a
test named for exactly that.

## An uploaded sheet fills the columns the office added

A custom column could only ever be **typed** — one scholar at a time, in a box
on the archive page. For a programme with a portal that is merely tedious. For
the ones without — DOST, CHED, GSIS, CoScho, TDP, most of the catalogue — it was
worse: those arrive *entirely* as the agency's spreadsheet, so a column the
funder's own file already carried had to be retyped row by row, and the next
import replaced the term's rows and lost every cell of it again.

`_scholars_from_sheet` fills them now. **Matched on the heading, not the
position** — a funder lays its file out as it likes, and the name is the only
thing the two ends share. The slug compared is the one `custom_key()` already
derives, so `Batch`, `BATCH` and `  batch  ` are one column; `Batch No.` is a
different one and stays unmatched rather than being guessed at.

Two things the matching has to refuse, both with a test named for them:

* **A position the import contract already claims is never read as a custom
  column.** A sheet whose `Sex` column happens to sit where a matching heading
  would otherwise be must not have that value read into two fields.
* **A cell of the wrong kind is refused, not stored.** `clean_value` is the same
  rule a typed value goes through, so a column holds one kind of thing however
  it was filled. The count comes back as `columns_bad=` on the redirect —
  a column half filled by an import, with nothing saying so, is the failure this
  feature could most easily have become.

**Excel dates needed translating first.** openpyxl returns a real `datetime` for
a date cell and `clean_value` reads text, so untranslated a Date column refused
every *correctly* formatted date in the file and kept only the ones somebody had
typed as a string — backwards, and silent. See `_cell_for_custom_column`.

A partner's import fills **its own** added columns, through
`_partner_override`, not the office's — a partner laying the table out its own
way named those columns and it is those its file should fill.

`_scholars_from_sheet` returns `(rows, refused)` now rather than a list. Both
callers unpack it. See `api/test_import_fills_custom_columns.py`.
## A decided account's registration stays readable

Account Verification laid a whole registration out under every card in the
queue — identity, enrolment, educational background, scholarship eligibility,
the socioeconomic answers, the declared awards and their proof — and then threw
all of it away the moment somebody pressed Verify or Reject. The decided list
below the queue was six columns: name, role, term, decision, the message the
officer typed, and who typed it. "Why was this one rejected" had an answer and
none of the evidence behind it.

**View record** on each decided row opens the same registration again:

* the verdict, with the words that account actually reads — in their portal if
  they were verified, on the login page if they were not;
* the account itself: address, whether they ever confirmed it, role, when they
  registered, whether they can sign in;
* everything the registration form asked, rendered by the same partial the
  queue includes — `templates/vpsea/_account_record.html`. One file, so a group
  added to the form appears under the queue card and in the record or in
  neither;
* every scholarship declared with the registration beside what became of it:
  the award number, the tier, the proof, the imported row it was merged with,
  and whether an award was written.

That last one had nowhere else to be read at all. **Approving a declaration
writes an award, so the archives remember it. Rejecting one writes nothing** —
the link request flips to Rejected and the only trace was a notification in the
student's own portal, which the office cannot see. The office had no way to
answer "did this student declare a CHED grant, and what did we say?"

Nothing in the dialog is a control. Verify-anyway stays on the row where it has
always been, and no archive candidates are offered: nothing is being chosen any
more.

The decided list's declarations are fetched in two queries for the whole page
rather than through `declared_scholarships()` per account — that helper answers
for one student, and twenty-five rows asking it one at a time is fifty queries
for a page that needs two.

`modal-open.js` now ignores Escape while the document viewer is open, because
this is the first dialog with `data-doc` proof links inside it: closing a
preview would otherwise have closed the record underneath it as well.

See `api/test_account_verification.py`,
`TheDecidedListShowsTheWholeRecordTest` and
`TheDecidedRecordShowsWhatBecameOfADeclarationTest`.
