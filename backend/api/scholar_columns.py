"""Which columns a scholar table shows, and what goes in them.

Each funder wants a different sheet, so the default column set follows the
programme and a portal may override it again. The office can also define custom
columns per programme, stored as JSON on the record.

Rows are flattened through the masterlist row builder, so a scholar reads the
same way in a table as in the printed report — the alternative is two
formatters that drift apart.
"""

import re

from .masterlist_report import _row_for

COLUMNS = [
    ('award_number', 'Award No.'),
    ('last_name', 'Last Name'),
    ('first_name', 'First Name'),
    ('middle_name', 'Middle Name'),
    ('m_i', 'Middle Initial'),
    ('sex', 'Sex'),
    ('brgy_st', 'Brgy. / St.'),
    ('municipality', 'Municipality'),
    ('province', 'Province'),
    ('cong_dist', 'Cong. District'),
    ('course', 'Course'),
    ('year_level', 'Year Level'),
    ('gwa', 'GWA'),
    ('percent', '% / Type of Scholarship'),
    ('number', 'Student No.'),
    ('scholarship_program', 'Scholarship Program'),
]

LABELS = dict(COLUMNS)

FILTERABLE = {
    'sex', 'brgy_st', 'municipality', 'province', 'cong_dist', 'course',
    'year_level', 'percent', 'scholarship_program',
}

DEFAULT_COLUMNS = [
    'last_name', 'first_name', 'm_i', 'sex', 'brgy_st',
    'municipality', 'province', 'course', 'year_level', 'number',
    'scholarship_program',
]

DEFAULT_COLUMNS_BY_TYPE = {
    'Academic': [
        'last_name', 'first_name', 'middle_name', 'sex', 'brgy_st',
        'municipality', 'province', 'course', 'year_level', 'gwa', 'percent',
        'scholarship_program',
    ],
    'CHED': [
        'award_number', 'last_name', 'first_name', 'middle_name', 'sex',
        'brgy_st', 'municipality', 'province', 'cong_dist', 'course',
        'year_level', 'scholarship_program',
    ],
    'Staff': [
        'last_name', 'first_name', 'm_i', 'sex', 'course',
        'year_level', 'number', 'percent', 'scholarship_program',
    ],
    'Affirmative': [
        'last_name', 'first_name', 'middle_name', 'sex', 'brgy_st',
        'municipality', 'province', 'course', 'year_level',
        'scholarship_program',
    ],
}
DEFAULT_COLUMNS_BY_TYPE['TDP'] = DEFAULT_COLUMNS_BY_TYPE['CHED']
DEFAULT_COLUMNS_BY_TYPE['DOST'] = DEFAULT_COLUMNS_BY_TYPE['CHED']

DEFAULTS_BY_PORTAL = {
    'partner': {
        'TES': [
            'last_name', 'first_name', 'm_i', 'sex', 'brgy_st', 'municipality',
            'province', 'course', 'year_level', 'number', 'award_number',
            'scholarship_program',
        ],
    },
}


def default_for(scholarship_type, portal=''):
    """The columns a scholar table starts with for one programme.

    Different funders want different sheets — CHED wants award numbers and
    congressional districts, Academic wants the GWA — so the default follows
    the programme rather than being one list for everything. A portal may
    override it again; partners see TES differently from the office.
    """
    per_portal = DEFAULTS_BY_PORTAL.get(portal, {})
    if scholarship_type in per_portal:
        return per_portal[scholarship_type]
    return DEFAULT_COLUMNS_BY_TYPE.get(scholarship_type, DEFAULT_COLUMNS)


CUSTOM_PREFIX = 'extra_'


def _slug(text):
    """Reduce a label to a comparable key: lowercase, words joined by _."""
    return re.sub(r'[^a-z0-9]+', '_', (text or '').strip().lower()).strip('_')


def custom_key(label):
    """The storage key for a custom column, or '' if the label is empty.

    Prefixed so a custom column can never collide with a catalogue one in the
    same dictionary.
    """
    slug = _slug(label)
    return f'{CUSTOM_PREFIX}{slug}' if slug else ''


CATALOGUE_NAMES = ({key for key, _ in COLUMNS}
                   | {_slug(label) for _, label in COLUMNS})


