import os
import sys
import zipfile
import shutil
import winshell
import ctypes
from win32com.client import Dispatch

def msg_box(title, text, style=0):
    """
    Simple Windows Message Box
    Styles: 0=OK, 1=OKCancel, 4=YesNo
    Returns: 1=OK, 2=Cancel, 6=Yes, 7=No
    """
    return ctypes.windll.user32.MessageBoxW(0, text, title, style)

def select_folder(title):
    """Simple folder selection using tkinter (standard library)"""
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw() # Hide main window
    folder = filedialog.askdirectory(title=title)
    root.destroy()
    return folder

def create_shortcut(target_exe, shortcut_path, icon_path):
    """Create a Windows desktop shortcut"""
    try:
        shell = Dispatch('WScript.Shell')
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.Targetpath = target_exe
        shortcut.WorkingDirectory = os.path.dirname(target_exe)
        shortcut.IconLocation = icon_path
        shortcut.save()
        return True
    except Exception as e:
        return False

def install():
    app_name = "ContractsApp"
    zip_name = f"{app_name}.zip"
    
    # 1. Check if ZIP exists
    if not os.path.exists(zip_name):
        msg_box("Грешка", f"Файлът {zip_name} не бе намерен!\nМоля, поставете инсталатора до ZIP архива.", 0)
        return

    # 2. Determine installation path
    default_install_path = os.path.join(os.environ['LOCALAPPDATA'], app_name)
    
    prompt = f"Желаете ли да инсталирате програмата в:\n{default_install_path}?"
    # 4 = YesNo
    choice = msg_box("Инсталация", prompt, 4)
    
    install_path = default_install_path
    if choice == 7: # No
        install_path = select_folder("Изберете папка за инсталация")
        if not install_path:
            return # User cancelled

    # 3. Extracting
    if os.path.exists(install_path):
        # Optional: Ask to overwrite
        res = msg_box("Предупреждение", "Папката вече съществува. Да я презапиша ли?", 4)
        if res == 7: return
        
        try:
            shutil.rmtree(install_path)
        except Exception as e:
            msg_box("Грешка", f"Неуспешно почистване на стара инсталация: {e}", 0)

    os.makedirs(install_path, exist_ok=True)
    
    try:
        with zipfile.ZipFile(zip_name, 'r') as zip_ref:
            zip_ref.extractall(install_path)
    except Exception as e:
        msg_box("Грешка", f"Грешка при разархивиране: {e}", 0)
        return

    # 4. Create Shortcut
    desktop = winshell.desktop()
    target_exe = os.path.join(install_path, "ContractsApp.exe")
    shortcut_path = os.path.join(desktop, "Contracts App.lnk")
    
    create_shortcut(target_exe, shortcut_path, target_exe)
    
    msg_box("Готово", "Инсталацията приключи успешно!\nСъздадена е икона на работния плот.", 0)

if __name__ == "__main__":
    install()
