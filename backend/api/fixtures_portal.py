"""Every portal page, rendered, for the checks that have to see the real thing.

A template read off disk is not a page. Half of what accessibility depends on —
which labels exist, which ids a form actually emits, whether a table has any
rows — only appears once a view has filled it in. So this builds a small but
complete database, signs in as each role and hands back the HTML.

Rendered once per test class rather than once per case: there are fifteen pages
and the suite is slow enough already.
"""

from django.test import Client

from .models import (
    Announcement, Application, Scholarship, StaffProfile, StudentProfile,
    SystemSettings, User,
)

OFFICE = 'office@bipsu.edu.ph'
STUDENT = 's1@bipsu.edu.ph'
STAFF = 'teacher@bipsu.edu.ph'
PASSWORD = 'not-a-real-password'

PAGES = (
    ('landing', '/', None),
    ('login', '/login/', None),
    ('register', '/register/', None),
    ('office-accounts', '/vpsea/accounts/', OFFICE),
    ('office-archives', '/vpsea/archives/?type=CHED', OFFICE),
    ('office-students', '/vpsea/students/', OFFICE),
    ('office-scholarships', '/vpsea/scholarships/', OFFICE),
    ('office-renewals', '/vpsea/renewals/', OFFICE),
    ('office-affirmative', '/vpsea/affirmative/', OFFICE),
    ('office-reports', '/vpsea/reports/', OFFICE),
    ('office-ranking', '/vpsea/ranking/', OFFICE),
    ('office-analytics', '/vpsea/analytics/', OFFICE),
    ('student-applications', '/student/applications/', STUDENT),
    ('student-profile', '/student/profile/', STUDENT),
    ('student-notifications', '/student/notifications/', STUDENT),
    ('staff-profile', '/nsu-staff/profile/', STAFF),
    ('staff-apply', '/nsu-staff/apply/', STAFF),
    ('staff-applications', '/nsu-staff/applications/', STAFF),
)


def build_a_small_university():
    """Enough rows that every page has something on it to get wrong."""
    SystemSettings.objects.update_or_create(
        pk=1, defaults={'academic_year': '26-1',
                        'active_semester': '1st Semester'})
    for name, kind in (('Academic Scholarship', 'Academic'),
                       ('CHED Merit', 'CHED'), ('DOST Scholarship', 'DOST')):
        Scholarship.objects.create(
            name=name, type=kind, category='application', group='internal',
            description='A description.', eligibility='Eligibility.',
            requirements=['Certificate of Grades'])

    office = User.objects.create_user(
        username=OFFICE, email=OFFICE, password=PASSWORD, first_name='Office',
        last_name='Staff', role='vpsea', verification_status='approved')
    Announcement.objects.create(
        title='Applications are open', body='Until the end of the month.',
        published_by=office)

    first = Scholarship.objects.first()
    for n in range(4):
        student = User.objects.create_user(
            username=f's{n}@bipsu.edu.ph', email=f's{n}@bipsu.edu.ph',
            password=PASSWORD, first_name=f'Student{n}', last_name='Cruz',
            role='student',
            verification_status='approved' if n else 'pending')
        profile = StudentProfile.objects.create(
            user=student, student_id=f'2024-0000{n}', course='BSCS',
            year_level=(n % 4) + 1, gender='Female' if n % 2 else 'Male',
            municipality='Naval', province='Biliran', shs_gpa=90 + n,
            suc_exam_score=40, suc_exam_total=50)
        Application.objects.create(
            student=profile, scholarship=first,
            status=['Pending Validation', 'Approved', 'Rejected',
                    'Needs Revision'][n],
            term_label='26-1', school_year='2026-2027',
            semester='1st Semester')

    staff = User.objects.create_user(
        username=STAFF, email=STAFF, password=PASSWORD, first_name='Ernesto',
        last_name='Pena', role='nsu_staff', verification_status='approved')
    StaffProfile.objects.create(
        user=staff, employee_id='EMP-1', department='Civil Engineering',
        position='Instructor I')


def render_every_page():
    """``{name: html}`` for every page in :data:`PAGES` that answered.

    A page that redirects or refuses is left out rather than checked as if it
    were a page; :func:`pages_that_answered` is how a case notices that the
    list has quietly shrunk.
    """
    build_a_small_university()
    pages, client, signed_in = {}, Client(), None
    for name, url, who in PAGES:
        if who != signed_in:
            client.logout()
            if who:
                assert client.login(email=who, password=PASSWORD), who
            signed_in = who
        response = client.get(url)
        if response.status_code == 200:
            pages[name] = response.content.decode()
    return pages


def pages_that_answered(pages):
    """The names that rendered, for a case that checks none went missing."""
    return sorted(pages)

def labelled_control(html, caption):
    """The tag of the control a caption is actually attached to, or ``''``.

    A `<label>` with no `for` is a caption, not a label: it is read out as loose
    text and clicking it focuses nothing. Asserting the literal
    `<label>Caption</label>` cannot tell the two apart, so this follows the
    `for` to the id and hands back the control it lands on.
    """
    import re

    label = re.search(
        r'<label[^>]*\bfor="([^"]+)"[^>]*>\s*' + re.escape(caption) + r'\s*</label>',
        html)
    if not label:
        return ''
    control = re.search(
        r'<(?:input|select|textarea)[^>]*\bid="' + re.escape(label.group(1))
        + r'"[^>]*>', html)
    return control.group(0) if control else ''
