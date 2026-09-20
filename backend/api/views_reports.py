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
    except FileNotFoundError:
        from urllib.parse import quote
        logger.exception('Masterlist template missing for term %r', term)
        return redirect(f'/vpsea/reports/?sy={quote(term)}&error=' + quote(
            'The masterlist template is missing on the server. Restore it from '
            'the office copy before generating this report.'))

    label = term.replace('-', '_')
    filename = f'BiPSU_List_of_Scholars_{label}.docx'
    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

MAX_COLS = 13

HEADERS_ACADEMIC = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX',
                    'BRGY./ST.', 'MUN.', 'PROV.', 'COURSE', 'YR.', 'GWA', '%',
                    'SCHOLARSHIP PROGRAM']

HEADERS_STAFF = ['NO.', 'LAST NAME', 'FIRST NAME', 'M.I.', 'SEX', 'COURSE',
                 'YEAR LEVEL', 'STUDENT NUMBER', '%', 'SCHOLARSHIP PROGRAM']

HEADERS_AWARD = ['NO.', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME',
                 'SEX', 'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE',
                 'YR.', 'SCHOLARSHIP PROGRAM']

HEADERS_GSIS = ['NO.', 'LAST NAME', 'FIRST NAME', 'MIDDLE NAME', 'SEX',
                'BRGY./ST.', 'MUN.', 'PROV.', 'CONG. DIST.', 'COURSE', 'YR.',
                'SCHOLARSHIP PROGRAM']

FOOTER_TEXT = (
    'Prepared by:\t\t\t\t\tNoted:\t\t\t\t\t\tRecommending approval:\t\t\t\t\t\tApproved:\n'
    'MARICEL S. SAULAN\t\t\t\tNORMA M. DUALLO, Ph.D.TM\t\t\tERWIN G. SALVATIERRA, Ph. D.\t\t\tVICTOR C. CAÑEZO, JR., Ed. D.\n'
    'Scholarship in charge\t\t\t\tSDSO Director\t\t\t\t\tVP for Extension Services, Student and External Affairs\t\tUniversity President'
)


def _split_name(full_name):
    """Split a single full name into last, first and middle initial."""
    parts = (full_name or '').strip().split()
    if len(parts) == 0:
        return ('', '', '')
    if len(parts) == 1:
        return (parts[0], '', '')
    if len(parts) == 2:
        return (parts[-1], parts[0], '')
    middle = ' '.join(parts[1:-1])
    return (parts[-1], parts[0], middle[0] + '.' if middle else '')


def _name_parts(user):
    """Name cells for a record, whichever shape it arrived in."""
    return (user.last_name or '', user.first_name or '', '')


def _address_parts(address):
    """Barangay, municipality and province as separate cells."""
    parts = [piece.strip() for piece in (address or '').split(',')]
    return (parts[0] if len(parts) > 0 else '',
            parts[1] if len(parts) > 1 else '',
            parts[2] if len(parts) > 2 else '')


def _is_female(gender):
    """Whether a gender cell reads as female."""
    return bool(gender) and gender.upper() in ('F', 'FEMALE')


def _by_gender(records, gender_of):
    """Split records into female and male bands, keeping the order.

    Anything that does not read as female goes in the male band rather than
    being dropped, so the two bands always add up to the section total.
    """
    female = [record for record in records if _is_female(gender_of(record))]
    female_pks = {record.pk for record in female}
    return female, [record for record in records if record.pk not in female_pks]


def _academic_rows(awards):
    """Rows for the Academic section."""
    rows = []
    for number, award in enumerate(awards, 1):
        profile = award.student
        last, first, initial = _name_parts(profile.user)
        brgy, mun, prov = _address_parts(profile.address)
        standing = ('University Scholar' if profile.gwa <= 1.29
                    else 'College Scholars' if profile.gwa <= 1.50 else '')
        rows.append([number, last, first, initial, profile.gender or '',
                     brgy, mun, prov, profile.course, profile.year_level,
                     profile.gwa, standing, 'ACADEMIC'])
    return rows


def _staff_rows(records):
    """Rows for the BiPSU Staff section."""
    rows = []
    for number, record in enumerate(records, 1):
        last, first, initial = _split_name(record.full_name)
        rows.append([number, last, first, initial, record.gender or '',
                     record.course, record.year_level, record.student_id or '',
                     '100' if record.is_nsu_staff else '75',
                     'BiPSU STAFF SCHOLARSHIP'])
    return rows


def _affirmative_rows(records):
    """Rows for the Affirmative Action section."""
    rows = []
    for number, record in enumerate(records, 1):
        last, first, initial = _split_name(record.full_name)
        brgy, mun, prov = _address_parts(record.address)
        rows.append([number, '', last, first, initial, record.gender or '',
                     brgy, mun, prov, '', record.course, record.year_level,
                     'Affirmative Action Scholarship'])
    return rows


