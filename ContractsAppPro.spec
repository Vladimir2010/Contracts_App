# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# List of assets to bundle
# Paths are relative to the root where PyInstaller is run
added_files = [
    ('Contracts_App_Pro/resources/*', 'resources'),
    ('Contracts_App_Pro/data/*', 'data'),
]

a = Analysis(
    ['Contracts_App_Pro/src/main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'win32com.client', 'pythoncom', 'requests', 'pandas', 'openpyxl', 
        'docx', 'reportlab', 'PyQt6', 'sqlite3', 'json', 'hashlib', 'binascii'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'unittest', 'pydoc'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ContractsAppPro',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='Contracts_App_Pro/resources/vladpos_logo.png',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ContractsAppPro',
)
