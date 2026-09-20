"""Helpers shared by more than one portal.

Split out of the former ``student_views`` module, which had grown to hold
every portal at once. ``student_views`` now re-exports these names so
existing imports keep working.
"""

from django.shortcuts import redirect
from . import ratelimit, scholar_columns
from .models import Scholarship, Application, ScholarshipLinkRequest
import logging

logger = logging.getLogger(__name__)

IMPORT_FAILED = ('That spreadsheet could not be filed. Nothing was saved — check the '
                 'file and try again, or ask IT to read the server log.')

DUPLICATE_AWARD_NUMBERS = ('That spreadsheet records the same award number twice for '
                           'this programme and term. Nothing was saved — an award '
                           'number identifies one award, so the duplicate has to be '
                           'settled before the list can be filed.')

IMPORT_ABANDONED = ('That import was interrupted before it finished — the server '
                    'restarted while it was reading. Nothing was saved. Upload '
                    'the same file again.')


def _declaration_slots(post=None):
    """The repeated declaration cards on the registration form."""
    post = post or {}
    slots = []
    for number, suffix in enumerate(DECLARATION_SLOTS, start=1):
        tail = '' if not suffix else str(number)
        slots.append({
            'n': number,
            'suffix': suffix,
            'extra': bool(suffix),
            'card_id': f'scholarshipData{tail}',
            'tier_id': f'chedTier{tail}',
            'type_id': f'scholarshipType{tail}',
            'open': bool(post.get(f'has_scholarship{suffix}')),
            'type': post.get(f'scholarship_type{suffix}', ''),
            'tier': post.get(f'award_tier{suffix}', ''),
            'award_number': post.get(f'award_number{suffix}', ''),
            'notes': post.get(f'notes{suffix}', ''),
            'staff_name': post.get(f'staff_name{suffix}', ''),
            'staff_employee_id': post.get(f'staff_employee_id{suffix}', ''),
            'relationship_to_staff': post.get(f'relationship_to_staff{suffix}', ''),
        })
    return slots

DECLARATION_SLOTS = ('', '_2', '_3')


DEFAULT_PAGE_SIZE = 25


def paginate(request, rows, per_page=DEFAULT_PAGE_SIZE, param='page'):
    """One page of ``rows``, plus what a template needs to offer the rest.

    Long office tables used to be materialised whole — every pending account,
    every scholar — and several of them then issued further queries per row.
    That is survivable at the few dozen records a demo holds and is not at the
    thousands a few years of intake produces.

    ``param`` is named so that two independent tables can page on one screen
    without moving each other.

    Args:
        request: the current request; its query string is preserved.
        rows: a queryset, or any sliceable sequence.
        per_page: rows per page.
        param: the query parameter carrying the page number.

    Returns:
        A mapping to merge into the template context:

        ``rows``
            The page's rows.
        ``page``
            Django's ``Page``, for the count and the navigation links.
        ``page_param``
            The parameter name, so the template builds the right links.
        ``querystring``
            Every *other* query parameter, already encoded, so paging keeps
            the caller's search, tab and filters instead of silently
            resetting them.
    """
    from django.core.paginator import Paginator

    paginator = Paginator(rows, per_page)
    try:
        number = int(request.GET.get(param, 1))
    except (TypeError, ValueError):
        number = 1
    page = paginator.get_page(number)

    others = request.GET.copy()
    others.pop(param, None)
    return {
        'rows': list(page.object_list),
        'page': page,
        'page_param': param,
        'querystring': others.urlencode(),
    }


