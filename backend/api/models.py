"""Every model in the system.

Three shapes are worth knowing before reading further.

**Two record types, deliberately distinct.** :class:`Application` is a student
applying through the portal for a catalogue programme. :class:`ApplicantRecord`
is a person in a programme the office administers directly — Affirmative
Action, the Staff Scholarship, or anything arriving by spreadsheet — and
carries its own name and email because most of those people never had an
account. Merging them is what produced phantom student records in earlier
versions.

**Detail rows.** The profiles spread their fields across satellite tables
reached through :class:`DetailField`, which reads and writes like a local
attribute. It is a Python property, not a model field, so it cannot be used in
a queryset — filter through the relation instead. This is the easiest mistake
to make in this codebase.

**Terms.** Anything happening in a semester inherits :class:`TermStamped`. Any
query deciding whether someone may act *now* must filter on the term; one that
matches on identity alone keeps finding last semester's row.
"""

from datetime import date

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ObjectDoesNotExist
from django.db import models

from .validators import validate_document, validate_spreadsheet
from .constants import (
    APPLICATION_SOURCES, APPLICATION_STATUSES, BIPSU_COURSES, BIPSU_SCHOOLS,
    BIPSU_STAFF_UNITS,
    CHED_TIER_CHOICES, CIVIL_STATUSES,
    GENDERS,
    DEFAULT_APPROVAL_MESSAGE, VERIFICATION_STATUSES,
    DESIGNATIONS, EMPLOYMENT_STATUSES, NOTIFICATION_TYPES,
    QUALIFICATION_CHOICES, RECOMMENDATION_STATUSES, REVIEW_STATUSES,
    SCHOLARSHIP_CATEGORIES, SCHOLARSHIP_GROUPS, SCHOLARSHIP_LOGO_DEFAULT,
    SCHOLARSHIP_LOGOS, SCHOLARSHIP_TYPE_CHOICES,
    SEMESTERS, STUDENT_LEVELS, USER_ROLES,
    school_for_course,
)

__all__ = [
    'BIPSU_COURSES', 'BIPSU_SCHOOLS', 'BIPSU_STAFF_UNITS',
    'CHED_TIER_CHOICES', 'SCHOLARSHIP_TYPE_CHOICES',
    'ched_tier', 'split_ched', 'states_a_disability', 'suc_exam_percent',
    'AcademicRenewal', 'ActivityLog', 'AffirmativeEligibility',
    'AffirmativeRecommendation', 'Announcement',
    'ApplicantAffirmativeEligibility', 'ApplicantEmployment',
    'ApplicantEnrollment', 'ApplicantInformation', 'ApplicantRecord',
    'ApplicantStaffEligibility',
    'Application', 'ApplicationDocument', 'EducationalBackground',
    'EnrollmentData', 'FamilyBackground', 'ImportedScholar', 'Notification',
    'PersonalInformation', 'Scholarship', 'ScholarListImport',
    'ScholarshipLinkRequest', 'SocioEconomicProfile', 'STAFF_APPLICATION_DETAILS',
    'StaffEducation', 'StaffEmployment', 'StaffPersonalInformation',
    'StaffProfile', 'StaffRenewal', 'StaffScholarshipDeclaration',
    'STUDENT_DETAILS', 'StudentProfile',
    'SystemSettings', 'TESEligibility', 'TermStamped', 'User',
]


class PhilippineAddress(models.Model):
    """Barangay, municipality and province, shared by several models."""
    barangay = models.CharField(max_length=100, blank=True)
    municipality = models.CharField(max_length=100, blank=True)
    province = models.CharField(max_length=100, blank=True)

    class Meta:
        abstract = True

    @property
    def address(self):
        """The address as one line, skipping blanks."""
        parts = [p for p in [self.barangay, self.municipality, self.province] if p]
        return ', '.join(parts)


NO_DISABILITY = frozenset({'', 'n/a', 'na', 'n.a.', 'none', 'no', 'not applicable',
                           'wala', '-', '--', 'nil'})


def states_a_disability(value):
    """Whether this answer claims a disability.

    "NO" is a real answer and must not read as one. The recommender has to
    tell declining apart from never being asked.
    """
    return (value or '').strip().casefold() not in NO_DISABILITY


def middle_initial_of(middle_name):
    """A middle initial with its full stop, or ''."""
    name = (middle_name or '').strip()
    return f'{name[0].upper()}.' if name else ''


def format_full_name(last, first, middle_name='', suffix=''):
    """Last, First M. — the order the reports print."""
    last = (last or '').strip()
    first = (first or '').strip()
    suffix = (suffix or '').strip()
    if last and suffix:
        last = f'{last} {suffix}'
    initial = middle_initial_of(middle_name)
    given = f'{first} {initial}'.strip() if initial else first
    if last and given:
        return f'{last}, {given}'
    return last or given


class PersonalInfo(models.Model):
    """Personal details shared by student and staff profiles."""
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
        """The middle initial with its full stop, or ''."""
        return middle_initial_of(self.middle_name)


