import sys
import time
import urllib.request
import os
import subprocess

if len(sys.argv) < 2:
    print("Грешка: Updater-ът трябва да се стартира от основната програма с линк към новата версия!")
    time.sleep(3)
    sys.exit(1)

download_url = sys.argv[1]

print("\n--- UPDATER СТАРТИРАН ---")
print("[4] Изчакваме 2 секунди старата версия (1.0) да се затвори напълно...")
time.sleep(2)

print(f"[5] Теглене на новите файлове от сървъра ({download_url})...")
try:
    # 2. Теглим новия app.py и презаписваме стария
    urllib.request.urlretrieve(download_url, "app.py")
    print(">>> Файловете са обновени успешно на Версия 2.0! <<<")
    
    print("\n[6] Стартиране на вече обновената програма...")
    # Отваряме обновения файл в нов прозорец
    if os.name == 'nt':
        subprocess.Popen(['start', 'cmd', '/c', sys.executable, "app.py"], shell=True)
    else:
        subprocess.Popen([sys.executable, "app.py"])
    
except Exception as e:
    print(f"Грешка при тегленето на ъпдейта: {e}")
    time.sleep(5)

print("[7] Updater-ът приключи работата си успешно и се самоизключва.")
time.sleep(2)
