"""A partner's changes reach the office's activity card.

An external partner writes into the same ``ImportedScholar`` table the office
reads. Their actions were audited, but every entry was written without a
``target``, so the row carried no ``target_type`` — and the office's Recent
Activity card selects on exactly that. A partner could add, edit, delete or
re-import scholars and none of it would reach the page the office watches.

These drive both portals: the partner acts, the office loads its own page, and
the entry has to be there with the partner named on it.
"""

from django.test import Client, TestCase

from api.models import (
    ActivityLog, ImportedScholar, PartnerOffice, Scholarship, SystemSettings,
    User,
)


class APartnersChangesAreVisibleToTheOfficeTest(TestCase):
    term = '26-1'

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year=self.term,
                                      active_semester='1st Semester')
        self.dost = Scholarship.objects.create(
            name='DOST Scholarship', type='DOST', category='application',
            description='x', eligibility='x', requirements=[])

        self.office = PartnerOffice.objects.create(name='DOST Region VIII')
        self.office.scholarships.add(self.dost)
        self.partner = User.objects.create_user(
            username='dost@bipsu.edu.ph', email='dost@bipsu.edu.ph',
            password='pw', role='partner')
        self.partner.partner_office = self.office
        self.partner.save()

        self.officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')

        self.pc = Client()
        self.assertTrue(self.pc.login(email='dost@bipsu.edu.ph', password='pw'))
        self.oc = Client()
        self.assertTrue(self.oc.login(email='v@bipsu.edu.ph', password='pw'))

    def partner_adds(self, last='Rosales'):
        self.pc.post('/partner/scholars/', {
            'action': 'add', 'type': 'DOST', 'sy': self.term,
            'first_name': 'Ana', 'last_name': last, 'student_id': '2022-11111',
            'gender': 'Female', 'course': 'BSCS', 'year_level': '2'})
        return ImportedScholar.objects.filter(last_name=last).first()

    def office_feed(self):
        page = self.oc.get('/vpsea/archives/?type=DOST')
        return list(page.context['recent_activity'])

    def test_a_partner_add_is_recorded_against_the_row_it_created(self):
        row = self.partner_adds()
        self.assertIsNotNone(row, 'the partner add did not create a scholar')
        entry = ActivityLog.objects.filter(verb='create').first()
        self.assertEqual(entry.target_type, 'ImportedScholar')
        self.assertEqual(entry.target_id, str(row.pk))

    def test_the_office_sees_it_on_its_own_archives_page(self):
        self.partner_adds()
        shown = self.office_feed()
        self.assertTrue(shown, 'the office feed showed nothing')
        self.assertIn('DOST Region VIII', shown[0].action)
        self.assertEqual(shown[0].user, self.partner)

    def test_a_partner_delete_is_recorded_after_the_row_is_gone(self):
        row = self.partner_adds()
        self.pc.post('/partner/scholars/', {
            'action': 'delete', 'type': 'DOST', 'sy': self.term,
            'scholar_id': row.pk})
        self.assertFalse(ImportedScholar.objects.filter(pk=row.pk).exists())
        entry = ActivityLog.objects.filter(verb='delete').first()
        self.assertEqual(entry.target_type, 'ImportedScholar')
        self.assertIn('Rosales', entry.target_label)
        self.assertIn(entry.action, [e.action for e in self.office_feed()])

    def test_the_office_can_tell_a_partner_edit_from_its_own(self):
        row = self.partner_adds()
        self.pc.post('/partner/scholars/', {
            'action': 'edit', 'type': 'DOST', 'sy': self.term,
            'scholar_id': row.pk, 'first_name': 'Ana', 'last_name': 'Rosales',
            'student_id': '2022-11111', 'gender': 'Female', 'course': 'BSIT',
            'year_level': '3'})
        edits = ActivityLog.objects.filter(verb='update')
        self.assertTrue(edits.exists(), 'the partner edit was not recorded')
        self.assertEqual(edits.first().user, self.partner)
        self.assertIn('DOST Region VIII', edits.first().action)
