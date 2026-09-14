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

    def test_email_token_reset_flow(self):
        # 1. Login with incorrect password
        res_login_fail = self.app.post('/login', data={'username': 'testuser', 'password': 'wrongpassword'})
        self.assertEqual(res_login_fail.status_code, 200)
        self.assertIn(b'Mot de passe erron', res_login_fail.data)
        self.assertIn(b'R\xc3\xa9initialiser par email', res_login_fail.data)

        # 2. Request email reset token on /forgot-password
        res_forgot = self.app.post('/forgot-password', data={'email': 'test.client@example.com'}, follow_redirects=True)
        self.assertEqual(res_forgot.status_code, 200)
        self.assertIn(b'Un lien de r\xc3\xa9initialisation vous a \xc3\xa9t\xc3\xa9 envoy\xc3\xa9 par email', res_forgot.data)

        with app.app_context():
            client = db.session.get(Client, self.client_id)
            self.assertIsNotNone(client.reset_token)
            self.assertIsNotNone(client.reset_token_expiration)
            token = client.reset_token

        # 3. Fail reset with invalid token
        res_invalid_token = self.app.get('/reset-password?token=invalidtoken123', follow_redirects=True)
        self.assertIn(b'Le lien de r\xc3\xa9initialisation est invalide', res_invalid_token.data)

        # 4. Succeed reset with valid token
        res_reset_page = self.app.get(f'/reset-password?token={token}')
        self.assertEqual(res_reset_page.status_code, 200)
        self.assertIn(b'Nouveau Mot de Passe', res_reset_page.data)

        res_reset_success = self.app.post('/reset-password', data={
            'token': token,
            'new_password': 'newpassword123',
            'confirm_password': 'newpassword123'
        }, follow_redirects=True)

        self.assertEqual(res_reset_success.status_code, 200)
        self.assertIn(b'r\xc3\xa9initialis\xc3\xa9 avec succ\xc3\xa8s', res_reset_success.data)

        with app.app_context():
            updated_client = db.session.get(Client, self.client_id)
            self.assertIsNone(updated_client.reset_token)
            self.assertIsNone(updated_client.reset_token_expiration)

        # 5. Login with new password
        res_login_new = self.app.post('/login', data={'username': 'testuser', 'password': 'newpassword123'}, follow_redirects=True)
        self.assertEqual(res_login_new.status_code, 200)
        self.assertIn(b'Bienvenue Client !', res_login_new.data)

if __name__ == '__main__':
    unittest.main()
