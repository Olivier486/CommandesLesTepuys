import unittest
from app import app
from models import db, Client

class ResetPasswordTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()

            client = Client(
                nom="Test", prenom="Client", email="test.client@example.com",
                telephone="0611223344", adresse="1 Rue Test", code_postal="75000",
                ville="Paris", username="testuser"
            )
            client.set_password("oldpassword")
            db.session.add(client)
            db.session.commit()
            self.client_id = client.id

    def test_wrong_password_prompt_and_sms_reset(self):
        # 1. Login with incorrect password
        res_login_fail = self.app.post('/login', data={'username': 'testuser', 'password': 'wrongpassword'})
        self.assertEqual(res_login_fail.status_code, 200)
        self.assertIn(b'Mot de passe erron', res_login_fail.data)
        self.assertIn(b'R\xc3\xa9initialiser par SMS', res_login_fail.data)

        # 2. Request SMS code on /forgot-password
        res_forgot = self.app.post('/forgot-password', data={'identifier': 'testuser'}, follow_redirects=True)
        self.assertEqual(res_forgot.status_code, 200)
        self.assertIn(b'Code SMS de confirmation', res_forgot.data)

        with self.app.session_transaction() as sess:
            sms_code = sess.get('reset_sms_code')
            self.assertIsNotNone(sms_code)
            self.assertEqual(len(sms_code), 4)

        # 3. Fail reset with invalid code
        res_reset_fail = self.app.post('/reset-password', data={
            'sms_code': '0000',
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        })
        self.assertIn(b'Code SMS \xc3\xa0 4 chiffres incorrect', res_reset_fail.data)

        # 4. Succeed reset with valid 4-digit code
        res_reset_success = self.app.post('/reset-password', data={
            'sms_code': sms_code,
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, follow_redirects=True)

        self.assertEqual(res_reset_success.status_code, 200)
        self.assertIn(b'r\xc3\xa9initialis\xc3\xa9 avec succ\xc3\xa8s', res_reset_success.data)

        # 5. Login with new password
        res_login_new = self.app.post('/login', data={'username': 'testuser', 'password': 'newpassword123'}, follow_redirects=True)
        self.assertEqual(res_login_new.status_code, 200)
        self.assertIn(b'Bienvenue Client !', res_login_new.data)

if __name__ == '__main__':
    unittest.main()
