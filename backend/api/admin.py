from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, StudentProfile, StaffProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, ImportedScholar,
    ActivityLog, SystemSettings,
    AffirmativeStaffApplication, AcademicRenewal, ScholarshipLinkRequest, ScholarListImport,
    AffirmativeEligibility, EducationalBackground, EnrollmentData, FamilyBackground,
    PersonalInformation, SocioEconomicProfile, TESEligibility,
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (('Role', {'fields': ('role',)}),)

# The detail rows edit alongside the profile rather than as seven separate
# entries in the sidebar — they are one student's record, not seven records.
STUDENT_DETAIL_MODELS = (
    EnrollmentData, PersonalInformation, AffirmativeEligibility,
    SocioEconomicProfile, TESEligibility, EducationalBackground, FamilyBackground,
)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'term_label')
    search_fields = ('student_id', 'user__last_name', 'user__first_name', 'user__email')
    inlines = [
        type(f'{model.__name__}Inline', (admin.StackedInline,),
             {'model': model, 'can_delete': False, 'extra': 0})
        for model in STUDENT_DETAIL_MODELS
    ]


admin.site.register(StaffProfile)
admin.site.register(Scholarship)
admin.site.register(Application)
admin.site.register(ApplicationDocument)
admin.site.register(Notification)
admin.site.register(Announcement)
admin.site.register(ImportedScholar)
admin.site.register(ActivityLog)
admin.site.register(SystemSettings)
admin.site.register(AffirmativeStaffApplication)
admin.site.register(AcademicRenewal)
admin.site.register(ScholarshipLinkRequest)
admin.site.register(ScholarListImport)
