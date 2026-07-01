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


class StudentProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField(max_length=20, unique=True)
    course = models.CharField(max_length=100)
    year_level = models.IntegerField(default=1)
    gwa = models.FloatField(default=0.0)
    contact_number = models.CharField(max_length=20, blank=True)
    address = models.CharField(max_length=200, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    family_income = models.FloatField(default=0.0)
    indigenous_group = models.CharField(max_length=100, blank=True)
    parent_employment = models.CharField(max_length=100, blank=True)
    is_pwd = models.BooleanField(default=False)
    is_athlete = models.BooleanField(default=False)
    is_coconut_farmer_family = models.BooleanField(default=False)
    has_other_scholarship = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"


class Scholarship(models.Model):
    TYPES = [
        ('Academic', 'Academic'), ('TDP', 'TDP'), ('DOST', 'DOST'),
        ('CHED', 'CHED'), ('CoScho', 'CoScho'), ('Sports', 'Sports'),
        ('Affirmative', 'Affirmative'), ('Staff', 'Staff'), ('GSIS', 'GSIS'),
    ]
    CATEGORIES = [('application', 'Application'), ('recommendation', 'Recommendation')]

    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=TYPES)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    description = models.TextField()
    eligibility = models.TextField()
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
    scholar_name = models.CharField(max_length=100)
    course = models.CharField(max_length=50)
    gwa = models.FloatField(default=0.0)
    year = models.IntegerField(default=0)
    imported_from = models.CharField(max_length=100, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class BillingRecord(models.Model):
    STATUSES = [
        ('Approved', 'Approved'),
        ('Pending Validation', 'Pending Validation'),
        ('Needs Revision', 'Needs Revision'),
    ]
    semester = models.CharField(max_length=20)
    amount = models.FloatField()
    submitted_at = models.DateField()
    status = models.CharField(max_length=30, choices=STATUSES, default='Pending Validation')


class LiquidationRecord(models.Model):
    STATUSES = [
        ('Approved', 'Approved'),
        ('Pending Validation', 'Pending Validation'),
        ('Needs Revision', 'Needs Revision'),
    ]
    batch = models.CharField(max_length=50)
    amount = models.FloatField()
    submitted_at = models.DateField()
    status = models.CharField(max_length=30, choices=STATUSES, default='Pending Validation')


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


class Office(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    manages = models.JSONField(default=list)

    def __str__(self):
        return self.name


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
    address = models.TextField()
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10)
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

    def __str__(self):
        return f"{self.full_name} — {self.qualified_for}"

    def set_password(self, raw_password):
        from django.contrib.auth.hashers import make_password
        self.password = make_password(raw_password)

    def check_password(self, raw_password):
        from django.contrib.auth.hashers import check_password
        return check_password(raw_password, self.password)

    def determine_qualification(self):
        # NSU Staff check
        if self.has_baccalaureate:
            pass  # disqualified from NSU Staff
        elif self.is_nsu_staff or (self.is_nsu_dependent and self.staff_employee_id):
            return 'Staff'
        # Affirmative check
        if (self.shs_gpa is not None and self.shs_gpa >= 75 and
                self.suc_exam_score is not None and self.suc_exam_score >= 50 and
                not self.is_tes_beneficiary):
            return 'Affirmative'
        return 'None'


class ScholarshipRollover(models.Model):
    scholarship_type = models.CharField(max_length=20)
    school_year = models.CharField(max_length=20)  # e.g. '2024-2025'
    scholar_count = models.IntegerField(default=0)
    excel_file = models.FileField(upload_to='rollovers/')
    rolled_over_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.scholarship_type} — {self.school_year} ({self.scholar_count} scholars)'


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
