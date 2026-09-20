from django.test import Client, TestCase

from api import scholar_columns
from api.models import (
    ApplicantRecord, Application, ImportedScholar, Scholarship,
    StudentProfile, SystemSettings, User,
)


def ticked_columns(html):
    import re
    found = []
    for tag in re.findall(r'<input type="checkbox" name="table_columns".*?/>', html, re.S):
        key = re.search(r'value="([^"]+)"', tag)
        if key and 'checked' in tag:
            found.append(key.group(1))
    return found


def custom_column_names(html):
    import re
    return re.findall(r'<input name="extra_columns" value="([^"]*)"', html)


def headings_of(html, index=0):
    import re
    tables = re.findall(
        r'<table[^>]*\bclass="[^"]*\bscholar-table\b[^"]*".*?</thead>',
        html, re.S)
    if index >= len(tables):
        return []
    return [h.strip()
            for h in re.findall(r'<th(?:\s[^>]*)?>(.*?)</th>', tables[index], re.S)]


class ColumnChoiceTest(TestCase):
    def test_an_unconfigured_programme_gets_the_columns_its_table_always_had(self):
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

    def test_a_partner_keeps_its_own_default_where_the_two_disagreed(self):
        sdso = [c['key'] for c in scholar_columns.resolve(None, 'TES')]
        partner = [c['key'] for c in scholar_columns.resolve(None, 'TES', 'partner')]
        self.assertNotIn('award_number', sdso)
        self.assertIn('award_number', partner)

    def test_a_configured_programme_ignores_who_is_asking(self):
        programme = Scholarship(name='TES', type='TES', table_columns=['last_name'])
        for portal in ('', 'partner'):
            keys = [c['key'] for c in scholar_columns.resolve(programme, 'TES', portal)]
            self.assertEqual(keys, ['last_name'])

    def test_columns_keep_the_order_they_were_given(self):
        chosen = scholar_columns.clean_choice(['course', 'last_name', 'award_number'])
        self.assertEqual(chosen, ['course', 'last_name', 'award_number'])

    def test_a_column_named_twice_is_kept_once(self):
        self.assertEqual(
            scholar_columns.clean_choice(['course', 'last_name', 'course']),
            ['course', 'last_name'])

    def test_the_chosen_order_survives_all_the_way_to_the_table(self):
        programme = Scholarship(name='X', type='X',
                                table_columns=['course', 'last_name'])
        keys = [c['key'] for c in scholar_columns.resolve(programme)]
        self.assertEqual(keys, ['course', 'last_name'])

    def test_a_key_that_is_not_a_column_is_dropped(self):
        self.assertEqual(scholar_columns.clean_choice(['last_name', 'shoe_size']),
                         ['last_name'])

    def test_a_selection_of_nothing_but_junk_falls_back_to_the_default(self):
        programme = Scholarship(name='X', type='X', table_columns=['shoe_size'])
        keys = [c['key'] for c in scholar_columns.resolve(programme)]
        self.assertEqual(keys, scholar_columns.DEFAULT_COLUMNS)

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

    def archive(self, stype='Academic', **query):
        return self.c.get('/vpsea/archives/',
                          {'type': stype, **query}).content.decode()