def _declared_scholarship(p, files, slot=''):
    """Validate one declared award from the registration form.

    Returns:
        ``(declaration, errors)``. ``(None, [])`` when the card was left
        unticked — not every applicant declares anything.
    """
    from .constants import declarable_type_values
    from .models import CHED_TIER_CHOICES, SystemSettings
    if f'has_scholarship{slot}' not in p:
        return None, []

    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    stype = p.get(f'scholarship_type{slot}', '')
    tier = p.get(f'award_tier{slot}', '') if stype == 'CHED' else ''
    proof = files.get(f'proof_document{slot}')
    where = f' (scholarship {DECLARATION_SLOTS.index(slot) + 1})' if slot else ''

    from .constants import (DEPENDENT_DECLARABLE_TYPE,
                            RELATIONSHIP_TO_STAFF_CHOICES)

    staff_name = p.get(f'staff_name{slot}', '').strip()
    staff_employee_id = p.get(f'staff_employee_id{slot}', '').strip()
    relationship = p.get(f'relationship_to_staff{slot}', '').strip()

    errors = []
    if stype not in declarable_type_values():
        errors.append(f'Say which scholarship you already hold{where}, or clear the '
                      '"I already hold a scholarship" box.')
    elif stype == 'CHED' and tier not in [t for t, _ in CHED_TIER_CHOICES]:
        errors.append(f'Please choose whether your CHED award{where} is Full Merit / '
                      'Full Scholar or Half Merit / Partial Scholar — your award '
                      'letter says which.')
    elif stype == DEPENDENT_DECLARABLE_TYPE:
        if not staff_name:
            errors.append('Name the BiPSU employee you depend on'
                          f'{where} — the Staff Scholarship is held through them.')
        if not staff_employee_id:
            errors.append(f"Give that employee's number{where}. The office checks "
                          'the appointment against it.')
        if relationship not in [r for r, _ in RELATIONSHIP_TO_STAFF_CHOICES]:
            errors.append('Say how you are related to that employee'
                          f'{where} — son, daughter, spouse or legal ward.')
    errors += [f'{problem}{where}' if where else problem
               for problem in _validate_proof(proof, settings_obj)]
    if errors:
        return None, errors

    if stype != DEPENDENT_DECLARABLE_TYPE:
        staff_name = staff_employee_id = relationship = ''

    return dict(
        scholarship_type=stype,
        proof_document=proof,
        award_number=p.get(f'award_number{slot}', '').strip(),
        award_tier=tier,
        notes=p.get(f'notes{slot}', ''),
        term_label=settings_obj.academic_year,
        staff_name=staff_name,
        staff_employee_id=staff_employee_id,
        relationship_to_staff=relationship,
    ), []

def _declared_scholarships(p, files):
    """Validate every declared award on the form.

    A type declared twice is reported rather than stored twice: two cards
    naming the same programme are a mistake, not two awards.
    """
    declarations, errors, seen = [], [], set()
    for slot in DECLARATION_SLOTS:
        declared, problems = _declared_scholarship(p, files, slot)
        errors.extend(problems)
        if not declared:
            continue
        if declared['scholarship_type'] in seen:
            from .constants import scholarship_type_labels
            label = scholarship_type_labels().get(
                declared['scholarship_type'], declared['scholarship_type'])
            errors.append(f'You named the {label} twice. Declare each scholarship '
                          'once — the office verifies them one at a time.')
            continue
        seen.add(declared['scholarship_type'])
        declarations.append(declared)
    return declarations, errors

def _unanswered(posted, questions):
    """Which of these required questions the form left blank."""
    return [f'{label} is required.' for name, label in questions
            if not (posted.get(name) or '').strip()]

def _tristate(raw, current):
    """Read a yes/no/unanswered field from a form.

    Three states, not two. An unanswered question must not read as "no" —
    the recommender treats the two completely differently.
    """
    value = (raw or '').strip().casefold()
    if value == 'yes':
        return True
    if value == 'no':
        return False
    if value == 'unknown':
        return None
    return current

def _positive_int(raw, current):
    """A positive integer from a posted field, or the current value."""
    text = (raw or '').strip()
    if text == '':
        return None
    if text.isdigit() and int(text) > 0:
        return int(text)
    return current

def _disability_answer(posted):
    """Read the disability question, which has its own "no" option.

    Returns:
        ``(value, problem)``. Choosing "Other" without naming the
        disability is the one error: every other answer, including
        declining, is valid.
    """
    from . import disability_list
    value = (posted.get('disability_type') or '').strip()
    if value != disability_list.OTHER:
        return value, ''
    typed = (posted.get('disability_type_other') or '').strip()
    if not typed:
        return '', 'Name the disability you chose "Other" for.'
    return typed, ''

