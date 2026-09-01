import unittest
from app import app, db, Client, Category, Product, Order

class TestEvolutions(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

        with app.app_context():
            self.admin = Client.query.filter_by(username='admin').first()
            self.p = Product.query.first()

    def test_evols_flow(self):
        # 1. Login as Admin
        res = self.client.post('/login', data={'username': 'admin', 'password': 'admin123'}, follow_redirects=True)
        self.assertIn(b'Espace Fromagerie', res.data)

        # 2. Check Admin Products route
        res = self.client.get('/admin/products')
        self.assertEqual(res.status_code, 200)

        # 3. Update Product Stock
        res = self.client.post(f'/admin/products/{self.p.id}/update', data={'price': '10.50', 'stock': '20'}, follow_redirects=True)
        self.assertIn(b'mis \xc3\xa0 jour', res.data)

        # 4. Check Restock Alert route (stock <= 5)
        res = self.client.get('/admin/restock')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Alerte de stock', res.data)

        # 5. Check Admin Payments route & CSV Export
        res = self.client.get('/admin/payments')
        self.assertEqual(res.status_code, 200)

        res_csv = self.client.get('/admin/payments/export')
        self.assertEqual(res_csv.status_code, 200)
        self.assertEqual(res_csv.mimetype, 'text/csv')

if __name__ == '__main__':
    unittest.main()
