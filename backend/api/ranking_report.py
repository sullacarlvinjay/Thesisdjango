"""The eligibility ranking workbooks.

One sheet per programme, each carrying the ranking and, beneath it, the
per-rule verdicts. The detail is the point: the office has to be able to answer
"why was this person not recommended?" from the file alone, months later,
without re-running anything.
"""

from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font
from openpyxl.utils import get_column_letter

TITLES = {
    'Affirmative': 'Affirmative Action',
    'TES': 'TES Recommendation',
    'Staff': 'Faculty and Staff Scholars',
}

SLUGS = {
    'Affirmative': 'Affirmative_Action',
    'TES': 'TES',
    'Staff': 'Faculty_and_Staff',
}

RULE_COLUMNS = {
    'TES': [
        ('citizenship', 'Citizenship'),
        ('enrollment', 'Current College Enrollment'),
        ('first_degree', 'First College Degree'),
        ('maximum_years', 'Maximum Years of Study'),
        ('other_assistance', 'Other Government Assistance'),
    ],
    'Staff': [
        ('standing', 'Employee or dependent'),
        ('permanent', 'Permanent appointment'),
        ('dependency', 'Legitimate dependent'),
        ('baccalaureate', 'No baccalaureate already'),
    ],
}

HEAD = Font(name='Arial', size=10, bold=True)
BODY = Font(name='Arial', size=10)
TITLE = Font(name='Arial', size=12, bold=True)
SUB = Font(name='Arial', size=10)


def _sheet(wb, name, title, subtitles, headers, first=False):
    """Start a worksheet with its title, subtitles and header row."""
    ws = wb.active if first else wb.create_sheet()
    ws.title = name[:31]

    ws['A1'] = title
    ws['A1'].font = TITLE
    line = 2
    for text in subtitles:
        ws.cell(row=line, column=1, value=text).font = SUB
        line += 1

    head = line + 1
    for col, label in enumerate(headers, start=1):
        cell = ws.cell(row=head, column=col, value=label)
        cell.font = HEAD
        cell.alignment = Alignment(horizontal='center', wrap_text=True)
        ws.column_dimensions[get_column_letter(col)].width = max(12, len(label) + 4)
    ws.freeze_panes = ws.cell(row=head + 1, column=1)
    return ws, head


def _write(ws, head, rows):
    """Write one row of values, styled as body text."""
    for line, row in enumerate(rows, start=head + 1):
        for col, value in enumerate(row, start=1):
            cell = ws.cell(row=line, column=col, value=value)
            cell.font = BODY
            cell.alignment = Alignment(vertical='top', wrap_text=isinstance(value, str)
                                       and len(value) > 60)


def _verdict(evaluation, key):
    """A rule verdict as the spreadsheet spells it."""
    rule = evaluation.rule(key)
    return rule.verdict if rule else '—'


def _reason_rows(evaluations, name_of, id_of):
    """The per-rule detail rows that follow a recommendation.

    The office has to be able to answer "why was this person not
    recommended?" from the file alone, months later, without re-running
    anything.
    """
    rows = []
    for evaluation in evaluations:
        for rule in evaluation.rules:
            rows.append([
                name_of(evaluation), id_of(evaluation), rule.label, rule.verdict,
                rule.detail, rule.source or '',
            ])
    return rows


def _affirmative(wb, data, passing_threshold, stamp):
    """Write the Affirmative Action ranking sheet."""
    ws, head = _sheet(
        wb, 'Affirmative Action', 'Affirmative Action — Rule-Based Recommendation',
        [
            f'{data["eligible_count"]} eligible · {data["ineligible_count"]} '
            'not meeting all rules · '
            f'{data["in_target_group_count"]} of the eligible in a target group',
            f'Rules: SHS GPA ≥ {passing_threshold:g}% · SUC admission exam ≥ 50% · '
            'not a TES beneficiary',
            'Ordered by target group, then by fit score. The groups are who the '
            'programme is for, not a requirement: PASUC-8 proposal §1 says grades '
            'are not the only factor and a qualifier need be neither indigent nor '
            'an excellent academic performer.',
            stamp,
        ],
        ['Rank', 'Student', 'Student No.', 'Course', 'Year Level',
         'SHS GPA (%)', f'GPA ≥ {passing_threshold:g}%', 'SUC Exam (%)',
         'Exam ≥ 50%', 'Not a TES Beneficiary', 'Target Groups',
         'Groups Matched', 'Unanswered Group Questions', 'Fit Score (%)', 'Status'],
        first=True)

    rows = []
    for row in data['rows']:
        profile, rec = row['profile'], row['rec']
        groups = row['groups']
        if rec.status == 'Disqualified':
            status = 'Disqualified'
        elif row['eligible']:
            status = 'Recommended'
        else:
            status = 'Not Eligible'
        rows.append([
            row['rank'] or '',
            profile.user.get_full_name(),
            profile.student_id or '',
            profile.course or '',
            profile.year_level or '',
            profile.shs_gpa if profile.shs_gpa is not None else '',
            'Yes' if row['gpa_pass'] else 'No',
            profile.suc_exam_percent if profile.suc_exam_percent is not None else '',
            'Yes' if row['exam_pass'] else 'No',
            'Yes' if row['not_tes'] else 'No',
            groups.summary,
            groups.count,
            ', '.join(groups.unknown) if groups.unknown else 'None',
            rec.fit_score if row['eligible'] else '',
            status,
        ])
    _write(ws, head, rows)


