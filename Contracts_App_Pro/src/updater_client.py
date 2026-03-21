import os
import sys
import json
import urllib.request
import subprocess
import time
from urllib.error import URLError

# ==============================================================================
# КОНФИГУРАЦИЯ ЗА ЪПДЕЙТИТЕ
# ==============================================================================
CURRENT_APP_VERSION = "1.1.6"

# Информация за Вашето GitHub хранилище
GITHUB_OWNER = "Vladimir2010"
GITHUB_REPO = "ContractsApp_Releases"

# Токенът се чете от системна среда (environment variable), НЕ е записан в кода.
# Задайте: setx GITHUB_ACCESS_TOKEN "вашия_токен" (Windows) или export GITHUB_ACCESS_TOKEN="вашия_токен" (Linux/macOS)
GITHUB_ACCESS_TOKEN = os.environ.get("GITHUB_ACCESS_TOKEN", "")
# ==============================================================================

def log_message(msg):
    try:
        # Логваме в папката на програмата
        with open("updater_log.txt", "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} - {msg}\n")
    except:
        pass
    print(msg)

def check_for_updates():
    """
    Проверява за нова версия. Първо опитва директно version.json, 
    ако не успее - ползва GitHub API за последния Release.
    Връща (has_update, new_version, download_url, release_notes)
    """
    raw_version_url = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/main/version.json"
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    
    log_message(f"--- СТАРТ НА ПРОВЕРКА ---")
    log_message(f"Текуща версия: {CURRENT_APP_VERSION}")
    
    # 1. Опит за взимане от version.json (най-актуална информация)
    try:
        log_message(f"Опит за четене на version.json от {raw_version_url}...")
        req = urllib.request.Request(raw_version_url)
        req.add_header('User-Agent', 'ContractsApp-Updater')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            server_version = data.get("version", "0.0.0").lstrip('v')
            download_url = data.get("url", "")
            release_notes = data.get("release_notes", "")
            
            log_message(f"Версия от version.json: {server_version}")
            
            if server_version > CURRENT_APP_VERSION:
                log_message("Намерен е ъпдейт във version.json!")
                return True, server_version, download_url, release_notes
    except Exception as e:
        log_message(f"Предупреждение: Неуспех при четене на version.json ({e}). Проба през GitHub API...")

    # 2. Fallback: GitHub API Release Latest
    try:
        req = urllib.request.Request(api_url)
        req.add_header('User-Agent', 'ContractsApp-Updater')
        
        if GITHUB_ACCESS_TOKEN:
            req.add_header('Authorization', f'token {GITHUB_ACCESS_TOKEN}')
            
        log_message("Изпращане на заявка към GitHub API...")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            tag_name = data.get("tag_name", "0.0.0")
            server_version = tag_name.lstrip('v')
            release_notes = data.get("body", "")
            
            # Намираме asset-а (инсталатора)
            assets = data.get("assets", [])
            download_url = ""
            for asset in assets:
                if asset.get("name") == "ContractsApp_Setup.exe":
                    download_url = asset.get("url")
                    break
            
            log_message(f"Версия от GitHub API: {server_version}")
            
            if server_version > CURRENT_APP_VERSION:
                if not download_url:
                    log_message("ГРЕШКА: Намерен е ъпдейт, но липсва инсталатор в релийза!")
                    return False, CURRENT_APP_VERSION, "", ""
                return True, server_version, download_url, release_notes
        
        log_message("Няма нова версия.")
        return False, CURRENT_APP_VERSION, "", "Имате най-новата версия."
        
    except Exception as e:
        log_message(f"КРИТИЧНА ГРЕШКА при проверка: {str(e)}")
        return False, CURRENT_APP_VERSION, "", f"Грешка: {str(e)}"

def download_and_install_update(download_url, access_token=None, progress_callback=None):
    """
    Изтегля инсталатора на части (chunks) и го стартира.
    progress_callback: функция, която приема (current_bytes, total_bytes)
    """
    import tempfile
    
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "ContractsApp_Update_Setup.exe")
    
    log_message(f"--- СТАРТ НА ИЗТЕГЛЯНЕ ---")
    log_message(f"Дестинация: {installer_path}")
    
    try:
        req = urllib.request.Request(download_url)
        req.add_header('User-Agent', 'ContractsApp-Updater')
        
        if access_token:
            req.add_header('Authorization', f'token {access_token}')
            req.add_header('Accept', 'application/octet-stream') 
            
        log_message("Свързване за изтегляне на файл...")
        with urllib.request.urlopen(req, timeout=60) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            log_message(f"Общ размер: {total_size} байта")
            
            downloaded = 0
            block_size = 8192
            
            with open(installer_path, 'wb') as out_file:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    
                    downloaded += len(buffer)
                    out_file.write(buffer)
                    
                    if progress_callback:
                        progress_callback(downloaded, total_size)
                    
            log_message(f"Изтеглени са {downloaded} байта. Успех.")
            
        log_message("Стартиране на инсталатора...")
        if os.name == 'nt':
            # Стартираме инсталатора и излизаме
            subprocess.Popen([installer_path], shell=True)
            log_message("Инсталаторът е стартиран.")
            
        # Малка пауза, за да сме сигурни, че инсталаторът е поел контрола
        time.sleep(1.5)
        log_message("Край на процеса. Изход.")
        sys.exit(0)
        
    except Exception as e:
        log_message(f"Грешка при изтегляне/инсталиране: {str(e)}")
        return False

# Само за директно тестване на този файл
if __name__ == "__main__":
    has_update, new_ver, url, notes = check_for_updates()
    print(f"Има ъпдейт: {has_update}")
    print(f"Нова версия: {new_ver}")
    print(f"Линк: {url}")
    print(f"Бележки: {notes}")
