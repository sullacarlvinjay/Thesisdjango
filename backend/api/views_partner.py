"""The partner-office portal.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from .models import STUDENT_DETAILS, Scholarship
from django.db import IntegrityError, transaction
from django.http import HttpResponse
import logging
from .views_shared import COLUMN_HINTS, DUPLICATE_AWARD_NUMBERS, _change_own_password, _column_picker_context, _custom_columns_for, _posted_custom_columns, _scholar_groups, _scholars_from_sheet

logger = logging.getLogger(__name__)


def _partner_office(user):
    """The active partner office behind this account, or ``None``.

    ``None`` for a suspended office as well as for a wrong role, so
    suspending an office takes effect on the next request.
    """
    if not getattr(user, 'is_authenticated', False) or user.role != 'partner':
        return None
    office = user.partner_office
    if office is None or not office.is_active:
        return None
    return office

def _partner_required(view_fn):
    """Restrict a view to partner accounts, passing the office in.

    The office is resolved once and handed to the view, so no view has to
    remember to do it — and none can forget.
    """
    from functools import wraps

    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        """Resolve the office, or send the caller to sign in."""
        office = _partner_office(request.user)
        if office is None:
            return redirect('/login/')
        return view_fn(request, office, *args, **kwargs)
    return wrapper

def _partner_override(office, stype):
    """This office's own column choice for a programme, if it set one."""
    from .models import PartnerTableColumns

    return (PartnerTableColumns.objects
            .filter(office=office, scholarship__type=stype)
            .select_related('scholarship').first())

@_partner_required
def partner_dashboard(request, office):
    """The partner portal's landing page, one card per programme."""
    from .models import Application, ImportedScholar, SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)

    programmes = []
    for scholarship in office.scholarships.order_by('name'):
        approved = Application.objects.filter(
            status='Approved', scholarship__type=scholarship.type).count()
        imported = ImportedScholar.objects.filter(
            scholarship_type=scholarship.type, claimed_by__isnull=True).count()
        programmes.append({'scholarship': scholarship, 'total': approved + imported})

    return render(request, 'partner/dashboard.html', {
        'office': office,
        'programmes': programmes,
        'total': sum(p['total'] for p in programmes),
        'has_access': bool(programmes),
        'term': settings_obj.academic_year,
    })

@_partner_required
def partner_profile(request, office):
    """View and update a partner office's own details."""
    user = request.user
    errors = []
    saved = password_changed = False

    if request.method == 'POST':
        wanted_password = bool(request.POST.get('new_password') or
                               request.POST.get('current_password'))
        errors = _change_own_password(request, user)
        if not errors:
            user.first_name = (request.POST.get('first_name') or user.first_name).strip()
            user.last_name = (request.POST.get('last_name') or user.last_name).strip()
            if request.FILES.get('photo'):
                user.photo = request.FILES['photo']
            user.save(update_fields=['first_name', 'last_name', 'photo'])
            saved = True
            password_changed = wanted_password

    return render(request, 'partner/profile.html', {
        'office': office,
        'programmes': office.scholarships.order_by('name'),
        'saved': saved,
        'password_changed': password_changed,
        'errors': errors,
    })

