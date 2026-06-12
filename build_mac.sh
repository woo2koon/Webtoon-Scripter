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
python3 -m PyInstaller --noconfirm Webtoon_Scripter.spec
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

# ── 6. DMG 파일 생성 및 디자인 커스텀 ──────────────────────────────
echo "▶ DMG 파일 생성 및 배경 지정 중..."

LOCAL_TEMP_DIR="${HOME}/.webtoon_scripter_dmg_temp"
rm -rf "${LOCAL_TEMP_DIR}"
mkdir -p "${LOCAL_TEMP_DIR}/dmg_content"

# 1. 앱 복사 및 Applications 바로가기 링크 생성
cp -R "${APP_PATH}" "${LOCAL_TEMP_DIR}/dmg_content/"
ln -s /Applications "${LOCAL_TEMP_DIR}/dmg_content/Applications"

# 2. 임시 DMG 생성 (수정 가능한 UDRW 포맷)
TEMP_DMG="dist/${APP_NAME}_temp.dmg"
rm -f "${TEMP_DMG}"
hdiutil create -volname "${APP_NAME}" -srcfolder "${LOCAL_TEMP_DIR}/dmg_content" -ov -format UDRW "${TEMP_DMG}"

# 3. 임시 DMG 마운트
echo "▶ DMG 마운트 및 디자인 적용 중..."
MOUNT_DIR="/Volumes/${APP_NAME}"
hdiutil detach "${MOUNT_DIR}" 2>/dev/null || true
hdiutil attach -readwrite -noverify -noautoopen "${TEMP_DMG}"
sleep 2

# 4. 배경 이미지 폴더 생성 및 복사
mkdir -p "${MOUNT_DIR}/.background"
cp "/Volumes/Samsung_T5/DEV_HOZAKZIL/Webtoon_OCR_Dev/app_icon/스크립트 매니저 BG.png" "${MOUNT_DIR}/.background/background.png"
chflags hidden "${MOUNT_DIR}/.background"

# 5. AppleScript를 이용해 Finder 뷰 커스텀 (창 크기, 배경화면, 아이콘 배치)
osascript <<EOF
tell application "Finder"
    tell disk "${APP_NAME}"
        open
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set the bounds of container window to {100, 100, 820, 669} -- 720 x 482 inner content size (adjusted with extra height)
        set theViewOptions to the icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 96
        set background picture of theViewOptions to file ".background:background.png"
        set position of item "${APP_NAME}.app" to {165, 286}
        set position of item "Applications" to {555, 286}
        update every item
        delay 2
        close
    end tell
end tell
EOF

# 변경사항이 동기화되도록 대기 후 마운트 해제
sleep 2
hdiutil detach "${MOUNT_DIR}"

# 6. 최종 압축 DMG 생성 (UDZO 포맷)
DMG_FILE="dist/${APP_NAME}_v3.0.0.dmg"
rm -f "${DMG_FILE}"
hdiutil convert "${TEMP_DMG}" -format UDZO -imagekey zlib-level=9 -o "${DMG_FILE}"

# 임시 파일 정리
rm -f "${TEMP_DMG}"
rm -rf "${LOCAL_TEMP_DIR}"

echo "  DMG 디자인 완성: ${DMG_FILE}"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅ 빌드 및 DMG 생성 성공: ${APP_PATH}"
echo "                          ${DMG_FILE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
