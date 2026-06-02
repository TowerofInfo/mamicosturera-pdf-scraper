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
                if isinstance(data, list):
                    return {"urls": data}
                return data
            except:
                return {"urls": []}
    return {"urls": []}

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

    # 1. Buscar el texto de instrucción
    instruction_text = soup.find(lambda t: t.name in ["h2", "p", "div"] and "Descarga dando click" in t.text)
    
    if not instruction_text:
        print("Pattern not available right now.")
        return

    print("Instructional text found! Searching for button...")

    # 2. Buscar el enlace del botón
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
        # Búsqueda global de respaldo
        all_links = soup.find_all("a", href=True)
        instruction_index = str(soup).find(str(instruction_text))
        for link in all_links:
            if str(soup).find(str(link)) > instruction_index:
                href = link['href']
                if "/resource_redirect/downloads/" in href or href.endswith(".pdf"):
                    download_link = href
                    break

    if not download_link:
        print("Instruction text found but no button link yet.")
        return

    if download_link.startswith("/"):
        download_link = "https://mami-costurera.mykajabi.com" + download_link

    # 3. Verificar historial por nombre de archivo (para ignorar hashes dinámicos)
    # Ejemplo: '50a3e0f-..._Short_deportivo.pdf' -> guardamos 'Short_deportivo.pdf'
    raw_file_name = download_link.split("/")[-1].split("?")[0]
    # Intentar extraer el nombre real quitando el hash inicial (Kajabi suele usar 'hash_NombreArchivo.pdf')
    if "_" in raw_file_name:
        base_file_name = "_".join(raw_file_name.split("_")[1:])
    else:
        base_file_name = raw_file_name

    if base_file_name in history.get("filenames", []):
        print(f"Pattern {base_file_name} was already sent. Skipping.")
        return

    # 4. Descargar y Enviar
    file_name = raw_file_name
    if not file_name.endswith(".pdf"): file_name += ".pdf"

    print(f"NEW Pattern found! Downloading: {file_name}")
    pdf_response = requests.get(download_link)
    with open(file_name, "wb") as f:
        f.write(pdf_response.content)

    print("Sending to Telegram...")
    res = send_to_telegram(file_name, "¡Nuevo patrón encontrado! 🧵")

    if res.get("ok"):
        print("Success! Adding to history.")
        if "filenames" not in history:
            history["filenames"] = []
        history["filenames"].append(base_file_name)
        # Mantener compatibilidad con URLs si es necesario, pero usar filenames para el check
        if "urls" not in history: history["urls"] = []
        history["urls"].append(download_link)
        save_history(history)
    else:
        print(f"Failed to send: {res}")

if __name__ == "__main__":
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Config Error: Tokens missing.")
    else:
        scrape_and_download()