class TermStamped(models.Model):
    """Base for anything that happens in one semester.

    **Any query deciding whether someone may act now must filter on the
    term.** A lookup matching on identity alone keeps finding last
    semester's row — the cause of employees being told they had already
    applied when they had not.
    """
    term_label = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Term as '<yy>-<sem>', e.g. '26-1'.")
    school_year = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Expanded school year, e.g. '2026-2027'.")
    semester = models.CharField(max_length=20, choices=SEMESTERS, blank=True)

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Stamp the term, then save."""
        self.fill_term()
        super().save(*args, **kwargs)

    def fill_term(self):
        """Stamp a new row with the active term if it carries none."""
        if not self.term_label and not self.school_year:
            active = SystemSettings.objects.filter(pk=1).values_list(
                'academic_year', flat=True).first()
            if active:
                self.term_label = active
        if self.term_label and not self.school_year:
            parsed = SystemSettings.parse_label(self.term_label)
            self.school_year = parsed['sy']
            self.semester = self.semester or parsed['semester']
        elif self.school_year and not self.term_label:
            self.term_label = SystemSettings.make_label(self.school_year, self.semester)

    @property
    def term_display(self):
        """The term as "2026-2027 — 1st Semester"."""
        both = f'{self.school_year} {self.semester}'.strip()
        return both or self.term_label


class User(AbstractUser):
    """An account. One model for students, employees, the office and partners.

    ``role`` decides which portal they land in and what they may reach.
    Verification is separate from ``is_active``: a new registration is real
    but cannot sign in until the office has looked at it.
    """
    role = models.CharField(max_length=20, choices=USER_ROLES, default='student')
    email = models.EmailField(unique=True)

    verification_status = models.CharField(
        max_length=10, choices=VERIFICATION_STATUSES, default='approved', db_index=True,
    )
    verification_note = models.TextField(blank=True)
    verified_by = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='verified_accounts',
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    partner_office = models.ForeignKey(
        'PartnerOffice', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='accounts')

    email_verified = models.BooleanField(default=True)
    email_confirmation_sent_at = models.DateTimeField(null=True, blank=True)

    terms_version = models.CharField(max_length=20, blank=True)
    terms_accepted_at = models.DateTimeField(null=True, blank=True)

    photo = models.ImageField(
        upload_to='profile/photos/', null=True, blank=True,
        help_text='Square headshot, any common image format.')

    mfa_secret = models.CharField(max_length=64, blank=True, editable=False)
    mfa_enabled = models.BooleanField(
        default=False,
        help_text='Whether this account is asked for an authenticator code.')
    mfa_confirmed_at = models.DateTimeField(null=True, blank=True)
    mfa_recovery_codes = models.JSONField(default=list, blank=True, editable=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    @property
    def mfa_required(self):
        """Whether this account's role is one the university requires MFA of.

        Answered from the role rather than from the account, so adding a
        second office account cannot quietly create one without it.
        """
        from django.conf import settings

        return self.role in getattr(settings, 'MFA_REQUIRED_ROLES', ())

    @property
    def mfa_outstanding(self):
        """Whether this account owes the university an MFA enrolment."""
        return self.mfa_required and not self.mfa_enabled

    def begin_mfa_enrolment(self):
        """Issue a secret this account can be enrolled against.

        Not turned on here: the secret is worthless until a code generated
        from it has been checked, and enabling it first would lock out an
        account whose authenticator never actually got set up.
        """
        from . import mfa

        self.mfa_secret = mfa.new_secret()
        self.mfa_enabled = False
        self.mfa_confirmed_at = None
        self.save(update_fields=['mfa_secret', 'mfa_enabled', 'mfa_confirmed_at'])
        return self.mfa_secret

    def confirm_mfa(self, submitted):
        """Turn MFA on once a code from the new secret checks out.

        Returns:
            The recovery codes, in the clear and for the only time, or
            ``None`` where the submitted code did not match.
        """
        from django.utils import timezone

        from . import mfa

        if not self.mfa_secret or not mfa.verify(self.mfa_secret, submitted):
            return None
        codes = mfa.new_recovery_codes()
        self.mfa_enabled = True
        self.mfa_confirmed_at = timezone.now()
        self.mfa_recovery_codes = [mfa.hash_recovery_code(c) for c in codes]
        self.save(update_fields=['mfa_enabled', 'mfa_confirmed_at',
                                 'mfa_recovery_codes'])
        return codes

    def disable_mfa(self):
        """Drop the second factor and everything that belonged to it."""
        self.mfa_secret = ''
        self.mfa_enabled = False
        self.mfa_confirmed_at = None
        self.mfa_recovery_codes = []
        self.save(update_fields=['mfa_secret', 'mfa_enabled',
                                 'mfa_confirmed_at', 'mfa_recovery_codes'])

    def check_mfa(self, submitted):
        """Whether a submitted authenticator or recovery code lets this account in.

        A recovery code is spent as it is accepted, so the list shortens by
        one each time one is used.
        """
        from . import mfa

        if not self.mfa_enabled:
            return True
        if mfa.verify(self.mfa_secret, submitted):
            return True
        matched, remaining = mfa.spend_recovery_code(
            self.mfa_recovery_codes, submitted)
        if matched:
            self.mfa_recovery_codes = remaining
            self.save(update_fields=['mfa_recovery_codes'])
        return matched

    @property
    def awaiting_verification(self):
        """Whether the office has still to decide on this account."""
        return self.verification_status == 'pending'

    @property
    def awaiting_email_confirmation(self):
        """Whether the address has still to be confirmed."""
        return not self.email_verified and self.email_confirmation_sent_at is not None

    @property
    def accepted_terms(self):
        """Whether this account accepted the current terms."""
        return bool(self.terms_version and self.terms_accepted_at)

    def mark_email_verified(self):
        """Record that the address was confirmed."""
        if self.email_verified:
            return False
        self.email_verified = True
        self.save(update_fields=['email_verified'])
        return True

    @property
    def can_sign_in(self):
        """Whether this account may sign in yet."""
        return self.is_active and self.verification_status == 'approved'

    @property
    def initials(self):
        """Initials for the avatar, falling back to the address."""
        first = (self.first_name or '').strip()[:1].upper()
        last = (self.last_name or '').strip()[:1].upper()
        return (first + last) or (self.email[:1].upper())

    @property
    def photo_url(self):
        """The profile photo URL, or ''."""
        if self.photo:
            return self.photo.url
        return ''

    def decide_verification(self, status, note, reviewer):
        """Record the office's decision, who made it and when."""
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


class DetailField(property):
    """A field that lives on a satellite table but reads like a local one.

    ``profile.gwa`` reads and writes ``profile.enrollment.gwa``, creating the
    row on first write.

    **It is a Python property, not a model field.** ``filter(gwa=...)`` raises
    ``FieldError``; filter through the relation — ``enrollment__gwa`` —
    instead. This is the easiest mistake to make in this codebase.
    """
    def __init__(self, related, field):
        self.related = related
        self.field = field
        super().__init__(self._read, self._write)

    def __set_name__(self, owner, name):
        """Register this field in the owner's ``DETAIL_FIELDS`` map."""
        owner.DETAIL_FIELDS[name] = (self.related, self.field)

    def _read(self, profile):
        """Read through to the detail row, or the field default."""
        row = profile.detail(self.related)
        if row is not None:
            return getattr(row, self.field)
        model = profile._meta.get_field(self.related).related_model
        return model._meta.get_field(self.field).get_default()

    def _write(self, profile, value):
        """Write through to the detail row, creating it if needed."""
        setattr(profile.detail(self.related, create=True), self.field, value)


class DetailRows(models.Model):
    """Base for a model whose fields are spread over satellite tables.

    The profiles carry a hundred-odd fields each, most of them read rarely.
    Splitting them keeps the main row narrow and lets a list query skip the
    columns it does not need, while :class:`DetailField` hides the split from
    everything that just wants a value.
    """
    DETAIL_FIELDS = {}
    DETAIL_RELATIONS = ()
    DETAIL_LINK = ''

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        """Save this row and any detail rows that were touched."""
        creating = self._state.adding
        update_fields = kwargs.pop('update_fields', None)
        detail_fields = None
        if update_fields is not None:
            own, detail_fields = [], {}
            for name in update_fields:
                moved = self.DETAIL_FIELDS.get(name)
                if moved is None:
                    own.append(name)
                else:
                    detail_fields.setdefault(moved[0], []).append(moved[1])
            if own or not detail_fields:
                super().save(*args, update_fields=own, **kwargs)
        else:
            super().save(*args, **kwargs)
        self.save_details(detail_fields)
        if creating:
            self.ensure_details()

    @property
    def _detail_cache(self):
        """Per-instance cache of loaded detail rows."""
        return self.__dict__.setdefault('_detail_rows', {})

    def detail(self, related, create=False):
        """Get one detail row, optionally creating it in memory.

        A created row is not saved here — it is written by :meth:`save`, so a
        read that touches a missing row does not write to the database.
        """
        cache = self._detail_cache
        if related not in cache:
            row = None
            if self.pk:
                try:
                    row = getattr(self, related)
                except ObjectDoesNotExist:
                    row = None
            cache[related] = row
        if cache[related] is None and create:
            cache[related] = self._meta.get_field(related).related_model()
        return cache[related]

    def save_details(self, only=None):
        """Save the loaded detail rows, optionally a named subset."""
        for related, row in self._detail_cache.items():
            if row is None or (only is not None and related not in only):
                continue
            setattr(row, self.DETAIL_LINK, self)
            fields = only.get(related) if only else None
            row.save(update_fields=fields if (fields and row.pk) else None)

    def ensure_details(self):
        """Create every detail row, so later writes have somewhere to go."""
        for related in self.DETAIL_RELATIONS:
            row = self.detail(related, create=True)
            if row.pk is None:
                setattr(row, self.DETAIL_LINK, self)
                row.save()

    def refresh_from_db(self, *args, **kwargs):
        """Reload, discarding cached detail rows so they are re-read."""
        self.__dict__.pop('_detail_rows', None)
        super().refresh_from_db(*args, **kwargs)

    @classmethod
    def with_details(cls, queryset=None):
        """A queryset that fetches every detail row in one go.

        Without it, reading a detail field on each of a hundred profiles is a
        hundred extra queries.
        """
        queryset = cls.objects.all() if queryset is None else queryset
        return queryset.select_related(*cls.DETAIL_RELATIONS)


