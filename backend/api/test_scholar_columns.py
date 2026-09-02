"""A programme choosing the columns its archive table shows.

The archive page carried seven hand-written tables, one per programme, each with
three copies of the row markup — one per shape a scholar arrives in. A column
added to one of them reached none of the others, and a programme that wanted a
column nobody had thought of could not have one at all.

A programme now names its columns on its own form. These tests cover the two
halves that have to agree: what the scholarship form stores, and what the
archive table renders from it.
"""
from django.test import Client, TestCase

from api import scholar_columns
from api.models import (
    AffirmativeStaffApplication, Application, ImportedScholar, Scholarship,
    StudentProfile, SystemSettings, User,
)


def ticked_columns(html):
    """The column keys whose checkbox came back ticked.

    Parsed rather than matched as a substring: the template puts `checked` on
    its own line, and a test that assumed otherwise would pass or fail on the
    template's indentation rather than on the choice.
    """
    import re
    found = []
    for tag in re.findall(r'<input type="checkbox" name="table_columns".*?/>', html, re.S):
        key = re.search(r'value="([^"]+)"', tag)
        if key and 'checked' in tag:
            found.append(key.group(1))
    return found


def custom_column_names(html):
    """The names typed into the custom-column boxes, as the form shows them back."""
    import re
    return re.findall(r'<input name="extra_columns" value="([^"]*)"', html)


def headings_of(html, index=0):
    """The heading row of one archive table, as a list.

    Read off the table rather than searched for in the page: 'GWA' and
    'Municipality' are also field labels in the add-a-scholar form above it, so
    a bare substring check passes whether the column is shown or not.
    """
    import re
    tables = re.findall(r'<table class="scholar-table".*?</thead>', html, re.S)
    if index >= len(tables):
        return []
    # A heading carries attributes now — data-filter marks it as something the
    # filter bar can narrow by, data-no-sort keeps the actions column out of the
    # sort — so the pattern has to allow them.
    # `<th(?:\s...)?>` rather than `<th[^>]*>`: the looser one also matches the
    # opening <thead>, and swallows the first heading into the tag.
    return [h.strip()
            for h in re.findall(r'<th(?:\s[^>]*)?>(.*?)</th>', tables[index], re.S)]


