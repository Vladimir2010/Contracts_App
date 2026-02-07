import os
import shutil
import zipfile
import json
from datetime import datetime
from path_utils import get_app_root

# Note: In a real environment, you would use google-api-python-client
# For this implementation, we provide the logic to prepare the backup file
# and a placeholder for the upload logic which can be hooked into the Drive API.

def get_backup_config():
    """Load backup settings from settings.json"""
    config_path = os.path.join(get_app_root(), "data", "settings.json")
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            settings = json.load(f)
            return settings.get("backup", {})
    return {}

def create_local_zip_backup():
    """Create a zipped backup of the database"""
    from database import DB_PATH
    if not os.path.exists(DB_PATH):
        return None
        
    backup_dir = os.path.join(get_app_root(), "backups", "temp")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_name = f"contracts_cloud_sync_{timestamp}.zip"
    zip_path = os.path.join(backup_dir, zip_name)
    
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(DB_PATH, os.path.basename(DB_PATH))
        
    return zip_path

def upload_to_google_drive(file_path):
    """
    Placeholder for Google Drive upload logic.
    Requires: google-auth, google-auth-oauthlib, google-api-python-client
    """
    config = get_backup_config()
    if not config.get("google_drive_enabled"):
        return False, "Google Drive backup is disabled in settings."
    
    # In a real implementation, you would:
    # 1. Load credentials from a token file
    # 2. Refresh tokens if expired
    # 3. Use the Drive API to upload the file to a specific folder
    
    print(f"DEBUG: Simulating upload of {file_path} to Google Drive...")
    # For now, we simulate success if enabled
    return True, "Успешно архивиране в Google Drive (Симулация)"

def upload_to_dropbox(file_path):
    """Upload file to Dropbox using the API"""
    config = get_backup_config()
    if not config.get("dropbox_enabled"):
        return False, "Dropbox backup is disabled in settings."
    
    token = config.get("dropbox_token")
    if not token:
        return False, "Dropbox token is missing."
    
    import requests
    import json
    
    url = "https://content.dropboxapi.com/2/files/upload"
    headers = {
        "Authorization": f"Bearer {token}",
        "Dropbox-API-Arg": json.dumps({
            "path": f"/backups/{os.path.basename(file_path)}",
            "mode": "add",
            "autorename": True,
            "mute": False,
            "strict_conflict": False
        }),
        "Content-Type": "application/octet-stream",
    }
    
    try:
        with open(file_path, "rb") as f:
            response = requests.post(url, headers=headers, data=f, timeout=60)
            
        if response.status_code == 200:
            return True, "Успешно архивиране в Dropbox"
        else:
            return False, f"Грешка от Dropbox: {response.text}"
    except Exception as e:
        return False, f"Грешка при качване: {e}"

def run_cloud_backup():
    """High-level function to trigger cloud backup"""
    config = get_backup_config()
    if not config.get("google_drive_enabled") and not config.get("dropbox_enabled"):
        return
        
    zip_path = create_local_zip_backup()
    if not zip_path:
        return
        
    if config.get("google_drive_enabled"):
        success, msg = upload_to_google_drive(zip_path)
        print(f"Cloud Backup (GDrive): {msg}")
        
    if config.get("dropbox_enabled"):
        success, msg = upload_to_dropbox(zip_path)
        print(f"Cloud Backup (Dropbox): {msg}")
    
    # Keep local copy in backups/
    final_dir = os.path.join(get_app_root(), "backups", "cloud_archives")
    os.makedirs(final_dir, exist_ok=True)
    shutil.move(zip_path, os.path.join(final_dir, os.path.basename(zip_path)))