def names_a_catalogue_column(label):
    """Whether this label is really a built-in column under another name.

    "Last name", "LAST NAME" and "last_name" are the same column. Letting one
    through as custom would give the office two columns holding the same
    thing, only one of which the reports know about.
    """
    return bool(label) and _slug(label) in CATALOGUE_NAMES


def catalogue_clashes(labels):
    """The labels in this list that duplicate a built-in column."""
    clashing = []
    for label in labels or ():
        label = (label or '').strip()
        if names_a_catalogue_column(label) and label not in clashing:
            clashing.append(label)
    return clashing


CUSTOM_TYPES = [
    ('text', 'Text'),
    ('number', 'Number'),
    ('date', 'Date'),
    ('choice', 'Choice list'),
    ('yesno', 'Yes / No'),
]
CUSTOM_TYPE_LABELS = dict(CUSTOM_TYPES)
DEFAULT_CUSTOM_TYPE = 'text'

YESNO_OPTIONS = ['Yes', 'No']

INPUT_TYPES = {'number': 'number', 'date': 'date'}

DATE_FORMAT = '%Y-%m-%d'

OTHER_DATE_FORMATS = ('%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y', '%d %B %Y')


def clean_options(raw):
    """Parse a choice list from a comma or newline separated string.

    Duplicates are dropped case-insensitively, keeping the first spelling the
    office typed, so a list is not silently reordered by re-saving.
    """
    parts = raw if isinstance(raw, (list, tuple)) else re.split(
        r'[,\n]', raw or '')
    seen, options = set(), []
    for part in parts:
        option = str(part).strip()
        if not option or option.lower() in seen:
            continue
        seen.add(option.lower())
        options.append(option)
    return options


def options_for(column):
    """The permitted values for a column, empty when it is free text."""
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    if kind == 'yesno':
        return list(YESNO_OPTIONS)
    if kind == 'choice':
        return list(column.get('options') or ())
    return []


def clean_value(column, raw):
    """Coerce one cell to the column's type, or ``None`` if it cannot be.

    Three outcomes, and the caller has to tell them apart: a value, ``''``
    for a blank cell, and ``None`` for something that does not fit the column
    at all. Returning ``''`` for a bad number would quietly discard data the
    office typed.
    """
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    value = ('' if raw is None else str(raw)).strip()
    if not value:
        return ''
    if kind == 'number':
        number = _as_number(value.replace(',', ''))
        if number is None:
            return None
        return str(number)
    if kind == 'date':
        return _clean_date(value)
    for option in options_for(column):
        if value.lower() == option.lower():
            return option
    return None if kind in ('choice', 'yesno') else value


def _as_number(text):
    """Parse a number, rejecting infinities and NaN.

    Whole floats come back as ints so a year does not land in a spreadsheet
    as ``2026.0``.
    """
    import math

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number == int(number) else number


def _clean_date(value):
    """Parse a date written any of the ways people write dates.

    Imports arrive from spreadsheets filled in by hand across several offices,
    so a single expected format would reject most of them.

    Returns:
        An ISO date string, or ``None`` if no format matched.
    """
    from datetime import datetime

    for fmt in (DATE_FORMAT,) + OTHER_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def excel_value(column, value):
    """The value to write into a spreadsheet cell, correctly typed.

    Numbers and dates are handed over as numbers and dates rather than text,
    so the office can sort and filter the download instead of receiving a
    sheet of strings. Anything that will not convert is written as text
    rather than dropped.
    """
    if not column.get('custom'):
        return value
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    text = ('' if value is None else str(value)).strip()
    if not text:
        return ''
    if kind == 'number':
        number = _as_number(text)
        return text if number is None else number
    if kind == 'date':
        from datetime import datetime
        try:
            return datetime.strptime(text, DATE_FORMAT).date()
        except ValueError:
            return text
    return text


def clean_choice(keys):
    """Keep the known column keys from a posted list, in order, once each."""
    seen, chosen = set(), []
    for key in keys or ():
        if key in LABELS and key not in seen:
            seen.add(key)
            chosen.append(key)
    return chosen