class ColumnChoiceTest(TestCase):
    """What the picker stores, before any table renders it."""

    def test_an_unconfigured_programme_gets_the_columns_its_table_always_had(self):
        """The seven tables were never alike, so neither are the defaults."""
        programme = Scholarship(name='Academic Scholarship', type='Academic')
        keys = [c['key'] for c in scholar_columns.resolve(programme)]
        self.assertEqual(keys, scholar_columns.default_for('Academic'))
        self.assertIn('gwa', keys)
        self.assertNotIn('award_number', keys, 'Academic reports no award number')

    def test_a_programme_reported_against_an_award_number_keeps_it_by_default(self):
        for stype in ('CHED', 'TDP', 'DOST'):
            keys = [c['key'] for c in scholar_columns.resolve(None, stype)]
            self.assertIn('award_number', keys, stype)
            self.assertIn('cong_dist', keys, stype)

    def test_the_two_offices_keep_their_own_default_where_they_disagreed(self):
        """UniFAST reported TES against an award number; the SDSO archive did not."""
        sdso = [c['key'] for c in scholar_columns.resolve(None, 'TES')]
        unifast = [c['key'] for c in scholar_columns.resolve(None, 'TES', 'unifast')]
        self.assertNotIn('award_number', sdso)
        self.assertIn('award_number', unifast)

    def test_a_configured_programme_ignores_which_office_is_asking(self):
        """Choosing the columns once is what makes the two offices agree."""
        programme = Scholarship(name='TES', type='TES', table_columns=['last_name'])
        for portal in ('', 'unifast'):
            keys = [c['key'] for c in scholar_columns.resolve(programme, 'TES', portal)]
            self.assertEqual(keys, ['last_name'])

    def test_columns_come_back_in_catalogue_order_not_the_order_ticked(self):
        """The office is choosing which columns appear, not rearranging them."""
        chosen = scholar_columns.clean_choice(['course', 'last_name', 'award_number'])
        self.assertEqual(chosen, ['award_number', 'last_name', 'course'])

    def test_a_key_that_is_not_a_column_is_dropped(self):
        self.assertEqual(scholar_columns.clean_choice(['last_name', 'shoe_size']),
                         ['last_name'])

    def test_a_selection_of_nothing_but_junk_falls_back_to_the_default(self):
        programme = Scholarship(name='X', type='X', table_columns=['shoe_size'])
        keys = [c['key'] for c in scholar_columns.resolve(programme)]
        self.assertEqual(keys, scholar_columns.DEFAULT_COLUMNS)

    def test_the_unifast_table_keeps_its_own_default_on_the_page(self):
        """Not just in resolve() — the page the office actually opens."""
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        Scholarship.objects.create(name='TES', type='TES', category='application',
                                   description='x', eligibility='x', requirements=[])
        User.objects.create_user(username='u@bipsu.edu.ph', email='u@bipsu.edu.ph',
                                 password='pw', first_name='U', last_name='Officer',
                                 role='unifast')
        c = Client()
        self.assertTrue(c.login(email='u@bipsu.edu.ph', password='pw'))
        html = c.get('/unifast/archives/', {'type': 'TES'}).content.decode()
        self.assertIn('Award No.', headings_of(html))

    def test_a_custom_column_keys_off_its_name_so_renaming_it_back_finds_the_values(self):
        self.assertEqual(scholar_columns.custom_key('Batch No.'), 'extra_batch_no')
        self.assertEqual(scholar_columns.custom_key('  batch   no  '), 'extra_batch_no')

    def test_blank_and_repeated_custom_columns_are_dropped(self):
        columns = scholar_columns.clean_custom(['Batch', '', '  ', 'Batch', 'Adviser'])
        self.assertEqual([c['label'] for c in columns], ['Batch', 'Adviser'])

    def test_a_custom_column_cannot_collide_with_a_catalogue_one(self):
        key = scholar_columns.custom_key('Last Name')
        self.assertTrue(key.startswith(scholar_columns.CUSTOM_PREFIX))
        self.assertNotIn(key, scholar_columns.LABELS)

    def test_custom_columns_come_after_the_catalogue_ones(self):
        programme = Scholarship(
            name='X', type='X', table_columns=['last_name'],
            extra_columns=[{'key': 'extra_batch', 'label': 'Batch'}])
        columns = scholar_columns.resolve(programme)
        self.assertEqual([c['key'] for c in columns], ['last_name', 'extra_batch'])
        self.assertEqual([c['custom'] for c in columns], [False, True])


class ArchiveFixtureMixin:
    """One programme with an award and an imported row under it, and an officer."""

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        self.term = '26-1'
        self.programme = Scholarship.objects.create(
            name='Academic Scholarship', type='Academic', category='application',
            description='x', eligibility='x', requirements=[])

        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        self.profile = StudentProfile.objects.create(
            user=user, student_id='2022-00111', course='BSCS', year_level=3,
            gwa=1.25, gender='Female', municipality='Naval')
        self.award = Application.objects.create(
            student=self.profile, scholarship=self.programme, status='Approved',
            award_number='ACA-001')
        self.imported = ImportedScholar.objects.create(
            scholarship_type='Academic', term_label=self.term, last_name='Cruz',
            first_name='Juan', gender='M', course='BSIT', year_level=2, gwa=1.7,
            student_id='2021-00099')

        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def archive(self, stype='Academic'):
        return self.c.get('/vpsea/archives/', {'type': stype}).content.decode()


