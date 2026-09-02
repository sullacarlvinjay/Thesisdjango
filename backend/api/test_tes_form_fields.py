"""The TES apply form, against the columns CHED's Annex 1 actually asks for.

Three things are guarded. That the programme and disability a student can pick
are the workbook's own lists, so a value this form accepts is never one the
sheet would reject. That the two optional CHED identifiers are collected rather
than exported blank. And that every box is the student's to fill in: the half
that comes from the profile arrives filled in and is saved back to it, so a
correction made here is a correction everywhere and there is still one copy of
each fact rather than two that can disagree.
"""
from django.test import TestCase, Client

from api import annex1_report
from api.models import (
    User, StudentProfile, Scholarship, TESApplication, SystemSettings,
)


class TESFormOptionsTest(TestCase):
    """The dropdowns are the workbook's lookup sheets, not a list typed in code."""

    def test_programs_are_the_registry_names_not_the_bipsu_abbreviations(self):
        programs = annex1_report.registry_programs()
        self.assertIn('BACHELOR OF SCIENCE IN COMPUTER SCIENCE', programs)
        self.assertIn('BACHELOR OF SCIENCE IN INFORMATION SYSTEM', programs)
        # 'BSCS' is what the university calls it; CHED reads the Annex 1
        # against its own registry, which is why the short form cannot be here.
        self.assertNotIn('BSCS', programs)
        self.assertGreater(len(programs), 30)

    def test_the_heading_row_is_not_an_option(self):
        self.assertNotIn('Course Name', annex1_report.registry_programs())
        self.assertNotIn('Disability', annex1_report.disability_types())

    def test_disabilities_are_cheds_list_plus_other(self):
        options = annex1_report.disability_types()
        self.assertEqual(options[0], 'NO')          # how the sheet spells N/A
        self.assertIn('Visual Disability', options)
        self.assertIn('Mental/ Psychosocial Disability', options)
        self.assertEqual(options[-1], annex1_report.OTHER)

    def test_the_lists_match_what_the_sheet_validates_against(self):
        """The form and the workbook's own dropdown cannot disagree."""
        import openpyxl
        ws = openpyxl.load_workbook(annex1_report.TEMPLATE_PATH)['Annex 1']
        sources = {dv.formula1: dv for dv in ws.data_validations.dataValidation}

        self.assertIn('Registry_Courses!$A$2:$A$41', sources)
        self.assertEqual(len(annex1_report.registry_programs()), 40)
        self.assertIn('Disability_List!$A$2:$A$12', sources)
        # 11 sheet values, plus this system's own 'Other'.
        self.assertEqual(len(annex1_report.disability_types()), 12)


class TESFormTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        Scholarship.objects.create(
            name='TES', type='TES', category='application',
            description='x', eligibility='x', requirements=[])
        self.user = User.objects.create_user(
            username='juan@gmail.com', email='juan@gmail.com', password='pw',
            first_name='Juan', last_name='Cruz', role='student')
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='23-0001', course='BSCS', year_level=2,
            gender='Male', middle_name='Santos')
        self.profile.mother_last_name = 'Reyes'
        self.profile.mother_first_name = 'Maria'
        self.profile.save()

        self.c = Client()
        self.assertTrue(self.c.login(email='juan@gmail.com', password='pw'))

    def _post(self, **extra):
        return self.c.post('/student/apply/tes/', dict({
            # The profile half of the form, editable and saved back to it.
            'student_id': '23-0001', 'last_name': 'Cruz', 'first_name': 'Juan',
            'middle_name': 'Santos', 'gender': 'Male', 'year_level': '2',
            'mother_last_name': 'Reyes', 'mother_first_name': 'Maria',
            'lrn': '123456789012',
            'birthdate': '2005-03-14',
            'complete_program': 'BACHELOR OF SCIENCE IN COMPUTER SCIENCE',
            'street_barangay': 'Purok 1, Poblacion',
            'city_municipality': 'Naval', 'province': 'Biliran',
            'region': 'Region VIII', 'zip_code': '6560',
            'contact_number': '09171234567', 'email_address': 'juan@gmail.com',
            'disability_type': 'NO',
            'is_solo_parent_dependent': '0', 'is_first_gen_college': '0',
            'indigenous_people_group': 'Not Applicable',
        }, **extra))

    # ── The dropdowns on the page ───────────────────────────────────────────

    def test_the_form_offers_the_registry_programmes(self):
        r = self.c.get('/student/apply/tes/')
        self.assertContains(r, 'BACHELOR OF SCIENCE IN COMPUTER SCIENCE')
        self.assertContains(r, 'name="complete_program"')
        self.assertContains(r, 'Select your programme')

    def test_the_programmes_are_grouped_by_school(self):
        """Forty entries opening with the same four words need a shape."""
        groups = self.c.get('/student/apply/tes/').context['program_groups']
        schools = [school for school, _programs in groups]
        self.assertIn('School of Engineering', schools)
        self.assertIn('School of Teacher Education', schools)
        # Every programme is filed somewhere, none twice.
        filed = [p for _school, programs in groups for p in programs]
        self.assertEqual(sorted(filed), sorted(annex1_report.registry_programs()))
        # Alphabetical inside each school.
        for _school, programs in groups:
            self.assertEqual(programs, sorted(programs))

    def test_the_schools_are_rendered_as_option_groups(self):
        r = self.c.get('/student/apply/tes/')
        self.assertContains(r, '<optgroup label="School of Engineering">')

    def test_the_school_dropdown_narrows_the_programme_list(self):
        r = self.c.get('/student/apply/tes/')
        self.assertContains(r, 'id="programSchool"')
        self.assertContains(r, 'data-filters="#completeProgram"')
        self.assertContains(r, '— All schools —')
        self.assertContains(r, 'js/select-by-group')

    def test_the_school_is_not_part_of_the_application(self):
        """It is worked out from the programme; storing it would be a copy."""
        html = self.c.get('/student/apply/tes/').content.decode()
        # No name attribute, so the browser never posts it.
        self.assertNotIn('name="programSchool"', html)
        self.assertNotIn('name="program_school"', html)

    def test_a_programme_off_the_registry_is_refused(self):
        """The dropdown is the registry; anything else is a hand-made post."""
        r = self._post(complete_program='BSCS')
        self.assertContains(r, 'Pick your programme from the list')
        self.assertFalse(TESApplication.objects.filter(student=self.profile).exists())

    def test_the_form_offers_the_disability_list_and_other(self):
        r = self.c.get('/student/apply/tes/')
        self.assertContains(r, 'Visual Disability')
        self.assertContains(r, 'NO — not applicable')
        self.assertContains(r, f'value="{annex1_report.OTHER}"')
        self.assertContains(r, 'data-reveals="#disabilityOther"')

    # ── The two optional CHED identifiers ───────────────────────────────────

    def test_philsys_and_four_ps_ids_are_collected(self):
        self._post(philsys_id='1234-5678-9012', four_ps_id='4P-000123')
        tes = TESApplication.objects.get(student=self.profile)
        self.assertEqual(tes.philsys_id, '1234-5678-9012')
        self.assertEqual(tes.four_ps_id, '4P-000123')

    def test_they_reach_the_annex_1_columns(self):
        self._post(philsys_id='1234-5678-9012', four_ps_id='4P-000123')
        row = annex1_report.applicant_rows()[0]
        self.assertEqual(row['philsys_id'], '1234-5678-9012')
        self.assertEqual(row['four_ps_id'], '4P-000123')
        values = annex1_report.row_values(row)
        self.assertEqual(values[3], '1234-5678-9012')       # column D
        self.assertEqual(values[4], '4P-000123')            # column E

    def test_leaving_them_blank_is_fine_because_both_are_optional(self):
        self._post()
        tes = TESApplication.objects.get(student=self.profile)
        self.assertEqual(tes.philsys_id, '')
        self.assertEqual(tes.four_ps_id, '')

    # ── 'Other' on the disability dropdown ──────────────────────────────────

    def test_other_saves_what_the_student_typed_not_the_word_other(self):
        self._post(disability_type=annex1_report.OTHER,
                   disability_type_other='Speech and language impairment')
        tes = TESApplication.objects.get(student=self.profile)
        self.assertEqual(tes.disability_type, 'Speech and language impairment')

    def test_other_with_nothing_typed_is_refused(self):
        r = self._post(disability_type=annex1_report.OTHER,
                       disability_type_other='   ')
        self.assertContains(r, 'Name the disability')
        self.assertFalse(TESApplication.objects.filter(student=self.profile).exists())

    def test_a_typed_disability_comes_back_as_other_when_editing(self):
        """Or re-opening the form would silently drop what they wrote."""
        self._post(disability_type=annex1_report.OTHER,
                   disability_type_other='Speech and language impairment')

        r = self.c.get('/student/apply/tes/')
        self.assertEqual(r.context['post']['disability_type'], annex1_report.OTHER)
        self.assertEqual(r.context['post']['disability_type_other'],
                         'Speech and language impairment')

    def test_a_listed_disability_comes_back_selected_on_the_dropdown(self):
        self._post(disability_type='Visual Disability')
        r = self.c.get('/student/apply/tes/')
        self.assertEqual(r.context['post']['disability_type'], 'Visual Disability')
        self.assertEqual(r.context['post']['disability_type_other'], '')

    def test_no_still_exports_as_no(self):
        self._post(disability_type='NO')
        self.assertEqual(annex1_report.applicant_rows()[0]['disability'], 'NO')


