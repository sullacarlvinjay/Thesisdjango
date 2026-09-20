"""Response shapes for the endpoints that are plain ``APIView``s.

A generic view carries its serializer, so the schema generator can read the
contract off it. The eight views below build their response dictionaries by
hand, and without these there is nothing for it to read: the published schema
would list the paths and say nothing about what comes back, which is most of
the way to having no contract at all.

These serializers are for documentation. Nothing validates against them, so
they have to be kept honest by the test that compares them with what the
views actually return — see ``api/test_openapi_schema.py``.
"""

from rest_framework import serializers


class RegistrationAcceptedSerializer(serializers.Serializer):
    """What ``POST /api/auth/register/`` returns on success."""
    role = serializers.CharField()
    verification_status = serializers.CharField()
    detail = serializers.CharField()


class TokenSerializer(serializers.Serializer):
    """An issued API token and the role it belongs to."""
    token = serializers.CharField()
    role = serializers.CharField()


class SignInRefusedSerializer(serializers.Serializer):
    """Why an account with correct credentials still may not sign in."""
    verification_status = serializers.CharField()
    detail = serializers.CharField()


class MatchScoreSerializer(serializers.Serializer):
    """One programme's fit for the signed-in student."""
    name = serializers.CharField()
    score = serializers.IntegerField()


class StudentDashboardSerializer(serializers.Serializer):
    """The counts behind the student dashboard."""
    recommended_count = serializers.IntegerField()
    pending_count = serializers.IntegerField()
    approved_count = serializers.IntegerField()
    notification_count = serializers.IntegerField()
    match_scores = MatchScoreSerializer(many=True)
    profile_strength = serializers.IntegerField()


class OfficeDashboardSerializer(serializers.Serializer):
    """The counts behind the office dashboard."""
    total_applicants = serializers.IntegerField()
    approved = serializers.IntegerField()
    rejected = serializers.IntegerField()
    pending = serializers.IntegerField()
    renewals = serializers.IntegerField()


class ArchiveUploadRequestSerializer(serializers.Serializer):
    """The spreadsheet posted to the archive upload endpoint."""
    file = serializers.FileField()


class ArchiveUploadSerializer(serializers.Serializer):
    """How many scholar rows an upload created."""
    imported = serializers.IntegerField()


class ErrorSerializer(serializers.Serializer):
    """A refusal this API states in one line."""
    error = serializers.CharField()


class CourseCountSerializer(serializers.Serializer):
    """Scholars enrolled on one course."""
    course = serializers.CharField(allow_null=True)
    scholars = serializers.IntegerField()


class BandCountSerializer(serializers.Serializer):
    """Students in one GWA band."""
    range = serializers.CharField()
    count = serializers.IntegerField()


class NamedValueSerializer(serializers.Serializer):
    """One slice of the programme distribution."""
    name = serializers.CharField(allow_null=True)
    value = serializers.IntegerField()


class MonthlyApprovalSerializer(serializers.Serializer):
    """Approvals in one month."""
    month = serializers.CharField()
    approvals = serializers.IntegerField()


class OfficeAnalyticsSerializer(serializers.Serializer):
    """The figures behind the office analytics dashboard."""
    course_distribution = CourseCountSerializer(many=True)
    gpa_distribution = BandCountSerializer(many=True)
    scholarship_distribution = NamedValueSerializer(many=True)
    approval_trend = MonthlyApprovalSerializer(many=True)


class ReportLinkSerializer(serializers.Serializer):
    """One downloadable masterlist."""
    term = serializers.CharField()
    name = serializers.CharField()
    desc = serializers.CharField()
    url = serializers.CharField()


class AffirmativeRecommendationSerializer(serializers.Serializer):
    """One applicant's place in the Affirmative Action ranking."""
    id = serializers.IntegerField()
    rank = serializers.IntegerField()
    student_id = serializers.CharField(allow_blank=True)
    name = serializers.CharField(allow_blank=True)
    course = serializers.CharField(allow_blank=True)
    year_level = serializers.IntegerField()
    shs_gpa = serializers.FloatField(allow_null=True)
    suc_exam_score = serializers.FloatField(allow_null=True)
    suc_exam_total = serializers.FloatField(allow_null=True)
    suc_exam_percent = serializers.FloatField(allow_null=True)
    is_tes_beneficiary = serializers.BooleanField()
    fit_score = serializers.FloatField()
    status = serializers.CharField()
    gpa_pass = serializers.BooleanField()
    exam_pass = serializers.BooleanField()
    not_tes = serializers.BooleanField()
    target_groups = serializers.ListField(child=serializers.CharField())
    target_group_count = serializers.IntegerField()
    unanswered_group_questions = serializers.ListField(
        child=serializers.CharField())
    eligible = serializers.BooleanField()


class AffirmativeRankingSerializer(serializers.Serializer):
    """A page of the ranking, with the totals the office reads beside it."""
    recommendations = AffirmativeRecommendationSerializer(many=True)
    recommendation_count = serializers.IntegerField()
    limit = serializers.IntegerField()
    offset = serializers.IntegerField()
    passing_threshold = serializers.FloatField()
    eligible_count = serializers.IntegerField()
    ineligible_count = serializers.IntegerField()
    in_target_group_count = serializers.IntegerField()
