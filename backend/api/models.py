"""SRMS entities.

This module holds entity definitions only. Choice lists and BiPSU reference data
live in ``api/constants.py``; report and workflow logic lives in the views. Read
top to bottom, the classes below are the entity-relationship diagram:

    User ─1:1─ StudentProfile ─1:N─ Application ─N:1─ Scholarship
                             ├─1:N─ ApplicationDocument (via Application)
                             ├─1:N─ Notification
                             ├─1:N─ AcademicRenewal
                             ├─1:N─ TESApplication
                             ├─1:N─ ScholarshipLinkRequest ─0:1─ ImportedScholar
                             └─1:1─ AffirmativeRecommendation

    User ─1:1─ StaffProfile

    AffirmativeStaffApplication and StaffRenewal cover the Affirmative / BiPSU Staff
    programs, which are applied for outside the student portal. StaffProfile holds
    the employee's own details; the application keeps the snapshot it was approved
    on.
"""
from datetime import date

from django.contrib.auth.models import AbstractUser
from django.db import models

from .constants import (
    APPLICATION_SOURCES, APPLICATION_STATUSES, BIPSU_COURSES, BIPSU_SCHOOLS,
    CHED_TIER_CHOICES, CIVIL_STATUSES,
    GENDERS,
    DEFAULT_APPROVAL_MESSAGE, VERIFICATION_STATUSES,
    DESIGNATIONS, EMPLOYMENT_STATUSES, NOTIFICATION_TYPES,
    QUALIFICATION_CHOICES, RECOMMENDATION_STATUSES, REVIEW_STATUSES,
    SCHOLARSHIP_CATEGORIES, SCHOLARSHIP_GROUPS, SCHOLARSHIP_TYPE_CHOICES,
    SEMESTERS, USER_ROLES,
)

# Re-exported so existing `from .models import BIPSU_SCHOOLS` imports keep working.
__all__ = [
    'BIPSU_COURSES', 'BIPSU_SCHOOLS', 'CHED_TIER_CHOICES', 'SCHOLARSHIP_TYPE_CHOICES',
    'ched_tier', 'split_ched',
    'AcademicRenewal', 'ActivityLog', 'AffirmativeStaffApplication',
    'AffirmativeRecommendation', 'Announcement', 'Application',
    'ApplicationDocument', 'ImportedScholar', 'Notification', 'Scholarship',
    'ScholarshipLinkRequest', 'ScholarListImport', 'StaffProfile',
    'StaffRenewal', 'StudentProfile', 'SystemSettings', 'TESApplication',
    'User',
]


class PhilippineAddress(models.Model):
    """Barangay / municipality / province, shared by every record that has one.

    Abstract, so it adds no table and no box to the entity diagram — the columns
    land on each concrete model instead.
    """
    barangay = models.CharField(max_length=100, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)

    class Meta:
        abstract = True

    @property
    def address(self):
        parts = [p for p in [self.barangay, self.municipality, self.province] if p]
        return ', '.join(parts)


class PersonalInfo(models.Model):
    """The personal details every person on file has, student or staff.

    Abstract like :class:`PhilippineAddress`, so it adds no table of its own.
    The given and family names stay on ``User`` — Django's auth machinery and
    the admin expect them there — and only the parts Django has no field for
    live here. ``middle_initial`` is derived, never stored: it is the first
    letter of ``middle_name`` and would go stale the moment the name is fixed.
    """
    middle_name = models.CharField(max_length=100, blank=True)
    suffix = models.CharField(max_length=20, blank=True, help_text='Jr., Sr., III …')
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDERS, blank=True)
    civil_status = models.CharField(max_length=20, choices=CIVIL_STATUSES, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)

    class Meta:
        abstract = True

    @property
    def middle_initial(self):
        """First letter of middle_name, uppercased with a period. Empty string if no middle name."""
        name = (self.middle_name or '').strip()
        return f"{name[0].upper()}." if name else ''

    @property
    def full_name(self):
        """Last, First M.I. — e.g. 'dela Cruz, Juan A.', 'dela Cruz Jr., Juan A.'"""
        last = self.user.last_name.strip()
        first = self.user.first_name.strip()
        suffix = (self.suffix or '').strip()
        if last and suffix:
            last = f"{last} {suffix}"
        mi = self.middle_initial
        given = f"{first} {mi}".strip() if mi else first
        if last and given:
            return f"{last}, {given}"
        return last or given