class ArchiveTableFollowsTheChoiceTest(ArchiveFixtureMixin, TestCase):
    """The other half: the table renders what the programme asked for."""

    def test_an_unconfigured_programme_looks_the_way_it_always_did(self):
        headings = headings_of(self.archive())
        self.assertEqual(headings[0], '#')
        self.assertEqual(headings[-1], 'Actions')
        self.assertIn('Last Name', headings)
        self.assertIn('GWA', headings)
        self.assertNotIn('Award No.', headings)

    def test_ticking_a_column_puts_it_in_the_table(self):
        self.programme.table_columns = ['last_name', 'award_number']
        self.programme.save(update_fields=['table_columns'])
        headings = headings_of(self.archive())
        self.assertEqual(headings, ['#', 'Award No.', 'Last Name', 'Actions'])

    def test_unticking_a_column_takes_it_out(self):
        self.programme.table_columns = ['last_name']
        self.programme.save(update_fields=['table_columns'])
        headings = headings_of(self.archive())
        for gone in ('GWA', 'Municipality', 'Course', '% / Type of Scholarship'):
            self.assertNotIn(gone, headings)

    def test_every_row_shape_lands_in_the_one_table(self):
        """An award, an imported row and a staff application, all one table now."""
        html = self.archive()
        self.assertIn('Lim', html)          # the award
        self.assertIn('Cruz', html)         # the imported row
        self.assertIn('Imported', html)     # and it kept its own delete

    def test_ched_still_reports_in_two_tier_blocks(self):
        Scholarship.objects.create(name='CHED Merit', type='CHED',
                                   category='application', description='x',
                                   eligibility='x', requirements=[])
        html = self.archive('CHED')
        self.assertIn('Full Merit / Full Scholar', html)
        self.assertIn('Half Merit / Partial Scholar', html)
        self.assertEqual(headings_of(html, 0), headings_of(html, 1),
                         'both CHED blocks report the same programme')

    def test_an_affirmative_or_staff_table_renders_from_its_own_records(self):
        for stype in ('Affirmative', 'Staff'):
            Scholarship.objects.create(name=f'{stype} Scholarship', type=stype,
                                       category='application', description='x',
                                       eligibility='x', requirements=[])
            AffirmativeStaffApplication.objects.create(
                full_name='Rosa Mendoza', contact_number='0918',
                date_of_birth='1990-01-01', course='BSED', year_level=1,
                status='Approved', qualified_for=stype, student_id='EMP-1')
            html = self.archive(stype)
            self.assertIn('Mendoza', html)
            self.assertTrue(headings_of(html), f'{stype} table did not render')


