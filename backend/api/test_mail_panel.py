from unittest import mock

from django.test import Client, TestCase, override_settings

from api.models import SystemSettings, User

BREVO = 'api.email_backends.BrevoEmailBackend'
SMTP = 'django.core.mail.backends.smtp.EmailBackend'
CONSOLE = 'django.core.mail.backends.console.EmailBackend'


class MailPanelTest(TestCase):
    def setUp(self):
        self.settings_row = SystemSettings.objects.create(
            pk=1, academic_year='26-1', active_semester='1st Semester')
        User.objects.create_user(username='v@bipsu.edu.ph', email='v@bipsu.edu.ph',
                                 password='pw', role='vpsea')
        self.c = Client()
        self.assertTrue(self.c.login(email='v@bipsu.edu.ph', password='pw'))

    def html(self):
        r = self.c.get('/vpsea/accounts/')
        self.assertEqual(r.status_code, 200)
        return r.content.decode()

    def context(self):
        return self.c.get('/vpsea/accounts/').context['mail']

    @override_settings(EMAIL_BACKEND=BREVO, EMAIL_ENABLED=True, BREVO_API_KEY='k')
    def test_the_brevo_route_is_named_as_itself(self):
        mail = self.context()
        self.assertEqual(mail['route'], 'Brevo')
        self.assertTrue(mail['enabled'])
        self.assertIn('443', mail['route_detail'])

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_ENABLED=True,
                       EMAIL_HOST='smtp.gmail.com', EMAIL_PORT=587)
    def test_the_smtp_route_says_render_blocks_it(self):
        mail = self.context()
        self.assertEqual(mail['route'], 'SMTP')
        self.assertIn('smtp.gmail.com', mail['route_detail'])
        self.assertIn('blocks outbound SMTP', mail['route_detail'])

    @override_settings(EMAIL_BACKEND=CONSOLE, EMAIL_ENABLED=False)
    def test_no_configuration_says_nobody_is_being_emailed(self):
        mail = self.context()
        self.assertEqual(mail['route'], 'Not configured')
        self.assertFalse(mail['enabled'])
        self.assertIn('delivered to', mail['route_detail'])
        self.assertIn('Not configured', self.html())

    @override_settings(EMAIL_BACKEND=BREVO, EMAIL_ENABLED=True,
                       BREVO_API_KEY='super-secret-key')
    def test_the_api_key_is_reported_as_set_and_never_printed(self):
        mail = self.context()
        self.assertTrue(mail['key_set'])
        self.assertNotIn('super-secret-key', str(mail))
        self.assertNotIn('super-secret-key', self.html())

    @override_settings(EMAIL_BACKEND=SMTP, EMAIL_ENABLED=True,
                       EMAIL_HOST='smtp.gmail.com',
                       EMAIL_HOST_PASSWORD='an-app-password')
    def test_the_smtp_password_is_never_printed_either(self):
        self.assertNotIn('an-app-password', self.html())

    @override_settings(EMAIL_BACKEND=BREVO, EMAIL_ENABLED=True,
                       DEFAULT_FROM_EMAIL='BiPSU SRMS <sdso@bipsu.edu.ph>')
    def test_the_sender_is_shown_because_it_is_what_is_usually_wrong(self):
        self.assertIn('sdso@bipsu.edu.ph', self.html())

    def test_before_anything_is_sent_it_says_so(self):
        self.assertIsNone(self.context()['last_at'])
        self.assertIn('Nothing has been sent from this deployment yet', self.html())

    def test_a_failure_is_recorded_with_the_providers_own_words(self):
        from api import notify
        with mock.patch('api.notify.send_mail',
                        side_effect=Exception('Brevo refused the message (400). '
                                              '{"message":"sender not valid"}')):
            self.assertFalse(notify.send_email('ana@bipsu.edu.ph', 'Subject', 'Body'))

        mail = self.context()
        self.assertIsNotNone(mail['last_at'])
        self.assertEqual(mail['last_to'], 'ana@bipsu.edu.ph')
        self.assertIn('sender not valid', mail['last_error'])
        self.assertIn('sender not valid', self.html())

    def test_a_success_is_recorded_with_no_error_against_it(self):
        from api import notify
        with mock.patch('api.notify.send_mail', return_value=1):
            self.assertTrue(notify.send_email('ana@bipsu.edu.ph', 'Subject', 'Body'))
        mail = self.context()
        self.assertEqual(mail['last_error'], '')
        self.assertIn('It left this server', self.html())

    def test_recording_never_turns_a_mail_failure_into_a_page_failure(self):
        from api import notify
        with mock.patch('api.notify.send_mail', side_effect=Exception('down')), \
             mock.patch('api.models.SystemSettings.objects.update_or_create',
                        side_effect=Exception('database is down too')):
            self.assertFalse(notify.send_email('ana@bipsu.edu.ph', 'Subject', 'Body'))

    def test_sending_a_test_reports_that_it_went(self):
        with mock.patch('api.notify.send_mail', return_value=1) as send:
            r = self.c.post('/vpsea/accounts/',
                            {'action': 'test_email', 'test_to': 'me@bipsu.edu.ph'})
        self.assertEqual(send.call_args.kwargs['recipient_list'], ['me@bipsu.edu.ph'])
        self.assertIn('tested=1', r['Location'])
        self.assertIn('accepted for delivery',
                      self.c.get(r['Location']).content.decode())

    def test_a_refused_test_is_not_reported_as_sent(self):
        with mock.patch('api.notify.send_mail',
                        side_effect=Exception('{"message":"Key not found"}')):
            r = self.c.post('/vpsea/accounts/',
                            {'action': 'test_email', 'test_to': 'me@bipsu.edu.ph'})
        self.assertIn('tested=0', r['Location'])
        html = self.c.get(r['Location']).content.decode()
        self.assertIn('did not go out', html)
        self.assertIn('Key not found', html)

    def test_a_test_with_no_address_is_refused_rather_than_sent_to_nobody(self):
        with mock.patch('api.notify.send_mail') as send:
            r = self.c.post('/vpsea/accounts/',
                            {'action': 'test_email', 'test_to': '   '})
        send.assert_not_called()
        self.assertIn('error=', r['Location'])

    def test_the_test_send_does_not_decide_anybody_s_account(self):
        student = User.objects.create_user(
            username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph', password='pw',
            role='student', verification_status='pending')
        with mock.patch('api.notify.send_mail', return_value=1):
            self.c.post('/vpsea/accounts/',
                        {'action': 'test_email', 'test_to': 'me@bipsu.edu.ph',
                         'user_id': student.id})
        student.refresh_from_db()
        self.assertEqual(student.verification_status, 'pending')

    def test_a_student_cannot_reach_the_panel_or_send_a_test(self):
        self.c.logout()
        User.objects.create_user(username='ana@bipsu.edu.ph', email='ana@bipsu.edu.ph',
                                 password='pw', role='student')
        self.assertTrue(self.c.login(email='ana@bipsu.edu.ph', password='pw'))
        with mock.patch('api.notify.send_mail') as send:
            r = self.c.post('/vpsea/accounts/',
                            {'action': 'test_email', 'test_to': 'me@bipsu.edu.ph'})
        send.assert_not_called()
        self.assertEqual(r.status_code, 302)
        self.assertNotIn('/vpsea/', r['Location'])
