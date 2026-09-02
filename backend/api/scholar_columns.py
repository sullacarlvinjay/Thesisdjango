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

# Where the two offices' tables disagreed about the same programme. UniFAST
# administers TES and reports it against CHED's award number; the SDSO archive
# listed the same scholars without one. That disagreement is what choosing a
# column set settles — but until a programme is configured, each office keeps
# the table it already had.
DEFAULTS_BY_PORTAL = {
    'unifast': {
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


def clean_choice(keys):
    """The catalogue columns out of a posted list, in catalogue order.

    Order comes from the catalogue rather than the form so a table always reads
    the way the reports do — the office is choosing which columns appear, not
    rearranging them.
    """
    wanted = set(keys or ())
    return [key for key, _ in COLUMNS if key in wanted]


def clean_custom(labels):
    """``[{'key', 'label'}]`` from the names typed into the form.

    Blanks are dropped, and a repeated name is kept once: two columns sharing a
    key would write to the same place and read back as duplicates of each other.
    """
    seen, columns = set(), []
    for label in labels or ():
        label = (label or '').strip()
        key = custom_key(label)
        if not key or key in seen:
            continue
        seen.add(key)
        columns.append({'key': key, 'label': label})
    return columns


def resolve(scholarship, scholarship_type=None, portal=''):
    """The ordered columns for a programme: ``[{'key', 'label', 'custom'}]``.

    Falls back to the columns that programme's table was hand-written with for
    one that has never been configured, and for one whose whole selection has
    since left the catalogue. ``scholarship_type`` covers the archive tabs that
    name a programme with no Scholarship row of its own; ``portal`` picks
    between the two offices where their tables differed.

    A configured programme ignores ``portal``: choosing the columns once is what
    makes both offices list the programme the same way.
    """
    stype = scholarship_type or getattr(scholarship, 'type', '')
    chosen = (clean_choice(getattr(scholarship, 'table_columns', None))
              or default_for(stype, portal))
    columns = [{'key': key, 'label': LABELS[key], 'custom': False,
                'filterable': key in FILTERABLE} for key in chosen]
    for extra in getattr(scholarship, 'extra_columns', None) or ():
        key, label = extra.get('key'), extra.get('label')
        if key and label:
            # A column the office types into holds whatever they typed, which is
            # exactly the kind of grouping they would want to filter on.
            columns.append({'key': key, 'label': label, 'custom': True,
                            'filterable': True})
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
            'cells': [
                {
                    'key': column['key'],
                    'custom': column['custom'],
                    'value': (extras.get(column['key'], '') if column['custom']
                              else flat.get(column['key'], '')),
                }
                for column in columns
            ],
            'search_name': _search_terms(record, flat)[0],
            'search_id': _search_terms(record, flat)[1],
        })
    return rows
