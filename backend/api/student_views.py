"""Backwards-compatible surface for the former monolithic view module.

The views themselves now live in ``views_auth``, ``views_student``,
``views_staff``, ``views_partner``, ``views_vpsea``, ``views_archives``,
``views_analytics``, ``views_reports``, ``views_ranking``,
``views_declarations`` and ``views_shared``. This module re-exports every
name they define so that ``api.urls`` and the test suite keep importing
from one place while the code itself stays split.
"""

from .views_shared import (  # noqa: F401
    CHED_ARCHIVE_TIERS, COLUMN_HINTS, COLUMN_MAPS, DECLARATION_SLOTS,
    _active_term, _cell_for_custom_column, _change_own_password,
    _column_picker_context, _custom_columns_for, _declaration_slots,
    _declared_scholarship, _declared_scholarships, _disability_answer,
    _disability_fields, _positive_int, _posted_custom_columns, _safe_next,
    _scholar_groups, _scholars_from_sheet, _scholars_from_worksheet,
    _sheet_custom_columns, _tristate, _unanswered, _validate_proof,
    _vpsea_required, application_window_reason, can_hold_alongside,
    declarable_types, held_scholarship_types,
)
from .views_auth import (  # noqa: F401
    PORTAL_FOR_ROLE, SIGN_IN_REFUSED, _REQUIRED_AFFIRMATIVE_ANSWERS,
    _REQUIRED_CERTIFICATES, _REQUIRED_ELIGIBILITY, _REQUIRED_OF_AN_APPLICANT,
    _REQUIRED_OF_A_STUDENT, _REQUIRED_OF_EVERYONE, _REQUIRED_OF_STAFF,
    _REQUIRED_TES_ANSWERS, _active_catalogue, _await_verification,
    _certificate_errors, _decimal_or, _declared_staff_scholarship,
    _missing_certificates, _portal_for, _register_context,
    _registration_profile_fields, _release_rejected_registration,
    _remember_registration_source, _sign_in_error, _unanswered_tes,
    _utm_payload, landing_view, login_view, logout_view, register_view,
    registration_received, resend_confirmation, verify_email,
)
from .views_student import (  # noqa: F401
    GWA_REQUIRED, _APPLY_ACADEMIC_DOCUMENTS, _APPLY_ACADEMIC_FROM_PROFILE,
    _APPLY_ACADEMIC_TYPED, _apply_academic_errors, _apply_academic_values,
    _gwa_for_display, _is_enrolled, _missing_documents,
    _missing_from_profile, _parse_gwa, _renewable_programmes,
    _scholarship_records, _system_settings, declaration_blocked_reason,
    renewal_window_reason, scholarship_block_reason, student_applications,
    student_apply_academic, student_dashboard, student_notifications,
    student_profile, student_renewal_academic,
)
from .views_staff import (  # noqa: F401
    _nsu_staff_enrolled, _nsu_staff_required, _parse_date, _pick, _pick_date,
    _staff_application_for, _staff_profile, nsu_staff_applications,
    nsu_staff_apply, nsu_staff_dashboard, nsu_staff_notifications,
    nsu_staff_profile, nsu_staff_renewal,
)
from .views_partner import (  # noqa: F401
    PARTNER_SCHOLAR_FIELDS, _partner_office, _partner_override,
    _partner_required, _partner_scholar_values, _partner_workbook,
    partner_archive_import, partner_archives, partner_columns,
    partner_dashboard, partner_profile, partner_report_download,
    partner_scholars,
)
from .views_declarations import (  # noqa: F401
    _approve_dependent_staff_declaration, _archive_back,
    approve_declared_scholarship, approve_declared_staff_scholarship,
    declared_scholarships, declared_staff_scholarship, pending_declarations,
    reject_declared_scholarship, reject_declared_staff_scholarship,
)
from .views_archives import (  # noqa: F401
    STUDENT_RECORD_FIELDS, UNAWARDED_TAB, _BAD_SHEET_CHARS,
    _apply_student_record_edits, _archive_candidates, _archive_records,
    _archive_tabs, _archive_term, _archive_terms,
    _delete_import_with_scholars, _rollover_fields, _rollover_workbook,
    _save_column_values, _sheet_name, _unawarded_rows, vpsea_archive_add,
    vpsea_archive_columns, vpsea_archive_delete, vpsea_archive_download,
    vpsea_archive_edit, vpsea_archive_import, vpsea_archives,
    vpsea_imported_delete, vpsea_new_semester, vpsea_rollover_delete,
    vpsea_student_record_delete, vpsea_student_record_edit,
    vpsea_undo_semester,
)
from .views_analytics import (  # noqa: F401
    _analytics_context, _analytics_data_version, _build_analytics_context,
    vpsea_analytics,
)
from .views_reports import (  # noqa: F401
    _report_term, vpsea_report_download, vpsea_report_download_excel,
    vpsea_report_preview_pdf, vpsea_reports,
)
from .views_ranking import (  # noqa: F401
    RANKING_TABS, _affirmative_ranking_data, _staff_ranking_data,
    _tes_ranking_data, _vpsea_staff_ranking, _vpsea_tes_ranking,
    vpsea_ranking, vpsea_ranking_download,
)
from .views_vpsea import (  # noqa: F401
    WINDOW_KINDS, _column_name_errors, _decide_added_scholarship, _doc_list,
    _enrollment_fields, _posted_logo, _posted_partner_scholarships,
    _posted_window, _save_window, _window_card_context,
    vpsea_accounts, vpsea_affirmative_applications, vpsea_announcements,
    vpsea_dashboard, vpsea_partners, vpsea_profile, vpsea_renewals,
    vpsea_scholarship_add, vpsea_scholarship_edit, vpsea_scholarship_toggle,
    vpsea_scholarships, vpsea_student_add, vpsea_student_delete,
    vpsea_student_edit, vpsea_students,
)
