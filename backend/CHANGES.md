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
