from django.urls import path
from . import views
from . import student_views

urlpatterns = [
    # Public landing & apply routes
    path('', student_views.landing_view),
    path('apply/register/', student_views.apply_register_view),
    path('apply/login/', student_views.apply_login_view),
    path('apply/portal/', student_views.apply_portal_view),
    path('apply/submit/', student_views.apply_submit_view),
    path('apply/logout/', student_views.apply_logout_view),
    path('apply/result/', student_views.apply_result_view),
    path('apply/submitted/', student_views.apply_submitted_view),

    # Auth
    path('login/', student_views.login_view),
    path('logout/', student_views.logout_view),
    path('register/', student_views.register_view),

    # Academic student pages only
    path('student/apply/academic/', student_views.student_apply_academic),
    path('student/applications/', student_views.student_applications),
    path('student/notifications/', student_views.student_notifications),

    # REST API
    path('api/auth/register/', views.RegisterView.as_view()),
    path('api/auth/login/', views.LoginView.as_view()),
    path('api/auth/logout/', views.LogoutView.as_view()),
    path('api/student/profile/', views.StudentProfileView.as_view()),
    path('api/student/dashboard/', views.StudentDashboardView.as_view()),
    path('api/student/scholarships/', views.ScholarshipListView.as_view()),
    path('api/student/applications/', views.StudentApplicationListCreateView.as_view()),
    path('api/student/applications/<int:pk>/', views.StudentApplicationDetailView.as_view()),
    path('api/student/notifications/', views.NotificationListView.as_view()),
    path('api/student/announcements/', views.StudentAnnouncementListView.as_view()),
    path('api/vpsea/dashboard/', views.VPSEADashboardView.as_view()),
    path('api/vpsea/applications/', views.VPSEAApplicationListView.as_view()),
    path('api/vpsea/applications/<int:pk>/', views.VPSEAApplicationDetailView.as_view()),
    path('api/vpsea/renewals/', views.VPSEARenewalListView.as_view()),
    path('api/vpsea/renewals/<int:pk>/', views.VPSEARenewalDetailView.as_view()),
    path('api/vpsea/archives/<str:type>/', views.VPSEAArchiveListView.as_view()),
    path('api/vpsea/archives/<str:type>/upload/', views.VPSEAArchiveUploadView.as_view()),
    path('api/vpsea/analytics/', views.VPSEAAnalyticsView.as_view()),
    path('api/vpsea/announcements/', views.VPSEAAnnouncementListCreateView.as_view()),
    path('api/vpsea/reports/', views.VPSEAReportsView.as_view()),
    path('api/unifast/dashboard/', views.UniFASTDashboardView.as_view()),
    path('api/unifast/tdp/', views.UniFASTTDPListView.as_view()),
    path('api/unifast/tdp/<int:pk>/', views.UniFASTTDPDetailView.as_view()),
    path('api/unifast/tes/', views.UniFASTTESView.as_view()),
    path('api/unifast/continuing/', views.UniFASTContinuingView.as_view()),
    path('api/unifast/billing/', views.UniFASTBillingListView.as_view()),
    path('api/unifast/distribution/', views.UniFASTDistributionView.as_view()),
    path('api/unifast/liquidation/', views.UniFASTLiquidationListView.as_view()),
    path('api/unifast/fhe/', views.UniFASTFHEView.as_view()),
    path('api/unifast/fhe/upload/', views.UniFASTFHEUploadView.as_view()),
    path('api/unifast/analytics/', views.UniFASTAnalyticsView.as_view()),
    path('api/unifast/reports/', views.UniFASTReportsView.as_view()),
    path('api/super/dashboard/', views.SuperDashboardView.as_view()),
    path('api/super/users/', views.SuperUserListCreateView.as_view()),
    path('api/super/users/<int:pk>/', views.SuperUserDetailView.as_view()),
    path('api/super/offices/', views.SuperOfficeListView.as_view()),
    path('api/super/categories/', views.SuperCategoryListView.as_view()),
    path('api/super/announcements/', views.SuperAnnouncementListCreateView.as_view()),
    path('api/super/logs/', views.SuperLogsView.as_view()),
    path('api/super/settings/', views.SuperSettingsView.as_view()),
]