class ArchiveTableFollowsTheChoiceTest(ArchiveFixtureMixin, TestCase):
    def test_an_unconfigured_programme_looks_the_way_it_always_did(self):
        headings = headings_of(self.archive())
        self.assertEqual(headings[0], '#')
        self.assertEqual(headings[-1], 'Actions')
        self.assertIn('Last Name', headings)
        self.assertIn('GWA', headings)
        self.assertNotIn('Award No.', headings)

    def test_ticking_a_column_puts_it_in_the_table_where_it_was_put(self):
        self.programme.table_columns = ['last_name', 'award_number']
        self.programme.save(update_fields=['table_columns'])
        self.assertEqual(headings_of(self.archive()),
                         ['#', 'Last Name', 'Award No.', 'Actions'])

        self.programme.table_columns = ['award_number', 'last_name']
        self.programme.save(update_fields=['table_columns'])
        self.assertEqual(headings_of(self.archive()),
                         ['#', 'Award No.', 'Last Name', 'Actions'])

    def test_unticking_a_column_takes_it_out(self):
        self.programme.table_columns = ['last_name']
        self.programme.save(update_fields=['table_columns'])
        headings = headings_of(self.archive())
        for gone in ('GWA', 'Municipality', 'Course', '% / Type of Scholarship'):
            self.assertNotIn(gone, headings)

    def test_every_row_shape_lands_in_the_one_table(self):
        html = self.archive()
        self.assertIn('Lim', html)
        self.assertIn('Cruz', html)
        self.assertIn('Imported', html)

    def test_both_ched_tiers_report_the_one_programme_the_same_way(self):
        Scholarship.objects.create(name='CHED Merit', type='CHED',
                                   category='application', description='x',
                                   eligibility='x', requirements=[])
        full = headings_of(self.archive('CHED', tier='Full'))
        half = headings_of(self.archive('CHED', tier='Half'))

        self.assertEqual(full, half,
                         'the two CHED tabs report the same programme')
        self.assertIn('Award No.', full)

    def test_an_affirmative_or_staff_table_renders_from_its_own_records(self):
        for stype in ('Affirmative', 'Staff'):
            Scholarship.objects.create(name=f'{stype} Scholarship', type=stype,
                                       category='application', description='x',
                                       eligibility='x', requirements=[])
            ApplicantRecord.objects.create(
                full_name='Rosa Mendoza', contact_number='0918',
                date_of_birth='1990-01-01', course='BSED', year_level=1,
                status='Approved', qualified_for=stype, student_id='EMP-1')
            html = self.archive(stype)
            self.assertIn('Mendoza', html)
            self.assertTrue(headings_of(html), f'{stype} table did not render')


class CustomColumnValuesTest(ArchiveFixtureMixin, TestCase):
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


class TheArchiveReadsTheProgrammesChoiceTest(TestCase):
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
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')

    def as_office(self, email, url):
        c = Client()
        self.assertTrue(c.login(email=email, password='pw'))
        return c, c.get(url, {'type': 'TDP'}).content.decode()

    def test_the_page_renders_the_headings_the_programme_names(self):
        _, sdso = self.as_office('v@bipsu.edu.ph', '/vpsea/archives/')
        self.assertEqual(headings_of(sdso), ['#', 'Last Name', 'Award No.', 'Batch', 'Actions'])

    def test_the_office_can_save_a_column_value(self):
        c, _ = self.as_office('v@bipsu.edu.ph', '/vpsea/archives/')
        c.post('/vpsea/archives/columns/', {
            'type': 'TDP', 'sy': '26-1',
            f'extra__imported__{self.imported.pk}__extra_batch': '2026-B',
        })
        self.imported.refresh_from_db()
        self.assertEqual(self.imported.extra_data['extra_batch'], '2026-B')

    def test_a_student_cannot_write_column_values(self):
        user = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        StudentProfile.objects.create(user=user, student_id='2022-00111')
        c = Client()
        self.assertTrue(c.login(email='ana@bipsu.edu.ph', password='pw'))
        c.post('/vpsea/archives/columns/',
               {'type': 'TDP',
                f'extra__imported__{self.imported.pk}__extra_batch': 'nope'})
        self.imported.refresh_from_db()
        self.assertEqual(self.imported.extra_data, {})


class ACustomColumnDeclaresWhatItHoldsTest(TestCase):
    def test_the_kind_is_stored_beside_the_name(self):
        columns = scholar_columns.clean_custom(
            ['Batch', 'Stipend', 'Awarded On'], ['text', 'number', 'date'], ['', '', ''])
        self.assertEqual([c['type'] for c in columns], ['text', 'number', 'date'])

    def test_a_choice_list_keeps_the_options_as_a_list(self):
        columns = scholar_columns.clean_custom(
            ['Tier'], ['choice'], ['Full, Partial , Full'])
        self.assertEqual(columns[0]['type'], 'choice')
        self.assertEqual(columns[0]['options'], ['Full', 'Partial'])

    def test_a_choice_list_with_no_options_is_a_text_column(self):
        columns = scholar_columns.clean_custom(['Tier'], ['choice'], ['  '])
        self.assertEqual(columns[0]['type'], 'text')
        self.assertNotIn('options', columns[0])

    def test_a_kind_that_is_not_one_of_the_offered_ones_reads_as_text(self):
        columns = scholar_columns.clean_custom(['Batch'], ['sql'], [''])
        self.assertEqual(columns[0]['type'], 'text')

    def test_a_blank_row_does_not_slide_the_kinds_onto_the_wrong_columns(self):
        columns = scholar_columns.clean_custom(
            ['Batch', '', 'Stipend'], ['text', 'date', 'number'], ['', '', ''])
        self.assertEqual([(c['label'], c['type']) for c in columns],
                         [('Batch', 'text'), ('Stipend', 'number')])

    def test_a_column_stored_before_kinds_existed_reads_as_text(self):
        programme = Scholarship(name='X', type='X', table_columns=['last_name'],
                                extra_columns=[{'key': 'extra_batch', 'label': 'Batch'}])
        batch = scholar_columns.resolve(programme)[-1]
        self.assertEqual(batch['type'], 'text')
        self.assertEqual(batch['options'], [])


