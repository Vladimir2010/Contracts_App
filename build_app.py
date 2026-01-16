import os
import shutil
import subprocess
import sys

def build():
    print("--- Starting Contracts App Build Process ---")
    
    # 1. Cleanup
    dirs_to_clean = ['build', 'dist']
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"Cleaning {d}...")
            shutil.rmtree(d)
    
    # 2. Run PyInstaller
    print("Running PyInstaller...")
    try:
        subprocess.check_call(['pyinstaller', '--noconfirm', 'ContractsApp.spec'])
    except subprocess.CalledProcessError as e:
        print(f"Error during PyInstaller execution: {e}")
        return
    except FileNotFoundError:
        print("Error: PyInstaller not found. Please install it with 'pip install pyinstaller'")
        return

    # 3. Verification
    exe_path = os.path.join('dist', 'ContractsApp', 'ContractsApp.exe')
    if os.path.exists(exe_path):
        print("\nSUCCESS!")
        print(f"Executable created at: {os.path.abspath(exe_path)}")
        print("Final Steps:")
        print("1. Copy 'dist/ContractsApp' to your installation folder.")
        print("2. Run ContractsApp.exe to start the application.")
    else:
        print("\nBuild completed, but executable not found. Check the output logs.")

if __name__ == "__main__":
    build()