class User(AbstractUser):
    """An account. Self-registered ones wait for the SDSO before they can sign in.

    ``verification_status`` defaults to approved, not pending, on purpose: every
    account the office creates itself — and every account that existed before
    this gate — is verified by the act of an officer creating it. Only the
    public registration form sets it to pending.

    The account stays ``is_active`` while it waits. Deactivating it instead
    would make ``authenticate()`` return None, and the login page could no
    longer tell a pending account apart from a wrong password — so the person
    would be stuck with 'Invalid credentials' and no idea why.
    """
    role = models.CharField(max_length=20, choices=USER_ROLES, default='student')
    email = models.EmailField(unique=True)

    verification_status = models.CharField(
        max_length=10, choices=VERIFICATION_STATUSES, default='approved',
    )
    # What the person is shown on the login page — the reviewer's own words when
    # they wrote any, otherwise the system's.
    verification_note = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_accounts',
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def awaiting_verification(self):
        return self.verification_status == 'pending'

    @property
    def can_sign_in(self):
        return self.is_active and self.verification_status == 'approved'

    def decide_verification(self, status, note, reviewer):
        """Record the SDSO's decision and the message the person will read."""
        from django.utils import timezone
        self.verification_status = status
        self.verification_note = (note or '').strip() or (
            DEFAULT_APPROVAL_MESSAGE if status == 'approved' else ''
        )
        self.verified_by = reviewer
        self.verified_at = timezone.now()
        self.save(update_fields=[
            'verification_status', 'verification_note', 'verified_by', 'verified_at',
        ])


class StudentProfile(PersonalInfo, PhilippineAddress):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField(max_length=20, unique=True)
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100)
    year_level = models.IntegerField(default=1)
    gwa = models.FloatField(default=0.0)

    # Needs-based and priority-group indicators.
    #
    # family_income is the household's ANNUAL income and defaults to 0.0, which
    # is indistinguishable from 'never entered' — so the TES recommender reads
    # 0.0 as missing rather than as a household with no income at all. See
    # api/tes_ranking.py.
    family_income = models.FloatField(default=0.0)
    # Needed to turn family_income into the per-capita figure TES ranks on.
    # Nullable because an unknown household size has to stay unknown: dividing
    # by an assumed size would invent a per-capita income.
    household_size = models.IntegerField(null=True, blank=True)
    indigenous_group = models.CharField(max_length=100, blank=True)
    parent_employment = models.CharField(max_length=100, blank=True)
    is_pwd = models.BooleanField(default=False)
    is_athlete = models.BooleanField(default=False)
    is_coconut_farmer_family = models.BooleanField(default=False)
    has_other_scholarship = models.BooleanField(default=False)

    # Affirmative scholarship eligibility inputs
    shs_gpa = models.FloatField(null=True, blank=True)
    shs_gpa_cert = models.FileField(upload_to='profile/shs_cert/', null=True, blank=True)
    suc_exam_score = models.FloatField(null=True, blank=True)
    suc_exam_cert = models.FileField(upload_to='profile/suc_cert/', null=True, blank=True)
    is_tes_beneficiary = models.BooleanField(default=False)

    # TES eligibility facts about the person and their household.
    #
    # Every one of these is three-state on purpose. A BooleanField defaulting to
    # False cannot tell 'the office confirmed no' apart from 'nobody has asked
    # yet', and the TES rules turn on that difference: missing data means the
    # requirement needs verification, never that the student failed it.
    citizenship = models.CharField(max_length=50, blank=True,
                                   help_text="Blank means not yet recorded, not 'non-Filipino'.")
    is_listahanan_household = models.BooleanField(
        null=True, blank=True,
        help_text='DSWD Listahanan listing. Null means not yet checked against the list.')
    is_4ps_beneficiary = models.BooleanField(
        null=True, blank=True,
        help_text='Pantawid Pamilyang Pilipino Program. Stands in for Listahanan when that list is unavailable.')
    has_previous_degree = models.BooleanField(
        null=True, blank=True,
        help_text='Holds an earlier undergraduate degree. Null means unknown.')
    year_first_enrolled = models.IntegerField(
        null=True, blank=True,
        help_text='Calendar year the student first enrolled in this programme, for the maximum-years rule.')

    # Educational background
    elementary = models.CharField(max_length=200, blank=True)
    highschool = models.CharField(max_length=200, blank=True)
    last_school = models.CharField(max_length=200, blank=True)

    # Family background. Parent names are held in parts rather than as one
    # string: CHED's TES form asks for them separately, and a combined name
    # cannot be split back reliably — "Maria Dela Cruz Santos" has no single
    # correct reading. Collected once here, the TES application reads them off
    # the profile instead of asking again.
    father_last_name = models.CharField(max_length=100, blank=True)
    father_first_name = models.CharField(max_length=100, blank=True)
    father_middle_name = models.CharField(max_length=100, blank=True)
    father_occupation = models.CharField(max_length=200, blank=True)
    mother_last_name = models.CharField(max_length=100, blank=True)
    mother_first_name = models.CharField(max_length=100, blank=True)
    mother_middle_name = models.CharField(max_length=100, blank=True)
    mother_occupation = models.CharField(max_length=200, blank=True)

    @staticmethod
    def _join_name(last, first, middle):
        """'First M. Last' from the parts, skipping whatever is missing."""
        middle_initial = f'{middle.strip()[0].upper()}.' if middle.strip() else ''
        return ' '.join(p for p in (first.strip(), middle_initial, last.strip()) if p)

    @property
    def father_name(self):
        """The father's name as one string, for display and reports."""
        return self._join_name(self.father_last_name, self.father_first_name,
                               self.father_middle_name)

    @property
    def mother_name(self):
        """The mother's name as one string, for display and reports."""
        return self._join_name(self.mother_last_name, self.mother_first_name,
                               self.mother_middle_name)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"


