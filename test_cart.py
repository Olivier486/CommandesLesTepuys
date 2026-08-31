import urllib.request
import urllib.parse
import http.cookiejar
import threading
import time
from app import app

BASE_URL = "http://127.0.0.1:5000"

def test_cart():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Add item 1 (product id 1 - Faisselle artisanale)
    add_data = urllib.parse.urlencode({"product_id": "1", "quantity": "2"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/cart/add", data=add_data, method="POST")
    res = opener.open(req)
    assert res.status == 200

    # 2. Add item 2 (product id 2 - Camembert)
    add_data2 = urllib.parse.urlencode({"product_id": "2", "quantity": "1"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/cart/add", data=add_data2, method="POST")
    res = opener.open(req)
    assert res.status == 200

    # 3. View cart
    res = opener.open(f"{BASE_URL}/cart")
    html = res.read().decode('utf-8')
    assert "Faisselle artisanale" in html
    assert "Camembert de Normandie" in html
    print("Items present in cart.")

    # 4. Update quantity of product 1 to 5
    update_data = urllib.parse.urlencode({"product_id": "1", "quantity": "5"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/cart/update", data=update_data, method="POST")
    res = opener.open(req)
    assert res.status == 200

    # Verify updated quantity
    res = opener.open(f"{BASE_URL}/cart")
    html = res.read().decode('utf-8')
    assert 'value="5"' in html
    print("Quantity update verified.")

    # 5. Remove product 2
    req = urllib.request.Request(f"{BASE_URL}/cart/remove/2", method="POST")
    res = opener.open(req)
    assert res.status == 200

    # Verify removal
    res = opener.open(f"{BASE_URL}/cart")
    html = res.read().decode('utf-8')
    assert "Camembert de Normandie" not in html
    assert "Faisselle artisanale" in html
    print("Item removal verified.")

if __name__ == "__main__":
    server_thread = threading.Thread(target=app.run, kwargs={'port': 5000, 'use_reloader': False})
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1.5)

    try:
        test_cart()
        print("--- Cart Persistence & Management Tests Passed! ---")
    except Exception as e:
        print(f"Cart test failed: {e}")
        exit(1)
