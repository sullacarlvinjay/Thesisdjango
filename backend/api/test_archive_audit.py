"""Every hand edit to the archives says who made it.

Imports and semester rollovers were audited; adding, editing and deleting a
scholar by hand were not. Three of the four things an officer does on that page
left no trace at all — a row could be created, changed or destroyed and the only
evidence was that the number in the table had moved.

These drive the real views and read the trail back, rather than checking that
``ActivityLog.record`` appears in the source, because an entry written with no
actor would satisfy that and answer nobody.
"""

from django.test import Client, TestCase

from api.models import (
    ActivityLog, ImportedScholar, Scholarship, SystemSettings, User,
)


class ArchiveEditsAreAttributedTest(TestCase):
    term = '26-1'

    def setUp(self):
        SystemSettings.objects.update_or_create(
            pk=1, defaults={'academic_year': self.term,
                            'active_semester': '1st Semester'})
        Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            group='internal', description='x', eligibility='x', requirements=[])
        self.officer = User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='Rosario', last_name='Bayhon', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def add(self, last='Scholar', student_id='99-9-999999'):
        self.c.post('/vpsea/archives/add/', {
            'scholarship_type': 'Academic', 'first_name': 'Testa',
            'last_name': last, 'student_id': student_id, 'gender': 'Female',
            'course': 'BSCS', 'year_level': '2', 'gwa': '1.5',
            'create_account': 'no'})
        return ImportedScholar.objects.get(student_id=student_id)

    def entries(self, verb=None):
        rows = ActivityLog.objects.filter(user=self.officer)
        return list(rows.filter(verb=verb) if verb else rows)

    def test_adding_a_scholar_names_the_officer_who_added_them(self):
        self.add()
        written = self.entries('create')
        self.assertEqual(len(written), 1)
        self.assertIn('Testa Scholar', written[0].action)
        self.assertEqual(written[0].user, self.officer)

    def test_the_entry_points_at_the_row_it_created(self):
        row = self.add()
        entry = self.entries('create')[0]
        self.assertEqual(entry.target_type, 'ImportedScholar')
        self.assertEqual(entry.target_id, str(row.pk))

    def test_deleting_a_scholar_is_recorded_after_the_row_is_gone(self):
        row = self.add()
        self.c.post(f'/vpsea/archives/imported/{row.pk}/delete/',
                    {'scholarship_type': 'Academic'})
        self.assertFalse(ImportedScholar.objects.filter(pk=row.pk).exists())
        entry = self.entries('delete')[0]
        self.assertEqual(entry.user, self.officer)
        self.assertIn('Testa Scholar', entry.target_label)

    def test_the_page_shows_what_happened_without_opening_a_menu(self):
        self.add()
        page = self.c.get('/vpsea/archives/?type=Academic')
        self.assertContains(page, 'Recent Activity')
        self.assertContains(page, 'activity-feed__row')
        self.assertContains(page, 'Rosario Bayhon')

    def test_an_untouched_page_says_so_rather_than_showing_an_empty_list(self):
        page = self.c.get('/vpsea/archives/?type=Academic')
        self.assertContains(page, 'Nothing has been added')
        self.assertNotContains(page, 'activity-feed__row')

    def test_the_feed_is_newest_first(self):
        self.add(last='Alpha', student_id='99-9-000001')
        self.add(last='Beta', student_id='99-9-000002')
        shown = self.c.get('/vpsea/archives/?type=Academic').context['recent_activity']
        self.assertIn('Beta', shown[0].action)
        self.assertIn('Alpha', shown[1].action)


class AnAuditEntryNamesTheModelTest(TestCase):
    """``identify`` reads the model, not the wrapper a view happens to pass."""

    def test_a_lazy_request_user_is_still_recorded_as_a_user(self):
        User.objects.create_user(
            username='out@bipsu.edu.ph', email='out@bipsu.edu.ph',
            password='pw', role='student', verification_status='approved')
        client = Client()
        self.assertTrue(client.login(email='out@bipsu.edu.ph', password='pw'))
        client.get('/logout/')
        signed_out = ActivityLog.objects.filter(action='Signed out').first()
        self.assertIsNotNone(signed_out)
        self.assertEqual(signed_out.target_type, 'User')