def _disability_fields(posted_value, posted_other, saved):
    """Template context for the disability question and its "other" box."""
    from . import disability_list
    options = disability_list.disability_types()
    if posted_value is not None:
        value, other = posted_value, posted_other
    else:
        saved = (saved or '').strip()
        custom = saved if saved and saved not in options else ''
        value, other = (disability_list.OTHER if custom else saved), custom
    return {
        'disabilities': options,
        'other_option': disability_list.OTHER,
        'disability_value': value,
        'disability_other': other,
    }

def held_scholarship_types(profile):
    """Scholarship types this student already holds.

    Counts both approved applications and approved declarations, because
    an award granted elsewhere exists here only as a declaration and still
    bars a second one.
    """
    if not profile:
        return set()
    held = set(
        Application.objects.filter(student=profile, status='Approved')
        .values_list('scholarship__type', flat=True))
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    held |= set(
        ScholarshipLinkRequest.objects.filter(
            student=profile, status='Approved', term_label=settings_obj.academic_year,
        ).values_list('scholarship_type', flat=True))
    return {t for t in held if t}

def can_hold_alongside(held, wanted):
    """Whether a student holding these may also take ``wanted``.

    Some programmes are explicitly holdable alongside anything — Free
    Higher Education is the usual case — and those neither block nor are
    blocked.
    """
    from .constants import ALWAYS_HOLDABLE_TYPES

    if wanted in ALWAYS_HOLDABLE_TYPES:
        return True
    return not ({t for t in held if t} - ALWAYS_HOLDABLE_TYPES)

def application_window_reason(stype):
    """Why applications for this programme are closed, or ''.

    Empty means open. An unknown programme is also empty rather than
    closed: refusing an application because the catalogue is incomplete
    would be the wrong answer to the wrong question.
    """
    from django.utils import timezone
    programme = Scholarship.objects.filter(type=stype).first()
    if not programme:
        return ''
    return programme.window_closed_reason(timezone.localdate())

def renewal_window_reason(stype):
    """Why renewals are closed for this programme, or ''."""
    from django.utils import timezone
    programme = Scholarship.objects.filter(type=stype).first()
    if not programme:
        return ''
    return programme.renewal_closed_reason(timezone.localdate())

def _validate_proof(uploaded, settings_obj):
    """Check an uploaded proof document's type and size.

    The ceiling comes from ``SystemSettings`` so the office can change it
    without a redeploy.
    """
    if not uploaded:
        return ['Proof document is required.']
    import os
    errors = []
    ext = os.path.splitext(uploaded.name)[1].lower()
    if ext not in ('.pdf', '.jpg', '.jpeg', '.png'):
        errors.append(f'Unsupported file type "{ext or uploaded.name}". Upload a PDF, JPG or PNG.')
    max_mb = settings_obj.max_file_size_mb or 5
    if uploaded.size > max_mb * 1024 * 1024:
        errors.append(f'File is too large ({uploaded.size / 1048576:.1f} MB). Maximum is {max_mb} MB.')
    return errors

def declarable_types(profile=None):
    """Scholarship types this student may still declare.

    Narrowed by what they already hold, so the form does not offer an
    award the rules would refuse a moment later.
    """
    from .constants import live_declarable_types, scholarship_type_labels
    held = held_scholarship_types(profile) if profile else set()
    labels = scholarship_type_labels()
    return [(value, labels.get(value, value))
            for value in live_declarable_types()
            if can_hold_alongside(held, value)]

def _change_own_password(request, user):
    """Change the signed-in user's own password.

    Returns a list of problems, empty on success. Throttled, and the
    session is re-keyed on success so the user is not signed out by their
    own change.
    """
    from django.contrib.auth import update_session_auth_hash
    from django.contrib.auth.password_validation import validate_password
    from django.core.exceptions import ValidationError
    from .models import ActivityLog

    current = request.POST.get('current_password') or ''
    new = request.POST.get('new_password') or ''
    confirm = request.POST.get('new_password_confirm') or ''

    if not (current or new or confirm):
        return []

    wait = ratelimit.retry_after(ratelimit.PASSWORD_CHANGE, request, user.email)
    if wait is not None:
        return [ratelimit.wait_message(wait, 'password attempts')]

    errors = []
    if not user.check_password(current):
        ratelimit.register_failure(ratelimit.PASSWORD_CHANGE, request,
                                   user.email)
        errors.append('Your current password is not right. '
                      'Passwords are case-sensitive.')
    if not new:
        errors.append('Enter the new password you want.')
    elif new != confirm:
        errors.append('The two new passwords do not match.')
    else:
        try:
            validate_password(new, user)
        except ValidationError as bad:
            errors.extend(bad.messages)
    if errors:
        return errors

    user.set_password(new)
    user.save(update_fields=['password'])
    update_session_auth_hash(request, user)
    ratelimit.clear(ratelimit.PASSWORD_CHANGE, request, user.email)
    ActivityLog.record(
        user, 'Changed their own password',
        verb='update', request=request)
    return []

