"""Flipcart – Flask REST API (Python backend)

Run:  python app.py      ->  http://localhost:8000
"""
import os
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from functools import wraps

from flask import Flask, g, jsonify, request
from werkzeug.security import check_password_hash, generate_password_hash

import database
import payments
from database import STATUSES, connect, init_db, make_svg, write_image

app = Flask(__name__, static_folder="public", static_url_path="")
app.json.ensure_ascii = False

PAYMENT_METHODS = {"COD": "Cash on Delivery", "UPI": "UPI", "CARD": "Credit / Debit Card", "NETBANKING": "Net Banking"}
CANCELLABLE = ("PLACED", "PACKED")
STATUS_NOTES = {
    "PLACED": "Order placed",
    "PACKED": "Seller has packed your item",
    "SHIPPED": "Item shipped – on its way",
    "OUT_FOR_DELIVERY": "Out for delivery",
    "DELIVERED": "Delivered",
    "CANCELLED": "Order cancelled",
}


# ------------------------------------------------------------------ helpers
def db():
    if "db" not in g:
        g.db = connect()
    return g.db


@app.after_request
def add_cors(resp):
    """Lets pages opened straight from disk (file://) talk to the API on localhost."""
    origin = request.headers.get("Origin", "")
    if origin == "null" or origin.startswith(("http://localhost", "http://127.0.0.1")):
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, PATCH, DELETE, OPTIONS"
        resp.headers["Vary"] = "Origin"
    return resp


@app.get("/api/health")
def health():
    # demo_admin lets the login page show the demo credentials only on local/demo installs
    return jsonify({"ok": True, "demo_admin": database.USING_DEFAULT_ADMIN})


@app.teardown_appcontext
def close_db(_exc):
    conn = g.pop("db", None)
    if conn:
        conn.close()


def fail(message, code=400):
    resp = jsonify({"error": message})
    resp.status_code = code
    return resp


def current_user():
    header = request.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else None
    if not token:
        return None
    return db().execute(
        "SELECT u.id,u.name,u.email,u.is_admin FROM sessions s JOIN users u ON u.id=s.user_id "
        "WHERE s.token=? AND s.created_at > datetime('now','-30 days')",
        (token,),
    ).fetchone(), token


def login_required(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        found = current_user()
        if not found or not found[0]:
            return fail("Please log in first", 401)
        g.user, g.token = found
        return fn(*a, **kw)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    @login_required
    def wrapper(*a, **kw):
        if not g.user["is_admin"]:
            return fail("Admin access only", 403)
        return fn(*a, **kw)
    return wrapper


def body():
    return request.get_json(silent=True) or {}


def user_dict(u):
    return {"id": u["id"], "name": u["name"], "email": u["email"], "is_admin": bool(u["is_admin"])}


def new_session(user_id):
    token = secrets.token_hex(32)
    db().execute("INSERT INTO sessions (token,user_id) VALUES (?,?)", (token, user_id))
    db().commit()
    return token


FAILED_LOGINS = {}  # "ip|email" -> timestamps of recent failures (in-memory, per process)


def login_blocked(key):
    now = time.time()
    recent = [t for t in FAILED_LOGINS.get(key, []) if now - t < 600]
    FAILED_LOGINS[key] = recent
    return len(recent) >= 8


EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


# --------------------------------------------------------------------- auth
@app.post("/api/auth/signup")
def signup():
    d = body()
    name, email, pw = (d.get("name") or "").strip(), (d.get("email") or "").strip().lower(), d.get("password") or ""
    if not name:
        return fail("Name is required")
    if not EMAIL_RE.match(email):
        return fail("Enter a valid email")
    if len(pw) < 4:
        return fail("Password must be at least 4 characters")
    if db().execute("SELECT 1 FROM users WHERE email=?", (email,)).fetchone():
        return fail("An account with this email already exists", 409)
    cur = db().execute("INSERT INTO users (name,email,password_hash) VALUES (?,?,?)",
                       (name, email, generate_password_hash(pw)))
    db().commit()
    user = db().execute("SELECT * FROM users WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify({"token": new_session(user["id"]), "user": user_dict(user)}), 201


@app.post("/api/auth/login")
def login():
    d = body()
    email = (d.get("email") or "").strip().lower()
    key = f"{request.remote_addr}|{email}"
    if login_blocked(key):
        return fail("Too many failed attempts. Please try again in 10 minutes.", 429)
    user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], d.get("password") or ""):
        FAILED_LOGINS.setdefault(key, []).append(time.time())
        return fail("Incorrect email or password", 401)
    FAILED_LOGINS.pop(key, None)
    return jsonify({"token": new_session(user["id"]), "user": user_dict(user)})