class CustomColumnValuesTest(ArchiveFixtureMixin, TestCase):
    """A column the office added, and the values typed down it."""

    def setUp(self):
        super().setUp()
        self.programme.table_columns = ['last_name']
        self.programme.extra_columns = [{'key': 'extra_batch', 'label': 'Batch'}]
        self.programme.save(update_fields=['table_columns', 'extra_columns'])

    def test_the_custom_column_gets_a_heading_and_a_box_on_every_row(self):
        html = self.archive()
        self.assertIn('Batch', headings_of(html))
        self.assertIn(f'extra__award__{self.award.pk}__extra_batch', html)
        self.assertIn(f'extra__imported__{self.imported.pk}__extra_batch', html)
        self.assertIn('Save column values', html)

    def test_typing_a_value_saves_it_on_the_award(self):
        self.c.post('/vpsea/archives/columns/', {
            'type': 'Academic', 'sy': self.term,
            f'extra__award__{self.award.pk}__extra_batch': '2026-A',
        })
        self.award.refresh_from_db()
        self.assertEqual(self.award.form_data['extra_batch'], '2026-A')
        self.assertIn('2026-A', self.archive())

    def test_typing_a_value_saves_it_on_an_imported_row_too(self):
        """Most programmes reach the system only as imported rows — a custom
        column that skipped them would be blank exactly where it mattered."""
        self.c.post('/vpsea/archives/columns/', {
            'type': 'Academic', 'sy': self.term,
            f'extra__imported__{self.imported.pk}__extra_batch': '2026-B',
        })
        self.imported.refresh_from_db()
        self.assertEqual(self.imported.extra_data['extra_batch'], '2026-B')

    def test_saving_one_column_leaves_the_rest_of_form_data_alone(self):
        self.award.form_data = {'scholar_type': 'Full', 'note': 'keep me'}
        self.award.save(update_fields=['form_data'])
        self.c.post('/vpsea/archives/columns/', {
            'type': 'Academic', 'sy': self.term,
            f'extra__award__{self.award.pk}__extra_batch': '2026-A',
        })
        self.award.refresh_from_db()
        self.assertEqual(self.award.form_data['scholar_type'], 'Full')
        self.assertEqual(self.award.form_data['note'], 'keep me')

    def test_a_field_name_that_is_not_a_custom_column_is_ignored(self):
        """The field names carry a record id, so they cannot be taken on trust."""
        self.c.post('/vpsea/archives/columns/', {
            'type': 'Academic', 'sy': self.term,
            f'extra__award__{self.award.pk}__gwa': '1.00',
            f'extra__award__{self.award.pk}__status': 'Rejected',
            'extra__nonsense__1__extra_batch': 'x',
        })
        self.award.refresh_from_db()
        self.assertNotIn('gwa', self.award.form_data)
        self.assertNotIn('status', self.award.form_data)
        self.assertEqual(self.award.status, 'Approved')

    def test_the_save_button_is_absent_when_no_column_was_added(self):
        self.programme.extra_columns = []
        self.programme.save(update_fields=['extra_columns'])
        self.assertNotIn('Save column values', self.archive())


class ScholarshipFormTest(TestCase):
    """The picker on the Add / Edit Scholarship form."""

    def setUp(self):
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_the_form_offers_every_column_in_the_catalogue(self):
        html = self.c.get('/vpsea/scholarships/add/').content.decode()
        for key, label in scholar_columns.COLUMNS:
            self.assertIn(f'value="{key}"', html, f'{label} is not offered')
        self.assertIn('addCustomColumn', html)

    def test_adding_a_scholarship_stores_the_chosen_columns(self):
        self.c.post('/vpsea/scholarships/add/', {
            'name': 'Sports Scholarship', 'type': 'Sports', 'group': 'internal',
            'description': 'x', 'background': '', 'eligibility_list': '', 'benefits': '',
            'table_columns': ['last_name', 'first_name', 'course'],
            'extra_columns': ['Batch', 'Team'],
        })
        programme = Scholarship.objects.get(type='Sports')
        self.assertEqual(programme.table_columns, ['last_name', 'first_name', 'course'])
        self.assertEqual([c['label'] for c in programme.extra_columns], ['Batch', 'Team'])

    def test_editing_a_scholarship_replaces_the_choice(self):
        programme = Scholarship.objects.create(
            name='GSIS Scholarship', type='GSIS', category='application',
            description='x', eligibility='x', requirements=[],
            table_columns=['last_name'], extra_columns=[{'key': 'extra_batch', 'label': 'Batch'}])
        self.c.post(f'/vpsea/scholarships/{programme.pk}/edit/', {
            'name': 'GSIS Scholarship', 'type': 'GSIS', 'group': 'external',
            'description': 'x', 'background': '', 'eligibility_list': '', 'benefits': '',
            'table_columns': ['award_number', 'last_name'],
            'extra_columns': ['Adviser'],
        })
        programme.refresh_from_db()
        self.assertEqual(programme.table_columns, ['award_number', 'last_name'])
        self.assertEqual([c['label'] for c in programme.extra_columns], ['Adviser'])

    def test_the_edit_form_shows_the_boxes_already_ticked(self):
        programme = Scholarship.objects.create(
            name='TDP Scholarship', type='TDP', category='application',
            description='x', eligibility='x', requirements=[],
            table_columns=['award_number'],
            extra_columns=[{'key': 'extra_batch', 'label': 'Batch'}])
        html = self.c.get(f'/vpsea/scholarships/{programme.pk}/edit/').content.decode()
        self.assertEqual(ticked_columns(html), ['award_number'])
        self.assertEqual(custom_column_names(html), ['Batch'])

    def test_a_rejected_submission_comes_back_with_the_choice_intact(self):
        r = self.c.post('/vpsea/scholarships/add/', {
            'name': '', 'type': 'Sports', 'group': 'internal',
            'description': 'x', 'background': '', 'eligibility_list': '', 'benefits': '',
            'table_columns': ['award_number'], 'extra_columns': ['Batch'],
        })
        self.assertContains(r, 'Name is required')
        html = r.content.decode()
        self.assertEqual(ticked_columns(html), ['award_number'])
        self.assertEqual(custom_column_names(html), ['Batch'])