MFA_SETUP_PATH = '/vpsea/profile/'

DECISION_VERBS = {'Approved': 'approve', 'Rejected': 'reject'}


def record_decision(request, row, status, remarks, what):
    """Stamp an office verdict onto ``row`` and audit who reached it.

    Every office decision goes through here so that none of them can record
    the outcome without recording the officer. That mattered little while the
    office was one person and a single login; it decides whether the audit
    trail means anything once the office has more than one account, which is
    the whole reason a second one can be created.

    The row is saved, so the caller does not save it again.
    """
    from django.utils import timezone

    from .models import ActivityLog

    before = ActivityLog.snapshot(row, ['status', 'remarks'])
    row.status = status
    row.remarks = remarks
    row.reviewed_by = request.user
    row.reviewed_at = timezone.now()
    row.save()
    ActivityLog.record(
        request.user, f'{status} {what}',
        verb=DECISION_VERBS.get(status, 'update'),
        target=row,
        changes=ActivityLog.diff(
            before, ActivityLog.snapshot(row, ['status', 'remarks']),
            ['status', 'remarks']),
        request=request)
    return row


def _vpsea_required(view_fn):
    """Restrict a view to SDSO office accounts.

    Where MFA is enforced, an office account that has not enrolled is sent to
    its own profile to do so. It is not signed out: these accounts read
    Listahanan status, disability and household income, and locking the
    office out of its own records is not a privacy improvement.
    """
    from functools import wraps

    @wraps(view_fn)
    def wrapper(request, *args, **kwargs):
        """Redirect anyone who is not an enrolled office account."""
        from django.conf import settings

        if not request.user.is_authenticated or request.user.role != 'vpsea':
            return redirect('/login/')
        if (getattr(settings, 'MFA_ENFORCED', False)
                and request.user.mfa_outstanding
                and request.path != MFA_SETUP_PATH):
            return redirect(f'{MFA_SETUP_PATH}?mfa=required')
        return view_fn(request, *args, **kwargs)
    return wrapper

def _safe_next(request, fallback):
    """A redirect target from the query string, or the fallback.

    Only same-site paths are accepted. An absolute URL in ``?next=`` would
    turn any page carrying one into an open redirect, which is what
    phishing links are made of.
    """
    from django.utils.http import url_has_allowed_host_and_scheme

    wanted = request.GET.get('next') or ''
    if wanted and url_has_allowed_host_and_scheme(
            wanted, allowed_hosts={request.get_host()},
            require_https=request.is_secure()):
        return wanted
    return fallback

def _active_term():
    """The active term, parsed into school year and semester."""
    from .models import SystemSettings
    settings_obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return SystemSettings.parse_label(settings_obj.academic_year)

CHED_ARCHIVE_TIERS = ('Full', 'Half')

def _scholar_groups(stype, groups, portal='vpsea', override=None):
    """Build the rendered table groups for a scholar list.

    One place for every scholar table in the system, so the office and a
    partner see the same record laid out the same way — with only the
    column choice differing between them.
    """
    from . import scholar_columns
    from .models import Scholarship

    programme = Scholarship.objects.filter(type=stype).first()
    columns = scholar_columns.resolve(programme, stype, portal, override=override)
    built = []
    for title, records, empty in groups:
        records = list(records)
        built.append({
            'title': title,
            'rows': scholar_columns.rows_for(records, columns),
            'empty': empty,
        })
    return {
        'columns': columns,
        'scholar_groups': built,
        'has_custom_columns': any(c['custom'] for c in columns),
    }

