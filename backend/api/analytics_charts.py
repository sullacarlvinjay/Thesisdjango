"""The parts of the analytics dashboard that do not touch the database.

Banding, identity, tier words and the readers that pull figures back out of a
filed spreadsheet. They were closures inside ``_build_analytics_context``,
where nothing could reach them: the function ran at cyclomatic complexity 101
and no independent path through any one chart could be exercised on its own.
Each is a plain function here, taking what it needs and returning what it
computed, so a test can state one case and read one answer.
"""

import logging
from collections.abc import Iterable
from typing import Any

logger = logging.getLogger(__name__)

GWA_BANDS = ('1.00-1.25', '1.26-1.50', '1.51-1.75', '1.76-2.00', '2.01-2.50')

GWA_CEILINGS = (1.25, 1.50, 1.75, 2.00, 2.50)

ROSTER_TYPES = ('Affirmative', 'Staff')

UNKNOWN_COURSE = 'Unknown'


def band_for(value: Any) -> str | None:
    """The GWA band a mark falls in, or ``None``.

    Lower is better on this scale, so the bands read as ceilings. Anything
    below 1.0 is not a real GWA and is excluded rather than banded.
    """
    try:
        mark = float(value or 0)
    except (ValueError, TypeError):
        return None
    if mark < 1.0:
        return None
    for band, ceiling in zip(GWA_BANDS, GWA_CEILINGS, strict=True):
        if mark <= ceiling:
            return band
    return None


def banded(values: Iterable[Any]) -> dict[str, int] | None:
    """Count marks into GWA bands.

    Returns ``None`` when nothing landed in any band, so the page can omit
    the chart rather than draw an axis over no data.
    """
    buckets = {band: 0 for band in GWA_BANDS}
    found = False
    for value in values:
        band = band_for(value)
        if band:
            buckets[band] += 1
            found = True
    return buckets if found else None


def empty_bands() -> dict[str, int]:
    """A zeroed bucket per band, for a term with nothing to show."""
    return {band: 0 for band in GWA_BANDS}


def identity(student_id: Any, last: Any, first: Any) -> str | None:
    """A stable key for one person across terms and sources.

    Student number where there is one, normalised name otherwise. Without
    it the same scholar appearing in two filed spreadsheets counts twice
    in a trend, which is precisely the number the office reads.
    """
    digits = ''.join(ch for ch in (student_id or '').upper() if ch.isalnum())
    if digits:
        return f'id:{digits}'
    name = ' '.join(' '.join((last or '', first or '')).upper().split())
    return f'name:{name}' if name else None


def tier_word(text: Any) -> str:
    """Full or Half from however a sheet spelled the CHED tier."""
    lowered = str(text or '').lower()
    if 'full' in lowered:
        return 'Full'
    if 'half' in lowered or 'partial' in lowered:
        return 'Half'
    return ''


