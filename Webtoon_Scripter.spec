# -*- mode: python ; coding: utf-8 -*-
import sys

# OS 플랫폼별 빌드 아이콘 분기 설정 (Windows: .ico, macOS: .icns)
app_icon = 'app_icon/webtoon_scripter_icon_windows.ico' if sys.platform == 'win32' else 'app_icon/webtoon_scripter_icon_mac.icns'

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets'), ('app_icon', 'app_icon'), ('app_icons', 'app_icons')],
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
    # argv_emulation=False: PySide6 + macOS 13+(Ventura) 환경에서
    # True로 설정 시 NSAppleEventManager와 충돌하여 NSApplication 초기화 순서가 깨질 수 있음.
    # About 메뉴 바인딩은 코드 레벨(_bind_macos_about_menu)에서 해결하므로 False가 안전함.
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[app_icon],
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
if sys.platform == 'darwin':
    app = BUNDLE(
        coll,
        name='Webtoon Scripter.app',
        icon='app_icon/webtoon_scripter_icon_mac.icns',
        bundle_identifier='com.woo2koon.webtoonscripter',
        info_plist={
            # 기본 앱 식별 정보
            'CFBundleName': 'Webtoon Scripter',
            'CFBundleDisplayName': 'Webtoon Scripter',
            'CFBundleExecutable': 'Webtoon_Scripter',
            'CFBundleShortVersionString': '3.0.1',
            'CFBundleVersion': '3.0.1',
            'CFBundleIdentifier': 'com.woo2koon.webtoonscripter',
            # macOS가 About 메뉴에 표시하는 저작권 문자열
            # NSHumanReadableCopyright가 있어야 macOS가 앱을 완전한 네이티브 앱으로 인식함
            'NSHumanReadableCopyright': '© 2026 PAK JINWOO. All rights reserved.',
            # Retina 디스플레이 고해상도 지원 명시
            'NSHighResolutionCapable': True,
            # NSApplication 진입점 (Qt 앱 필수)
            'NSPrincipalClass': 'NSApplication',
            # 최소 macOS 버전 (Ventura 이상)
            'LSMinimumSystemVersion': '13.0',
        }
    )


