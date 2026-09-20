"""The SDSO analytics dashboard.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render
from .models import Scholarship, Application, ApplicantRecord
import logging
from .views_shared import _vpsea_required
from . import analytics_charts as charts

logger = logging.getLogger(__name__)


class TermWindow:
    """Which term the dashboard is showing, and where its figures come from.

    The active term is answered from the database; a past one from the
    spreadsheet filed when it closed. Nearly every branch in this module
    turns on that difference, so it is stated once here and passed around
    rather than rediscovered in each chart.
    """
    def __init__(self, active_label, selected_label, term_labels, whole_year):
        self.active_label = active_label
        self.selected_label = selected_label
        self.term_labels = term_labels
        self.whole_year = whole_year

    @property
    def is_active(self):
        """Whether the selected term is the one currently running."""
        return self.selected_label == self.active_label

    def sheet_for(self, stype, label=None):
        """The filed spreadsheet for a programme in this term, if any."""
        from .models import ScholarListImport

        return ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=label or self.selected_label).first()


def _imported(stype, label, unclaimed_only=False):
    """Imported scholars for one programme and term."""
    from .models import ImportedScholar

    rows = ImportedScholar.objects.filter(
        scholarship_type=stype, term_label=label)
    return rows.filter(claimed_by__isnull=True) if unclaimed_only else rows


def _term_labels():
    """Every term the dashboard can be pointed at, newest first."""
    from .models import ImportedScholar, ScholarListImport

    labels = set(
        ScholarListImport.objects.values_list('term_label', flat=True).distinct()
    )
    labels |= set(
        ImportedScholar.objects.exclude(term_label='')
        .values_list('term_label', flat=True).order_by().distinct()
    )
    return sorted(labels, reverse=True)


def _term_choices(all_labels, active_label):
    """The term picker: one group per school year, plus whole-year entries.

    Returns:
        ``(sy_groups, whole_year_terms, all_sy_display)``.
    """
    from .models import SystemSettings

    terms_by_year = {}
    for label in all_labels:
        terms_by_year.setdefault(
            SystemSettings.parse_label(label)['sy'], []).append(label)

    whole_year_terms = {}
    for labels in terms_by_year.values():
        if len(set(labels)) > 1:
            key = f"{sorted(labels)[0].split('-')[0]}-Y"
            whole_year_terms[key] = sorted(set(labels))

    sy_groups = []
    for sy in sorted(terms_by_year, reverse=True):
        labels = sorted(set(terms_by_year[sy]))
        options = []
        year_key = f"{labels[0].split('-')[0]}-Y"
        if year_key in whole_year_terms:
            options.append((year_key, 'Whole academic year'))
        options += [(label, SystemSettings.parse_label(label)['semester'])
                    for label in labels]
        sy_groups.append({'sy': sy, 'options': options})

    all_sy_display = [
        (label, '{sy} — {semester}'.format(**SystemSettings.parse_label(label)))
        for label in all_labels
    ]
    return sy_groups, whole_year_terms, all_sy_display


def _selected_window(request, all_labels, whole_year_terms, active_label):
    """The term the request asked for, falling back to the active one."""
    selectable = set(all_labels) | set(whole_year_terms)
    selected = request.GET.get('sy', active_label)
    if selected not in selectable:
        selected = active_label
    whole_year = selected in whole_year_terms
    return TermWindow(active_label, selected,
                      whole_year_terms.get(selected, [selected]), whole_year)


def _programme_total(stype, window):
    """How many scholars one programme has in the selected term."""
    from .models import ApplicantRecord

    if window.is_active:
        if stype in charts.ROSTER_TYPES:
            counted = ApplicantRecord.objects.filter(
                status='Approved', qualified_for=stype).count()
        else:
            counted = Application.objects.filter(
                status='Approved', scholarship__type=stype).count()
        counted += _imported(stype, window.active_label, unclaimed_only=True).count()
    else:
        counted = _imported(stype, window.selected_label).count()

    if counted:
        return counted
    record = window.sheet_for(stype)
    return record.scholar_count if record else 0


def _course_counts(stype, window):
    """Scholars per course for one programme in the selected term."""
    from django.db.models import Count

    from .models import ApplicantRecord

    counts = {}
    if window.is_active:
        if stype in charts.ROSTER_TYPES:
            rows = (ApplicantRecord.objects
                    .filter(status='Approved', qualified_for=stype)
                    .values('enrollment__course').annotate(n=Count('id')))
            field = 'enrollment__course'
        else:
            rows = (Application.objects
                    .filter(status='Approved', scholarship__type=stype)
                    .values('student__enrollment__course').annotate(n=Count('id')))
            field = 'student__enrollment__course'
        for row in rows:
            key = row[field] or charts.UNKNOWN_COURSE
            counts[key] = counts.get(key, 0) + row['n']

        imported = (_imported(stype, window.active_label, unclaimed_only=True)
                    .values('course').annotate(n=Count('id')))
        for row in imported:
            key = row['course'] or charts.UNKNOWN_COURSE
            counts[key] = counts.get(key, 0) + row['n']
    else:
        for row in _imported(stype, window.selected_label).values('course'):
            key = row['course'] or charts.UNKNOWN_COURSE
            counts[key] = counts.get(key, 0) + 1

    if counts:
        return counts
    return charts.course_counts_from_sheet(
        window.sheet_for(stype), stype, window.selected_label)


def _gwa_buckets(window):
    """Academic GWA counted into bands for the selected term."""
    if window.is_active:
        marks = [
            row['student__enrollment__gwa'] for row in Application.objects.filter(
                status='Approved', scholarship__type='Academic'
            ).values('student__enrollment__gwa')
        ]
        marks += [row['gwa'] for row in
                  _imported('Academic', window.active_label, unclaimed_only=True)
                  .values('gwa')]
        buckets = charts.banded(marks)
    else:
        buckets = charts.banded(
            row['gwa'] for row in
            _imported('Academic', window.selected_label).values('gwa')
        )
    fallback = charts.gwa_from_sheet(
        window.sheet_for('Academic'), window.selected_label)
    return buckets or fallback or charts.empty_bands()


def _roster_details(stype):
    """Affirmative and Staff scholars, keyed by identity."""
    from .models import ApplicantRecord

    people = {}
    rows = ApplicantRecord.objects.filter(
        status='Approved', qualified_for=stype
    ).values('enrollment__student_id', 'full_name', 'enrollment__course')
    for row in rows:
        parts = (row['full_name'] or '').split()
        key = charts.identity(row['enrollment__student_id'],
                              parts[-1] if parts else '',
                              parts[0] if len(parts) > 1 else '')
        people[key] = {'course': row['enrollment__course'],
                       'gwa': None, 'tier': ''}
    return people


def _award_details(stype):
    """Portal scholars for a programme, keyed by identity."""
    people = {}
    rows = Application.objects.filter(
        status='Approved', scholarship__type=stype
    ).values('student__student_id', 'student__user__last_name',
             'student__user__first_name', 'student__enrollment__course',
             'student__enrollment__gwa', 'form_data', 'scholarship__name')
    for row in rows:
        key = charts.identity(row['student__student_id'],
                              row['student__user__last_name'],
                              row['student__user__first_name'])
        declared = (row['form_data'] or {}).get('scholar_type') or ''
        people[key] = {
            'course': row['student__enrollment__course'],
            'gwa': row['student__enrollment__gwa'],
            'tier': (charts.tier_word(declared)
                     or charts.tier_word(row['scholarship__name'])),
        }
    return people


def _scholar_details(stype, label, window):
    """Every scholar in a programme for one term, keyed by identity."""
    people = {}
    if label == window.active_label:
        if stype in charts.ROSTER_TYPES:
            people = _roster_details(stype)
        else:
            people = _award_details(stype)
        rows = _imported(stype, label, unclaimed_only=True)
    else:
        rows = _imported(stype, label)

    for row in rows.values('student_id', 'last_name', 'first_name',
                           'course', 'gwa', 'award_tier'):
        key = charts.identity(row['student_id'], row['last_name'],
                              row['first_name'])
        people[key] = {'course': row['course'], 'gwa': row['gwa'],
                       'tier': charts.tier_word(row['award_tier'])}

    people.pop(None, None)
    if people:
        return people
    return charts.details_from_sheet(
        window.sheet_for(stype, label), stype, label)


def _people_across(stype, labels, window):
    """Merge one programme's scholars across several terms."""
    return charts.merge_people(
        _scholar_details(stype, label, window) for label in labels)