@_partner_required
def partner_archives(request, office):
    """Scholar lists for the programmes this office may see."""
    from .models import Application, ImportedScholar, ScholarListImport, SystemSettings

    types = office.visible_types()
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)

    stype = request.GET.get('type', '')
    if stype not in types:
        stype = types[0] if types else ''

    labels = []
    if stype:
        labels = sorted(
            set(ScholarListImport.objects.filter(scholarship_type=stype)
                .values_list('term_label', flat=True))
            | {settings_obj.academic_year},
            reverse=True,
        )
    selected = request.GET.get('sy', settings_obj.academic_year)
    if selected not in labels:
        selected = settings_obj.academic_year

    def _display(label):
        """A programme name for the tab strip."""
        p = SystemSettings.parse_label(label)
        return f"{p['sy']} — {p['semester']}"

    active_label = settings_obj.academic_year
    history = []
    if stype:
        history = [
            {'label': lbl, 'display': _display(lbl), 'count': count}
            for lbl, count in (
                ScholarListImport.objects
                .filter(scholarship_type=stype).exclude(term_label=active_label)
                .order_by('-term_label')
                .values_list('term_label', 'scholar_count'))
        ]

    scholars, imported = [], []
    if stype:
        scholars = list(
            Application.objects
            .filter(status='Approved', scholarship__type=stype, term_label=selected)
            .select_related('student__user', 'scholarship', *STUDENT_DETAILS)
            .order_by('student__user__last_name', 'student__user__first_name'))
        imported = list(
            ImportedScholar.objects
            .filter(scholarship_type=stype, term_label=selected, claimed_by__isnull=True)
            .order_by('last_name', 'first_name'))

    override = _partner_override(office, stype) if stype else None
    groups = _scholar_groups(stype, [
        (None, scholars + imported,
         f'No {stype} scholars recorded for {selected}.'),
    ], portal='partner', override=override) if stype else {
        'columns': [], 'scholar_groups': [], 'has_custom_columns': False}

    programme = Scholarship.objects.filter(type=stype).first() if stype else None
    return render(request, 'partner/archives.html', dict(groups, **{
        'office': office,
        'archive_types': types,
        'active_type': stype,
        'all_sy': labels,
        'selected_sy': selected,
        'active_sy': active_label,
        'active_sy_display': _display(active_label),
        'selected_sy_display': _display(selected) if selected else '',
        'history': history,
        'col_hint': COLUMN_HINTS.get(stype, COLUMN_HINTS['CoScho']),
        'import_ok': request.GET.get('import_ok'),
        'import_error': request.GET.get('import_error'),
        'total': len(scholars) + len(imported),
        'uses_own_columns': override is not None,
        **(_column_picker_context(
            scholarship=override or programme, stype=stype, portal='partner')
           if stype else {}),
    }))

PARTNER_SCHOLAR_FIELDS = (
    'last_name', 'first_name', 'middle_name', 'gender', 'course',
    'student_id', 'award_number', 'congress_district',
    'barangay', 'municipality', 'province',
)

def _partner_scholar_values(posted):
    """Validate a posted scholar row.

    Returns:
        ``(values, errors)``. A year level outside 1–10 is dropped to 0
        rather than rejected, because partners' spreadsheets carry all
        sorts of things in that column and it is not worth refusing a
        scholar over.
    """
    values = {name: (posted.get(name) or '').strip()
              for name in PARTNER_SCHOLAR_FIELDS}
    errors = []

    if not values['last_name'] and not values['first_name']:
        errors.append('A scholar needs at least a first or a last name.')

    raw_year = (posted.get('year_level') or '').strip()
    values['year_level'] = 0
    if raw_year:
        if raw_year.isdigit() and 1 <= int(raw_year) <= 10:
            values['year_level'] = int(raw_year)
        else:
            errors.append('Year level must be a whole number between 1 and 10.')

    raw_gwa = (posted.get('gwa') or '').strip()
    values['gwa'] = 0.0
    if raw_gwa:
        try:
            values['gwa'] = float(raw_gwa)
        except ValueError:
            errors.append('GWA must be a number, like 1.25.')

    return values, errors