def _tes(wb, data, stamp):
    """Write the TES ranking sheet, one column per eligibility rule."""
    rules = RULE_COLUMNS['TES']
    ws, head = _sheet(
        wb, 'TES Recommendation', 'TES — Rule-Based Recommendation',
        [
            f'{data["counts"]["eligible"]} eligible · '
            f'{data["counts"]["not_eligible"]} not eligible · '
            f'{data["total"]} students ranked',
            f'{data["counts"]["excluded"]} student(s) not shown — record still '
            'has an unanswered question, so no rule was run against it.',
            'UniFAST awards TES. This is what the SDSO would recommend; producing '
            'it writes no status onto any student.',
            stamp,
        ],
        ['Rank', 'Student', 'Student No.', 'Eligibility', 'Priority',
         'Priority Markers', 'Per Capita Income',
         'Recommendation'] + [label for _, label in rules] + ['Reason'],
        first=True)

    rows = []
    for e in data['rows']:
        rows.append([
            e.rank or '',
            e.student_name,
            e.student_id or '',
            e.status,
            e.priority,
            ' · '.join(e.priority_markers) if e.priority_markers else '',
            e.per_capita_income,
            e.recommendation,
        ] + [_verdict(e, key) for key, _ in rules]
          + [e.reason or 'Every rule passed'])
    _write(ws, head, rows)

    ws, head = _sheet(
        wb, 'Reasons', 'Why each student reached that verdict',
        ['One row per rule, as the Why? panel on the Student Ranking page shows it.',
         stamp],
        ['Student', 'Student No.', 'Rule', 'Verdict', 'Reading', 'Read From'])
    _write(ws, head, _reason_rows(
        data['rows'],
        lambda e: e.student_name, lambda e: e.student_id or ''))


def _staff(wb, data, stamp):
    """Write the Faculty and Staff ranking sheet."""
    rules = RULE_COLUMNS['Staff']
    ws, head = _sheet(
        wb, 'Faculty and Staff', 'Faculty and Staff Scholars — Rule-Based Recommendation',
        [
            f'{data["counts"]["qualified"]} qualified · '
            f'{data["counts"]["verification"]} for verification · '
            f'{data["counts"]["not_qualified"]} not qualified · '
            f'{data["total"]} application(s) screened',
            f'{data["counts"]["employees"]} employee(s) · '
            f'{data["counts"]["dependents"]} dependent(s). Nothing is scored: the '
            'programme has no merit test, so a rank is reading order, not a ranking.',
            stamp,
        ],
        ['Rank', 'Applicant', 'Applying As', 'Employee / Student No.',
         'Qualification', 'Recommendation']
        + [label for _, label in rules] + ['Missing Information'],
        first=True)

    rows = []
    for e in data['rows'] + data['refused'] + data['needs_info']:
        rows.append([
            e.rank or '',
            e.applicant_name,
            e.standing,
            e.application.student_id or '',
            e.status,
            e.recommendation,
        ] + [_verdict(e, key) for key, _ in rules]
          + [', '.join(e.missing) if e.missing else 'None'])
    _write(ws, head, rows)

    ws, head = _sheet(
        wb, 'Reasons', 'Why each applicant reached that verdict',
        ['One row per qualification, as the Why? panel on the Student Ranking '
         'page shows it.', stamp],
        ['Applicant', 'Employee / Student No.', 'Qualification', 'Verdict',
         'Reading', 'Read From'])
    _write(ws, head, _reason_rows(
        data['rows'] + data['refused'] + data['needs_info'],
        lambda e: e.applicant_name, lambda e: e.application.student_id or ''))


def build(tab, data, passing_threshold=None, generated=None):
    """Build the ranking workbook for one programme.

    Returns:
        ``(buffer, filename)``, the buffer positioned at the start.
    """
    from django.utils import timezone

    when = generated or timezone.localtime()
    stamp = f'Generated {when.strftime("%d %B %Y, %I:%M %p")}'

    wb = Workbook()
    if tab == 'TES':
        _tes(wb, data, stamp)
    elif tab == 'Staff':
        _staff(wb, data, stamp)
    else:
        _affirmative(wb, data, passing_threshold or 75.0, stamp)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    slug = SLUGS.get(tab, tab.replace(' ', '_'))
    return buf, f'BiPSU_{slug}_recommendation_{when.strftime("%Y-%m-%d")}.xlsx'