@app.get("/api/auth/me")
@login_required
def me():
    return jsonify({"user": user_dict(g.user)})


@app.post("/api/auth/logout")
@login_required
def logout():
    db().execute("DELETE FROM sessions WHERE token=?", (g.token,))
    db().commit()
    return jsonify({"ok": True})


# ----------------------------------------------------------------- catalogue
def stem(word):
    w = re.sub(r"[^a-z0-9]", "", word.lower())
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 4 and re.search(r"(ch|sh|x|ss|z)es$", w):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


STOP = {"and", "the", "for", "with", "in", "of", "a", "an", "to", "item", "items", "product", "products"}

PRODUCT_SELECT = """SELECT p.id,p.name,p.description,p.price,p.mrp,p.rating,p.rating_count,p.image,p.stock,
       c.slug AS category, c.name AS category_name,
       CAST(ROUND((p.mrp-p.price)*100.0/p.mrp) AS INTEGER) AS discount
  FROM products p JOIN categories c ON c.id=p.category_id"""

SORTS = {
    "relevance": "p.rating_count DESC",
    "price_asc": "p.price ASC",
    "price_desc": "p.price DESC",
    "rating": "p.rating DESC, p.rating_count DESC",
    "newest": "p.id DESC",
    "discount": "(p.mrp-p.price)*1.0/p.mrp DESC",
}


@app.get("/api/categories")
def categories():
    rows = db().execute("SELECT slug,name,icon FROM categories ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/api/products")
def products():
    a = request.args
    tokens = [t for t in (stem(w) for w in (a.get("q") or "").split()) if t and t not in STOP]

    def run(joiner):
        where, args = [], []
        if a.get("category") and a["category"] != "all":
            where.append("c.slug=?"); args.append(a["category"])
        if a.get("min_price", "").isdigit():
            where.append("p.price>=?"); args.append(int(a["min_price"]))
        if a.get("max_price", "").isdigit():
            where.append("p.price<=?"); args.append(int(a["max_price"]))
        try:
            if a.get("rating"):
                where.append("p.rating>=?"); args.append(float(a["rating"]))
        except ValueError:
            pass
        if tokens:
            one = "(p.name LIKE ? OR p.description LIKE ? OR p.keywords LIKE ? OR c.name LIKE ?)"
            where.append("(" + joiner.join([one] * len(tokens)) + ")")
            for t in tokens:
                args += [f"%{t}%"] * 4
        sql = PRODUCT_SELECT + (" WHERE " + " AND ".join(where) if where else "")
        sql += " ORDER BY " + SORTS.get(a.get("sort"), SORTS["relevance"])
        if a.get("limit", "").isdigit():
            sql += f" LIMIT {int(a['limit'])}"
        return db().execute(sql, args).fetchall()

    rows = run(" AND ")
    if not rows and len(tokens) > 1:
        rows = run(" OR ")
    return jsonify([dict(r) for r in rows])