class StaffProfile(PersonalInfo, PhilippineAddress):
    """A BiPSU employee's own record — one row per staff member, kept current.

    The employment details used to live on whichever ``AffirmativeStaffApplication``
    the staff member submitted last, found by email address. That made every
    re-application a second copy and left nothing for the rest of the system to
    read an employee ID off. They live here now, and the application reads from
    this profile.

    Applications still keep their own copies on purpose: an approved award has
    to keep the details it was approved on, so editing this profile never
    rewrites a record the VPSEA office already reviewed.

    ``employee_id`` is not unique at the database level — the records this was
    backfilled from allow blanks and duplicates. The views that write it check
    for a clash first.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff_profile',
        limit_choices_to={'role': 'nsu_staff'},
    )
    employee_id = models.CharField(max_length=50, blank=True, db_index=True,
                                   help_text='School / employee ID, e.g. 32-1-213313')

    # Employment
    school = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    employment_status = models.CharField(max_length=30, choices=EMPLOYMENT_STATUSES, blank=True)
    designation = models.CharField(max_length=30, choices=DESIGNATIONS, blank=True)
    date_hired = models.DateField(null=True, blank=True)
    date_of_regularization = models.DateField(null=True, blank=True)
    declared_years_of_service = models.IntegerField(
        null=True, blank=True,
        help_text='Only read when date_hired is blank — see the years_of_service property.',
    )
    appointment_paper = models.FileField(upload_to='staff/appointment/', null=True, blank=True)

    # Study background, for the staff scholarship
    highest_education = models.CharField(max_length=200, blank=True)
    has_baccalaureate = models.BooleanField(default=False)

    # A separated employee keeps their record for the archives; only the flag changes.
    is_active = models.BooleanField(default=True)
    separated_on = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id or 'no ID'})"

    @property
    def years_of_service(self):
        """Whole years since ``date_hired``, computed — a stored count goes stale.

        Falls back to ``declared_years_of_service`` for the records where the
        hiring date was never captured, which is most of the backfilled ones.
        """
        if not self.date_hired:
            return self.declared_years_of_service
        today = date.today()
        started = self.date_hired
        return today.year - started.year - (
            (today.month, today.day) < (started.month, started.day)
        )

    @property
    def is_regular(self):
        """The whole eligibility bar for the BiPSU Staff Scholarship — see
        :meth:`AffirmativeStaffApplication.is_regular_staff`, which decides the
        same question for an applicant who is a dependent rather than staff."""
        return self.employment_status == 'Regular'


class Scholarship(models.Model):
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50)
    category = models.CharField(max_length=20, choices=SCHOLARSHIP_CATEGORIES)
    group = models.CharField(max_length=20, choices=SCHOLARSHIP_GROUPS, default='internal')
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
    """One scholarship award, whatever route produced it.

    Not only "a student applied". This is the ledger every approved award lands
    in — portal submissions, approved link requests, approved TES applications,
    approved renewals, office imports — and the masterlist, the office
    dashboards and the archive screens all read it. That is why the term an
    award belongs to is a column here rather than a key inside ``form_data``:
    student-submitted rows never wrote that key at all, so every semester-scoped
    office query silently excluded them.

    ``term_label`` is the '<yy>-<sem>' key SystemSettings and ImportedScholar are
    keyed on; ``school_year`` and ``semester`` are the expanded form the office
    reads. ``save()`` keeps the three in step, so a caller sets whichever it has.
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='applications')
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=30, choices=APPLICATION_STATUSES, default='Pending Validation')
    remarks = models.TextField(blank=True)

    # ── Term.
    term_label = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Active term as '<yy>-<sem>', e.g. '26-1'.")
    school_year = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Expanded school year, e.g. '2026-2027'.")
    semester = models.CharField(max_length=20, choices=SEMESTERS, blank=True)

    # ── Provenance and reporting columns, also promoted out of form_data.
    source = models.CharField(max_length=20, choices=APPLICATION_SOURCES,
                              default='portal', db_index=True)
    award_number = models.CharField(max_length=50, blank=True)
    congress_district = models.CharField(max_length=100, blank=True)

    # ── What this award was created from. Both of these were integers inside
    # form_data, so a deleted source row left behind an id nothing could detect.
    claimed_archive = models.ForeignKey(
        'ImportedScholar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='claiming_applications',
    )
    tes_application = models.ForeignKey(
        'TESApplication', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='awards',
    )
    # The link request behind an award is reachable in reverse through
    # ScholarshipLinkRequest.linked_application — no second copy is kept here.

    # What the applicant actually typed. Everything the system queries on has a
    # column above; this is the free-form remainder.
    form_data = models.JSONField(default=dict, blank=True)

    submitted_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['term_label', 'status']),
            models.Index(fields=['scholarship', 'status']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'scholarship', 'school_year', 'semester'],
                name='one_award_per_student_scholarship_term',
            ),
        ]

    def save(self, *args, **kwargs):
        """Fill in whatever term the caller did not set, and never store a CSRF token.

        The office views know the '<yy>-<sem>' label; the student apply form
        knows neither. Rather than leave the blank that used to hide an
        application from every office filter, an unset term falls back to the
        active one in SystemSettings.
        """
        if not self.term_label and not self.school_year:
            active = SystemSettings.objects.filter(pk=1).values_list('academic_year', flat=True).first()
            if active:
                self.term_label = active
        if self.term_label and not self.school_year:
            parsed = SystemSettings.parse_label(self.term_label)
            self.school_year = parsed['sy']
            self.semester = self.semester or parsed['semester']
        elif self.school_year and not self.term_label:
            # The office paths set the expanded term because that is what
            # parse_label hands them. Derive the short key so the indexed
            # column the dashboards filter on is never left blank.
            self.term_label = SystemSettings.make_label(self.school_year, self.semester)
        if isinstance(self.form_data, dict):
            self.form_data.pop('csrfmiddlewaretoken', None)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.student_id} — {self.scholarship.name}"


