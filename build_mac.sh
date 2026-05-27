#!/bin/bash
# build_mac.sh
# macOS 빌드 스크립트 - Finder 캐시 버스팅 및 서명 포함
set -e

APP_NAME="Webtoon Scripter"
APP_PATH="dist/${APP_NAME}.app"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Webtoon Scripter macOS 빌드 시작"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── 1. 기존 dist 완전 제거 (Finder 캐시 버스팅) ──────────────────
# macOS는 앱 번들을 LaunchServices DB에 캐싱함.
# 기존 dist를 삭제하지 않으면 이전 버전의 메뉴 설정이 캐시에 남아
# About 메뉴 비활성화 등의 문제가 지속될 수 있음.
echo "▶ 기존 빌드 결과물 제거 중..."
rm -rf dist/
echo "  완료"

# ── 2. PyInstaller 빌드 ──────────────────────────────────────────
echo "▶ PyInstaller 빌드 중..."
venv/bin/pyinstaller --noconfirm Webtoon_Scripter.spec
echo "  빌드 완료"

# ── 3. ._* 메타데이터 파일 제거 (외장 드라이브 서명 버그 방지) ─────
# 외장 드라이브(exFAT/FAT32)에서 macOS가 생성하는 ._ 파일들이
# codesign --deep 실행 시 "Operation not permitted" 오류를 일으킴.
echo "▶ 메타데이터 파일(._*) 제거 중..."
find "${APP_PATH}" -name "._*" -delete 2>/dev/null || true
echo "  완료"

# ── 4. 임시 서명 적용 ────────────────────────────────────────────
echo "▶ 코드 서명 적용 중..."
codesign --force --deep --sign - "${APP_PATH}"
echo "  서명 완료"

# ── 5. LaunchServices DB 강제 갱신 (Finder 캐시 무효화) ──────────
# macOS LaunchServices가 새 앱 번들을 인식하도록 DB를 재등록.
# 이 단계를 건너뛰면 Finder가 이전 버전의 앱 메뉴 정보를 캐시에서
# 읽어와 About 메뉴 등이 여전히 비활성화된 것처럼 보일 수 있음.
echo "▶ LaunchServices DB 캐시 강제 갱신 중..."
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister \
    -f "${APP_PATH}" 2>/dev/null || true
echo "  완료"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 빌드 성공: ${APP_PATH}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