def _award_rows(awards):
    """Rows for the CHED, DOST and TES sections."""
    rows = []
    for number, award in enumerate(awards, 1):
        profile = award.student
        last, first, initial = _name_parts(profile.user)
        brgy, mun, prov = _address_parts(profile.address)
        rows.append([number, award.award_number, last, first, initial,
                     profile.gender or '', brgy, mun, prov,
                     award.congress_district, profile.course,
                     profile.year_level, award.scholarship.name])
    return rows


def _gsis_rows(awards):
    """Rows for the GSIS section, which carries no award number."""
    rows = []
    for number, award in enumerate(awards, 1):
        profile = award.student
        last, first, initial = _name_parts(profile.user)
        brgy, mun, prov = _address_parts(profile.address)
        rows.append([number, last, first, initial, profile.gender or '',
                     brgy, mun, prov, award.congress_district, profile.course,
                     profile.year_level, award.scholarship.name])
    return rows


def _approved_awards(stype, term):
    """Approved portal awards for one programme in one term."""
    from .models import Application

    return list(Application.objects.filter(
        status='Approved', scholarship__type=stype, term_label=term
    ).select_related('student__user', 'scholarship', *STUDENT_DETAILS)
        .order_by('student__user__last_name'))


def _approved_records(qualified_for, term):
    """Approved roster records for one programme in one term."""
    from .models import ApplicantRecord

    return list(ApplicantRecord.objects.filter(
        status='Approved', qualified_for=qualified_for, term_label=term
    ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name'))


def _award_gender(award):
    """The gender on a portal award's student profile."""
    return award.student.gender


def _record_gender(record):
    """The gender on a roster record."""
    return record.gender


class _MasterlistSheet:
    """The masterlist workbook, with one method per kind of row.

    Written top to bottom: every method appends at the cursor and moves it
    on, so a section is a sequence of calls rather than a row arithmetic
    the caller has to keep straight.
    """
    def __init__(self, sheet_title):
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        self.workbook = openpyxl.Workbook()
        self.sheet = self.workbook.active
        self.sheet.title = sheet_title
        self.row = 1

        thin = Side(style='thin')
        self.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        self.center = Alignment(horizontal='center', vertical='center',
                                wrap_text=True)
        self.header_font = Font(bold=True, size=9)
        self.header_fill = PatternFill('solid', fgColor='D9E1F2')
        self.section_fill = PatternFill('solid', fgColor='BDD7EE')
        self.title_fill = PatternFill('solid', fgColor='1F4E79')
        self.title_font = Font(bold=True, size=11, color='FFFFFF')

    def _merged(self, text, ncols):
        """Write one merged cell across the row and return it."""
        self.sheet.cell(row=self.row, column=1, value=text)
        self.sheet.merge_cells(start_row=self.row, start_column=1,
                               end_row=self.row, end_column=ncols)
        return self.sheet.cell(row=self.row, column=1)

    def title(self, text, ncols=MAX_COLS):
        """Write one of the merged title rows."""
        cell = self._merged(text, ncols)
        cell.font = self.title_font
        cell.fill = self.title_fill
        cell.alignment = self.center
        cell.border = self.border
        self.sheet.row_dimensions[self.row].height = 18
        self.row += 1

    def section(self, text, ncols):
        """Write a programme's section heading."""
        from openpyxl.styles import Font

        cell = self._merged(text, ncols)
        cell.font = Font(bold=True, size=10)
        cell.fill = self.section_fill
        cell.alignment = self.center
        cell.border = self.border
        self.row += 1

    def gender_label(self, text, ncols):
        """Write the FEMALE or MALE band label."""
        from openpyxl.styles import Alignment, Font

        cell = self._merged(text, ncols)
        cell.font = Font(bold=True, size=9)
        cell.alignment = Alignment(horizontal='left', vertical='center')
        self.row += 1

    def headers(self, headers):
        """Write a header row."""
        for column, heading in enumerate(headers, 1):
            cell = self.sheet.cell(row=self.row, column=column, value=heading)
            cell.font = self.header_font
            cell.fill = self.header_fill
            cell.border = self.border
            cell.alignment = self.center
        self.row += 1

    def rows(self, values):
        """Write a block of scholar rows."""
        from openpyxl.styles import Alignment, Font

        for line in values:
            for column, value in enumerate(line, 1):
                cell = self.sheet.cell(row=self.row, column=column, value=value)
                cell.border = self.border
                cell.alignment = Alignment(vertical='center', wrap_text=True)
                cell.font = Font(size=9)
            self.row += 1

    def blank(self):
        """Leave a row empty, for spacing."""
        self.row += 1

    def gendered(self, headers, records, build_rows, gender_of):
        """Write a section's female band then its male band."""
        female, male = _by_gender(records, gender_of)
        for label, band in (('FEMALE', female), ('MALE', male)):
            self.gender_label(label, len(headers))
            self.headers(headers)
            self.rows(build_rows(band))

    def footer(self, text):
        """Put the signature block in the page footer."""
        for footer in (self.sheet.oddFooter, self.sheet.evenFooter):
            footer.center.text = text
            footer.center.size = 8

    def autofit(self):
        """Widen each column to its longest cell, within reason."""
        from openpyxl.utils import get_column_letter

        for index in range(1, self.sheet.max_column + 1):
            longest = 0
            for row in range(1, self.sheet.max_row + 1):
                value = self.sheet.cell(row=row, column=index).value
                if value:
                    longest = max(longest, len(str(value)))
            self.sheet.column_dimensions[get_column_letter(index)].width = min(
                longest + 3, 35)

    def as_response(self, filename):
        """The workbook as a download."""
        from io import BytesIO

        buffer = BytesIO()
        self.workbook.save(buffer)
        buffer.seek(0)
        response = HttpResponse(
            buffer.read(),
            content_type=('application/vnd.openxmlformats-officedocument'
                          '.spreadsheetml.sheet'),
        )
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


def _write_ched_sections(sheet, term, heading_suffix):
    """The two CHED tiers, each as its own gendered section."""
    full, half = split_ched(_approved_awards('CHED', term))
    for title, awards in (('FULL MERIT/ FULL SCHOLAR (*)', full),
                          ('HALF MERIT/ PARTIAL SCHOLAR (*)', half)):
        sheet.section(f'{title} SCHOLARSHIP GRANT — {heading_suffix}',
                      len(HEADERS_AWARD))
        sheet.gendered(HEADERS_AWARD, list(awards), _award_rows, _award_gender)
        sheet.blank()


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
    term, parsed, _display = _report_term(request)
    semester = parsed['semester']
    ay = parsed['sy']
    suffix = f'{semester} SY: {ay}'

    sheet = _MasterlistSheet('Scholars')
    sheet.title('Republic of the Philippines')
    sheet.title('BILIRAN PROVINCE STATE UNIVERSITY — Naval, Biliran')
    sheet.title(f'LIST OF SCHOLARS FOR {suffix}')
    sheet.blank()

    sheet.section(f'ACADEMIC (@) SCHOLARSHIP GRANT — {suffix}',
                  len(HEADERS_ACADEMIC))
    sheet.gendered(HEADERS_ACADEMIC, _approved_awards('Academic', term),
                   _academic_rows, _award_gender)
    sheet.blank()

    sheet.section(f'BiPSU STAFF (@) SCHOLARSHIP GRANT — {suffix}',
                  len(HEADERS_STAFF))
    sheet.headers(HEADERS_STAFF)
    sheet.rows(_staff_rows(_approved_records('Staff', term)))
    sheet.blank()

    sheet.section(f'AFFIRMATIVE ACTION (*) SCHOLARSHIP GRANT — {suffix}',
                  len(HEADERS_AWARD))
    sheet.gendered(HEADERS_AWARD, _approved_records('Affirmative', term),
                   _affirmative_rows, _record_gender)
    sheet.blank()

    _write_ched_sections(sheet, term, suffix)

    sheet.section(f'DOST (*) SCHOLARSHIP GRANT — {suffix}', len(HEADERS_AWARD))
    sheet.gendered(HEADERS_AWARD, _approved_awards('DOST', term),
                   _award_rows, _award_gender)
    sheet.blank()

    sheet.section(f'GSIS (*) SCHOLARSHIP GRANT — {suffix}', len(HEADERS_GSIS))
    sheet.gendered(HEADERS_GSIS, _approved_awards('GSIS', term),
                   _gsis_rows, _award_gender)
    sheet.blank()

    sheet.section(
        f'TERTIARY EDUCATION SUBSIDY -TES (*) SCHOLARSHIP GRANT — {suffix}',
        len(HEADERS_AWARD))
    sheet.gendered(HEADERS_AWARD, _approved_awards('TDP', term),
                   _award_rows, _award_gender)
    sheet.blank()
    sheet.blank()

    sheet.footer(FOOTER_TEXT)
    sheet.autofit()
    return sheet.as_response(
        f'Scholarship_Report_{term.replace("-", "_")}_'
        f'{semester.replace(" ", "_")}.xlsx')
