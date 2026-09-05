from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    User, StudentProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, AcademicRenewal, ImportedScholar,
    ActivityLog, SystemSettings,
)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    student_id = serializers.CharField()
    course = serializers.CharField()
    year_level = serializers.IntegerField()
    gwa = serializers.FloatField()
    contact_number = serializers.CharField(required=False, allow_blank=True)
    # The address is three columns, not one. A single 'address' field was
    # declared here and passed straight to StudentProfile.objects.create(),
    # where it hit the read-only property of that name and raised
    # AttributeError — after the User row had already been created.
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

    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name',
            'student_id', 'course', 'year_level', 'gwa',
            'contact_number', 'barangay', 'municipality', 'province',
            'middle_name', 'suffix',
            'date_of_birth', 'gender',
            'family_income', 'indigenous_group', 'parent_employment',
            'disability_type',
        ]

    def create(self, validated_data):
        profile_fields = [
            'student_id', 'course', 'year_level', 'gwa', 'contact_number',
            'barangay', 'municipality', 'province',
            'middle_name', 'suffix', 'date_of_birth', 'gender', 'family_income',
            'indigenous_group', 'parent_employment', 'disability_type',
        ]
        profile_data = {f: validated_data.pop(f, None) for f in profile_fields}
        password = validated_data.pop('password')
        validated_data['username'] = validated_data['email']
        # The same gate as the web form: registering yourself never releases the
        # account, whichever door it came through.
        validated_data['verification_status'] = 'pending'
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        StudentProfile.objects.create(user=user, **{k: v for k, v in profile_data.items() if v is not None})
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

    def validate(self, data):
        user = authenticate(username=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Invalid credentials')
        data['user'] = user
        return data


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'role']


class StudentProfileSerializer(serializers.ModelSerializer):
    """A student's whole record, flat, the way the API has always returned it.

    Most of these are no longer columns on StudentProfile — they live on the
    detail rows it hangs off. They are declared here rather than left to
    ``fields = '__all__'`` because the autodetected list only sees this table's
    own columns, and dropping forty keys from a response is not a refactor. The
    profile's :class:`~api.models.DetailField` proxies read and write them, so a
    PATCH lands on the right row without this serializer knowing which.
    """
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar = serializers.SerializerMethodField()

    # ── Enrolment
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

    # ── Personal
    middle_name = serializers.CharField(required=False, allow_blank=True)
    suffix = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    birth_place = serializers.CharField(required=False, allow_blank=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    civil_status = serializers.CharField(required=False, allow_blank=True)
    contact_number = serializers.CharField(required=False, allow_blank=True)
    disability_type = serializers.CharField(required=False, allow_blank=True)

    # ── Affirmative eligibility
    shs_gpa = serializers.FloatField(required=False, allow_null=True)
    suc_exam_score = serializers.FloatField(required=False, allow_null=True)
    suc_exam_total = serializers.FloatField(required=False, allow_null=True)
    is_tes_beneficiary = serializers.BooleanField(required=False)

    # ── Needs-based and priority-group indicators
    family_income = serializers.FloatField(required=False)
    household_size = serializers.IntegerField(required=False, allow_null=True)
    indigenous_group = serializers.CharField(required=False, allow_blank=True)
    parent_employment = serializers.CharField(required=False, allow_blank=True)

    # ── TES eligibility. Three-state, so null has to survive the round trip.
    citizenship = serializers.CharField(required=False, allow_blank=True)
    is_listahanan_household = serializers.BooleanField(required=False, allow_null=True)
    is_4ps_beneficiary = serializers.BooleanField(required=False, allow_null=True)
    has_previous_degree = serializers.BooleanField(required=False, allow_null=True)
    year_first_enrolled = serializers.IntegerField(required=False, allow_null=True)

    # ── Educational background
    elementary = serializers.CharField(required=False, allow_blank=True)
    highschool = serializers.CharField(required=False, allow_blank=True)
    last_school = serializers.CharField(required=False, allow_blank=True)

    # ── Family background
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

    def get_name(self, obj):
        return obj.user.get_full_name()

    def get_avatar(self, obj):
        name = obj.user.get_full_name().split()
        return ''.join([n[0] for n in name[:2]]).upper()


class ScholarshipSerializer(serializers.ModelSerializer):
    match = serializers.SerializerMethodField()

    class Meta:
        model = Scholarship
        fields = '__all__'

    def get_match(self, obj):
        """Delegates to Scholarship.match_score, so the API and the web portal
        agree.

        This method used to carry a second, different formula. For a student
        with GWA 1.28 on the Academic scholarship the portal showed 80 and this
        returned 89 — same student, same scholarship, two numbers.
        """
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'profile'):
            return 0
        return obj.match_score(request.user.profile)


class ApplicationDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationDocument
        fields = ['id', 'name', 'file', 'uploaded_at']


class ApplicationSerializer(serializers.ModelSerializer):
    scholarship_name = serializers.CharField(source='scholarship.name', read_only=True)
    documents = ApplicationDocumentSerializer(many=True, read_only=True)

    class Meta:
        model = Application
        fields = '__all__'
        read_only_fields = ['student', 'submitted_at', 'updated_at']


class NotificationSerializer(serializers.ModelSerializer):
    time = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = ['id', 'type', 'title', 'body', 'is_read', 'time']

    def get_time(self, obj):
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now()) + ' ago'


class AnnouncementSerializer(serializers.ModelSerializer):
    date = serializers.DateTimeField(source='created_at', format='%b %d, %Y', read_only=True)

    class Meta:
        model = Announcement
        fields = ['id', 'title', 'body', 'date']


class AcademicRenewalSerializer(serializers.ModelSerializer):
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
    class Meta:
        model = ImportedScholar
        fields = '__all__'



class ActivityLogSerializer(serializers.ModelSerializer):
    who = serializers.CharField(source='user.get_full_name', read_only=True)
    time = serializers.SerializerMethodField()

    class Meta:
        model = ActivityLog
        fields = ['id', 'who', 'action', 'time']

    def get_time(self, obj):
        from django.utils import timezone
        from django.utils.timesince import timesince
        return timesince(obj.created_at, timezone.now()) + ' ago'


class SystemSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SystemSettings
        fields = '__all__'


class AdminUserSerializer(serializers.ModelSerializer):
    status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'role', 'status']

    def get_status(self, obj):
        return 'Active' if obj.is_active else 'Inactive'