class OnlyThatKindOfValueIsStoredTest(TestCase):
    def cleaned(self, kind, raw, options=None):
        column = {'type': kind, 'options': options or []}
        return scholar_columns.clean_value(column, raw)

    def test_blank_is_always_allowed(self):
        for kind in ('text', 'number', 'date', 'choice', 'yesno'):
            self.assertEqual(self.cleaned(kind, '   ', ['Full']), '')

    def test_a_number_column_refuses_what_is_not_a_number(self):
        self.assertIsNone(self.cleaned('number', 'n/a'))
        self.assertIsNone(self.cleaned('number', '2,500 pesos'))

    def test_a_number_column_refuses_the_two_floats_that_are_not_figures(self):
        self.assertIsNone(self.cleaned('number', 'inf'))
        self.assertIsNone(self.cleaned('number', 'nan'))

    def test_a_number_is_stored_the_way_it_would_be_written(self):
        self.assertEqual(self.cleaned('number', ' 2500 '), '2500')
        self.assertEqual(self.cleaned('number', '2,500'), '2500')
        self.assertEqual(self.cleaned('number', '1.5'), '1.5')

    def test_a_date_column_stores_iso_and_refuses_a_non_date(self):
        self.assertEqual(self.cleaned('date', '2026-06-15'), '2026-06-15')
        self.assertEqual(self.cleaned('date', '15/06/2026'), '2026-06-15')
        self.assertIsNone(self.cleaned('date', 'sometime in June'))

    def test_a_choice_column_refuses_an_answer_not_on_its_list(self):
        self.assertEqual(self.cleaned('choice', 'full', ['Full', 'Partial']), 'Full',
                         "and stores it in the office's own spelling")
        self.assertIsNone(self.cleaned('choice', 'Three-quarters', ['Full', 'Partial']))

    def test_a_yes_no_column_takes_only_those_two(self):
        self.assertEqual(self.cleaned('yesno', 'yes'), 'Yes')
        self.assertIsNone(self.cleaned('yesno', 'maybe'))

    def test_a_text_column_still_takes_anything(self):
        self.assertEqual(self.cleaned('text', '  2026-A  '), '2026-A')


class TheRowsBoxIsTheKindTheColumnDeclaredTest(ArchiveFixtureMixin, TestCase):
    def with_columns(self, *extras):
        self.programme.table_columns = ['last_name']
        self.programme.extra_columns = list(extras)
        self.programme.save(update_fields=['table_columns', 'extra_columns'])
        return self.archive()

    def test_a_choice_column_is_a_dropdown_of_its_options(self):
        html = self.with_columns({'key': 'extra_tier', 'label': 'Tier',
                                  'type': 'choice', 'options': ['Full', 'Partial']})
        self.assertIn(f'name="extra__award__{self.award.pk}__extra_tier"', html)
        self.assertIn('<option value="Full">Full</option>', html)
        self.assertIn('<option value="Partial">Partial</option>', html)

    def test_a_yes_no_column_offers_those_two_without_being_given_them(self):
        html = self.with_columns({'key': 'extra_hostel', 'label': 'Hostel',
                                  'type': 'yesno'})
        self.assertIn('<option value="Yes">Yes</option>', html)
        self.assertIn('<option value="No">No</option>', html)

    def test_a_date_column_gets_a_date_box_and_a_number_a_number_box(self):
        html = self.with_columns(
            {'key': 'extra_awarded_on', 'label': 'Awarded On', 'type': 'date'},
            {'key': 'extra_stipend', 'label': 'Stipend', 'type': 'number'})
        self.assertIn('type="date"', html)
        self.assertIn('type="number"', html)

    def test_the_value_already_stored_is_the_one_selected(self):
        self.with_columns({'key': 'extra_tier', 'label': 'Tier', 'type': 'choice',
                           'options': ['Full', 'Partial']})
        scholar_columns.set_extra_values(self.award, {'extra_tier': 'Partial'})
        self.assertIn('<option value="Partial" selected>Partial</option>',
                      self.archive())


