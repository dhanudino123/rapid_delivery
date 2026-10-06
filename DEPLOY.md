# Deploy Flipcart online (free)

Do this **before** deploying: get real photos and test locally.

## Step 0 – Real product photos (do this on your own computer, once)
Double-click **Get_Real_Images.command** (Mac) / **Get_Real_Images.bat** (Windows), or run:

    python fetch_images.py                      # no key needed (Wikimedia Commons)
    python fetch_images.py --pexels-key YOUR_KEY   # best quality – free key at https://www.pexels.com/api/

It saves `public/images/<product>.jpg`, updates the database and writes `public/images/CREDITS.txt`.
Open the shop and check the photos. Re-run with `--force` to replace photos you don't like.
Any product that can't be matched keeps its placeholder image. Wikimedia results can be hit-and-miss,
Pexels is much better. For one specific photo, use Admin → Add product → "Image URL", or drop
a `.jpg` named like the product slug into `public/images`.

---
## Option A – PythonAnywhere (recommended: your SQLite data is kept)
Free URL: `https://YOURNAME.pythonanywhere.com`

1. Sign up at pythonanywhere.com (free "Beginner" account). Remember your username.
2. **Files** tab → upload `flipcart_python.zip` (zip the project *after* Step 0 so photos are included).
3. **Consoles → Bash**:

       unzip flipcart_python.zip
       python3 -m venv ~/flipenv
       ~/flipenv/bin/pip install flask

4. **Web** tab → *Add a new web app* → *Manual configuration* → pick the Python version (3.10+).
   * **Source code:** `/home/YOURNAME/flipcart_py`
   * **Virtualenv:** `/home/YOURNAME/flipenv`
   * Click the **WSGI configuration file** link, delete everything and paste:

         import sys, os
         sys.path.insert(0, '/home/YOURNAME/flipcart_py')
         os.environ['ADMIN_PASSWORD'] = 'choose-a-strong-password'
         from app import app as application

5. Click **Reload** (green button). Open `https://YOURNAME.pythonanywhere.com` ✅
6. Admin login: `admin@flipcart.com` + the password you put in the WSGI file.

Notes: free accounts can only reach whitelisted sites, so run `fetch_images.py` on your own computer (Step 0),
not on PythonAnywhere. Free apps must be re-activated (button on the Web tab) about every 3 months.

---
## Option B – Render.com
1. Put the project on GitHub:

       git init && git add . && git commit -m "Flipcart"
       git branch -M main && git remote add origin https://github.com/YOU/flipcart.git && git push -u origin main

2. render.com → **New → Blueprint** → choose the repo (it reads `render.yaml`).
   Or **New → Web Service** with: Build `pip install -r requirements.txt`,
   Start `gunicorn app:app --workers 1 --threads 4 --bind 0.0.0.0:$PORT`.
3. Add the environment variable **ADMIN_PASSWORD** (your own strong password) and deploy.
4. Open the `https://….onrender.com` URL.

⚠️ Render's free plan sleeps after ~15 min idle (first visit takes ~50 s) and has a **temporary disk**:
accounts/orders are wiped on every restart or redeploy (products & photos come back because they are re-seeded).
Fine for a demo; for permanent data use PythonAnywhere, a paid Render disk
(set `FLIPCART_DB=/var/data/shop.db`), or switch the database to PostgreSQL.

---
## Before you zip & upload
* **Delete `shop.db`** (and any `shop.db-wal / -shm` files) from the folder – it holds your local test accounts and orders.
  A fresh database with all products is created automatically on first start.
* Delete the `.venv` folder (it is rebuilt on the server).

## Before you share the link
* ✅ Set a strong `ADMIN_PASSWORD` (the demo credentials are hidden on the login page once it is set).
* ✅ The site is served over HTTPS automatically on both platforms.
* ℹ️ Payments are simulated – never present this as a store that takes real money.
* ℹ️ For a real shop you would also add: rate-limiting on login, email verification, session expiry and a real payment gateway.
