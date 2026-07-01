from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.db.models import Count
from .models import (
    User, StudentProfile, Scholarship, Application, Notification,
    Announcement, Renewal, ArchiveRecord, BillingRecord, LiquidationRecord,
    TDPApplication, Office, ActivityLog, SystemSettings,
)
from .serializers import (
    RegisterSerializer, LoginSerializer, StudentProfileSerializer,
    ScholarshipSerializer, ApplicationSerializer, NotificationSerializer,
    AnnouncementSerializer, RenewalSerializer, ArchiveRecordSerializer,
    BillingRecordSerializer, LiquidationRecordSerializer, TDPApplicationSerializer,
    OfficeSerializer, ActivityLogSerializer, SystemSettingsSerializer,
    AdminUserSerializer,
)


# ── Auth ──────────────────────────────────────────────────────────────────────

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
    def get(self, request):
        from .models import AffirmativeNSUApplication
        scholarship_type = request.query_params.get('type', 'Affirmative')
        if scholarship_type not in ('Affirmative', 'Staff'):
            scholarship_type = 'Affirmative'
        applicants = AffirmativeNSUApplication.objects.exclude(status='Approved').filter(
            qualified_for=scholarship_type
        )
        def score(a):
            if scholarship_type == 'Affirmative':
                s = 0
                if a.shs_gpa: s += min((a.shs_gpa / 100) * 50, 50)
                if a.suc_exam_score: s += min((a.suc_exam_score / 100) * 50, 50)
                return round(s)
            return 100 if a.is_nsu_staff else 75
        ranked = sorted(applicants, key=score, reverse=True)
        return Response([{
            'rank': i + 1, 'name': a.full_name, 'course': a.course,
            'year_level': a.year_level, 'shs_gpa': a.shs_gpa,
            'suc_exam_score': a.suc_exam_score, 'score': score(a),
        } for i, a in enumerate(ranked)])


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
    serializer_class = RenewalSerializer
    queryset = Renewal.objects.select_related('student__user', 'scholarship').all()


class VPSEARenewalDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = RenewalSerializer
    queryset = Renewal.objects.all()


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


# ── UniFAST ───────────────────────────────────────────────────────────────────

class UniFASTTDPListView(generics.ListAPIView):
    serializer_class = TDPApplicationSerializer
    queryset = TDPApplication.objects.select_related('student__user').all()


class UniFASTTDPDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = TDPApplicationSerializer
    queryset = TDPApplication.objects.all()

    def perform_update(self, serializer):
        tdp = serializer.save()
        ActivityLog.objects.create(
            user=self.request.user,
            action=f"Updated TDP application {tdp.id} to {tdp.status}"
        )


class UniFASTTESView(APIView):
    def get(self, request):
        return Response([
            {'title': 'Continuing TES Grantees', 'desc': f"{Application.objects.filter(status='Approved').count()} grantees rolled over.", 'status': 'done'},
            {'title': 'TES Regular Applicants', 'desc': f"{Application.objects.filter(status='Pending Validation').count()} new applicants screened.", 'status': 'done'},
            {'title': 'Validation Process', 'desc': 'Document & eligibility verification.', 'status': 'active'},
            {'title': 'Billing Preparation', 'desc': 'Generating billing templates.', 'status': 'upcoming'},
            {'title': 'Distribution', 'desc': 'Fund release to grantees.', 'status': 'upcoming'},
            {'title': 'Liquidation', 'desc': 'Final liquidation submitted to UniFAST.', 'status': 'upcoming'},
        ])


class UniFASTContinuingView(generics.ListAPIView):
    serializer_class = TDPApplicationSerializer

    def get_queryset(self):
        return TDPApplication.objects.filter(status='Approved').select_related('student__user')


class UniFASTBillingListView(generics.ListAPIView):
    serializer_class = BillingRecordSerializer
    queryset = BillingRecord.objects.all()


class UniFASTDistributionView(APIView):
    def get(self, request):
        return Response({
            'released_funds': '₱3.45M',
            'liquidated': '₱2.86M',
            'pending': '₱590K',
            'schedule': [
                {'batch': 'Batch 1 — Apr 15', 'count': 412, 'status': 'Released', 'pct': 100},
                {'batch': 'Batch 2 — May 03', 'count': 286, 'status': 'Claiming', 'pct': 78},
                {'batch': 'Batch 3 — May 20', 'count': 318, 'status': 'Scheduled', 'pct': 0},
            ],
        })


class UniFASTLiquidationListView(generics.ListAPIView):
    serializer_class = LiquidationRecordSerializer
    queryset = LiquidationRecord.objects.all()


class UniFASTFHEView(APIView):
    def get(self, request):
        from .models import StudentProfile
        enrolled = StudentProfile.objects.count()
        return Response({
            'fhe_eligible': enrolled,
            'enrolled': round(enrolled * 0.91),
            'pending_billing': round(enrolled * 0.09),
            'enrollment_by_course': list(
                StudentProfile.objects.values('course').annotate(count=Count('id'))
            ),
        })


