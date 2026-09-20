"""Serializers for the REST API.

The profile serializers flatten the satellite detail tables into one object:
the split is a storage decision, not something a client should have to know.
"""

from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    User, StudentProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, AcademicRenewal, ImportedScholar,
    ActivityLog, SystemSettings,
)


class RegisterSerializer(serializers.ModelSerializer):
    """Create an account from the API.

    The web form is the main route; this exists so a client can register
    without scraping the page. Both end in the same place: an account the
    SDSO still has to verify.
    """
    password = serializers.CharField(write_only=True)
    student_id = serializers.CharField()
    course = serializers.CharField()
    year_level = serializers.IntegerField()
    gwa = serializers.FloatField()
    contact_number = serializers.CharField(required=False, allow_blank=True)
    barangay = serializers.CharField(required=False, allow_blank=True)
    municipality = serializers.CharField(required=False, allow_blank=True)
    province = serializers.CharField(required=False, allow_blank=True)
    middle_name = serializers.CharField(required=False, allow_blank=True)
    suffix = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    family_income = serializers.FloatField(required=False, default=0.0)
    indigenous_group = serializers.CharField(required=False, allow_blank=True)
    parent_employment = serializers.CharField(required=False, allow_blank=True)
    disability_type = serializers.CharField(required=False, allow_blank=True)
    highschool_is_public = serializers.BooleanField(required=False, allow_null=True)
    is_from_depressed_area = serializers.BooleanField(required=False, allow_null=True)
    accept_terms = serializers.BooleanField(required=False, default=False,
                                            write_only=True)

    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name',
            'student_id', 'course', 'year_level', 'gwa',
            'contact_number', 'barangay', 'municipality', 'province',
            'middle_name', 'suffix',
            'date_of_birth', 'gender',
            'family_income', 'indigenous_group', 'parent_employment',
            'disability_type', 'highschool_is_public', 'is_from_depressed_area',
            'accept_terms',
        ]

    def create(self, validated_data):
        """Create the account and its profile together."""
        profile_fields = [
            'student_id', 'course', 'year_level', 'gwa', 'contact_number',
            'barangay', 'municipality', 'province',
            'middle_name', 'suffix', 'date_of_birth', 'gender', 'family_income',
            'indigenous_group', 'parent_employment', 'disability_type',
            'highschool_is_public', 'is_from_depressed_area',
        ]
        profile_data = {f: validated_data.pop(f, None) for f in profile_fields}
        password = validated_data.pop('password')
        if validated_data.pop('accept_terms', False):
            from django.utils import timezone

            from . import terms
            validated_data['terms_version'] = terms.VERSION
            validated_data['terms_accepted_at'] = timezone.now()
        validated_data['username'] = validated_data['email']
        validated_data['verification_status'] = 'pending'
        validated_data['email_verified'] = False
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        StudentProfile.objects.create(user=user, **{k: v for k, v in profile_data.items() if v is not None})
        return user


class LoginSerializer(serializers.Serializer):
    """Check credentials and hand back the authenticated user."""
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        """Authenticate, refusing without saying which half was wrong.

        One message for an unknown address and for a wrong password, for the
        same reason the web form does it: the difference would let anyone test
        an address and learn whether it belongs to a scholar.
        """
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    """An account, as the API represents it."""
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role']


class StudentProfileSerializer(serializers.ModelSerializer):
    """A student profile, flattened across its detail tables.

    The model spreads its fields over several one-to-one tables; the API
    presents one object, because the split is a storage decision and not
    something a client should have to know.
    """
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar = serializers.SerializerMethodField()

    school = serializers.CharField(required=False, allow_blank=True)
    course = serializers.CharField(required=False, allow_blank=True)
    level = serializers.CharField(required=False, allow_blank=True)
    department = serializers.CharField(required=False, allow_blank=True)
    curriculum = serializers.CharField(required=False, allow_blank=True)
    year_level = serializers.IntegerField(required=False)
    learner_ref_no = serializers.CharField(required=False, allow_blank=True)
    entry_period = serializers.CharField(required=False, allow_blank=True)
    entry_date = serializers.DateField(required=False, allow_null=True)
    exam_score = serializers.FloatField(required=False, allow_null=True)
    gwa = serializers.FloatField(required=False)

    middle_name = serializers.CharField(required=False, allow_blank=True)
    suffix = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    birth_place = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    civil_status = serializers.CharField(required=False, allow_blank=True)
    contact_number = serializers.CharField(required=False, allow_blank=True)
    disability_type = serializers.CharField(required=False, allow_blank=True)

    shs_gpa = serializers.FloatField(required=False, allow_null=True)
    suc_exam_score = serializers.FloatField(required=False, allow_null=True)
    suc_exam_total = serializers.FloatField(required=False, allow_null=True)
    is_tes_beneficiary = serializers.BooleanField(required=False)

    family_income = serializers.FloatField(required=False)
    household_size = serializers.IntegerField(required=False, allow_null=True)
    indigenous_group = serializers.CharField(required=False, allow_blank=True)
    parent_employment = serializers.CharField(required=False, allow_blank=True)
    is_from_depressed_area = serializers.BooleanField(required=False, allow_null=True)

    citizenship = serializers.CharField(required=False, allow_blank=True)
    is_listahanan_household = serializers.BooleanField(required=False, allow_null=True)
    is_4ps_beneficiary = serializers.BooleanField(required=False, allow_null=True)
    has_previous_degree = serializers.BooleanField(required=False, allow_null=True)
    year_first_enrolled = serializers.IntegerField(required=False, allow_null=True)
    is_solo_parent_dependent = serializers.BooleanField(required=False, allow_null=True)

    elementary = serializers.CharField(required=False, allow_blank=True)
    highschool = serializers.CharField(required=False, allow_blank=True)
    highschool_is_public = serializers.BooleanField(required=False, allow_null=True)
    last_school = serializers.CharField(required=False, allow_blank=True)

    father_last_name = serializers.CharField(required=False, allow_blank=True)
    father_first_name = serializers.CharField(required=False, allow_blank=True)
    father_middle_name = serializers.CharField(required=False, allow_blank=True)
    father_occupation = serializers.CharField(required=False, allow_blank=True)
    mother_last_name = serializers.CharField(required=False, allow_blank=True)
    mother_first_name = serializers.CharField(required=False, allow_blank=True)
    mother_middle_name = serializers.CharField(required=False, allow_blank=True)
    mother_occupation = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = StudentProfile
        fields = '__all__'

    def get_name(self, obj) -> str:
        """The student's full name."""
        return obj.user.get_full_name()

    def get_avatar(self, obj) -> str:
        """The profile photo URL, or ''."""
        name = obj.user.get_full_name().split()
        return ''.join([n[0] for n in name[:2]]).upper()