def as_number(value: Any) -> float:
    """A float from anything, or 0.0."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def label_sort_key(label: str) -> int:
    """Sort key for a term label; unparseable sorts first."""
    try:
        year, semester = label.split('-')
        return int(year) * 10 + int(semester)
    except Exception:
        return 0


def subtype(stype: str, row: dict[str, Any]) -> str:
    """The series a scholar belongs to within their programme.

    Academic splits by scholar classification and CHED by tier, because a
    single line for either would hide the split the office reports on.
    """
    if stype == 'Academic':
        from .constants import academic_classification

        label = academic_classification(as_number(row.get('gwa')))
        return label if label in ('University Scholar', 'College Scholar') else ''
    if stype == 'CHED':
        return {'Full': 'Full Merit', 'Half': 'Half Merit'}.get(
            (row.get('tier') or '').strip(), '')
    return ''


def series_name(stype: str, sub: str) -> str:
    """The chart series label for a programme and subtype."""
    return f'{stype} — {sub}' if sub else stype


def course_distribution(counts: dict[str, int]) -> list[dict[str, Any]]:
    """Course counts as chart rows, commonest course first."""
    return [{'course': course, 'scholars': total}
            for course, total in sorted(counts.items(), key=lambda pair: -pair[1])]


def course_chart_height(course_dist: list) -> int:
    """Tall enough for one bar per course."""
    return max(420, 150 + len(course_dist) * 34)


def trend_chart_height(trend_series: list) -> int:
    """Tall enough for the legend the trend chart will carry."""
    return max(420, 250 + len(trend_series) * 26)


def _sheet_rows(excel_file: Any, stype: str, label: str) -> Any:
    """The worksheet of a filed spreadsheet, or ``None``.

    A sheet the office filed months ago can be anything at all, so every
    failure to read one is logged and treated as no data rather than as a
    broken dashboard.
    """
    from .views_archives import _rollover_workbook

    try:
        return _rollover_workbook(excel_file).active
    except Exception:
        logger.exception('analytics: could not read rollover sheet for %s %s',
                         stype, label)
        return None


def _heading_index(worksheet: Any, *wanted: str) -> int | None:
    """The index of the first heading containing any of these words.

    Found by heading rather than by position, because the column order
    differs between funders.
    """
    for cell in worksheet[1]:
        heading = str(cell.value or '').strip().lower()
        if heading and any(word in heading for word in wanted):
            return cell.column - 1
    return None


def _cell(row: Any, index: int | None) -> str:
    """One cell as trimmed text, tolerating short rows."""
    if index is None or index >= len(row):
        return ''
    return str(row[index]).strip() if row[index] is not None else ''


def course_counts_from_sheet(record: Any, stype: str,
                             label: str) -> dict[str, int]:
    """Scholars per course, read out of a filed spreadsheet.

    Used for past terms, whose figures live in the file rather than in the
    database.
    """
    if not record or not record.excel_file:
        return {}
    worksheet = _sheet_rows(record.excel_file, stype, label)
    if worksheet is None:
        return {}
    course_col = _heading_index(worksheet, 'course')
    if course_col is None:
        return {}

    counts: dict[str, int] = {}
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        course = _cell(row, course_col)
        if course:
            counts[course] = counts.get(course, 0) + 1
    return counts


def gwa_from_sheet(record: Any, label: str) -> dict[str, int] | None:
    """GWA bands read out of a filed Academic spreadsheet."""
    if not record or not record.excel_file:
        return None
    worksheet = _sheet_rows(record.excel_file, 'Academic', label)
    if worksheet is None:
        return None
    gwa_col = _heading_index(worksheet, 'gwa')
    if gwa_col is None:
        return None
    return banded(
        row[gwa_col] for row in worksheet.iter_rows(min_row=2, values_only=True)
        if row and row[0] is not None and gwa_col < len(row)
    )


def details_from_sheet(record: Any, stype: str,
                       label: str) -> dict[str, dict[str, Any]]:
    """One scholar per row, read out of a filed spreadsheet."""
    if not record or not record.excel_file:
        return {}
    worksheet = _sheet_rows(record.excel_file, stype, label)
    if worksheet is None:
        return {}

    last_col = _heading_index(worksheet, 'last name')
    first_col = _heading_index(worksheet, 'first name')
    id_col = _heading_index(worksheet, 'student number', 'student id', 'student no')
    if last_col is None and id_col is None:
        return {}
    course_col = _heading_index(worksheet, 'course')
    gwa_col = _heading_index(worksheet, 'gwa')
    tier_col = _heading_index(worksheet, 'award tier', 'scholar type', 'tier')

    people = {}
    for row in worksheet.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        key = identity(_cell(row, id_col), _cell(row, last_col),
                       _cell(row, first_col))
        if key:
            people[key] = {'course': _cell(row, course_col),
                           'gwa': _cell(row, gwa_col),
                           'tier': tier_word(_cell(row, tier_col))}
    return people


def merge_people(per_term: Iterable[dict[str, dict[str, Any]]],
                 ) -> dict[str, dict[str, Any]]:
    """Merge scholars across several terms, keyed by identity.

    A later term wins unless it carries less detail, so a scholar recorded
    fully in one term is not replaced by a sparser row from another.
    """
    merged = {}
    for people in per_term:
        for key, row in people.items():
            if key in merged and not (row.get('course') or row.get('gwa')):
                continue
            merged[key] = row
    return merged


def count_courses(people: dict[str, dict[str, Any]]) -> dict[str, int]:
    """Course counts over merged scholar rows."""
    counts: dict[str, int] = {}
    for row in people.values():
        course = str(row.get('course') or UNKNOWN_COURSE).strip() or UNKNOWN_COURSE
        counts[course] = counts.get(course, 0) + 1
    return counts


def rename_unsplit_series(trend_data: list[dict[str, Any]],
                          trend_types: Iterable[str]) -> None:
    """Give a programme's unsplit total a name of its own.

    Where a programme has any split series at all, a bare total alongside
    them is not the programme — it is the scholars whose level was never
    recorded, and a legend that calls it ``Academic`` reads as a double
    count.
    """
    for stype in trend_types:
        prefix = f'{stype} — '
        if not any(name.startswith(prefix)
                   for entry in trend_data for name in entry['counts']):
            continue
        renamed = f'{stype} — Level not recorded'
        for entry in trend_data:
            if stype in entry['counts']:
                entry['counts'][renamed] = entry['counts'].pop(stype)
                entry['per_type'] = {k: v for k, v in entry['counts'].items() if v}


def series_for(trend_data: list[dict[str, Any]],
               trend_types: Iterable[str]) -> list[str]:
    """The chart series to draw, in programme order, dropping empty ones."""
    names = []
    for stype in trend_types:
        prefix = f'{stype} — '
        candidates = sorted({
            name for entry in trend_data for name in entry['counts']
            if name == stype or name.startswith(prefix)
        })
        for name in candidates:
            if name in names:
                continue
            if any(entry['counts'].get(name) for entry in trend_data):
                names.append(name)
    return names
