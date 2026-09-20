"""URL map.

Views are imported from the module that owns them rather than through the
``student_views`` re-export surface, so this file doubles as an index of where
each area of the system lives.
"""

from django.shortcuts import redirect
from django.urls import path
from drf_spectacular.views import (
    SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView,
)

from . import health, seo, views
from . import views_analytics as analytics
from . import views_archives as archives
from . import views_auth as auth
from . import views_partner as partner
from . import views_ranking as ranking
from . import views_reports as reports
from . import views_staff as staff
from . import views_student as student
from . import views_vpsea as vpsea

urlpatterns = [
    path('', auth.landing_view),
    path('robots.txt', seo.robots_txt),
    path('healthz/', health.healthz),
    path('readyz/', health.readyz),

    path('login/', auth.login_view),
    path('logout/', auth.logout_view),
    path('register/', auth.register_view),
    path('register/received/', auth.registration_received),
    path('register/verify/<str:token>/', auth.verify_email),
    path('register/resend/', auth.resend_confirmation),

    path('student/', lambda r: redirect('/student/applications/')),
    path('student/apply/academic/', student.student_apply_academic),
    path('student/applications/', student.student_applications),
    path('student/notifications/', student.student_notifications),
    path('student/renewal/academic/', student.student_renewal_academic),
    path('student/profile/', student.student_profile),

    path('vpsea/archives/import/<int:pk>/status/',
         archives.vpsea_archive_import_status),

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

    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema')),
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema')),

    path('vpsea/', vpsea.vpsea_dashboard),
    path('vpsea/affirmative/', vpsea.vpsea_affirmative_applications),
    path('vpsea/renewals/', vpsea.vpsea_renewals),
    path('vpsea/announcements/', vpsea.vpsea_announcements),
    path('vpsea/accounts/', vpsea.vpsea_accounts),
    path('vpsea/profile/', vpsea.vpsea_profile),
    path('vpsea/students/', vpsea.vpsea_students),
    path('vpsea/students/add/', vpsea.vpsea_student_add),
    path('vpsea/students/<int:pk>/edit/', vpsea.vpsea_student_edit),
    path('vpsea/students/<int:pk>/delete/', vpsea.vpsea_student_delete),
    path('vpsea/scholarships/', vpsea.vpsea_scholarships),
    path('vpsea/scholarships/add/', vpsea.vpsea_scholarship_add),
    path('vpsea/scholarships/<int:pk>/edit/', vpsea.vpsea_scholarship_edit),
    path('vpsea/scholarships/<int:pk>/toggle/', vpsea.vpsea_scholarship_toggle),
    path('vpsea/partners/', vpsea.vpsea_partners),

    path('vpsea/archives/', archives.vpsea_archives),
    path('vpsea/archives/add/', archives.vpsea_archive_add),
    path('vpsea/archives/imported/<int:pk>/delete/', archives.vpsea_imported_delete),
    path('vpsea/archives/rollover/<int:pk>/delete/', archives.vpsea_rollover_delete),
    path('vpsea/archives/import/', archives.vpsea_archive_import),
    path('vpsea/archives/new-semester/', archives.vpsea_new_semester),
    path('vpsea/archives/undo-semester/', archives.vpsea_undo_semester),
    path('vpsea/archives/columns/', archives.vpsea_archive_columns),
    path('vpsea/archives/download/', archives.vpsea_archive_download),
    path('vpsea/archives/student/<int:pk>/edit/', archives.vpsea_student_record_edit),
    path('vpsea/archives/student/<int:pk>/delete/', archives.vpsea_student_record_delete),
    path('vpsea/archives/<int:pk>/edit/', archives.vpsea_archive_edit),
    path('vpsea/archives/<int:pk>/delete/', archives.vpsea_archive_delete),

    path('vpsea/analytics/', analytics.vpsea_analytics),

    path('vpsea/reports/', reports.vpsea_reports),
    path('vpsea/reports/preview/', reports.vpsea_report_preview_pdf),
    path('vpsea/reports/download/', reports.vpsea_report_download),
    path('vpsea/reports/download/pdf/', reports.vpsea_report_download_pdf),
    path('vpsea/reports/download/excel/', reports.vpsea_report_download_excel),

    path('vpsea/ranking/', ranking.vpsea_ranking),
    path('vpsea/ranking/download/', ranking.vpsea_ranking_download),

    path('nsu-staff/', staff.nsu_staff_dashboard),
    path('nsu-staff/apply/', staff.nsu_staff_apply),
    path('nsu-staff/applications/', staff.nsu_staff_applications),
    path('nsu-staff/profile/', staff.nsu_staff_profile),
    path('nsu-staff/notifications/', staff.nsu_staff_notifications),
    path('nsu-staff/renewal/', staff.nsu_staff_renewal),

    path('partner/', partner.partner_dashboard),
    path('partner/profile/', partner.partner_profile),
    path('partner/archives/', partner.partner_archives),
    path('partner/archives/import/', partner.partner_archive_import),
    path('partner/columns/', partner.partner_columns),
    path('partner/scholars/', partner.partner_scholars),
    path('partner/reports/download/', partner.partner_report_download),
]
