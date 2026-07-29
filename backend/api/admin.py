from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, StudentProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, Renewal, ArchiveRecord,
    TDPApplication, ActivityLog, SystemSettings,
    AffirmativeNSUApplication, AcademicRenewal, ScholarshipLinkRequest, ScholarshipRollover,
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (('Role', {'fields': ('role',)}),)

admin.site.register(StudentProfile)
admin.site.register(Scholarship)
admin.site.register(Application)
admin.site.register(ApplicationDocument)
admin.site.register(Notification)
admin.site.register(Announcement)
admin.site.register(Renewal)
admin.site.register(ArchiveRecord)
admin.site.register(TDPApplication)
admin.site.register(ActivityLog)
admin.site.register(SystemSettings)
admin.site.register(AffirmativeNSUApplication)
admin.site.register(AcademicRenewal)
admin.site.register(ScholarshipLinkRequest)
admin.site.register(ScholarshipRollover)
