"""Building the university's List of Scholars.

The DOCX template is the authority on what the report looks like: the office
maintains it, and the format is not ours to choose. Column headings are parsed
out of it, so adding a column to the document needs no code change.

:func:`build_context` gathers every programme's scholars for one term and is
the single source for all three renderings — the page, the DOCX and the PDF.
Every source is filtered by term; they were not, and the report carried every
approved award ever made under a heading naming one semester.
"""

import os
import re

TEMPLATE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates', 'docx', 'masterlist_template.docx',
)

PROGRAM_SLOTS = [
    ('program1',  'ACADEMIC',        'Academic',    'gendered'),
    ('program2',  'BiPSU STAFF',     'Staff',       'students'),
    ('program3',  'AFFIRMATIVE',     'Affirmative', 'gendered'),
    ('program4',  'CHED FULL MERIT', 'CHED_FULL',   'gendered'),
    ('program5',  'CHED HALF MERIT', 'CHED_HALF',   'gendered'),
    ('program6',  'DOST',            'DOST',        'gendered'),
    ('program7',  'TDP',             'TDP',         'gendered'),
    ('program8',  'TES',             'TES',         'gendered'),
    ('program9',  'GSIS',            'GSIS',        'gendered'),
    ('program10', 'CoScho',          'CoScho',      'gendered'),
    ('program12', 'SPORTS',          'Sports',      'gendered'),
    ('program13', 'SUC-TDP',         'SUC-TDP',     'gendered'),
    ('program14', 'DOST-JLSS',       'JLSS',        'gendered'),
    ('program15', 'FHE',             'FHE',         'gendered'),
]
ALL_SLOTS = [f'program{i}' for i in range(1, 17)]

UNUSED_MARKER = '∅UNUSED'

HEADER_FIELD = {
    'NO.': 'no',
    'AWARD NUMBER': 'award_number',
    'LAST NAME': 'last_name',
    'FIRST NAME': 'first_name',
    'MIDDLE NAME': 'middle_name',
    'M.I.': 'm_i',
    'SEX': 'sex',
    'BRGY./ST.': 'brgy_st',
    'MUN.': 'mun',
    'MUNICIPALITY': 'municipality',
    'PROV.': 'prov',
    'PROVINCE': 'province',
    'CONG. DIST.': 'cong_dist',
    'COURSE': 'course',
    'YR.': 'yr',
    'YEAR LEVEL': 'year_level',
    'GWA': 'gwa',
    '%': 'percent',
    'NUMBER': 'number',
    'SCHOLARSHIP PROGRAM': 'scholarship_program',
    'PROGRAM': 'program',
}

_HEADER_CACHE = {}


def slot_headers():
    """Read each programme's column headings out of the DOCX template.

    The template is the authority on what the masterlist looks like, because
    the office maintains it and the university's format is not ours to
    choose. Parsing it means adding a column to the document is enough —
    no code change follows.

    Cached after the first read; the template does not change at runtime.
    """
    if _HEADER_CACHE:
        return _HEADER_CACHE
    import re
    import docx

    tag = re.compile(r'\{%tr\s*for row in (\w+)\.(\w+)')
    document = docx.Document(TEMPLATE_PATH)
    for table in document.tables:
        joined = ' '.join(c.text for r in table.rows for c in r.cells)
        found = tag.search(joined)
        if not found or found.group(1) in _HEADER_CACHE:
            continue
        raw = [c.text.strip().replace(chr(10), ' ') for c in table.rows[1].cells]
        headings = []
        for h in raw:
            if not headings or headings[-1] != h:
                headings.append(h)
        _HEADER_CACHE[found.group(1)] = headings
    return _HEADER_CACHE


def cells_for(row, headings):
    """Lay one row out in the order a set of headings asks for."""
    return [row.get(HEADER_FIELD.get(h, ''), '') for h in headings]


FEMALE_VALUES = ('F', 'FEMALE')


def _is_female(gender):
    """Whether a gender value reads as female, however it was typed."""
    return (gender or '').strip().upper() in FEMALE_VALUES


def _initial(name):
    """A middle initial with its full stop, or '' if there is no name."""
    name = (name or '').strip()
    return f'{name[0].upper()}.' if name else ''


def _blank_row(no):
    """An empty row carrying every field a template might ask for.

    Every row starts from this, so a template referring to a field the source
    record does not have renders blank instead of raising mid-document.
    """
    return {
        'no': no, 'col': '',
        'last_name': '', 'first_name': '', 'first_name1': '',
        'middle_name': '', 'm_i': '',
        'sex': '', 'brgy_st': '', 'mun': '', 'municipality': '',
        'prov': '', 'province': '',
        'course': '', 'yr': '', 'year_level': '',
        'gwa': '', 'percent': '', 'number': '',
        'award_number': '', 'cong_dist': '',
        'scholarship_program': '', 'program': '',
    }