@app.get("/api/suggest")
def suggest():
    q = (request.args.get("q") or "").strip()
    if len(q) < 2:
        return jsonify([])
    t = f"%{stem(q.split()[0]) if len(q.split()) == 1 else q}%"
    names = db().execute(
        "SELECT name FROM products WHERE name LIKE ? OR keywords LIKE ? ORDER BY rating_count DESC LIMIT 6", (t, t)
    ).fetchall()
    cats = db().execute("SELECT slug,name FROM categories WHERE name LIKE ? LIMIT 2", (t,)).fetchall()
    out = [{"type": "category", "label": c["name"], "slug": c["slug"]} for c in cats]
    out += [{"type": "product", "label": n["name"]} for n in names]
    return jsonify(out)


@app.get("/api/products/<int:pid>")
def product_detail(pid):
    row = db().execute(PRODUCT_SELECT + " WHERE p.id=?", (pid,)).fetchone()
    if not row:
        return fail("Product not found", 404)
    prod = dict(row)
    prod["reviews"] = [dict(r) for r in db().execute(
        """SELECT r.id,r.rating,r.comment,r.created_at,u.name AS user FROM reviews r
           JOIN users u ON u.id=r.user_id WHERE r.product_id=? ORDER BY r.id DESC LIMIT 20""", (pid,))]
    prod["related"] = [dict(r) for r in db().execute(
        PRODUCT_SELECT + " WHERE c.slug=? AND p.id<>? ORDER BY p.rating_count DESC LIMIT 8", (row["category"], pid))]
    prod["offers"] = [dict(r) for r in db().execute("SELECT code,description FROM promos")]
    return jsonify(prod)


@app.post("/api/products/<int:pid>/reviews")
@login_required
def add_review(pid):
    d = body()
    prod = db().execute("SELECT rating,rating_count FROM products WHERE id=?", (pid,)).fetchone()
    if not prod:
        return fail("Product not found", 404)
    try:
        rating = int(d.get("rating"))
    except (TypeError, ValueError):
        return fail("Choose a rating from 1 to 5")
    if not 1 <= rating <= 5:
        return fail("Choose a rating from 1 to 5")
    db().execute("INSERT INTO reviews (product_id,user_id,rating,comment) VALUES (?,?,?,?)",
                 (pid, g.user["id"], rating, (d.get("comment") or "").strip()[:500]))
    n = prod["rating_count"] or 0
    new_avg = round(((prod["rating"] or 0) * n + rating) / (n + 1), 1)
    db().execute("UPDATE products SET rating=?, rating_count=? WHERE id=?", (new_avg, n + 1, pid))
    db().commit()
    return jsonify({"rating": new_avg, "rating_count": n + 1}), 201


@app.get("/api/payment/options")
def payment_options():
    return jsonify({"banks": payments.BANKS, "methods": PAYMENT_METHODS})


@app.get("/api/delivery")
def delivery_check():
    pin = request.args.get("pincode", "")
    if not re.fullmatch(r"[1-9]\d{5}", pin):
        return fail("Enter a valid 6-digit pincode")
    days = 2 + int(pin[-1]) % 4
    eta = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%a, %d %b")
    return jsonify({"pincode": pin, "days": days, "eta": eta})


# --------------------------------------------------------------------- cart
def build_cart(user_id, promo_code=None):
    items = [dict(r) for r in db().execute(
        """SELECT p.id,p.name,p.price,p.mrp,p.image,p.stock,ci.qty FROM cart_items ci
           JOIN products p ON p.id=ci.product_id WHERE ci.user_id=? ORDER BY ci.rowid""", (user_id,))]
    mrp_total = sum(i["mrp"] * i["qty"] for i in items)
    subtotal = sum(i["price"] * i["qty"] for i in items)
    coupon, code, promo_error = 0, None, None
    if promo_code:
        p = db().execute("SELECT * FROM promos WHERE code=?", (promo_code.strip().upper(),)).fetchone()
        if not p:
            promo_error = "Invalid coupon code"
        elif subtotal < p["min_order"]:
            promo_error = f"Add items worth ₹{p['min_order'] - subtotal} more to use {p['code']}"
        else:
            code = p["code"]
            coupon = min(round(subtotal * p["percent"] / 100), p["max_discount"])
    delivery = 0 if subtotal == 0 or subtotal >= 500 else 40
    total = subtotal - coupon + delivery
    return {
        "items": items, "count": sum(i["qty"] for i in items), "mrp_total": mrp_total, "subtotal": subtotal,
        "discount": mrp_total - subtotal, "coupon": coupon, "coupon_code": code, "delivery": delivery,
        "total": total, "savings": mrp_total - subtotal + coupon, "promoError": promo_error,
    }


