"""High-stakes actions warn before they happen, and name the consequence.

The evaluators asked for hazard warnings. Seven destructive controls already
asked "are you sure?"; the ones that could not be taken back — replacing a
scholar list, rolling the whole system to a new semester, deciding a
registration — asked nothing at all.

A warning that only repeats the button's own label is not a warning, so these
cases check the consequence is stated, and that exactly one script implements
the dialog.
"""

import glob
import re

from django.conf import settings
from django.test import Client, SimpleTestCase, TestCase

from api.models import (
    Application, Scholarship, ScholarshipLinkRequest, StudentProfile,
    SystemSettings, User,
)


def attributes_on(html, needle):
    """The data-confirm attributes of the control containing ``needle``."""
    for tag in re.findall(r'<button[^>]*>', html):
        if needle in tag:
            return dict(re.findall(r'data-(confirm[a-z-]*)="([^"]*)"', tag))
    return {}


class TheDialogIsTheOnlyImplementationTest(SimpleTestCase):

    def test_one_script_implements_the_dialog_and_no_other(self):
        """Two scripts reading data-confirm would ask twice, or not at all."""
        owners = [path for path in glob.glob('static/js/*.js')
                  if 'data-confirm' in open(path, encoding='utf-8').read()
                  or 'confirmDialog' in open(path, encoding='utf-8').read()]
        self.assertEqual(
            [p.replace('\\', '/') for p in owners],
            ['static/js/confirm-dialog.js'])

    def test_the_dialog_can_show_a_consequence_and_a_hazard_icon(self):
        base = (settings.BASE_DIR / 'templates/base.html').read_text(
            encoding='utf-8')
        self.assertIn('id="confirmConsequence"', base)
        self.assertIn('id="confirmIcon"', base)

    def test_the_script_reads_the_consequence_it_is_given(self):
        source = (settings.BASE_DIR / 'static/js/confirm-dialog.js').read_text(
            encoding='utf-8')
        self.assertIn('confirmConsequence', source)
        self.assertIn('dataset.confirmConsequence', source)

    def test_focus_lands_on_cancel_not_on_the_dangerous_button(self):
        """One stray Enter must not be enough to do the thing."""
        source = (settings.BASE_DIR / 'static/js/confirm-dialog.js').read_text(
            encoding='utf-8')
        opened = source.split('function open(')[1].split('function close(')[0]
        self.assertIn('cancelEl.focus()', opened)
        self.assertNotIn('goEl.focus()', opened)


class TheOfficeIsWarnedTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        Scholarship.objects.create(
            name='CHED Merit', type='CHED', category='application',
            description='x', eligibility='x', requirements=[])
        User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.client = Client()
        self.assertTrue(self.client.login(
            email='sdso@bipsu.edu.ph', password='pw'))

    def _archives(self):
        return self.client.get('/vpsea/archives/?type=CHED').content.decode()

    def test_replacing_a_scholar_list_says_there_is_no_undo(self):
        marks = attributes_on(self._archives(), 'Replace the list')
        self.assertTrue(marks, 'the import button carries no warning at all')
        self.assertIn('no undo', marks['confirm-consequence'])
        self.assertEqual(marks['confirm-tone'], 'danger')

    def test_the_import_warning_says_what_survives_it(self):
        marks = attributes_on(self._archives(), 'Replace the list')
        self.assertIn('already claimed are kept', marks['confirm-consequence'])

    def test_rolling_the_term_over_says_it_moves_the_whole_system(self):
        marks = attributes_on(self._archives(), 'Start the new semester')
        self.assertTrue(marks, 'the rollover button carries no warning at all')
        self.assertIn('not just this page', marks['confirm-detail'])
        self.assertEqual(marks['confirm-tone'], 'danger')

    def test_undoing_the_term_says_what_it_does_not_undo(self):
        marks = attributes_on(self._archives(), 'Step the term back')
        self.assertTrue(marks, 'the undo button carries no warning at all')
        self.assertIn('not a way to reopen', marks['confirm-consequence'])

    def test_every_warning_names_its_own_action_on_the_button(self):
        """"Confirm" tells nobody what they are about to do."""
        html = self._archives()
        for tag in re.findall(r'<button[^>]*data-confirm=[^>]*>', html):
            marks = dict(re.findall(r'data-(confirm[a-z-]*)="([^"]*)"', tag))
            with self.subTest(action=marks.get('confirm', '')[:40]):
                self.assertNotIn(marks.get('confirm-label', ''),
                                 ('', 'Confirm', 'OK', 'Yes'))


class ApprovingIsWarnedTest(TestCase):

    def setUp(self):
        SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        for stype in ('CHED', 'DOST'):
            Scholarship.objects.create(
                name=f'{stype} Scholarship', type=stype,
                category='application', description='x', eligibility='x',
                requirements=[])
        User.objects.create_user(
            username='sdso@bipsu.edu.ph', email='sdso@bipsu.edu.ph',
            password='pw', role='vpsea')
        self.client = Client()
        self.client.login(email='sdso@bipsu.edu.ph', password='pw')

    def _a_registrant(self, *declared, student_id='2026-0001'):
        """A pending account declaring the named programmes."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        user = User.objects.create_user(
            username=f'{student_id}@bipsu.edu.ph',
            email=f'{student_id}@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Cruz', role='student',
            verification_status='pending')
        profile = StudentProfile.objects.create(
            user=user, student_id=student_id, course='BSCS', year_level=2)
        for stype in declared:
            ScholarshipLinkRequest.objects.create(
                student=profile, scholarship_type=stype, status='Pending',
                term_label='26-1',
                proof_document=SimpleUploadedFile(
                    f'{stype}.pdf', b'%PDF-1.4',
                    content_type='application/pdf'))
        return user, profile

    def _warning_for(self, account):
        page = self.client.get('/vpsea/accounts/')
        for row in page.context['pending']:
            if row.pk == account.pk:
                return row.duplicate_benefit_warning
        return None

    def test_one_declared_grant_is_no_hazard(self):
        account, _profile = self._a_registrant('CHED')
        self.assertEqual(self._warning_for(account), '')

    def test_two_declared_national_grants_are_named_as_a_hazard(self):
        account, _profile = self._a_registrant('CHED', 'DOST')
        warning = self._warning_for(account)
        self.assertIn('CHED', warning)
        self.assertIn('DOST', warning)
        self.assertIn('not meant to be held together', warning)

    def test_declaring_one_while_already_holding_another_is_a_hazard(self):
        account, profile = self._a_registrant('DOST')
        Application.objects.create(
            student=profile, scholarship=Scholarship.objects.get(type='CHED'),
            status='Approved', term_label='26-1')
        warning = self._warning_for(account)
        self.assertIn('already holds CHED', warning)
        self.assertIn('duplicate government benefit', warning)

    def test_the_verify_button_carries_the_hazard_when_there_is_one(self):
        self._a_registrant('CHED', 'DOST')
        html = self.client.get('/vpsea/accounts/').content.decode()
        marks = attributes_on(html, 'Verify the account')
        self.assertEqual(marks['confirm-tone'], 'danger')
        self.assertIn('DOST', marks.get('confirm-consequence', ''))

    def test_rejecting_says_the_person_reads_the_message(self):
        self._a_registrant('CHED')
        html = self.client.get('/vpsea/accounts/').content.decode()
        marks = attributes_on(html, 'Reject the account')
        self.assertIn('Rejection is not silent', marks['confirm-consequence'])
