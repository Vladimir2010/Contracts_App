# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

# List of assets to bundle (relative to root)
# Format: (source_path, destination_folder_in_bundle)
added_files = [
    ('logo-d-d.jpg', '.'),
    ('vladpos_logo.png', '.'),
    ('LD/bg_places_flat.json', 'LD'),
    ('1 Профинанс Д и Д ЕООД.docx', '.'),
    ('Заявка за фискализация.docx', '.'),
    ('RegCert_DY432051.docx', '.'),
    ('DeregProtocol_DT123456.docx', '.'),
]

a = Analysis(
    ['LD/main.py'],
    pathex=[],
    binaries=[],
    datas=added_files,
    hiddenimports=['win32com.client', 'pythoncom', 'requests', 'pandas', 'openpyxl', 'docx', 'reportlab'],
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
    name='ContractsApp',
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
    icon=['vladpos_logo.png'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ContractsApp',
)