class StudentProfile(PhilippineAddress, DetailRows, TermStamped):
    """A student, their enrolment, background and eligibility answers."""
    DETAIL_RELATIONS = (
        'enrollment', 'personal', 'affirmative_eligibility', 'socioeconomic',
        'tes_eligibility', 'education', 'family',
    )
    DETAIL_LINK = 'student'
    DETAIL_FIELDS = {}

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    student_id = models.CharField(max_length=20, unique=True)

    school = DetailField('enrollment', 'school')
    course = DetailField('enrollment', 'course')
    level = DetailField('enrollment', 'level')
    department = DetailField('enrollment', 'department')
    curriculum = DetailField('enrollment', 'curriculum')
    year_level = DetailField('enrollment', 'year_level')
    learner_ref_no = DetailField('enrollment', 'learner_ref_no')
    entry_period = DetailField('enrollment', 'entry_period')
    entry_date = DetailField('enrollment', 'entry_date')
    exam_score = DetailField('enrollment', 'exam_score')
    gwa = DetailField('enrollment', 'gwa')
    study_load = DetailField('enrollment', 'study_load')

    middle_name = DetailField('personal', 'middle_name')
    suffix = DetailField('personal', 'suffix')
    date_of_birth = DetailField('personal', 'date_of_birth')
    birth_place = DetailField('personal', 'birth_place')
    gender = DetailField('personal', 'gender')
    civil_status = DetailField('personal', 'civil_status')
    contact_number = DetailField('personal', 'contact_number')
    disability_type = DetailField('personal', 'disability_type')

    shs_gpa = DetailField('affirmative_eligibility', 'shs_gpa')
    shs_gpa_cert = DetailField('affirmative_eligibility', 'shs_gpa_cert')
    suc_exam_score = DetailField('affirmative_eligibility', 'suc_exam_score')
    suc_exam_total = DetailField('affirmative_eligibility', 'suc_exam_total')
    suc_exam_cert = DetailField('affirmative_eligibility', 'suc_exam_cert')
    is_tes_beneficiary = DetailField('affirmative_eligibility', 'is_tes_beneficiary')

    family_income = DetailField('socioeconomic', 'family_income')
    household_size = DetailField('socioeconomic', 'household_size')
    indigenous_group = DetailField('socioeconomic', 'indigenous_group')
    is_from_depressed_area = DetailField('socioeconomic', 'is_from_depressed_area')
    parent_employment = DetailField('socioeconomic', 'parent_employment')

    citizenship = DetailField('tes_eligibility', 'citizenship')
    is_listahanan_household = DetailField('tes_eligibility', 'is_listahanan_household')
    is_4ps_beneficiary = DetailField('tes_eligibility', 'is_4ps_beneficiary')
    has_previous_degree = DetailField('tes_eligibility', 'has_previous_degree')
    year_first_enrolled = DetailField('tes_eligibility', 'year_first_enrolled')
    is_solo_parent_dependent = DetailField('tes_eligibility', 'is_solo_parent_dependent')

    elementary = DetailField('education', 'elementary')
    highschool = DetailField('education', 'highschool')
    highschool_is_public = DetailField('education', 'highschool_is_public')
    last_school = DetailField('education', 'last_school')

    father_last_name = DetailField('family', 'father_last_name')
    father_first_name = DetailField('family', 'father_first_name')
    father_middle_name = DetailField('family', 'father_middle_name')
    father_occupation = DetailField('family', 'father_occupation')
    mother_last_name = DetailField('family', 'mother_last_name')
    mother_first_name = DetailField('family', 'mother_first_name')
    mother_middle_name = DetailField('family', 'mother_middle_name')
    mother_occupation = DetailField('family', 'mother_occupation')

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"

    @property
    def is_pwd(self):
        """Whether the disability answer claims a disability."""
        return states_a_disability(self.disability_type)

    @property
    def middle_initial(self):
        """The student's middle initial."""
        return middle_initial_of(self.middle_name)

    @property
    def full_name(self):
        """The student's full name."""
        return format_full_name(self.user.last_name, self.user.first_name,
                                self.middle_name, self.suffix)

    @property
    def suc_exam_percent(self):
        """The entrance exam score as a percentage."""
        return suc_exam_percent(self.suc_exam_score, self.suc_exam_total)

    @property
    def suc_exam_display(self):
        """The entrance exam score as a readable string."""
        return format_exam_score(self.suc_exam_score, self.suc_exam_total)

    @property
    def father_name(self):
        """The father's name, assembled from its parts."""
        return join_parent_name(self.father_last_name, self.father_first_name,
                                self.father_middle_name)

    @property
    def mother_name(self):
        """The mother's name, assembled from its parts."""
        return join_parent_name(self.mother_last_name, self.mother_first_name,
                                self.mother_middle_name)


STUDENT_DETAILS = tuple(f'student__{name}' for name in StudentProfile.DETAIL_RELATIONS)


class StudentDetail(models.Model):
    """Base for a satellite table hanging off a student profile."""
    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.student.student_id} — {self._meta.verbose_name}'


class EnrollmentData(StudentDetail):
    """The student's enrolment, and their proof of it."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='enrollment')
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100, blank=True)
    level = models.CharField(max_length=20, choices=STUDENT_LEVELS, blank=True,
                             help_text='Undergraduate, Graduate …')
    department = models.CharField(max_length=200, blank=True)
    curriculum = models.CharField(max_length=100, blank=True,
                                  help_text='Curriculum year the student is following, e.g. 2018-2019.')
    year_level = models.IntegerField(default=1)
    learner_ref_no = models.CharField(
        max_length=30, blank=True, db_index=True,
        help_text="DepEd Learner Reference Number (LRN), the student's ID from basic education.")
    entry_period = models.CharField(
        max_length=20, choices=SEMESTERS, blank=True,
        help_text='Semester the student first entered BiPSU.')
    entry_date = models.DateField(null=True, blank=True,
                                  help_text='Date of first entry, as the registrar recorded it.')
    exam_score = models.FloatField(
        null=True, blank=True,
        help_text=('Admission exam score on the registrar\'s record. The score a '
                   'scholarship is judged on is the certified one the student '
                   'submits — see AffirmativeEligibility.suc_exam_score.'))
    gwa = models.FloatField(default=0.0)
    study_load = models.FileField(
        upload_to='profile/study_load/', null=True, blank=True,
        validators=validate_document,
        help_text=("Certificate of registration or study load for the current "
                   "term. The office checks it to confirm the applicant is a "
                   "bonafide, currently enrolled student — a student number "
                   "alone survives a student leaving."))

    class Meta:
        verbose_name = 'enrollment data'
        verbose_name_plural = 'enrollment data'


class PersonalInformation(PersonalInfo, StudentDetail):
    """A student's personal details."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='personal')
    birth_place = models.CharField(max_length=200, blank=True)
    disability_type = models.CharField(
        max_length=100, blank=True,
        help_text="A value from CHED's Disability_List, or 'NO' for none.")

    class Meta:
        verbose_name = 'personal information'
        verbose_name_plural = 'personal information'


class AffirmativeEligibility(StudentDetail):
    """Grades and exam scores for the Affirmative Action rules."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='affirmative_eligibility')
    shs_gpa = models.FloatField(null=True, blank=True)
    shs_gpa_cert = models.FileField(upload_to='profile/shs_cert/', null=True, blank=True,
                                    validators=validate_document)
    suc_exam_score = models.FloatField(
        null=True, blank=True,
        help_text='Raw score. A percentage when suc_exam_total is blank.')
    suc_exam_total = models.FloatField(
        null=True, blank=True,
        help_text='Items the exam was out of. Blank means the score is already a percentage.')
    suc_exam_cert = models.FileField(upload_to='profile/suc_cert/', null=True, blank=True,
                                     validators=validate_document)
    is_tes_beneficiary = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'affirmative eligibility'
        verbose_name_plural = 'affirmative eligibility'

    @property
    def suc_exam_percent(self):
        """The entrance exam score as a percentage."""
        return suc_exam_percent(self.suc_exam_score, self.suc_exam_total)

    @property
    def suc_exam_display(self):
        """The entrance exam score as a readable string."""
        return format_exam_score(self.suc_exam_score, self.suc_exam_total)


class SocioEconomicProfile(StudentDetail):
    """Household income and the programmes it is listed under."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='socioeconomic')
    family_income = models.FloatField(default=0.0)
    household_size = models.IntegerField(null=True, blank=True)
    indigenous_group = models.CharField(max_length=100, blank=True)
    is_from_depressed_area = models.BooleanField(
        null=True, blank=True,
        help_text='Declared to live in a depressed area, for the office to verify. '
                  'Null means not yet asked.')
    parent_employment = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = 'socio-economic profile'
        verbose_name_plural = 'socio-economic profiles'


