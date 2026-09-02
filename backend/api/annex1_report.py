"""TES applicants report — the CHED 'Annex 1' workbook.

The office's own Annex 1 template is bundled at ``templates/xlsx/`` and used as
the template, the same way :mod:`api.tes_report` uses the Annex 2 workbook: it
is opened, applicant rows are written into the pre-formatted data range, and the
title row is stamped with the school year being reported. Nothing about the
layout, the General Instructions tab, the hidden lookup sheets or the macros is
recreated in code, so the download is the form CHED expects apart from the data.

The file is macro-enabled (.xlsm). openpyxl is told to keep the VBA project, so
the sheet's own sequence-number macro and the three dropdown validations —
Sex_Code, Registry_Courses and Disability_List — survive the round trip.

Where Annex 2 lists the grantees the office bills for, this one lists everybody
who *applied*: a decision has not necessarily been made yet, so the default is
every application in the chosen school year rather than the approved ones only.
"""
import os

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates', 'xlsx', 'tes_annex1_applicants_template.xlsm',
)

SHEET = 'Annex 1'

# Where the applicant table starts and stops. Row 1 carries the academic year,
# rows 5-8 the three-deep merged header, and the data range below runs to the
# end of the sheet's own formatting and validation.
TITLE_CELL = 'A1'
FIRST_ROW = 9
LAST_ROW = 2008
CAPACITY = LAST_ROW - FIRST_ROW + 1

# Column order of the 'Annex 1' sheet, A..AD. Kept flat rather than nested the
# way the merged header draws it, because this is also what the on-screen
# preview and the tests read.
ANNEX1_HEADERS = [
    'SEQ', 'STUDENT ID', 'LRN', 'PHILSYS ID', '4PS ID',
    'LAST NAME', 'GIVEN NAME', 'EXT. NAME', 'MIDDLE NAME',
    'SEX', 'BIRTHDATE', 'COMPLETE PROGRAM NAME', 'YEAR LEVEL',
    "FATHER'S LAST NAME", "FATHER'S GIVEN NAME", "FATHER'S MIDDLE NAME",
    "MOTHER'S LAST NAME", "MOTHER'S GIVEN NAME", "MOTHER'S MIDDLE NAME",
    'STREET & BARANGAY', 'CITY/MUNICIPALITY', 'PROVINCE', 'REGION', 'ZIPCODE',
    'CONTACT NUMBER', 'EMAIL ADDRESS', 'DISABILITY TYPE',
    'SOLO PARENT DEPENDENT', 'FIRST-GEN COLLEGE', 'INDIGENOUS PEOPLE GROUP',
]
_NCOLS = len(ANNEX1_HEADERS)

# What the form wants in the two columns that are never left blank. The
# Disability_List and the IP instruction both spell 'not applicable' as NO.
NOT_APPLICABLE = 'NO'

# PhilSys and 4Ps ID numbers are both optional on the form and neither is
# collected anywhere in this system — the TES eligibility record holds a 4Ps
# yes/no, not the household's ID. They export blank for the office to fill in
# rather than being invented from the flag.


def _sex_code(gender):
    """0 = Male, 1 = Female — the codes the Sex_Code sheet validates against.

    Anything else defaults to 0, which is what the General Instructions tab
    says a blank does anyway.
    """
    return 1 if (gender or '').strip().lower().startswith('f') else 0


def _contact(number):
    """A contact number in the shape the form asks for.

    CHED wants a 10-digit mobile starting with 9 (or an 8-digit landline), but
    Philippine mobiles are written and stored as 11 digits beginning '09'. Only
    that leading zero is dropped; a number of any other length is passed through
    as typed rather than guessed at.
    """
    digits = ''.join(c for c in (number or '') if c.isdigit())
    if len(digits) == 11 and digits.startswith('0'):
        return digits[1:]
    return digits or (number or '').strip()


def _disability(value):
    value = (value or '').strip()
    if not value or value.lower() in ('n/a', 'na', 'none', 'not applicable', 'no'):
        return NOT_APPLICABLE
    return value


def _ip_group(value):
    value = (value or '').strip()
    if not value or value.lower() in ('n/a', 'na', 'none', 'not applicable', 'no'):
        return NOT_APPLICABLE
    return value


