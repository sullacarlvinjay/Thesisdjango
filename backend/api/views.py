"""The REST API.

Token-authenticated, mounted under ``/api/``. It serves clients that are not
the server-rendered portals; the portals themselves use the view modules.

List endpoints are paged — responses are ``{count, next, previous, results}``
rather than bare arrays. See ``api/pagination.py``.
"""

from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.authtoken.models import Token
from django.db.models import Count
from . import email_verify
from .models import (
    STUDENT_DETAILS,
    StudentProfile, Scholarship, Application, Notification,
    Announcement, AcademicRenewal, ImportedScholar,
    ActivityLog,
)
from .serializers import (
    RegisterSerializer, LoginSerializer, StudentProfileSerializer,
    ScholarshipSerializer, ApplicationSerializer, NotificationSerializer,
    AnnouncementSerializer, AcademicRenewalSerializer,
    ImportedScholarSerializer,
)


OFFICE_ROLES = ('vpsea', 'super')


class IsOfficeStaff(BasePermission):
    """Allow only SDSO office accounts and superusers."""
    message = 'This endpoint is for SDSO office accounts.'

    def has_permission(self, request, view):
        """Whether this request comes from the office."""
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_superuser or getattr(user, 'role', '') in OFFICE_ROLES)
        )


class RegisterView(APIView):
    """Register an account and send the confirmation email."""
    permission_classes = [AllowAny]

    def post(self, request):
        """Create the account; it still needs SDSO verification."""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        email_verify.send_confirmation(user, request)
        return Response({
            'role': user.role,
            'verification_status': user.verification_status,
            'detail': 'Registration received. The SDSO has to verify this account '
                      'before it can be used.',
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    """Exchange credentials for an API token."""
    permission_classes = [AllowAny]

    def post(self, request):
        """Issue a token, unless the account may not sign in yet.

        An unverified account is refused with its standing, so a client can say
        what is happening rather than showing a bare failure.
        """
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        if not user.can_sign_in:
            return Response({
                'verification_status': user.verification_status,
                'detail': user.verification_note or (
                    'This account is waiting for SDSO verification.'),
            }, status=status.HTTP_403_FORBIDDEN)
        token, _ = Token.objects.get_or_create(user=user)
        ActivityLog.record(
            user, 'Logged in',
            verb='sign-in', request=request)
        return Response({'token': token.key, 'role': user.role})


class LogoutView(APIView):
    """Discard the caller's API token."""
    def post(self, request):
        """Delete the token, ending every session using it."""
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentProfileView(generics.RetrieveUpdateAPIView):
    """Read and update the signed-in student's own profile."""
    serializer_class = StudentProfileSerializer

    def get_object(self):
        """Always the caller's own profile, never another's."""
        return self.request.user.profile


class ScholarshipListView(generics.ListAPIView):
    """The active scholarship catalogue."""
    serializer_class = ScholarshipSerializer
    queryset = Scholarship.objects.filter(is_active=True)

    def get_serializer_context(self):
        """Pass the request so match scores can be computed."""
        return {'request': self.request}


class StudentApplicationListCreateView(generics.ListCreateAPIView):
    """The student's own applications."""
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        """Only the caller's applications."""
        return Application.objects.filter(student=self.request.user.profile)

    def perform_create(self, serializer):
        """File the application and record it in the audit log."""
        app = serializer.save(student=self.request.user.profile)
        ActivityLog.record(
            self.request.user, f"Submitted application for {app.scholarship.name}",
            verb='other')


class StudentApplicationDetailView(generics.RetrieveUpdateAPIView):
    """One of the student's own applications."""
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        """Only the caller's applications."""
        return Application.objects.filter(student=self.request.user.profile)


class NotificationListView(generics.ListAPIView):
    """The student's notifications, newest first."""
    serializer_class = NotificationSerializer

    def get_queryset(self):
        """Only the caller's notifications."""
        return Notification.objects.filter(student=self.request.user.profile).order_by('-created_at')


class StudentAnnouncementListView(generics.ListAPIView):
    """Announcements, newest first."""
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all().order_by('-created_at')


class StudentDashboardView(APIView):
    """The counts and match scores behind the student dashboard."""
    def get(self, request):
        """Summarise this student's standing."""
        profile = request.user.profile
        apps = Application.objects.filter(student=profile)
        scholarships = Scholarship.objects.filter(is_active=True)
        serializer = ScholarshipSerializer(scholarships, many=True, context={'request': request})
        match_scores = [{'name': s['name'].split()[0], 'score': s['match']} for s in serializer.data]
        return Response({
            'recommended_count': scholarships.count(),
            'pending_count': apps.filter(status='Pending Validation').count(),
            'approved_count': apps.filter(status='Approved').count(),
            'notification_count': Notification.objects.filter(student=profile).count(),
            'match_scores': match_scores,
            'profile_strength': max((s['match'] for s in serializer.data), default=0),
        })


class VPSEAStudentRankingView(APIView):
    """The Affirmative Action ranking, a page at a time.

    This one is paged by hand rather than through ``SRMSPagination``. The
    response is an envelope — the ranking plus the counts the office reads
    alongside it — and DRF's ``{count, next, previous, results}`` would
    replace that envelope, taking the summary with it. So the rows are sliced
    and the totals kept.
    """

    permission_classes = [IsOfficeStaff]

    DEFAULT_LIMIT = 50
    MAX_LIMIT = 200

    def _window(self, request):
        """``?limit=`` and ``?offset=``, clamped rather than refused."""
        def number(name, fallback, lowest=0):
            """A bounded integer from a query parameter, falling back when absent."""
            try:
                return max(lowest, int(request.query_params.get(name, fallback)))
            except (TypeError, ValueError):
                return fallback

        limit = min(number('limit', self.DEFAULT_LIMIT, 1), self.MAX_LIMIT)
        return limit, number('offset', 0)

    def get(self, request):
        """Recompute and return the ranking for a threshold."""
        from .models import AffirmativeRecommendation
        from .views_ranking import _affirmative_ranking_data

        try:
            passing = float(request.query_params.get('passing', 75.0))
        except (TypeError, ValueError):
            passing = 75.0

        AffirmativeRecommendation.evaluate_and_sync(passing)
        data = _affirmative_ranking_data(passing)
        rec_data = [{
            'id': row['rec'].id,
            'rank': row['rank'],
            'student_id': row['profile'].student_id,
            'name': row['profile'].user.get_full_name(),
            'course': row['profile'].course,
            'year_level': row['profile'].year_level,
            'shs_gpa': row['profile'].shs_gpa,
            'suc_exam_score': row['profile'].suc_exam_score,
            'suc_exam_total': row['profile'].suc_exam_total,
            'suc_exam_percent': row['profile'].suc_exam_percent,
            'is_tes_beneficiary': row['profile'].is_tes_beneficiary,
            'fit_score': row['rec'].fit_score,
            'status': row['rec'].status,
            'gpa_pass': row['gpa_pass'],
            'exam_pass': row['exam_pass'],
            'not_tes': row['not_tes'],
            'target_groups': list(row['groups'].markers),
            'target_group_count': row['groups'].count,
            'unanswered_group_questions': list(row['groups'].unknown),
            'eligible': row['eligible'],
        } for row in data['rows']]

        limit, offset = self._window(request)
        page = rec_data[offset:offset + limit]

        return Response({
            'recommendations': page,
            'recommendation_count': len(rec_data),
            'limit': limit,
            'offset': offset,
            'passing_threshold': passing,
            'eligible_count': data['eligible_count'],
            'ineligible_count': data['ineligible_count'],
            'in_target_group_count': data['in_target_group_count'],
        })


class VPSEAApplicationListView(generics.ListAPIView):
    """Every application, for the office."""
    permission_classes = [IsOfficeStaff]
    serializer_class = ApplicationSerializer
    queryset = Application.objects.select_related('student__user', 'scholarship', *STUDENT_DETAILS).all()


class VPSEAApplicationDetailView(generics.RetrieveUpdateAPIView):
    """One application, for the office to decide."""
    permission_classes = [IsOfficeStaff]
    serializer_class = ApplicationSerializer
    queryset = Application.objects.all()

    def perform_update(self, serializer):
        """Save the decision, notify the student and log it."""
        app = serializer.save()
        ActivityLog.record(
            self.request.user, f"{serializer.validated_data.get('status', 'Updated')} application {app.id}",
            verb='other')


class VPSEARenewalListView(generics.ListAPIView):
    """Every renewal submission, for the office."""
    permission_classes = [IsOfficeStaff]
    serializer_class = AcademicRenewalSerializer

    def get_queryset(self):
        """Every renewal, newest first."""
        return AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).order_by('-submitted_at')


class VPSEARenewalDetailView(generics.RetrieveUpdateAPIView):
    """One renewal, for the office to decide."""
    permission_classes = [IsOfficeStaff]
    serializer_class = AcademicRenewalSerializer
    queryset = AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).all()

    def perform_update(self, serializer):
        """Save the decision, notify the student and log it."""
        renewal = serializer.save()
        ActivityLog.record(
            self.request.user, f"Updated renewal {renewal.id} to {renewal.status} for {renewal.student}",
            verb='other')