class ApplicationDocument(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'{self.name} — {self.application_id}'


class Notification(models.Model):
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='info')
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']          # already the order every caller asks for
        indexes = [models.Index(fields=['student', 'is_read'])]

    def __str__(self):
        return self.title


class Announcement(models.Model):
    title = models.CharField(max_length=200)
    body = models.TextField()
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ImportedScholar(PhilippineAddress):
    """A scholar row imported from an office's Excel list.

    Flat by design: programmes without a portal (DOST, CHED, CoScho, GSIS…)
    reach the system only as spreadsheets the VPSEA office uploads. Named for
    what it is rather than the screen it appears on — most rows describe the
    current term, not an archive.

    ``gender`` deliberately has no choices: it is copied verbatim from the
    agency's own column, which uses F/M where the rest of the system uses
    Male/Female. The exports derive the letter either way.
    """
    scholarship_type = models.CharField(max_length=20, choices=SCHOLARSHIP_TYPE_CHOICES)
    term_label = models.CharField(max_length=20, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    middle_name = models.CharField(max_length=100, blank=True)
    gender = models.CharField(max_length=10, blank=True)
    course = models.CharField(max_length=100, blank=True)
    year_level = models.IntegerField(default=0)
    gwa = models.FloatField(default=0.0)
    student_id = models.CharField(max_length=50, blank=True)
    award_number = models.CharField(max_length=50, blank=True)
    congress_district = models.CharField(max_length=100, blank=True)
    imported_from = models.CharField(max_length=100, blank=True)
    # Set when a student account claims this imported row through an approved
    # ScholarshipLinkRequest. Claimed rows are hidden from the archive tables so
    # the Application created on approval is the only entry for that scholar.
    claimed_by = models.ForeignKey(
        StudentProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='claimed_archive_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name']   # every archive query already asks for this
        indexes = [
            models.Index(fields=['scholarship_type', 'term_label', 'claimed_by']),
        ]

    @property
    def full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def __str__(self):
        return f'{self.full_name} — {self.scholarship_type}'


class AffirmativeStaffApplication(PhilippineAddress):
    """Affirmative Action / BiPSU Staff application.

    Applied for outside the student portal, so it carries its own copy of the
    applicant's details.

    Neither programme is scored here. BiPSU Staff has no merit test — see
    ``is_regular_staff``. Affirmative Action eligibility is decided from the
    student's own profile by :meth:`AffirmativeRecommendation.evaluate_and_sync`,
    which reads the SHS GPA, SUC exam score and TES status the student entered
    in My Profile; this model only records the resulting application.
    """
    # Personal
    full_name = models.CharField(max_length=200)
    # Not unique. The constraint served the public apply portal, which no longer
    # has a route: it made staff registration fail with IntegrityError once an
    # application already used the address, and forced the archive-add view to
    # fabricate one in a dedupe loop for records that have no email at all.
    email = models.EmailField(blank=True)
    contact_number = models.CharField(max_length=20)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDERS, blank=True)
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100)
    year_level = models.IntegerField(default=1)
    student_id = models.CharField(max_length=30, blank=True)

    # BiPSU Staff eligibility. staff_* fields describe the sponsoring staff member
    # when the applicant is a dependent, not the applicant themselves.
    is_nsu_staff = models.BooleanField(default=False)
    is_nsu_dependent = models.BooleanField(default=False)
    staff_name = models.CharField(max_length=200, blank=True)
    staff_employee_id = models.CharField(max_length=50, blank=True)
    relationship_to_staff = models.CharField(max_length=50, blank=True)
    has_baccalaureate = models.BooleanField(default=False)

    # Employment details, filled from the NSU staff portal
    employment_status = models.CharField(max_length=30, choices=EMPLOYMENT_STATUSES, blank=True)
    designation = models.CharField(max_length=30, choices=DESIGNATIONS, blank=True)
    department = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    years_of_service = models.IntegerField(null=True, blank=True)
    date_of_regularization = models.DateField(null=True, blank=True)
    appointment_paper = models.FileField(upload_to='staff/appointment/', null=True, blank=True)

    # Affirmative eligibility
    shs_gpa = models.FloatField(null=True, blank=True)
    shs_certificate = models.FileField(upload_to='affirmative/shs/', null=True, blank=True)
    suc_exam_score = models.FloatField(null=True, blank=True)
    suc_exam_certificate = models.FileField(upload_to='affirmative/suc/', null=True, blank=True)
    is_tes_beneficiary = models.BooleanField(default=False)

    # Result
    qualified_for = models.CharField(max_length=20, choices=QUALIFICATION_CHOICES, default='None')
    status = models.CharField(max_length=30, choices=APPLICATION_STATUSES, default='Pending Validation')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.full_name} — {self.qualified_for}"

    @property
    def name_parts(self):
        """(last, first, middle) split out of the single ``full_name`` field.

        The last token is taken as the surname, the first as the given name and
        anything between as the middle name. A multi-word surname such as
        "Dela Cruz" cannot be recovered this way — the office can correct the
        record if the split lands wrong.
        """
        parts = (self.full_name or '').strip().split()
        if len(parts) >= 3:
            return parts[-1], parts[0], ' '.join(parts[1:-1])
        if len(parts) == 2:
            return parts[-1], parts[0], ''
        return (parts[0] if parts else ''), '', ''

    @property
    def last_name(self):
        return self.name_parts[0]

    @property
    def first_name(self):
        return self.name_parts[1]

    @property
    def middle_name(self):
        return self.name_parts[2]

    @property
    def middle_initial(self):
        middle = self.middle_name
        return f'{middle[0].upper()}.' if middle else ''

    @property
    def is_regular_staff(self):
        """The only bar for the BiPSU Staff Scholarship: a regular appointment.

        A permanent employee qualifies by applying, as does the dependent of
        one. Nothing is scored — there is no merit test for this programme.
        """
        if self.is_nsu_staff:
            return self.employment_status == 'Regular'
        if self.is_nsu_dependent:
            return bool(self.staff_employee_id)
        return False


