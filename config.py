# config.py
import os
import json
import sys

# 1. OS별 최적화된 폰트 리스트 정의
if sys.platform == "darwin":  # macOS (진우님의 M1 맥북 에어)
    # 맥에서는 윈도우 폰트를 아예 빼버려 검색 시간을 0으로 만듭니다.
    FONT_FAMILY = "'Pretendard', '-apple-system', 'Helvetica Neue', sans-serif"
else:  # Windows 또는 기타
    # 윈도우에서는 기존처럼 Segoe UI와 맑은 고딕을 포함합니다.
    FONT_FAMILY = "'Pretendard', 'Segoe UI', 'Malgun Gothic', sans-serif"

# =================================================================
# [사용자 지정 기본 키]
# 보안을 위해 실제 키는 앱 내 설정이나 별도 파일에서 관리하세요.
# =================================================================
MY_DEFAULT_OCR_KEY = ""  # <-- 여기에 직접 입력하지 마세요!
MY_DEFAULT_AI_KEY = ""   # <-- 여기에 직접 입력하지 마세요!
# =================================================================

# 1. 앱 이름 (이 이름으로 사용자의 컴퓨터에 폴더가 생깁니다)
APP_NAME = "Webtoon_Script_Manager"
APP_VERSION = "2.2.0"

if getattr(sys, 'frozen', False):
    # [읽기전용] EXE 내부에 압축된 아이콘 등 (임시 폴더)
    BUNDLE_DIR = sys._MEIPASS 
    
    # [쓰기권한] 프로젝트 저장소 (윈도우가 허락한 자유 구역: AppData)
    # 이제 'C:\Users\진우\AppData\Roaming\Webtoon_Script_Manager'를 사용합니다.
    STORAGE_DIR = os.path.join(os.environ["APPDATA"], APP_NAME)
else:
    # 개발 환경 (VS Code) - 현재 폴더 사용
    BUNDLE_DIR = STORAGE_DIR = os.path.dirname(os.path.abspath(__file__))

# --- 아래 변수명들은 기존 코드와 호환되도록 그대로 유지합니다 ---

# 2. [신의 한 수] 기존 BASE_DIR를 에셋용으로 그대로 둡니다.
# 이렇게 하면 아래의 수십 개 아이콘 경로를 하나도 안 고쳐도 됩니다!
BASE_DIR = BUNDLE_DIR 

ASSETS_DIR = os.path.join(BASE_DIR, "assets")
TEMPLATE_PATH = os.path.join(ASSETS_DIR, "template.xlsx")

PROJECTS_DIR = os.path.join(STORAGE_DIR, "projects")
SETTINGS_FILE = os.path.join(STORAGE_DIR, "settings.json")
CACHE_DIR = os.path.join(STORAGE_DIR, "cache")

# 폴더 생성 안전장치 (STORAGE_DIR 기준)
if not os.path.exists(PROJECTS_DIR):
    os.makedirs(PROJECTS_DIR)
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# =================================================================
# [신규 추가] UI 아이콘 경로 설정 (진우님이 정한 이름들)
# =================================================================
# 'assets' 폴더 안에 있는 svg 파일들과 이름을 매칭해줍니다.
ICON_MOVIE   = os.path.join(ASSETS_DIR, "movie.svg")
ICON_SAVE    = os.path.join(ASSETS_DIR, "save.svg")
ICON_UPLOAD  = os.path.join(ASSETS_DIR, "image-upload.svg")
ICON_CHECK   = os.path.join(ASSETS_DIR, "wand.svg")
ICON_FILE    = os.path.join(ASSETS_DIR, "file-image.svg")
ICON_FOLDER    = os.path.join(ASSETS_DIR, "folder.svg")
ICON_DELETE  = os.path.join(ASSETS_DIR, "trash.svg")
ICON_EXCEL   = os.path.join(ASSETS_DIR, "sheet.svg")
ICON_LINK    = os.path.join(ASSETS_DIR, "link.svg")
ICON_LIBRARY = os.path.join(ASSETS_DIR, "library.svg")
ICON_REFRESH = os.path.join(ASSETS_DIR, "refresh.svg")
ICON_ARROW_UP = os.path.join(ASSETS_DIR, "arrow-up.svg")
ICON_ARROW_DOWN = os.path.join(ASSETS_DIR, "arrow-down.svg")
ICON_KEY = os.path.join(ASSETS_DIR, "key.svg")
ICON_MENU = os.path.join(ASSETS_DIR, "menu.svg")
ICON_UNDO = os.path.join(ASSETS_DIR, "undo.svg")
ICON_REDO = os.path.join(ASSETS_DIR, "redo.svg")
# =================================================================

