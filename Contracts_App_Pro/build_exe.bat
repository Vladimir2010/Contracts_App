@echo off
echo [1/3] Installing requirements...
pip install -r requirements.txt

echo [2/3] Building Executable with PyInstaller...
pyinstaller ContractsApp.spec --noconfirm

echo [3/3] Build finished!
echo Output is in the 'dist/ContractsApp_v1' directory.
pause