class AValueThatIsNotThatKindIsNotStoredTest(ArchiveFixtureMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.programme.table_columns = ['last_name']
        self.programme.extra_columns = [
            {'key': 'extra_stipend', 'label': 'Stipend', 'type': 'number'},
            {'key': 'extra_tier', 'label': 'Tier', 'type': 'choice',
             'options': ['Full', 'Partial']},
        ]
        self.programme.save(update_fields=['table_columns', 'extra_columns'])

    def save(self, **fields):
        return self.c.post('/vpsea/archives/columns/',
                           {'type': 'Academic', 'sy': self.term, **fields})

    def test_a_number_column_handed_words_keeps_the_cell_it_had(self):
        self.save(**{f'extra__award__{self.award.pk}__extra_stipend': '2500'})
        self.save(**{f'extra__award__{self.award.pk}__extra_stipend': 'n/a'})
        self.award.refresh_from_db()
        self.assertEqual(self.award.form_data['extra_stipend'], '2500')

    def test_the_office_is_told_how_many_boxes_to_go_back_to(self):
        response = self.save(**{
            f'extra__award__{self.award.pk}__extra_stipend': 'n/a',
            f'extra__award__{self.award.pk}__extra_tier': 'Three-quarters',
        })
        self.assertIn('columns_bad=2', response['Location'])
        followed = self.c.get(response['Location']).content.decode()
        self.assertIn('2 values did not match', followed)

    def test_the_rows_that_were_fine_are_still_saved(self):
        response = self.save(**{
            f'extra__award__{self.award.pk}__extra_stipend': 'n/a',
            f'extra__imported__{self.imported.pk}__extra_stipend': '1800',
        })
        self.imported.refresh_from_db()
        self.assertEqual(self.imported.extra_data['extra_stipend'], '1800')
        self.assertIn('columns_saved=1', response['Location'])

    def test_a_column_belonging_to_some_other_programme_is_not_written(self):
        self.save(**{f'extra__award__{self.award.pk}__extra_somebody_elses': 'x'})
        self.award.refresh_from_db()
        self.assertNotIn('extra_somebody_elses', self.award.form_data)


class TheFormAsksWhatTheColumnHoldsTest(TestCase):
    def setUp(self):
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_the_form_offers_every_kind(self):
        html = self.c.get('/vpsea/scholarships/add/').content.decode()
        for key, label in scholar_columns.CUSTOM_TYPES:
            self.assertIn(f'{key}:{label}', html)

    def test_adding_a_scholarship_stores_the_kinds_chosen(self):
        self.c.post('/vpsea/scholarships/add/', {
            'name': 'Sports Scholarship', 'type': 'Sports', 'group': 'internal',
            'description': 'x', 'background': '', 'eligibility_list': '', 'benefits': '',
            'table_columns': ['last_name'],
            'extra_columns': ['Batch', 'Tier'],
            'extra_types': ['number', 'choice'],
            'extra_options': ['', 'Full, Partial'],
        })
        stored = Scholarship.objects.get(type='Sports').extra_columns
        self.assertEqual([(c['label'], c['type']) for c in stored],
                         [('Batch', 'number'), ('Tier', 'choice')])
        self.assertEqual(stored[1]['options'], ['Full', 'Partial'])

    def test_the_edit_form_shows_the_kind_and_the_options_back(self):
        programme = Scholarship.objects.create(
            name='TDP Scholarship', type='TDP', category='application',
            description='x', eligibility='x', requirements=[],
            extra_columns=[{'key': 'extra_tier', 'label': 'Tier', 'type': 'choice',
                            'options': ['Full', 'Partial']}])
        html = self.c.get(f'/vpsea/scholarships/{programme.pk}/edit/').content.decode()
        self.assertIn('<option value="choice" selected>', html)
        self.assertIn('value="Full, Partial"', html)


class ANamedColumnCannotRepeatACatalogueOneTest(TestCase):
    def setUp(self):
        User.objects.create_user(
            username='v@bipsu.edu.ph', email='v@bipsu.edu.ph', password='pw',
            first_name='V', last_name='Officer', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def test_a_name_the_archive_already_fills_is_refused(self):
        for typed in ('Course', 'GWA', 'Last Name', 'Sex', 'Scholarship Program'):
            self.assertTrue(scholar_columns.names_a_catalogue_column(typed), typed)

    def test_the_name_is_matched_however_it_is_written(self):
        for typed in ('Award No.', 'award no', 'AWARD NO', 'Award Number',
                      'award_number', '  award   no.  '):
            self.assertTrue(scholar_columns.names_a_catalogue_column(typed), typed)

    def test_a_genuinely_new_name_is_still_allowed(self):
        for typed in ('Batch', 'Batch No.', 'Adviser', 'Remarks', 'Year Awarded'):
            self.assertFalse(scholar_columns.names_a_catalogue_column(typed), typed)

    def test_the_clashing_column_is_not_stored(self):
        columns = scholar_columns.clean_custom(['Course', 'Batch', 'GWA', 'Adviser'])
        self.assertEqual([c['label'] for c in columns], ['Batch', 'Adviser'])

    def test_the_table_no_longer_carries_one_heading_twice(self):
        programme = Scholarship(
            name='X', type='CHED', table_columns=['last_name', 'course'],
            extra_columns=scholar_columns.clean_custom(['Course', 'Batch']))
        labels = [c['label'] for c in scholar_columns.resolve(programme)]
        self.assertEqual(labels, ['Last Name', 'Course', 'Batch'])
        self.assertEqual(len(labels), len(set(labels)), labels)

    def test_the_refused_names_are_reported_in_the_order_they_were_typed(self):
        self.assertEqual(
            scholar_columns.catalogue_clashes(['Course', 'Batch', 'GWA']),
            ['Course', 'GWA'])

    def test_the_form_refuses_the_save_and_names_the_column(self):
        r = self.c.post('/vpsea/scholarships/add/', {
            'name': 'Sports Scholarship', 'type': 'Sports', 'group': 'internal',
            'description': 'x', 'background': '', 'eligibility_list': '',
            'benefits': '', 'table_columns': ['last_name', 'course'],
            'extra_columns': ['Course'], 'extra_types': ['text'],
            'extra_options': [''],
        })
        self.assertEqual(r.status_code, 200, 'the save should not have gone through')
        self.assertFalse(Scholarship.objects.filter(type='Sports').exists())
        self.assertTrue(any('"Course"' in e for e in r.context['errors']),
                        r.context['errors'])
        self.assertTrue(any('tick it in the list above' in e
                            for e in r.context['errors']), r.context['errors'])

    def test_editing_refuses_it_too_and_leaves_the_programme_alone(self):
        programme = Scholarship.objects.create(
            name='GSIS Scholarship', type='GSIS', category='application',
            description='x', eligibility='x', requirements=[],
            table_columns=['last_name'],
            extra_columns=[{'key': 'extra_batch', 'label': 'Batch', 'type': 'text'}])
        r = self.c.post(f'/vpsea/scholarships/{programme.pk}/edit/', {
            'name': 'GSIS Scholarship', 'type': 'GSIS', 'group': 'internal',
            'description': 'x', 'background': '', 'eligibility_list': '',
            'benefits': '', 'table_columns': ['last_name'],
            'extra_columns': ['GWA'], 'extra_types': ['text'],
            'extra_options': [''],
        })
        self.assertEqual(r.status_code, 200)
        programme.refresh_from_db()
        self.assertEqual([c['label'] for c in programme.extra_columns], ['Batch'])

    def test_a_name_that_is_not_taken_still_saves(self):
        r = self.c.post('/vpsea/scholarships/add/', {
            'name': 'Sports Scholarship', 'type': 'Sports', 'group': 'internal',
            'description': 'x', 'background': '', 'eligibility_list': '',
            'benefits': '', 'table_columns': ['last_name', 'course'],
            'extra_columns': ['Batch'], 'extra_types': ['text'],
            'extra_options': [''],
        })
        self.assertEqual(r.status_code, 302)
        programme = Scholarship.objects.get(type='Sports')
        self.assertEqual([c['label'] for c in programme.extra_columns], ['Batch'])