@app.get("/api/cart")
@login_required
def get_cart():
    return jsonify(build_cart(g.user["id"], request.args.get("promo")))


@app.post("/api/cart")
@login_required
def add_to_cart():
    d = body()
    try:
        pid, qty = int(d.get("productId")), max(1, int(d.get("quantity") or 1))
    except (TypeError, ValueError):
        return fail("Invalid product")
    prod = db().execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
    if not prod:
        return fail("Product not found", 404)
    cur = db().execute("SELECT qty FROM cart_items WHERE user_id=? AND product_id=?", (g.user["id"], pid)).fetchone()
    new_qty = (cur["qty"] if cur else 0) + qty
    if prod["stock"] < new_qty:
        return fail("Only %d left in stock" % prod["stock"] if prod["stock"] else "Currently out of stock")
    db().execute(
        """INSERT INTO cart_items (user_id,product_id,qty) VALUES (?,?,?)
           ON CONFLICT(user_id,product_id) DO UPDATE SET qty=excluded.qty""", (g.user["id"], pid, new_qty))
    db().commit()
    return jsonify(build_cart(g.user["id"])), 201


@app.patch("/api/cart/<int:pid>")
@login_required
def update_cart(pid):
    d = body()
    try:
        qty = int(d.get("quantity"))
    except (TypeError, ValueError):
        return fail("Invalid quantity")
    if qty < 0:
        return fail("Invalid quantity")
    if qty == 0:
        db().execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?", (g.user["id"], pid))
    else:
        prod = db().execute("SELECT stock FROM products WHERE id=?", (pid,)).fetchone()
        if prod and qty > prod["stock"]:
            return fail("Only %d left in stock" % prod["stock"])
        db().execute("UPDATE cart_items SET qty=? WHERE user_id=? AND product_id=?", (qty, g.user["id"], pid))
    db().commit()
    return jsonify(build_cart(g.user["id"], d.get("promo")))


@app.delete("/api/cart/<int:pid>")
@login_required
def remove_from_cart(pid):
    db().execute("DELETE FROM cart_items WHERE user_id=? AND product_id=?", (g.user["id"], pid))
    db().commit()
    return jsonify(build_cart(g.user["id"], request.args.get("promo")))