def applicant_rows(school_year='', status=''):
    """TES applicants in the column order the Annex 1 form expects.

    ``school_year`` is the expanded '2026-2027' form; blank means every year.
    ``status`` filters to one review status; blank means all of them, which is
    the point of this list — an applicant belongs on it before the decision.
    """
    from .models import STUDENT_DETAILS, TESApplication

    # Every detail row is joined in: this report reads personal, enrolment and
    # family fields on each applicant, and they live on separate tables.
    applications = (
        TESApplication.objects
        .select_related('student__user', *STUDENT_DETAILS)
        .order_by('student__user__last_name', 'student__user__first_name')
    )
    if school_year:
        applications = applications.filter(school_year=school_year)
    if status:
        applications = applications.filter(status=status)

    rows = []
    for seq, tes in enumerate(applications, 1):
        p = tes.student
        u = p.user
        rows.append({
            'seq': seq,
            'student_no': p.student_id or '',
            'lrn': tes.lrn or p.learner_ref_no or '',
            'philsys_id': '',
            'four_ps_id': '',
            'last_name': u.last_name or '',
            'first_name': u.first_name or '',
            'ext_name': p.suffix or '',
            'middle_name': p.middle_name or '',
            'sex': _sex_code(p.gender),
            'birthdate': tes.birthdate or p.date_of_birth or None,
            'course': tes.complete_program or p.course or '',
            'year_level': p.year_level or '',
            'father_last_name': p.father_last_name or '',
            'father_first_name': p.father_first_name or '',
            'father_middle_name': p.father_middle_name or '',
            'mother_last_name': p.mother_last_name or '',
            'mother_first_name': p.mother_first_name or '',
            'mother_middle_name': p.mother_middle_name or '',
            'street_barangay': tes.street_barangay or '',
            'city_municipality': tes.city_municipality or '',
            'province': tes.province or '',
            'region': tes.region or '',
            'zip_code': tes.zip_code or '',
            'contact': _contact(tes.contact_number or p.contact_number),
            'email': tes.email_address or u.email or '',
            'disability': _disability(tes.disability_type),
            'solo_parent': 1 if tes.is_solo_parent_dependent else 0,
            'first_gen': 1 if tes.is_first_gen_college else 0,
            'ip_group': _ip_group(tes.indigenous_people_group),
            # Not a form column — the preview shows it so an officer can see at
            # a glance which of these applicants have been decided.
            'status': tes.status,
        })
    return rows


def row_values(row):
    """The 30 'Annex 1' cell values, left to right (columns A..AD)."""
    return [
        row['seq'], row['student_no'], row['lrn'], row['philsys_id'],
        row['four_ps_id'], row['last_name'], row['first_name'], row['ext_name'],
        row['middle_name'], row['sex'], row['birthdate'], row['course'],
        row['year_level'], row['father_last_name'], row['father_first_name'],
        row['father_middle_name'], row['mother_last_name'],
        row['mother_first_name'], row['mother_middle_name'],
        row['street_barangay'], row['city_municipality'], row['province'],
        row['region'], row['zip_code'], row['contact'], row['email'],
        row['disability'], row['solo_parent'], row['first_gen'], row['ip_group'],
    ]


def build_workbook(school_year, status=''):
    """Return ``(BytesIO, written, overflow)`` for the filled Annex 1 workbook."""
    import openpyxl
    from io import BytesIO

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(
            f'The TES Annex 1 workbook template is missing at {TEMPLATE_PATH}. '
            'Restore it from the office copy before generating this report.'
        )

    all_rows = applicant_rows(school_year=school_year, status=status)
    rows = all_rows[:CAPACITY]
    # Anything past the pre-formatted range is reported rather than silently
    # dropped — the office would need extra lines inserted in the template.
    overflow = len(all_rows) - len(rows)

    # keep_vba, so the sheet's sequence-number macro comes back out with it.
    wb = openpyxl.load_workbook(TEMPLATE_PATH, keep_vba=True)
    ws = wb[SHEET]
    ws[TITLE_CELL] = f'Academic Year {school_year}' if school_year else 'Academic Year'

    for i, row in enumerate(rows):
        r = FIRST_ROW + i
        for j, value in enumerate(row_values(row)):
            ws.cell(row=r, column=1 + j).value = value

    # The template ships empty, but clearing the tail keeps a regenerated report
    # from ever showing a longer previous run's leftovers.
    for r in range(FIRST_ROW + len(rows), LAST_ROW + 1):
        for c in range(1, _NCOLS + 1):
            ws.cell(row=r, column=c).value = None

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf, len(rows), overflow