class AcademicRenewal(models.Model):
    """A continuing academic scholar's per-semester renewal submission."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='academic_renewals')
    certificate_of_grades = models.FileField(upload_to='renewals/academic/')
    certificate_of_enrollment = models.FileField(upload_to='renewals/academic/')
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']        # parity with StaffRenewal

    def __str__(self):
        return f"{self.student} — Renewal ({self.status})"


class StaffRenewal(models.Model):
    """BiPSU Staff scholarship renewal submission."""
    staff_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='staff_renewals',
        limit_choices_to={'role': 'nsu_staff'},
    )
    supporting_document = models.FileField(upload_to='renewals/staff/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.staff_user.get_full_name()} — Staff Renewal ({self.status})"


class ScholarshipLinkRequest(models.Model):
    """A student connecting a scholarship they already hold to their account.

    Approving one creates the Approved Application for the semester and claims
    the matching imported ImportedScholar, so the scholar is counted once.
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='link_requests')
    scholarship_type = models.CharField(max_length=50, choices=SCHOLARSHIP_TYPE_CHOICES)
    proof_document = models.FileField(upload_to='link_requests/')
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    # Semester this link applies to — the same '<yy>-<sem>' label used by
    # SystemSettings.academic_year and ImportedScholar.term_label. Named
    # school_year until now, which it never held: the value is a term.
    term_label = models.CharField(max_length=20, blank=True)
    award_number = models.CharField(max_length=50, blank=True)
    # Which CHED tier the award is. Blank for every other programme — only CHED
    # is reported in two blocks, so only CHED asks. Copied onto the Application
    # as form_data['scholar_type'] when the request is approved, which is what
    # the masterlists read.
    award_tier = models.CharField(max_length=10, choices=CHED_TIER_CHOICES, blank=True)

    # Review trail
    remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_link_requests',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    matched_archive = models.ForeignKey(
        ImportedScholar, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='link_requests',
    )
    linked_application = models.ForeignKey(
        Application, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )

    def __str__(self):
        return f"{self.student} — Link {self.scholarship_type} ({self.status})"


