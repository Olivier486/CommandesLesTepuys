import json
import os
from models import db, Client, Category, Product
from flask import Flask

def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all()

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
            # Frais, Pâtes molles, Pâtes dures, Pâtes Pressées non cuites, Pâtes Pressées cuites, A pâtes fondues, Chèvres et brebis, Persillés
            cheese_subcats = [
                ("Frais", "frais"),
                ("Pâtes molles", "pates-molles"),
                ("Pâtes dures", "pates-dures"),
                ("Pâtes Pressées non cuites", "pates-pressees-non-cuites"),
                ("Pâtes Pressées cuites", "pates-pressees-cuites"),
                ("A pâtes fondues", "a-pates-fondues"),
                ("Chèvres et brebis", "chevres-et-brebis"),
                ("Persillés", "persilles")
            ]

            for sub_name, sub_slug in cheese_subcats:
                sub_cat = Category(name=sub_name, slug=sub_slug, parent_id=fromages_cat.id)
                db.session.add(sub_cat)

            db.session.commit()

            # Seed sample cheese products for testing (user can load full inventory later)
            frais_cat = Category.query.filter_by(slug="frais").first()
            pates_molles_cat = Category.query.filter_by(slug="pates-molles").first()
            pates_pressees_non_cuites = Category.query.filter_by(slug="pates-pressees-non-cuites").first()
            pates_pressees_cuites = Category.query.filter_by(slug="pates-pressees-cuites").first()
            chevres_cat = Category.query.filter_by(slug="chevres-et-brebis").first()
            persilles_cat = Category.query.filter_by(slug="persilles").first()

            cheese_samples = [
                (frais_cat.id, "Faisselle artisanale", 3.20, "Faisselle fraîche au lait cru"),
                (pates_molles_cat.id, "Camembert de Normandie AOP", 6.80, "Camembert au lait cru moulé à la louche"),
                (pates_molles_cat.id, "Brie de Meaux AOP", 7.50, "Brie de Meaux au lait cru"),
                (pates_pressees_non_cuites.id, "Reblochon de Savoie AOP", 8.20, "Reblochon fermier au lait cru"),
                (pates_pressees_cuites.id, "Comté AOP 18 mois", 9.50, "Comté affiné 18 mois d'alpage"),
                (pates_pressees_cuites.id, "Beaufort d'été AOP", 11.00, "Beaufort fabriqué en alpage"),
                (chevres_cat.id, "Crottin de Chavignol AOP", 3.80, "Fromage de chèvre affiné"),
                (persilles_cat.id, "Roquefort AOP", 7.90, "Roquefort de tradition")
            ]

            for cat_id, p_name, p_price, p_desc in cheese_samples:
                if cat_id:
                    db.session.add(Product(category_id=cat_id, name=p_name, price=p_price, description=p_desc))

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

if __name__ == "__main__":
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lestepuys.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    init_db(app)
    print("Database successfully initialized.")
