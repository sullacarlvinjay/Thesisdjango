"""The SDSO analytics dashboard.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render
from .models import Scholarship, Application, ApplicantRecord
import logging
from .views_shared import _vpsea_required
from .views_archives import _rollover_workbook

logger = logging.getLogger(__name__)


def _build_analytics_context(request, all_types, include_gwa=True):
    """Assemble every figure the analytics dashboard shows.

    The highest-complexity block in the codebase, and the honest reason is
    that its inputs are not uniform: the active term's numbers come from
    the database, while a past term's come from the spreadsheet that was
    filed when it closed. Each programme also counts differently — CHED
    splits by tier, Academic by scholar classification.

    Decomposing it is the first refactor worth doing here; see
    ``docs/TESTING.md`` on path coverage.
    """
    from .models import ScholarListImport, SystemSettings
    from collections import defaultdict

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    active_label = settings_obj.academic_year
    ALL_TYPES = list(all_types)

    from .models import ImportedScholar

    def _imported_current(stype):
        """Imported scholars for a programme in the active term, unclaimed."""
        return ImportedScholar.objects.filter(
            scholarship_type=stype, term_label=active_label, claimed_by__isnull=True,
        )

    all_labels = list(
        ScholarListImport.objects.values_list('term_label', flat=True)
        .distinct().order_by('-term_label')
    )
    ar_labels = list(
        ImportedScholar.objects.exclude(term_label='')
        .values_list('term_label', flat=True).order_by().distinct()
    )
    for lbl in ar_labels:
        if lbl not in all_labels:
            all_labels.append(lbl)
    all_labels = sorted(set(all_labels), reverse=True)
    if active_label not in all_labels:
        all_labels.insert(0, active_label)
    all_sy_display = [(lbl, f"{SystemSettings.parse_label(lbl)['sy']} — {SystemSettings.parse_label(lbl)['semester']}") for lbl in all_labels]

    terms_by_year = {}
    for lbl in all_labels:
        terms_by_year.setdefault(
            SystemSettings.parse_label(lbl)['sy'], []).append(lbl)

    whole_year_terms = {}
    for labels in terms_by_year.values():
        if len(set(labels)) > 1:
            whole_year_terms[f"{sorted(labels)[0].split('-')[0]}-Y"] = sorted(set(labels))

    sy_groups = []
    for sy in sorted(terms_by_year, reverse=True):
        labels = sorted(set(terms_by_year[sy]))
        options = []
        year_key = f"{labels[0].split('-')[0]}-Y"
        if year_key in whole_year_terms:
            options.append((year_key, 'Whole academic year'))
        options += [(lbl, SystemSettings.parse_label(lbl)['semester'])
                    for lbl in labels]
        sy_groups.append({'sy': sy, 'options': options})

    selectable = set(all_labels) | set(whole_year_terms)
    selected_label = request.GET.get('sy', active_label)
    if selected_label not in selectable:
        selected_label = active_label

    whole_year = selected_label in whole_year_terms
    term_labels = whole_year_terms.get(selected_label, [selected_label])

    selected_parsed = SystemSettings.parse_label(term_labels[0])
    selected_sy = selected_parsed['sy']
    selected_semester = ('Whole academic year' if whole_year
                         else SystemSettings.parse_label(selected_label)['semester'])
    selected_type = request.GET.get('stype', '')

    def _sheet_for(stype):
        """The filed spreadsheet for a programme in the selected term."""
        return ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=selected_label).first()

    rollover_counts = {}
    for t in ALL_TYPES:
        if selected_label == active_label:
            if t in ('Affirmative', 'Staff'):
                from .models import ApplicantRecord
                counted = ApplicantRecord.objects.filter(
                    status='Approved', qualified_for=t
                ).count()
            else:
                counted = Application.objects.filter(
                    status='Approved', scholarship__type=t
                ).count()
            counted += _imported_current(t).count()
        else:
            counted = ImportedScholar.objects.filter(
                scholarship_type=t, term_label=selected_label).count()

        if not counted:
            record = _sheet_for(t)
            counted = record.scholar_count if record else 0
        rollover_counts[t] = counted

    def _course_counts_from_sheet(stype):
        """Scholars per course, read out of a filed spreadsheet.

        Used for past terms, whose figures live in the file rather than in the
        database. The course column is found by heading rather than position,
        because the layout differs between funders.
        """
        r = _sheet_for(stype)
        if not r or not r.excel_file:
            return {}
        try:
            ws = _rollover_workbook(r.excel_file).active
            course_col = next((cell.column - 1 for cell in ws[1] if cell.value and 'course' in str(cell.value).lower()), None)
            if course_col is None:
                return {}
            counts = defaultdict(int)
            for row in ws.iter_rows(min_row=2, values_only=True):
                if row and row[0] is not None and course_col < len(row) and row[course_col]:
                    counts[str(row[course_col]).strip()] += 1
            return dict(counts)
        except Exception:
            logger.exception('analytics: could not read rollover sheet for %s %s',
                             stype, selected_label)
            return {}

    def _course_counts_from_rollover(stype):
        """Scholars per course for the active term, from the database."""
        counts = {}
        if selected_label == active_label:
            from django.db.models import Count as DCount
            if stype in ('Affirmative', 'Staff'):
                from .models import ApplicantRecord
                qs = ApplicantRecord.objects.filter(
                    status='Approved', qualified_for=stype
                ).values('enrollment__course').annotate(n=DCount('id'))
                for r in qs:
                    key = r['enrollment__course'] or 'Unknown'
                    counts[key] = counts.get(key, 0) + r['n']
            else:
                qs = Application.objects.filter(
                    status='Approved', scholarship__type=stype
                ).values('student__enrollment__course').annotate(n=DCount('id'))
                for r in qs:
                    key = r['student__enrollment__course'] or 'Unknown'
                    counts[key] = counts.get(key, 0) + r['n']
            for r in _imported_current(stype).values('course').annotate(n=DCount('id')):
                key = r['course'] or 'Unknown'
                counts[key] = counts.get(key, 0) + r['n']
        else:
            for rec in ImportedScholar.objects.filter(
                scholarship_type=stype, term_label=selected_label
            ).values('course'):
                c = rec['course'] or 'Unknown'
                counts[c] = counts.get(c, 0) + 1

        return counts or _course_counts_from_sheet(stype)

    if selected_type and selected_type in ALL_TYPES:
        raw = _course_counts_from_rollover(selected_type)
    else:
        raw = defaultdict(int)
        for t in ALL_TYPES:
            for k, v in _course_counts_from_rollover(t).items():
                raw[k] += v
    course_dist = [{'course': k, 'scholars': v} for k, v in sorted(raw.items(), key=lambda x: -x[1])]

    GWA_BANDS = ['1.00-1.25', '1.26-1.50', '1.51-1.75', '1.76-2.00', '2.01-2.50']

    def _band(value):
        """The GWA band a mark falls in, or ``None``.

        Lower is better on this scale, so the bands read as ceilings. Anything
        below 1.0 is not a real GWA and is excluded rather than banded.
        """
        try:
            g = float(value or 0)
        except (ValueError, TypeError):
            return None
        if g < 1.0:
            return None
        for band, ceiling in zip(GWA_BANDS, (1.25, 1.50, 1.75, 2.00, 2.50),
                             strict=True):
            if g <= ceiling:
                return band
        return None

    def _banded(values):
        """Count marks into GWA bands.

        Returns ``None`` when nothing landed in any band, so the page can omit
        the chart rather than draw an axis over no data.
        """
        buckets = {band: 0 for band in GWA_BANDS}
        found = False
        for value in values:
            band = _band(value)
            if band:
                buckets[band] += 1
                found = True
        return buckets if found else None

    def _gwa_from_sheet():
        """GWA values read out of a filed Academic spreadsheet."""
        record = _sheet_for('Academic')
        if not record or not record.excel_file:
            return None
        try:
            ws = _rollover_workbook(record.excel_file).active
            gwa_col = next((cell.column - 1 for cell in ws[1]
                            if cell.value and 'gwa' in str(cell.value).lower()), None)
            if gwa_col is None:
                return None
            return _banded(
                row[gwa_col] for row in ws.iter_rows(min_row=2, values_only=True)
                if row and row[0] is not None and gwa_col < len(row)
            )
        except Exception:
            logger.exception('analytics: could not read Academic rollover '
                             'sheet for %s', selected_label)
            return None

    if not include_gwa:
        gpa_ranges = []
    else:
        if selected_label == active_label:
            buckets = _banded(
                [p['student__enrollment__gwa'] for p in Application.objects.filter(
                    status='Approved', scholarship__type='Academic'
                ).values('student__enrollment__gwa')]
                + [r['gwa'] for r in _imported_current('Academic').values('gwa')]
            )
        else:
            buckets = _banded(
                r['gwa'] for r in ImportedScholar.objects.filter(
                    scholarship_type='Academic', term_label=selected_label
                ).values('gwa')
            )
        buckets = buckets or _gwa_from_sheet() or {band: 0 for band in GWA_BANDS}
        gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]

    def _identity(student_id, last, first):
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

    def _details_from_sheet(stype, label):
        """One scholar per row, read out of a filed spreadsheet."""
        record = ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=label).first()
        if not record or not record.excel_file:
            return {}
        try:
            ws = _rollover_workbook(record.excel_file).active

            def column(*wanted):
                """The index of the first heading containing any of these words."""
                for cell in ws[1]:
                    heading = str(cell.value or '').strip().lower()
                    if heading and any(w in heading for w in wanted):
                        return cell.column - 1
                return None

            last_col = column('last name')
            first_col = column('first name')
            id_col = column('student number', 'student id', 'student no')
            course_col = column('course')
            gwa_col = column('gwa')
            tier_col = column('award tier', 'scholar type', 'tier')
            if last_col is None and id_col is None:
                return {}

            def cell(row, index):
                """One cell as trimmed text, tolerating short rows."""
                if index is None or index >= len(row):
                    return ''
                return str(row[index]).strip() if row[index] is not None else ''

            people = {}
            for row in ws.iter_rows(min_row=2, values_only=True):
                if not row or row[0] is None:
                    continue
                key = _identity(cell(row, id_col), cell(row, last_col),
                                cell(row, first_col))
                if key:
                    people[key] = {'course': cell(row, course_col),
                                   'gwa': cell(row, gwa_col),
                                   'tier': _tier_word(cell(row, tier_col))}
            return people
        except Exception:
            logger.exception('analytics: could not read rollover sheet for %s %s',
                             stype, label)
            return {}

    def _tier_word(text):
        """Full or Half from however a sheet spelled the CHED tier."""
        lowered = str(text or '').lower()
        if 'full' in lowered:
            return 'Full'
        if 'half' in lowered or 'partial' in lowered:
            return 'Half'
        return ''

    def _scholar_details(stype, label):
        """Every scholar in a programme for one term, keyed by identity."""
        people = {}

        if label == active_label:
            if stype in ('Affirmative', 'Staff'):
                from .models import ApplicantRecord
                for r in ApplicantRecord.objects.filter(
                    status='Approved', qualified_for=stype
                ).values('enrollment__student_id', 'full_name',
                         'enrollment__course'):
                    parts = (r['full_name'] or '').split()
                    key = _identity(r['enrollment__student_id'],
                                    parts[-1] if parts else '',
                                    parts[0] if len(parts) > 1 else '')
                    people[key] = {'course': r['enrollment__course'],
                                   'gwa': None, 'tier': ''}
            else:
                for r in Application.objects.filter(
                    status='Approved', scholarship__type=stype
                ).values('student__student_id', 'student__user__last_name',
                         'student__user__first_name',
                         'student__enrollment__course',
                         'student__enrollment__gwa',
                         'form_data', 'scholarship__name'):
                    key = _identity(r['student__student_id'],
                                    r['student__user__last_name'],
                                    r['student__user__first_name'])
                    declared = (r['form_data'] or {}).get('scholar_type') or ''
                    people[key] = {'course': r['student__enrollment__course'],
                                   'gwa': r['student__enrollment__gwa'],
                                   'tier': _tier_word(declared)
                                           or _tier_word(r['scholarship__name'])}
            rows = _imported_current(stype)
        else:
            rows = ImportedScholar.objects.filter(
                scholarship_type=stype, term_label=label)

        for r in rows.values('student_id', 'last_name', 'first_name',
                             'course', 'gwa', 'award_tier'):
            key = _identity(r['student_id'], r['last_name'], r['first_name'])
            people[key] = {'course': r['course'], 'gwa': r['gwa'],
                           'tier': _tier_word(r['award_tier'])}

        people.pop(None, None)
        return people or _details_from_sheet(stype, label)

    def _people_across(stype, labels):
        """Merge scholars across several terms, keyed by identity.

        A later term wins unless it carries less detail, so a scholar recorded
        fully in one term is not replaced by a sparser row from another.
        """
        merged = {}
        for label in labels:
            for key, row in _scholar_details(stype, label).items():
                if key in merged and not (row.get('course') or row.get('gwa')):
                    continue
                merged[key] = row
        return merged

    if whole_year:
        rollover_counts = {t: len(_people_across(t, term_labels))
                           for t in ALL_TYPES}

        if selected_type and selected_type in ALL_TYPES:
            year_people_by_type = {selected_type: _people_across(selected_type, term_labels)}
        else:
            year_people_by_type = {t: _people_across(t, term_labels) for t in ALL_TYPES}

        raw = defaultdict(int)
        for rows in year_people_by_type.values():
            for row in rows.values():
                raw[str(row.get('course') or 'Unknown').strip() or 'Unknown'] += 1
        course_dist = [{'course': k, 'scholars': v}
                       for k, v in sorted(raw.items(), key=lambda x: -x[1])]

        if include_gwa:
            buckets = _banded(row.get('gwa') for row
                              in _people_across('Academic', term_labels).values())
            buckets = buckets or {band: 0 for band in GWA_BANDS}
            gpa_ranges = [{'range': k, 'count': v} for k, v in buckets.items()]

    def _label_sort_key(lbl):
        """Sort key for a term label; unparseable sorts first."""
        try:
            yy, s = lbl.split('-')
            return int(yy) * 10 + int(s)
        except Exception:
            return 0

    every_label = sorted(set(all_labels), key=_label_sort_key)
    trend_year_labels = [lbl for lbl in every_label
                         if SystemSettings.parse_label(lbl)['sy'] == selected_sy]
    trend_labels_sorted = every_label

    def _as_number(value):
        """A float from anything, or 0.0."""
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    def _subtype(stype, row):
        """The series a scholar belongs to within their programme.

        Academic splits by scholar classification and CHED by tier, because a
        single line for either would hide the split the office reports on.
        """
        if stype == 'Academic':
            from .constants import academic_classification
            label = academic_classification(_as_number(row.get('gwa')))
            return label if label in ('University Scholar', 'College Scholar') else ''
        if stype == 'CHED':
            return {'Full': 'Full Merit', 'Half': 'Half Merit'}.get(
                (row.get('tier') or '').strip(), '')
        return ''

    def _series_name(stype, sub):
        """The chart series label for a programme and subtype."""
        return f'{stype} — {sub}' if sub else stype

    def _trend_counts(stype, label):
        """Scholars per programme per term, for the trend chart."""
        rows = _scholar_details(stype, label)
        if rows:
            buckets = {}
            for row in rows.values():
                name = _series_name(stype, _subtype(stype, row))
                buckets[name] = buckets.get(name, 0) + 1
            return buckets
        record = ScholarListImport.objects.filter(
            scholarship_type=stype, term_label=label).first()
        total = record.scholar_count if record else 0
        return {stype: total} if total else {}

    if selected_type and selected_type in ALL_TYPES:
        trend_types = [selected_type]
    else:
        trend_types = ALL_TYPES

    trend_data = []
    for lbl in trend_labels_sorted:
        parsed = SystemSettings.parse_label(lbl)
        counts = {}
        for t in trend_types:
            for name, value in _trend_counts(t, lbl).items():
                counts[name] = counts.get(name, 0) + value
        trend_data.append({
            'label': lbl,
            'sy': parsed['sy'],
            'display': f"{parsed['sy']} — {parsed['semester']}",
            'total': sum(counts.values()),
            'counts': counts,
            'per_type': {t: c for t, c in counts.items() if c},
        })

    for stype in trend_types:
        split = {name for d in trend_data for name in d['counts']
                 if name.startswith(f'{stype} — ')}
        if not split:
            continue
        renamed = f'{stype} — Level not recorded'
        for entry in trend_data:
            if stype in entry['counts']:
                entry['counts'][renamed] = entry['counts'].pop(stype)
                entry['per_type'] = {k: v for k, v in entry['counts'].items() if v}

    series_names = []
    for t in trend_types:
        for name in sorted({name for d in trend_data for name in d['counts']
                            if name == t or name.startswith(f'{t} — ')}):
            if name not in series_names and any(d['counts'].get(name)
                                                for d in trend_data):
                series_names.append(name)

    if selected_type and selected_type in ALL_TYPES and not series_names:
        series_names = [selected_type]

    trend_series = [
        {'type': name, 'counts': [d['counts'].get(name, 0) for d in trend_data]}
        for name in series_names
    ]
    course_chart_height = max(420, 150 + len(course_dist) * 34)
    trend_chart_height = max(420, 250 + len(trend_series) * 26)

    show_program = bool(course_dist) if selected_type else any(rollover_counts.values())
    show_gwa = (
        bool(gpa_ranges)
        and (not selected_type or selected_type == 'Academic')
        and any(g['count'] for g in gpa_ranges)
    )
    show_trend = len(trend_data) > 1 and any(any(s['counts']) for s in trend_series)

    return {
        'rollover_counts': rollover_counts,
        'all_types': ALL_TYPES,
        'course_dist': course_dist,
        'course_chart_height': course_chart_height,
        'trend_chart_height': trend_chart_height,
        'gpa_ranges': gpa_ranges,
        'show_program': show_program,
        'show_gwa': show_gwa,
        'show_trend': show_trend,
        'all_sy_display': all_sy_display,
        'sy_groups': sy_groups,
        'whole_year': whole_year,
        'term_labels': term_labels,
        'selected_sy': selected_label,
        'selected_type': selected_type,
        'selected_sy_display': f"{selected_sy} — {selected_semester}",
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
