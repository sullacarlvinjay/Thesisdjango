from django.urls import path
from . import views
from . import student_views
from django.shortcuts import redirect

urlpatterns = [
    # Public landing
    path('', student_views.landing_view),

    # Auth
    path('login/', student_views.login_view),
    path('logout/', student_views.logout_view),
    path('register/', student_views.register_view),
    path('register/received/', student_views.registration_received),

    # Student portal — /student/ redirects straight to applications
    path('student/', lambda r: redirect('/student/applications/')),
    path('student/apply/tes/', student_views.student_apply_tes),
    path('student/apply/academic/', student_views.student_apply_academic),
    path('student/applications/', student_views.student_applications),
    path('student/notifications/', student_views.student_notifications),
    path('student/renewal/academic/', student_views.student_renewal_academic),
    path('student/link-scholarship/', student_views.student_link_scholarship),
    path('student/profile/', student_views.student_profile),

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
    path('api/vpsea/ranking/', views.VPSEAStudentRankingView.as_view()),
    # VPSEA portal pages
    path('vpsea/', student_views.vpsea_dashboard),
    path('vpsea/affirmative/', student_views.vpsea_affirmative_applications),
    path('vpsea/renewals/', student_views.vpsea_renewals),
    path('vpsea/link-requests/', student_views.vpsea_link_requests),
    path('vpsea/archives/', student_views.vpsea_archives),
    path('vpsea/archives/add/', student_views.vpsea_archive_add),
    path('vpsea/archives/imported/<int:pk>/delete/', student_views.vpsea_imported_delete),
    path('vpsea/archives/rollover/<int:pk>/delete/', student_views.vpsea_rollover_delete),
    path('vpsea/archives/import/', student_views.vpsea_archive_import),
    path('vpsea/archives/new-semester/', student_views.vpsea_new_semester),
    path('vpsea/archives/undo-semester/', student_views.vpsea_undo_semester),
    path('vpsea/archives/download/', student_views.vpsea_archive_download),
    path('vpsea/archives/student/<int:pk>/edit/', student_views.vpsea_student_record_edit),
    path('vpsea/archives/<int:pk>/edit/', student_views.vpsea_archive_edit),
    path('vpsea/archives/<int:pk>/delete/', student_views.vpsea_archive_delete),
    path('vpsea/analytics/', student_views.vpsea_analytics),
    path('vpsea/announcements/', student_views.vpsea_announcements),
    path('vpsea/reports/', student_views.vpsea_reports),
    path('vpsea/reports/preview/', student_views.vpsea_report_preview_pdf),
    path('vpsea/reports/download/', student_views.vpsea_report_download),
    path('vpsea/reports/download/excel/', student_views.vpsea_report_download_excel),
    path('vpsea/scholarships/', student_views.vpsea_scholarships),
    path('vpsea/scholarships/add/', student_views.vpsea_scholarship_add),
    path('vpsea/scholarships/<int:pk>/edit/', student_views.vpsea_scholarship_edit),
    path('vpsea/scholarships/<int:pk>/toggle/', student_views.vpsea_scholarship_toggle),
    path('vpsea/ranking/', student_views.vpsea_ranking),
    path('vpsea/accounts/', student_views.vpsea_accounts),
    path('vpsea/students/', student_views.vpsea_students),
    path('vpsea/students/add/', student_views.vpsea_student_add),
    path('vpsea/students/<int:pk>/edit/', student_views.vpsea_student_edit),
    path('vpsea/students/<int:pk>/delete/', student_views.vpsea_student_delete),
    # BiPSU Staff portal pages
    path('nsu-staff/', student_views.nsu_staff_dashboard),
    path('nsu-staff/apply/', student_views.nsu_staff_apply),
    path('nsu-staff/applications/', student_views.nsu_staff_applications),
    path('nsu-staff/profile/', student_views.nsu_staff_profile),
    path('nsu-staff/notifications/', student_views.nsu_staff_notifications),
    path('nsu-staff/renewal/', student_views.nsu_staff_renewal),

    # UniFAST portal pages
    path('unifast/', student_views.unifast_dashboard),
    path('unifast/archives/', student_views.unifast_archives),
    path('unifast/archives/add/', student_views.unifast_archive_add),
    path('unifast/archives/import/', student_views.unifast_archive_import),
    path('unifast/archives/rollover/<int:pk>/delete/', student_views.unifast_rollover_delete),
    path('unifast/archives/download/', student_views.unifast_archive_download),
    path('unifast/archives/<int:pk>/edit/', student_views.unifast_archive_edit),
    path('unifast/archives/<int:pk>/delete/', student_views.unifast_archive_delete),
    path('unifast/tes-applications/', student_views.unifast_tes_applications),
    path('unifast/tes-ranking/', student_views.unifast_tes_ranking),
    path('unifast/announcements/', student_views.unifast_announcements),
    path('unifast/analytics/', student_views.unifast_analytics),
    path('unifast/reports/', student_views.unifast_reports),
    path('unifast/reports/preview/', student_views.unifast_report_preview_pdf),
    path('unifast/reports/download/excel/', student_views.unifast_report_download_excel),
    path('unifast/reports/download/tes/', student_views.unifast_report_download_tes),
    path('unifast/tes-applications/<int:pk>/review/', student_views.unifast_tes_review),
    path('api/unifast/dashboard/', views.UniFASTDashboardView.as_view()),
]

# /media/ is wired in config.urls, through a view that checks who is asking.
# It is deliberately not served here: this URLconf is included first, so a
# static() fallback would shadow that check whenever DEBUG was on.
