"""What the student sidebar offers, and when.

Renewal used to show from the day an account was created, so a student with
nothing to renew could walk into a page whose only job was to tell them so. It
now arrives with the scholarship it renews.

The nav had been copied into ten templates, which is how that survived: a change
had to be made ten times to be made at all. It lives in student/_nav.html now,
and the last test here is what keeps it there.

Which Apply page is offered is a per-programme question, not a per-student one.
Every programme is held on its own, so holding any one of them closes the Apply
pages. See can_hold_alongside in api/student_views.py.
"""
import glob
import io
import os
import re

from django.test import Client, TestCase

from api.models import (
    Application, Scholarship, ScholarshipLinkRequest, StudentProfile,
    SystemSettings, User,
)

TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'templates', 'student')


class StudentNavTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.scholarship = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])
        self.user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='2022-00111', course='BSCS', year_level=2)
        self.c = Client()
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))

    def nav(self, url='/student/applications/'):
        """The sidebar link labels, in order."""
        r = self.c.get(url)
        self.assertEqual(r.status_code, 200, url)
        html = r.content.decode()
        nav = html.split('</aside>')[0]
        return re.findall(r'class="sidebar-link[^"]*"[^>]*>(?:<svg.*?</svg>)?([^<]+)',
                          nav, re.S)

    def _enrol(self):
        Application.objects.create(
            student=self.profile, scholarship=self.scholarship, status='Approved',
            school_year='2026-2027', semester='1st Semester')

    # ── Renewal ─────────────────────────────────────────────────────────────

    def test_renewal_is_hidden_until_there_is_something_to_renew(self):
        self.assertNotIn('Renewal', self.nav())

    def test_renewal_appears_once_a_scholarship_is_held(self):
        self._enrol()
        self.assertIn('Renewal', self.nav())

    def test_a_pending_application_is_not_yet_something_to_renew(self):
        Application.objects.create(
            student=self.profile, scholarship=self.scholarship,
            status='Pending Validation', school_year='2026-2027',
            semester='1st Semester')
        self.assertNotIn('Renewal', self.nav())

    def test_an_approved_link_also_brings_renewal(self):
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='CHED', status='Approved',
            term_label='26-1')
        self.assertIn('Renewal', self.nav())

    # ── Apply ───────────────────────────────────────────────────────────────

    def test_the_apply_page_is_offered_to_a_student_holding_nothing(self):
        self.assertIn('Apply: Academic', self.nav())

    def test_an_academic_scholar_has_nothing_left_to_apply_for(self):
        self._enrol()
        self.assertNotIn('Apply: Academic', self.nav())

    def test_any_other_programme_closes_the_page_too(self):
        """TDP, DOST, CHED and the rest are held on their own."""
        ScholarshipLinkRequest.objects.create(
            student=self.profile, scholarship_type='DOST', status='Approved',
            term_label='26-1')
        self.assertNotIn('Apply: Academic', self.nav())

    def test_there_is_no_tes_page_to_offer(self):
        """TES is UniFAST's and is not applied for here — see the catalogue."""
        self.assertNotIn('Apply: TES', self.nav())
        self.assertEqual(self.c.get('/student/apply/tes/').status_code, 404)

    def test_there_is_no_link_scholarship_entry_left(self):
        """A scholarship already held is declared at registration instead."""
        self.assertNotIn('Link Scholarship', self.nav())
        self.assertNotIn('/student/link-scholarship/', self.c.get(
            '/student/applications/').content.decode())

    # ── The nav lives in one file ───────────────────────────────────────────

    def test_every_student_template_includes_the_shared_nav(self):
        """Copied into ten files is how the two bugs above were possible.

        The tag is matched up to the template name rather than in full: what
        this protects is that the nav comes from one file, and a page that
        passes the include an argument has not broken that. Matching the whole
        `{% include ... %}` failed a template for adding a `with` clause, which
        is a spelling difference, not a second copy of the nav.
        """
        for path in sorted(glob.glob(os.path.join(TEMPLATE_DIR, '*.html'))):
            name = os.path.basename(path)
            if name == '_nav.html':
                continue
            html = io.open(path, encoding='utf-8').read()
            self.assertIn('{% include "student/_nav.html"', html, name)
            # No stray copy left behind to drift out of step again.
            self.assertNotIn('/student/renewal/academic/" class="sidebar-link',
                             html, f'{name} still has its own copy of the nav')