class BothOfficesReadTheSameChoiceTest(TestCase):
    """A programme names its columns once; the SDSO and UniFAST tables agree.

    The two archive pages carried separate hand-written tables, so the same
    programme could be listed with different columns depending on which office
    was looking at it.
    """

    def setUp(self):
        SystemSettings.objects.update_or_create(pk=1, defaults={'academic_year': '26-1'})
        self.programme = Scholarship.objects.create(
            name='TDP Scholarship', type='TDP', category='application',
            description='x', eligibility='x', requirements=[],
            table_columns=['last_name', 'award_number'],
            extra_columns=[{'key': 'extra_batch', 'label': 'Batch'}])
        self.imported = ImportedScholar.objects.create(
            scholarship_type='TDP', term_label='26-1', last_name='Cruz',
            first_name='Juan', course='BSIT', year_level=2, student_id='2021-00099')
        for role, email in (('vpsea', 'v@bipsu.edu.ph'), ('unifast', 'u@bipsu.edu.ph')):
            User.objects.create_user(username=email, email=email, password='pw',
                                     first_name=role, last_name='Officer', role=role)

    def as_office(self, email, url):
        c = Client()
        self.assertTrue(c.login(email=email, password='pw'))
        return c, c.get(url, {'type': 'TDP'}).content.decode()

    def test_both_offices_render_the_same_headings(self):
        _, sdso = self.as_office('v@bipsu.edu.ph', '/vpsea/archives/')
        _, unifast = self.as_office('u@bipsu.edu.ph', '/unifast/archives/')
        self.assertEqual(headings_of(sdso), ['#', 'Award No.', 'Last Name', 'Batch', 'Actions'])
        self.assertEqual(headings_of(unifast), headings_of(sdso))

    def test_unifast_can_save_a_column_value_of_its_own(self):
        c, _ = self.as_office('u@bipsu.edu.ph', '/unifast/archives/')
        c.post('/unifast/archives/columns/', {
            'type': 'TDP', 'sy': '26-1',
            f'extra__imported__{self.imported.pk}__extra_batch': '2026-B',
        })
        self.imported.refresh_from_db()
        self.assertEqual(self.imported.extra_data['extra_batch'], '2026-B')

    def test_a_student_cannot_write_column_values(self):
        """The endpoint writes office records; only an officer reaches it."""
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        StudentProfile.objects.create(user=user, student_id='2022-00111')
        c = Client()
        self.assertTrue(c.login(email='ana@bipsu.edu.ph', password='pw'))
        for url in ('/vpsea/archives/columns/', '/unifast/archives/columns/'):
            c.post(url, {'type': 'TDP',
                         f'extra__imported__{self.imported.pk}__extra_batch': 'nope'})
        self.imported.refresh_from_db()
        self.assertEqual(self.imported.extra_data, {})
