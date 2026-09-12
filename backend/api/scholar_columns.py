"""Which columns a scholarship's archive table shows, and how to fill them.

The archive page used to carry a hand-written table per programme — seven of
them, each with its own headings and its own three copies of the row markup, one
per shape a scholar can arrive in. Adding a column meant editing the same row
three times in one block and leaving the other six behind.

A programme now says which columns it wants. :func:`resolve` turns that choice
into an ordered list, :func:`rows_for` turns a list of scholars into cells in
that order, and the template renders whatever it is handed.

The catalogue is deliberately the set of columns the office already reports on —
the headings in the masterlist document and the archive tables — so a column can
be shown, hidden and reordered without inventing data no report has ever asked
for. What a programme needs beyond that is a custom column: the office names it
and types a value per scholar.
"""
import re

from .masterlist_report import _row_for

# key -> heading. The keys are the ones masterlist_report already builds a row
# out of, so a column shown here is a column the reports can print.
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

# Columns whose values repeat across scholars, and so make a useful filter. A
# name, a student number or an award number is one row each — a dropdown of them
# is just the list again.
FILTERABLE = {
    'sex', 'brgy_st', 'municipality', 'province', 'cong_dist', 'course',
    'year_level', 'percent', 'scholarship_program',
}

# What a programme shows before anyone has chosen. These are the columns each
# hand-written table actually carried, read off the markup they replaced —
# they were never all the same, and flattening them to one list dropped the
# award number from every programme that reports one.
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
    # The three agency programmes are reported against an award number and the
    # congressional district the agency allocates by.
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

# Where a partner's table and the SDSO's disagreed about the same programme. A
# funder reports its scholars against the award number it issued them; the SDSO
# archive lists the same scholars without one. That disagreement is what
# choosing a column set settles — but until a programme is configured, each side
# keeps the table it already had.
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
    """The columns a programme shows until the office picks its own.

    The order here is the order rendered — these lists are read off the tables
    they replaced, so an unconfigured programme is listed exactly as before.
    """
    per_portal = DEFAULTS_BY_PORTAL.get(portal, {})
    if scholarship_type in per_portal:
        return per_portal[scholarship_type]
    return DEFAULT_COLUMNS_BY_TYPE.get(scholarship_type, DEFAULT_COLUMNS)


# A custom column's key is prefixed so it can never be mistaken for a catalogue
# one, whatever the office names it.
CUSTOM_PREFIX = 'extra_'


def custom_key(label):
    """A storage key for a column the office named. '' when the name is unusable.

    Derived from the label rather than counted, so renaming a column to the same
    words keeps the values already typed under it.
    """
    slug = re.sub(r'[^a-z0-9]+', '_', (label or '').strip().lower()).strip('_')
    return f'{CUSTOM_PREFIX}{slug}' if slug else ''


# ── What kind of data a column the office added holds.
#
# A custom column used to be a name and nothing else: the office typed one and
# every scholar's row got an empty text box under it, so a single 'Batch' column
# came back holding '2026-A', '2026 A', 'AY 2026', 'n/a' and blank — five
# spellings of four different things, in the column a report groups and sorts
# by. The office says what the column holds at the moment it names it, and a
# value that is not that is refused rather than written.
#
# The list is closed on purpose. Each kind here is a control a row can be filled
# in through *and* a cell the workbook can carry — a kind with neither would be
# a text box wearing a label, which is what this replaces.
CUSTOM_TYPES = [
    ('text', 'Text'),
    ('number', 'Number'),
    ('date', 'Date'),
    ('choice', 'Choice list'),
    ('yesno', 'Yes / No'),
]
CUSTOM_TYPE_LABELS = dict(CUSTOM_TYPES)
DEFAULT_CUSTOM_TYPE = 'text'

# Yes / No is a choice list whose options are already decided. It is stored as
# the words rather than as a boolean because the archive, the workbook and the
# masterlist all print the cell, and 'True' is not something an office writes on
# a list of scholars.
YESNO_OPTIONS = ['Yes', 'No']

# The box a value is typed into, per kind. A kind not named here gets a plain
# text box; the two here get the browser's own picker and its own validation.
INPUT_TYPES = {'number': 'number', 'date': 'date'}

