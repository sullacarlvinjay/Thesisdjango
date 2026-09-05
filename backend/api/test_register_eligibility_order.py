"""The two eligibility cards come last, and only for a student who holds nothing.

They ask what someone might qualify for. A student who has just declared an
award in Scholarship Data has already answered that, so asking anyway collected
two accounts of the same fact that could disagree — a student could tick "I
already hold a scholarship: TES" at the top of the form and leave "I am a
current TES beneficiary" unticked further up it, and both would be recorded.

Two halves to the rule, and both are needed:

* **Order.** Scholarship Data comes first, because whether you hold something
  decides whether the rest of the questions are asked at all.
* **The hidden attribute is rendered by the server**, not only toggled by the
  script, so a form coming back from a validation error is right before any
  JavaScript runs and a reader without JavaScript is never shown a question the
  form has stopped asking.

The fields themselves stay optional server-side, which is what makes hiding them
safe: a post with them disabled records nothing rather than failing.
"""
import re

from django.test import Client, TestCase

from api.models import SystemSettings


def _card(html, element_id):
    """The opening tag of one card, so its `hidden` attribute can be read."""
    match = re.search(r'<div[^>]*id="' + element_id + r'"[^>]*>', html)
    return match.group(0) if match else ''


class RegisterEligibilityOrderTest(TestCase):
    def setUp(self):
        SystemSettings.objects.create(pk=1, academic_year='26-1',
                                      active_semester='1st Semester')
        self.c = Client()

    def _form(self, **post):
        """The registration form, optionally as it comes back from a bad post."""
        if post:
            return self.c.post('/register/', dict({
                'account_type': 'student', 'first_name': 'Juan',
                'last_name': 'Cruz', 'email': 'juan@gmail.com',
                # Mismatched on purpose: the form has to come back rendered,
                # carrying what was typed, which is the case that broke.
                'password': 'pw12345', 'confirm_password': 'different',
                'student_id': '23-0001', 'course': 'BSCS', 'year_level': '1',
            }, **post)).content.decode()
        return self.c.get('/register/').content.decode()

    # ── Order ───────────────────────────────────────────────────────────────

    def test_both_eligibility_cards_come_after_scholarship_data(self):
        html = self._form()
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertLess(html.index('id="scholarshipData"'),
                                html.index(f'id="{card}"'),
                                f'{card} still renders before Scholarship Data')

    def test_scholarship_eligibility_comes_before_tes_eligibility(self):
        """Their order relative to each other is unchanged."""
        html = self._form()
        self.assertLess(html.index('id="scholarshipEligibility"'),
                        html.index('id="tesEligibility"'))

    def test_they_stay_inside_the_form(self):
        """Moved, not moved out — a card past </form> posts nothing."""
        html = self._form()
        self.assertLess(html.index('id="tesEligibility"'), html.index('</form>'))

    # ── Shown to a student who holds nothing ────────────────────────────────

    def test_a_blank_form_asks_both(self):
        html = self._form()
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertNotIn('hidden', _card(html, card))

    # ── Hidden once a scholarship is declared ───────────────────────────────

    def test_declaring_a_scholarship_hides_both(self):
        """The rule itself, rendered by the server rather than left to script."""
        html = self._form(has_scholarship='on', scholarship_type='DOST')
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertIn('hidden', _card(html, card),
                              f'{card} was still asked of a declared scholar')

    def test_the_scholarship_data_card_opens_in_their_place(self):
        """The two are opposites: one closes exactly as the other opens."""
        html = self._form(has_scholarship='on', scholarship_type='DOST')
        self.assertNotIn('hidden', _card(html, 'scholarshipData'))

    def test_not_declaring_leaves_them_asked(self):
        html = self._form()
        self.assertIn('hidden', _card(html, 'scholarshipData'))
        self.assertNotIn('hidden', _card(html, 'scholarshipEligibility'))

    # ── A staff registration shows neither ──────────────────────────────────

    def test_a_staff_form_hides_them_whatever_the_box_says(self):
        """The trap in reading this as simply 'not declaring': on a staff form
        nothing is declared either, and these are student cards."""
        html = self._form(account_type='nsu_staff')
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertIn('hidden', _card(html, card))

    # ── Hiding them is safe ─────────────────────────────────────────────────

    def test_registering_without_any_eligibility_answers_still_works(self):
        """What the disabled fields post: nothing. Every one of them is optional
        server-side, so the account is created rather than the form refused."""
        from api.models import User

        self.c.post('/register/', {
            'account_type': 'student', 'first_name': 'Ana', 'last_name': 'Reyes',
            'email': 'ana@gmail.com', 'password': 'pw12345',
            'confirm_password': 'pw12345', 'student_id': '23-0002',
            'course': 'BSCS', 'year_level': '1',
        })
        self.assertTrue(User.objects.filter(email='ana@gmail.com').exists())

    def test_a_declared_scholar_registers_with_the_cards_posting_nothing(self):
        """The case the change creates: the two cards are disabled, so none of
        their fields arrive. The declaration alone has to carry the form.

        The proof document is required for a declaration and always was — that
        rule predates this and is not what is being tested here; it is included
        so the post is a valid one.
        """
        from django.core.files.uploadedfile import SimpleUploadedFile

        from api.models import ScholarshipLinkRequest, User

        self.c.post('/register/', {
            'account_type': 'student', 'first_name': 'Ben', 'last_name': 'Lim',
            'email': 'ben@gmail.com', 'password': 'pw12345',
            'confirm_password': 'pw12345', 'student_id': '23-0003',
            'course': 'BSCS', 'year_level': '1',
            'has_scholarship': 'on', 'scholarship_type': 'DOST',
            'proof_document': SimpleUploadedFile(
                'award.pdf', b'%PDF-1.4 award letter', content_type='application/pdf'),
        })
        self.assertTrue(User.objects.filter(email='ben@gmail.com').exists())
        self.assertTrue(ScholarshipLinkRequest.objects.filter(
            student__user__email='ben@gmail.com', scholarship_type='DOST').exists())

    def test_both_cards_are_still_marked_student_only(self):
        """The account-type switch finds its blocks by this marker, so a card
        that lost it would survive a flip to the staff form."""
        html = self._form()
        for card in ('scholarshipEligibility', 'tesEligibility'):
            with self.subTest(card=card):
                self.assertIn('data-student-only', _card(html, card))
