# -*- mode: python ; coding: utf-8 -*-
# Empaquetador de Music Minimal Player
#
# Uso:  pyinstaller reproductor.spec --noconfirm --clean
#      dist\reproductor.exe

block_cipher = None


a = Analysis(
    ['reproductor.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # No gathers: tkinter, vlc (python-vlc) y stdlib ya se detectan solos.
    excludes=['matplotlib', 'numpy', 'PyQt5', 'PySide2', 'pytest'],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='reproductor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,          # UPX suele romper con las DLL de VLC
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,      # sin ventana de consola
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='favicon.ico',
)