@_partner_required
def partner_scholars(request, office):
    """Add, edit and remove scholars on a partner list."""
    from urllib.parse import quote

    from .models import ActivityLog, ImportedScholar, SystemSettings

    back = '/partner/archives/'
    if request.method != 'POST':
        return redirect(back)

    p = request.POST
    stype = p.get('type', '')
    term = (p.get('sy') or '').strip()
    here = f'{back}?type={quote(stype)}' + (f'&sy={quote(term)}' if term else '')

    if stype not in office.visible_types():
        return redirect(f'{back}?error=' + quote(
            'That programme is not one this account can read.'))
    if not term:
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        term = settings_obj.academic_year
        here = f'{back}?type={quote(stype)}&sy={quote(term)}'

    action = p.get('action')

    scholar = None
    if action in ('edit', 'delete'):
        scholar = ImportedScholar.objects.filter(
            pk=p.get('scholar_id'), scholarship_type=stype,
            claimed_by__isnull=True,
        ).first()
        if not scholar:
            return redirect(f'{here}&error=' + quote(
                f'That scholar is not one this account can change. Your own '
                f'{stype} rows are; a scholar the office has matched to a BiPSU '
                'student account is theirs to correct.'))

    if action == 'delete':
        name = scholar.full_name or scholar.student_id or f'row #{scholar.pk}'
        scholar.delete()
        ActivityLog.record(
            request.user, f'{office.name} deleted the {stype} scholar {name} ({term})',
            verb='delete', request=request)
        return redirect(f'{here}&scholar=deleted')

    if action not in ('add', 'edit'):
        return redirect(f'{here}&error=' + quote('Unknown action.'))

    values, errors = _partner_scholar_values(p)
    if errors:
        return redirect(f'{here}&error=' + quote(' '.join(errors)))

    if action == 'edit':
        for field, value in values.items():
            setattr(scholar, field, value)
        scholar.save()
        ActivityLog.record(
            request.user, f'{office.name} edited the {stype} scholar '
                       f'{scholar.full_name} ({term})',
            verb='update', request=request)
        return redirect(f'{here}&scholar=saved')

    scholar = ImportedScholar.objects.create(
        scholarship_type=stype, term_label=term,
        imported_from=f'Added by {office.name}',
        **values,
    )
    ActivityLog.record(
        request.user, f'{office.name} added the {stype} scholar '
                   f'{scholar.full_name} ({term})',
        verb='create', request=request)
    return redirect(f'{here}&scholar=added')

@_partner_required
def partner_archive_import(request, office):
    """Import a partner scholar list from a spreadsheet."""
    from urllib.parse import quote

    from .models import ActivityLog, ImportedScholar, ScholarListImport, SystemSettings

    back = '/partner/archives/'
    if request.method != 'POST':
        return redirect(back)

    stype = request.POST.get('type', '')
    if stype not in office.visible_types():
        return redirect(f'{back}?error=' + quote(
            'That programme is not one this account can read.'))

    here = f'{back}?type={quote(stype)}'
    term = (request.POST.get('rollover_label') or '').strip()
    file = request.FILES.get('file')
    if not file:
        return redirect(f'{here}&import_error=' + quote('No file provided.'))
    if not term:
        return redirect(f'{here}&import_error=' + quote('A term label is required.'))

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    parsed = SystemSettings.parse_label(settings_obj.academic_year)
    term_parsed = (SystemSettings.parse_label(term) if '-' in term
                   else {'sy': term, 'semester': parsed['semester']})

    try:
        records, refused = _scholars_from_sheet(
            file, stype, term, imported_from=f'{file.name} ({office.name})',
            custom_columns=_custom_columns_for(
                stype, override=_partner_override(office, stype)))
    except Exception:
        logger.exception(
            '%s import failed for %s term %r', office.name, stype, term)
        return redirect(f'{here}&sy={quote(term)}&import_error=' + quote(
            f'That file could not be read as a {stype} list. Nothing was saved — '
            'check the column headings and try again.'))

    try:
        with transaction.atomic():
            replaced = ImportedScholar.objects.filter(
                scholarship_type=stype, term_label=term, claimed_by__isnull=True,
            ).delete()[0]
            ImportedScholar.objects.bulk_create(records)

            saved = ScholarListImport.objects.filter(
                scholarship_type=stype, term_label=term).first()
            if saved:
                saved.scholar_count = len(records)
                saved.save(update_fields=['scholar_count'])
            else:
                ScholarListImport.objects.create(
                    scholarship_type=stype,
                    school_year=term_parsed['sy'],
                    semester=term_parsed.get('semester', parsed['semester']),
                    term_label=term,
                    scholar_count=len(records),
                    imported_by=request.user,
                )
    except IntegrityError:
        logger.exception(
            '%s import repeated an award number for %s term %r',
            office.name, stype, term)
        return redirect(f'{here}&sy={quote(term)}&import_error='
                        + quote(DUPLICATE_AWARD_NUMBERS))

    ActivityLog.record(
        request.user, f'{office.name} imported {file.name} ({len(records)} rows) for '
                   f'{stype} as "{term}", replacing {replaced} of its own row(s)',
        verb='import', request=request)
    target = f'{here}&sy={quote(term)}&import_ok={len(records)}'
    if refused:
        target += f'&columns_bad={refused}'
    return redirect(target)

