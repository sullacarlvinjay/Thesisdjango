"""Reference data and choice lists for the SRMS.

Kept out of ``models.py`` so that file holds nothing but entity definitions and
reads cleanly as an entity-relationship diagram. Import from here rather than
re-declaring a choices list on a model.
"""

# ── Accounts ────────────────────────────────────────────────────────────────

USER_ROLES = [
    ('student', 'Student'),
    ('nsu_staff', 'BiPSU Staff'),
    ('vpsea', 'VPSEA Admin'),
    # An outside body that funds scholarships here — DOST, GSIS, a foundation.
    # Not a BiPSU office: what it may see is decided by the SDSO, one partner
    # at a time, rather than being a property of the role. See PartnerOffice.
    ('partner', 'External Partner'),
    ('super', 'Super Admin'),
]


# ── Account verification ────────────────────────────────────────────────────

# A self-registered account waits for the SDSO before it can sign in. Accounts
# the office creates itself are approved the moment they exist.
VERIFICATION_STATUSES = [
    ('pending', 'Pending Verification'),
    ('approved', 'Verified'),
    ('rejected', 'Rejected'),
]

# What the person is told when the office approves without typing anything of
# their own. A rejection always carries the reviewer's own reason.
DEFAULT_APPROVAL_MESSAGE = (
    'Your account has been verified by the SDSO. You can sign in now.'
)


# ── Academic scholarship classification ───────────────────────────────────────

# The two GWA ceilings the Academic Scholarship is judged on. The apply page
# shows the same numbers to the applicant and reads them from here, so the rule
# printed on screen cannot drift from the rule actually applied.
UNIVERSITY_SCHOLAR_MAX_GWA = 1.29
COLLEGE_SCHOLAR_MAX_GWA = 1.50


# ── Workflow statuses ───────────────────────────────────────────────────────

