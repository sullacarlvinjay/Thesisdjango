from api import terms

STUDENT = {
    'account_type': 'student',
    'first_name': 'Juan', 'last_name': 'Dela Cruz', 'middle_name': 'Ramirez',
    'email': 'juan@bipsu.edu.ph', 'contact_number': '09171234567',
    'password': 'demo1234', 'confirm_password': 'demo1234',
    'date_of_birth': '2004-03-11', 'gender': 'Female',
    'birth_place': 'Naval, Biliran', 'civil_status': 'Single',
    'disability_type': 'NO',
    'barangay': 'Brgy. Larrazabal', 'municipality': 'Naval', 'province': 'Biliran',
    'student_id': '2022-00999',
    'school': 'School of Technologies and Computer Studies',
    'course': 'BSCS', 'year_level': '2',
    'elementary': 'Naval Central School', 'highschool': 'Biliran NHS',
    'last_school': 'Biliran NHS',
    'highschool_is_public': 'no', 'is_from_depressed_area': 'no',
    'family_income': '180000',
    'shs_gpa': '92.5', 'suc_exam_score': '35', 'suc_exam_total': '50',
    'citizenship': 'Filipino', 'household_size': '5', 'year_first_enrolled': '2023',
    'is_listahanan_household': 'yes', 'is_4ps_beneficiary': 'no',
    'is_solo_parent_dependent': 'no', 'has_previous_degree': 'no',
    'accept_terms': 'yes', 'terms_version': terms.VERSION,
}

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
    'accept_terms': 'yes', 'terms_version': terms.VERSION,
}


def a_student(**overrides):
    return dict(STUDENT, **overrides)


def a_declared_scholar(**overrides):
    data = {name: value for name, value in STUDENT.items()
            if name not in ELIGIBILITY}
    data['has_scholarship'] = 'on'
    return dict(data, **overrides)


def a_staff_member(**overrides):
    return dict(STAFF, **overrides)