OCR_API_KEY = ""
AI_API_KEY = ""

API_PRESETS = {
    "Default": {"ocr": MY_DEFAULT_OCR_KEY, "ai": MY_DEFAULT_AI_KEY}
}
ACTIVE_PRESET_NAME = "Default"

# 기타 설정
AGE_OPTIONS = ["영유아", "어린이", "청소년", "청년", "중년", "노년", "미상"]
GENDER_OPTIONS = ["남성", "여성", "미상"]
ROLE_OPTIONS = ["주연", "조연", "단역"]

# [관용구 설정] 자주 쓰는 지문 리스트
IDIOMS = []

# [저장 경로 설정] 마지막으로 저장한 디렉토리 경로 기억
LAST_SAVE_DIR = ""

MODERN_STYLE = f"""
    QWidget {{
        font-family: {FONT_FAMILY};
        font-size: 14px;
        color: #1F2937;
    }}
"""

def load_settings():
    global OCR_API_KEY, AI_API_KEY, API_PRESETS, ACTIVE_PRESET_NAME, IS_SIMPLE_MODE, IDIOMS, LAST_SAVE_DIR
    IS_SIMPLE_MODE = False
    
    # 1. 일단 하드코딩된 키로 초기화
    API_PRESETS = {
        "Default": {"ocr": MY_DEFAULT_OCR_KEY, "ai": MY_DEFAULT_AI_KEY}
    }
    ACTIVE_PRESET_NAME = "Default"

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                
                if "presets" in data and isinstance(data["presets"], dict):
                    loaded_presets = data["presets"]
                    
                    # 데이터 정리 (마이그레이션)
                    cleaned_presets = {}
                    for name, value in loaded_presets.items():
                        if isinstance(value, str):
                            cleaned_presets[name] = {"ocr": value, "ai": ""}
                        elif isinstance(value, dict):
                            cleaned_presets[name] = {
                                "ocr": value.get("ocr", ""),
                                "ai": value.get("ai", "")
                            }
                        else:
                            cleaned_presets[name] = {"ocr": "", "ai": ""}
                    
                    # [핵심 로직] 불러온 데이터의 'Default'가 비어있다면, 내 키로 강제 주입
                    if "Default" in cleaned_presets:
                        if not cleaned_presets["Default"]["ocr"]:
                            cleaned_presets["Default"]["ocr"] = MY_DEFAULT_OCR_KEY
                        if not cleaned_presets["Default"]["ai"]:
                            cleaned_presets["Default"]["ai"] = MY_DEFAULT_AI_KEY
                    else:
                        # Default 프리셋이 아예 없으면 생성
                        cleaned_presets["Default"] = {"ocr": MY_DEFAULT_OCR_KEY, "ai": MY_DEFAULT_AI_KEY}

                    API_PRESETS = cleaned_presets
                    ACTIVE_PRESET_NAME = data.get("active_preset", "Default")
                    IS_SIMPLE_MODE = data.get("is_simple_mode", False)
                    IDIOMS = data.get("idioms", [])
                    LAST_SAVE_DIR = data.get("last_save_dir", "")
                
                else:
                    # 구형 데이터 구조일 경우 처리
                    old_ocr = data.get("ocr_api_key", data.get("api_key", ""))
                    old_ai = data.get("ai_api_key", "")
                    
                    # 비어있으면 하드코딩 키 사용
                    if not old_ocr: old_ocr = MY_DEFAULT_OCR_KEY
                    if not old_ai: old_ai = MY_DEFAULT_AI_KEY
                    
                    API_PRESETS = {
                        "Default": {"ocr": old_ocr, "ai": old_ai}
                    }
                    ACTIVE_PRESET_NAME = "Default"
                    
        except Exception as e:
            print(f"설정 로드 실패 (기본값 사용): {e}")

    # 활성 프리셋 키 세팅
    if ACTIVE_PRESET_NAME not in API_PRESETS:
        ACTIVE_PRESET_NAME = "Default"
        if "Default" not in API_PRESETS:
             API_PRESETS["Default"] = {"ocr": MY_DEFAULT_OCR_KEY, "ai": MY_DEFAULT_AI_KEY}

    current_set = API_PRESETS[ACTIVE_PRESET_NAME]
    
    # 안전장치
    if isinstance(current_set, str):
        current_set = {"ocr": current_set, "ai": ""}
        API_PRESETS[ACTIVE_PRESET_NAME] = current_set

    OCR_API_KEY = current_set.get("ocr", "")
    AI_API_KEY = current_set.get("ai", "")

