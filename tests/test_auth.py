import os
import unittest
from unittest.mock import Mock, patch
from services import api, sign_up


class AuthTests(unittest.TestCase):
    def test_email_delivery_error_is_actionable_and_redacted(self):
        response = Mock(ok=False, status_code=400)
        response.json.return_value = {
            'error_code': 'email_address_not_authorized',
            'msg': 'private response content must not appear',
        }
        with patch.dict(os.environ, {'SUPABASE_URL': 'https://example.supabase.co', 'SUPABASE_KEY': 'test'}), patch('services.requests.request', return_value=response):
            with self.assertRaisesRegex(ValueError, 'custom SMTP') as error:
                api('POST', '/auth/v1/signup')
            self.assertNotIn('private response', str(error.exception))

    def test_short_password_does_not_send_request(self):
        with patch('services.api') as request:
            with self.assertRaisesRegex(ValueError, 'at least 6'):
                sign_up('student@example.com', '123')
            request.assert_not_called()

    def test_successful_signup_returns_session(self):
        with patch('services.api', return_value={'access_token': 'test-session'}):
            self.assertEqual(sign_up('student@example.com', 'test-password')['access_token'], 'test-session')
