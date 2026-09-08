import unittest
from app import app
from models import db, Client, Category, Product

class DestockTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
        app.config['WTF_CSRF_ENABLED'] = False
        self.app = app.test_client()

        with app.app_context():
            db.drop_all()
            db.create_all()

            # Admin user
            admin = Client(
                nom="Admin", prenom="User", email="admin@test.com",
                telephone="0102030405", adresse="1 Admin St", code_postal="75000",
                ville="Paris", username="admin", is_admin=True
            )
            admin.set_password("admin123")
            db.session.add(admin)

            # Category
            cat = Category(name="Fromages", slug="fromages")
            db.session.add(cat)
            db.session.commit()

            # Product
            p = Product(category_id=cat.id, name="Morbier AOP", price=8.50, stock=20, is_active=True)
            db.session.add(p)
            db.session.commit()

            self.admin_id = admin.id
            self.product_id = p.id
            self.category_id = cat.id

    def test_add_and_toggle_destock(self):
        # Login admin
        self.app.post('/login', data={'username': 'admin', 'password': 'admin123'})

        # 1. Add new product
        res = self.app.post('/admin/products/add', data={
            'category_id': self.category_id,
            'name': 'Abondance AOP',
            'price': '9.80',
            'stock': '15',
            'description': 'Fromage de Savoie'
        }, follow_redirects=True)

        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Abondance AOP', res.data)

        with app.app_context():
            p_new = Product.query.filter_by(name='Abondance AOP').first()
            self.assertIsNotNone(p_new)
            self.assertTrue(p_new.is_active)

        # 2. Check catalog display (both items present)
        res_cat = self.app.get('/products')
        self.assertIn(b'Morbier AOP', res_cat.data)
        self.assertIn(b'Abondance AOP', res_cat.data)

        # 3. Destock Morbier
        res_destock = self.app.post(f'/admin/products/{self.product_id}/toggle-active', follow_redirects=True)
        self.assertEqual(res_destock.status_code, 200)

        with app.app_context():
            p_morbier = db.session.get(Product, self.product_id)
            self.assertFalse(p_morbier.is_active)

        # 4. Check catalog display (Morbier hidden, Abondance shown)
        res_cat_after = self.app.get('/products')
        self.assertNotIn(b'Morbier AOP', res_cat_after.data)
        self.assertIn(b'Abondance AOP', res_cat_after.data)

        # 5. Re-stock Morbier
        self.app.post(f'/admin/products/{self.product_id}/toggle-active', follow_redirects=True)
        with app.app_context():
            p_morbier = db.session.get(Product, self.product_id)
            self.assertTrue(p_morbier.is_active)

        res_cat_restored = self.app.get('/products')
        self.assertIn(b'Morbier AOP', res_cat_restored.data)

if __name__ == '__main__':
    unittest.main()