def _whole_year_figures(all_types, selected_type, window, include_gwa):
    """Counts, courses and GWA for a whole academic year.

    A year is not the sum of its semesters: the same scholar appears in
    both, so the figures are recounted over merged people rather than
    added up.
    """
    labels = window.term_labels
    counts = {stype: len(_people_across(stype, labels, window))
              for stype in all_types}

    wanted = [selected_type] if selected_type in all_types else all_types
    course_counts = {}
    for stype in wanted:
        for course, total in charts.count_courses(
                _people_across(stype, labels, window)).items():
            course_counts[course] = course_counts.get(course, 0) + total

    gpa_ranges = []
    if include_gwa:
        buckets = charts.banded(
            row.get('gwa') for row
            in _people_across('Academic', labels, window).values()
        ) or charts.empty_bands()
        gpa_ranges = [{'range': band, 'count': n} for band, n in buckets.items()]

    return counts, charts.course_distribution(course_counts), gpa_ranges


def _trend_counts(stype, label, window):
    """Scholars per series for one programme in one term."""
    rows = _scholar_details(stype, label, window)
    if rows:
        buckets = {}
        for row in rows.values():
            name = charts.series_name(stype, charts.subtype(stype, row))
            buckets[name] = buckets.get(name, 0) + 1
        return buckets
    record = window.sheet_for(stype, label)
    total = record.scholar_count if record else 0
    return {stype: total} if total else {}