def save_settings(presets=None, active_name=None, is_simple_mode=None):
    global OCR_API_KEY, AI_API_KEY, API_PRESETS, ACTIVE_PRESET_NAME, IS_SIMPLE_MODE, IDIOMS, LAST_SAVE_DIR
    
    if presets is not None:
        API_PRESETS = presets
    if active_name is not None:
        ACTIVE_PRESET_NAME = active_name
    if is_simple_mode is not None:
        IS_SIMPLE_MODE = is_simple_mode
    
    current_set = API_PRESETS.get(ACTIVE_PRESET_NAME, {"ocr": "", "ai": ""})
    OCR_API_KEY = current_set.get("ocr", "")
    AI_API_KEY = current_set.get("ai", "")
    
    data = {
        "presets": API_PRESETS,
        "active_preset": ACTIVE_PRESET_NAME,
        "is_simple_mode": IS_SIMPLE_MODE,
        "idioms": IDIOMS,
        "last_save_dir": LAST_SAVE_DIR
    }
    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"설정 저장 실패: {e}")

def get_initial_dir(fallback_path=""):
    """마지막 저장 경로가 있으면 반환, 없으면 기본값 반환"""
    if LAST_SAVE_DIR and os.path.exists(LAST_SAVE_DIR):
        return LAST_SAVE_DIR
    return fallback_path

def update_last_save_dir(path):
    """마지막 저장 경로를 업데이트하고 저장"""
    global LAST_SAVE_DIR
    if not path:
        return
        
    if os.path.isdir(path):
        LAST_SAVE_DIR = path
    else:
        LAST_SAVE_DIR = os.path.dirname(path)
    save_settings()

load_settings()

# [기타 설정들]
AGE_OPTIONS = ["영유아", "어린이", "청소년", "청년", "중년", "노년", "미상"]
GENDER_OPTIONS = ["남성", "여성", "미상"]
ROLE_OPTIONS = ["주연", "조연", "단역"]
EXCEL_TEMPLATE_BASE64 = ""

