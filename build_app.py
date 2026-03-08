
import os
import subprocess
import sys

def build():
    # Configuration
    project_root = os.path.dirname(os.path.abspath(__file__))
    main_script = os.path.join(project_root, "Contracts_App_Pro", "src", "main.py")
    version_file = os.path.join(project_root, "version_info.txt")
    icon_file = os.path.join(project_root, "Contracts_App_Pro", "resources", "vladpos_logo.ico")
    
    # Check if files exist
    if not os.path.exists(main_script):
        print(f"Error: Main script not found at {main_script}")
        return
    
    # PyInstaller command
    cmd = [
        "pyinstaller",
        "--noconfirm",
        "--onefile",
        "--windowed", # No console
        f"--icon={icon_file}" if os.path.exists(icon_file) else "",
        f"--version-file={version_file}" if os.path.exists(version_file) else "",
        # Add data folders
        f"--add-data=Contracts_App_Pro/src;src",
        f"--add-data=Contracts_App_Pro/resources;resources",
        # Name of the output
        "--name=ContractsAppPro",
        main_script
    ]
    
    # Remove empty strings from cmd
    cmd = [c for c in cmd if c]
    
    print("Starting build process...")
    print(f"Command: {' '.join(cmd)}")
    
    try:
        subprocess.check_call(cmd)
        print("\n" + "="*50)
        print("BUILD SUCCESSFUL!")
        print("Your professional executable is in the 'dist' folder.")
        print("="*50)
    except subprocess.CalledProcessError as e:
        print(f"Build failed with error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    # Check if pyinstaller is installed
    try:
        import PyInstaller
    except ImportError:
        print("PyInstaller is not installed. Please run: pip install pyinstaller")
        sys.exit(1)
        
    build()
