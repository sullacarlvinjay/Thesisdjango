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


# ── Who may call what ─────────────────────────────────────────────────────────
#
# settings.REST_FRAMEWORK sets IsAuthenticated as the default, which answers
# "is this a signed-in account" and nothing else. Every /api/vpsea/ endpoint
# below reads or writes the whole office's records, so on that default a
# student's own token reached all of them: the applicant list is every
# applicant's data, and VPSEAApplicationDetailView is a PATCH away from
# approving your own application.
#
# The web portal never had that hole — api.student_views._vpsea_required checks
# the role on every page. This is the same check, spelled the way DRF expects
# it, so the two doors into the office agree about who may come in.

OFFICE_ROLES = ('vpsea', 'super')


class IsOfficeStaff(BasePermission):
    """An SDSO account, or a superuser. Nobody else reaches an office endpoint."""

    message = 'This endpoint is for SDSO office accounts.'

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user and user.is_authenticated
            and (user.is_superuser or getattr(user, 'role', '') in OFFICE_ROLES)
        )


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        # Prove the address the same way the web form does. Best-effort, and
        # after the account is saved: a mail server that is down must not lose
        # a registration — see api.email_verify.send_confirmation.
        email_verify.send_confirmation(user, request)
        # No token: the account is not usable until the SDSO verifies it, and
        # handing one out here would walk straight around that.
        return Response({
            'role': user.role,
            'verification_status': user.verification_status,
            'detail': 'Registration received. The SDSO has to verify this account '
                      'before it can be used.',
        }, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        # Same gate as the web login, checked after the password so the answer
        # is only ever about the caller's own account.
        if not user.can_sign_in:
            return Response({
                'verification_status': user.verification_status,
                'detail': user.verification_note or (
                    'This account is waiting for SDSO verification.'),
            }, status=status.HTTP_403_FORBIDDEN)
        token, _ = Token.objects.get_or_create(user=user)
        ActivityLog.objects.create(user=user, action='Logged in')
        return Response({'token': token.key, 'role': user.role})


class LogoutView(APIView):
    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Student ───────────────────────────────────────────────────────────────────

class StudentProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = StudentProfileSerializer

    def get_object(self):
        return self.request.user.profile


class ScholarshipListView(generics.ListAPIView):
    serializer_class = ScholarshipSerializer
    queryset = Scholarship.objects.filter(is_active=True)

    def get_serializer_context(self):
        return {'request': self.request}


class StudentApplicationListCreateView(generics.ListCreateAPIView):
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        return Application.objects.filter(student=self.request.user.profile)

    def perform_create(self, serializer):
        app = serializer.save(student=self.request.user.profile)
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"Submitted application for {app.scholarship.name}"
        )


class StudentApplicationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ApplicationSerializer

    def get_queryset(self):
        return Application.objects.filter(student=self.request.user.profile)


class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer

    def get_queryset(self):
        return Notification.objects.filter(student=self.request.user.profile).order_by('-created_at')


class StudentAnnouncementListView(generics.ListAPIView):
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all().order_by('-created_at')


class StudentDashboardView(APIView):
    def get(self, request):
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


# ── VPSEA ─────────────────────────────────────────────────────────────────────

class VPSEAStudentRankingView(APIView):
    """Who the Affirmative Action rules currently pass, and on what.

    Recommendations only. Nobody applies for this programme -- eligibility is
    decided from the student's own profile -- so there is no applicant list to
    return beside them; see vpsea_ranking, which renders the same thing.

    "The same thing" is literal: this returns the rows _affirmative_ranking_data
    built, in the order it built them, target groups first.
    """
    permission_classes = [IsOfficeStaff]

    def get(self, request):
        # Built from the same _affirmative_ranking_data the page renders, so the
        # two cannot end up ordered differently. They were separate queries
        # before, which was survivable only while both sorted on the same
        # column; the page now sorts target groups above the fit score, and a
        # second copy of that rule would be a second answer to "who are the top
        # five?" — the exact question this endpoint is asked.
        from .models import AffirmativeRecommendation
        from .student_views import _affirmative_ranking_data

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
            # Who the programme is for. Not a rule — see api/affirmative_ranking.
            'target_groups': list(row['groups'].markers),
            'target_group_count': row['groups'].count,
            'unanswered_group_questions': list(row['groups'].unknown),
            'eligible': row['eligible'],
        } for row in data['rows']]

        return Response({
            'recommendations': rec_data,
            'passing_threshold': passing,
            'eligible_count': data['eligible_count'],
            'ineligible_count': data['ineligible_count'],
            'in_target_group_count': data['in_target_group_count'],
        })