class VPSEAArchiveListView(generics.ListAPIView):
    """Imported scholars for one programme."""
    permission_classes = [IsOfficeStaff]
    serializer_class = ImportedScholarSerializer

    def get_queryset(self):
        """Scholars of the programme named in the URL."""
        return ImportedScholar.objects.filter(scholarship_type=self.kwargs['type'])


class VPSEAArchiveUploadView(APIView):
    """Import a scholar list from a spreadsheet."""
    permission_classes = [IsOfficeStaff]
    def post(self, request, type):
        """Read the workbook and record what it created."""
        import openpyxl
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)
        wb = openpyxl.load_workbook(file)
        ws = wb.active
        created = 0
        for row in ws.iter_rows(min_row=2, values_only=True):
            if row[0]:
                ImportedScholar.objects.create(
                    scholarship_type=type,
                    course=str(row[1]) if row[1] else '',
                    gwa=float(row[2]) if row[2] else 0.0,
                    year_level=int(row[3]) if row[3] else 0,
                    imported_from=file.name,
                )
                created += 1
        ActivityLog.record(
            request.user, f"Imported {file.name} ({created} rows) for {type}",
            verb='import', request=request)
        return Response({'imported': created})


def _approval_trend():
    """Approvals per month, for the dashboard chart."""
    from django.utils import timezone
    import datetime
    months = []
    today = timezone.now().date()
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - datetime.timedelta(days=i * 28)).replace(day=1)
        month_end = (month_start + datetime.timedelta(days=32)).replace(day=1)
        count = Application.objects.filter(
            status='Approved',
            submitted_at__gte=month_start,
            submitted_at__lt=month_end,
        ).count()
        months.append({'month': month_start.strftime('%b %Y'), 'approvals': count})
    return months


