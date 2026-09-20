"""Masterlist report rendering and download.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from django.views.decorators.clickjacking import xframe_options_exempt
from .models import STAFF_APPLICATION_DETAILS, STUDENT_DETAILS, split_ched
from django.http import HttpResponse
import logging
from .views_shared import _vpsea_required

logger = logging.getLogger(__name__)


def _report_term(request):
    """The term being reported on, parsed, plus the full list on offer.

    Returns:
        ``(label, parsed, display)``.
    """
    from .models import SystemSettings
    from . import masterlist_report
    label = masterlist_report.term_for(request.GET.get('sy'))
    display = [(term, '{sy} — {semester}'.format(
                    **SystemSettings.parse_label(term)))
               for term in masterlist_report.known_terms()]
    return label, SystemSettings.parse_label(label), display

@_vpsea_required
def vpsea_reports(request):
    """The reports page: per-programme totals and the downloads."""
    import os
    from .models import SystemSettings
    from . import doc_convert, masterlist_report

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    label, parsed, all_sy_display = _report_term(request)
    context, summary = masterlist_report.build_context(term_label=label)

    sections = []
    for entry in summary:
        slot = context[entry['slot']]
        gendered = entry['layout'] == 'gendered'
        headers = entry['headers']

        def cells(rows, headers=headers):
            return [masterlist_report.cells_for(r, headers) for r in rows]

        sections.append((
            entry['heading'],
            headers,
            cells(slot['female'] if gendered else slot['students']),
            cells(slot['male']) if gendered else [],
            gendered,
            entry['key'].lower(),
        ))

    active = SystemSettings.parse_label(settings_obj.academic_year)
    return render(request, 'vpsea/reports.html', {
        'sections': sections,
        'semester': parsed['semester'],
        'ay': parsed['sy'],
        'all_sy_display': all_sy_display,
        'selected_sy': label,
        'is_active_term': label == settings_obj.academic_year,
        'active_sy_display': f"{active['sy']} — {active['semester']}",
        'grand_total': sum(e['total'] for e in summary),
        'summary': summary,
        'template_available': os.path.exists(masterlist_report.TEMPLATE_PATH),
        'exact_preview': doc_convert.available(),
        'error': request.GET.get('error'),
    })

def _requested_programme(request):
    """The programme key from ``?type=``, or ``None`` for the whole masterlist.

    Validated against the slot table rather than trusted, so an unknown value
    falls back to the full report instead of silently producing an empty one.
    """
    from . import masterlist_report
    wanted = (request.GET.get('type') or '').strip()
    keys = {key for _slot, _heading, key, _layout in masterlist_report.PROGRAM_SLOTS}
    return wanted if wanted in keys else None


def _programme_filename(term, only):
    """The download filename for a term, and a programme if given."""
    stem = 'BiPSU_List_of_Scholars'
    if only:
        stem = f'{stem}_{only.replace(" ", "_")}'
    return f'{stem}_{term.replace("-", "_")}'


@_vpsea_required
def vpsea_report_download_pdf(request):
    """Download the masterlist as PDF, for one programme or for all of them.

    Asked for by the office: a single combined list is unwieldy when only one
    programme's scholars need to be submitted, and splitting it by hand
    afterwards invites the wrong page going to the wrong agency.
    """
    from . import report_pdf

    term, parsed, _display = _report_term(request)
    only = _requested_programme(request)
    buf, _summary = report_pdf.masterlist_pdf(
        parsed['sy'], parsed['semester'], term_label=term, only=only)

    response = HttpResponse(buf.read(), content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{_programme_filename(term, only)}.pdf"')
    return response


@_vpsea_required
@xframe_options_exempt
def vpsea_report_preview_pdf(request):
    """Render the masterlist inline as a PDF.

    Prefers LibreOffice, which renders the office's own DOCX template
    exactly. Falls back to the ReportLab layout when LibreOffice is absent
    — as it is on the deployed container — and always for a single
    programme, which the template cannot express.
    """
    from . import doc_convert, masterlist_report, report_pdf

    term, parsed, _display = _report_term(request)
    only = _requested_programme(request)
    label = term.replace('-', '_')

    pdf = None
    if doc_convert.available() and not only:
        try:
            buf, _summary = masterlist_report.build_document(
                parsed['sy'], parsed['semester'], term_label=term)
            pdf = doc_convert.to_pdf(buf.getvalue(), '.docx')
        except (FileNotFoundError, doc_convert.ConversionUnavailable,
                doc_convert.ConversionFailed):
            pdf = None
    if pdf is None:
        buf, _summary = report_pdf.masterlist_pdf(
            parsed['sy'], parsed['semester'], term_label=term, only=only)
        pdf = buf.read()

    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = (
        f'inline; filename="BiPSU_List_of_Scholars_{label}.pdf"')
    return response

@_vpsea_required
def vpsea_report_download(request):
    """Download the masterlist as a DOCX."""
    from . import masterlist_report

    term, parsed, _display = _report_term(request)
    try:
        buf, _summary = masterlist_report.build_document(
            parsed['sy'], parsed['semester'], term_label=term)
    except FileNotFoundError as exc:
        from urllib.parse import quote
        return redirect(f'/vpsea/reports/?sy={quote(term)}&error={quote(str(exc))}')

    label = term.replace('-', '_')
    filename = f'BiPSU_List_of_Scholars_{label}.docx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

@_vpsea_required
def vpsea_report_download_excel(request):
    """The masterlist as a spreadsheet, for the term the office selected.

    Each programme is queried separately here rather than through
    ``masterlist_report._sources``, because the rows are read as ``Application``
    objects — reaching through ``student.user`` for names — while that helper
    also returns ``ImportedScholar`` rows, which carry their own. Every filter
    below is scoped to ``term``; they were not, and the sheet carried every
    approved award ever made under a heading naming one semester.
    """
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from io import BytesIO
    from django.http import HttpResponse
    from .models import Application, ApplicantRecord

    term, parsed, _display = _report_term(request)
    semester = parsed['semester']
    ay = parsed['sy']

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = 'Scholars'

    thin = Side(style='thin')
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    center = Alignment(horizontal='center', vertical='center', wrap_text=True)
    header_font = Font(bold=True, size=9)
    header_fill = PatternFill('solid', fgColor='D9E1F2')
    section_fill = PatternFill('solid', fgColor='BDD7EE')
    title_fill = PatternFill('solid', fgColor='1F4E79')
    title_font = Font(bold=True, size=11, color='FFFFFF')

    current_row = [1]

    def write_title(text, ncols):
        """Write the merged title row."""
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = title_font
        cell.fill = title_fill
        cell.alignment = center
        cell.border = border
        ws.row_dimensions[r].height = 18
        current_row[0] += 1

    def write_section(text, ncols):
        """Write a programme's section heading."""
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = Font(bold=True, size=10)
        cell.fill = section_fill
        cell.alignment = center
        cell.border = border
        current_row[0] += 1

    def write_gender_label(text, ncols):
        """Write the FEMALE or MALE band label."""
        r = current_row[0]
        ws.cell(row=r, column=1, value=text)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=ncols)
        cell = ws.cell(row=r, column=1)
        cell.font = Font(bold=True, size=9)
        cell.alignment = Alignment(horizontal='left', vertical='center')
        current_row[0] += 1

    def write_headers(headers):
        """Write a header row."""
        r = current_row[0]
        for ci, h in enumerate(headers, 1):
            cell = ws.cell(row=r, column=ci, value=h)
            cell.font = header_font
            cell.fill = header_fill
            cell.border = border
            cell.alignment = center
        current_row[0] += 1

    def write_rows(rows_data):
        """Write a block of scholar rows."""
        for row_vals in rows_data:
            r = current_row[0]
            for ci, val in enumerate(row_vals, 1):
                cell = ws.cell(row=r, column=ci, value=val)
                cell.border = border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
                cell.font = Font(size=9)
            current_row[0] += 1

    def blank_row():
        """An empty row of the right width, for spacing."""
        current_row[0] += 1

    def _split_name(full_name):
        """Split a single full name into last, first and middle."""
        parts = full_name.strip().split()
        if len(parts) == 0: return ('', '', '')
        if len(parts) == 1: return (parts[0], '', '')
        if len(parts) == 2: return (parts[-1], parts[0], '')
        last = parts[-1]; first = parts[0]
        middle = ' '.join(parts[1:-1])
        return (last, first, middle[0] + '.' if middle else '')

    def _name_parts(user):
        """Name cells for a record, whichever shape it arrived in."""
        return (user.last_name or '', user.first_name or '', '')

    def addr_parts(addr):
        """Barangay, municipality and province as separate cells."""
        parts = [x.strip() for x in (addr or '').split(',')]
        return (parts[0] if len(parts) > 0 else '',
                parts[1] if len(parts) > 1 else '',
                parts[2] if len(parts) > 2 else '')

    MAX_COLS = 13

    write_title('Republic of the Philippines', MAX_COLS)
    write_title('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran', MAX_COLS)
    write_title(f'LIST OF SCHOLARS FOR {semester} SY: {ay}', MAX_COLS)
    blank_row()

    academic = list(Application.objects.filter(
        status='Approved', scholarship__type='Academic', term_label=term
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    females_a = [a for a in academic if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    female_pks_a = {a.pk for a in females_a}
    males_a   = [a for a in academic if a.pk not in female_pks_a]

    headers_acad = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'COURSE', 'YR.', 'GWA', '%', 'SCHOLARSHIP PROGRAM']
    write_section(f'ACADEMIC (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_acad))

    def acad_rows(apps):
        """Rows for the Academic section."""
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            pct = 'University Scholar' if p.gwa <= 1.29 else ('College Scholars' if p.gwa <= 1.50 else '')
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, p.course, p.year_level, p.gwa, pct, 'ACADEMIC'])
        return rows

    write_gender_label('FEMALE', len(headers_acad))
    write_headers(headers_acad)
    write_rows(acad_rows(females_a))
    write_gender_label('MALE', len(headers_acad))
    write_headers(headers_acad)
    write_rows(acad_rows(males_a))
    blank_row()

    staff = list(ApplicantRecord.objects.filter(
        status='Approved', qualified_for='Staff', term_label=term
    ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name'))
    headers_staff = ['NO.', 'LAST NAME', 'FIRST NAME', 'M.I.', 'SEX', 'COURSE', 'YEAR LEVEL', 'STUDENT NUMBER', '%', 'SCHOLARSHIP PROGRAM']
    write_section(f'BiPSU STAFF (@) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_staff))
    write_headers(headers_staff)
    staff_rows = []
    for i, app in enumerate(staff, 1):
        last, first, mi = _split_name(app.full_name)
        pct = '100' if app.is_nsu_staff else '75'
        staff_rows.append([i, last, first, mi, app.gender or '', app.course, app.year_level, app.student_id or '', pct, 'BiPSU STAFF SCHOLARSHIP'])
    write_rows(staff_rows)
    blank_row()

    affirmative = list(ApplicantRecord.objects.filter(
        status='Approved', qualified_for='Affirmative', term_label=term
    ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name'))
    aff_females = [a for a in affirmative if a.gender and a.gender.upper() in ('F', 'FEMALE')]
    female_pks  = {a.pk for a in aff_females}
    aff_males   = [a for a in affirmative if a.pk not in female_pks]
    headers_aff = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'AFFIRMATIVE ACTION (*) SCHOLARSHIP GRANT — {semester} SY: {ay}',
                  len(headers_aff))

    def aff_rows(apps):
        """Rows for the Affirmative and Staff sections."""
        rows = []
        for i, app in enumerate(apps, 1):
            last, first, mi = _split_name(app.full_name)
            brgy, mun, prov = addr_parts(app.address)
            rows.append([i, '', last, first, mi, app.gender or '', brgy, mun, prov, '', app.course, app.year_level, 'Affirmative Action Scholarship'])
        return rows

    write_gender_label('FEMALE', len(headers_aff))
    write_headers(headers_aff)
    write_rows(aff_rows(aff_females))
    write_gender_label('MALE', len(headers_aff))
    write_headers(headers_aff)
    write_rows(aff_rows(aff_males))
    blank_row()

    ched_all = list(Application.objects.filter(
        status='Approved', scholarship__type='CHED', term_label=term
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    ched_full, ched_half = split_ched(ched_all)
    headers_ched = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']

    def ched_rows(apps):
        """Rows for the CHED, DOST and TDP sections."""
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            award = app.award_number
            cong  = app.congress_district
            rows.append([i, award, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    for block_title, block_apps in [('FULL MERIT/ FULL SCHOLAR (*)', ched_full), ('HALF MERIT/ PARTIAL SCHOLAR (*)', ched_half)]:
        write_section(f'{block_title} SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
        bf = [a for a in block_apps if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
        female_pks = {a.pk for a in bf}
        bm = [a for a in block_apps if a.pk not in female_pks]
        write_gender_label('FEMALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bf))
        write_gender_label('MALE', len(headers_ched))
        write_headers(headers_ched)
        write_rows(ched_rows(bm))
        blank_row()

    dost_all = list(Application.objects.filter(
        status='Approved', scholarship__type='DOST', term_label=term
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    write_section(f'DOST (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    dost_f = [a for a in dost_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    dost_female_pks = {a.pk for a in dost_f}
    dost_m = [a for a in dost_all if a.pk not in dost_female_pks]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(dost_m))
    blank_row()

    gsis_all = list(Application.objects.filter(
        status='Approved', scholarship__type='GSIS', term_label=term
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    headers_gsis = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.', 'SCHOLARSHIP PROGRAM']
    write_section(f'GSIS (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_gsis))

    def gsis_rows(apps):
        """Rows for the GSIS section."""
        rows = []
        for i, app in enumerate(apps, 1):
            p = app.student; u = p.user
            last, first, mi = _name_parts(u)
            brgy, mun, prov = addr_parts(p.address)
            cong = app.congress_district
            rows.append([i, last, first, mi, p.gender or '', brgy, mun, prov, cong, p.course, p.year_level, app.scholarship.name])
        return rows

    gsis_f = [a for a in gsis_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    gsis_female_pks = {a.pk for a in gsis_f}
    gsis_m = [a for a in gsis_all if a.pk not in gsis_female_pks]
    write_gender_label('FEMALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_f))
    write_gender_label('MALE', len(headers_gsis))
    write_headers(headers_gsis)
    write_rows(gsis_rows(gsis_m))
    blank_row()

    tes_all = list(Application.objects.filter(
        status='Approved', scholarship__type='TDP', term_label=term
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS).order_by('student__user__last_name'))
    write_section(f'TERTIARY EDUCATION SUBSIDY -TES (*) SCHOLARSHIP GRANT — {semester} SY: {ay}', len(headers_ched))
    tes_f = [a for a in tes_all if a.student.gender and a.student.gender.upper() in ('F', 'FEMALE')]
    tes_female_pks = {a.pk for a in tes_f}
    tes_m = [a for a in tes_all if a.pk not in tes_female_pks]
    write_gender_label('FEMALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_f))
    write_gender_label('MALE', len(headers_ched))
    write_headers(headers_ched)
    write_rows(ched_rows(tes_m))
    blank_row()
    blank_row()

    footer_text = (
        'Prepared by:\t\t\t\t\tNoted:\t\t\t\t\t\tRecommending approval:\t\t\t\t\t\tApproved:\n'
        'MARICEL S. SAULAN\t\t\t\tNORMA M. DUALLO, Ph.D.TM\t\t\tERWIN G. SALVATIERRA, Ph. D.\t\t\tVICTOR C. CAÑEZO, JR., Ed. D.\n'
        'Scholarship in charge\t\t\t\tSDSO Director\t\t\t\t\tVP for Extension Services, Student and External Affairs\t\tUniversity President'
    )
    ws.oddFooter.center.text = footer_text
    ws.oddFooter.center.size = 8
    ws.evenFooter.center.text = footer_text
    ws.evenFooter.center.size = 8

    for col_idx in range(1, ws.max_column + 1):
        max_len = 0
        col_letter = get_column_letter(col_idx)
        for row_idx in range(1, ws.max_row + 1):
            cell = ws.cell(row=row_idx, column=col_idx)
            try:
                if cell.value:
                    max_len = max(max_len, len(str(cell.value)))
            except Exception:
                pass
        ws.column_dimensions[col_letter].width = min(max_len + 3, 35)

    buffer = BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f'Scholarship_Report_{term.replace("-","_")}_{semester.replace(" ","_")}.xlsx'
    response = HttpResponse(
        buffer.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response
