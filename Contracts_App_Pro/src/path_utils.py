import os
import sys

def get_app_root():
    # Returns Contracts_App_Pro root
    if hasattr(sys, 'frozen'):
        # For PyInstaller 6+ "directory" builds, assets are often in _internal
        root = os.path.dirname(sys.executable)
        internal = os.path.join(root, "_internal")
        if os.path.exists(internal):
            return internal
        return root
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_resource_path(relative_path):
    # Returns path in resources/ folder
    # Absolute paths are returned as-is by os.path.join
    base = get_app_root()
    return os.path.join(base, "resources", relative_path)
