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
    per_portal = DEFAULTS_BY_PORTAL.get(portal, {})
    if scholarship_type in per_portal:
        return per_portal[scholarship_type]
    return DEFAULT_COLUMNS_BY_TYPE.get(scholarship_type, DEFAULT_COLUMNS)


CUSTOM_PREFIX = 'extra_'


def _slug(text):
    return re.sub(r'[^a-z0-9]+', '_', (text or '').strip().lower()).strip('_')


def custom_key(label):
    slug = _slug(label)
    return f'{CUSTOM_PREFIX}{slug}' if slug else ''


CATALOGUE_NAMES = ({key for key, _ in COLUMNS}
                   | {_slug(label) for _, label in COLUMNS})


def names_a_catalogue_column(label):
    return bool(label) and _slug(label) in CATALOGUE_NAMES


def catalogue_clashes(labels):
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
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    if kind == 'yesno':
        return list(YESNO_OPTIONS)
    if kind == 'choice':
        return list(column.get('options') or ())
    return []


def clean_value(column, raw):
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
    import math

    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number) if number == int(number) else number


def _clean_date(value):
    from datetime import datetime

    for fmt in (DATE_FORMAT,) + OTHER_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def excel_value(column, value):
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
    seen, chosen = set(), []
    for key in keys or ():
        if key in LABELS and key not in seen:
            seen.add(key)
            chosen.append(key)
    return chosen


def clean_custom(labels, types=None, options=None):
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
    from .models import Application

    holder = 'form_data' if isinstance(record, Application) else 'extra_data'
    return getattr(record, holder, None) or {}


def set_extra_values(record, values):
    from .models import Application

    holder = 'form_data' if isinstance(record, Application) else 'extra_data'
    current = dict(getattr(record, holder, None) or {})
    current.update(values)
    setattr(record, holder, current)
    record.save(update_fields=[holder])


def kind_of(record):
    from .models import AffirmativeStaffApplication, ImportedScholar

    if isinstance(record, ImportedScholar):
        return 'imported'
    if isinstance(record, AffirmativeStaffApplication):
        return 'staff'
    return 'award'


def _search_terms(record, flat):
    name = f"{flat.get('last_name', '')} {flat.get('first_name', '')}".strip().lower()
    return name, str(flat.get('number') or '').lower()


def _cell(column, flat, extras):
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
