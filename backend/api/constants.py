USER_ROLES = [
    ('student', 'Student'),
    ('nsu_staff', 'BiPSU Staff'),
    ('vpsea', 'VPSEA Admin'),
    ('partner', 'External Partner'),
    ('super', 'Super Admin'),
]


VERIFICATION_STATUSES = [
    ('pending', 'Pending Verification'),
    ('approved', 'Verified'),
    ('rejected', 'Rejected'),
]

DEFAULT_APPROVAL_MESSAGE = (
    'Your account has been verified by the SDSO. You can sign in now.'
)


UNIVERSITY_SCHOLAR_MAX_GWA = 1.29
COLLEGE_SCHOLAR_MAX_GWA = 1.50


APPLICATION_STATUSES = [
    ('Pending Validation', 'Pending Validation'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
    ('Needs Revision', 'Needs Revision'),
]

REVIEW_STATUSES = [
    ('Pending', 'Pending'),
    ('Approved', 'Approved'),
    ('Rejected', 'Rejected'),
]

DECIDED_APPLICATION_STATUSES = ('Approved', 'Rejected', 'Needs Revision')

EDITABLE_APPLICATION_STATUSES = ('Pending Validation', 'Needs Revision')

RECOMMENDATION_STATUSES = [
    ('Recommended', 'Recommended'),
    ('Disqualified', 'Disqualified'),
]

NOTIFICATION_TYPES = [
    ('success', 'Success'),
    ('warning', 'Warning'),
    ('info', 'Info'),
]


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

STUDENT_UNDECLARABLE_TYPES = frozenset({'Staff', 'Affirmative'})

DECLARABLE_SCHOLARSHIP_TYPES = [
    (value, label) for value, label in SCHOLARSHIP_TYPE_CHOICES
    if value not in STUDENT_UNDECLARABLE_TYPES
]

STAFF_DECLARABLE_TYPE = 'Staff'
STAFF_DECLARABLE_LABEL = dict(SCHOLARSHIP_TYPE_CHOICES)[STAFF_DECLARABLE_TYPE]


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

def available_logos():
    import os

    from django.conf import settings

    folder = os.path.join(settings.MEDIA_ROOT, 'logos')
    try:
        names = os.listdir(folder)
    except OSError:
        return []
    return sorted(n for n in names
                  if n.lower().endswith(('.png', '.jpg', '.jpeg', '.svg')))


SCHOLARSHIP_LOGO_DEFAULT = 'BiPSU.png'
SCHOLARSHIP_LOGOS = {
    'Academic':    'BiPSU.png',
    'Staff':       'BiPSU.png',
    'Sports':      'BiPSU.png',
    'Affirmative': 'BiPSU.png',
    'DOST':        'DOST.png',
    'JLSS':        'DOST.png',
    'CHED':        'CHED.png',
    'CoScho':      'CHED.png',
    'TES':         'UniFAST.png',
    'TDP':         'UniFAST.png',
    'SUC-TDP':     'UniFAST.png',
    'FHE':         'UniFAST.png',
}

QUALIFICATION_CHOICES = [
    ('Affirmative', 'Affirmative Action Scholarship'),
    ('Staff', 'BiPSU Staff Scholarship'),
    ('None', 'Not Qualified'),
]


APPLICATION_SOURCES = [
    ('portal', 'Student portal'),
    ('link', 'Approved link request'),
    ('renewal', 'Approved renewal'),
    ('import', 'Office import'),
]


SEMESTERS = [
    ('1st Semester', '1st Semester'),
    ('2nd Semester', '2nd Semester'),
]

STUDENT_LEVELS = [
    ('Undergraduate', 'Undergraduate'),
    ('Graduate', 'Graduate'),
    ('Post-Graduate', 'Post-Graduate'),
]


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


EMPLOYMENT_STATUSES = [
    ('Regular', 'Regular'),
    ('Contract of Service', 'Contract of Service'),
    ('Part Time', 'Part Time'),
    ('Job Order', 'Job Order'),
]

DESIGNATIONS = [
    ('Teaching', 'Teaching'),
    ('Non-Teaching', 'Non-Teaching'),
]


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


BIPSU_TEACHING_UNITS = [
    ('School of Law and Governance', 'School of Law and Governance'),
    ('School of Graduate Studies', 'School of Graduate Studies'),
    ('School of Agri-Industries and Natural Resource Management',
     'School of Agri-Industries and Natural Resource Management'),
    ('School of Teacher Education Biliran Campus',
     'School of Teacher Education Biliran Campus'),
    ('National Service Training Program', 'National Service Training Program'),
]

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

BIPSU_STAFF_UNITS = BIPSU_SCHOOLS + BIPSU_TEACHING_UNITS + BIPSU_OFFICES

BIPSU_STAFF_UNIT_GROUPS = [
    ('Academic units', BIPSU_SCHOOLS + BIPSU_TEACHING_UNITS),
    ('Administrative offices', BIPSU_OFFICES),
]


def school_for_course(course):
    course = (course or '').strip()
    if not course:
        return ''
    for school, courses in BIPSU_COURSES.items():
        if course in courses:
            return school
    return ''


def academic_classification(gwa):
    if not gwa or gwa <= 0:
        return ''
    if gwa <= UNIVERSITY_SCHOLAR_MAX_GWA:
        return 'University Scholar'
    if gwa <= COLLEGE_SCHOLAR_MAX_GWA:
        return 'College Scholar'
    return 'Not Eligible'
