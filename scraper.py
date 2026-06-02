import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime

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
                # Ensure it's a dict for our new logic, but handle old list format
                if isinstance(data, list):
                    return {"last_week": 0, "last_year": 0, "urls": data}
                return data
            except:
                return {"last_week": 0, "last_year": 0, "urls": []}
    return {"last_week": 0, "last_year": 0, "urls": []}

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
    # --- OPTIMIZATION: Weekly Check ---
    now = datetime.now()
    current_year, current_week, _ = now.isocalendar()
    history = get_history()

    if history.get("last_week") == current_week and history.get("last_year") == current_year:
        print(f"INFO: Pattern for week {current_week} of {current_year} already sent. Skipping check.")
        return

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

    # Search for instruction text
    instruction_text = soup.find(lambda t: t.name in ["h2", "p", "div"] and "Descarga dando click" in t.text)
    
    if not instruction_text:
        print("Pattern not available right now.")
        return

    print("Instructional text found! Searching for button...")

    # Search for the button link
    download_link = None
    parent = instruction_text.parent
    for _ in range(5):
        if not parent: break
        links = parent.find_all("a", href=True)
        for link in links:
            href = link['href']
            if "/resource_redirect/downloads/" in href or href.endswith(".pdf"):
                download_link = href
                break
        if download_link: break
        parent = parent.parent

    if not download_link:
        # Fallback global search
        all_links = soup.find_all("a", href=True)
        instruction_index = str(soup).find(str(instruction_text))
        for link in all_links:
            if str(soup).find(str(link)) > instruction_index:
                href = link['href']
                if "/resource_redirect/downloads/" in href or href.endswith(".pdf"):
                    download_link = href
                    break

    if not download_link:
        print("Link not found after instruction text.")
        return

    if download_link.startswith("/"):
        download_link = "https://mami-costurera.mykajabi.com" + download_link

    # Final check: Don't resend exact same URL if week somehow changed or reset
    if download_link in history.get("urls", []):
        print("This specific URL was already sent. Updating weekly lock.")
        history["last_week"] = current_week
        history["last_year"] = current_year
        save_history(history)
        return

    # Download
    file_name = download_link.split("/")[-1].split("?")[0]
    if not file_name.endswith(".pdf"): file_name += ".pdf"

    print(f"Downloading: {file_name}")
    pdf_data = requests.get(download_link).content
    with open(file_name, "wb") as f:
        f.write(pdf_data)

    # Send
    print("Sending to Telegram...")
    res = send_to_telegram(file_name, "¡Nuevo patrón encontrado! 🧵")

    if res.get("ok"):
        print("Success! Locking this week.")
        history["last_week"] = current_week
        history["last_year"] = current_year
        history["urls"].append(download_link)
        save_history(history)
    else:
        print(f"Failed to send: {res}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Config Error.")
    else:
        scrape_and_download()
