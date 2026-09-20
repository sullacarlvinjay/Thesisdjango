"""Django admin registrations.

The profile models keep most of their fields in satellite tables, so each one
registers those tables as inlines — without that the admin shows a record with
almost nothing on it.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import (
    User, StudentProfile, StaffProfile, Scholarship, Application, ApplicationDocument,
    Notification, Announcement, ImportedScholar,
    ActivityLog, SystemSettings, SignupSource,
    ApplicantRecord, AcademicRenewal, ScholarshipLinkRequest, ScholarListImport,
    AffirmativeEligibility, EducationalBackground, EnrollmentData, FamilyBackground,
    PersonalInformation, SocioEconomicProfile, TESEligibility,
    StaffEducation, StaffEmployment, StaffPersonalInformation,
    ApplicantAffirmativeEligibility, ApplicantEmployment, ApplicantEnrollment,
    ApplicantInformation, ApplicantStaffEligibility,
)

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Accounts, with the role and verification fields exposed."""
    fieldsets = BaseUserAdmin.fieldsets + (('Role', {'fields': ('role',)}),)

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
    """Build inline admins for a model's satellite detail tables.

    The profile models spread their fields across several one-to-one
    tables, so without this the admin shows a record with almost nothing
    on it.
    """
    return [
        type(f'{model.__name__}Inline', (admin.StackedInline,),
             {'model': model, 'can_delete': False, 'extra': 0})
        for model in models
    ]


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    """Student records, with their detail tables inline."""
    list_display = ('student_id', 'user', 'term_label')
    search_fields = ('student_id', 'user__last_name', 'user__first_name', 'user__email')
    inlines = detail_inlines(STUDENT_DETAIL_MODELS)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    """Employee records, with their detail tables inline."""
    list_display = ('employee_id', 'user')
    search_fields = ('employee_id', 'user__last_name', 'user__first_name', 'user__email')
    inlines = detail_inlines(STAFF_DETAIL_MODELS)
admin.site.register(Scholarship)
admin.site.register(Application)
admin.site.register(ApplicationDocument)
admin.site.register(Notification)
admin.site.register(Announcement)
admin.site.register(ImportedScholar)
@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """Who did what, when, and to which record.

    Read-only on purpose. An audit trail an administrator can edit answers a
    weaker question than one they cannot, so the add, change and delete
    permissions are all refused here — including for a superuser. Entries are
    written by ``ActivityLog.record`` and by nothing else.
    """
    list_display = ('created_at', 'actor', 'verb', 'target_type',
                    'target_label', 'ip_address')
    list_filter = ('verb', 'target_type', 'created_at', 'user__role')
    search_fields = ('action', 'target_label', 'target_id',
                     'user__email', 'user__first_name', 'user__last_name')
    date_hierarchy = 'created_at'
    list_select_related = ('user',)
    ordering = ('-created_at',)
    list_per_page = 50

    @admin.display(description='Who', ordering='user__email')
    def actor(self, entry):
        """The account that acted, named as an administrator would recognise it."""
        if entry.user is None:
            return 'the system'
        who = entry.user.get_full_name() or entry.user.email
        return f'{who} ({entry.user.get_role_display()})'

    def has_add_permission(self, request):
        """Nobody writes an audit entry by hand."""
        return False

    def has_change_permission(self, request, obj=None):
        """An entry that can be edited is not evidence."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Entries are kept, not pruned from the admin."""
        return False


admin.site.register(SystemSettings)
@admin.register(ApplicantRecord)
class ApplicantRecordAdmin(admin.ModelAdmin):
    """Affirmative, staff and imported scholar records."""
    list_display = ('full_name', 'qualified_for', 'status', 'term_label')
    list_filter = ('qualified_for', 'status')
    search_fields = ('full_name', 'email')
    inlines = detail_inlines(STAFF_APPLICATION_DETAIL_MODELS)

@admin.register(SignupSource)
class SignupSourceAdmin(admin.ModelAdmin):
    """Where registrations came from, read-only."""
    list_display = ('email', 'kind', 'campaign_label', 'is_active', 'created_at')
    list_filter = ('kind', 'is_active', 'utm_source', 'utm_medium')
    search_fields = ('email', 'utm_campaign', 'utm_source')
    readonly_fields = ('created_at', 'updated_at')


admin.site.register(AcademicRenewal)
admin.site.register(ScholarshipLinkRequest)
admin.site.register(ScholarListImport)
