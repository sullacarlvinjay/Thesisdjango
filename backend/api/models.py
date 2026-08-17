from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    ROLES = [
        ('student', 'Student'),
        ('vpsea', 'VPSEA Admin'),
        ('unifast', 'UniFAST Admin'),
        ('super', 'Super Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLES, default='student')
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']


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


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField(max_length=20, unique=True)
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100)
    year_level = models.IntegerField(default=1)
    gwa = models.FloatField(default=0.0)
    contact_number = models.CharField(max_length=20, blank=True)
    barangay = models.CharField(max_length=100, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    family_income = models.FloatField(default=0.0)
    indigenous_group = models.CharField(max_length=100, blank=True)
    parent_employment = models.CharField(max_length=100, blank=True)
    is_pwd = models.BooleanField(default=False)
    is_athlete = models.BooleanField(default=False)
    is_coconut_farmer_family = models.BooleanField(default=False)
    has_other_scholarship = models.BooleanField(default=False)
    # Educational background
    elementary = models.CharField(max_length=200, blank=True)
    highschool = models.CharField(max_length=200, blank=True)
    last_school = models.CharField(max_length=200, blank=True)
    # Family background
    father_name = models.CharField(max_length=200, blank=True)
    father_occupation = models.CharField(max_length=200, blank=True)
    mother_name = models.CharField(max_length=200, blank=True)
    mother_occupation = models.CharField(max_length=200, blank=True)

    @property
    def address(self):
        parts = [p for p in [self.barangay, self.municipality, self.province] if p]
        return ', '.join(parts)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"


class Scholarship(models.Model):
    CATEGORIES = [('application', 'Application'), ('recommendation', 'Recommendation')]
    GROUPS = [
        ('internal', 'Internal'),
        ('external', 'External'),
        ('institutional', 'Institutional'),
    ]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    group = models.CharField(max_length=20, choices=GROUPS, default='internal')
    description = models.TextField()
    eligibility = models.TextField()
    background = models.TextField(blank=True)
    eligibility_list = models.JSONField(default=list, blank=True)
    benefits = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    def match_score(self, profile):
        if not profile:
            return 0
        score = 50
        if self.type == 'Academic' and profile.gwa <= 1.50:
            score += 30 if profile.gwa <= 1.29 else 15
        if self.type == 'TDP' and profile.family_income < 60000:
            score += 30
        if profile.is_athlete and self.type == 'Sports':
            score += 30
        return min(score, 100)

    def __str__(self):
        return self.name


class Application(models.Model):
    STATUSES = [
        ('Pending Validation', 'Pending Validation'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Needs Revision', 'Needs Revision'),
        ('Draft', 'Draft'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='applications')
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE)
    status = models.CharField(max_length=30, choices=STATUSES, default='Pending Validation')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)
    form_data = models.JSONField(default=dict)

    def __str__(self):
        return f"{self.student.student_id} — {self.scholarship.name}"


class ApplicationDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)


class Notification(models.Model):
    TYPES = [('success', 'Success'), ('warning', 'Warning'), ('info', 'Info')]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=10, choices=TYPES, default='info')
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Renewal(models.Model):
    STATUSES = [
        ('Renewal Pending', 'Renewal Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='renewals')
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE)
    previous_gwa = models.FloatField()
    current_gwa = models.FloatField()
    status = models.CharField(max_length=20, choices=STATUSES, default='Renewal Pending')
    report_card = models.FileField(upload_to='renewals/', null=True, blank=True)
    created_at = models.DateField(auto_now_add=True)


class ArchiveRecord(models.Model):
    scholarship_type = models.CharField(max_length=20)
    rollover_label = models.CharField(max_length=20, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    scholar_name = models.CharField(max_length=200, blank=True)  # kept for legacy
    gender = models.CharField(max_length=10, blank=True)
    course = models.CharField(max_length=100, blank=True)
    year = models.IntegerField(default=0)
    gwa = models.FloatField(default=0.0)
    barangay = models.CharField(max_length=100, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    student_number = models.CharField(max_length=50, blank=True)
    award_number = models.CharField(max_length=50, blank=True)
    congress_district = models.CharField(max_length=100, blank=True)
    imported_from = models.CharField(max_length=100, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class TDPApplication(models.Model):
    STATUSES = [
        ('Pending Validation', 'Pending Validation'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Needs Revision', 'Needs Revision'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='tdp_applications')
    subsidy_amount = models.FloatField(default=20000)
    status = models.CharField(max_length=30, choices=STATUSES, default='Pending Validation')
    created_at = models.DateField(auto_now_add=True)


class AffirmativeNSUApplication(models.Model):
    SCHOLARSHIP_TYPES = [
        ('Affirmative', 'Affirmative Action Scholarship'),
        ('Staff', 'NSU Staff Scholarship'),
        ('None', 'Not Qualified'),
    ]
    STATUSES = [
        ('Pending Validation', 'Pending Validation'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Needs Revision', 'Needs Revision'),
        ('Draft', 'Draft'),
    ]
    # Personal Info
    full_name = models.CharField(max_length=200)
    email = models.EmailField(unique=True)
    contact_number = models.CharField(max_length=20)
    barangay = models.CharField(max_length=100, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100)
    year_level = models.IntegerField(default=1)
    school_id = models.CharField(max_length=30, blank=True)

    # NSU Staff eligibility fields
    is_nsu_staff = models.BooleanField(default=False)
    is_nsu_dependent = models.BooleanField(default=False)
    staff_name = models.CharField(max_length=200, blank=True)
    staff_employee_id = models.CharField(max_length=50, blank=True)
    relationship_to_staff = models.CharField(max_length=50, blank=True)
    has_baccalaureate = models.BooleanField(default=False)

    # Affirmative eligibility fields
    shs_gpa = models.FloatField(null=True, blank=True)
    shs_certificate = models.FileField(upload_to='affirmative/shs/', null=True, blank=True)
    suc_exam_score = models.FloatField(null=True, blank=True)
    suc_exam_certificate = models.FileField(upload_to='affirmative/suc/', null=True, blank=True)
    is_tes_beneficiary = models.BooleanField(default=False)

    # Result
    password = models.CharField(max_length=255, default='')
    qualified_for = models.CharField(max_length=20, choices=SCHOLARSHIP_TYPES, default='None')
    status = models.CharField(max_length=30, choices=STATUSES, default='Pending Validation')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def address(self):
        parts = [p for p in [self.barangay, self.municipality, self.province] if p]
        return ', '.join(parts)

    def __str__(self):
        return f"{self.full_name} — {self.qualified_for}"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def determine_qualification(self):
        if self.has_baccalaureate:
            pass
        elif self.is_nsu_staff or (self.is_nsu_dependent and self.staff_employee_id):
            return 'Staff'
        if (self.shs_gpa is not None and self.shs_gpa >= 75 and
                self.suc_exam_score is not None and self.suc_exam_score >= 50 and
                not self.is_tes_beneficiary):
            return 'Affirmative'
        return 'None'


class AcademicRenewal(models.Model):
    STATUSES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='academic_renewals')
    certificate_of_grades = models.FileField(upload_to='renewals/academic/')
    certificate_of_enrollment = models.FileField(upload_to='renewals/academic/')
    status = models.CharField(max_length=20, choices=STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.student} — Renewal ({self.status})"


class ScholarshipLinkRequest(models.Model):
    STATUSES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='link_requests')
    scholarship_type = models.CharField(max_length=50)
    proof_document = models.FileField(upload_to='link_requests/')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUSES, default='Pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student} — Link {self.scholarship_type} ({self.status})"


class ScholarshipRollover(models.Model):
    SEMESTERS = [('1st Semester', '1st Semester'), ('2nd Semester', '2nd Semester')]
    scholarship_type = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20, choices=SEMESTERS, default='1st Semester')
    label = models.CharField(max_length=20, blank=True)
    scholar_count = models.IntegerField(default=0)
    excel_file = models.FileField(upload_to='rollovers/')
    rolled_over_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.scholarship_type} — {self.label or self.school_year} {self.semester} ({self.scholar_count} scholars)'


class TESApplication(models.Model):
    STATUSES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='tes_applications')
    # Personal
    lrn = models.CharField(max_length=30, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    birthdate = models.DateField(null=True, blank=True)
    complete_program = models.CharField(max_length=200, blank=True)
    # Family background
    father_last_name = models.CharField(max_length=100, blank=True)
    father_first_name = models.CharField(max_length=100, blank=True)
    father_middle_name = models.CharField(max_length=100, blank=True)
    mother_last_name = models.CharField(max_length=100, blank=True)
    mother_first_name = models.CharField(max_length=100, blank=True)
    mother_middle_name = models.CharField(max_length=100, blank=True)
    # Address
    street_barangay = models.CharField(max_length=200, blank=True)
    city_municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)
    # Additional
    disability_type = models.CharField(max_length=100, blank=True)
    is_solo_parent_dependent = models.BooleanField(default=False)
    is_first_gen_college = models.BooleanField(default=False)
    indigenous_people_group = models.CharField(max_length=100, blank=True)
    # Status
    status = models.CharField(max_length=20, choices=STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.student} — TES ({self.status})"


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']


class SystemSettings(models.Model):

    academic_year = models.CharField(max_length=20, default='2025-2026')
    active_semester = models.CharField(max_length=20, default='1st Semester')
    email_notifications = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    inapp_push = models.BooleanField(default=True)
    max_file_size_mb = models.IntegerField(default=5)
    allowed_formats = models.CharField(max_length=50, default='PDF, JPG, PNG')
    show_match_scores = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'System Settings'

    @staticmethod
    def parse_label(label):
        try:
            yy, s = label.split('-')
            start = 2000 + int(yy)
            end = start + 1
            sem = '1st Semester' if s == '1' else '2nd Semester'
            return {'sy': f'{start}-{end}', 'semester': sem, 'sy_start': start, 'sy_end': end}
        except Exception:
            return {'sy': label, 'semester': '1st Semester', 'sy_start': None, 'sy_end': None}

    def next_label(self):
        yy, s = self.academic_year.split('-')
        if s == '1':
            return f'{yy}-2'
        else:
            return f'{int(yy)+1}-1'