def _application_row(no, app):
    """Flatten a portal application into a masterlist row.

    The scholar classification is worked out here rather than read, because
    only the Academic programme has one and it follows from the GWA.
    """
    p = app.student
    u = p.user
    middle = getattr(p, 'middle_name', '') or ''
    gwa = p.gwa or 0
    if app.scholarship.type == 'Academic':
        percent = 'Univ. Scholar' if gwa <= 1.29 else ('College Scholar' if gwa <= 1.50 else '')
    else:
        percent = ''

    row = _blank_row(no)
    row.update({
        'last_name': u.last_name or '',
        'first_name': u.first_name or '',
        'first_name1': u.first_name or '',
        'middle_name': middle,
        'm_i': _initial(middle),
        'sex': (p.gender or '')[:1].upper(),
        'brgy_st': p.barangay or '',
        'mun': p.municipality or '',
        'municipality': p.municipality or '',
        'prov': p.province or '',
        'province': p.province or '',
        'course': p.course or '',
        'yr': p.year_level or '',
        'year_level': p.year_level or '',
        'gwa': f'{gwa:.2f}' if gwa else '',
        'percent': percent,
        'number': p.student_id or '',
        'award_number': app.award_number,
        'cong_dist': app.congress_district,
        'scholarship_program': app.scholarship.name,
        'program': app.scholarship.name,
    })
    return row


def _affirmative_row(no, app):
    """Flatten an Affirmative or Staff record into a masterlist row.

    These carry a single ``full_name`` rather than separate fields, so the
    name is split back out. Two parts are read as first and last; anything
    longer treats the middle as a middle name.
    """
    parts = (app.full_name or '').strip().split()
    if len(parts) >= 3:
        last, first, middle = parts[-1], parts[0], parts[1]
    elif len(parts) == 2:
        last, first, middle = parts[-1], parts[0], ''
    else:
        last, first, middle = (parts[0] if parts else ''), '', ''

    name = 'BiPSU Staff Scholarship' if app.is_nsu_staff else 'Affirmative Action Scholarship'
    row = _blank_row(no)
    row.update({
        'last_name': last, 'first_name': first, 'first_name1': first,
        'middle_name': middle, 'm_i': _initial(middle),
        'sex': (app.gender or '')[:1].upper(),
        'brgy_st': app.barangay or '',
        'mun': app.municipality or '', 'municipality': app.municipality or '',
        'prov': app.province or '', 'province': app.province or '',
        'course': app.course or '',
        'yr': app.year_level or '', 'year_level': app.year_level or '',
        'percent': '100%' if app.is_nsu_staff else '75%',
        'number': app.student_id or '',
        'scholarship_program': name, 'program': name,
    })
    return row


def _imported_row(no, rec):
    """Flatten a spreadsheet-imported scholar into a masterlist row."""
    middle = rec.middle_name or ''
    gwa = rec.gwa or 0
    if rec.scholarship_type == 'Academic':
        percent = 'Univ. Scholar' if 0 < gwa <= 1.29 else ('College Scholar' if 0 < gwa <= 1.50 else '')
    else:
        percent = ''

    name = getattr(rec, '_program_name', '') or rec.scholarship_type

    row = _blank_row(no)
    row.update({
        'last_name': rec.last_name or '',
        'first_name': rec.first_name or '',
        'first_name1': rec.first_name or '',
        'middle_name': middle,
        'm_i': _initial(middle),
        'sex': (rec.gender or '')[:1].upper(),
        'brgy_st': rec.barangay or '',
        'mun': rec.municipality or '', 'municipality': rec.municipality or '',
        'prov': rec.province or '', 'province': rec.province or '',
        'course': rec.course or '',
        'yr': rec.year_level or '', 'year_level': rec.year_level or '',
        'gwa': f'{gwa:.2f}' if gwa else '',
        'percent': percent,
        'number': rec.student_id or '',
        'award_number': rec.award_number or '',
        'cong_dist': rec.congress_district or '',
        'scholarship_program': name, 'program': name,
    })
    return row


def _row_for(no, record):
    """Flatten any of the three record types into a masterlist row.

    The one place that knows all three shapes, so every renderer downstream
    sees a single flat dictionary.
    """
    from .models import ApplicantRecord, ImportedScholar

    if isinstance(record, ApplicantRecord):
        return _affirmative_row(no, record)
    if isinstance(record, ImportedScholar):
        return _imported_row(no, record)
    return _application_row(no, record)


