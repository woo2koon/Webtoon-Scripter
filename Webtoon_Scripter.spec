# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Webtoon_Scripter',
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
    icon=['app_icon/Webtoon_script_manager_icon.icns'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Webtoon_Scripter',
)
app = BUNDLE(
    coll,
    name='Webtoon Scripter.app',
    icon='app_icon/Webtoon_script_manager_icon.icns',
    bundle_identifier='com.woo2koon.webtoonscripter',
    info_plist={
        'CFBundleName': 'Webtoon Scripter',
        'CFBundleDisplayName': 'Webtoon Scripter',
        'CFBundleShortVersionString': '2.5.5',
        'CFBundleVersion': '2.5.5',
        'NSPrincipalClass': 'NSApplication'
    }
)