class VPSEAAnalyticsView(APIView):
    """The figures behind the analytics dashboard."""
    permission_classes = [IsOfficeStaff]
    CACHE_KEY = 'api-vpsea-analytics'

    def get(self, request):
        """Totals, distributions and the approval trend."""
        from django.conf import settings as django_settings
        from django.core.cache import cache

        payload = cache.get(self.CACHE_KEY)
        if payload is None:
            payload = self._payload()
            cache.set(self.CACHE_KEY, payload,
                      django_settings.ANALYTICS_CACHE_SECONDS)
        return Response(payload)

    def _payload(self):
        """Compute the dashboard figures.

        Separate from :meth: so the cached and uncached paths cannot
        diverge: the response is built here and only here.
        """
        course_dist = [
            {'course': row['enrollment__course'], 'scholars': row['scholars']}
            for row in StudentProfile.objects.filter(applications__status='Approved')
            .values('enrollment__course').annotate(scholars=Count('id'))
        ]
        gwa_bands = [
            ('1.00-1.25', {'enrollment__gwa__gte': 1.0, 'enrollment__gwa__lte': 1.25}),
            ('1.26-1.50', {'enrollment__gwa__gt': 1.25, 'enrollment__gwa__lte': 1.50}),
            ('1.51-1.75', {'enrollment__gwa__gt': 1.50, 'enrollment__gwa__lte': 1.75}),
            ('1.76-2.00', {'enrollment__gwa__gt': 1.75, 'enrollment__gwa__lte': 2.00}),
            ('2.01-2.50', {'enrollment__gwa__gt': 2.00, 'enrollment__gwa__lte': 2.50}),
        ]
        gpa_ranges = [
            {'range': label, 'count': StudentProfile.objects.filter(**band).count()}
            for label, band in gwa_bands
        ]
        scholarship_dist = (
            Application.objects.filter(status='Approved')
            .values('scholarship__type').annotate(value=Count('id'))
        )
        return {
            'course_distribution': list(course_dist),
            'gpa_distribution': gpa_ranges,
            'scholarship_distribution': [{'name': s['scholarship__type'], 'value': s['value']} for s in scholarship_dist],
            'approval_trend': _approval_trend(),
        }


class VPSEAAnnouncementListCreateView(generics.ListCreateAPIView):
    """Read and publish announcements."""
    permission_classes = [IsOfficeStaff]
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        """Publish, recording who wrote it."""
        ann = serializer.save(published_by=self.request.user)
        ActivityLog.record(
            self.request.user, f"Published announcement: {ann.title}",
            verb='other')


class VPSEAReportsView(APIView):
    """Report totals for the office."""
    permission_classes = [IsOfficeStaff]

    def get(self, request):
        """Scholar counts per programme for the active term."""
        from .models import SystemSettings
        from . import masterlist_report

        return Response([
            {
                'term': label,
                'name': 'BiPSU List of Scholars — {sy} {semester}'.format(
                    **SystemSettings.parse_label(label)),
                'desc': 'Every approved scholar for the term, by programme.',
                'url': f'/vpsea/reports/download/?sy={label}',
            }
            for label in masterlist_report.known_terms()
        ])


class VPSEADashboardView(APIView):
    """The counts behind the office dashboard."""
    permission_classes = [IsOfficeStaff]
    def get(self, request):
        """Applications, renewals and accounts awaiting a decision."""
        apps = Application.objects.all()
        return Response({
            'total_applicants': apps.count(),
            'approved': apps.filter(status='Approved').count(),
            'rejected': apps.filter(status='Rejected').count(),
            'pending': apps.filter(status='Pending Validation').count(),
            'renewals': AcademicRenewal.objects.filter(status='Pending').count(),
        })


