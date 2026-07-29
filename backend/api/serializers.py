from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import (
    User, StudentProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, Renewal, AcademicRenewal, ArchiveRecord,
    TDPApplication, ActivityLog, SystemSettings,
)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    student_id = serializers.CharField()
    course = serializers.CharField()
    year_level = serializers.IntegerField()
    gwa = serializers.FloatField()
    contact_number = serializers.CharField(required=False, allow_blank=True)
    address = serializers.CharField(required=False, allow_blank=True)
    date_of_birth = serializers.DateField(required=False, allow_null=True)
    gender = serializers.CharField(required=False, allow_blank=True)
    family_income = serializers.FloatField(required=False, default=0.0)
    indigenous_group = serializers.CharField(required=False, allow_blank=True)
    parent_employment = serializers.CharField(required=False, allow_blank=True)
    is_pwd = serializers.BooleanField(required=False, default=False)
    is_athlete = serializers.BooleanField(required=False, default=False)
    is_coconut_farmer_family = serializers.BooleanField(required=False, default=False)
    has_other_scholarship = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = User
        fields = [
            'email', 'password', 'first_name', 'last_name',
            'student_id', 'course', 'year_level', 'gwa',
            'contact_number', 'address', 'date_of_birth', 'gender',
            'family_income', 'indigenous_group', 'parent_employment',
            'is_pwd', 'is_athlete', 'is_coconut_farmer_family', 'has_other_scholarship',
        ]

    def create(self, validated_data):
        profile_fields = [
            'student_id', 'course', 'year_level', 'gwa', 'contact_number',
            'address', 'date_of_birth', 'gender', 'family_income',
            'indigenous_group', 'parent_employment', 'is_pwd',
            'is_athlete', 'is_coconut_farmer_family', 'has_other_scholarship',
        ]
        profile_data = {f: validated_data.pop(f, None) for f in profile_fields}
        password = validated_data.pop('password')
        validated_data['username'] = validated_data['email']
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
    name = serializers.SerializerMethodField()
    email = serializers.EmailField(source='user.email', read_only=True)
    avatar = serializers.SerializerMethodField()

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
        request = self.context.get('request')
        if not request or not hasattr(request.user, 'profile'):
            return 0
        profile = request.user.profile
        score = 50
        if obj.type == 'Academic' and profile.gwa <= 1.50:
            score = round(100 - (profile.gwa - 1.0) * 40)
        elif obj.type == 'TDP' and profile.family_income < 300000:
            score = round(100 - (profile.family_income / 300000) * 30)
        elif obj.type == 'Sports' and profile.is_athlete:
            score = 85
        elif obj.type == 'Affirmative' and (profile.is_pwd or profile.indigenous_group):
            score = 80
        elif obj.type == 'CoScho' and profile.is_coconut_farmer_family:
            score = 75
        return min(max(score, 0), 100)


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


class RenewalSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    scholarship_name = serializers.CharField(source='scholarship.name', read_only=True)

    class Meta:
        model = Renewal
        fields = '__all__'


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


class ArchiveRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = ArchiveRecord
        fields = '__all__'


class TDPApplicationSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source='student.user.get_full_name', read_only=True)
    course = serializers.CharField(source='student.course', read_only=True)

    class Meta:
        model = TDPApplication
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
