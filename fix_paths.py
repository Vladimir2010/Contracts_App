import os
import glob

src_dir = r"c:\Users\Dell\PycharmProjects\Contracts_App\Contracts_App_Pro\src"
files = ["database.py", "main.py", "dialogs.py", "sync_manager.py", "super_admin_manager.py"]

for fname in files:
    path = os.path.join(src_dir, fname)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Import get_data_root
    content = content.replace("from path_utils import get_app_root", "from path_utils import get_app_root, get_data_root")
    
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "get_app_root()" in line:
            if "\"data\"" in line or "\"backups\"" in line or "\"Generated\"" in line or "\"temp_expiring_report" in line or "'data'" in line:
                lines[i] = line.replace("get_app_root()", "get_data_root()")
            elif "app_root =" in line and ("database.py" in fname or "dialogs.py" in fname):
                if i+1 < len(lines) and "backups" in lines[i+1]:
                    lines[i] = line.replace("get_app_root()", "get_data_root()")
    
    content = "\n".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

print("Paths updated successfully.")