def _trend(all_labels, trend_types, window):
    """The trend chart: one row per term, one series per programme split.

    Returns:
        ``(trend_data, trend_series)``.
    """
    from .models import SystemSettings

    trend_data = []
    for label in sorted(set(all_labels), key=charts.label_sort_key):
        parsed = SystemSettings.parse_label(label)
        counts = {}
        for stype in trend_types:
            for name, value in _trend_counts(stype, label, window).items():
                counts[name] = counts.get(name, 0) + value
        trend_data.append({
            'label': label,
            'sy': parsed['sy'],
            'display': f"{parsed['sy']} — {parsed['semester']}",
            'total': sum(counts.values()),
            'counts': counts,
            'per_type': {name: n for name, n in counts.items() if n},
        })

    charts.rename_unsplit_series(trend_data, trend_types)
    names = charts.series_for(trend_data, trend_types)
    if len(trend_types) == 1 and not names:
        names = list(trend_types)

    series = [
        {'type': name, 'counts': [entry['counts'].get(name, 0)
                                  for entry in trend_data]}
        for name in names
    ]
    return trend_data, series


def _build_analytics_context(request, all_types, include_gwa=True):
    """Assemble every figure the analytics dashboard shows.

    Each chart is built by a function of its own above; this one chooses the
    term, calls them in order and hands the page a dictionary. The whole-year
    view overrides three of the figures because a year is not the sum of its
    semesters.
    """
    from .models import SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    all_types = list(all_types)

    all_labels = _term_labels()
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    sy_groups, whole_year_terms, all_sy_display = _term_choices(
        all_labels, active_label)
    window = _selected_window(request, all_labels, whole_year_terms, active_label)

    selected_parsed = SystemSettings.parse_label(window.term_labels[0])
    selected_sy = selected_parsed['sy']
    selected_semester = (
        'Whole academic year' if window.whole_year
        else SystemSettings.parse_label(window.selected_label)['semester'])
    selected_type = request.GET.get('stype', '')
    one_programme = selected_type if selected_type in all_types else ''

    rollover_counts = {stype: _programme_total(stype, window)
                       for stype in all_types}

    course_counts = {}
    for stype in ([one_programme] if one_programme else all_types):
        for course, total in _course_counts(stype, window).items():
            course_counts[course] = course_counts.get(course, 0) + total
    course_dist = charts.course_distribution(course_counts)

    gpa_ranges = []
    if include_gwa:
        gpa_ranges = [{'range': band, 'count': n}
                      for band, n in _gwa_buckets(window).items()]

    if window.whole_year:
        rollover_counts, course_dist, year_gpa = _whole_year_figures(
            all_types, one_programme, window, include_gwa)
        if include_gwa:
            gpa_ranges = year_gpa

    trend_types = [one_programme] if one_programme else all_types
    trend_data, trend_series = _trend(all_labels, trend_types, window)
    trend_year_labels = [
        label for label in sorted(set(all_labels), key=charts.label_sort_key)
        if SystemSettings.parse_label(label)['sy'] == selected_sy
    ]

    show_gwa = (
        bool(gpa_ranges)
        and (not selected_type or selected_type == 'Academic')
        and any(entry['count'] for entry in gpa_ranges)
    )

    return {
        'rollover_counts': rollover_counts,
        'all_types': all_types,
        'course_dist': course_dist,
        'course_chart_height': charts.course_chart_height(course_dist),
        'trend_chart_height': charts.trend_chart_height(trend_series),
        'gpa_ranges': gpa_ranges,
        'show_program': (bool(course_dist) if selected_type
                         else any(rollover_counts.values())),
        'show_gwa': show_gwa,
        'show_trend': (len(trend_data) > 1
                       and any(any(s['counts']) for s in trend_series)),
        'all_sy_display': all_sy_display,
        'sy_groups': sy_groups,
        'whole_year': window.whole_year,
        'term_labels': window.term_labels,
        'selected_sy': window.selected_label,
        'selected_type': selected_type,
        'selected_sy_display': f'{selected_sy} — {selected_semester}',
        'active_sy': active_label,
        'trend_data': trend_data,
        'trend_series': trend_series,
        'trend_year_labels': trend_year_labels,
        'selected_academic_year': selected_sy,
        'selected_term_display': f'{selected_sy} {selected_semester}',
    }