class TESEligibility(StudentDetail):
    """The answers the TES rules read."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='tes_eligibility')
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
    is_solo_parent_dependent = models.BooleanField(
        null=True, blank=True,
        help_text='Dependent of a solo parent on the DSWD registry. Null means not yet asked.')

    class Meta:
        verbose_name = 'TES eligibility'
        verbose_name_plural = 'TES eligibility'


class EducationalBackground(StudentDetail):
    """Schools this student attended before BiPSU."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='education')
    elementary = models.CharField(max_length=200, blank=True)
    highschool = models.CharField(max_length=200, blank=True)
    highschool_is_public = models.BooleanField(
        null=True, blank=True,
        help_text='Was the high school above a public school? Null means not yet asked.')
    last_school = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'educational background'
        verbose_name_plural = 'educational backgrounds'


class FamilyBackground(StudentDetail):
    """The student's parents and household."""
    student = models.OneToOneField(StudentProfile, on_delete=models.CASCADE,
                                   related_name='family')
    father_last_name = models.CharField(max_length=100, blank=True)
    father_first_name = models.CharField(max_length=100, blank=True)
    father_middle_name = models.CharField(max_length=100, blank=True)
    father_occupation = models.CharField(max_length=200, blank=True)
    mother_last_name = models.CharField(max_length=100, blank=True)
    mother_first_name = models.CharField(max_length=100, blank=True)
    mother_middle_name = models.CharField(max_length=100, blank=True)
    mother_occupation = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = 'family background'
        verbose_name_plural = 'family backgrounds'

    @property
    def father_name(self):
        """The father's name, assembled from its parts."""
        return join_parent_name(self.father_last_name, self.father_first_name,
                                self.father_middle_name)

    @property
    def mother_name(self):
        """The mother's name, assembled from its parts."""
        return join_parent_name(self.mother_last_name, self.mother_first_name,
                                self.mother_middle_name)


class StaffProfile(PhilippineAddress, DetailRows):
    """An employee, their appointment and their qualifications."""
    DETAIL_RELATIONS = ('employment', 'personal', 'education')
    DETAIL_LINK = 'staff'
    DETAIL_FIELDS = {}

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='staff_profile',
        limit_choices_to={'role': 'nsu_staff'},
    )
    employee_id = models.CharField(max_length=50, blank=True, db_index=True,
                                   help_text='School / employee ID, e.g. 32-1-213313')

    school = DetailField('employment', 'school')
    department = DetailField('employment', 'department')
    position = DetailField('employment', 'position')
    employment_status = DetailField('employment', 'employment_status')
    designation = DetailField('employment', 'designation')
    date_hired = DetailField('employment', 'date_hired')
    date_of_regularization = DetailField('employment', 'date_of_regularization')
    declared_years_of_service = DetailField('employment', 'declared_years_of_service')
    appointment_paper = DetailField('employment', 'appointment_paper')
    is_active = DetailField('employment', 'is_active')
    separated_on = DetailField('employment', 'separated_on')

    middle_name = DetailField('personal', 'middle_name')
    suffix = DetailField('personal', 'suffix')
    date_of_birth = DetailField('personal', 'date_of_birth')
    gender = DetailField('personal', 'gender')
    civil_status = DetailField('personal', 'civil_status')
    contact_number = DetailField('personal', 'contact_number')

    highest_education = DetailField('education', 'highest_education')
    has_baccalaureate = DetailField('education', 'has_baccalaureate')
    course = DetailField('education', 'course')
    year_level = DetailField('education', 'year_level')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['user__last_name', 'user__first_name']

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.employee_id or 'no ID'})"

    @property
    def middle_initial(self):
        """The employee's middle initial."""
        return middle_initial_of(self.middle_name)

    @property
    def full_name(self):
        """The employee's full name."""
        return format_full_name(self.user.last_name, self.user.first_name,
                                self.middle_name, self.suffix)

    @property
    def years_of_service(self):
        """Years of service, measured or declared.

        Measured from the date of regularisation where there is one, because a
        declared figure goes stale the moment it is typed.
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
        """Whether the appointment is a permanent one."""
        return self.employment_status == 'Regular'


class StaffDetail(models.Model):
    """Base for a satellite table hanging off a staff profile."""
    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.staff.employee_id or self.staff_id} — {self._meta.verbose_name}'


class StaffEmployment(StaffDetail):
    """An employee's appointment."""
    staff = models.OneToOneField(StaffProfile, on_delete=models.CASCADE,
                                 related_name='employment')
    school = models.CharField(max_length=100, blank=True)
    department = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    employment_status = models.CharField(max_length=30, choices=EMPLOYMENT_STATUSES, blank=True)
    designation = models.CharField(max_length=30, choices=DESIGNATIONS, blank=True)
    date_hired = models.DateField(null=True, blank=True)
    date_of_regularization = models.DateField(null=True, blank=True)
    declared_years_of_service = models.IntegerField(
        null=True, blank=True,
        help_text='Only read when date_hired is blank — see StaffProfile.years_of_service.',
    )
    appointment_paper = models.FileField(upload_to='staff/appointment/', null=True, blank=True, validators=validate_document)
    is_active = models.BooleanField(default=True)
    separated_on = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = 'staff employment'
        verbose_name_plural = 'staff employment'


class StaffPersonalInformation(PersonalInfo, StaffDetail):
    """An employee's personal details."""
    staff = models.OneToOneField(StaffProfile, on_delete=models.CASCADE,
                                 related_name='personal')

    class Meta:
        verbose_name = 'staff personal information'
        verbose_name_plural = 'staff personal information'


class StaffEducation(StaffDetail):
    """An employee's qualifications."""
    staff = models.OneToOneField(StaffProfile, on_delete=models.CASCADE,
                                 related_name='education')
    highest_education = models.CharField(max_length=200, blank=True)
    has_baccalaureate = models.BooleanField(default=False)
    course = models.CharField(max_length=100, blank=True,
                              help_text='The programme the employee is enrolled in as a scholar.')
    year_level = models.IntegerField(default=1)

    class Meta:
        verbose_name = 'staff education'
        verbose_name_plural = 'staff education'


