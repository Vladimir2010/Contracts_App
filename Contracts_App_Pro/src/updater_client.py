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
CURRENT_APP_VERSION = "1.1.4"

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
    Проверява GitHub API за най-новия Release.
    Връща (has_update, new_version, download_url, release_notes)
    """
    api_url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
    
    log_message(f"--- СТАРТ НА ПРОВЕРКА (API) ---")
    log_message(f"Текуща версия: {CURRENT_APP_VERSION}")
    log_message(f"API URL: {api_url}")

    try:
        req = urllib.request.Request(api_url)
        req.add_header('User-Agent', 'ContractsApp-Updater')
        
        if GITHUB_ACCESS_TOKEN:
            req.add_header('Authorization', f'token {GITHUB_ACCESS_TOKEN}')
            
        log_message("Изпращане на заявка към GitHub API...")
        response = urllib.request.urlopen(req, timeout=10)
        
        data = json.loads(response.read().decode('utf-8'))
        
        # GitHub Release таговете обикновено са "v1.1.3", махаме 'v' ако го има
        tag_name = data.get("tag_name", "0.0.0")
        server_version = tag_name.lstrip('v')
        release_notes = data.get("body", "")
        
        # Намираме asset-а (инсталатора)
        assets = data.get("assets", [])
        download_url = ""
        for asset in assets:
            if asset.get("name") == "ContractsApp_Setup.exe":
                # ВАЖНО: За частни хранилища ни трябва url на самия asset (API url)
                download_url = asset.get("url")
                break
        
        log_message(f"Версия на сървъра: {server_version}")
        
        if server_version > CURRENT_APP_VERSION:
            if not download_url:
                log_message("ГРЕШКА: Намерен е ъпдейт, но липсва инсталатор ContractsApp_Setup.exe в релийза!")
                return False, CURRENT_APP_VERSION, "", ""
                
            log_message("Намерен е ъпдейт!")
            return True, server_version, download_url, release_notes
            
        log_message("Няма нова версия.")
        return False, CURRENT_APP_VERSION, "", "Имате най-новата версия."
        
    except Exception as e:
        log_message(f"КРИТИЧНА ГРЕШКА API: {str(e)}")
        import traceback
        log_message(traceback.format_exc())
        return False, CURRENT_APP_VERSION, "", f"Грешка: {str(e)}"

def download_and_install_update(download_url, access_token=None):
    """
    Изтегля инсталатора от GitHub API Asset URL.
    """
    import tempfile
    
    # Решаваме къде да запазим новия .exe инсталатор
    temp_dir = tempfile.gettempdir()
    installer_path = os.path.join(temp_dir, "ContractsApp_Update_Setup.exe")
    
    log_message(f"--- СТАРТ НА ИЗТЕГЛЯНЕ (API Asset) ---")
    log_message(f"Дестинация: {installer_path}")
    
    try:
        req = urllib.request.Request(download_url)
        req.add_header('User-Agent', 'ContractsApp-Updater')
        
        if access_token:
            log_message("Използва се Access Token за оторизация.")
            req.add_header('Authorization', f'token {access_token}')
            # GitHub изисква ТОЗИ хедър, за да изпрати самия файл, а не метаданни!
            req.add_header('Accept', 'application/octet-stream') 
            
        log_message("Свързване с GitHub API за изтегляне на файл...")
        with urllib.request.urlopen(req, timeout=60) as response:
            status = response.getcode()
            log_message(f"Статус отговор: {status}")
            
            # Четене на съдържанието
            content = response.read()
            size = len(content)
            log_message(f"Изтеглени са {size} байта.")
            
            with open(installer_path, 'wb') as out_file:
                out_file.write(content)
                
        log_message("Файлът е запазен успешно.")
            
        log_message("Стартиране на инсталатора...")
        if os.name == 'nt':
            subprocess.Popen([installer_path], shell=True)
            log_message("subprocess.Popen() изпълнен.")
            
        log_message("Самоизключване на програмата за ъпдейт...")
        time.sleep(1)
        sys.exit(0)
        
    except Exception as e:
        log_message(f"Грешка при изтегляне/инсталиране: {str(e)}")
        import traceback
        log_message(traceback.format_exc())
        return False

# Само за директно тестване на този файл
if __name__ == "__main__":
    has_update, new_ver, url, notes = check_for_updates()
    print(f"Има ъпдейт: {has_update}")
    print(f"Нова версия: {new_ver}")
    print(f"Линк: {url}")
    print(f"Бележки: {notes}")
