import os
import json
import smtplib
import csv
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, Response
from models import db, Client, Category, Product, Order, OrderItem, StripePaymentDetail
from seed import init_db
import uuid

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lestepuys-super-secret-key-2025'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///lestepuys.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

init_db(app)

def send_order_confirmation_email(order, client):
    subject = f"Confirmation de votre commande #{order.id} - Fromagerie Les Tepuys"

    if order.payment_status == 'Payé':
        pickup_msg = "Merci de venir récupérer votre commande dans votre fromagerie Les Tepuys, au 5 avenue Thérèse, 94420 Le Plessis-Trévise."
        payment_info = "Votre commande est déjà réglée (Paiement en ligne effectué)."
    else:
        pickup_msg = "Merci de venir régler et récupérer votre commande dans votre fromagerie Les Tepuys, au 5 avenue Thérèse, 94420 Le Plessis-Trévise."
        payment_info = "Votre commande sera à régler lorsque vous viendrez récupérer votre commande."

    items_summary = "\n".join([
        f"  - {item.product_name} x{item.quantity} ({item.unit_price * item.quantity:.2f} €)"
        for item in order.items
    ])

    body = f"""Bonjour {client.prenom},

Nous vous remercions pour votre commande n°#{order.id} auprès de la Fromagerie Les Tepuys !

{payment_info}

{pickup_msg}

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
    low_stock_count = 0
    if 'client_id' in session:
        current_user = Client.query.get(session['client_id'])
        if current_user and current_user.is_admin:
            low_stock_count = Product.query.filter(Product.stock <= 5).count()

    return dict(
        main_categories=main_categories,
        cheese_subcategories=cheese_subcategories,
        cart=cart,
        cart_count=cart_count,
        current_user=current_user,
        low_stock_count=low_stock_count
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
    try:
        quantity = int(request.form.get('quantity', 1))
    except ValueError:
        quantity = 1

    if quantity < 1:
        quantity = 1

    product = Product.query.get(int(product_id))
    if not product:
        flash("Produit introuvable.", "danger")
        return redirect(url_for('products'))

    if product.stock <= 0:
        flash(f"Le produit '{product.name}' est actuellement épuisé / en rupture de stock.", "warning")
        return redirect(request.referrer or url_for('products'))

    cart = session.get('cart', {})
    current_in_cart = cart.get(product_id, {}).get('quantity', 0)
    if current_in_cart + quantity > product.stock:
        flash(f"Désolé, la quantité désirée pour '{product.name}' n'est pas disponible ({product.stock} restant(s) en stock).", "warning")
        return redirect(request.referrer or url_for('products'))

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
            product = Product.query.get(int(product_id))
            if product and quantity > product.stock:
                flash(f"Désolé, la quantité désirée pour '{product.name}' n'est pas disponible ({product.stock} disponible(s)).", "warning")
                return redirect(url_for('view_cart'))
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

    return redirect(request.referrer or url_for('view_cart'))

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
        # Check stock for all cart items before proceeding
        for item in cart_items:
            product_obj = Product.query.get(item['id'])
            if not product_obj or product_obj.stock < item['quantity']:
                avail = product_obj.stock if product_obj else 0
                flash(f"La quantité désirée pour '{item['name']}' n'est pas disponible ({avail} en stock). Veuillez ajuster votre panier.", "danger")
                return redirect(url_for('view_cart'))

        payment_choice = request.form.get('payment_method', 'stripe')
        if payment_choice == 'livraison':
            payment_method = "Paiement à la livraison"
            payment_status = "En attente de paiement à la livraison"
        elif payment_choice == 'stripe':
            payment_method = "Carte bancaire (Stripe)"
            payment_status = "En attente de règlement CB"
        else:
            payment_method = "Virement bancaire"
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

            # Deduct stock
            prod = Product.query.get(item['id'])
            if prod:
                prod.stock = max(0, prod.stock - item['quantity'])

        db.session.commit()

        # If Stripe payment chosen, redirect to Stripe checkout screen before completing email
        if payment_choice == 'stripe':
            session['cart'] = {}
            session.modified = True
            return redirect(url_for('stripe_checkout', order_id=order.id))

        # Send confirmation email for other payment methods
        send_order_confirmation_email(order, client)

        session['cart'] = {}
        session.modified = True

        return redirect(url_for('order_confirmation', order_id=order.id))

    return render_template('checkout.html', current_user=client, cart_items=cart_items, total_amount=total_amount)

@app.route('/stripe/checkout/<int:order_id>')
def stripe_checkout(order_id):
    if 'client_id' not in session:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    if order.client_id != session['client_id']:
        flash("Accès non autorisé à cette commande.", "danger")
        return redirect(url_for('products'))

    client = Client.query.get(order.client_id)
    return render_template('stripe_checkout.html', order=order, current_user=client)

@app.route('/stripe/process/<int:order_id>', methods=['POST'])
def stripe_process(order_id):
    if 'client_id' not in session:
        return redirect(url_for('login'))

    order = Order.query.get_or_404(order_id)
    if order.client_id != session['client_id']:
        flash("Accès non autorisé.", "danger")
        return redirect(url_for('products'))

    card_holder = request.form.get('card_holder', '').strip()
    card_number = request.form.get('card_number', '').replace(' ', '')
    card_exp = request.form.get('card_exp', '').strip()
    card_cvc = request.form.get('card_cvc', '').strip()

    if not card_holder or len(card_number) < 12 or not card_exp or not card_cvc:
        flash("Veuillez saisir des coordonnées bancaires valides.", "danger")
        return redirect(url_for('stripe_checkout', order_id=order.id))

    last4 = card_number[-4:] if len(card_number) >= 4 else "4242"
    stripe_charge_id = f"ch_{uuid.uuid4().hex[:16]}"

    # Record Stripe transaction
    payment_detail = StripePaymentDetail(
        order_id=order.id,
        stripe_payment_id=stripe_charge_id,
        card_holder=card_holder,
        card_brand="Visa/CB",
        last4=last4,
        amount=order.total_price,
        status="succeeded"
    )

    order.payment_status = "Payé"
    order.payment_method = "Carte bancaire (Stripe)"

    db.session.add(payment_detail)
    db.session.commit()

    # Send order confirmation email
    client = Client.query.get(order.client_id)
    send_order_confirmation_email(order, client)

    flash("Paiement par carte bancaire validé avec succès !", "success")
    return redirect(url_for('order_confirmation', order_id=order.id))

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
    new_method = request.form.get('payment_method', '').strip()

    order.payment_status = new_status
    if new_method:
        order.payment_method = new_method

    db.session.commit()
    flash(f"Le statut de la commande #{order.id} a été mis à jour : '{new_status}' ({order.payment_method}).", "success")
    return redirect(request.referrer or url_for('admin_orders'))

@app.route('/admin/payments')
@admin_required
def admin_payments():
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    query = Order.query.filter(Order.payment_status == 'Payé')

    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Order.created_at >= start_dt)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Order.created_at <= end_dt)
        except ValueError:
            pass

    paid_orders = query.order_by(Order.created_at.desc()).all()
    total_paid_amount = sum(o.total_price for o in paid_orders)

    return render_template(
        'admin_payments.html',
        orders=paid_orders,
        total_paid_amount=total_paid_amount,
        start_date=start_date_str,
        end_date=end_date_str
    )

@app.route('/admin/payments/export')
@admin_required
def export_payments_csv():
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()

    query = Order.query.filter(Order.payment_status == 'Payé')

    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(Order.created_at >= start_dt)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_dt = datetime.strptime(end_date_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
            query = query.filter(Order.created_at <= end_dt)
        except ValueError:
            pass

    paid_orders = query.order_by(Order.created_at.desc()).all()

    si = StringIO()
    cw = csv.writer(si, delimiter=';')
    cw.writerow(['Numéro Commande', 'Date', 'Nom Client', 'Prénom Client', 'Email', 'Téléphone', 'Montant Payé (€)', 'Mode de Paiement'])

    for order in paid_orders:
        cw.writerow([
            order.id,
            order.created_at.strftime('%d/%m/%Y %H:%M'),
            order.client.nom,
            order.client.prenom,
            order.client.email,
            order.client.telephone,
            f"{order.total_price:.2f}",
            order.payment_method
        ])

    output = si.getvalue().encode('utf-8-sig')
    filename = f"export_paiements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        output,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment;filename={filename}"}
    )

@app.route('/admin/products')
@admin_required
def admin_products():
    categories = Category.query.all()
    products_list = Product.query.order_by(Product.name.asc()).all()
    return render_template('admin_products.html', products=products_list, categories=categories)

@app.route('/admin/products/<int:product_id>/update', methods=['POST'])
@admin_required
def update_product_stock(product_id):
    product = Product.query.get_or_404(product_id)
    try:
        new_price = float(request.form.get('price', product.price))
        new_stock = int(request.form.get('stock', product.stock))
        if new_price >= 0 and new_stock >= 0:
            product.price = new_price
            product.stock = new_stock
            db.session.commit()
            flash(f"Produit '{product.name}' mis à jour : Prix = {new_price:.2f}€, Stock = {new_stock} unités.", "success")
        else:
            flash("Le prix et le stock doivent être des valeurs positives.", "danger")
    except ValueError:
        flash("Valeurs invalides transmises.", "danger")

    return redirect(request.referrer or url_for('admin_products'))

@app.route('/admin/restock')
@admin_required
def admin_restock():
    low_stock_products = Product.query.filter(Product.stock <= 5).order_by(Product.stock.asc()).all()
    return render_template('admin_restock.html', products=low_stock_products)

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