# Full review lifecycle: scholarship applications, which can be sent back for
# correction. There is no draft — a submission the office cannot see is one
# nobody can act on. An applicant corrects a real submission instead, for as
# long as it has no decision on it; see EDITABLE_APPLICATION_STATUSES.
APPLICATION_STATUSES = [
    ('Pending Validation', 'Pending Validation'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
    ('Needs Revision', 'Needs Revision'),
]

# Simple review lifecycle: submissions that are only ever waved through or
# turned down — renewals and link requests.
REVIEW_STATUSES = [
    ('Pending', 'Pending'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
]

# A decision is made once. These are the statuses that record one, so a review
# screen must refuse to overwrite them: an approval quietly turned into a
# rejection days later leaves the applicant holding a notification that no
# longer matches their record, and nothing saying who changed it or why.
# Everything not listed here — Pending Validation, Pending — is a
# submission still waiting on the office.
DECIDED_APPLICATION_STATUSES = ('Approved', 'Rejected', 'Needs Revision')
DECIDED_REVIEW_STATUSES = ('Approved', 'Rejected')

# The other side of the same line: what the APPLICANT may still change.
#
# A submission stays open to correction until a decision lands on it, and
# 'Needs Revision' is the office asking for exactly that — the student uploaded
# the wrong document and is being told to send it again. Approved and Rejected
# are final, and a student can no more edit those than a reviewer can overwrite
# them.
EDITABLE_APPLICATION_STATUSES = ('Pending Validation', 'Needs Revision')
EDITABLE_REVIEW_STATUSES = ('Pending',)

# A recommendation says whether the rules pass, and nothing else. There is no
# 'Endorsed' any more: the award itself is recorded on the Archives page like
# every other programme's, so a separate endorsement flag here was a second,
# private status for a decision already written down somewhere the reports read.
RECOMMENDATION_STATUSES = [
    ('Recommended', 'Recommended'),
    ('Disqualified', 'Disqualified'),
]

NOTIFICATION_TYPES = [
    ('success', 'Success'),
    ('warning', 'Warning'),
    ('info', 'Info'),
]


# ── Scholarships ────────────────────────────────────────────────────────────

# Canonical scholarship type keys. The key is what gets stored on
# Scholarship.type, ImportedScholar.scholarship_type and
# ScholarshipLinkRequest.scholarship_type; the label is display only.
# 'Staff' is the BiPSU Staff Scholarship — one program, one key.
SCHOLARSHIP_TYPE_CHOICES = [
    ('Academic', 'Academic Scholarship'),
    ('TDP', 'TDP Scholarship'),
    ('SUC-TDP', 'SUC-TDP Scholarship'),
    ('DOST', 'DOST S&T Undergraduate Scholarship'),
    ('JLSS', 'DOST Junior Level Science Scholarship'),
    ('CHED', 'CHED Scholarship'),
    ('CoScho', 'CoScho Scholarship'),
    ('Sports', 'Sports Scholarship'),
    ('GSIS', 'GSIS Scholarship'),
    ('Affirmative', 'Affirmative Scholarship'),
    ('Staff', 'BiPSU Staff Scholarship'),
]

# What a STUDENT may declare they already hold, at registration. Not the same
# list as the one above: that one is every award this system records, whoever
# holds it, and two of those are not a student's to claim.
#
# 'Staff' is the BiPSU Staff Scholarship. An employee holds it, or a dependent
# of one does — so a student *can* be on it — but it is neither applied for nor
# recorded on the student side: a Staff award lives on an
# AffirmativeStaffApplication, which has no StudentProfile to hang off. A
# student declaring it left the office with a claim it could approve into the
# wrong ledger, or not at all. A staff member declares it on their own half of
# the registration form instead.
#
# 'Affirmative' is out for the same structural reason: it is the other
# programme AffirmativeStaffApplication records, and nobody applies for it in
# any case — eligibility is read off the student's profile.
STUDENT_UNDECLARABLE_TYPES = frozenset({'Staff', 'Affirmative'})

DECLARABLE_SCHOLARSHIP_TYPES = [
    (value, label) for value, label in SCHOLARSHIP_TYPE_CHOICES
    if value not in STUDENT_UNDECLARABLE_TYPES
]

# What a STAFF member may declare on their half of the same form. Exactly one
# programme, so the form asks it as a checkbox rather than a dropdown — a select
# with a single option is a question that answers itself.
#
# Affirmative Action is the other programme on that record and is deliberately
# not here: nobody applies for it, so nobody can hold it without this system
# having decided so already.
STAFF_DECLARABLE_TYPE = 'Staff'
STAFF_DECLARABLE_LABEL = dict(SCHOLARSHIP_TYPE_CHOICES)[STAFF_DECLARABLE_TYPE]


# Two more programmes on the university's chart are deliberately absent from
# SCHOLARSHIP_TYPE_CHOICES altogether, rather than merely from the declarable
# lists above.
#
# TES is absent because nothing in this system awards or verifies it. It is
# UniFAST's, administered outside the portal entirely, so a student declaring it
# would be handing the SDSO a claim it has no record to check against. There is
# one place TES is still asked about — the is_tes_beneficiary checkbox, which
# Affirmative Action disqualifies on — and that is a self-declaration the
# Affirmative rules read, not an award the office records.
#
# FHE is absent for a different reason. Free Higher Education under RA 10931 is
# not awarded to anyone — it is the tuition every qualified student at a state
# university already has, so there is nothing for the SDSO to verify against
# their records. Listing it here would also make it exclusive: the declare flow
# feeds held_scholarship_types, and can_hold_alongside would then refuse a DOST
# application from a student for holding what all of them hold. It is in the
# catalogue and on the landing page, where saying it exists is the point.

# CHED awards under one programme but at two tiers, and every masterlist CHED
# appears on is split by them. The programme name cannot be relied on to say
# which — "CHED Merit" covers both — so the tier is carried on the record that
# creates the award. The labels are the exact block headings the reports print.
CHED_TIER_CHOICES = [
    ('Full', 'Full Merit / Full Scholar'),
    ('Half', 'Half Merit / Partial Scholar'),
]

SCHOLARSHIP_CATEGORIES = [
    ('application', 'Application'),
    ('recommendation', 'Recommendation'),
]

SCHOLARSHIP_GROUPS = [
    ('internal', 'Internal'),
    ('external', 'External'),
    ('institutional', 'Institutional'),
]

# Which agency's seal belongs on a programme, keyed by the same type key.
#
# The landing page showed the BiPSU seal on every card, including the ones BiPSU
# does not fund — a DOST scholarship advertised under the university's own logo,
# which is the sort of thing an accrediting body reads as a claim. The mapping
# follows the university's own programme chart: DOST runs the S&T undergraduate
# scholarships and JLSS; CHED runs CHED-Merit and CoScho; TES and TDP are
# UniFAST's, not CHED's, however often the two are spoken of together.
#
# The seals live in media/logos/ and are public branding — see
# api.media_views.PUBLIC_PREFIXES — so an anonymous visitor can load them.
# A type absent here falls back to BiPSU's seal, which is right for the
# programmes BiPSU funds itself and a neutral placeholder for an agency whose
# logo the office has not supplied (GSIS today).
def available_logos():
    """The seal files on disk, newest additions included, sorted for display.

    Read from the directory rather than hard-coded so a seal committed to
    media/logos/ is offered to the office without a code change — which is the
    whole route by which a new agency logo arrives. Returns bare filenames; the
    only thing the office may store is one of these, so a stored value can never
    be a path.
    """
    import os

    from django.conf import settings

    folder = os.path.join(settings.MEDIA_ROOT, 'logos')
    try:
        names = os.listdir(folder)
    except OSError:
        # No MEDIA_ROOT on a fresh checkout is not worth an exception here; the
        # form falls back to offering nothing but the per-type default.
        return []
    return sorted(n for n in names
                  if n.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')))


SCHOLARSHIP_LOGO_DEFAULT = 'BiPSU.png'
SCHOLARSHIP_LOGOS = {
    # BiPSU's own — Academic (University/College Scholar), Staff, Sports and
    # Cultural, Affirmative Action.
    'Academic':    'BiPSU.png',
    'Staff':       'BiPSU.png',
    'Sports':      'BiPSU.png',
    'Affirmative': 'BiPSU.png',
    # Externally funded, by the agency that funds them.
    'DOST':        'DOST.png',
    'JLSS':        'DOST.png',
    'CHED':        'CHED.png',
    'CoScho':      'CHED.png',
    'TES':         'UniFAST.png',
    'TDP':         'UniFAST.png',
    'SUC-TDP':     'UniFAST.png',
    'FHE':         'UniFAST.png',
}

# What an AffirmativeStaffApplication was found to qualify for.
QUALIFICATION_CHOICES = [
    ('Affirmative', 'Affirmative Action Scholarship'),
    ('Staff', 'BiPSU Staff Scholarship'),
    ('None', 'Not Qualified'),
]


# ── Award provenance ────────────────────────────────────────────────────────

# Which route created an Application row. These were already written as free
# strings into form_data by three separate views; named here so the set is
# closed and the admin renders them properly.
APPLICATION_SOURCES = [
    ('portal', 'Student portal'),
    ('link', 'Approved link request'),
    ('renewal', 'Approved renewal'),
    ('import', 'Office import'),
]


# ── Academic calendar ───────────────────────────────────────────────────────

SEMESTERS = [
    ('1st Semester', '1st Semester'),
    ('2nd Semester', '2nd Semester'),
]

# The programme level a student is enrolled at. Recorded on EnrollmentData
# alongside the course, because a course name alone does not say it — BSN is
# undergraduate, an MA in the same school is not.
STUDENT_LEVELS = [
    ('Undergraduate', 'Undergraduate'),
    ('Graduate', 'Graduate'),
    ('Post-Graduate', 'Post-Graduate'),
]


# ── Personal details ──────────────────────────────────────────────────────────

# Recorded on students, staff applicants and imported scholar rows. The
# masterlist exports a single-letter sex column derived from this, so the set
# has to stay closed.
GENDERS = [
    ('Male', 'Male'),
    ('Female', 'Female'),
]

CIVIL_STATUSES = [
    ('Single', 'Single'),
    ('Married', 'Married'),
    ('Widowed', 'Widowed'),
    ('Separated', 'Separated'),
]


# ── BiPSU staff employment ────────────────────────────────────────────────────

EMPLOYMENT_STATUSES = [
    ('Regular', 'Regular'),
    ('Contractual', 'Contractual'),
    ('Part-time', 'Part-time'),
]

DESIGNATIONS = [
    ('Teaching', 'Teaching'),
    ('Non-Teaching', 'Non-Teaching'),
]


# ── BiPSU academic structure ────────────────────────────────────────────────

BIPSU_SCHOOLS = [
    ('School of Technologies and Computer Studies', 'School of Technologies and Computer Studies'),
    ('School of Engineering', 'School of Engineering'),
    ('School of Nursing and Health Sciences', 'School of Nursing and Health Sciences'),
    ('School of Criminal Justice Education', 'School of Criminal Justice Education'),
    ('School of Tourism and Hospitality Management', 'School of Tourism and Hospitality Management'),
    ('School of Arts and Sciences', 'School of Arts and Sciences'),
    ('School of Teacher Education', 'School of Teacher Education'),
    ('School of Business and Management', 'School of Business and Management'),
]

BIPSU_COURSES = {
    'School of Technologies and Computer Studies': [
        'BSCS', 'BSIS',
        'BSIT - Automotive Technology', 'BSIT - Architectural Drafting',
        'BSIT - Electrical Technology', 'BSIT - Electronics Technology',
        'BSIT - Culinary Technology', 'BSIT - Apparel and Fashion Design Technology',
        'BSIT - HVAC-R Technology',
    ],
    'School of Engineering': ['BSCE', 'BSEE', 'BSCpE', 'BSME'],
    'School of Nursing and Health Sciences': ['BSN'],
    'School of Criminal Justice Education': ['BSCrim', 'BSISM'],
    'School of Tourism and Hospitality Management': ['BSHM', 'BSTM'],
    'School of Arts and Sciences': ['BAComm', 'BAEcon'],
    'School of Teacher Education': [
        'BSEd - Mathematics', 'BSEd - Science', 'BSEd - English',
        'BSEd - Filipino', 'BSEd - Social Studies',
        'BEEd', 'BTLEd', 'BPEd', 'BECEd', 'BSNEd',
    ],
    'School of Business and Management': [
        'BSBA - Financial Management', 'BSBA - Marketing Management',
    ],
}


# ── Where a BiPSU employee works ────────────────────────────────────────────
#
# Its own list, and deliberately not BIPSU_SCHOOLS.
#
# That one is the list a *student* enrols in, and every entry has courses under
# it in BIPSU_COURSES — the Course dropdown on the registration form is built
# from them, and it is required, so a school with no courses under it is one a
# student can pick and then be unable to finish the form. Half of what an
# employee can be assigned to has no courses and never will: the
# vice-presidents' offices, the two lifelong-learning offices, the library.
#
# An employee is not enrolled in anything, so nothing here feeds a course list.
# The dropdown offers all three lists below, grouped so the schools read apart
# from the offices — see BIPSU_STAFF_UNIT_GROUPS.

# Teaching units that grant no undergraduate degree through BIPSU_COURSES:
# graduate and professional schools, the Biliran campus's own teacher-education
# unit, and NSTP, which every student takes and none majors in.
BIPSU_TEACHING_UNITS = [
    ('School of Law and Governance', 'School of Law and Governance'),
    ('School of Graduate Studies', 'School of Graduate Studies'),
    ('School of Agri-Industries and Natural Resource Management',
     'School of Agri-Industries and Natural Resource Management'),
    ('School of Teacher Education Biliran Campus',
     'School of Teacher Education Biliran Campus'),
    ('National Service Training Program', 'National Service Training Program'),
]

# Non-teaching assignments: the four vice-presidential clusters, the two
# offices under Academic Affairs, and the library.
BIPSU_OFFICES = [
    ('Academic Affairs & Lifelong Learning', 'Academic Affairs & Lifelong Learning'),
    ('Research, Innovation, and Social Impact', 'Research, Innovation, and Social Impact'),
    ('Student, Internationalization & Strategic Partner',
     'Student, Internationalization & Strategic Partner'),
    ('Administration, Finance, & Sustainable Management',
     'Administration, Finance, & Sustainable Management'),
    ('Office of Advance and Accessible Lifelong Learning',
     'Office of Advance and Accessible Lifelong Learning'),
    ('Office of Teaching, Learning, and Curriculum Effectiveness',
     'Office of Teaching, Learning, and Curriculum Effectiveness'),
    ('Center for Learning Resources', 'Center for Learning Resources'),
]

# Everything an employee may be assigned to, flat. This is what StaffProfile.school
# validates against; the grouping below is only how the dropdown draws it.
BIPSU_STAFF_UNITS = BIPSU_SCHOOLS + BIPSU_TEACHING_UNITS + BIPSU_OFFICES

# The same list as <optgroup>s. A flat list of twenty is a list nobody reads to
# the end of, and the two halves answer different questions — an employee knows
# straight away which half they are in.
BIPSU_STAFF_UNIT_GROUPS = [
    ('Academic units', BIPSU_SCHOOLS + BIPSU_TEACHING_UNITS),
    ('Administrative offices', BIPSU_OFFICES),
]


def school_for_course(course):
    """The school a course belongs to, or '' when it matches none of them.

    Students type their course free-hand at registration and the office picks it
    from a dropdown, so the two do not always agree on spelling. Only an exact
    match counts — guessing a school wrong is worse than leaving it blank for
    the office to set.
    """
    course = (course or '').strip()
    if not course:
        return ''
    for school, courses in BIPSU_COURSES.items():
        if course in courses:
            return school
    return ''


def academic_classification(gwa):
    """'University Scholar' | 'College Scholar' | 'Not Eligible' for a GWA.

    GWA runs the other way from a percentage — 1.00 is the top mark and larger
    numbers are worse, so these are ceilings. A blank or zero GWA means nothing
    has been entered yet, which is not the same as a perfect one: it returns ''
    rather than crowning an empty form University Scholar.
    """
    if not gwa or gwa <= 0:
        return ''
    if gwa <= UNIVERSITY_SCHOLAR_MAX_GWA:
        return 'University Scholar'
    if gwa <= COLLEGE_SCHOLAR_MAX_GWA:
        return 'College Scholar'
    return 'Not Eligible'
