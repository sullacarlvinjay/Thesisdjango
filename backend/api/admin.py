from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, StudentProfile, StaffProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, ImportedScholar,
    ActivityLog, SystemSettings,
    AffirmativeStaffApplication, AcademicRenewal, ScholarshipLinkRequest, ScholarListImport,
    AffirmativeEligibility, EducationalBackground, EnrollmentData, FamilyBackground,
    PersonalInformation, SocioEconomicProfile, TESEligibility,
    StaffEducation, StaffEmployment, StaffPersonalInformation,
    ApplicantAffirmativeEligibility, ApplicantEmployment, ApplicantEnrollment,
    ApplicantInformation, ApplicantStaffEligibility,
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (('Role', {'fields': ('role',)}),)

# The detail rows edit alongside the record they belong to rather than as
# separate entries in the sidebar — they are one student's record, not seven
# records, and one employee's record, not three.
STUDENT_DETAIL_MODELS = (
    EnrollmentData, PersonalInformation, AffirmativeEligibility,
    SocioEconomicProfile, TESEligibility, EducationalBackground, FamilyBackground,
)

STAFF_DETAIL_MODELS = (
    StaffEmployment, StaffPersonalInformation, StaffEducation,
)

STAFF_APPLICATION_DETAIL_MODELS = (
    ApplicantInformation, ApplicantEnrollment, ApplicantStaffEligibility,
    ApplicantEmployment, ApplicantAffirmativeEligibility,
)


def detail_inlines(models):
    """A StackedInline per detail model, built rather than written out.

    ``can_delete=False`` because a detail row is part of its parent record: a
    missing one reads as the defaults a fresh one would hold, so deleting it
    from the admin looks like clearing a group and is really removing the row
    every other screen expects to be there.
    """
    return [
        type(f'{model.__name__}Inline', (admin.StackedInline,),
             {'model': model, 'can_delete': False, 'extra': 0})
        for model in models
    ]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'user', 'term_label')
    search_fields = ('student_id', 'user__last_name', 'user__first_name', 'user__email')
    inlines = detail_inlines(STUDENT_DETAIL_MODELS)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'user')
    search_fields = ('employee_id', 'user__last_name', 'user__first_name', 'user__email')
    inlines = detail_inlines(STAFF_DETAIL_MODELS)
admin.site.register(Scholarship)
admin.site.register(Application)
admin.site.register(ApplicationDocument)
admin.site.register(Notification)
admin.site.register(Announcement)
admin.site.register(ImportedScholar)
admin.site.register(ActivityLog)
admin.site.register(SystemSettings)
@admin.register(AffirmativeStaffApplication)
class AffirmativeStaffApplicationAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'qualified_for', 'status', 'term_label')
    list_filter = ('qualified_for', 'status')
    search_fields = ('full_name', 'email')
    inlines = detail_inlines(STAFF_APPLICATION_DETAIL_MODELS)

admin.site.register(AcademicRenewal)
admin.site.register(ScholarshipLinkRequest)
admin.site.register(ScholarListImport)
