"""Eligibility recommendation and ranking.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import render, redirect
from django.db.models import Q
from .models import STAFF_APPLICATION_DETAILS, STUDENT_DETAILS, StudentProfile
from django.http import HttpResponse
import logging
from .views_shared import _active_term, _vpsea_required

logger = logging.getLogger(__name__)


RANKING_TABS = [
    ('Affirmative', 'Affirmative Action'),
    ('TES', 'TES Recommendation'),
    ('Staff', 'Faculty and Staff Scholars'),
]

def _applicant_identity(application):
    """What makes two staff applications the same applicant.

    The applicant's own number first, because that is what the office reads
    down the list. ``staff_employee_id`` is deliberately not used: on a
    dependent's record it holds the *parent's* number, so two children of one
    employee would collapse into one row.

    Falling back to the name happens only where neither a number nor an
    address was recorded. Two strangers can share a name, and merging them
    would hide a real applicant — worse than showing a duplicate — so it is
    the last resort rather than the first test.
    """
    own_number = (application.student_id or '').strip().lower()
    if own_number:
        return ('number', own_number)
    email = (application.email or '').strip().lower()
    if email:
        return ('email', email)
    return ('name', ' '.join((application.full_name or '').lower().split()))


def _one_per_applicant(applications):
    """The newest application each applicant has on file.

    One person legitimately holds several records: every write path scopes
    itself to a term so a new semester files a new one, a refusal is left
    behind when they resubmit, and the archive form adds a roster record
    without checking whether they already applied. All of that is correct
    where it happens — but the ranking is a list of who to recommend, so the
    same person appearing twice is a list the office cannot count.

    ``submitted_at`` decides, matching ``_staff_application_for`` in
    ``views_staff``: the record they most recently stood behind is the one
    they are asking to be judged on.
    """
    newest = {}
    for application in sorted(applications,
                              key=lambda a: (a.submitted_at, a.pk),
                              reverse=True):
        newest.setdefault(_applicant_identity(application), application)
    return list(newest.values())


def _staff_ranking_data():
    """Rank the staff applications for the office's ranking page.

    Applications needing verification are ranked too but numbered
    separately, so an incomplete application stays visible instead of
    vanishing from the list the office works from.

    Scoped to the active term, because the list answers "who do we recommend
    now" and last semester's applications are not up for a decision. Records
    carrying no term at all are kept: ``ApplicantRecord`` only gained the term
    columns in 0049 and nothing backfilled them, so a blank is an unstamped
    old row rather than evidence it belongs elsewhere, and dropping it would
    quietly lose a scholar from the office's working list.
    """
    from . import staff_ranking
    from .models import ApplicantRecord

    term = _active_term()
    applications = (ApplicantRecord.objects
                    .filter(qualified_for='Staff')
                    .filter(Q(school_year=term['sy'], semester=term['semester'])
                            | Q(school_year=''))
                    .exclude(status='Rejected')
                    .select_related(*STAFF_APPLICATION_DETAILS))

    evaluations = staff_ranking.rank(_one_per_applicant(applications))

    decided = [e for e in evaluations if e.status != staff_ranking.FOR_VERIFICATION]
    needs_info = [e for e in evaluations if e.status == staff_ranking.FOR_VERIFICATION]
    position = 0
    for evaluation in decided:
        if evaluation.qualified:
            position += 1
            evaluation.rank = position
        else:
            evaluation.rank = None
    for evaluation in needs_info:
        evaluation.rank = None

    return {
        'rows': decided,
        'needs_info': needs_info,
        'total': len(evaluations),
        'counts': {
            'qualified': sum(1 for e in evaluations if e.status == staff_ranking.QUALIFIED),
            'verification': len(needs_info),
            'not_qualified': sum(1 for e in evaluations
                                 if e.status == staff_ranking.NOT_QUALIFIED),
            'employees': sum(1 for e in evaluations if e.standing == staff_ranking.STAFF),
            'dependents': sum(1 for e in evaluations if e.standing == staff_ranking.DEPENDENT),
        },
    }

def _vpsea_staff_ranking(request):
    """Render the staff tab of the ranking page."""
    data = _staff_ranking_data()
    return render(request, 'vpsea/ranking.html', {
        'active': 'ranking',
        'ranking_tabs': RANKING_TABS,
        'active_tab': 'Staff',
        'staff_rows': data['rows'],
        'staff_needs_info': data['needs_info'],
        'staff_total': data['total'],
        'staff_counts': data['counts'],
    })

@_vpsea_required
def vpsea_ranking_download(request):
    """Download the current ranking tab as a spreadsheet."""
    from . import ranking_report
    from .models import ActivityLog

    tab = request.GET.get('type', 'Affirmative')
    if tab not in dict(RANKING_TABS):
        tab = 'Affirmative'

    threshold = None
    if tab == 'TES':
        data = _tes_ranking_data()
    elif tab == 'Staff':
        data = _staff_ranking_data()
    else:
        try:
            threshold = float(request.GET.get('passing', 75.0))
        except (TypeError, ValueError):
            threshold = 75.0
        data = _affirmative_ranking_data(threshold)

    buf, filename = ranking_report.build(tab, data, passing_threshold=threshold)

    ActivityLog.record(
        request.user, f'Downloaded the {dict(RANKING_TABS)[tab]} recommendation list',
        verb='export', request=request)

    response = HttpResponse(
        buf.read(),
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def _affirmative_ranking_data(passing_threshold):
    """Rank Affirmative Action recommendations against a passing mark.

    The threshold is the office's to set, so eligibility is recomputed per
    request rather than stored: a stored verdict would silently belong to
    whatever threshold was in force when it was written.
    """
    from .affirmative_ranking import target_groups
    from .models import AffirmativeRecommendation

    recommendations = (
        AffirmativeRecommendation.objects
        .select_related('student__user', *STUDENT_DETAILS)
        .order_by('-fit_score', 'student__user__last_name')
    )

    rows = []
    for rec in recommendations:
        p = rec.student
        gpa_pass   = p.shs_gpa is not None and p.shs_gpa >= passing_threshold
        exam_pass  = p.suc_exam_percent is not None and p.suc_exam_percent >= 50.0
        not_tes    = not p.is_tes_beneficiary
        rows.append({
            'rank': None,
            'rec': rec,
            'profile': p,
            'gpa_pass': gpa_pass,
            'exam_pass': exam_pass,
            'not_tes': not_tes,
            'groups': target_groups(p),
            'eligible': gpa_pass and exam_pass and not_tes,
        })

    rows.sort(key=lambda r: (
        0 if r['eligible'] else 1,
        -r['groups'].count,
        -r['rec'].fit_score,
        (r['profile'].user.last_name or '').lower(),
    ))
    rank_counter = 1
    for row in rows:
        if row['eligible']:
            row['rank'] = rank_counter
            rank_counter += 1

    return {
        'rows': rows,
        'eligible_count': sum(1 for r in rows if r['eligible']),
        'ineligible_count': sum(1 for r in rows if not r['eligible']),
        'in_target_group_count': sum(1 for r in rows
                                     if r['eligible'] and r['groups'].count),
    }

def _tes_ranking_data():
    """Screen and rank students for TES.

    Only eligible students are numbered. The ineligible and the
    incompletely-recorded are still returned, with their reasons, because
    the office needs to see who was left out and why — a list that showed
    only the winners could not be checked.
    """
    from . import tes_ranking

    profiles = StudentProfile.objects.filter(
        user__verification_status='approved',
    ).select_related('user', *StudentProfile.DETAIL_RELATIONS)

    complete, incomplete = tes_ranking.screen(profiles)
    evaluations = tes_ranking.rank(complete)

    position = 0
    for evaluation in evaluations:
        if evaluation.eligible:
            position += 1
            evaluation.rank = position
        else:
            evaluation.rank = None

    return {
        'rows': evaluations,
        'total': len(evaluations),
        'excluded': len(incomplete),
        'counts': {
            'eligible': sum(1 for e in evaluations if e.status == tes_ranking.ELIGIBLE),
            'excluded': len(incomplete),
            'not_eligible': sum(1 for e in evaluations if e.status == tes_ranking.NOT_ELIGIBLE),
            'priority_1': sum(1 for e in evaluations if e.priority == tes_ranking.PRIORITY_1),
            'priority_2': sum(1 for e in evaluations if e.priority == tes_ranking.PRIORITY_2),
        },
    }

def _vpsea_tes_ranking(request):
    """Render the TES tab of the ranking page."""
    data = _tes_ranking_data()
    return render(request, 'vpsea/ranking.html', {
        'active': 'ranking',
        'ranking_tabs': RANKING_TABS,
        'active_tab': 'TES',
        'tes_rows': data['rows'],
        'tes_excluded': data['excluded'],
        'tes_student_total': data['total'],
        'tes_counts': data['counts'],
    })

@_vpsea_required
def vpsea_ranking(request):
    """The eligibility ranking page, one tab per programme."""
    from .models import AffirmativeRecommendation

    scholarship_type = request.GET.get('type', 'Affirmative')
    if scholarship_type == 'TES':
        return _vpsea_tes_ranking(request)
    if scholarship_type == 'Staff':
        return _vpsea_staff_ranking(request)
    scholarship_type = 'Affirmative'

    try:
        passing_threshold = float(request.GET.get('passing', 75.0))
    except (TypeError, ValueError):
        passing_threshold = 75.0

    if request.method == 'POST':
        if request.POST.get('action') == 'resync':
            AffirmativeRecommendation.evaluate_and_sync(passing_threshold)
        return redirect(f'/vpsea/ranking/?type={scholarship_type}&passing={passing_threshold}')

    AffirmativeRecommendation.evaluate_and_sync(passing_threshold)

    data = _affirmative_ranking_data(passing_threshold)
    return render(request, 'vpsea/ranking.html', {
        'ranking_tabs': RANKING_TABS,
        'active_tab': 'Affirmative',
        'rec_rows': data['rows'],
        'passing_threshold': passing_threshold,
        'eligible_count': data['eligible_count'],
        'ineligible_count': data['ineligible_count'],
        'in_target_group_count': data['in_target_group_count'],
    })
