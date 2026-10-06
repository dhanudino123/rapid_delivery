#!/bin/bash
# Downloads real product photos (needs internet). Optional: paste a free Pexels API key for best quality.
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { echo "Run Open_Flipcart.command once first."; read -p "Press Enter"; exit 1; }
read -p "Pexels API key (press Enter to skip and use Wikimedia): " KEY
if [ -n "$KEY" ]; then .venv/bin/python fetch_images.py --pexels-key "$KEY"; else .venv/bin/python fetch_images.py; fi
read -p "Finished. Press Enter to close"