class Scholarship(models.Model):
    """One programme in the catalogue.

    ``category`` says whether it is applied for here or only recorded;
    ``group`` says who funds it. Externally funded programmes are applied for
    through the agency, and the API refuses an application to one.
    """
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=50, db_index=True)
    category = models.CharField(max_length=20, choices=SCHOLARSHIP_CATEGORIES)
    group = models.CharField(max_length=20, choices=SCHOLARSHIP_GROUPS, default='internal')
    description = models.TextField()
    eligibility = models.TextField()
    background = models.TextField(blank=True)
    eligibility_list = models.JSONField(default=list, blank=True)
    benefits = models.JSONField(default=list, blank=True)
    requirements = models.JSONField(default=list)
    is_active = models.BooleanField(default=True)

    logo = models.CharField(
        max_length=100, blank=True,
        help_text="Seal filename from media/logos/, e.g. 'CHED.png'. "
                  'Blank uses the default for this programme type.')

    accepting_applications = models.BooleanField(
        default=True,
        help_text='Off closes applications now, whatever the window below says.')
    applications_open_on = models.DateField(
        null=True, blank=True,
        help_text='First day students may apply. Blank leaves the programme always open.')
    applications_open_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='How many days it stays open, counting the first. Blank means no closing date.')

    accepting_renewals = models.BooleanField(
        default=True,
        help_text='Off closes renewals now, whatever the window below says.')
    renewals_open_on = models.DateField(
        null=True, blank=True,
        help_text='First day scholars may renew. Blank leaves renewals always open.')
    renewals_open_days = models.PositiveIntegerField(
        null=True, blank=True,
        help_text='How many days renewals stay open, counting the first.')

    updated_at = models.DateTimeField(auto_now=True)

    table_columns = models.JSONField(
        default=list, blank=True,
        help_text='Column keys from api/scholar_columns.COLUMNS. Empty means the default set.')
    extra_columns = models.JSONField(
        default=list, blank=True,
        help_text="Columns the office added, as [{'key', 'label'}].")

    def __str__(self):
        return self.name

    @property
    def logo_url(self):
        """The programme's seal, or the university's."""
        return '/media/logos/' + (
            self.logo
            or SCHOLARSHIP_LOGOS.get(self.type, SCHOLARSHIP_LOGO_DEFAULT))

    @staticmethod
    def _window_end(opens, days):
        """The last day of a window that opens on a date and runs N days."""
        from datetime import timedelta
        if not opens or not days:
            return None
        return opens + timedelta(days=days - 1)

    @staticmethod
    def _window_open(enabled, opens, days, day):
        """Whether a window is open on a given day.

        A window with no opening date is open whenever it is enabled — the office
        often runs one with no fixed dates at all.
        """
        if not enabled:
            return False
        if not opens:
            return True
        if day < opens:
            return False
        closes = Scholarship._window_end(opens, days)
        return closes is None or day <= closes

    @staticmethod
    def _window_reason(noun, enabled, opens, days, day):
        """Why a window is shut, phrased for the reader.

        Returns '' when it is open. Three different closures — switched off, not
        yet open, already past — read as three different sentences, because
        "closed" alone leaves the applicant nothing to do.
        """
        if Scholarship._window_open(enabled, opens, days, day):
            return ''
        if not enabled:
            return f'{noun} are closed.'
        if day < opens:
            return f'{noun} open on {opens.strftime("%B %d, %Y")}.'
        closed = Scholarship._window_end(opens, days)
        return f'{noun} closed on {closed.strftime("%B %d, %Y")}.'

    @property
    def applications_close_on(self):
        """The last day applications are accepted."""
        return self._window_end(self.applications_open_on,
                                self.applications_open_days)

    def accepts_applications_on(self, day):
        """Whether applications are open on a day."""
        return self._window_open(self.accepting_applications,
                                 self.applications_open_on,
                                 self.applications_open_days, day)

    def window_closed_reason(self, day):
        """Why applications are closed, or ''."""
        return self._window_reason(
            f'Applications for the {self.name}', self.accepting_applications,
            self.applications_open_on, self.applications_open_days, day)

    @property
    def renewals_close_on(self):
        """The last day renewals are accepted."""
        return self._window_end(self.renewals_open_on, self.renewals_open_days)

    def accepts_renewals_on(self, day):
        """Whether renewals are open on a day."""
        return self._window_open(self.accepting_renewals, self.renewals_open_on,
                                 self.renewals_open_days, day)

    def renewal_closed_reason(self, day):
        """Why renewals are closed, or ''."""
        return self._window_reason(
            f'Renewals for the {self.name}', self.accepting_renewals,
            self.renewals_open_on, self.renewals_open_days, day)

    def match_score(self, profile):
        """A rough fit between a programme and a student.

        Orders the catalogue so the likeliest programmes surface first. Not an
        eligibility verdict — those come from the recommender modules, which give
        reasons.
        """
        if not profile:
            return 0
        score = 50
        if self.type == 'Academic' and profile.gwa <= 1.50:
            score += 30 if profile.gwa <= 1.29 else 15
        if self.type == 'TDP' and profile.family_income < 60000:
            score += 30
        return min(score, 100)


class Application(TermStamped):
    """A student applying, through the portal, for a catalogue programme."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='applications')
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE, related_name='applications')
    status = models.CharField(max_length=30, choices=APPLICATION_STATUSES, default='Pending Validation')
    remarks = models.TextField(blank=True)

    source = models.CharField(max_length=20, choices=APPLICATION_SOURCES,
                              default='portal', db_index=True)
    award_number = models.CharField(max_length=50, blank=True)
    congress_district = models.CharField(max_length=100, blank=True)

    claimed_archive = models.ForeignKey(
        'ImportedScholar', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='claiming_applications',
    )

    form_data = models.JSONField(default=dict, blank=True)

    submitted_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_applications',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

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
            models.UniqueConstraint(
                fields=['scholarship', 'school_year', 'semester', 'award_number'],
                condition=~models.Q(award_number=''),
                name='one_award_number_per_programme_term',
            ),
        ]

    def __str__(self):
        return f"{self.student.student_id} — {self.scholarship.name}"

    def save(self, *args, **kwargs):
        """Stamp the term, then save."""
        if isinstance(self.form_data, dict):
            self.form_data.pop('csrfmiddlewaretoken', None)
        super().save(*args, **kwargs)

    def conflicts_with(self):
        """Other approved awards this one duplicates a benefit with.

        Reported, never refused. A student who really does hold two national
        grants is the problem this system exists to surface, and a database
        that would not store the second one could not show the office the
        first thing about it. The office is warned before it approves and can
        find every case afterwards with ``manage.py find_duplicate_awards``.
        """
        from .constants import ALWAYS_HOLDABLE_TYPES, CONFLICTING_BENEFIT_TYPES

        if self.status != 'Approved' or not self.scholarship_id:
            return Application.objects.none()
        if self.scholarship.type not in CONFLICTING_BENEFIT_TYPES:
            return Application.objects.none()
        return (Application.objects
                .filter(student_id=self.student_id, status='Approved',
                        school_year=self.school_year, semester=self.semester,
                        scholarship__type__in=CONFLICTING_BENEFIT_TYPES)
                .exclude(pk=self.pk)
                .exclude(scholarship__type__in=ALWAYS_HOLDABLE_TYPES)
                .select_related('scholarship'))


class ApplicationDocument(models.Model):
    """A file attached to an application."""
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='documents')
    name = models.CharField(max_length=100)
    file = models.FileField(upload_to='documents/', validators=validate_document)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['uploaded_at']

    def __str__(self):
        return f'{self.name} — {self.application_id}'


class Notification(models.Model):
    """One message to one person, shown in their portal."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES, default='info')
    title = models.CharField(max_length=200)
    body = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['student', 'is_read'])]

    def __str__(self):
        return self.title


class Announcement(models.Model):
    """A notice from the office to everyone."""
    title = models.CharField(max_length=200)
    body = models.TextField()
    published_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                     related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


SIGNUP_KINDS = (
    ('alert', 'Scholarship alerts'),
    ('registration', 'Registration'),
)


