#!/usr/bin/env python3
"""Download real product photos and attach them to the products in the database.

    python fetch_images.py                      # free, no key  (Wikimedia Commons)
    python fetch_images.py --pexels-key KEY     # best quality   (free key: https://www.pexels.com/api/)
    python fetch_images.py --force              # re-download photos that already exist

Photos are saved as public/images/<product-slug>.jpg, the database is updated, and
public/images/CREDITS.txt lists the source/photographer of every photo.
Needs an internet connection. Uses only the Python standard library.
"""
import argparse
import json
import os
import re
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

import database
from database import IMG_DIR, PRODUCTS, slugify

UA = "FlipcartStudentProject/1.0 (educational demo)"

# product name -> (Pexels query, Wikimedia Commons query)
QUERIES = {
    "Nova X5 5G Smartphone": ("smartphone", "smartphone"),
    "Lite Z2 Smartphone": ("android phone", "android smartphone"),
    "Wireless Earbuds Pro": ("wireless earbuds", "wireless earbuds"),
    "Smart Watch Active": ("smartwatch", "smartwatch"),
    "AeroBook 14 Laptop": ("laptop computer", "laptop computer"),
    "Student Laptop 15": ("laptop on desk", "notebook computer"),
    "Gaming Mouse RGB": ("gaming mouse", "computer mouse"),
    "Mechanical Keyboard": ("mechanical keyboard", "mechanical keyboard"),
    'Smart LED TV 43"': ("television", "led television"),
    "Bluetooth Speaker": ("bluetooth speaker", "bluetooth speaker"),
    "Power Bank 20000mAh": ("power bank", "power bank"),
    "Ceiling Fan 1200mm": ("ceiling fan", "ceiling fan"),
    "Electric Kettle 1.5L": ("electric kettle", "electric kettle"),
    "Beard Trimmer": ("beard trimmer", "hair trimmer"),
    "Digital Camera 24MP": ("digital camera", "digital camera"),
    '24" Full HD Monitor': ("computer monitor", "computer monitor"),
    "Steam Iron 1400W": ("steam iron", "clothes iron"),
    "Classic Denim Jacket": ("denim jacket", "denim jacket"),
    "Running Sneakers": ("running shoes", "running shoes"),
    "Formal Leather Shoes": ("leather shoes", "leather dress shoes"),
    "Casual Sandals": ("sandals", "sandals footwear"),
    "Cotton Casual T-Shirt": ("t-shirt", "t-shirt"),
    "Leather Backpack": ("leather backpack", "backpack"),
    "Fresh Fruit Basket 2kg": ("fruit basket", "fruit basket"),
    "Basmati Rice 5kg": ("basmati rice", "basmati rice"),
    "Assorted Dry Fruits 500g": ("dry fruits nuts", "dried fruit nuts"),
    "Non-Stick Cookware Set": ("cookware pots pans", "cookware"),
    "LED Desk Lamp": ("desk lamp", "desk lamp"),
    "Coffee Maker": ("coffee maker", "coffee maker"),
    "Vitamin C Face Serum": ("face serum bottle", "serum dropper bottle"),
    "Matte Lipstick Set": ("lipstick", "lipstick"),
    "Hair Dryer 1800W": ("hair dryer", "hair dryer"),
    "Building Blocks 500pcs": ("toy building blocks", "building blocks toy"),
    "Remote Control Car": ("remote control car toy", "radio-controlled car"),
    "Plush Teddy Bear": ("teddy bear", "teddy bear"),
    "Atomic Habits": ("books stack", "books"),
    "The Psychology of Money": ("book", "book cover"),
}
BAD_TITLE = re.compile(r"logo|diagram|icon|map|flag|screenshot|drawing|poster|chart|schematic|\.svg|coat of arms", re.I)


def http_get(url, headers=None, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def from_pexels(query, key):
    url = "https://api.pexels.com/v1/search?" + urllib.parse.urlencode(
        {"query": query, "per_page": 5, "orientation": "landscape"})
    photos = json.loads(http_get(url, {"Authorization": key})).get("photos", [])
    if not photos:
        return None
    p = photos[0]
    return {"url": p["src"].get("large") or p["src"]["original"],
            "credit": f"Photo by {p.get('photographer', 'unknown')} on Pexels – {p.get('url', '')}"}


def from_wikimedia(query):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({
        "action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo",
        "iiprop": "url|mime|size|extmetadata", "iiurlwidth": 640})
    pages = json.loads(http_get(url)).get("query", {}).get("pages", {}).values()
    for pg in sorted(pages, key=lambda x: x.get("index", 999)):
        info = (pg.get("imageinfo") or [{}])[0]
        if info.get("mime") != "image/jpeg" or info.get("width", 0) < 500 or BAD_TITLE.search(pg.get("title", "")):
            continue
        meta = info.get("extmetadata", {})
        artist = re.sub(r"<[^>]+>", "", meta.get("Artist", {}).get("value", "unknown"))
        lic = meta.get("LicenseShortName", {}).get("value", "see page")
        return {"url": info.get("thumburl") or info["url"],
                "credit": f"{pg['title']} by {artist} ({lic}) – {info.get('descriptionurl', '')}"}
    return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pexels-key", default=os.environ.get("PEXELS_API_KEY"))
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args(argv)

    database.init_db()
    os.makedirs(IMG_DIR, exist_ok=True)
    conn = sqlite3.connect(database.DB_PATH)
    credits, ok, failed = [], 0, []
    source = "Pexels" if args.pexels_key else "Wikimedia Commons"
    print(f"Fetching photos from {source} ...")
    for prod in PRODUCTS:
        name = prod[1]
        dest = os.path.join(IMG_DIR, slugify(name) + ".jpg")
        if os.path.exists(dest) and not args.force:
            print(f"  = {name} (already has a photo)")
            continue
        pexels_q, wiki_q = QUERIES.get(name, (name, name))
        try:
            hit = from_pexels(pexels_q, args.pexels_key) if args.pexels_key else from_wikimedia(wiki_q)
            if not hit:
                raise RuntimeError("no suitable photo found")
            data = http_get(hit["url"])
            if len(data) < 5000:
                raise RuntimeError("download too small")
            with open(dest, "wb") as f:
                f.write(data)
            conn.execute("UPDATE products SET image=? WHERE name=?", (f"images/{slugify(name)}.jpg", name))
            conn.commit()
            credits.append(f"{name}: {hit['credit']}")
            ok += 1
            print(f"  ✓ {name}")
        except Exception as e:  # keep going; the SVG placeholder stays for this product
            failed.append(name)
            print(f"  ✗ {name}: {e}")
        time.sleep(0.4)
    if credits:
        with open(os.path.join(IMG_DIR, "CREDITS.txt"), "a", encoding="utf-8") as f:
            f.write("\n".join(credits) + "\n")
    conn.close()
    print(f"\nDone: {ok} photos downloaded, {len(failed)} failed.")
    if failed:
        print("Failed items keep their placeholder. Run again, or try --pexels-key for better coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