class ScholarListImport(models.Model):
    """The uploaded sheet for one programme and term, kept for re-download.

    Named for the artefact rather than the ceremony: this is the spreadsheet an
    officer uploaded, not the act of rolling a semester over. ``school_year``
    and ``semester`` are the readable form the download list shows;
    ``term_label`` is the key every query matches on.
    """
    scholarship_type = models.CharField(max_length=20, choices=SCHOLARSHIP_TYPE_CHOICES)
    school_year = models.CharField(max_length=20)
    semester = models.CharField(max_length=20, choices=SEMESTERS, default='1st Semester')
    term_label = models.CharField(max_length=20, blank=True)
    scholar_count = models.IntegerField(default=0)
    excel_file = models.FileField(upload_to='rollovers/')
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='scholar_imports')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return (f'{self.scholarship_type} — {self.term_label or self.school_year} '
                f'{self.semester} ({self.scholar_count} scholars)')


class TESApplication(models.Model):
    """Tertiary Education Subsidy application, reviewed by the UniFAST office."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='tes_applications')

    # Personal. The student's middle name and both parents' names are not
    # repeated here — they are on StudentProfile, and the apply form fills
    # itself in from there. Two copies of a name only ever disagree.
    lrn = models.CharField(max_length=30, blank=True)
    birthdate = models.DateField(null=True, blank=True)
    complete_program = models.CharField(max_length=200, blank=True)

    # Address as CHED's form asks for it — finer-grained than PhilippineAddress,
    # and submitted by the student rather than copied from their profile.
    street_barangay = models.CharField(max_length=200, blank=True)
    city_municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=10, blank=True)
    contact_number = models.CharField(max_length=20, blank=True)
    email_address = models.EmailField(blank=True)

    # Priority groups
    disability_type = models.CharField(max_length=100, blank=True)
    is_solo_parent_dependent = models.BooleanField(default=False)
    is_first_gen_college = models.BooleanField(default=False)
    indigenous_people_group = models.CharField(max_length=100, blank=True)

    award_number = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['status'])]
        constraints = [
            # student_apply_tes has always refused a second application; this is
            # the same rule, enforced where it cannot be bypassed.
            models.UniqueConstraint(fields=['student'], name='one_tes_application_per_student'),
        ]

    def __str__(self):
        return f"{self.student} — TES ({self.status})"


class AffirmativeRecommendation(models.Model):
    """A student the system flags as fitting the Affirmative Action program."""
    student = models.OneToOneField(
        StudentProfile, on_delete=models.CASCADE,
        related_name='affirmative_recommendation',
    )
    # Snapshot of the values when the recommendation was generated, so historical
    # records stay consistent even if the profile changes later.
    shs_gpa_snapshot = models.FloatField()
    suc_exam_score_snapshot = models.FloatField()
    shs_gpa_passing = models.FloatField(default=75.0)
    fit_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=RECOMMENDATION_STATUSES, default='Recommended')
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-fit_score', 'student__user__last_name']

    def __str__(self):
        return f"{self.student} — {self.status} ({self.fit_score}%)"

    @staticmethod
    def compute_fit_score(shs_gpa, suc_exam_score):
        """Weighted: 50 pts from GPA (out of 100), 50 pts from exam (out of 100)."""
        score = 0.0
        if shs_gpa is not None:
            score += min((shs_gpa / 100.0) * 50.0, 50.0)
        if suc_exam_score is not None:
            score += min((suc_exam_score / 100.0) * 50.0, 50.0)
        return round(score, 2)

    @classmethod
    def evaluate_and_sync(cls, passing_threshold=75.0):
        """Re-evaluate every student against the three eligibility rules.

        Creates a recommendation when all rules pass, disqualifies one when they
        stop passing. Returns ``(created_count, disqualified_count)``.
        """
        created = disqualified = 0
        for profile in StudentProfile.objects.all():
            gpa, exam = profile.shs_gpa, profile.suc_exam_score
            passes = (
                gpa is not None and gpa >= passing_threshold and
                exam is not None and exam >= 50.0 and
                not profile.is_tes_beneficiary
            )
            rec = cls.objects.filter(student=profile).first()

            if rec is None:
                if passes:
                    cls.objects.create(
                        student=profile,
                        shs_gpa_snapshot=gpa,
                        suc_exam_score_snapshot=exam,
                        shs_gpa_passing=passing_threshold,
                        fit_score=cls.compute_fit_score(gpa, exam),
                    )
                    created += 1
                continue

            if passes:
                rec.shs_gpa_snapshot = gpa
                rec.suc_exam_score_snapshot = exam
                rec.shs_gpa_passing = passing_threshold
                rec.fit_score = cls.compute_fit_score(gpa, exam)
                if rec.status == 'Disqualified':
                    rec.status = 'Recommended'
                rec.save()
            elif rec.status != 'Disqualified':
                rec.status = 'Disqualified'
                rec.shs_gpa_snapshot = gpa or rec.shs_gpa_snapshot
                rec.suc_exam_score_snapshot = exam or rec.suc_exam_score_snapshot
                rec.fit_score = cls.compute_fit_score(gpa, exam)
                rec.save()
                disqualified += 1
        return created, disqualified


class ActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.action[:80]


class SystemSettings(models.Model):
    """Single-row settings table (pk=1). ``academic_year`` is a '<yy>-<sem>'
    label such as '26-1', which every semester-scoped record is keyed against."""
    # The default has to be in the '<yy>-<sem>' form parse_label expects. It was
    # '2025-2026', which parsed to school year 4025-4026, 2nd Semester on every
    # fresh install.
    academic_year = models.CharField(
        max_length=20, default='26-1',
        help_text="Active term as '<yy>-<sem>', e.g. '26-1'. Must parse — see parse_label.",
    )
    active_semester = models.CharField(max_length=20, default='1st Semester')
    email_notifications = models.BooleanField(default=True)
    sms_alerts = models.BooleanField(default=False)
    inapp_push = models.BooleanField(default=True)
    max_file_size_mb = models.IntegerField(default=5)
    allowed_formats = models.CharField(max_length=50, default='PDF, JPG, PNG')
    show_match_scores = models.BooleanField(default=True)

    class Meta:
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f'SY {self.academic_year} — {self.active_semester}'

    @staticmethod
    def parse_label(label):
        try:
            yy, sem = label.split('-')
            start = 2000 + int(yy)
            return {
                'sy': f'{start}-{start + 1}',
                'semester': '1st Semester' if sem == '1' else '2nd Semester',
                'sy_start': start,
                'sy_end': start + 1,
            }
        except Exception:
            return {'sy': label, 'semester': '1st Semester', 'sy_start': None, 'sy_end': None}

    @staticmethod
    def make_label(school_year, semester):
        """The inverse of parse_label: '2026-2027' + '1st Semester' -> '26-1'.

        Callers that know the expanded term (the link, renewal and TES approval
        paths all derive it from parse_label) get the short key back, so every
        Application lands with all three term fields agreeing.
        """
        try:
            start = int(str(school_year).split('-')[0])
        except (ValueError, IndexError, AttributeError):
            return ''
        return f"{start - 2000}-{'1' if semester == '1st Semester' else '2'}"

    def next_label(self):
        yy, sem = self.academic_year.split('-')
        return f'{yy}-2' if sem == '1' else f'{int(yy) + 1}-1'


# ── CHED tiers ──────────────────────────────────────────────────────────────

def ched_tier(app):
    """'Full', 'Half' or '' for one approved CHED application.

    Three signals, most trustworthy first: the tier the student declared on
    their link request and the office confirmed, which is copied onto the award
    as ``form_data['scholar_type']``; then the programme name, for awards
    created before the field existed or imported under a tier-specific name;
    then nothing, for rows no one has ever classified.
    """
    declared = ((app.form_data or {}).get('scholar_type') or '').lower()
    name = (app.scholarship.name or '').lower() if app.scholarship_id else ''
    for text in (declared, name):
        if 'full' in text:
            return 'Full'
        if 'half' in text or 'partial' in text:
            return 'Half'
    return ''


def split_ched(apps):
    """Split approved CHED applications into the (full, half) report blocks.

    Every masterlist prints CHED as two tables, so an unclassified row still has
    to land in one of them. It goes to half — where this code has always put
    anything not named 'full' — rather than silently disappearing from the
    report.
    """
    apps = list(apps)
    full = [a for a in apps if ched_tier(a) == 'Full']
    return full, [a for a in apps if a not in full]