class VPSEAApplicationListView(generics.ListAPIView):
    permission_classes = [IsOfficeStaff]
    serializer_class = ApplicationSerializer
    queryset = Application.objects.select_related('student__user', 'scholarship', *STUDENT_DETAILS).all()


class VPSEAApplicationDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsOfficeStaff]
    serializer_class = ApplicationSerializer
    queryset = Application.objects.all()

    def perform_update(self, serializer):
        app = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"{serializer.validated_data.get('status', 'Updated')} application {app.id}"
        )


class VPSEARenewalListView(generics.ListAPIView):
    permission_classes = [IsOfficeStaff]
    serializer_class = AcademicRenewalSerializer

    def get_queryset(self):
        return AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).order_by('-submitted_at')


class VPSEARenewalDetailView(generics.RetrieveUpdateAPIView):
    permission_classes = [IsOfficeStaff]
    serializer_class = AcademicRenewalSerializer
    queryset = AcademicRenewal.objects.select_related('student__user', *STUDENT_DETAILS).all()

    def perform_update(self, serializer):
        renewal = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"Updated renewal {renewal.id} to {renewal.status} for {renewal.student}"
        )


class VPSEAArchiveListView(generics.ListAPIView):
    permission_classes = [IsOfficeStaff]
    serializer_class = ImportedScholarSerializer

    def get_queryset(self):
        return ImportedScholar.objects.filter(scholarship_type=self.kwargs['type'])


class VPSEAArchiveUploadView(APIView):
    permission_classes = [IsOfficeStaff]
    def post(self, request, type):
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
                    # The model's own default. A blank year level used to land
                    # here as 2024 — a calendar year in a column that holds 1
                    # to 4, which printed as "Year 2024" on every archive table
                    # and every report the row reached.
                    year_level=int(row[3]) if row[3] else 0,
                    imported_from=file.name,
                )
                created += 1
        ActivityLog.objects.create(user=request.user, action=f"Imported {file.name} ({created} rows) for {type}")
        return Response({'imported': created})


def _approval_trend():
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
    permission_classes = [IsOfficeStaff]
    def get(self, request):
            # The course and the GWA are columns on the enrolment row now, so these
        # aggregate across the relation rather than off the profile table.
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
        return Response({
            'course_distribution': list(course_dist),
            'gpa_distribution': gpa_ranges,
            'scholarship_distribution': [{'name': s['scholarship__type'], 'value': s['value']} for s in scholarship_dist],
            'approval_trend': _approval_trend(),
        })


class VPSEAAnnouncementListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsOfficeStaff]
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        ann = serializer.save(published_by=self.request.user)
        ActivityLog.objects.create(user=self.request.user, action=f"Published announcement: {ann.title}")


class VPSEAReportsView(APIView):
    """The masterlists this office can actually produce, one per term on file.

    It used to answer with four invented rows — a fixed 'Scholarship Master List
    A.Y. 2024-2025' at '2.4 MB', a 'GWA Distribution Report' that no code here
    has ever built — with plausible names and sizes attached to nothing. A
    caller could not tell them from real ones, which is the whole problem with
    a stub that answers 200.

    What the office really has is one masterlist per term, built on demand by
    api.masterlist_report and downloaded from /vpsea/reports/. That is what
    this lists, with the term it covers and the URL that produces it, and no
    size: the document does not exist until somebody asks for it.
    """
    permission_classes = [IsOfficeStaff]

    def get(self, request):
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
    permission_classes = [IsOfficeStaff]
    def get(self, request):
        apps = Application.objects.all()
        return Response({
            'total_applicants': apps.count(),
            'approved': apps.filter(status='Approved').count(),
            'rejected': apps.filter(status='Rejected').count(),
            'pending': apps.filter(status='Pending Validation').count(),
            'renewals': AcademicRenewal.objects.filter(status='Pending').count(),
        })