class EditableProfileHalfTest(TestCase):
    """The form fills itself in from the profile, and writes back to it.

    On the profile page these fields lock after the first save, so that an edit
    cannot quietly change a record the office has already reviewed. This form
    only opens while the application is undecided — nothing has been reviewed —
    so the same reasoning leaves them open here.
    """

    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        Scholarship.objects.create(
            name='TES', type='TES', category='application',
            description='x', eligibility='x', requirements=[])
        self.user = User.objects.create_user(
            username='juan@gmail.com', email='juan@gmail.com', password='pw',
            first_name='Juan', last_name='Cruz', role='student')
        self.profile = StudentProfile.objects.create(
            user=self.user, student_id='23-0001', course='BSCS', year_level=2,
            gender='Male', middle_name='Santos')
        self.c = Client()
        self.assertTrue(self.c.login(email='juan@gmail.com', password='pw'))

    def _post(self, **extra):
        return self.c.post('/student/apply/tes/', dict({
            'student_id': '23-0001', 'last_name': 'Cruz', 'first_name': 'Juan',
            'middle_name': 'Santos', 'gender': 'Male', 'year_level': '2',
            'mother_last_name': 'Reyes', 'mother_first_name': 'Maria',
            'lrn': '123456789012', 'birthdate': '2005-03-14',
            'complete_program': 'BACHELOR OF SCIENCE IN COMPUTER SCIENCE',
            'street_barangay': 'Purok 1', 'city_municipality': 'Naval',
            'province': 'Biliran', 'region': 'Region VIII', 'zip_code': '6560',
            'contact_number': '09171234567', 'email_address': 'juan@gmail.com',
            'disability_type': 'NO', 'is_solo_parent_dependent': '0',
            'is_first_gen_college': '0', 'indigenous_people_group': 'Not Applicable',
        }, **extra))

    # ── Filled in from the profile ──────────────────────────────────────────

    def test_the_boxes_arrive_filled_in_from_the_profile(self):
        post = self.c.get('/student/apply/tes/').context['post']
        self.assertEqual(post['student_id'], '23-0001')
        self.assertEqual(post['last_name'], 'Cruz')
        self.assertEqual(post['first_name'], 'Juan')
        self.assertEqual(post['middle_name'], 'Santos')
        self.assertEqual(post['gender'], 'Male')

    def test_nothing_is_read_only_any_more(self):
        html = self.c.get('/student/apply/tes/').content.decode()
        for field in ('student_id', 'last_name', 'first_name', 'middle_name',
                      'mother_last_name', 'father_last_name'):
            self.assertIn(f'name="{field}"', html, field)
        self.assertNotIn('readonly', html)

    # ── Saved back to the profile ───────────────────────────────────────────

    def test_correcting_a_name_here_corrects_the_profile(self):
        self._post(middle_name='Ramirez', mother_last_name='Reyes',
                   mother_first_name='Maria', mother_middle_name='Lim')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.middle_name, 'Ramirez')
        self.assertEqual(self.profile.mother_last_name, 'Reyes')
        self.assertEqual(self.profile.mother_middle_name, 'Lim')

    def test_correcting_the_student_name_corrects_the_account(self):
        self._post(last_name='dela Cruz', first_name='Juan Miguel')
        self.user.refresh_from_db()
        self.assertEqual(self.user.last_name, 'dela Cruz')
        self.assertEqual(self.user.first_name, 'Juan Miguel')

    def test_the_application_keeps_no_copy_of_the_names(self):
        """One record of each fact — the reason these were read-only at all."""
        self._post()
        for gone in ('middle_name', 'mother_last_name', 'father_last_name'):
            self.assertNotIn(gone, [f.name for f in TESApplication._meta.fields])

    def test_the_corrections_reach_the_annex_1(self):
        self._post(middle_name='Ramirez', gender='Female', year_level='4',
                   mother_last_name='Reyes', mother_first_name='Maria')
        row = annex1_report.applicant_rows()[0]
        self.assertEqual(row['middle_name'], 'Ramirez')
        self.assertEqual(row['sex'], 1)                 # Female
        self.assertEqual(row['year_level'], 4)
        self.assertEqual(row['mother_last_name'], 'Reyes')

    # ── Still valid where CHED requires it ──────────────────────────────────

    def test_a_blank_required_field_is_refused(self):
        r = self._post(mother_last_name='', mother_first_name='')
        self.assertContains(r, 'CHED requires')
        self.assertContains(r, "Mother&#x27;s last name")
        self.assertFalse(TESApplication.objects.filter(student=self.profile).exists())

    def test_the_fathers_name_is_still_optional(self):
        self.assertEqual(self._post(father_last_name='').status_code, 302)

    def test_a_year_level_outside_one_to_six_is_refused(self):
        self.assertContains(self._post(year_level='9'), 'Year level must be a number')
        self.assertContains(self._post(year_level='abc'), 'Year level must be a number')

    def test_a_student_id_belonging_to_someone_else_is_refused(self):
        """It is the key the office matches against its enrolment list."""
        other = User.objects.create_user(
            username='ana@gmail.com', email='ana@gmail.com', password='pw',
            first_name='Ana', last_name='Lim', role='student')
        StudentProfile.objects.create(user=other, student_id='23-9999')

        r = self._post(student_id='23-9999')
        self.assertContains(r, 'belongs to another account')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.student_id, '23-0001')

    def test_keeping_your_own_student_id_is_not_a_collision(self):
        self.assertEqual(self._post(student_id='23-0001').status_code, 302)

    def test_a_rejected_submission_shows_what_was_typed_not_what_is_stored(self):
        """Or a field they were correcting comes back with the old value."""
        r = self._post(middle_name='Ramirez', mother_last_name='')
        self.assertEqual(r.context['post']['middle_name'], 'Ramirez')
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.middle_name, 'Santos', 'nothing saved on error')

    def test_a_decided_application_is_still_closed_to_editing(self):
        """'No locking' is about the boxes, not about reopening a decision."""
        self._post()
        app = TESApplication.objects.get(student=self.profile)
        app.status = 'Approved'
        app.save(update_fields=['status'])

        self._post(middle_name='Changed', lrn='999999999999')
        app.refresh_from_db()
        self.profile.refresh_from_db()
        self.assertEqual(app.lrn, '123456789012')
        self.assertEqual(self.profile.middle_name, 'Santos')
