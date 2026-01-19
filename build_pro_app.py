import os
import shutil
import subprocess
import sys
import zipfile

def build():
    print("--- Starting Contracts App Pro Build Process ---")
    
    # 1. Cleanup
    dirs_to_clean = ['build', 'dist']
    for d in dirs_to_clean:
        if os.path.exists(d):
            print(f"Cleaning {d}...")
            shutil.rmtree(d)
    
    # 2. Run PyInstaller
    print("Running PyInstaller...")
    try:
        subprocess.check_call(['pyinstaller', '--noconfirm', 'ContractsAppPro.spec'])
    except subprocess.CalledProcessError as e:
        print(f"Error during PyInstaller execution: {e}")
        return

    # 3. Packaging into ZIP
    print("Packaging into ZIP...")
    dist_folder = os.path.join('dist', 'ContractsAppPro')
    zip_path = 'ContractsAppPro.zip'
    
    if os.path.exists(dist_folder):
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zip_ref:
            for root, dirs, files in os.walk(dist_folder):
                for file in files:
                    file_path = os.path.join(root, file)
                    # Archive path should be relative to dist_folder
                    arcname = os.path.relpath(file_path, dist_folder)
                    zip_ref.write(file_path, arcname)
        
        print(f"\nSUCCESS!")
        print(f"Executable created in: {os.path.abspath(dist_folder)}")
        print(f"ZIP package created at: {os.path.abspath(zip_path)}")
    else:
        print("\nBuild completed, but dist/ContractsAppPro folder not found. Check the output logs.")

if __name__ == "__main__":
    build()
