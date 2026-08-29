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
    ('unifast', 'UniFAST Admin'),
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

# Full review lifecycle: scholarship applications that can be saved as a draft
# and sent back for correction.
APPLICATION_STATUSES = [
    ('Pending Validation', 'Pending Validation'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
    ('Needs Revision', 'Needs Revision'),
    ('Draft', 'Draft'),
]

# Simple review lifecycle: submissions that are only ever waved through or
# turned down — renewals, link requests, TES applications.
REVIEW_STATUSES = [
    ('Pending', 'Pending'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
]

RECOMMENDATION_STATUSES = [
    ('Recommended', 'Recommended'),
    ('Endorsed', 'Endorsed'),          # VPSEA formally endorses the student
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
    ('DOST', 'DOST Scholarship'),
    ('CHED', 'CHED Scholarship'),
    ('CoScho', 'CoScho Scholarship'),
    ('Sports', 'Sports Scholarship'),
    ('GSIS', 'GSIS Scholarship'),
    ('Affirmative', 'Affirmative Scholarship'),
    ('Staff', 'BiPSU Staff Scholarship'),
]

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
    ('tes_application', 'Approved TES application'),
    ('renewal', 'Approved renewal'),
    ('import', 'Office import'),
]


# ── Academic calendar ───────────────────────────────────────────────────────

SEMESTERS = [
    ('1st Semester', '1st Semester'),
    ('2nd Semester', '2nd Semester'),
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
