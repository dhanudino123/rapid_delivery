"""Tests fetch_images.py with the network mocked (run: python -m unittest discover tests)"""
import json, os, sys, tempfile, unittest
from unittest import mock
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
tmp = tempfile.mkdtemp()
os.environ["FLIPCART_DB"] = os.path.join(tmp, "img.db")
import database
database.DB_PATH = os.environ["FLIPCART_DB"]
database.IMG_DIR = os.path.join(tmp, "images")
import fetch_images
fetch_images.IMG_DIR = database.IMG_DIR

WIKI = {"query": {"pages": {
    "1": {"title": "File:Logo.jpg", "index": 1, "imageinfo": [{"mime": "image/jpeg", "width": 900, "thumburl": "http://x/logo.jpg"}]},
    "2": {"title": "File:Phone.jpg", "index": 2, "imageinfo": [{"mime": "image/jpeg", "width": 900, "thumburl": "http://x/phone.jpg",
          "descriptionurl": "http://x/p", "extmetadata": {"Artist": {"value": "<b>Ann</b>"}, "LicenseShortName": {"value": "CC BY"}}}]},
    "3": {"title": "File:Small.jpg", "index": 3, "imageinfo": [{"mime": "image/jpeg", "width": 100, "thumburl": "http://x/s.jpg"}]}}}}


def fake_get(url, headers=None, timeout=30):
    if "commons.wikimedia.org" in url:
        return json.dumps(WIKI).encode()
    if "api.pexels.com" in url:
        return json.dumps({"photos": [{"src": {"large": "http://x/pex.jpg"}, "photographer": "Bob", "url": "http://p"}]}).encode()
    return b"\xff\xd8\xff" + b"0" * 6000  # fake jpeg bytes


class FetchImages(unittest.TestCase):
    def test_wikimedia_skips_logo_and_small(self):
        with mock.patch.object(fetch_images, "http_get", fake_get):
            hit = fetch_images.from_wikimedia("phone")
        self.assertEqual(hit["url"], "http://x/phone.jpg")
        self.assertIn("Ann", hit["credit"])

    def test_full_run_updates_db_and_files(self):
        with mock.patch.object(fetch_images, "http_get", fake_get), mock.patch("time.sleep"):
            fetch_images.main(["--pexels-key", "k"])
        import sqlite3
        row = sqlite3.connect(database.DB_PATH).execute("SELECT image FROM products WHERE name='Atomic Habits'").fetchone()
        self.assertEqual(row[0], "images/atomic-habits.jpg")
        self.assertTrue(os.path.exists(os.path.join(database.IMG_DIR, "atomic-habits.jpg")))
        self.assertTrue(os.path.exists(os.path.join(database.IMG_DIR, "CREDITS.txt")))


if __name__ == "__main__":
    unittest.main()
