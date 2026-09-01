import os
import json
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, Client, Category, Product, Order, OrderItem
from seed import init_db

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lestepuys-super-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lestepuys.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

def send_order_confirmation_email(order, client):
    subject = f"Confirmation de votre commande #{order.id} - Fromagerie Les Tepuys"

    if order.payment_status == 'Payé':
        payment_info = "Votre commande est déjà réglée (Paiement en ligne effectué)."
    else:
        payment_info = "Votre commande sera à régler lorsque vous viendrez récupérer votre commande."

    items_summary = "\n".join([
        f"  - {item.product_name} x{item.quantity} ({item.unit_price * item.quantity:.2f} €)"
        for item in order.items
    ])

    body = f"""Bonjour {client.prenom},

Nous vous remercions pour votre commande n°#{order.id} auprès de la Fromagerie Les Tepuys !

{payment_info}

--- Récapitulatif de votre commande ---
{items_summary}

Total TTC : {order.total_price:.2f} €
Mode de paiement : {order.payment_method}
Statut du paiement : {order.payment_status}

Coordonnées :
{client.prenom} {client.nom}
{client.adresse}, {client.code_postal} {client.ville}
Téléphone : {client.telephone}

À très bientôt,
L'équipe Fromagerie Les Tepuys
https://www.lestepuys.com
"""

    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER')
    smtp_password = os.environ.get('SMTP_PASSWORD')

    if smtp_server and smtp_user and smtp_password:
        try:
            msg = MIMEMultipart()
            msg['From'] = smtp_user
            msg['To'] = client.email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            server = smtplib.SMTP(smtp_server, int(smtp_port))
            server.starttls()
            server.login(smtp_user, smtp_password)
            server.sendmail(smtp_user, client.email, msg.as_string())
            server.quit()
            print(f"Email de confirmation envoyé à {client.email}")
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email : {e}")
    else:
        print(f"--- [SIMULATION EMAIL] Envoyé à {client.email} ---\n{body}\n----------------------------------")

    return body

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'client_id' not in session:
            flash("Veuillez vous connecter en tant qu'administrateur de la fromagerie.", "warning")
            return redirect(url_for('login', next=request.url))
        client = Client.query.get(session['client_id'])
        if not client or not client.is_admin:
            flash("Accès réservé uniquement à la Fromagerie.", "danger")
            return redirect(url_for('products'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_global_data():
    main_categories = Category.query.filter_by(parent_id=None).all()
    fromages_cat = Category.query.filter_by(slug="fromages").first()
    cheese_subcategories = []
    if fromages_cat:
        cheese_subcategories = Category.query.filter_by(parent_id=fromages_cat.id).all()

    cart = session.get('cart', {})
    cart_count = sum(item['quantity'] for item in cart.values())

    current_user = None
    if 'client_id' in session:
        current_user = Client.query.get(session['client_id'])

    return dict(
        main_categories=main_categories,
        cheese_subcategories=cheese_subcategories,
        cart_count=cart_count,
        current_user=current_user
    )

@app.route('/')
def index():
    return redirect(url_for('products'))

@app.route('/products')
def products():
    cat_slug = request.args.get('cat', '').strip()
    current_category = None
    is_cheese_category = False

    fromages_cat = Category.query.filter_by(slug="fromages").first()
    cheese_sub_ids = []
    if fromages_cat:
        subcats = Category.query.filter_by(parent_id=fromages_cat.id).all()
        cheese_sub_ids = [sc.id for sc in subcats]

    if cat_slug:
        current_category = Category.query.filter_by(slug=cat_slug).first()
        if current_category:
            if current_category.slug == 'fromages' or current_category.parent_id == (fromages_cat.id if fromages_cat else None):
                is_cheese_category = True

            if current_category.slug == 'fromages':
                products_list = Product.query.filter(
                    (Product.category_id == current_category.id) | (Product.category_id.in_(cheese_sub_ids))
                ).all()
            else:
                products_list = Product.query.filter_by(category_id=current_category.id).all()
        else:
            products_list = Product.query.all()
    else:
        products_list = Product.query.all()

    return render_template(
        'products.html',
        products=products_list,
        current_category=current_category,
        is_cheese_category=is_cheese_category or (not cat_slug)
    )

@app.route('/cart/add', methods=['POST'])
def add_to_cart():
    product_id = str(request.form.get('product_id'))
    quantity = int(request.form.get('quantity', 1))

    if quantity < 1:
        quantity = 1

    product = Product.query.get(int(product_id))
    if not product:
        flash("Produit introuvable.", "danger")
        return redirect(url_for('products'))

    cart = session.get('cart', {})
    if product_id in cart:
        cart[product_id]['quantity'] += quantity
    else:
        cart[product_id] = {
            'id': product.id,
            'name': product.name,
            'price': product.price,
            'quantity': quantity
        }

    session['cart'] = cart
    session.modified = True
    flash(f"'{product.name}' a été ajouté à votre panier.", "success")
    return redirect(request.referrer or url_for('products'))

@app.route('/cart')
def view_cart():
    cart = session.get('cart', {})
    cart_items = []
    total_amount = 0.0
    total_items_count = 0

    for item_id, item_data in cart.items():
        subtotal = item_data['price'] * item_data['quantity']
        total_amount += subtotal
        total_items_count += item_data['quantity']
        cart_items.append({
            'id': item_data['id'],
            'name': item_data['name'],
            'price': item_data['price'],
            'quantity': item_data['quantity'],
            'subtotal': subtotal
        })

    return render_template(
        'cart.html',
        cart_items=cart_items,
        total_amount=total_amount,
        total_items_count=total_items_count
    )

@app.route('/cart/update', methods=['POST'])
def update_cart():
    product_id = str(request.form.get('product_id'))
    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        quantity = 1

    cart = session.get('cart', {})
    if product_id in cart:
        if quantity <= 0:
            del cart[product_id]
            flash("Produit retiré du panier.", "info")
        else:
            cart[product_id]['quantity'] = quantity
            flash("Panier mis à jour.", "success")

        session['cart'] = cart
        session.modified = True

    return redirect(url_for('view_cart'))

@app.route('/cart/remove/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    str_pid = str(product_id)
    cart = session.get('cart', {})
    if str_pid in cart:
        removed_name = cart[str_pid]['name']
        del cart[str_pid]
        session['cart'] = cart
        session.modified = True
        flash(f"'{removed_name}' a été retiré de votre panier.", "info")

    return redirect(url_for('view_cart'))

@app.route('/cart/clear', methods=['POST'])
def clear_cart():
    session['cart'] = {}
    session.modified = True
    flash("Votre panier a été vidé.", "info")
    return redirect(url_for('view_cart'))

@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'client_id' not in session:
        flash("Veuillez vous connecter pour valider votre commande.", "warning")
        return redirect(url_for('login', next=url_for('checkout')))

    client = Client.query.get(session['client_id'])
    cart = session.get('cart', {})

    if not cart:
        flash("Votre panier est vide.", "warning")
        return redirect(url_for('products'))

    cart_items = []
    total_amount = 0.0
    for item_id, item_data in cart.items():
        subtotal = item_data['price'] * item_data['quantity']
        total_amount += subtotal
        cart_items.append({
            'id': item_data['id'],
            'name': item_data['name'],
            'price': item_data['price'],
            'quantity': item_data['quantity'],
            'subtotal': subtotal
        })

    if request.method == 'POST':
        payment_choice = request.form.get('payment_method', 'virement')
        if payment_choice == 'livraison':
            payment_method = "Paiement à la livraison"
            payment_status = "En attente de paiement à la livraison"
        else:
            payment_method = "Virement bancaire / PayPal"
            payment_status = "Payé"

        now_str = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        recap_lines = [
            f"=== BON DE COMMANDE - FROMAGERIE LES TEPUYS ===",
            f"Date: {now_str}",
            f"Client: {client.prenom} {client.nom}",
            f"Email: {client.email} | Tel: {client.telephone}",
            f"Adresse: {client.adresse}, {client.code_postal} {client.ville}",
            f"Mode de Paiement: {payment_method}",
            f"Statut Paiement: {payment_status}",
            f"-----------------------------------------------",
            f"PRODUITS COMMANDÉS:"
        ]

        for item in cart_items:
            recap_lines.append(f"  - {item['name']} x{item['quantity']} @ {item['price']:.2f}€ = {item['subtotal']:.2f}€")

        recap_lines.append(f"-----------------------------------------------")
        recap_lines.append(f"TOTAL COMMANDE TTC: {total_amount:.2f} €")
        recap_lines.append(f"===============================================")

        recap_file_text = "\n".join(recap_lines)

        order = Order(
            client_id=client.id,
            total_price=total_amount,
            payment_method=payment_method,
            payment_status=payment_status,
            recap_file=recap_file_text
        )

        db.session.add(order)
        db.session.flush()

        for item in cart_items:
            order_item = OrderItem(
                order_id=order.id,
                product_id=item['id'],
                product_name=item['name'],
                unit_price=item['price'],
                quantity=item['quantity']
            )
            db.session.add(order_item)

        db.session.commit()

        # Send confirmation email
        send_order_confirmation_email(order, client)

        session['cart'] = {}
        session.modified = True

        return redirect(url_for('order_confirmation', order_id=order.id))

    return render_template('checkout.html', current_user=client, cart_items=cart_items, total_amount=total_amount)

@app.route('/order/confirmation/<int:order_id>')
def order_confirmation(order_id):
    if 'client_id' not in session:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    if order.client_id != session['client_id'] and not session.get('is_admin'):
        flash("Accès non autorisé à cette commande.", "danger")
        return redirect(url_for('products'))

    return render_template('order_confirmation.html', order=order)

@app.route('/admin/orders')
@admin_required
def admin_orders():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    return render_template('admin_orders.html', orders=orders)

@app.route('/admin/orders/<int:order_id>/update-status', methods=['POST'])
@admin_required
def update_order_status(order_id):
    order = Order.query.get_or_404(order_id)
    new_status = request.form.get('payment_status', 'Payé').strip()
    order.payment_status = new_status
    db.session.commit()
    flash(f"Le statut de la commande #{order.id} a été mis à jour avec succès : '{new_status}'.", "success")
    return redirect(url_for('admin_orders'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nom = request.form.get('nom', '').strip()
        prenom = request.form.get('prenom', '').strip()
        email = request.form.get('email', '').strip()
        telephone = request.form.get('telephone', '').strip()
        adresse = request.form.get('adresse', '').strip()
        code_postal = request.form.get('code_postal', '').strip()
        ville = request.form.get('ville', '').strip()
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not all([nom, prenom, email, telephone, adresse, code_postal, ville, username, password]):
            flash("Veuillez remplir tous les champs obligatoires.", "danger")
            return render_template('register.html')

        if Client.query.filter_by(email=email).first():
            flash("Cette adresse email est déjà utilisée.", "danger")
            return render_template('register.html')

        if Client.query.filter_by(username=username).first():
            flash("Ce nom d'utilisateur est déjà pris.", "danger")
            return render_template('register.html')

        client = Client(
            nom=nom,
            prenom=prenom,
            email=email,
            telephone=telephone,
            adresse=adresse,
            code_postal=code_postal,
            ville=ville,
            username=username
        )
        client.set_password(password)
        db.session.add(client)
        db.session.commit()

        flash("Inscription réussie ! Vous pouvez maintenant vous connecter.", "success")
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        client = Client.query.filter_by(username=username).first()
        if client and client.check_password(password):
            session['client_id'] = client.id
            session['username'] = client.username
            session['is_admin'] = client.is_admin
            flash(f"Bienvenue {client.prenom} !", "success")

            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if client.is_admin:
                return redirect(url_for('admin_orders'))
            return redirect(url_for('products'))
        else:
            flash("Nom d'utilisateur ou mot de passe incorrect.", "danger")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('client_id', None)
    session.pop('username', None)
    session.pop('is_admin', None)
    flash("Vous avez été déconnecté.", "info")
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)
