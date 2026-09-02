"""TES validation & billing report — the CHED 'Annex 2 Continuing' workbook.

The office's own workbook is bundled at ``templates/xlsx/`` and used as the
template: it is opened, grantee rows are written into the pre-formatted data
ranges, and unused rows are cleared and hidden. No part of the layout,
instructions, formulas or signatory blocks is recreated in code, so the download
matches the form CHED expects exactly apart from the data.

Because the template's own formulas are preserved, filling the Form 2 amount
columns makes the totals, the 1% management fee and the whole Form 1 billing
statement compute themselves when the file is opened.
"""
import os

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates', 'xlsx', 'tes_validation_billing_template.xlsx',
)

# Pre-formatted data ranges. Past these rows the workbook holds its totals,
# undertaking text and signatory blocks, which must survive untouched.
OFFICIAL_LIST = {'sheet': 'Official List', 'first_row': 20, 'last_row': 1110}
BILLING_FORM2 = {'sheet': 'Annex 2-Form 2', 'first_row': 31, 'last_row': 1100}

# Neither amount column is filled in here. CHED sets what a grantee is paid —
# the SUC rate quoted in the Form 2 header is a reference, not this office's
# figure, and TES-3A (PWD) top-ups are decided per case. Writing a flat rate
# into every row turned a guess into a number an officer would have signed off.
# Both go out blank for the office to complete from CHED's own advice.

# Column order of the 'Official List' sheet. Annex 2-Form 2 repeats these in
# columns B..P, keeping a 5-digit control number in column A and a per-student
# total in column Q.
OFFICIAL_LIST_HEADERS = [
    'SEQ', 'STUDENT ID NUMBER', 'AWARD NUMBER', 'LAST NAME', 'FIRST NAME',
    'EXT NAME', 'MIDDLE NAME', 'SEX (F/M)', 'BIRTHDATE',
    'COURSE/ PROGRAM ENROLLED', 'YEAR LEVEL', 'CONTACT NUMBER', 'BATCH',
    'TES AMOUNT', 'TES-3A (PWD) AMOUNT', 'VALIDATION REMARKS',
]
_NCOLS = len(OFFICIAL_LIST_HEADERS)


def _is_pwd(tes):
    value = (tes.disability_type or '').strip().lower()
    return bool(value) and value not in ('n/a', 'na', 'none', 'not applicable')


def school_year_options():
    """The school years a TES report can be generated for, newest first.

    Every year TES applications were actually submitted in, plus the active
    term from SystemSettings — so the year the office is working in is always
    on the list even before the first application of it comes in. Shared by
    both TES reports; :mod:`api.annex1_report` reads the same list.
    """
    from .models import SystemSettings, TESApplication

    years = set(
        TESApplication.objects
        .exclude(school_year='')
        .values_list('school_year', flat=True)
    )
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active = SystemSettings.parse_label(settings_obj.academic_year)['sy']
    if active:
        years.add(active)
    return sorted(years, reverse=True)


def grantee_rows(batch='', school_year=''):
    """Approved TES grantees in the column order the CHED form expects.

    Sourced from the TES applications this portal reviews. The award number is
    read directly from TESApplication.award_number (set by UniFAST staff during
    the review decision). ``school_year`` is the expanded '2026-2027' form;
    blank means every year, which is what this returned before the office could
    pick one.
    """
    from .models import TESApplication

    rows = []
    grantees = (
        TESApplication.objects.filter(status='Approved')
        .select_related('student__user')
        .order_by('student__user__last_name', 'student__user__first_name')
    )
    if school_year:
        grantees = grantees.filter(school_year=school_year)
    for seq, tes in enumerate(grantees, 1):
        p = tes.student
        u = p.user
        sex = (p.gender or '').strip().upper()[:1]
        rows.append({
            'seq': seq,
            'student_no': p.student_id or '',
            'award_no': tes.award_number or '',
            'last_name': u.last_name or '',
            'first_name': u.first_name or '',
            'ext_name': '',
            'middle_name': tes.student.middle_name or '',
            'sex': sex if sex in ('F', 'M') else '',
            'birthdate': tes.birthdate or p.date_of_birth or None,
            'course': tes.complete_program or p.course or '',
            'year_level': p.year_level or '',
            'contact': tes.contact_number or p.contact_number or '',
            'batch': batch,
            'tes_amount': None,      # set by CHED, entered by the office
            'tes_3a_amount': None,   # PWD top-up rate is set by CHED per case
            'is_pwd': _is_pwd(tes),
            'remarks': 'Enrolled',
        })
    return rows


