import unittest
from app import app
from models import db, Client, Product, Order, StripePaymentDetail

class StripePaymentTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Create client
            client = Client(
                nom="Test", prenom="StripeUser", email="stripe.user@example.com",
                telephone="0600000000", adresse="10 Rue Test", code_postal="75000",
                ville="Paris", username="stripeuser"
            )
            client.set_password("password")
            db.session.add(client)

            # Create product
            product = Product(category_id=1, name="Test Cheese", price=10.0, stock=20)
            db.session.add(product)
            db.session.commit()

            self.client_id = client.id
            self.product_id = product.id

    def test_stripe_checkout_flow(self):
        # Login
        self.app.post('/login', data={'username': 'stripeuser', 'password': 'password'})

        # Add item to cart
        self.app.post('/cart/add', data={'product_id': self.product_id, 'quantity': 2})

        # Submit checkout with Stripe payment
        res = self.app.post('/checkout', data={'payment_method': 'stripe'}, follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn('/stripe/checkout/', res.location)

        order_id = int(res.location.split('/')[-1])

        with app.app_context():
            order = db.session.get(Order, order_id)
            self.assertIsNotNone(order)
            self.assertEqual(order.payment_status, 'En attente de règlement CB')

        # Visit Stripe checkout page
        res_stripe_page = self.app.get(f'/stripe/checkout/{order_id}')
        self.assertEqual(res_stripe_page.status_code, 200)
        self.assertIn(b'Paiement S\xc3\xa9curis\xc3\xa9 Stripe', res_stripe_page.data)

        # Process Stripe payment
        res_process = self.app.post(f'/stripe/process/{order_id}', data={
            'card_holder': 'StripeUser Test',
            'card_number': '4242 4242 4242 4242',
            'card_exp': '12/28',
            'card_cvc': '123'
        }, follow_redirects=True)

        self.assertEqual(res_process.status_code, 200)
        self.assertIn(b'Paiement par carte bancaire valid\xc3\xa9', res_process.data)

        with app.app_context():
            updated_order = db.session.get(Order, order_id)
            self.assertEqual(updated_order.payment_status, 'Payé')
            self.assertEqual(updated_order.payment_method, 'Carte bancaire (Stripe)')

            stripe_detail = StripePaymentDetail.query.filter_by(order_id=order_id).first()
            self.assertIsNotNone(stripe_detail)
            self.assertEqual(stripe_detail.last4, '4242')
            self.assertEqual(stripe_detail.card_holder, 'StripeUser Test')
            self.assertEqual(stripe_detail.amount, 20.0)

    def test_email_messages_address(self):
        from app import send_order_confirmation_email

        with app.app_context():
            client = db.session.get(Client, self.client_id)

            paid_order = Order(client_id=client.id, total_price=20.0, payment_method='Stripe', payment_status='Payé', recap_file='')
            unpaid_order = Order(client_id=client.id, total_price=20.0, payment_method='Livraison', payment_status='En attente', recap_file='')

            body_paid = send_order_confirmation_email(paid_order, client)
            self.assertIn("Merci de venir récupérer votre commande dans votre fromagerie Les Tepuys, au 5 avenue Thérèse, 94420 Le Plessis-Trévise.", body_paid)

            body_unpaid = send_order_confirmation_email(unpaid_order, client)
            self.assertIn("Merci de venir régler et récupérer votre commande dans votre fromagerie Les Tepuys, au 5 avenue Thérèse, 94420 Le Plessis-Trévise.", body_unpaid)

if __name__ == '__main__':
    unittest.main()
