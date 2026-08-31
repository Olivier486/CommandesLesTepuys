import urllib.request
import urllib.parse
import http.cookiejar
import threading
import time
from app import app

BASE_URL = "http://127.0.0.1:5000"

def test_admin_orders():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Try accessing admin page without login -> redirect to login
    req = urllib.request.Request(f"{BASE_URL}/admin/orders")
    res = opener.open(req)
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "Connexion" in html or "Se connecter" in html
    print("Unauthenticated access redirected to login.")

    # 2. Login as regular user -> try accessing admin page -> access denied redirect to products
    login_user = urllib.parse.urlencode({"username": "amartin", "password": "mypassword123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/login", data=login_user, method="POST")
    res = opener.open(req)

    req = urllib.request.Request(f"{BASE_URL}/admin/orders")
    res = opener.open(req)
    html = res.read().decode('utf-8')
    assert "Accès réservé" in html or "Tous nos Produits" in html
    print("Regular user denied access to admin interface.")

    # 3. Login as admin user -> access admin page successfully
    opener.open(f"{BASE_URL}/logout")

    login_admin = urllib.parse.urlencode({"username": "admin", "password": "admin123"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/login", data=login_admin, method="POST")
    res = opener.open(req)

    req = urllib.request.Request(f"{BASE_URL}/admin/orders")
    res = opener.open(req)
    html = res.read().decode('utf-8')
    assert "Espace Fromagerie" in html
    assert "Détail de la Commande" in html or "Marquer comme Payé" in html
    print("Admin access granted & order list rendered successfully.")

    # 4. Test updating order status to 'Payé'
    update_data = urllib.parse.urlencode({"payment_status": "Payé"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/admin/orders/2/update-status", data=update_data, method="POST")
    res = opener.open(req)
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "Le statut de la commande" in html or "mis à jour" in html
    print("Admin payment status update verified.")

if __name__ == "__main__":
    server_thread = threading.Thread(target=app.run, kwargs={'port': 5000, 'use_reloader': False})
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1.5)

    try:
        test_admin_orders()
        print("--- Admin Orders Tests Passed! ---")
    except Exception as e:
        print(f"Admin orders test failed: {e}")
        exit(1)