def _gender_of(record):
    """The gender of any record type, wherever it keeps it."""
    from .models import Application

    if isinstance(record, Application):
        return record.student.gender
    return record.gender


def _sources(term_label=None):
    """Every scholar to appear on the masterlist for one term, by programme.

    All three sources are filtered by ``term_label``. They did not used to be:
    imported rows were scoped to the term while portal applications and
    applicant records were not, so choosing a semester moved only part of the
    report and every list silently carried every approved award ever made.
    """
    from .models import (STAFF_APPLICATION_DETAILS, STUDENT_DETAILS, Application,
                         ApplicantRecord, ImportedScholar,
                         Scholarship, SystemSettings, split_ched)

    if term_label is None:
        settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
        term_label = settings_obj.academic_year

    programme_names = dict(Scholarship.objects.values_list('type', 'name'))

    def imported(stype):
        """Unclaimed imported scholars of one programme, this term."""
        rows = list(
            ImportedScholar.objects
            .filter(scholarship_type=stype, term_label=term_label, claimed_by__isnull=True)
            .order_by('last_name', 'first_name')
        )
        for r in rows:
            r._program_name = programme_names.get(stype, stype)
        return rows

    def apps(stype):
        """Approved portal applications of one programme, this term, plus imports."""
        return list(
            Application.objects.filter(status='Approved', scholarship__type=stype,
                                       term_label=term_label)
            .select_related('student__user', 'scholarship', *STUDENT_DETAILS)
            .order_by('student__user__last_name', 'student__user__first_name')
        ) + imported(stype)

    ched_full, ched_half = split_ched(apps('CHED'))

    def affirmative(qualified_for):
        """Approved applicant records of one kind, this term, plus imports."""
        return list(
            ApplicantRecord.objects.filter(
                status='Approved', qualified_for=qualified_for,
                term_label=term_label,
            ).select_related(*STAFF_APPLICATION_DETAILS).order_by('full_name')
        ) + imported(qualified_for)

    return {
        'Academic': apps('Academic'),
        'DOST': apps('DOST'),
        'GSIS': apps('GSIS'),
        'TDP': apps('TDP'),
        'TES': apps('TES'),
        'CoScho': apps('CoScho'),
        'Sports': apps('Sports'),
        'CHED_FULL': ched_full,
        'CHED_HALF': ched_half,
        'SUC-TDP': apps('SUC-TDP'),
        'JLSS': apps('JLSS'),
        'FHE': apps('FHE'),
        'Affirmative': affirmative('Affirmative'),
        'Staff': affirmative('Staff'),
    }


def known_terms():
    """Every term the office can ask for a report on, newest first.

    All three sources are consulted, not just the imported one. A semester
    whose scholars all came through the portal used to be missing from the
    list entirely, and asking for it fell back to the active term — so the
    page answered a different question than the one selected, without saying
    so.
    """
    from .models import (Application, ApplicantRecord, ImportedScholar,
                         SystemSettings)
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    labels = set()
    for model in (ImportedScholar, Application, ApplicantRecord):
        labels.update(
            label for label in
            model.objects.values_list('term_label', flat=True).distinct()
            if label)
    labels.add(settings_obj.academic_year)
    return sorted(labels, key=_term_order, reverse=True)


def _term_order(label):
    """Sort key for a term label, oldest first; unparseable last."""
    try:
        yy, sem = label.split('-')
        return (int(yy), int(sem))
    except (ValueError, AttributeError):
        return (-1, -1)


def term_for(requested):
    """Validate a requested term, falling back to the active one.

    A label that is not on offer is not an error — a bookmark can outlive a
    term — so the active term is served instead.
    """
    label = (requested or '').strip()
    if label in known_terms():
        return label
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return settings_obj.academic_year