class UniFASTFHEUploadView(APIView):
    def post(self, request):
        file = request.FILES.get('file')
        if not file:
            return Response({'error': 'No file provided'}, status=400)
        ActivityLog.objects.create(user=request.user, action=f"Uploaded FHE template: {file.name}")
        return Response({'status': 'Imported', 'file': file.name})


class UniFASTAnalyticsView(APIView):
    def get(self, request):
        from .models import BillingRecord
        billing = BillingRecord.objects.values('semester').annotate(
            submitted=Count('id'),
        )
        return Response({
            'tes_disbursement': [
                {'semester': '1st 2023', 'amount': 2400000},
                {'semester': '2nd 2023', 'amount': 2650000},
                {'semester': '1st 2024', 'amount': 2890000},
                {'semester': '2nd 2024', 'amount': 3120000},
                {'semester': '1st 2025', 'amount': 3450000},
            ],
            'billing_progress': list(billing),
        })


class UniFASTReportsView(APIView):
    def get(self, request):
        return Response([
            {'name': 'TES Disbursement Summary', 'desc': 'Per-semester TES release breakdown.', 'size': '1.2 MB'},
            {'name': 'TDP Compliance Report', 'desc': 'Compliance with UniFAST guidelines.', 'size': '920 KB'},
            {'name': 'FHE Utilization Report', 'desc': 'Free Higher Education enrollment metrics.', 'size': '740 KB'},
        ])


class UniFASTDashboardView(APIView):
    def get(self, request):
        return Response({
            'tes_beneficiaries': TDPApplication.objects.filter(status='Approved').count(),
            'tdp_scholars': TDPApplication.objects.count(),
            'billing_approved_pct': 92,
            'pending_liquidation': LiquidationRecord.objects.filter(status='Pending Validation').count(),
        })


# ── Super Admin ───────────────────────────────────────────────────────────────

class SuperUserListCreateView(generics.ListCreateAPIView):
    serializer_class = AdminUserSerializer
    queryset = User.objects.all()

    def perform_create(self, serializer):
        user = serializer.save()
        ActivityLog.objects.create(user=self.request.user, action=f"Created user {user.email}")


class SuperUserDetailView(generics.RetrieveUpdateAPIView):
    serializer_class = AdminUserSerializer
    queryset = User.objects.all()


class SuperOfficeListView(generics.ListAPIView):
    serializer_class = OfficeSerializer
    queryset = Office.objects.all()


class SuperCategoryListView(generics.ListAPIView):
    serializer_class = ScholarshipSerializer
    queryset = Scholarship.objects.all()

    def get_serializer_context(self):
        return {'request': self.request}


class SuperAnnouncementListCreateView(generics.ListCreateAPIView):
    serializer_class = AnnouncementSerializer
    queryset = Announcement.objects.all().order_by('-created_at')

    def perform_create(self, serializer):
        ann = serializer.save(published_by=self.request.user)
        ActivityLog.objects.create(user=self.request.user, action=f"Published system-wide announcement: {ann.title}")


class SuperLogsView(generics.ListAPIView):
    serializer_class = ActivityLogSerializer
    queryset = ActivityLog.objects.all()


class SuperSettingsView(APIView):
    def get(self, request):
        settings, _ = SystemSettings.objects.get_or_create(pk=1)
        return Response(SystemSettingsSerializer(settings).data)

    def patch(self, request):
        settings, _ = SystemSettings.objects.get_or_create(pk=1)
        serializer = SystemSettingsSerializer(settings, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        ActivityLog.objects.create(user=request.user, action="Updated system settings")
        return Response(serializer.data)


class SuperDashboardView(APIView):
    def get(self, request):
        return Response({
            'total_users': User.objects.count(),
            'office_accounts': Office.objects.count(),
            'scholarship_programs': Scholarship.objects.filter(is_active=True).count(),
            'activity_24h': ActivityLog.objects.count(),
            'recent_users': AdminUserSerializer(User.objects.order_by('-date_joined')[:5], many=True).data,
        })


# ── Helpers ───────────────────────────────────────────────────────────────────

def _approval_trend():
    from django.utils import timezone
    import calendar
    months = []
    now = timezone.now()
    for i in range(5, -1, -1):
        m = (now.month - i - 1) % 12 + 1
        y = now.year if now.month - i > 0 else now.year - 1
        approved = Application.objects.filter(submitted_at__month=m, submitted_at__year=y, status='Approved').count()
        rejected = Application.objects.filter(submitted_at__month=m, submitted_at__year=y, status='Rejected').count()
        months.append({'month': calendar.month_abbr[m], 'approved': approved, 'rejected': rejected})
    return months
