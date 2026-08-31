from flask import Flask
from models import db, Client, Category, Product, Order, OrderItem

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lestepuys.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

with app.app_context():
    print("--- Database Verification ---")
    clients_count = Client.query.count()
    categories_count = Category.query.count()
    products_count = Product.query.count()
    orders_count = Order.query.count()

    print(f"Clients count: {clients_count}")
    print(f"Categories count: {categories_count}")
    print(f"Products count: {products_count}")
    print(f"Orders count: {orders_count}")

    # Check admin user
    admin = Client.query.filter_by(username="admin").first()
    assert admin is not None and admin.is_admin, "Admin user check failed!"
    print(f"Admin verified: {admin.username} ({admin.email})")

    # Check cheese category and subcategories
    fromages = Category.query.filter_by(slug="fromages").first()
    assert fromages is not None, "Fromages main category missing!"
    subcats = Category.query.filter_by(parent_id=fromages.id).all()
    print(f"Cheese subcategories ({len(subcats)}): {[s.name for s in subcats]}")
    assert len(subcats) == 8, f"Expected 8 cheese subcategories, got {len(subcats)}"

    # Check scraped product categories
    charcuterie = Category.query.filter_by(slug="charcuterie").first()
    charcuterie_prods = Product.query.filter_by(category_id=charcuterie.id).count()
    print(f"Charcuterie products count: {charcuterie_prods}")
    assert charcuterie_prods > 0, "Charcuterie products missing!"

    print("--- All Database Checks Passed Successfully! ---")