class SignupSource(models.Model):
    """Where a registration came from, for the office to read."""
    email = models.EmailField()
    kind = models.CharField(max_length=20, choices=SIGNUP_KINDS, default='alert')
    is_active = models.BooleanField(default=True)

    utm_source = models.CharField(max_length=120, blank=True)
    utm_medium = models.CharField(max_length=120, blank=True)
    utm_campaign = models.CharField(max_length=120, blank=True)
    utm_term = models.CharField(max_length=120, blank=True)
    utm_content = models.CharField(max_length=120, blank=True)
    referrer = models.CharField(max_length=200, blank=True)
    landed_on = models.CharField(max_length=200, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = ('email', 'kind')

    def __str__(self):
        return f'{self.email} ({self.get_kind_display()})'

    @property
    def campaign_label(self):
        """The campaign in a phrase, or where they came from."""
        parts = [self.utm_source, self.utm_medium, self.utm_campaign]
        return ' / '.join(p for p in parts if p) or 'direct'

    @classmethod
    def record(cls, email, kind, payload):
        """Record how one address reached the register form.

        Keyed by address, so a person who arrives twice is one row. Never raises
        — losing a campaign attribution must not cost someone their account.
        """
        email = (email or '').strip().lower()
        if not email:
            return None
        data = payload if isinstance(payload, dict) else {}
        fields = {
            name: str(data.get(name) or '')[:120]
            for name in ('utm_source', 'utm_medium', 'utm_campaign',
                         'utm_term', 'utm_content')
        }
        fields['referrer'] = str(data.get('referrer') or '')[:200]
        fields['landed_on'] = str(data.get('landed_on') or '')[:200]
        fields['is_active'] = True
        row, created = cls.objects.get_or_create(
            email=email, kind=kind, defaults=fields)
        if not created:
            changed = ['is_active']
            row.is_active = True
            for name, value in fields.items():
                if name == 'is_active':
                    continue
                if value and getattr(row, name) != value:
                    setattr(row, name, value)
                    changed.append(name)
            row.save(update_fields=changed + ['updated_at'])
        return row


class ImportedScholar(PhilippineAddress):
    """One scholar from a funder's spreadsheet.

    ``claimed_by`` links the row to a portal account once someone declares
    it, so the same person is not counted twice.

    Award numbers are not unique here, deliberately. This table is a copy of
    a document the office did not write, and a copy that refuses the rows it
    was given cannot show anyone that the document repeats itself.
    ``manage.py find_duplicate_awards`` reports the repeats instead.
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
    award_tier = models.CharField(max_length=10, choices=CHED_TIER_CHOICES, blank=True)
    extra_data = models.JSONField(default=dict, blank=True)
    claimed_by = models.ForeignKey(
        StudentProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='claimed_archive_records',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['last_name', 'first_name']
        indexes = [
            models.Index(fields=['scholarship_type', 'term_label', 'claimed_by']),
        ]

    def __str__(self):
        return f'{self.full_name} — {self.scholarship_type}'

    @property
    def full_name(self):
        """The scholar's full name, assembled from its parts."""
        return f'{self.first_name} {self.last_name}'.strip()


class ApplicantRecord(PhilippineAddress, DetailRows, TermStamped):
    """A person in a programme the office administers directly.

    Affirmative Action, the Staff Scholarship, and anything arriving by
    spreadsheet. Carries its own name and email rather than requiring a
    portal account, because most of these people never had one.

    Kept separate from :class:`Application` because an imported scholar has
    no account, no profile and no application, and inventing them is what
    produced phantom student records in earlier versions.
    """
    DETAIL_RELATIONS = (
        'applicant', 'enrollment', 'staff_eligibility', 'employment',
        'affirmative_eligibility',
    )
    DETAIL_LINK = 'application'
    DETAIL_FIELDS = {}

    full_name = models.CharField(max_length=200)
    email = models.EmailField(blank=True)

    contact_number = DetailField('applicant', 'contact_number')
    date_of_birth = DetailField('applicant', 'date_of_birth')
    gender = DetailField('applicant', 'gender')

    school = DetailField('enrollment', 'school')
    course = DetailField('enrollment', 'course')
    year_level = DetailField('enrollment', 'year_level')
    student_id = DetailField('enrollment', 'student_id')

    is_nsu_staff = DetailField('staff_eligibility', 'is_nsu_staff')
    is_nsu_dependent = DetailField('staff_eligibility', 'is_nsu_dependent')
    staff_name = DetailField('staff_eligibility', 'staff_name')
    staff_employee_id = DetailField('staff_eligibility', 'staff_employee_id')
    relationship_to_staff = DetailField('staff_eligibility', 'relationship_to_staff')
    has_baccalaureate = DetailField('staff_eligibility', 'has_baccalaureate')

    employment_status = DetailField('employment', 'employment_status')
    designation = DetailField('employment', 'designation')
    department = DetailField('employment', 'department')
    position = DetailField('employment', 'position')
    years_of_service = DetailField('employment', 'years_of_service')
    date_of_regularization = DetailField('employment', 'date_of_regularization')
    appointment_paper = DetailField('employment', 'appointment_paper')

    shs_gpa = DetailField('affirmative_eligibility', 'shs_gpa')
    shs_certificate = DetailField('affirmative_eligibility', 'shs_certificate')
    suc_exam_score = DetailField('affirmative_eligibility', 'suc_exam_score')
    suc_exam_total = DetailField('affirmative_eligibility', 'suc_exam_total')
    suc_exam_certificate = DetailField('affirmative_eligibility', 'suc_exam_certificate')
    is_tes_beneficiary = DetailField('affirmative_eligibility', 'is_tes_beneficiary')

    extra_data = models.JSONField(default=dict, blank=True)

    qualified_for = models.CharField(max_length=20, choices=QUALIFICATION_CHOICES, default='None', db_index=True)
    status = models.CharField(max_length=30, choices=APPLICATION_STATUSES, default='Pending Validation', db_index=True)
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_applicant_records',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.full_name} — {self.qualified_for}"

    @property
    def suc_exam_percent(self):
        """The entrance exam score as a percentage."""
        return suc_exam_percent(self.suc_exam_score, self.suc_exam_total)

    @property
    def suc_exam_display(self):
        """The entrance exam score as a readable string."""
        return format_exam_score(self.suc_exam_score, self.suc_exam_total)

    @property
    def name_parts(self):
        """Last, first and middle, split out of the full name."""
        parts = (self.full_name or '').strip().split()
        if len(parts) >= 3:
            return parts[-1], parts[0], ' '.join(parts[1:-1])
        if len(parts) == 2:
            return parts[-1], parts[0], ''
        return (parts[0] if parts else ''), '', ''

    @property
    def last_name(self):
        """Surname, split out of the full name."""
        return self.name_parts[0]

    @property
    def first_name(self):
        """First name, split out of the full name."""
        return self.name_parts[1]

    @property
    def middle_name(self):
        """Middle name, split out of the full name."""
        return self.name_parts[2]

    @property
    def middle_initial(self):
        """Middle initial, split out of the full name."""
        return middle_initial_of(self.middle_name)

    @property
    def course_school(self):
        """The school this record's course belongs to."""
        return self.school or school_for_course(self.course)

    @property
    def is_regular_staff(self):
        """Whether the appointment behind this record is permanent.

        For an employee, their own appointment. For a dependent, the fact that
        an employee was named at all — the appointment itself is checked against
        the staff record by the recommender.
        """
        if self.is_nsu_staff:
            return self.employment_status == 'Regular'
        if self.is_nsu_dependent:
            return bool(self.staff_employee_id)
        return False


STAFF_APPLICATION_DETAILS = ApplicantRecord.DETAIL_RELATIONS


class StaffApplicationDetail(models.Model):
    """Base for a satellite table hanging off an applicant record."""
    class Meta:
        abstract = True

    def __str__(self):
        return f'{self.application.full_name} — {self._meta.verbose_name}'


class ApplicantInformation(StaffApplicationDetail):
    """Contact details for an applicant record."""
    application = models.OneToOneField(ApplicantRecord, on_delete=models.CASCADE,
                                       related_name='applicant')
    contact_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=GENDERS, blank=True)

    class Meta:
        verbose_name = 'applicant information'
        verbose_name_plural = 'applicant information'


class ApplicantEnrollment(StaffApplicationDetail):
    """Enrolment details for an applicant record."""
    application = models.OneToOneField(ApplicantRecord, on_delete=models.CASCADE,
                                       related_name='enrollment')
    school = models.CharField(max_length=100, blank=True)
    course = models.CharField(max_length=100, blank=True)
    year_level = models.IntegerField(default=1)
    student_id = models.CharField(max_length=30, blank=True)

    class Meta:
        verbose_name = 'applicant enrollment'
        verbose_name_plural = 'applicant enrollment'


class ApplicantStaffEligibility(StaffApplicationDetail):
    """Whether an applicant record is an employee or a dependent."""
    application = models.OneToOneField(ApplicantRecord, on_delete=models.CASCADE,
                                       related_name='staff_eligibility')
    is_nsu_staff = models.BooleanField(default=False)
    is_nsu_dependent = models.BooleanField(default=False)
    staff_name = models.CharField(max_length=200, blank=True)
    staff_employee_id = models.CharField(max_length=50, blank=True)
    relationship_to_staff = models.CharField(max_length=50, blank=True)
    has_baccalaureate = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'applicant staff eligibility'
        verbose_name_plural = 'applicant staff eligibility'


class ApplicantEmployment(StaffApplicationDetail):
    """Appointment details for an employee applicant."""
    application = models.OneToOneField(ApplicantRecord, on_delete=models.CASCADE,
                                       related_name='employment')
    employment_status = models.CharField(max_length=30, choices=EMPLOYMENT_STATUSES, blank=True)
    designation = models.CharField(max_length=30, choices=DESIGNATIONS, blank=True)
    department = models.CharField(max_length=200, blank=True)
    position = models.CharField(max_length=200, blank=True)
    years_of_service = models.IntegerField(null=True, blank=True)
    date_of_regularization = models.DateField(null=True, blank=True)
    appointment_paper = models.FileField(upload_to='staff/appointment/', null=True, blank=True, validators=validate_document)

    class Meta:
        verbose_name = 'applicant employment'
        verbose_name_plural = 'applicant employment'