COLUMN_HINTS = {
    'Academic':    'No. | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Course | Year | GWA | % / Type | Scholarship',
    'Staff':       'No. | Last Name | First Name | Middle Initial | Sex | Course | Year Level | Student Number | % | Scholarship Program',
    'CHED':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'TDP':         'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'DOST':        'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'GSIS':        'No. | Last Name | First Name | Middle Initial | Brgy./St. | Municipality | Province | Sex | Course | Year Level | Student Number | Scholarship Program',
    'Affirmative': 'No. | Award Number | Last Name | First Name | Middle Name | Sex | Brgy./St. | Municipality | Province | Congress District | Course | Yr. | Scholarship Program',
    'CoScho':      'No. | Last Name | First Name | Middle Initial | Sex | Brgy./St. | Municipality | Province | Course | Year Level | Student Number | Scholarship Program',
    'Sports':      'No. | Last Name | First Name | Middle Initial | Sex | Brgy./St. | Municipality | Province | Course | Year Level | Student Number | Scholarship Program',
}

COLUMN_MAPS = {
    'Academic':    [(1,'last_name'),(2,'first_name'),(3,'middle_name'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'gwa'),(11,'pct_type'),(12,'scholarship')],
    'Staff':       [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'course'),(6,'year'),(7,'student_number'),(8,'pct'),(9,'scholarship_program')],
    'CHED':        [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'TDP':         [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'DOST':        [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'GSIS':        [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'barangay'),(5,'municipality'),(6,'province'),(7,'sex'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
    'Affirmative': [(1,'award_number'),(2,'last_name'),(3,'first_name'),(4,'middle_name'),(5,'sex'),(6,'barangay'),(7,'municipality'),(8,'province'),(9,'congress_district'),(10,'course'),(11,'year'),(12,'scholarship_program')],
    'CoScho':      [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
    'Sports':      [(1,'last_name'),(2,'first_name'),(3,'middle_initial'),(4,'sex'),(5,'barangay'),(6,'municipality'),(7,'province'),(8,'course'),(9,'year'),(10,'student_number'),(11,'scholarship_program')],
}

def _custom_columns_for(stype, override=None):
    """Just the custom columns configured for a programme."""
    programme = Scholarship.objects.filter(type=stype).first()
    return [column for column
            in scholar_columns.resolve(programme, stype, override=override)
            if column['custom']]

def _sheet_custom_columns(headings, col_map, columns):
    """Match spreadsheet headings to configured custom columns.

    Columns already claimed by the built-in mapping are skipped, and a
    heading matching a column already matched is ignored, so a sheet with
    two identically named columns does not silently overwrite itself.
    """
    by_key = {column['key']: column for column in columns}
    claimed = {0} | {index for index, _field in col_map}

    matched = {}
    for index, heading in enumerate(headings):
        if index in claimed or heading is None:
            continue
        column = by_key.get(scholar_columns.custom_key(str(heading)))
        if column is not None and column['key'] not in {c['key'] for c in matched.values()}:
            matched[index] = column
    return matched

def _cell_for_custom_column(column, raw):
    """Coerce one spreadsheet cell into a custom column's type.

    openpyxl hands back real ``date`` and ``datetime`` objects, which have
    to become ISO strings before they can be stored as JSON.
    """
    import datetime

    if isinstance(raw, datetime.datetime):
        raw = raw.date().isoformat()
    elif isinstance(raw, datetime.date):
        raw = raw.isoformat()
    if raw is None or str(raw).strip() == '':
        return ''
    return scholar_columns.clean_value(column, raw)

def _scholars_from_sheet(file, stype, term_label, imported_from=None,
                         custom_columns=None):
    """Read scholars out of an uploaded spreadsheet.

    The column mapping follows the programme, because each funder sends a
    different layout. ``CoScho`` is the fallback for anything unmapped.
    """
    import openpyxl

    workbook = openpyxl.load_workbook(file)
    col_map = COLUMN_MAPS.get(stype, COLUMN_MAPS['CoScho'])

    if custom_columns is None:
        custom_columns = _custom_columns_for(stype)

    records, refused = [], 0
    for worksheet in workbook.worksheets:
        found, bad = _scholars_from_worksheet(
            worksheet, stype, term_label, col_map, custom_columns,
            imported_from or file.name)
        records.extend(found)
        refused += bad
    return records, refused

def _scholars_from_worksheet(ws, stype, term_label, col_map, custom_columns,
                             imported_from):
    """Read one worksheet into scholar rows.

    Rows with no usable name are skipped rather than imported blank: a
    spreadsheet almost always carries trailing empty rows, and a list of
    nameless scholars helps nobody.
    """
    from .models import ImportedScholar

    headings = [cell.value for cell in ws[1]] if ws.max_row else []
    from_sheet = _sheet_custom_columns(headings, col_map, custom_columns)

    records, refused = [], 0
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or row[0] is None:
            continue
        try:
            int(row[0])
        except (ValueError, TypeError):
            continue

        extra = {}
        for idx, field in col_map:
            val = row[idx] if idx < len(row) else None
            extra[field] = str(val).strip() if val is not None else ''

        last = extra.get('last_name', '').strip()
        first = extra.get('first_name', '').strip()
        if not last and not first:
            continue

        try:
            year_level = int(extra.get('year', 0) or 0)
        except (ValueError, TypeError):
            year_level = 0
        try:
            gwa = float(extra.get('gwa', 0) or 0)
        except (ValueError, TypeError):
            gwa = 0.0

        address = extra.get('address', '')
        addr_parts = [x.strip() for x in address.split(',')] if address else []

        added = {}
        for index, column in from_sheet.items():
            cleaned = _cell_for_custom_column(
                column, row[index] if index < len(row) else None)
            if cleaned is None:
                refused += 1
            elif cleaned != '':
                added[column['key']] = cleaned

        records.append(ImportedScholar(
            scholarship_type=stype,
            term_label=term_label,
            last_name=last,
            first_name=first,
            middle_name=extra.get('middle_name', extra.get('middle_initial', '')),
            gender=extra.get('sex', ''),
            course=extra.get('course', ''),
            year_level=year_level,
            gwa=gwa,
            barangay=extra.get('barangay', addr_parts[0] if len(addr_parts) > 0 else ''),
            municipality=extra.get('municipality', addr_parts[1] if len(addr_parts) > 1 else ''),
            province=extra.get('province', addr_parts[2] if len(addr_parts) > 2 else ''),
            student_id=extra.get('student_number', extra.get('student_id', '')),
            award_number=extra.get('award_number', ''),
            congress_district=extra.get('congress_district', ''),
            extra_data=added,
            imported_from=imported_from,
        ))
    return records, refused

def _column_picker_context(posted=None, scholarship=None, stype='', portal=''):
    """Context for the column picker on a scholar table."""
    from . import scholar_columns

    if posted is not None:
        chosen = scholar_columns.clean_choice(posted.getlist('table_columns'))
        custom = _posted_custom_columns(posted)
    else:
        chosen = scholar_columns.clean_choice(
            getattr(scholarship, 'table_columns', None))
        custom = list(getattr(scholarship, 'extra_columns', None) or [])
    if not chosen:
        chosen = scholar_columns.default_for(
            stype or getattr(scholarship, 'type', ''), portal)

    order = {key: i for i, key in enumerate(chosen)}
    catalogue = sorted(
        ({'key': key, 'label': label}
         for key, label in scholar_columns.COLUMNS),
        key=lambda c: (order.get(c['key'], len(order)),
                       0 if c['key'] in order else 1),
    )
    for column in catalogue:
        column['position'] = order.get(column['key'])
        column['chosen'] = column['key'] in order
    custom = [{**column,
               'options_text': ', '.join(column.get('options') or ())}
              for column in custom]
    return {
        'column_catalogue': catalogue,
        'chosen_columns': chosen,
        'custom_columns': custom,
        'custom_types': scholar_columns.CUSTOM_TYPES,
    }

def _posted_custom_columns(posted):
    """Read custom column definitions back off the picker form."""
    return scholar_columns.clean_custom(
        posted.getlist('extra_columns'),
        posted.getlist('extra_types'),
        posted.getlist('extra_options'),
    )
