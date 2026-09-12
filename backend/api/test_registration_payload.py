"""One complete registration, for the tests that have to post a valid one.

Not a test module — a fixture. It lives under ``test_`` so it sits beside the
modules that use it, and so a reader asking "what does a registration look like
now" finds it where they are already reading.

The form asks for the whole student record and refuses everything short of it,
bar the seven optional questions named in
:mod:`api.test_register_optional_labels`. That turned every "post a minimal
registration" helper in the suite into a thirty-line dict, and thirty-line dicts
copied into seven modules drift apart: one of them keeps working while the form
moves under it, and the test goes on passing about a form nobody has.

So there is one of them, and a test overrides only what it is actually about::

    from api.test_registration_payload import a_student

    Client().post('/register/', a_student(email='ana@gmail.com',
                                          student_id='23-0002'))

The values are answers rather than filler. A test that posts ``x`` for a birth
place proves the field is accepted and nothing about whether it is the right
field; these read the way the form reads, so a failure message shows a record
somebody could recognise.
"""

STUDENT = {
    'account_type': 'student',
    # The account's own
    'first_name': 'Juan', 'last_name': 'Dela Cruz', 'middle_name': 'Ramirez',
    'email': 'juan@bipsu.edu.ph', 'contact_number': '09171234567',
    'password': 'demo1234', 'confirm_password': 'demo1234',
    # Personal. 'NO' is how CHED's Disability_List spells not applicable, and
    # it is an answer — the form no longer takes a blank there.
    'date_of_birth': '2004-03-11', 'gender': 'Female',
    'birth_place': 'Naval, Biliran', 'civil_status': 'Single',
    'disability_type': 'NO',
    'barangay': 'Brgy. Larrazabal', 'municipality': 'Naval', 'province': 'Biliran',
    # Enrolment
    'student_id': '2022-00999',
    'school': 'School of Technologies and Computer Studies',
    'course': 'BSCS', 'year_level': '2',
    # Educational background
    'elementary': 'Naval Central School', 'highschool': 'Biliran NHS',
    'last_school': 'Biliran NHS',
    # Two of the four groups the Affirmative Action programme is for. Asked of
    # every student, not only of applicants, so they sit here rather than in
    # ELIGIBILITY below — see api/affirmative_ranking.py. Answered 'no' on
    # purpose: a fixture that claimed both would make every test in the suite a
    # test about a student the mandate reaches.
    'highschool_is_public': 'no', 'is_from_depressed_area': 'no',
    # Socio-economic. Indigenous Group is left out on purpose: it is the one
    # question on the form that stays optional, and a fixture that answered it
    # would hide the fact that a registration without it is accepted.
    'family_income': '180000',
    # Scholarship eligibility. Asked only of a student who holds nothing yet —
    # see :func:`a_declared_scholar`.
    'shs_gpa': '92.5', 'suc_exam_score': '35', 'suc_exam_total': '50',
    # TES eligibility
    'citizenship': 'Filipino', 'household_size': '5', 'year_first_enrolled': '2023',
    'is_listahanan_household': 'yes', 'is_4ps_beneficiary': 'no',
    'is_solo_parent_dependent': 'no', 'has_previous_degree': 'no',
}

# The questions the two eligibility cards ask. A student who ticks "I already
# hold a scholarship" is not asked them: register-scholarship.js closes both
# cards and disables their fields, so none of this arrives, and the server must
# not demand what it did not ask for.
ELIGIBILITY = ('shs_gpa', 'suc_exam_score', 'suc_exam_total',
               'citizenship', 'household_size', 'year_first_enrolled',
               'is_listahanan_household', 'is_4ps_beneficiary',
               'is_solo_parent_dependent', 'has_previous_degree')

STAFF = {
    'account_type': 'nsu_staff',
    'first_name': 'Ernesto', 'last_name': 'Dela Pena', 'middle_name': 'Bagayas',
    'email': 'ernesto@bipsu.edu.ph', 'contact_number': '09181234567',
    'password': 'pw-for-tests', 'confirm_password': 'pw-for-tests',
    'school_id': 'EMP-0042', 'staff_school': 'School of Engineering',
    'department': 'Civil Engineering', 'position': 'Instructor I',
}


def a_student(**overrides):
    """A student registration the form accepts, with `overrides` applied."""
    return dict(STUDENT, **overrides)


def a_declared_scholar(**overrides):
    """The same, as it arrives from a student who already holds an award.

    The eligibility answers are dropped rather than blanked, because that is
    what a disabled field posts: nothing at all.
    """
    data = {name: value for name, value in STUDENT.items()
            if name not in ELIGIBILITY}
    data['has_scholarship'] = 'on'
    return dict(data, **overrides)


def a_staff_member(**overrides):
    """A BiPSU staff registration the form accepts, with `overrides` applied."""
    return dict(STAFF, **overrides)