class ApplicantAffirmativeEligibility(StaffApplicationDetail):
    """Grades and exam scores for an applicant record."""
    application = models.OneToOneField(ApplicantRecord, on_delete=models.CASCADE,
                                       related_name='affirmative_eligibility')
    shs_gpa = models.FloatField(null=True, blank=True)
    shs_certificate = models.FileField(upload_to='affirmative/shs/', null=True, blank=True, validators=validate_document)
    suc_exam_score = models.FloatField(
        null=True, blank=True,
        help_text='Raw score. A percentage when suc_exam_total is blank.')
    suc_exam_total = models.FloatField(
        null=True, blank=True,
        help_text='Items the exam was out of. Blank means the score is already a percentage.')
    suc_exam_certificate = models.FileField(upload_to='affirmative/suc/', null=True, blank=True, validators=validate_document)
    is_tes_beneficiary = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'applicant affirmative eligibility'
        verbose_name_plural = 'applicant affirmative eligibility'


class AcademicRenewal(TermStamped):
    """A renewal submission for an academic scholarship."""
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='academic_renewals')
    scholarship_type = models.CharField(
        max_length=50, choices=SCHOLARSHIP_TYPE_CHOICES, default='Academic',
        help_text='Which programme this submission renews.')
    certificate_of_grades = models.FileField(upload_to='renewals/academic/', validators=validate_document)
    certificate_of_enrollment = models.FileField(upload_to='renewals/academic/', validators=validate_document)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_academic_renewals',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']
        indexes = [models.Index(fields=['status', 'term_label'])]

    def __str__(self):
        return f"{self.student} — Renewal {self.term_label} ({self.status})"


class StaffRenewal(TermStamped):
    """A renewal submission for a staff award."""
    staff_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='staff_renewals',
        limit_choices_to={'role': 'nsu_staff'},
    )
    supporting_document = models.FileField(upload_to='renewals/staff/', null=True, blank=True, validators=validate_document)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    remarks = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return f"{self.staff_user.get_full_name()} — Staff Renewal {self.term_label} ({self.status})"


class ScholarshipLinkRequest(TermStamped):
    """A student declaring an award granted elsewhere.

    ``filed_in_portal`` says which queue reviews it: one filed during
    registration is decided alongside the account, and one filed later goes
    to the declarations queue.
    """
    student = models.ForeignKey(StudentProfile, on_delete=models.CASCADE, related_name='link_requests')
    scholarship_type = models.CharField(max_length=50, choices=SCHOLARSHIP_TYPE_CHOICES)
    proof_document = models.FileField(upload_to='link_requests/', validators=validate_document)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending', db_index=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    award_number = models.CharField(max_length=50, blank=True)
    award_tier = models.CharField(max_length=10, choices=CHED_TIER_CHOICES, blank=True)
    filed_in_portal = models.BooleanField(
        default=False,
        help_text='Declared from the student portal rather than on the '
                  'registration form.')

    staff_name = models.CharField(
        max_length=200, blank=True,
        help_text='Staff Scholarship only: the employee this student depends on.')
    staff_employee_id = models.CharField(
        max_length=50, blank=True,
        help_text="Staff Scholarship only: that employee's number.")
    relationship_to_staff = models.CharField(
        max_length=50, blank=True,
        help_text='Staff Scholarship only: how the student is related to them.')

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
    linked_applicant_record = models.ForeignKey(
        'ApplicantRecord', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='+',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['scholarship_type', 'term_label', 'award_number'],
                condition=models.Q(status='Approved') & ~models.Q(award_number=''),
                name='one_approved_link_award_number_per_term',
            ),
        ]

    def __str__(self):
        return f"{self.student} — Link {self.scholarship_type} ({self.status})"


class StaffScholarshipDeclaration(TermStamped):
    """An employee declaring a staff award granted elsewhere."""
    staff_user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='staff_declarations',
        limit_choices_to={'role': 'nsu_staff'},
    )
    proof_document = models.FileField(
        upload_to='staff_declarations/', validators=validate_document)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=REVIEW_STATUSES, default='Pending')
    submitted_at = models.DateTimeField(auto_now_add=True)

    remarks = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_staff_declarations',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    linked_application = models.ForeignKey(
        'ApplicantRecord', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='+',
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        return (f"{self.staff_user.get_full_name()} — Declared Staff Scholarship "
                f"({self.status})")


class ScholarListImport(TermStamped):
    """One uploaded spreadsheet, and the scholars it created."""
    scholarship_type = models.CharField(max_length=20, choices=SCHOLARSHIP_TYPE_CHOICES)
    scholar_count = models.IntegerField(default=0)
    excel_file = models.FileField(upload_to='rollovers/', validators=validate_spreadsheet)
    imported_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                    related_name='scholar_imports')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['scholarship_type', 'term_label'])]

    def __str__(self):
        return (f'{self.scholarship_type} — {self.term_label or self.school_year} '
                f'{self.semester} ({self.scholar_count} scholars)')


class BackgroundJob(models.Model):
    """One piece of work a request handed to the pool in ``api/jobs.py``.

    The row is written before the job is queued, so it exists even if the
    process dies in between. That ordering is the whole point: the pool lives
    inside the web process and does not survive a restart, and a row still
    marked ``running`` when nothing is running is the only way the office finds
    out that nobody is going to finish it.

    Nothing retries on its own. A job that failed says why, and the office
    decides whether to send the spreadsheet again.
    """

    QUEUED, RUNNING, DONE, FAILED = 'queued', 'running', 'done', 'failed'
    STATUS_CHOICES = [
        (QUEUED, 'Queued'),
        (RUNNING, 'Running'),
        (DONE, 'Done'),
        (FAILED, 'Failed'),
    ]

    kind = models.CharField(max_length=30)
    label = models.CharField(max_length=200)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default=QUEUED)
    detail = models.TextField(blank=True)
    outcome = models.JSONField(default=dict, blank=True)
    started_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                   related_name='background_jobs')
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['kind', 'status'])]

    def __str__(self):
        return f'{self.label} ({self.get_status_display()})'

    @property
    def finished(self):
        """Whether there is an outcome to show."""
        return self.status in (self.DONE, self.FAILED)

    def begin(self):
        """Mark the job as picked up."""
        from django.utils import timezone

        self.status = self.RUNNING
        self.started_at = timezone.now()
        self.save(update_fields=['status', 'started_at'])

    def succeed(self, detail='', **outcome):
        """Record what the job produced."""
        self._settle(self.DONE, detail, outcome)

    def fail(self, detail, **outcome):
        """Record why the job stopped, in words the office can act on."""
        self._settle(self.FAILED, detail, outcome)

    def _settle(self, status, detail, outcome):
        """Write the ending once, so the two endings cannot drift apart."""
        from django.utils import timezone

        self.status = status
        self.detail = detail
        self.outcome = outcome
        self.finished_at = timezone.now()
        self.save(update_fields=['status', 'detail', 'outcome', 'finished_at'])

    def abandoned(self, after_minutes=30):
        """Whether this job was unfinished when the process went away.

        A restart takes the queue with it and leaves the row behind. Nothing
        rewrites that row afterwards, so its age is the only evidence there is.
        """
        from datetime import timedelta

        from django.utils import timezone

        if self.finished:
            return False
        since = self.started_at or self.created_at
        return bool(since and timezone.now() - since >
                    timedelta(minutes=after_minutes))


class PartnerOffice(models.Model):
    """An external office with its own portal and its own scholar lists."""
    name = models.CharField(max_length=120, unique=True)
    logo = models.CharField(
        max_length=100, blank=True,
        help_text="Seal filename from media/logos/. Blank uses BiPSU's.")

    scholarships = models.ManyToManyField(
        'Scholarship', blank=True, related_name='partner_offices',
        help_text='Programmes this partner may see. None means they see nothing.')

    may_add_scholarships = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'partner office'

    def __str__(self):
        return self.name

    @property
    def logo_url(self):
        """The office's seal, or the university's."""
        return '/media/logos/' + (self.logo or SCHOLARSHIP_LOGO_DEFAULT)

    def visible_types(self):
        """The programme types this office may see."""
        return list(self.scholarships.values_list('type', flat=True))


