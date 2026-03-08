import os
import sys

def get_app_root():
    # Returns Contracts_App_Pro root for resources (read-only)
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        if hasattr(sys, '_MEIPASS'):
            return sys._MEIPASS
        # Fallback for some onedir builds
        return os.path.dirname(sys.executable)
    # Dev mode
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_data_root():
    # Returns root for persistent data (db, settings, backups, generated reports)
    if getattr(sys, 'frozen', False):
        # Always return the folder where the .exe is.
        return os.path.dirname(sys.executable)
    # Dev mode
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    # Returns path in resources/ folder
    # Absolute paths are returned as-is by os.path.join
    base = get_app_root()
    return os.path.join(base, "resources", relative_path)