def _analytics_data_version():
    """A stamp that changes whenever the underlying figures could have.

    Used as the cache key, so the dashboard is recomputed when the data
    moves and reused when it has not, without anyone remembering to clear
    anything.
    """
    from django.db.models import Count, Max

    from .models import ImportedScholar, ScholarListImport

    sheets = ScholarListImport.objects.aggregate(n=Count('id'), last=Max('created_at'))
    scholars = ImportedScholar.objects.aggregate(n=Count('id'))
    approved = Application.objects.filter(status='Approved').count()
    staff = ApplicantRecord.objects.filter(status='Approved').count()
    marker = sheets['last'].timestamp() if sheets['last'] else 0
    return f"{sheets['n']}:{marker}:{scholars['n']}:{approved}:{staff}"

def _analytics_context(request, all_types, include_gwa=True):
    """The dashboard context, cached against the data version.

    ``?fresh=1`` recomputes on demand, which is what the office's
    "recalculate" button sends.
    """
    import hashlib

    from django.conf import settings as django_settings
    from django.core.cache import cache
    from django.utils import timezone

    from .models import SystemSettings

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    seed = '|'.join((
        settings_obj.academic_year,
        request.GET.get('sy', ''),
        request.GET.get('stype', ''),
        str(int(bool(include_gwa))),
        str(len(all_types)),
        _analytics_data_version(),
    ))
    key = 'analytics:' + hashlib.sha1(seed.encode('utf-8')).hexdigest()

    fresh = request.GET.get('refresh') == '1'
    cached = None if fresh else cache.get(key)

    if cached is None:
        context = _build_analytics_context(request, all_types, include_gwa)
        context['analytics_generated'] = timezone.now()
        cache.set(key, context, django_settings.ANALYTICS_CACHE_SECONDS)
        context = dict(context)
        context['analytics_cached'] = False
    else:
        context = dict(cached)
        context['analytics_cached'] = True

    query = request.GET.copy()
    query['refresh'] = '1'
    context['analytics_refresh_url'] = '?' + query.urlencode()
    return context

@_vpsea_required
def vpsea_analytics(request):
    """The SDSO analytics dashboard."""
    _base = ['Academic', 'TDP', 'DOST', 'CHED', 'CoScho', 'Sports', 'Affirmative', 'Staff', 'GSIS']
    all_types = _base + [
        t for t in Scholarship.objects.values_list('type', flat=True).distinct()
        if t not in _base
    ]
    return render(request, 'vpsea/analytics.html', _analytics_context(request, all_types))
