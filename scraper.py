import os
import requests
from bs4 import BeautifulSoup
import json

# Configuration
TARGET_URL = "https://mami-costurera.mykajabi.com/emprendiendoycosiendo"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
HISTORY_FILE = "download_history.json"

def get_download_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_download_history(history):
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
    print(f"Checking {TARGET_URL}...")
    response = requests.get(TARGET_URL)
    if response.status_code != 200:
        print(f"Error accessing site: {response.status_code}")
        return

    soup = BeautifulSoup(response.text, "html.parser")
    history = get_download_history()

    # Step 1: Find the instructional text
    # The user mentioned: "Descarga dando click en el siguiente botón el Patrón Gratis del live de hoy"
    instruction_text = soup.find(lambda t: t.name in ["h2", "p", "div"] and "Descarga dando click" in t.text)
    
    if not instruction_text:
        print("Instructional text not found. The pattern might not be available right now.")
        return

    print("Instructional text found! Searching for button...")

    # Step 2: Find the nearest link/button after this text
    # We look for <a> tags with 'btn' class or suspicious download hrefs
    download_link = None
    
    # Try finding the <a> tag within the same parent or following blocks
    # First, check if the instruction itself is inside a block that has a button
    parent = instruction_text.parent
    for _ in range(5): # Go up a few levels to find a common container
        if not parent:
            break
        links = parent.find_all("a", href=True)
        for link in links:
            href = link['href']
            if "/resource_redirect/downloads/" in href or href.endswith(".pdf"):
                download_link = href
                break
        if download_link:
            break
        parent = parent.parent

    # Fallback: Find all links in the document and pick the one that appears after the text
    if not download_link:
        all_links = soup.find_all("a", href=True)
        instruction_index = str(soup).find(str(instruction_text))
        
        for link in all_links:
            href = link['href']
            link_index = str(soup).find(str(link))
            
            if link_index > instruction_index: # Only links after the text
                if "/resource_redirect/downloads/" in href or href.endswith(".pdf"):
                    download_link = href
                    break

    if not download_link:
        print("Download link not found.")
        return

    # Handle relative URLs
    if download_link.startswith("/"):
        download_link = "https://mami-costurera.mykajabi.com" + download_link

    print(f"Pattern found: {download_link}")

    # Step 3: Check history to avoid duplicates
    if download_link in history:
        print("This pattern was already downloaded and sent.")
        return

    # Step 4: Download the file
    file_name = download_link.split("/")[-1].split("?")[0]
    if not file_name.endswith(".pdf"):
        file_name += ".pdf"

    print(f"Downloading {file_name}...")
    pdf_response = requests.get(download_link)
    
    with open(file_name, "wb") as f:
        f.write(pdf_response.content)

    # Step 5: Send to Telegram
    print("Sending to Telegram...")
    caption = "¡Nuevo patrón encontrado! 🧵"
    result = send_to_telegram(file_name, caption)

    # History update
    if result.get("ok"):
        print("Success! Notification sent.")
        history.append(download_link)
        save_download_history(history)
    else:
        print(f"Failed to send to Telegram: {result}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: TELEGRAM_TOKEN or TELEGRAM_CHAT_ID environment variables not set.")
    else:
        scrape_and_download()
