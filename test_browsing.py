import urllib.request
import threading
import time
from app import app

BASE_URL = "http://127.0.0.1:5000"

def test_browsing():
    # 1. Fetch all products page
    req = urllib.request.Request(f"{BASE_URL}/products")
    res = urllib.request.urlopen(req)
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "Tous nos Produits" in html or "Fromages" in html
    print("Main products browsing OK")

    # 2. Filter by cheese subcategory 'pates-molles'
    req = urllib.request.Request(f"{BASE_URL}/products?cat=pates-molles")
    res = urllib.request.urlopen(req)
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "Camembert de Normandie" in html or "Pâtes molles" in html
    print("Subcategory 'Pâtes molles' browsing OK")

    # 3. Filter by charcuterie
    req = urllib.request.Request(f"{BASE_URL}/products?cat=charcuterie")
    res = urllib.request.urlopen(req)
    assert res.status == 200
    html = res.read().decode('utf-8')
    assert "Fuet" in html or "Charcuterie" in html
    print("Category 'Charcuterie' browsing OK")

if __name__ == "__main__":
    server_thread = threading.Thread(target=app.run, kwargs={'port': 5000, 'use_reloader': False})
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1.5)

    try:
        test_browsing()
        print("--- Navigation & Browsing Tests Passed! ---")
    except Exception as e:
        print(f"Browsing test failed: {e}")
        exit(1)