def clean_custom(labels, types=None, options=None):
    """Validate the custom columns posted from the column picker.

    Drops anything unusable — blank labels, duplicates, and labels that
    rename a built-in column — rather than storing a definition the table
    cannot render.
    """
    types = list(types or ())
    options = list(options or ())
    seen, columns = set(), []
    for index, label in enumerate(labels or ()):
        label = (label or '').strip()
        key = custom_key(label)
        if not key or key in seen or names_a_catalogue_column(label):
            continue
        seen.add(key)
        kind = types[index] if index < len(types) else DEFAULT_CUSTOM_TYPE
        if kind not in CUSTOM_TYPE_LABELS:
            kind = DEFAULT_CUSTOM_TYPE
        chosen = clean_options(options[index] if index < len(options) else '')
        if kind == 'choice' and not chosen:
            kind = DEFAULT_CUSTOM_TYPE
        column = {'key': key, 'label': label, 'type': kind}
        if kind == 'choice':
            column['options'] = chosen
        columns.append(column)
    return columns


def resolve(scholarship, scholarship_type=None, portal='', override=None):
    """Work out the full column set for a table: built-in plus custom.

    Returns the columns in display order, each a dict the template can render
    without knowing whether it came from the catalogue or from the office.
    """
    stype = scholarship_type or getattr(scholarship, 'type', '')
    chosen = (clean_choice(getattr(override, 'table_columns', None))
              or clean_choice(getattr(scholarship, 'table_columns', None))
              or default_for(stype, portal))
    columns = [{'key': key, 'label': LABELS[key], 'custom': False,
                'filterable': key in FILTERABLE} for key in chosen]
    source = override if getattr(override, 'extra_columns', None) else scholarship
    for extra in getattr(source, 'extra_columns', None) or ():
        key, label = extra.get('key'), extra.get('label')
        if key and label:
            kind = extra.get('type') or DEFAULT_CUSTOM_TYPE
            if kind not in CUSTOM_TYPE_LABELS:
                kind = DEFAULT_CUSTOM_TYPE
            columns.append({'key': key, 'label': label, 'custom': True,
                            'filterable': True, 'type': kind,
                            'options': list(extra.get('options') or ())})
    return columns


def extra_values(record):
    """The custom-column values stored on one record.

    Applications keep them in ``form_data`` and everything else in
    ``extra_data``; this hides which.
    """
    from .models import Application

    holder = 'form_data' if isinstance(record, Application) else 'extra_data'
    return getattr(record, holder, None) or {}


def set_extra_values(record, values):
    """Merge custom-column values onto one record and save.

    Merges rather than replaces, so editing a table that shows three of five
    custom columns does not erase the other two.
    """
    from .models import Application

    holder = 'form_data' if isinstance(record, Application) else 'extra_data'
    current = dict(getattr(record, holder, None) or {})
    current.update(values)
    setattr(record, holder, current)
    record.save(update_fields=[holder])


def kind_of(record):
    """Which sort of record this is: ``award``, ``staff`` or ``imported``.

    The three carry their fields in different places, and the templates need
    to know which they are holding.
    """
    from .models import ApplicantRecord, ImportedScholar

    if isinstance(record, ImportedScholar):
        return 'imported'
    if isinstance(record, ApplicantRecord):
        return 'staff'
    return 'award'


def _search_terms(record, flat):
    """Lowercased name and student number, for client-side filtering."""
    name = f"{flat.get('last_name', '')} {flat.get('first_name', '')}".strip().lower()
    return name, str(flat.get('number') or '').lower()


def _cell(column, flat, extras):
    """Build one rendered cell, catalogue or custom."""
    if not column['custom']:
        return {'key': column['key'], 'custom': False,
                'value': flat.get(column['key'], '')}
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    return {
        'key': column['key'],
        'custom': True,
        'value': extras.get(column['key'], ''),
        'type': kind,
        'options': options_for(column),
        'input_type': INPUT_TYPES.get(kind, 'text'),
    }


def rows_for(records, columns, start=1):
    """Render records into table rows for one column set.

    Flattens each record through the masterlist row builder, so a scholar
    reads the same way in a table as in the printed report — the alternative
    is two formatters that drift apart.

    Args:
        records: the scholars to render.
        columns: the resolved column set from :func:`resolve`.
        start: the number to give the first row, for paging.
    """
    rows = []
    for offset, record in enumerate(records):
        number = start + offset
        flat = _row_for(number, record)
        extras = extra_values(record)
        search_name, search_id = _search_terms(record, flat)
        rows.append({
            'no': number,
            'obj': record,
            'kind': kind_of(record),
            'cells': [_cell(column, flat, extras) for column in columns],
            'search_name': search_name,
            'search_id': search_id,
        })
    return rows