def build_context(sources=None, term_label=None):
    """Assemble every programme's rows for one term.

    Returns:
        ``(context, summary)``. The context is keyed by template slot and
        feeds the DOCX directly; the summary is the same data described —
        heading, layout, headers and total per programme — which is what the
        page and the PDF read, so neither has to understand slot names.

    Programmes with no scholars are kept, marked unused, and removed later by
    :func:`_drop_unused_sections`. Dropping them here would leave the
    template's tables and their headings mismatched.
    """
    sources = sources if sources is not None else _sources(term_label)
    headings = slot_headers()
    context = {slot: {'name': UNUSED_MARKER, 'female': [], 'male': [], 'students': []}
               for slot in ALL_SLOTS}
    summary = []

    for slot, heading, key, layout in PROGRAM_SLOTS:
        records = sources.get(key, [])
        build, gender_of = _row_for, _gender_of

        entry = {'name': heading, 'female': [], 'male': [], 'students': []}
        if layout == 'students':
            entry['students'] = [build(i, r) for i, r in enumerate(records, 1)]
        else:
            female = [r for r in records if _is_female(gender_of(r))]
            male = [r for r in records if not _is_female(gender_of(r))]
            entry['female'] = [build(i, r) for i, r in enumerate(female, 1)]
            entry['male'] = [build(i, r) for i, r in enumerate(male, 1)]

        context[slot] = entry
        summary.append({
            'slot': slot, 'heading': heading, 'key': key, 'layout': layout,
            'headers': headings.get(slot, []),
            'female': len(entry['female']), 'male': len(entry['male']),
            'students': len(entry['students']),
            'total': len(records),
        })

    return context, summary


def _restamp_period(document, sy, semester):
    """Rewrite the period line in the rendered document to the term asked for."""
    second = semester.strip().lower().startswith('2')
    year_re = re.compile(r'SY:\s*\d{4}\s*[-–]\s*\d{4}', re.I)
    sem_re = re.compile(r'\b1(st|ST)\b')

    def fix(text):
        """Rewrite the period text in one paragraph."""
        text = year_re.sub(f'SY: {sy}', text)
        if second:
            text = sem_re.sub(lambda m: '2ND' if m.group(1).isupper() else '2nd', text)
        return text

    def walk(paragraphs):
        """Visit every paragraph, including those inside tables."""
        for p in paragraphs:
            original = p.text
            if 'SY:' not in original.upper():
                continue
            updated = fix(original)
            if updated == original or not p.runs:
                continue
            p.runs[0].text = updated
            for run in p.runs[1:]:
                run.text = ''

    walk(document.paragraphs)
    for table in document.tables:
        for row in table.rows:
            for cell in row.cells:
                walk(cell.paragraphs)
    for section in document.sections:
        walk(section.header.paragraphs)
        walk(section.footer.paragraphs)


def _drop_unused_sections(document):
    """Remove the tables for programmes with no scholars this term.

    Done on the rendered document rather than the context, because a heading
    and its table are separate elements in the DOCX and both have to go —
    leaving the heading would print a programme with an empty table under it.
    """
    from docx.text.paragraph import Paragraph

    body = document.element.body
    children = [c for c in body.iterchildren()
                if c.tag.endswith('}p') or c.tag.endswith('}tbl')]

    def is_para(el):
        """Whether this element is a paragraph."""
        return el.tag.endswith('}p')

    def text_of(el):
        """A paragraph's text, or '' for a table."""
        return Paragraph(el, document).text.strip() if is_para(el) else ''

    headings = []
    for i, el in enumerate(children):
        if not is_para(el):
            continue
        for nxt in children[i + 1:]:
            if not is_para(nxt):
                break
            following = text_of(nxt)
            if not following:
                continue
            if following.upper().startswith('SCHOLARSHIP GRANT'):
                headings.append(i)
            break

    removed = 0
    for pos, start in enumerate(headings):
        if UNUSED_MARKER not in text_of(children[start]):
            continue
        end = headings[pos + 1] if pos + 1 < len(headings) else len(children)
        for el in children[start:end]:
            parent = el.getparent()
            if parent is not None:
                parent.remove(el)
                removed += 1

    for el in children:
        if is_para(el) and UNUSED_MARKER in text_of(el):
            para = Paragraph(el, document)
            for run in para.runs:
                run.text = run.text.replace(UNUSED_MARKER, '')
    return removed


def build_document(academic_year, semester, term_label=None):
    """Render the masterlist to a DOCX for one term.

    Returns:
        ``(buffer, summary)``, the buffer positioned at the start.

    Raises:
        FileNotFoundError: the template is missing, which is a deployment
            fault rather than a data one and is worth saying plainly.
    """
    from io import BytesIO
    from docxtpl import DocxTemplate

    if not os.path.exists(TEMPLATE_PATH):
        raise FileNotFoundError(
            f'The masterlist template is missing at {TEMPLATE_PATH}. '
            'Restore it from the office copy before generating this report.'
        )

    context, summary = build_context(term_label=term_label)
    tpl = DocxTemplate(TEMPLATE_PATH)
    tpl.render(context)
    _drop_unused_sections(tpl.docx)
    _restamp_period(tpl.docx, academic_year, semester)

    buf = BytesIO()
    tpl.save(buf)
    buf.seek(0)
    return buf, summary