# What a date column stores, and what `<input type="date">` posts and reads back.
DATE_FORMAT = '%Y-%m-%d'

# Formats accepted on the way in but never written. The date box cannot post
# any of them; they are here for values that arrived some other way — an office
# import, or a column switched from Text to Date after values were typed under
# it — so that switching the kind does not blank the column.
#
# Month-first leads, because '06/07/2026' is genuinely ambiguous and the office
# writes it the way the university does. Day-first follows and so only catches
# what month-first cannot read at all, like '15/06/2026'.
OTHER_DATE_FORMATS = ('%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y', '%d %B %Y')


def clean_options(raw):
    """The options of a choice column, from the line the office typed them on.

    Split on commas and newlines both, because both are how a short list gets
    typed. De-duplicated case-insensitively: two options differing only in case
    read as one answer, and would split one group across two rows of every
    report that counts by this column.
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
    """The values a column accepts, or ``[]`` where it is not a list of them."""
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    if kind == 'yesno':
        return list(YESNO_OPTIONS)
    if kind == 'choice':
        return list(column.get('options') or ())
    return []


def clean_value(column, raw):
    """One typed cell, in the shape its column declared. ``None`` refuses it.

    Refused rather than coerced, and refused one cell at a time: a Number column
    handed 'n/a' should leave that cell as it was and say so — storing 0 would
    print a real-looking figure nobody typed — and rejecting the whole post
    would throw away the forty rows in the same save that were fine.

    Blank is always accepted. A column the office added is not a column every
    scholar has an answer for, and refusing the empty box would make it one.
    """
    kind = column.get('type') or DEFAULT_CUSTOM_TYPE
    value = ('' if raw is None else str(raw)).strip()
    if not value:
        return ''
    if kind == 'number':
        number = _as_number(value.replace(',', ''))
        if number is None:
            return None
        # Written back the way it was meant: a whole number keeps no '.0', which
        # is how a batch size or a year is put on a list.
        return str(number)
    if kind == 'date':
        return _clean_date(value)
    for option in options_for(column):
        if value.lower() == option.lower():
            return option           # stored in the office's own spelling
    return None if kind in ('choice', 'yesno') else value


def _as_number(text):
    """``int`` or ``float`` for a number typed into a cell, else ``None``.

    ``float()`` also reads 'inf' and 'nan', which are not figures anybody means
    to put on a scholars list and which raise on the way to an ``int`` — so they
    are refused here rather than 500ing the save.
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
    """A date cell as ISO, or ``None`` when it is not a date at all."""
    from datetime import datetime

    for fmt in (DATE_FORMAT,) + OTHER_DATE_FORMATS:
        try:
            return datetime.strptime(value, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def excel_value(column, value):
    """One cell as a workbook should carry it, rather than as a page prints it.

    A number written as text sorts '10' above '9' and cannot be summed; a date
    written as text cannot be filtered by month. Both are the first things done
    to a downloaded scholars list, so the kind the office declared is carried
    into the cell rather than left behind on the page.

    A value that does not parse goes in as it stands rather than being dropped —
    a cell the office can see and fix beats a blank it cannot.
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
    """The catalogue columns out of a posted list, in the order given.

    The order is kept, because the office asked to control it: the picker shows
    the table as it will read, numbered, and a column moved there moves in the
    archive and in the workbook that follows from it. Anything not a catalogue
    key is dropped, and a key repeated is kept once — two copies of a column
    would render the same value twice under the same heading.

    This used to re-sort into catalogue order on the grounds that the office was
    choosing *which* columns appear rather than rearranging them. That was a
    smaller claim than the office actually wanted.
    """
    seen, chosen = set(), []
    for key in keys or ():
        if key in LABELS and key not in seen:
            seen.add(key)
            chosen.append(key)
    return chosen


def clean_custom(labels, types=None, options=None):
    """``[{'key', 'label', 'type', 'options'}]`` from the columns the office named.

    The three lists are parallel — one row of the form is a name, the kind of
    data it holds, and for a choice list the options it offers — so they are
    read by position, blank rows included. Dropping the blanks first would slide
    every kind after one onto the wrong column, which is the kind of fault that
    shows up as a Date column refusing dates weeks later.

    Blanks are dropped, and a repeated name is kept once: two columns sharing a
    key would write to the same place and read back as duplicates of each other.

    A kind that is not one of ``CUSTOM_TYPES`` is read as Text, and so is a
    choice list left with no options — a dropdown nobody can pick anything from
    is a column that can never be filled in.
    """
    types = list(types or ())
    options = list(options or ())
    seen, columns = set(), []
    for index, label in enumerate(labels or ()):
        label = (label or '').strip()
        key = custom_key(label)
        if not key or key in seen:
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
    """The ordered columns for a programme: ``[{'key', 'label', 'custom'}]``.

    Falls back to the columns that programme's table was hand-written with for
    one that has never been configured, and for one whose whole selection has
    since left the catalogue. ``scholarship_type`` covers the archive tabs that
    name a programme with no Scholarship row of its own; ``portal`` picks
    between the two offices where their tables differed.

    A configured programme ignores ``portal``: choosing the columns once is what
    makes both offices list the programme the same way.

    ``override`` is one reader's own choice for this programme — an
    :class:`~api.models.PartnerTableColumns` row, or anything else carrying
    ``table_columns`` and ``extra_columns``. It wins where it has a selection,
    and falls through to the office's where it does not, so a partner that has
    never rearranged anything sees the table everybody else does. Nothing here
    writes: the override exists precisely so a partner's layout cannot reach
    the office's ``Scholarship`` row.
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
            # Stored before a column declared its kind means Text, which is what
            # every custom column was until it could say otherwise.
            kind = extra.get('type') or DEFAULT_CUSTOM_TYPE
            if kind not in CUSTOM_TYPE_LABELS:
                kind = DEFAULT_CUSTOM_TYPE
            # A column the office types into holds whatever they typed, which is
            # exactly the kind of grouping they would want to filter on.
            columns.append({'key': key, 'label': label, 'custom': True,
                            'filterable': True, 'type': kind,
                            'options': list(extra.get('options') or ())})
    return columns


def extra_values(record):
    """The custom-column values held on one scholar, whatever shape they are.

    An award keeps them in ``form_data``, which already exists for exactly this
    — whatever the applicant sent that has no column of its own. The imported
    and staff records have an ``extra_data`` field of their own, because for
    most programmes an imported row *is* the record and a custom column that
    only worked on portal awards would be empty everywhere it mattered.
    """
    from .models import Application

    holder = 'form_data' if isinstance(record, Application) else 'extra_data'
    return getattr(record, holder, None) or {}


def set_extra_values(record, values):
    """Merge typed values into a scholar's custom columns and save that field."""
    from .models import Application

    holder = 'form_data' if isinstance(record, Application) else 'extra_data'
    current = dict(getattr(record, holder, None) or {})
    current.update(values)
    setattr(record, holder, current)
    record.save(update_fields=[holder])


def kind_of(record):
    """'award' | 'imported' | 'staff' — which row actions and edit form apply."""
    from .models import AffirmativeStaffApplication, ImportedScholar

    if isinstance(record, ImportedScholar):
        return 'imported'
    if isinstance(record, AffirmativeStaffApplication):
        return 'staff'
    return 'award'


def _search_terms(record, flat):
    """What the table's search box matches a row on: the name and the ID."""
    name = f"{flat.get('last_name', '')} {flat.get('first_name', '')}".strip().lower()
    return name, str(flat.get('number') or '').lower()


def _cell(column, flat, extras):
    """One cell of one row: its value, and how a custom one is typed into.

    The control belongs here rather than in the template because it follows from
    the kind the column declared, and the template would otherwise have to know
    the kinds — which is the same knowledge in a second place, spelt in a
    language that cannot be tested.
    """
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
    """One dict per scholar, with cells already in the order ``columns`` asks.

    Keeping the lookup here rather than in the template is what lets a single
    table serve all three record shapes: the differences between an award, an
    imported row and a staff application are resolved into a flat row before the
    template ever sees one.
    """
    rows = []
    for offset, record in enumerate(records):
        number = start + offset
        flat = _row_for(number, record)
        extras = extra_values(record)
        rows.append({
            'no': number,
            'obj': record,
            'kind': kind_of(record),
            'cells': [_cell(column, flat, extras) for column in columns],
            'search_name': _search_terms(record, flat)[0],
            'search_id': _search_terms(record, flat)[1],
        })
    return rows
