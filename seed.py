import json
import os
from models import db, Client, Category, Product, Order, OrderItem
from flask import Flask
from datetime import datetime

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()

        # Auto-migrate missing columns for existing SQLite database files
        try:
            db.session.execute(db.text("SELECT stock FROM products LIMIT 1"))
        except Exception:
            db.session.rollback()
            try:
                db.session.execute(db.text("ALTER TABLE products ADD COLUMN stock INTEGER NOT NULL DEFAULT 50"))
                db.session.commit()
                print("Migration automatique : colonne 'stock' ajoutée à la table 'products'.")
            except Exception as e:
                print(f"Notice migration : {e}")

        # Check if categories exist
        if Category.query.count() == 0:
            print("Seeding categories...")
            # Main Categories
            fromages_cat = Category(name="Fromages", slug="fromages")
            charcuterie_cat = Category(name="Charcuterie", slug="charcuterie")
            plateaux_cat = Category(name="Plateaux de dégustation", slug="plateaux")
            boissons_cat = Category(name="Boissons", slug="boissons")
            tartinables_cat = Category(name="Tartinables", slug="tartinables")

            db.session.add_all([fromages_cat, charcuterie_cat, plateaux_cat, boissons_cat, tartinables_cat])
            db.session.commit()

            # Sub-categories for Fromages
            cheese_subcats = [
                ("Frais", "frais"),
                ("Pâtes molles", "pates-molles"),
                ("Pâtes dures", "pates-dures"),
                ("Pâtes pressées non cuites", "pates-pressees-non-cuites"),
                ("Pâtes pressées cuites", "pates-pressees-cuites"),
                ("A pâtes fondues", "a-pates-fondues"),
                ("Chèvres et brebis", "chevres-et-brebis"),
                ("Persillés", "persilles")
            ]

            for sub_name, sub_slug in cheese_subcats:
                sub_cat = Category(name=sub_name, slug=sub_slug, parent_id=fromages_cat.id)
                db.session.add(sub_cat)

            db.session.commit()

            # Seed sample cheese products for testing
            frais_cat = Category.query.filter_by(slug="frais").first()
            pates_molles_cat = Category.query.filter_by(slug="pates-molles").first()
            pates_pressees_non_cuites = Category.query.filter_by(slug="pates-pressees-non-cuites").first()
            pates_pressees_cuites = Category.query.filter_by(slug="pates-pressees-cuites").first()
            chevres_cat = Category.query.filter_by(slug="chevres-et-brebis").first()
            persilles_cat = Category.query.filter_by(slug="persilles").first()

            cheese_samples = [
                (frais_cat.id, "Faisselle artisanale", 3.20, 20, "Faisselle fraîche au lait cru"),
                (pates_molles_cat.id, "Camembert de Normandie AOP", 6.80, 15, "Camembert au lait cru moulé à la louche"),
                (pates_molles_cat.id, "Brie de Meaux AOP", 7.50, 10, "Brie de Meaux au lait cru"),
                (pates_pressees_non_cuites.id, "Reblochon de Savoie AOP", 8.20, 12, "Reblochon fermier au lait cru"),
                (pates_pressees_cuites.id, "Comté AOP 18 mois", 9.50, 25, "Comté affiné 18 mois d'alpage"),
                (pates_pressees_cuites.id, "Beaufort d'été AOP", 11.00, 8, "Beaufort fabriqué en alpage"),
                (chevres_cat.id, "Crottin de Chavignol AOP", 3.80, 18, "Fromage de chèvre affiné"),
                (persilles_cat.id, "Roquefort AOP", 7.90, 14, "Roquefort de tradition")
            ]

            for cat_id, p_name, p_price, p_stock, p_desc in cheese_samples:
                if cat_id:
                    db.session.add(Product(category_id=cat_id, name=p_name, price=p_price, stock=p_stock, description=p_desc))

            db.session.commit()

            # Load scraped products from JSON
            if os.path.exists("scraped_products.json"):
                with open("scraped_products.json", "r", encoding="utf-8") as f:
                    scraped_data = json.load(f)

                cat_map = {
                    "Charcuterie": charcuterie_cat.id,
                    "Plateaux de dégustation": plateaux_cat.id,
                    "Boissons": boissons_cat.id,
                    "Tartinables": tartinables_cat.id
                }

                for cat_name, products in scraped_data.items():
                    target_cat_id = cat_map.get(cat_name)
                    if target_cat_id:
                        for item in products:
                            p = Product(
                                category_id=target_cat_id,
                                name=item["name"],
                                price=item["price"],
                                description=item["description"],
                                image_url=item["image_url"]
                            )
                            db.session.add(p)
                db.session.commit()
                print("Scraped products seeded.")

        # Check if admin user exists
        if Client.query.filter_by(username="admin").first() is None:
            admin_user = Client(
                nom="Les Tepuys",
                prenom="Admin",
                email="contact@lestepuys.com",
                telephone="0102030405",
                adresse="1 Place de la Fromagerie",
                code_postal="75001",
                ville="Paris",
                username="admin",
                is_admin=True
            )
            admin_user.set_password("admin123")
            db.session.add(admin_user)
            db.session.commit()
            print("Admin user created.")

        # Seed sample demo clients
        client1 = Client.query.filter_by(email="alice.martin@example.com").first()
        if not client1:
            client1 = Client(
                nom="Martin", prenom="Alice", email="alice.martin@example.com",
                telephone="0611223344", adresse="12 Rue des Fromages", code_postal="75002",
                ville="Paris", username="amartin"
            )
            client1.set_password("password123")
            db.session.add(client1)

        client2 = Client.query.filter_by(email="jean.dupont@example.com").first()
        if not client2:
            client2 = Client(
                nom="Dupont", prenom="Jean", email="jean.dupont@example.com",
                telephone="0612345678", adresse="45 Avenue de la République", code_postal="69002",
                ville="Lyon", username="jdupont"
            )
            client2.set_password("password123")
            db.session.add(client2)

        client3 = Client.query.filter_by(email="michel.chausson@gmail.com").first()
        if not client3:
            client3 = Client(
                nom="CHAUSSON", prenom="Michel", email="michel.chausson@gmail.com",
                telephone="0612345678", adresse="8 Boulevard Haussmann", code_postal="75009",
                ville="Paris", username="mchausson"
            )
            client3.set_password("password123")
            db.session.add(client3)

        db.session.commit()

        # Seed sample demo orders if none exist
        if Order.query.count() == 0:
            print("Seeding sample demo orders...")
            camembert = Product.query.filter_by(name="Camembert de Normandie AOP").first()
            brie = Product.query.filter_by(name="Brie de Meaux AOP").first()
            beaufort = Product.query.filter_by(name="Beaufort d'été AOP").first()
            crottin = Product.query.filter_by(name="Crottin de Chavignol AOP").first()
            comte = Product.query.filter_by(name="Comté AOP 18 mois").first()

            demo_orders = [
                {
                    "client": client1,
                    "method": "Virement bancaire",
                    "status": "Payé",
                    "items": [(camembert, 1)] if camembert else []
                },
                {
                    "client": client1,
                    "method": "Paiement à la livraison",
                    "status": "En attente de paiement à la livraison",
                    "items": [(camembert, 1)] if camembert else []
                },
                {
                    "client": client2,
                    "method": "Paiement à la livraison",
                    "status": "En attente de paiement à la livraison",
                    "items": [(camembert, 1), (beaufort, 1)] if camembert and beaufort else []
                },
                {
                    "client": client1,
                    "method": "Virement bancaire",
                    "status": "Payé",
                    "items": [(camembert, 1)] if camembert else []
                },
                {
                    "client": client1,
                    "method": "Paiement à la livraison",
                    "status": "En attente de paiement à la livraison",
                    "items": [(camembert, 1)] if camembert else []
                },
                {
                    "client": client2,
                    "method": "Paiement à la livraison",
                    "status": "En attente de paiement à la livraison",
                    "items": [(camembert, 1), (beaufort, 1)] if camembert and beaufort else []
                },
                {
                    "client": client3,
                    "method": "Paiement à la livraison",
                    "status": "En attente de paiement à la livraison",
                    "items": [(camembert, 1), (brie, 1), (beaufort, 1), (crottin, 3)] if camembert and brie and beaufort and crottin else []
                }
            ]

            for ord_info in demo_orders:
                c = ord_info["client"]
                if not ord_info["items"]:
                    continue
                total = sum(p.price * q for p, q in ord_info["items"])
                recap = f"Commande pour {c.prenom} {c.nom}\nMode de paiement: {ord_info['method']}\nTotal: {total:.2f} €"
                order = Order(
                    client_id=c.id,
                    total_price=total,
                    payment_method=ord_info["method"],
                    payment_status=ord_info["status"],
                    recap_file=recap
                )
                db.session.add(order)
                db.session.commit()

                for p, q in ord_info["items"]:
                    item = OrderItem(
                        order_id=order.id,
                        product_id=p.id,
                        product_name=p.name,
                        unit_price=p.price,
                        quantity=q
                    )
                    db.session.add(item)
                db.session.commit()

            print("Sample demo orders seeded.")

if __name__ == "__main__":
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lestepuys.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    init_db(app)
    print("Database successfully initialized.")