MODERN_STYLE = """
QWidget { font-family: 'Pretendard', 'Malgun Gothic', 'AppleGothic', sans-serif; font-size: 14px; color: #333333; }
QMainWindow { background-color: #ffffff; }
QMenuBar { background-color: white; border-bottom: 1px solid #e5e7eb; }
QMenuBar::item { padding: 8px 12px; background: transparent; color: #333; }
QMenuBar::item:selected { background-color: #f3f4f6; color: #000; }
QMenu { 
    background-color: white; 
    border: 1px solid #d1d5db; 
    border-radius: 0px; /* 메뉴창 모서리도 살짝 둥글게 하면 예쁩니다 */
    padding: 3px; 
}

QMenu::item { 
    /* 상, 우, 하, 좌 순서입니다. 좌측(40px)을 넉넉하게 주면 아이콘이 안으로 들어옵니다. */
    padding: 8px 10px 8px 22px; 
    border-radius: 4px;
    margin: 2px 5px;
}

/* [핵심 추가] 아이콘의 위치를 세밀하게 조정합니다. */
QMenu::icon {
    position: absolute;
    left: 12px; /* 아이콘을 왼쪽 끝에서 15px만큼 오른쪽으로 밀어냅니다. */
}

QMenu::item:selected { 
    background-color: #FFECEC; 
    color: #FF4B4B; 
}

QMenu::separator {
    height: 1px;
    background: #e5e7eb;
    margin: 5px 10px;
}
QWidget#Sidebar { background-color: #f8f9fa; border-right: 1px solid #e0e0e0; }
QLabel#SidebarTitle { font-size: 16px; font-weight: bold; color: #1f2937; margin: 10px 0; }
QLineEdit, QComboBox { 
    font-family: 'Pretendard'; 
    border: 1px solid #d1d5db; 
    border-radius: 6px; 
    background-color: #ffffff; 
    min-height: 38px; 
    padding-left: 12px; 
    color: #333; 
}
QLineEdit:focus, QComboBox:focus, QComboBox:on { border: 1px solid #ff4b4b; }

QComboBox::drop-down { 
    border: none; 
    background-color: #f9fafb; 
    width: 30px; 
    border-top-right-radius: 5px; 
    border-bottom-right-radius: 5px; 
}
QComboBox::down-arrow { 
    image: url(assets/dropdown-arrow.svg);
    width: 12px; 
    height: 12px; 
}
QComboBox QAbstractItemView { font-family: 'Pretendard'; border: 1px solid #d1d5db; border-radius: 4px; background-color: white; selection-background-color: #ffecec; selection-color: #ff4b4b; outline: none; }
QComboBox QAbstractItemView::item { font-family: 'Pretendard'; min-height: 30px; padding: 5px; margin: 2px 0px; }
QTableWidget { border: 1px solid #d1d5db; gridline-color: #d0d0d0; font-family: 'Pretendard', 'AppleGothic'; font-size: 10pt; selection-background-color: transparent; selection-color: black; }
QTableWidget::item:selected, QTableWidget::item:focus { border: 2px solid #ff4b4b; background-color: transparent; color: black; }
QHeaderView::section { background-color: #f0f0f0; border: none; border-right: 1px solid #d0d0d0; border-bottom: 1px solid #d0d0d0; padding: 4px; font-weight: normal; color: #333; font-family: 'Pretendard'; font-size: 10pt; }
QPushButton { background-color: #ffffff; border: 1px solid #d1d5db; border-radius: 4px; padding: 6px 16px; font-weight: bold; color: #444; }
QPushButton:hover { border-color: #ff4b4b; color: #ff4b4b; }
QPushButton:pressed { background-color: #fff0f0; }
QPushButton#PlusBtn { background-color: #ff4b4b; color: white; border: none; font-size: 20px; font-family: 'Arial'; padding: 0px 0px 4px 0px; }
QPushButton#PlusBtn:hover { background-color: #e03e3e; }
QPushButton#PrimaryBtn { background-color: #FF5722; color: white; border: none; }
QPushButton#PrimaryBtn:hover { background-color: #e03e3e; }
QPushButton#BlackBtn { background-color: #212529; color: white; border: none; padding: 12px; }
QPushButton#BlackBtn:hover { background-color: #000000; }
QTabWidget::pane { border: 1px solid #e5e7eb; border-radius: 4px; top: -1px; }
QTabBar::tab { background: transparent; border-bottom: 3px solid transparent; padding: 10px 16px; font-weight: bold; color: #888; margin-right: 4px; }
QTabBar::tab:selected { color: #ff4b4b; border-bottom: 3px solid #ff4b4b; }
QListWidget { border: 1px solid #e0e0e0; border-radius: 4px; background-color: #ffffff; padding: 5px; }
QListWidget::item { padding: 8px; border-bottom: 1px solid #f0f0f0; color: #333; }
QListWidget::item:selected { background-color: #ffecec; color: #ff4b4b; border: none; }
QLabel#ApiCountTitle { font-size: 13px; color: #666; margin-top: 10px; }
QLabel#ApiCountNum { font-size: 32px; font-weight: bold; color: #333; margin-bottom: 10px; font-family: sans-serif; }
QScrollBar:vertical { border: none; background: #f1f1f1; width: 10px; margin: 0px; }
QScrollBar::handle:vertical { background: #c1c1c1; min-height: 30px; border-radius: 5px; }
QScrollBar::handle:vertical:hover { background: #a8a8a8; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QProgressBar { border: none; background-color: #f0f0f0; border-radius: 2px; text-align: center; }
QProgressBar::chunk { background-color: #ff4b4b; border-radius: 2px; }
QTextEdit { color: #333333; line-height: 160%; background-color: white; border: 1px solid #d1d5db; border-radius: 4px; }
"""