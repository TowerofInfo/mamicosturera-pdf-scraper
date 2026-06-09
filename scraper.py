import os
import requests
from bs4 import BeautifulSoup
import json

# Configuration
TARGET_URL = "https://mami-costurera.mykajabi.com/emprendiendoycosiendo"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HISTORY_FILE = "download_history.json"

def get_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            try:
                data = json.load(f)
                # Handle cases where history might be an old list format
                if isinstance(data, list):
                    return {"filenames": []}
                return data
            except:
                return {"filenames": []}
    return {"filenames": []}

def save_history(history):
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f)

def send_to_telegram(file_path, caption):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendDocument"
    with open(file_path, "rb") as f:
        files = {"document": f}
        data = {"chat_id": TELEGRAM_CHAT_ID, "caption": caption}
        response = requests.post(url, data=data, files=files)
    return response.json()

def scrape_and_download():
    history = get_history()
    if "filenames" not in history:
        history["filenames"] = []

    print(f"Checking {TARGET_URL}...")
    
    try:
        response = requests.get(TARGET_URL, timeout=30)
        if response.status_code != 200:
            print(f"Error accessing site: {response.status_code}")
            return
    except Exception as e:
        print(f"Network error: {e}")
        return

    soup = BeautifulSoup(response.text, "html.parser")

    # 1. Find ALL links that look like PDF downloads
    all_links = soup.find_all("a", href=True)
    potential_downloads = []

    for link in all_links:
        href = link['href']
        if "/resource_redirect/downloads/" in href or href.lower().endswith(".pdf"):
            if href.startswith("/"):
                href = "https://mami-costurera.mykajabi.com" + href
            potential_downloads.append(href)

    if not potential_downloads:
        print("No pattern links found on the page.")
        return

    print(f"Found {len(potential_downloads)} potential links. Checking for new ones...")

    new_found = False
    for download_link in potential_downloads:
        # Extract filename and strip the dynamic hash
        # Kajabi format is usually: .../downloads/HASH_Actual_FileName.pdf
        raw_name = download_link.split("/")[-1].split("?")[0]
        
        if "_" in raw_name:
            # Everything after the first underscore is the stable filename
            base_name = "_".join(raw_name.split("_")[1:])
        else:
            base_name = raw_name

        # --- DUPLICATE CHECK ---
        if base_name in history["filenames"]:
            print(f"Skipping {base_name}: already sent.")
            continue

        # --- NEW PATTERN FOUND ---
        print(f"New pattern detected: {base_name}")
        
        try:
            pdf_data = requests.get(download_link, timeout=60).content
            temp_path = f"temp_{raw_name}"
            with open(temp_path, "wb") as f:
                f.write(pdf_data)

            print("Sending to Telegram...")
            res = send_to_telegram(temp_path, f"¡Nuevo patrón encontrado! 🧵\nNombre: {base_name}")

            if res.get("ok"):
                print("Success! Adding to history.")
                history["filenames"].append(base_name)
                new_found = True
            else:
                print(f"Failed to send to Telegram: {res}")

            if os.path.exists(temp_path):
                os.remove(temp_path)

        except Exception as e:
            print(f"Error processing {base_name}: {e}")

    if new_found:
        save_history(history)
    else:
        print("No new unique patterns to send.")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Config error: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID not set.")
    else:
        scrape_and_download()