def row_values(row):
    """The 16 'Official List' cell values, left to right."""
    return [
        row['seq'], row['student_no'], row['award_no'], row['last_name'],
        row['first_name'], row['ext_name'], row['middle_name'], row['sex'],
        row['birthdate'], row['course'], row['year_level'], row['contact'],
        row['batch'], row['tes_amount'], row['tes_3a_amount'], row['remarks'],
    ]


def _fill(ws, spec, rows, layout):
    """Write rows into a pre-formatted range; clear and hide what is left over.

    Unused rows are hidden rather than deleted so the merged cells, totals
    formulas and signatory blocks below the table keep their row positions —
    and so the totals keep summing the range they were written against.
    """
    first, last = spec['first_row'], spec['last_row']
    capacity = last - first + 1
    written = 0

    for i, row in enumerate(rows[:capacity]):
        r = first + i
        values = row_values(row)
        if layout == 'official':
            for j, value in enumerate(values):
                ws.cell(row=r, column=1 + j).value = value
        else:
            ws.cell(row=r, column=1).value = f'{i + 1:05d}'
            for j, value in enumerate(values[1:]):      # column A holds the control no.
                ws.cell(row=r, column=2 + j).value = value
            ws.cell(row=r, column=17).value = (
                (row['tes_amount'] or 0) + (row['tes_3a_amount'] or 0)
            )
        ws.row_dimensions[r].hidden = False
        written += 1

    ncols = _NCOLS if layout == 'official' else _NCOLS + 1
    for r in range(first + written, last + 1):
        for c in range(1, ncols + 1):
            ws.cell(row=r, column=c).value = None
        ws.row_dimensions[r].hidden = True

    return written


def build_workbook(academic_year, semester, batch='', school_year=''):
    """Return ``(BytesIO, written, overflow)`` for the filled CHED workbook.

    ``academic_year`` is what gets printed in the sheet headers; ``school_year``
    is what the grantee list is filtered on. They are the same value whenever
    the office picks a year, and are kept apart only so a caller can still print
    a header over an unfiltered list, as this did before the picker existed.
    """
    import openpyxl
    from io import BytesIO

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(
            f'The TES workbook template is missing at {TEMPLATE_PATH}. '
            'Restore it from the office copy before generating this report.'
        )

    all_rows = grantee_rows(batch=batch, school_year=school_year)
    # Both sheets must list the same grantees, so the smaller pre-formatted
    # range is the real capacity. Anything past it is reported, not silently
    # dropped — the office would need extra lines inserted in the template.
    capacity = min(
        OFFICIAL_LIST['last_row'] - OFFICIAL_LIST['first_row'] + 1,
        BILLING_FORM2['last_row'] - BILLING_FORM2['first_row'] + 1,
    )
    rows = all_rows[:capacity]
    overflow = len(all_rows) - len(rows)

    wb = openpyxl.load_workbook(TEMPLATE_PATH)

    official = wb[OFFICIAL_LIST['sheet']]
    official['A3'] = f'TES Batch {batch or "On-going"}, {semester}, AY {academic_year}'
    written = _fill(official, OFFICIAL_LIST, rows, 'official')

    form2 = wb[BILLING_FORM2['sheet']]
    form2['J28'] = f'{semester}, AY {academic_year}'
    _fill(form2, BILLING_FORM2, rows, 'form2')

    # Grantee headcount on the billing statement; its money figures already
    # pull straight from the Form 2 totals.
    wb['Annex 2-Form 1']['Q24'] = written

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf, written, overflow
