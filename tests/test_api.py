"""Run:  python -m unittest discover tests -v"""
import os, sys, tempfile, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["FLIPCART_DB"] = os.path.join(tempfile.mkdtemp(), "test.db")

import database
database.DB_PATH = os.environ["FLIPCART_DB"]
import app as flipcart


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        database.init_db()
        cls.c = flipcart.app.test_client()

    def call(self, method, url, token=None, **kw):
        h = {"Authorization": "Bearer " + token} if token else {}
        r = getattr(self.c, method)(url, headers=h, **kw)
        return r.status_code, r.get_json()

    def signup(self, email="a@b.com"):
        code, d = self.call("post", "/api/auth/signup", json={"name": "Asha K", "email": email, "password": "pass1"})
        self.assertEqual(code, 201)
        return d["token"]

    def test_01_search(self):
        for q, expect in [("shoes", "Sneakers"), ("phones", "Smartphone"), ("laptops", "Laptop"),
                          ("electric devices", "Laptop"), ("tv", "TV"), ("books", "Atomic")]:
            _, rows = self.call("get", "/api/products?q=" + q)
            self.assertTrue(any(expect in r["name"] for r in rows), q)
        _, rows = self.call("get", "/api/products?category=fashion&sort=price_asc&max_price=1000")
        self.assertTrue(all(r["price"] <= 1000 for r in rows) and rows == sorted(rows, key=lambda r: r["price"]))
        _, s = self.call("get", "/api/suggest?q=lap")
        self.assertTrue(s)

    def test_02_auth_rules(self):
        self.assertEqual(self.call("get", "/api/cart")[0], 401)
        self.assertEqual(self.call("post", "/api/auth/login", json={"email": "x@y.com", "password": "no"})[0], 401)
        tok = self.signup("dup@b.com")
        code, _ = self.call("post", "/api/auth/signup", json={"name": "x", "email": "dup@b.com", "password": "pass1"})
        self.assertEqual(code, 409)
        self.assertEqual(self.call("get", "/api/admin/stats", tok)[0], 403)

    def test_03_full_order_flow(self):
        tok = self.signup("flow@b.com")
        _, p = self.call("get", "/api/products?q=sneakers")
        pid = p[0]["id"]
        code, cart = self.call("post", "/api/cart", tok, json={"productId": pid, "quantity": 2})
        self.assertEqual((code, cart["count"], cart["subtotal"]), (201, 2, 2199 * 2))
        _, cart = self.call("get", "/api/cart?promo=FIRST50", tok)
        self.assertEqual(cart["coupon"], 150)  # 50% capped at 150
        self.assertEqual(cart["delivery"], 0)
        # cannot order without an address
        self.assertEqual(self.call("post", "/api/orders", tok, json={"payment_method": "COD"})[0], 400)
        code, addr = self.call("post", "/api/addresses", tok, json={
            "name": "Asha", "phone": "9876543210", "pincode": "132103", "line1": "12 Model Town",
            "city": "Panipat", "state": "Haryana"})
        self.assertEqual(code, 201)
        stock_before = self.call("get", f"/api/products/{pid}")[1]["stock"]
        code, order = self.call("post", "/api/orders", tok, json={"address_id": addr["id"], "payment_method": "COD", "promo": "FIRST50"})
        self.assertEqual(code, 201)
        self.assertEqual(order["total"], 2199 * 2 - 150)
        self.assertEqual(order["status"], "PLACED")
        self.assertEqual(self.call("get", "/api/cart", tok)[1]["count"], 0)  # cart emptied
        self.assertEqual(self.call("get", f"/api/products/{pid}")[1]["stock"], stock_before - 2)
        # admin moves the order forward
        _, a = self.call("post", "/api/auth/login", json={"email": "admin@flipcart.com", "password": "admin123"})
        adm = a["token"]
        code, o = self.call("patch", f"/api/admin/orders/{order['id']}/status", adm, json={"status": "SHIPPED"})
        self.assertEqual((code, o["status"], o["can_cancel"]), (200, "SHIPPED", False))
        self.assertEqual(self.call("post", f"/api/orders/{order['id']}/cancel", tok)[0], 400)
        self.assertEqual(self.call("get", "/api/admin/stats", adm)[1]["orders"] >= 1, True)

    def test_04_cancel_restocks(self):
        tok = self.signup("cancel@b.com")
        _, p = self.call("get", "/api/products?q=teddy")
        pid = p[0]["id"]
        before = p[0]["stock"]
        self.call("post", "/api/cart", tok, json={"productId": pid})
        _, addr = self.call("post", "/api/addresses", tok, json={"name": "A", "phone": "9876543210", "pincode": "110001",
                                                                "line1": "x", "city": "Delhi", "state": "Delhi"})
        _, o = self.call("post", "/api/orders", tok, json={"address_id": addr["id"], "payment_method": "UPI", "payment": {"upi_id": "asha@okhdfcbank"}})
        self.assertEqual(o["payment_status"], "PAID")
        self.assertTrue(o["payment_ref"].startswith("TXN"))
        self.assertEqual(o["payment_detail"], "UPI a***@okhdfcbank")
        code, c = self.call("post", f"/api/orders/{o['id']}/cancel", tok)
        self.assertEqual((code, c["status"], c["payment_status"]), (200, "CANCELLED", "REFUNDED"))
        self.assertEqual(self.call("get", f"/api/products/{pid}")[1]["stock"], before)

    def test_05_stock_limit_and_review(self):
        tok = self.signup("rev@b.com")
        _, p = self.call("get", "/api/products?q=camera")
        code, _ = self.call("post", "/api/cart", tok, json={"productId": p[0]["id"], "quantity": 10 ** 6})
        self.assertEqual(code, 400)
        code, r = self.call("post", f"/api/products/{p[0]['id']}/reviews", tok, json={"rating": 5, "comment": "Great"})
        self.assertEqual(code, 201)
        self.assertEqual(self.call("get", f"/api/products/{p[0]['id']}")[1]["reviews"][0]["comment"], "Great")

    def test_06_admin_product(self):
        _, a = self.call("post", "/api/auth/login", json={"email": "admin@flipcart.com", "password": "admin123"})
        code, prod = self.call("post", "/api/admin/products", a["token"], json={
            "name": "Test Gadget", "category": "electronics", "price": 500, "mrp": 800, "stock": 5})
        self.assertEqual(code, 201)
        code, upd = self.call("patch", f"/api/admin/products/{prod['id']}", a["token"], json={"stock": 50})
        self.assertEqual(upd["stock"], 50)

    def test_07_admin_only_moves_forward(self):
        tok = self.signup("fwd@b.com")
        _, p = self.call("get", "/api/products?q=teddy")
        self.call("post", "/api/cart", tok, json={"productId": p[0]["id"]})
        _, addr = self.call("post", "/api/addresses", tok, json={"name": "A", "phone": "9876543210", "pincode": "110001",
                                                                "line1": "x", "city": "Delhi", "state": "Delhi"})
        _, o = self.call("post", "/api/orders", tok, json={"address_id": addr["id"], "payment_method": "COD"})
        adm = self.call("post", "/api/auth/login", json={"email": "admin@flipcart.com", "password": "admin123"})[1]["token"]
        self.assertEqual(self.call("patch", f"/api/admin/orders/{o['id']}/status", adm, json={"status": "SHIPPED"})[0], 200)
        self.assertEqual(self.call("patch", f"/api/admin/orders/{o['id']}/status", adm, json={"status": "PLACED"})[0], 400)

    def test_08_stock_never_negative(self):
        tok = self.signup("race@b.com")
        _, p = self.call("get", "/api/products?q=teddy")
        pid = p[0]["id"]
        self.call("post", "/api/cart", tok, json={"productId": pid, "quantity": 2})
        _, addr = self.call("post", "/api/addresses", tok, json={"name": "A", "phone": "9876543210", "pincode": "110001",
                                                                "line1": "x", "city": "Delhi", "state": "Delhi"})
        # someone else buys almost everything after this cart was filled
        import database as dbm
        c = dbm.connect(); c.execute("UPDATE products SET stock=1 WHERE id=?", (pid,)); c.commit(); c.close()
        code, r = self.call("post", "/api/orders", tok, json={"address_id": addr["id"], "payment_method": "COD"})
        self.assertEqual(code, 400)
        self.assertEqual(self.call("get", f"/api/products/{pid}")[1]["stock"], 1)
        self.assertEqual(self.call("get", "/api/orders", tok)[1], [])  # nothing half-saved

    def test_09_login_rate_limit_and_expiry(self):
        tok = self.signup("brute@b.com")
        for _ in range(8):
            self.assertEqual(self.call("post", "/api/auth/login", json={"email": "brute@b.com", "password": "bad"})[0], 401)
        self.assertEqual(self.call("post", "/api/auth/login", json={"email": "brute@b.com", "password": "pass1"})[0], 429)
        import database as dbm
        c = dbm.connect(); c.execute("UPDATE sessions SET created_at=datetime('now','-31 days') WHERE token=?", (tok,)); c.commit(); c.close()
        self.assertEqual(self.call("get", "/api/auth/me", tok)[0], 401)


