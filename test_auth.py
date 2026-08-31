import urllib.request
import urllib.parse
import json
import http.cookiejar

BASE_URL = "http://127.0.0.1:5000"

def test_auth():
    cj = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

    # 1. Register a new user
    reg_data = urllib.parse.urlencode({
        "nom": "Martin",
        "prenom": "Alice",
        "email": "alice.martin@example.com",
        "telephone": "0611223344",
        "adresse": "10 Rue des Fromages",
        "code_postal": "69001",
        "ville": "Lyon",
        "username": "amartin",
        "password": "mypassword123"
    }).encode('utf-8')

    print("Registering new user...")
    req = urllib.request.Request(f"{BASE_URL}/register", data=reg_data, method="POST")
    res = opener.open(req)
    assert res.status == 200, f"Register failed with status {res.status}"
    print("Registration HTTP 200")

    # 2. Login with new user
    login_data = urllib.parse.urlencode({
        "username": "amartin",
        "password": "mypassword123"
    }).encode('utf-8')

    print("Logging in...")
    req = urllib.request.Request(f"{BASE_URL}/login", data=login_data, method="POST")
    res = opener.open(req)
    assert res.status == 200, f"Login failed with status {res.status}"
    content = res.read().decode('utf-8')
    assert "Products" in content or "Alice" in content, "Login redirect missing!"
    print("Login successful! User authenticated.")

    # 3. Logout
    print("Logging out...")
    res = opener.open(f"{BASE_URL}/logout")
    assert res.status == 200
    print("Logged out successfully.")

if __name__ == "__main__":
    import threading
    import time
    from app import app

    server_thread = threading.Thread(target=app.run, kwargs={'port': 5000, 'use_reloader': False})
    server_thread.daemon = True
    server_thread.start()
    time.sleep(1.5)

    try:
        test_auth()
        print("--- Authentication Tests Passed! ---")
    except Exception as e:
        print(f"Auth test failed: {e}")
        exit(1)