# ---------------------------------------------------------------- addresses
@app.get("/api/addresses")
@login_required
def list_addresses():
    rows = db().execute("SELECT * FROM addresses WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    return jsonify([dict(r) for r in rows])


@app.post("/api/addresses")
@login_required
def add_address():
    d = body()
    f = {k: (d.get(k) or "").strip() for k in ("name", "phone", "pincode", "line1", "city", "state")}
    if not all(f.values()):
        return fail("Please fill in all address fields")
    if not re.fullmatch(r"\d{10}", f["phone"]):
        return fail("Enter a valid 10-digit mobile number")
    if not re.fullmatch(r"[1-9]\d{5}", f["pincode"]):
        return fail("Enter a valid 6-digit pincode")
    kind = d.get("kind") if d.get("kind") in ("Home", "Work") else "Home"
    cur = db().execute(
        "INSERT INTO addresses (user_id,name,phone,pincode,line1,city,state,kind) VALUES (?,?,?,?,?,?,?,?)",
        (g.user["id"], f["name"], f["phone"], f["pincode"], f["line1"], f["city"], f["state"], kind))
    db().commit()
    return jsonify(dict(db().execute("SELECT * FROM addresses WHERE id=?", (cur.lastrowid,)).fetchone())), 201


@app.delete("/api/addresses/<int:aid>")
@login_required
def delete_address(aid):
    db().execute("DELETE FROM addresses WHERE id=? AND user_id=?", (aid, g.user["id"]))
    db().commit()
    return jsonify({"ok": True})


# ------------------------------------------------------------------- orders
def order_dict(row):
    o = dict(row)
    o["items"] = [dict(r) for r in db().execute("SELECT * FROM order_items WHERE order_id=?", (o["id"],))]
    o["events"] = [dict(r) for r in db().execute(
        "SELECT status,note,created_at FROM order_events WHERE order_id=? ORDER BY id", (o["id"],))]
    created = datetime.strptime(o["created_at"], "%Y-%m-%d %H:%M:%S")
    o["expected_delivery"] = (created + timedelta(days=5)).strftime("%a, %d %b %Y")
    o["can_cancel"] = o["status"] in CANCELLABLE
    o["payment_label"] = PAYMENT_METHODS.get(o["payment_method"], o["payment_method"])
    return o


def log_event(order_id, status, note=None):
    db().execute("INSERT INTO order_events (order_id,status,note) VALUES (?,?,?)",
                 (order_id, status, note or STATUS_NOTES.get(status, "")))


@app.post("/api/orders")
@login_required
def place_order():
    d = body()
    uid = g.user["id"]
    addr = db().execute("SELECT * FROM addresses WHERE id=? AND user_id=?", (d.get("address_id"), uid)).fetchone()
    if not addr:
        return fail("Please select a delivery address")
    method = d.get("payment_method")
    if method not in PAYMENT_METHODS:
        return fail("Please select a payment method")
    cart = build_cart(uid, d.get("promo"))
    if not cart["items"]:
        return fail("Your cart is empty")
    for i in cart["items"]:
        if i["qty"] > i["stock"]:
            return fail(f"'{i['name']}' has only {i['stock']} left in stock")

    # ---- take the payment first; the order is only created if it succeeds ----
    pay = payments.charge(method, cart["total"], d.get("payment"))
    if not pay["ok"] and pay["status"] == 400:
        return fail(pay["error"], 400)               # bad input: nothing is logged or charged
    db().execute(
        "INSERT INTO payments (user_id,method,amount,status,reference,detail,message) VALUES (?,?,?,?,?,?,?)",
        (uid, method, cart["total"], "SUCCESS" if pay["ok"] else "FAILED", pay["ref"], pay["detail"], pay["error"]))
    payment_id = db().execute("SELECT last_insert_rowid()").fetchone()[0]
    if not pay["ok"]:
        db().commit()
        return fail(pay["error"], 402)               # declined: cart and stock untouched

    address_text = f"{addr['line1']}, {addr['city']}, {addr['state']} - {addr['pincode']}"
    cur = db().execute(
        """INSERT INTO orders (user_id,mrp_total,subtotal,discount,coupon,coupon_code,delivery,total,
                               payment_method,payment_status,payment_ref,payment_detail,ship_name,ship_phone,ship_address)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (uid, cart["mrp_total"], cart["subtotal"], cart["discount"], cart["coupon"], cart["coupon_code"],
         cart["delivery"], cart["total"], method, "PENDING" if method == "COD" else "PAID",
         pay["ref"], pay["detail"], addr["name"], addr["phone"], address_text))
    oid = cur.lastrowid
    db().execute("UPDATE payments SET order_id=? WHERE id=?", (oid, payment_id))
    for i in cart["items"]:
        # conditional update = stock can never go negative, even with two buyers at once
        took = db().execute("UPDATE products SET stock=stock-? WHERE id=? AND stock>=?", (i["qty"], i["id"], i["qty"]))
        if took.rowcount == 0:
            db().rollback()
            return fail(f"Sorry, '{i['name']}' just went out of stock. You have not been charged.")
        db().execute("INSERT INTO order_items (order_id,product_id,name,image,price,mrp,qty) VALUES (?,?,?,?,?,?,?)",
                     (oid, i["id"], i["name"], i["image"], i["price"], i["mrp"], i["qty"]))
    log_event(oid, "PLACED")
    db().execute("DELETE FROM cart_items WHERE user_id=?", (uid,))
    db().commit()
    return jsonify(order_dict(db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone())), 201


@app.get("/api/orders")
@login_required
def my_orders():
    rows = db().execute("SELECT * FROM orders WHERE user_id=? ORDER BY id DESC", (g.user["id"],)).fetchall()
    return jsonify([order_dict(r) for r in rows])


@app.get("/api/orders/<int:oid>")
@login_required
def one_order(oid):
    row = db().execute("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, g.user["id"])).fetchone()
    return jsonify(order_dict(row)) if row else fail("Order not found", 404)


@app.post("/api/orders/<int:oid>/cancel")
@login_required
def cancel_order(oid):
    row = db().execute("SELECT * FROM orders WHERE id=? AND user_id=?", (oid, g.user["id"])).fetchone()
    if not row:
        return fail("Order not found", 404)
    if row["status"] not in CANCELLABLE:
        return fail("This order can no longer be cancelled")
    restock_and_cancel(row)
    return jsonify(order_dict(db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()))


def restock_and_cancel(order_row):
    for it in db().execute("SELECT product_id,qty FROM order_items WHERE order_id=?", (order_row["id"],)):
        db().execute("UPDATE products SET stock=stock+? WHERE id=?", (it["qty"], it["product_id"]))
    refund = "REFUNDED" if order_row["payment_status"] == "PAID" else "CANCELLED"
    db().execute("UPDATE orders SET status='CANCELLED', payment_status=? WHERE id=?", (refund, order_row["id"]))
    note = ("Order cancelled – refund of ₹%d initiated to %s" % (order_row["total"], order_row["payment_detail"])
            if refund == "REFUNDED" else None)
    log_event(order_row["id"], "CANCELLED", note)
    db().commit()


# -------------------------------------------------------------------- admin
@app.get("/api/admin/stats")
@admin_required
def admin_stats():
    q = lambda sql: db().execute(sql).fetchone()[0]
    by_status = {r["status"]: r["n"] for r in db().execute("SELECT status, COUNT(*) n FROM orders GROUP BY status")}
    low = [dict(r) for r in db().execute("SELECT id,name,stock FROM products WHERE stock<=10 ORDER BY stock LIMIT 10")]
    top = [dict(r) for r in db().execute(
        """SELECT oi.name, SUM(oi.qty) AS sold FROM order_items oi JOIN orders o ON o.id=oi.order_id
           WHERE o.status<>'CANCELLED' GROUP BY oi.name ORDER BY sold DESC LIMIT 5""")]
    return jsonify({
        "orders": q("SELECT COUNT(*) FROM orders"),
        "revenue": q("SELECT COALESCE(SUM(total),0) FROM orders WHERE status NOT IN ('CANCELLED')"),
        "users": q("SELECT COUNT(*) FROM users WHERE is_admin=0"),
        "products": q("SELECT COUNT(*) FROM products"),
        "by_status": by_status, "low_stock": low, "top_products": top,
    })


@app.get("/api/admin/orders")
@admin_required
def admin_orders():
    rows = db().execute(
        "SELECT o.*, u.name AS customer, u.email FROM orders o JOIN users u ON u.id=o.user_id ORDER BY o.id DESC"
    ).fetchall()
    out = []
    for r in rows:
        o = order_dict(r)
        o["customer"], o["email"] = r["customer"], r["email"]
        out.append(o)
    return jsonify(out)


@app.patch("/api/admin/orders/<int:oid>/status")
@admin_required
def admin_set_status(oid):
    status = (body().get("status") or "").upper()
    row = db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()
    if not row:
        return fail("Order not found", 404)
    if status not in STATUSES:
        return fail("Invalid status")
    if row["status"] in ("DELIVERED", "CANCELLED"):
        return fail(f"Order is already {row['status'].lower()}")
    flow = ["PLACED", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED"]
    if status != "CANCELLED" and flow.index(status) <= flow.index(row["status"]):
        return fail("An order can only move forward (or be cancelled)")
    if status == "CANCELLED":
        restock_and_cancel(row)
    else:
        db().execute("UPDATE orders SET status=? WHERE id=?", (status, oid))
        if status == "DELIVERED" and row["payment_method"] == "COD":
            db().execute("UPDATE orders SET payment_status='PAID' WHERE id=?", (oid,))
        log_event(oid, status)
        db().commit()
    return jsonify(order_dict(db().execute("SELECT * FROM orders WHERE id=?", (oid,)).fetchone()))


@app.post("/api/admin/products")
@admin_required
def admin_add_product():
    d = body()
    name = (d.get("name") or "").strip()
    cat = db().execute("SELECT id FROM categories WHERE slug=?", (d.get("category"),)).fetchone()
    try:
        price, mrp, stock = int(d.get("price")), int(d.get("mrp") or d.get("price")), int(d.get("stock") or 0)
    except (TypeError, ValueError):
        return fail("Price, MRP and stock must be numbers")
    if not name or not cat:
        return fail("Name and a valid category are required")
    if price <= 0 or mrp < price:
        return fail("MRP must be greater than or equal to the price")
    if db().execute("SELECT 1 FROM products WHERE name=?", (name,)).fetchone():
        return fail("A product with this name already exists", 409)
    image = (d.get("image") or "").strip() or write_image(name, d.get("emoji") or "🎁", "#dbe6ff", "#a9c1ff")
    keywords = (d.get("keywords") or name).lower()
    cur = db().execute(
        """INSERT INTO products (category_id,name,description,price,mrp,rating,rating_count,image,stock,keywords)
           VALUES (?,?,?,?,?,4.0,0,?,?,?)""",
        (cat["id"], name, (d.get("description") or "").strip(), price, mrp, image, stock, keywords))
    db().commit()
    return jsonify(dict(db().execute(PRODUCT_SELECT + " WHERE p.id=?", (cur.lastrowid,)).fetchone())), 201


@app.patch("/api/admin/products/<int:pid>")
@admin_required
def admin_edit_product(pid):
    d = body()
    if not db().execute("SELECT 1 FROM products WHERE id=?", (pid,)).fetchone():
        return fail("Product not found", 404)
    for field in ("price", "mrp", "stock"):
        if field in d:
            try:
                val = int(d[field])
                if val < 0:
                    raise ValueError
            except (TypeError, ValueError):
                return fail(f"Invalid {field}")
            db().execute(f"UPDATE products SET {field}=? WHERE id=?", (val, pid))
    db().commit()
    return jsonify(dict(db().execute(PRODUCT_SELECT + " WHERE p.id=?", (pid,)).fetchone()))


@app.errorhandler(404)
def not_found(_e):
    if request.path.startswith("/api/"):
        return fail("Not found", 404)
    return app.send_static_file("index.html")


@app.route("/")
def home():
    return app.send_static_file("index.html")


init_db()  # runs on import so gunicorn / PythonAnywhere also create the database


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    print(f"Flipcart running at http://localhost:{port}   (admin: admin@flipcart.com)")
    try:
        app.run(host=host, port=port, debug=False)
    except OSError:
        print("\nERROR: port 8000 is already in use. Close the other Flipcart window "
              "(or whatever uses port 8000) and start again.")
        raise SystemExit(1)
