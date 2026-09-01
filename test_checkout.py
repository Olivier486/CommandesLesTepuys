import urllib.request
import urllib.parse
import http.cookiejar
import threading
import time
from app import app, send_order_confirmation_email, Client, Order

BASE_URL = "http://127.0.0.1:5000"

def test_email_function():
    with app.app_context():
        client = Client.query.filter_by(username="amartin").first()
        order_paid = Order.query.filter_by(payment_status="Payé").first()
        order_delivery = Order.query.filter_by(payment_status="En attente de paiement à la livraison").first()

        if client and order_paid:
            email_paid = send_order_confirmation_email(order_paid, client)
            assert f"Bonjour {client.prenom}," in email_paid
            assert "déjà réglée" in email_paid or "déjà payée" in email_paid
            print("Email test for online payment OK.")

        if client and order_delivery:
            email_del = send_order_confirmation_email(order_delivery, client)
            assert f"Bonjour {client.prenom}," in email_del
            assert "sera à régler" in email_del
            print("Email test for payment on delivery OK.")

def test_checkout():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Login user
    login_data = urllib.parse.urlencode({"username": "amartin", "password": "mypassword123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method="POST")
    res = opener.open(req)
    assert res.status == 200

    # 2. Add product to cart
    add_data = urllib.parse.urlencode({"product_id": "1", "quantity": "2"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/cart/add", data=add_data, method="POST")
    res = opener.open(req)
    assert res.status == 200

    # 3. Checkout with online payment
    chk_data = urllib.parse.urlencode({"payment_method": "virement"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/checkout", data=chk_data, method="POST")
    res = opener.open(req)
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "Merci ! Votre commande" in html
    assert "BON DE COMMANDE" in html
    print("Checkout with online payment successful.")

    # 4. Add another product to cart and checkout with payment on delivery
    add_data2 = urllib.parse.urlencode({"product_id": "2", "quantity": "1"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/cart/add", data=add_data2, method="POST")
    res = opener.open(req)

    chk_data2 = urllib.parse.urlencode({"payment_method": "livraison"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/checkout", data=chk_data2, method="POST")
    res = opener.open(req)
    assert res.status == 200
    html2 = res.read().decode('utf-8')
    assert "Paiement à la livraison" in html2
    print("Checkout with payment on delivery successful.")

if __name__ == "__main__":
    test_email_function()

    server_thread = threading.Thread(target=app.run, kwargs={'port': 5000, 'use_reloader': False})
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1.5)

    try:
        test_checkout()
        print("--- Checkout Tests Passed! ---")
    except Exception as e:
        print(f"Checkout test failed: {e}")
        exit(1)
