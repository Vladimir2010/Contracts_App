import os
import shutil
import sys

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Source (Pro version is cleaner)
SRC_PRO = os.path.join(BASE_DIR, "Contracts_App_Pro", "src")
DATA_PRO = os.path.join(BASE_DIR, "Contracts_App_Pro", "data")
RES_PRO = os.path.join(BASE_DIR, "Contracts_App_Pro", "resources")

# Destination
WEB_DIR = os.path.join(BASE_DIR, "Contracts_App_Web")
BACKEND_DIR = os.path.join(WEB_DIR, "backend")
FRONTEND_DIR = os.path.join(WEB_DIR, "frontend")

FILES_TO_COPY = [
    "database.py", 
    "auth.py", 
    "contract_generator.py", 
    "date_utils.py", 
    "bim_loader.py", 
    "importer.py",
    "vat_check.py",
    "export_word.py",
    "export_pdf.py",
    "export_excel.py"
]

def setup_backend():
    print(f"Setting up Backend in {BACKEND_DIR}...")
    os.makedirs(BACKEND_DIR, exist_ok=True)
    
    # 1. Copy Logic Files
    if not os.path.exists(SRC_PRO):
        print(f"Error: Source directory {SRC_PRO} not found!")
        return

    for f in FILES_TO_COPY:
        src = os.path.join(SRC_PRO, f)
        dst = os.path.join(BACKEND_DIR, f)
        if os.path.exists(src):
            shutil.copy2(src, dst)
            print(f"Copied {f}")
        else:
            print(f"Warning: {f} not found in source.")

    # 2. Copy Data and Resources
    print("Copying Data and Resources...")
    shutil.copytree(DATA_PRO, os.path.join(BACKEND_DIR, "data"), dirs_exist_ok=True)
    shutil.copytree(RES_PRO, os.path.join(BACKEND_DIR, "resources"), dirs_exist_ok=True)
    os.makedirs(os.path.join(BACKEND_DIR, "Generated"), exist_ok=True)

    # 3. Create Web-Specific path_utils.py
    print("Creating web path_utils.py...")
    path_utils_content = """import os
import sys

def get_app_root():
    # In web version, root is the backend folder
    return os.path.dirname(os.path.abspath(__file__))

def get_resource_path(relative_path):
    # Resources are in the resources/ subfolder
    return os.path.join(get_app_root(), "resources", relative_path)
"""
    with open(os.path.join(BACKEND_DIR, "path_utils.py"), "w", encoding="utf-8") as f:
        f.write(path_utils_content)

    # 4. Create main.py (FastAPI App)
    print("Creating main.py (FastAPI)...")
    main_py_content = """from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn
import os

# Import existing logic
from database import init_db, get_all_users, get_all_devices, search_devices
from auth import verify_password, hash_password

app = FastAPI(title="Contracts App API", version="1.0.0")

# CORS (Allow Frontend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup_event():
    init_db()

@app.get("/")
def read_root():
    return {"message": "Contracts App API is running"}

@app.get("/devices")
def read_devices():
    devices = get_all_devices()
    return {"count": len(devices), "data": devices}

if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
"""
    with open(os.path.join(BACKEND_DIR, "main.py"), "w", encoding="utf-8") as f:
        f.write(main_py_content)

    # 5. Create requirements.txt
    print("Creating requirements.txt...")
    reqs = """fastapi
uvicorn
python-multipart
python-jose[cryptography]
passlib[bcrypt]
pandas
openpyxl
requests
python-docx
reportlab
pywin32
"""
    with open(os.path.join(BACKEND_DIR, "requirements.txt"), "w", encoding="utf-8") as f:
        f.write(reqs)

    print("Backend Setup Complete.")

if __name__ == "__main__":
    setup_backend()
