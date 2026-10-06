"""SQLite schema + seed data for Flipcart (Python edition)."""
import os
import re
import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("FLIPCART_DB", os.path.join(BASE_DIR, "shop.db"))
IMG_DIR = os.path.join(BASE_DIR, "public", "images")

# Set ADMIN_PASSWORD in the environment when you deploy (default is for local demo only)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
USING_DEFAULT_ADMIN = ADMIN_PASSWORD is None

STATUSES = ["PLACED", "PACKED", "SHIPPED", "OUT_FOR_DELIVERY", "DELIVERED", "CANCELLED"]


def connect():
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL,
  email TEXT NOT NULL UNIQUE,
  password_hash TEXT NOT NULL,
  is_admin INTEGER NOT NULL DEFAULT 0,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS sessions (
  token TEXT PRIMARY KEY,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS categories (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  slug TEXT NOT NULL UNIQUE,
  name TEXT NOT NULL,
  icon TEXT DEFAULT '🛍️'
);
CREATE TABLE IF NOT EXISTS products (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  category_id INTEGER NOT NULL REFERENCES categories(id),
  name TEXT NOT NULL UNIQUE,
  description TEXT DEFAULT '',
  price INTEGER NOT NULL,
  mrp INTEGER NOT NULL,
  rating REAL DEFAULT 4.0,
  rating_count INTEGER DEFAULT 0,
  image TEXT NOT NULL,
  stock INTEGER NOT NULL DEFAULT 100,
  keywords TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS cart_items (
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
  qty INTEGER NOT NULL CHECK (qty > 0),
  PRIMARY KEY (user_id, product_id)
);
CREATE TABLE IF NOT EXISTS addresses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  phone TEXT NOT NULL,
  pincode TEXT NOT NULL,
  line1 TEXT NOT NULL,
  city TEXT NOT NULL,
  state TEXT NOT NULL,
  kind TEXT DEFAULT 'Home'
);
CREATE TABLE IF NOT EXISTS promos (
  code TEXT PRIMARY KEY,
  percent INTEGER NOT NULL,
  max_discount INTEGER NOT NULL,
  min_order INTEGER NOT NULL DEFAULT 0,
  description TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS orders (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  status TEXT NOT NULL DEFAULT 'PLACED',
  mrp_total INTEGER, subtotal INTEGER, discount INTEGER, coupon INTEGER,
  coupon_code TEXT, delivery INTEGER, total INTEGER,
  payment_method TEXT, payment_status TEXT, payment_ref TEXT, payment_detail TEXT,
  ship_name TEXT, ship_phone TEXT, ship_address TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS order_items (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  product_id INTEGER, name TEXT, image TEXT, price INTEGER, mrp INTEGER, qty INTEGER
);
CREATE TABLE IF NOT EXISTS order_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  order_id INTEGER NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
  status TEXT NOT NULL,
  note TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS payments (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  order_id INTEGER REFERENCES orders(id) ON DELETE SET NULL,
  method TEXT NOT NULL,
  amount INTEGER NOT NULL,
  status TEXT NOT NULL,          -- SUCCESS / FAILED
  reference TEXT,                -- gateway transaction id
  detail TEXT,                   -- masked: 'Visa •••• 1111', 'UPI ra***@okhdfc'  (never full card / CVV)
  message TEXT,
  created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_products_cat ON products(category_id);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
"""

CATEGORIES = [
    ("mobiles", "Mobiles", "📱"), ("laptops", "Laptops", "💻"),
    ("electronics", "Electronics & Appliances", "🔌"), ("fashion", "Fashion", "👕"),
    ("grocery", "Grocery", "🛒"), ("home", "Home & Kitchen", "🏠"),
    ("beauty", "Beauty", "💄"), ("toys", "Toys & Games", "🧸"), ("books", "Books", "📚"),
]

E = "electronic electric device gadget"
# category, name, emoji, colour1, colour2, price, mrp, rating, description, keywords
PRODUCTS = [
    ("mobiles", "Nova X5 5G Smartphone", "📱", "#a8c0ff", "#3f2b96", 17999, 22999, 4.4, '6.6" AMOLED, 128GB, 50MP camera, 5G', f"phone mobile smartphone cellphone android {E}"),
    ("mobiles", "Lite Z2 Smartphone", "📱", "#ffd6a5", "#ff6f91", 9999, 13999, 4.1, '6.5" HD+, 64GB, 5000mAh battery', f"phone mobile smartphone cellphone budget android {E}"),
    ("mobiles", "Wireless Earbuds Pro", "🎧", "#fbc2eb", "#a6c1ee", 1999, 3999, 4.2, "30h battery with noise cancellation", f"earphone earphones headphone headphones bluetooth audio {E}"),
    ("mobiles", "Smart Watch Active", "⌚", "#84fab0", "#8fd3f4", 2499, 4999, 4.1, "AMOLED display, heart-rate & SpO2", f"watch smartwatch wearable fitness {E}"),
    ("laptops", "AeroBook 14 Laptop", "💻", "#c3cfe2", "#5f72bd", 46990, 58990, 4.5, '14" FHD, 16GB RAM, 512GB SSD', f"laptop computer notebook pc {E}"),
    ("laptops", "Student Laptop 15", "💻", "#cfd9df", "#6a85b6", 32990, 41990, 4.2, '15.6" FHD, 8GB RAM, 256GB SSD', f"laptop computer notebook pc student {E}"),
    ("laptops", "Gaming Mouse RGB", "🖱️", "#ff9a9e", "#6a3093", 799, 1499, 4.3, "7200 DPI, 6 programmable buttons", f"mouse computer accessory {E}"),
    ("laptops", "Mechanical Keyboard", "⌨️", "#fddb92", "#d1fdff", 2299, 3299, 4.4, "Hot-swappable blue switches", f"keyboard computer accessory {E}"),
    ("electronics", 'Smart LED TV 43"', "📺", "#a18cd1", "#fbc2eb", 24999, 34999, 4.4, "4K Ultra HD, Smart TV with apps", f"tv television led screen display {E}"),
    ("electronics", "Bluetooth Speaker", "🔊", "#f6d365", "#fda085", 1499, 2999, 4.3, "20W, waterproof, 12h playtime", f"speaker audio music sound bluetooth {E}"),
    ("electronics", "Power Bank 20000mAh", "🔋", "#96fbc4", "#f9f586", 1299, 2199, 4.2, "Fast charging, dual USB", f"charger battery powerbank {E}"),
    ("electronics", "Ceiling Fan 1200mm", "🌀", "#c2e9fb", "#a1c4fd", 2199, 3199, 4.1, "Energy saving, 3 blades", f"fan cooling appliance home {E}"),
    ("electronics", "Electric Kettle 1.5L", "🫖", "#ffe29f", "#ffa99f", 899, 1499, 4.3, "Stainless steel, auto shut-off", f"kettle kitchen appliance water heater {E}"),
    ("electronics", "Beard Trimmer", "✂️", "#b2fefa", "#0ed2f7", 999, 1799, 4.2, "Cordless, 60 min runtime", f"trimmer shaver grooming men {E}"),
    ("electronics", "Digital Camera 24MP", "📷", "#d299c2", "#fef9d7", 18999, 24999, 4.5, '24MP, 4K video, 3" screen', f"camera photo photography video {E}"),
    ("electronics", '24" Full HD Monitor', "🖥️", "#89f7fe", "#66a6ff", 8499, 11999, 4.3, "IPS, 75Hz, HDMI", f"monitor display screen computer {E}"),
    ("electronics", "Steam Iron 1400W", "🧺", "#e6dada", "#a8bfc4", 1199, 1999, 4.0, "Non-stick soleplate", f"iron press clothes appliance {E}"),
    ("fashion", "Classic Denim Jacket", "🧥", "#89f7fe", "#66a6ff", 1599, 2999, 4.0, "Regular fit, 100% cotton", "jacket clothes clothing dress wear men women coat"),
    ("fashion", "Running Sneakers", "👟", "#f6d365", "#fda085", 2199, 3999, 4.3, "Lightweight breathable mesh", "shoe shoes footwear sneaker boots sports running"),
    ("fashion", "Formal Leather Shoes", "👞", "#c79081", "#dfa579", 2499, 4299, 4.2, "Genuine leather, office wear", "shoe shoes footwear formal boots men office"),
    ("fashion", "Casual Sandals", "🩴", "#fbab7e", "#f7ce68", 699, 1299, 4.0, "Comfortable everyday sandals", "shoe footwear sandal slippers chappal flipflop"),
    ("fashion", "Cotton Casual T-Shirt", "👕", "#a1c4fd", "#c2e9fb", 399, 899, 4.1, "Soft & breathable cotton", "tshirt shirt clothes clothing wear"),
    ("fashion", "Leather Backpack", "🎒", "#d4fc79", "#96e6a1", 1299, 2499, 4.2, "25L, laptop compartment", "bag backpack school travel"),
    ("grocery", "Fresh Fruit Basket 2kg", "🍎", "#ffecd2", "#fcb69f", 349, 449, 4.5, "Apples, bananas & oranges", "fruit apple banana orange food fresh"),
    ("grocery", "Basmati Rice 5kg", "🍚", "#fdfbfb", "#ebedee", 549, 699, 4.4, "Aged long-grain premium rice", "rice food staple"),
    ("grocery", "Assorted Dry Fruits 500g", "🥜", "#f5d7a1", "#e0a84a", 599, 799, 4.6, "Almonds, cashews, raisins", "nuts almond cashew food snack"),
    ("home", "Non-Stick Cookware Set", "🍳", "#e0c3fc", "#8ec5fc", 1799, 3499, 4.2, "3-piece induction base set", "pan kitchen cooking utensil"),
    ("home", "LED Desk Lamp", "💡", "#fff1eb", "#ace0f9", 699, 1199, 4.3, "3 colour modes, USB powered", f"lamp light bulb {E}"),
    ("home", "Coffee Maker", "☕", "#d7d2cc", "#8a9ba8", 2899, 4500, 4.1, "Drip brewer, 1.2L, keep-warm", f"coffee machine kitchen appliance {E}"),
    ("beauty", "Vitamin C Face Serum", "🧴", "#ffd1ff", "#fad0c4", 449, 799, 4.3, "30ml, brightening & glow", "skincare face cream"),
    ("beauty", "Matte Lipstick Set", "💄", "#ff758c", "#ff7eb3", 599, 1099, 4.2, "Set of 4 long-lasting shades", "makeup cosmetic"),
    ("beauty", "Hair Dryer 1800W", "💨", "#c1dfc4", "#deecdd", 999, 1799, 4.0, "Ionic, 3 heat settings", f"hair appliance grooming {E}"),
    ("toys", "Building Blocks 500pcs", "🧱", "#f093fb", "#f5576c", 899, 1599, 4.6, "Creative bricks for ages 6+", "lego toy kids game"),
    ("toys", "Remote Control Car", "🏎️", "#4facfe", "#00f2fe", 1199, 1999, 4.2, "2.4GHz, rechargeable battery", f"toy kids car remote {E}"),
    ("toys", "Plush Teddy Bear", "🧸", "#fccb90", "#d57eeb", 499, 899, 4.7, "60cm, super soft", "toy kids doll soft"),
    ("books", "Atomic Habits", "📘", "#667eea", "#764ba2", 399, 699, 4.8, "Build good habits, break bad ones", "book novel reading"),
    ("books", "The Psychology of Money", "📗", "#43e97b", "#38f9d7", 349, 599, 4.7, "Timeless lessons on wealth", "book novel reading finance"),
]

PROMOS = [
    ("FIRST50", 50, 150, 299, "50% off up to ₹150 on orders above ₹299"),
    ("SAVE20", 20, 300, 999, "20% off up to ₹300 on orders above ₹999"),
    ("FLIP10", 10, 100, 0, "10% off up to ₹100 on any order"),
]


def slugify(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def make_svg(emoji, c1, c2):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 300">'
        f'<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="{c1}"/>'
        f'<stop offset="1" stop-color="{c2}"/></linearGradient></defs>'
        '<rect width="400" height="300" fill="url(#g)"/>'
        '<circle cx="200" cy="150" r="105" fill="rgba(255,255,255,.55)"/>'
        f'<text x="200" y="155" font-size="120" text-anchor="middle" dominant-baseline="central">{emoji}</text>'
        "</svg>"
    )


def write_image(name, emoji, c1, c2):
    os.makedirs(IMG_DIR, exist_ok=True)
    fname = slugify(name) + ".svg"
    with open(os.path.join(IMG_DIR, fname), "w", encoding="utf-8") as f:
        f.write(make_svg(emoji, c1, c2))
    return "images/" + fname


def init_db():
    conn = connect()
    conn.executescript(SCHEMA)
    cur = conn.cursor()
    # migrate databases created before payments existed
    cols = [c["name"] for c in cur.execute("PRAGMA table_info(orders)")]
    for col in ("payment_ref", "payment_detail"):
        if col not in cols:
            cur.execute(f"ALTER TABLE orders ADD COLUMN {col} TEXT")
    for slug, name, icon in CATEGORIES:
        cur.execute("INSERT OR IGNORE INTO categories (slug, name, icon) VALUES (?,?,?)", (slug, name, icon))
    for i, (cat, name, emoji, c1, c2, price, mrp, rating, desc, kw) in enumerate(PRODUCTS):
        if cur.execute("SELECT 1 FROM products WHERE name=?", (name,)).fetchone():
            continue
        image = write_image(name, emoji, c1, c2)
        cur.execute(
            """INSERT INTO products (category_id,name,description,price,mrp,rating,rating_count,image,keywords)
               VALUES ((SELECT id FROM categories WHERE slug=?),?,?,?,?,?,?,?,?)""",
            (cat, name, desc, price, mrp, rating, 80 + (i * 137) % 2400, image, kw),
        )
    # use real photos (public/images/<product-slug>.jpg, made by fetch_images.py) when present
    for p in PRODUCTS:
        slug = slugify(p[1])
        if os.path.exists(os.path.join(IMG_DIR, slug + ".jpg")):
            cur.execute("UPDATE products SET image=? WHERE name=? AND image LIKE '%.svg'",
                        (f"images/{slug}.jpg", p[1]))
    for p in PROMOS:
        cur.execute("INSERT OR IGNORE INTO promos VALUES (?,?,?,?,?)", p)
    # admin account: password comes from ADMIN_PASSWORD (default only for local demo)
    admin = cur.execute("SELECT id, password_hash FROM users WHERE email='admin@flipcart.com'").fetchone()
    if not admin:
        cur.execute("INSERT INTO users (name,email,password_hash,is_admin) VALUES (?,?,?,1)",
                    ("Admin", "admin@flipcart.com", generate_password_hash(ADMIN_PASSWORD or "admin123")))
    elif ADMIN_PASSWORD and not check_password_hash(admin["password_hash"], ADMIN_PASSWORD):
        # an old database (e.g. uploaded from your laptop) must not keep the demo password
        cur.execute("UPDATE users SET password_hash=?, is_admin=1 WHERE id=?",
                    (generate_password_hash(ADMIN_PASSWORD), admin["id"]))
        cur.execute("DELETE FROM sessions WHERE user_id=?", (admin["id"],))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database ready:", DB_PATH)
