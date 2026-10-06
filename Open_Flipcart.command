#!/bin/bash
# Mac / Linux launcher. Keep this window open while you use the shop.
cd "$(dirname "$0")"
if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/"; read -p "Press Enter to close"; exit 1
fi
if [ ! -x .venv/bin/python ]; then
  echo "First run: setting up, please wait..."
  python3 -m venv .venv && .venv/bin/python -m pip install -r requirements.txt || {
    echo "Setup failed - check your internet connection."; rm -rf .venv; read -p "Press Enter to close"; exit 1; }
fi
echo "Starting Flipcart at http://localhost:8000  (keep this window open)"
(sleep 2; open http://localhost:8000 2>/dev/null || xdg-open http://localhost:8000 2>/dev/null) &
.venv/bin/python app.py
read -p "Server stopped. Press Enter to close"