class PaymentTests(unittest.TestCase):
    def setUp(self):
        self.c = flipcart.app.test_client()

    def call(self, method, url, token=None, **kw):
        h = {"Authorization": "Bearer " + token} if token else {}
        r = getattr(self.c, method)(url, headers=h, **kw)
        return r.status_code, r.get_json()

    def ready(self, email):
        _, d = self.call("post", "/api/auth/signup", json={"name": "Pay T", "email": email, "password": "pass1"})
        tok = d["token"]
        _, p = self.call("get", "/api/products?q=psychology")
        self.call("post", "/api/cart", tok, json={"productId": p[0]["id"]})
        _, addr = self.call("post", "/api/addresses", tok, json={"name": "A", "phone": "9876543210", "pincode": "110001",
                                                                "line1": "x", "city": "Delhi", "state": "Delhi"})
        return tok, addr["id"], p[0]["id"]

    def pay(self, tok, aid, method, payment=None):
        return self.call("post", "/api/orders", tok, json={"address_id": aid, "payment_method": method, "payment": payment or {}})

    def test_card_success_masks_number(self):
        tok, aid, _ = self.ready("c1@t.com")
        code, o = self.pay(tok, aid, "CARD", {"card_number": "4111 1111 1111 1111", "card_name": "A B", "expiry": "12/40", "cvv": "123"})
        self.assertEqual(code, 201)
        self.assertEqual(o["payment_detail"], "Visa •••• 1111")
        self.assertNotIn("4111111111111111", str(o))
        import database as dbm
        c = dbm.connect()
        row = c.execute("SELECT status, reference, detail FROM payments WHERE order_id=?", (o["id"],)).fetchone()
        c.close()
        self.assertEqual(row["status"], "SUCCESS")

    def test_declined_card_creates_no_order_and_keeps_cart(self):
        tok, aid, pid = self.ready("c2@t.com")
        code, r = self.pay(tok, aid, "CARD", {"card_number": "4000000000000002", "card_name": "A", "expiry": "12/40", "cvv": "123"})
        self.assertEqual(code, 402)
        self.assertEqual(self.call("get", "/api/orders", tok)[1], [])
        self.assertEqual(self.call("get", "/api/cart", tok)[1]["count"], 1)
        import database as dbm
        c = dbm.connect(); n = c.execute("SELECT COUNT(*) FROM payments WHERE status='FAILED'").fetchone()[0]; c.close()
        self.assertGreaterEqual(n, 1)

    def test_validation_errors(self):
        tok, aid, _ = self.ready("c3@t.com")
        bad = [("CARD", {"card_number": "4111111111111112", "card_name": "A", "expiry": "12/40", "cvv": "123"}),   # luhn
               ("CARD", {"card_number": "4111111111111111", "card_name": "A", "expiry": "01/20", "cvv": "123"}),   # expired
               ("CARD", {"card_number": "4111111111111111", "card_name": "A", "expiry": "12/40", "cvv": "12"}),    # cvv
               ("UPI", {"upi_id": "nonsense"}), ("NETBANKING", {})]
        for method, payload in bad:
            self.assertEqual(self.pay(tok, aid, method, payload)[0], 400, (method, payload))
        self.assertEqual(self.pay(tok, aid, "UPI", {"upi_id": "fail@upi"})[0], 402)
        self.assertEqual(self.pay(tok, aid, "NETBANKING", {"bank": "State Bank of India"})[0], 402)

    def test_netbanking_and_cod_then_refund_note(self):
        tok, aid, _ = self.ready("c4@t.com")
        code, o = self.pay(tok, aid, "NETBANKING", {"bank": "HDFC Bank"})
        self.assertEqual((code, o["payment_status"]), (201, "PAID"))
        _, c = self.call("post", f"/api/orders/{o['id']}/cancel", tok)
        self.assertEqual(c["payment_status"], "REFUNDED")
        self.assertIn("refund", c["events"][-1]["note"].lower())
        tok2, aid2, _ = self.ready("c5@t.com")
        code, o2 = self.pay(tok2, aid2, "COD")
        self.assertEqual((code, o2["payment_status"]), (201, "PENDING"))


class AdminPasswordSync(unittest.TestCase):
    def test_old_db_gets_new_admin_password(self):
        import database as dbm
        from werkzeug.security import check_password_hash
        dbm.ADMIN_PASSWORD = "Brand-New-Pass1"
        try:
            dbm.init_db()
            c = dbm.connect()
            h = c.execute("SELECT password_hash FROM users WHERE email='admin@flipcart.com'").fetchone()[0]
            c.close()
            self.assertTrue(check_password_hash(h, "Brand-New-Pass1"))
            self.assertFalse(check_password_hash(h, "admin123"))
        finally:
            dbm.ADMIN_PASSWORD = None
            c = dbm.connect(); c.execute("UPDATE users SET password_hash=? WHERE email='admin@flipcart.com'",
                                         (dbm.generate_password_hash("admin123"),)); c.commit(); c.close()


if __name__ == "__main__":
    unittest.main()
