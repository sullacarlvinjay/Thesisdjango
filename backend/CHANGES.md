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