class PartnerTableColumns(models.Model):
    """One office's column choice for one programme."""
    office = models.ForeignKey(
        'PartnerOffice', on_delete=models.CASCADE, related_name='table_columns_set')
    scholarship = models.ForeignKey(
        'Scholarship', on_delete=models.CASCADE, related_name='partner_columns')

    table_columns = models.JSONField(default=list, blank=True)
    extra_columns = models.JSONField(default=list, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'partner table columns'
        verbose_name_plural = 'partner table columns'
        constraints = [
            models.UniqueConstraint(fields=['office', 'scholarship'],
                                    name='one_column_choice_per_partner_programme'),
        ]

    def __str__(self):
        return f'{self.office} — {self.scholarship}'


class AffirmativeRecommendation(models.Model):
    """A stored Affirmative Action fit score for one student."""
    student = models.OneToOneField(
        StudentProfile, on_delete=models.CASCADE,
        related_name='affirmative_recommendation',
    )
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
        """Score this student against the Affirmative criteria."""
        score = 0.0
        if shs_gpa is not None:
            score += min((shs_gpa / 100.0) * 50.0, 50.0)
        if suc_exam_score is not None:
            score += min((suc_exam_score / 100.0) * 50.0, 50.0)
        return round(score, 2)

    @classmethod
    def evaluate_and_sync(cls, passing_threshold=75.0):
        """Recompute every recommendation against a passing mark.

        The threshold is the office's to set, so the scores are recomputed rather
        than trusted: a stored verdict silently belongs to whatever threshold was
        in force when it was written.
        """
        created = disqualified = 0
        profiles = StudentProfile.objects.select_related(
            'affirmative_eligibility', 'affirmative_recommendation')
        for profile in profiles:
            gpa, exam = profile.shs_gpa, profile.suc_exam_percent
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


AUDIT_VERBS = [
    ('approve', 'Approved'),
    ('reject', 'Rejected'),
    ('create', 'Created'),
    ('update', 'Updated'),
    ('delete', 'Deleted'),
    ('import', 'Imported'),
    ('export', 'Exported'),
    ('sign-in', 'Signed in'),
    ('other', 'Other'),
]


class ActivityLog(models.Model):
    """Who did what, when, to which record, and what changed.

    The free-text ``action`` on its own could say that something was approved
    but not which row, nor what the values were beforehand, so it could not
    answer the question an audit actually asks. The structured columns beside
    it can, and they are queryable: every decision on one record, or
    everything one officer did in a week.

    Entries are written through :meth:`record` and never updated or deleted by
    application code.
    """

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.TextField()
    verb = models.CharField(max_length=20, choices=AUDIT_VERBS,
                            default='other', db_index=True)
    target_type = models.CharField(max_length=60, blank=True, db_index=True)
    target_id = models.CharField(max_length=40, blank=True, db_index=True)
    target_label = models.CharField(max_length=200, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['target_type', 'target_id']),
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return self.action[:80]

    @staticmethod
    def identify(target):
        """Snapshot a row's identity so it can still be audited once deleted.

        ``record(target=...)`` reads the primary key off a live instance, and
        Django clears that key during ``delete()``. A deletion therefore has to
        capture the identity first and hand the snapshot over afterwards —
        which is the one case where the audit entry matters most, because the
        row it describes no longer exists to be looked up.
        """
        return {
            'target_type': type(target).__name__,
            'target_id': str(getattr(target, 'pk', '') or ''),
            'target_label': str(target)[:200],
        }

    @classmethod
    def record(cls, user, action, verb='other', target=None, changes=None,
               request=None, identity=None):
        """Write one audit entry.

        Args:
            user: who acted. ``None`` for something the system did alone.
            action: the human-readable summary, as it will be read back.
            verb: one of :data:`AUDIT_VERBS`.
            target: the model instance acted on, if there is one. Its type,
                primary key and ``str()`` are stored, not a reference — the
                entry has to survive the row being deleted, which is exactly
                the case a deletion audit exists for.
            changes: ``{field: [before, after]}``, usually from :meth:`diff`.
            request: the current request, read only for the caller's address.
            identity: a snapshot from :meth:`identify`, for a row that has
                already been deleted. Takes precedence over ``target``.

        Returns:
            The saved ``ActivityLog``.
        """
        address = None
        if request is not None:
            from . import ratelimit
            address = ratelimit.client_address(request)
            if address in ('', 'unknown'):
                address = None

        known = identity or (cls.identify(target) if target is not None else {})

        return cls.objects.create(
            user=user if getattr(user, 'pk', None) else None,
            action=action,
            verb=verb,
            target_type=known.get('target_type', ''),
            target_id=known.get('target_id', ''),
            target_label=known.get('target_label', ''),
            changes=changes or {},
            ip_address=address,
        )

    @staticmethod
    def diff(before, after, fields):
        """Field-level ``{name: [old, new]}`` between two snapshots.

        Both arguments are mappings, not model instances, so a caller can
        capture the old values before a form overwrites them — by then the
        instance holds only the new ones. Fields that did not move are left
        out, so an entry records the change rather than the whole row.
        """
        moved = {}
        for name in fields:
            old = before.get(name)
            new = after.get(name)
            if old != new:
                moved[name] = [
                    None if old is None else str(old),
                    None if new is None else str(new),
                ]
        return moved

    @staticmethod
    def snapshot(instance, fields):
        """Current values of ``fields`` on ``instance``, for :meth:`diff`."""
        return {name: getattr(instance, name, None) for name in fields}


class SystemSettings(models.Model):
    """The single settings row, ``pk=1``.

    Holds the active term, the upload ceiling, and what became of the last
    email — which is the only way anyone finds out whether mail works on a
    deployment with no shell.
    """
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

    last_mail_attempt_at = models.DateTimeField(null=True, blank=True)
    last_mail_to = models.CharField(max_length=254, blank=True)
    last_mail_subject = models.CharField(max_length=200, blank=True)
    last_mail_error = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'System Settings'

    def __str__(self):
        return f'SY {self.academic_year} — {self.active_semester}'

    @staticmethod
    def parse_label(label):
        """Split '26-1' into school year and semester."""
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
        """Build '26-1' from a school year and semester."""
        try:
            start = int(str(school_year).split('-')[0])
        except (ValueError, IndexError, AttributeError):
            return ''
        return f"{start - 2000}-{'1' if semester == '1st Semester' else '2'}"

    def next_label(self):
        """The term after this one."""
        yy, sem = self.academic_year.split('-')
        return f'{yy}-2' if sem == '1' else f'{int(yy) + 1}-1'


def join_parent_name(last, first, middle):
    """A parent name from its parts, skipping the blanks."""
    middle_initial = middle_initial_of(middle)
    return ' '.join(p for p in (first.strip(), middle_initial, last.strip()) if p)


def suc_exam_percent(score, total):
    """An exam score as a percentage, or ``None`` if unusable."""
    if score is None:
        return None
    if total:
        return round(score / total * 100.0, 2)
    return float(score)


def format_exam_score(score, total):
    """An exam score as "score / total (pct%)"."""
    pct = suc_exam_percent(score, total)
    if pct is None:
        return ''
    if total:
        return f'{score:g} / {total:g} ({pct:g}%)'
    return f'{pct:g}%'


def ched_tier(app):
    """Full or Half from however a CHED award was recorded."""
    declared = ((getattr(app, 'form_data', None) or {}).get('scholar_type') or '').lower()
    name = (app.scholarship.name or '').lower() if getattr(app, 'scholarship_id', None) else ''
    for text in (declared, name):
        if 'full' in text:
            return 'Full'
        if 'half' in text or 'partial' in text:
            return 'Half'
    return ''


def split_ched(apps):
    """Split CHED awards into Full Merit and Half Merit.

    They are one programme in the catalogue and two sections on every report,
    so the split happens here rather than in each renderer.
    """
    tiers = [(a, ched_tier(a)) for a in apps]
    return ([a for a, tier in tiers if tier != 'Half'],
            [a for a, tier in tiers if tier == 'Half'])
