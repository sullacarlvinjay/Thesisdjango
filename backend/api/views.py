from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.db.models import Count
from .models import (
    User, StudentProfile, Scholarship, Application, Notification,
    Announcement, Renewal, AcademicRenewal, ArchiveRecord,
    TDPApplication, ActivityLog, SystemSettings,
)
from .serializers import (
    RegisterSerializer, LoginSerializer, StudentProfileSerializer,
    ScholarshipSerializer, ApplicationSerializer, NotificationSerializer,
    AnnouncementSerializer, RenewalSerializer, AcademicRenewalSerializer,
    ArchiveRecordSerializer, TDPApplicationSerializer,
    ActivityLogSerializer, SystemSettingsSerializer, AdminUserSerializer,
)


# â”€â”€ Auth â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({'token': token.key, 'role': user.role}, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        token, _ = Token.objects.get_or_create(user=user)
        ActivityLog.objects.create(user=user, action=f"Logged in")
        return Response({'token': token.key, 'role': user.role})


class LogoutView(APIView):
    def post(self, request):
        request.user.auth_token.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# â”€â”€ Student â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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


# â”€â”€ VPSEA â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

class VPSEAStudentRankingView(APIView):
    def get(self, request):
        from .models import AffirmativeNSUApplication, AffirmativeRecommendation
        scholarship_type = request.query_params.get('type', 'Affirmative')
        if scholarship_type not in ('Affirmative', 'Staff'):
            scholarship_type = 'Affirmative'
        try:
            passing = float(request.query_params.get('passing', 75.0))
        except (TypeError, ValueError):
            passing = 75.0

        # ── Applicants tab ──
        applicants = AffirmativeNSUApplication.objects.exclude(status='Approved').filter(
            qualified_for=scholarship_type
        )
        def score(a):
            if scholarship_type == 'Affirmative':
                s = 0.0
                if a.shs_gpa: s += min((a.shs_gpa / 100) * 50, 50)
                if a.suc_exam_score: s += min((a.suc_exam_score / 100) * 50, 50)
                return round(s)
            return 100 if a.is_nsu_staff else 75

        ranked = sorted(applicants, key=score, reverse=True)
        applicant_data = [{
            'rank': i + 1, 'name': a.full_name, 'course': a.course,
            'year_level': a.year_level, 'shs_gpa': a.shs_gpa,
            'suc_exam_score': a.suc_exam_score, 'score': score(a),
            'eligible': (
                a.shs_gpa is not None and a.shs_gpa >= passing and
                a.suc_exam_score is not None and a.suc_exam_score >= 50.0 and
                not a.is_tes_beneficiary
            ) if scholarship_type == 'Affirmative' else True,
        } for i, a in enumerate(ranked)]

        # ── Recommendations tab (enrolled students) ──
        AffirmativeRecommendation.evaluate_and_sync(passing)
        recs = AffirmativeRecommendation.objects.select_related('student__user').order_by('-fit_score')
        rec_data = [{
            'id': r.id,
            'student_id': r.student.student_id,
            'name': r.student.user.get_full_name(),
            'course': r.student.course,
            'year_level': r.student.year_level,
            'shs_gpa': r.student.shs_gpa,
            'suc_exam_score': r.student.suc_exam_score,
            'is_tes_beneficiary': r.student.is_tes_beneficiary,
            'fit_score': r.fit_score,
            'status': r.status,
            'gpa_pass': r.student.shs_gpa is not None and r.student.shs_gpa >= passing,
            'exam_pass': r.student.suc_exam_score is not None and r.student.suc_exam_score >= 50.0,
            'not_tes': not r.student.is_tes_beneficiary,
        } for r in recs]

        return Response({
            'applicants': applicant_data,
            'recommendations': rec_data,
            'passing_threshold': passing,
        })


class VPSEAApplicationListView(generics.ListAPIView):
    serializer_class = ApplicationSerializer
    queryset = Application.objects.select_related('student__user', 'scholarship').all()


class VPSEAApplicationDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = ApplicationSerializer
    queryset = Application.objects.all()

    def perform_update(self, serializer):
        app = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"{serializer.validated_data.get('status', 'Updated')} application {app.id}"
        )


class VPSEARenewalListView(generics.ListAPIView):
    serializer_class = AcademicRenewalSerializer

    def get_queryset(self):
        return AcademicRenewal.objects.select_related('student__user').order_by('-submitted_at')


class VPSEARenewalDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AcademicRenewalSerializer
    queryset = AcademicRenewal.objects.select_related('student__user').all()

    def perform_update(self, serializer):
        renewal = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"Updated renewal {renewal.id} to {renewal.status} for {renewal.student}"
        )


class VPSEAArchiveListView(generics.ListAPIView):
    serializer_class = ArchiveRecordSerializer

    def get_queryset(self):
        return ArchiveRecord.objects.filter(scholarship_type=self.kwargs['type'])


class VPSEAArchiveUploadView(APIView):
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
                ArchiveRecord.objects.create(
                    scholarship_type=type,
                    scholar_name=str(row[0]),
                    course=str(row[1]) if row[1] else '',
                    gwa=float(row[2]) if row[2] else 0.0,
                    year=int(row[3]) if row[3] else 2024,
                    imported_from=file.name,
                )
                created += 1
        ActivityLog.objects.create(user=request.user, action=f"Imported {file.name} ({created} rows) for {type}")
        return Response({'imported': created})


def _approval_trend():
    from django.db.models.functions import TruncMonth
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
    def get(self, request):
        from django.db.models.functions import TruncMonth
        course_dist = (
            StudentProfile.objects.filter(applications__status='Approved')
            .values('course').annotate(scholars=Count('id'))
        )
        gpa_ranges = [
            {'range': '1.00-1.25', 'count': StudentProfile.objects.filter(gwa__gte=1.0, gwa__lte=1.25).count()},
            {'range': '1.26-1.50', 'count': StudentProfile.objects.filter(gwa__gt=1.25, gwa__lte=1.50).count()},
            {'range': '1.51-1.75', 'count': StudentProfile.objects.filter(gwa__gt=1.50, gwa__lte=1.75).count()},
            {'range': '1.76-2.00', 'count': StudentProfile.objects.filter(gwa__gt=1.75, gwa__lte=2.00).count()},
            {'range': '2.01-2.50', 'count': StudentProfile.objects.filter(gwa__gt=2.00, gwa__lte=2.50).count()},
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
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        ann = serializer.save(published_by=self.request.user)
        ActivityLog.objects.create(user=self.request.user, action=f"Published announcement: {ann.title}")


class VPSEAReportsView(APIView):
    def get(self, request):
        return Response([
            {'name': 'Scholarship Master List A.Y. 2024-2025', 'desc': 'Consolidated list of all active scholars.', 'size': '2.4 MB'},
            {'name': 'Academic Scholarship Approval Report Q2', 'desc': 'Approval, rejection and renewal statistics.', 'size': '812 KB'},
            {'name': 'GWA Distribution Report', 'desc': 'Cohort-wise GWA breakdown.', 'size': '640 KB'},
            {'name': 'TDP Recipients Report', 'desc': 'List of TDP recipients with subsidy amounts.', 'size': '1.1 MB'},
        ])


class VPSEADashboardView(APIView):
    def get(self, request):
        apps = Application.objects.all()
        return Response({
            'total_applicants': apps.count(),
            'approved': apps.filter(status='Approved').count(),
            'rejected': apps.filter(status='Rejected').count(),
            'pending': apps.filter(status='Pending Validation').count(),
            'renewals': Renewal.objects.filter(status='Renewal Pending').count(),
        })



class UniFASTDashboardView(APIView):
    def get(self, request):
        from .models import TDPApplication
        return Response({
            'tes_beneficiaries': TDPApplication.objects.filter(status='Approved').count(),
            'tdp_scholars': TDPApplication.objects.count(),
        })