class ScholarshipSerializer(serializers.ModelSerializer):
    """A catalogue programme, with this student's fit score."""
    match = serializers.SerializerMethodField()

    class Meta:
        model = Scholarship
        fields = '__all__'

    def get_match(self, obj) -> int:
        """How well the signed-in student matches this programme.

        A rough score for ordering the catalogue, not an eligibility verdict —
        that comes from the recommender modules, which state their reasons.
        """
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'profile'):
            return 0
        return obj.match_score(request.user.profile)


class ApplicationDocumentSerializer(serializers.ModelSerializer):
    """One document attached to an application."""
    class Meta:
        model = ApplicationDocument
        fields = ['id', 'name', 'file', 'uploaded_at']


class ApplicationSerializer(serializers.ModelSerializer):
    """An application, its programme and its documents."""
    scholarship_name = serializers.CharField(source='scholarship.name', read_only=True)
    documents = ApplicationDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ['student', 'submitted_at', 'updated_at']

    def validate_scholarship(self, scholarship):
        """Refuse an application to a programme that is not applied for here.

        Externally funded programmes are applied for through the agency. Letting
        one through would record an award this office never granted and cannot
        honour.
        """
        if (self.instance is None
                and scholarship is not None and scholarship.group == 'external'):
            raise serializers.ValidationError(
                f'{scholarship.name} is applied for through the funding agency, '
                'not here. The office records the award once the agency grants it.'
            )
        return scholarship


class NotificationSerializer(serializers.ModelSerializer):
    """One notification."""
    time = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'body', 'is_read', 'time']

    def get_time(self, obj) -> str:
        """How long ago it arrived, in words."""
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now()) + ' ago'


class AnnouncementSerializer(serializers.ModelSerializer):
    """One announcement."""
    date = serializers.DateTimeField(source='created_at', format='%b %d, %Y', read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'date']


class AcademicRenewalSerializer(serializers.ModelSerializer):
    """One academic renewal submission."""
    student_name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    student_id = serializers.CharField(source='student.student_id', read_only=True)
    course = serializers.CharField(source='student.course', read_only=True)

    class Meta:
        model = AcademicRenewal
        fields = [
            'id', 'student', 'student_name', 'student_id', 'course',
            'certificate_of_grades', 'certificate_of_enrollment',
            'status', 'remarks', 'submitted_at', 'reviewed_at',
        ]
        read_only_fields = ['student', 'submitted_at']


class ImportedScholarSerializer(serializers.ModelSerializer):
    """One scholar imported from a funder spreadsheet."""
    class Meta:
        model = ImportedScholar
        fields = '__all__'



class ActivityLogSerializer(serializers.ModelSerializer):
    """One audit entry."""
    who = serializers.CharField(source='user.get_full_name', read_only=True)
    time = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ['id', 'who', 'action', 'time']

    def get_time(self, obj) -> str:
        """How long ago it happened, in words."""
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now()) + ' ago'


class SystemSettingsSerializer(serializers.ModelSerializer):
    """The system settings row."""
    class Meta:
        model = SystemSettings
        fields = '__all__'


class AdminUserSerializer(serializers.ModelSerializer):
    """An account as the office sees it, with its standing."""
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'role', 'status']

    def get_status(self, obj):
        """Verification standing in a word."""
        return 'Active' if obj.is_active else 'Inactive'
