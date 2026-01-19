import os
import shutil
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PRO_DIR = os.path.join(BASE_DIR, "Contracts_App_Pro")
SRC_DIR = os.path.join(PRO_DIR, "src")
DATA_DIR = os.path.join(PRO_DIR, "data")
RES_DIR = os.path.join(PRO_DIR, "resources")
GEN_DIR = os.path.join(PRO_DIR, "Generated")

def setup():
    print(f"Setting up Contracts_App_Pro at {PRO_DIR}...")
    
    # 1. Create structure
    for d in [SRC_DIR, DATA_DIR, RES_DIR, GEN_DIR]:
        os.makedirs(d, exist_ok=True)
        
    # 2. Copy Code (LD/*.py -> src/)
    ld_dir = os.path.join(BASE_DIR, "LD")
    print(f"Copying code from {ld_dir}...")
    for f in os.listdir(ld_dir):
        if f.endswith(".py"):
            src_f = os.path.join(ld_dir, f)
            dst_f = os.path.join(SRC_DIR, f)
            shutil.copy2(src_f, dst_f)
            
    # 3. Copy Data (data/* -> data/)
    root_data = os.path.join(BASE_DIR, "data")
    if os.path.exists(root_data):
        print(f"Copying data from {root_data}...")
        for f in os.listdir(root_data):
            shutil.copy2(os.path.join(root_data, f), DATA_DIR)
    else:
        print("Root data not found, trying LD/data...")
        ld_data = os.path.join(ld_dir, "data")
        if os.path.exists(ld_data):
            for f in os.listdir(ld_data):
                shutil.copy2(os.path.join(ld_data, f), DATA_DIR)

    # 4. Copy Resources (*.doc*, *.json -> resources/)
    # From ROOT
    print("Copying resources from root...")
    for f in os.listdir(BASE_DIR):
        if f.endswith((".docx", ".doc", ".json")) and "package" not in f and "settings.json" not in f:
            shutil.copy2(os.path.join(BASE_DIR, f), RES_DIR)
            
    # From LD
    print("Copying resources from LD...")
    for f in os.listdir(ld_dir):
        if f.endswith((".docx", ".doc", ".json")) and "settings.json" not in f:
            shutil.copy2(os.path.join(ld_dir, f), RES_DIR)
            
    # 5. Overwrite path_utils.py
    print("Refactoring path_utils.py...")
    path_utils_code = """import os
import sys

def get_app_root():
    # Returns Contracts_App_Pro root
    # src/path_utils.py -> dirname -> dirname -> Pro
    if hasattr(sys, 'frozen'):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    # Returns path in resources/ folder
    # Absolute paths are returned as-is by os.path.join
    base = get_app_root()
    return os.path.join(base, "resources", relative_path)
"""
    with open(os.path.join(SRC_DIR, "path_utils.py"), "w", encoding="utf-8") as f:
        f.write(path_utils_code)
        
    # 6. Create requirements.txt
    print("Creating requirements.txt...")
    reqs = """PyQt6
pandas
openpyxl
requests
python-docx
reportlab
pywin32
"""
    with open(os.path.join(PRO_DIR, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(reqs)
    
    # 7. Create run_app.bat
    print("Creating run_app.bat...")
    bat_code = """@echo off
pushd %~dp0
python src/main.py
popd
pause
"""
    with open(os.path.join(PRO_DIR, "run_app.bat"), "w") as f:
        f.write(bat_code)

    print("Success! Project cloned to Contracts_App_Pro.")

if __name__ == "__main__":
    setup()