@_partner_required
def partner_columns(request, office):
    """Choose which columns this office sees for a programme."""
    from urllib.parse import quote

    from . import scholar_columns
    from .models import PartnerTableColumns

    back = '/partner/archives/'
    stype = (request.POST.get('type') if request.method == 'POST'
             else request.GET.get('type', '')) or ''
    if stype not in office.visible_types():
        return redirect(f'{back}?error=' + quote(
            'That programme is not one this account can read.'))

    programme = Scholarship.objects.filter(type=stype).first()
    if request.method != 'POST' or not programme:
        return redirect(f'{back}?type={quote(stype)}')

    chosen = scholar_columns.clean_choice(request.POST.getlist('table_columns'))
    if request.POST.get('action') == 'reset' or not chosen:
        PartnerTableColumns.objects.filter(office=office, scholarship=programme).delete()
        return redirect(f'{back}?type={quote(stype)}&columns=reset')

    PartnerTableColumns.objects.update_or_create(
        office=office, scholarship=programme,
        defaults={
            'table_columns': chosen,
            'extra_columns': _posted_custom_columns(request.POST),
        },
    )
    return redirect(f'{back}?type={quote(stype)}&columns=saved')

@_partner_required
def partner_report_download(request, office):
    """Download this office's scholar list as a spreadsheet."""
    from urllib.parse import quote

    from .models import SystemSettings

    stype = request.GET.get('type', '')
    if stype not in office.visible_types():
        return redirect('/partner/archives/?error=' + quote(
            'That programme is not one this account can read.'))

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    term = request.GET.get('sy', settings_obj.academic_year)
    buf, filename = _partner_workbook(office, stype, term)
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def _partner_workbook(office, stype, term):
    """Build the partner scholar spreadsheet."""
    from io import BytesIO

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font

    from . import scholar_columns
    from .models import Application, ImportedScholar

    programme = Scholarship.objects.filter(type=stype).first()
    columns = scholar_columns.resolve(
        programme, stype, 'partner', override=_partner_override(office, stype))

    records = list(
        Application.objects
        .filter(status='Approved', scholarship__type=stype, term_label=term)
        .select_related('student__user', 'scholarship', *STUDENT_DETAILS)
        .order_by('student__user__last_name', 'student__user__first_name')
    ) + list(
        ImportedScholar.objects
        .filter(scholarship_type=stype, term_label=term, claimed_by__isnull=True)
        .order_by('last_name', 'first_name')
    )

    wb = Workbook()
    ws = wb.active
    ws.title = (stype or 'Scholars')[:31]
    ws['A1'] = f'{office.name} — {stype} scholars'
    ws['A1'].font = Font(name='Arial', size=12, bold=True)
    ws['A2'] = f'Term {term}'
    ws['A2'].font = Font(name='Arial', size=10)

    head = 4
    for col, column in enumerate(columns, start=1):
        cell = ws.cell(row=head, column=col, value=column['label'])
        cell.font = Font(name='Arial', size=10, bold=True)
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        ws.column_dimensions[cell.column_letter].width = max(12, len(column['label']) + 4)

    for line, row in enumerate(scholar_columns.rows_for(records, columns), start=head + 1):
        for col, (column, cell_value) in enumerate(zip(columns, row['cells'], strict=False), start=1):
            out = ws.cell(row=line, column=col,
                          value=scholar_columns.excel_value(column, cell_value['value']))
            out.font = Font(name='Arial', size=10)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe = ''.join(c if c.isalnum() else '_' for c in f'{office.name}_{stype}_{term}')
    return buf, f'{safe}.xlsx'
