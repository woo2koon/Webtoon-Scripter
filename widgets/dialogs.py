# widgets/dialogs.py
import sys
import os
import re
import difflib
import time
import platform
import unicodedata
import excel_handler
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QComboBox, QFrame, QListWidget, QListWidgetItem, QWidget, QListView,
    QInputDialog, QAbstractItemView, QApplication, QStackedWidget,
    QFileDialog, QCheckBox, QMenu, QScrollArea, QGraphicsOpacityEffect, QTextEdit,
    QProgressBar, QGraphicsDropShadowEffect, QTableWidget, QTableWidgetItem, QHeaderView, QGridLayout
)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QMimeData, QByteArray, QTimer, QEvent, QPropertyAnimation, QEasingCurve, QRect
from PySide6.QtGui import (
    QPixmap, QIcon, QDrag, QPainter, QColor, QPen, QFont, QAction, QKeySequence,
    QTextCharFormat, QTextFormat, QTextCursor
)

import config
from config import PROJECTS_DIR, STORAGE_DIR
from utils import get_icon, get_colored_icon, get_colored_pixmap, open_path
from .common import PopupItemDelegate, SingleClickLineEdit
from .character import GlobalCharacterSettingsDialog
from .message_box import CustomMessageBox

# =================================================================
# 환경 설정 통합 다이얼로그 (PreferencesDialog)
# =================================================================
class PreferencesDialog(QDialog):
    def __init__(self, parent=None, active_page_idx=0, only_idioms=False):
        super().__init__(parent)
        self.setFont(QApplication.font())
        self.only_idioms = only_idioms
        if only_idioms:
            self.setWindowTitle("관용구 설정")
            self.setFixedSize(580, 540)
        else:
            self.setWindowTitle("환경 설정")
            self.setFixedSize(780, 540)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        # 1. 로컬 상태 데이터 복사
        self.local_presets = config.API_PRESETS.copy()
        self.local_active = config.ACTIVE_PRESET_NAME
        self.is_unified = False
        self.local_storage_dir = config.PROJECT_STORAGE_DIR
        self.local_idioms = [item.copy() for item in config.IDIOMS]
        
        self.init_ui(active_page_idx)

    SVG_EYE_OPEN = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>"""
    SVG_EYE_CLOSE = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>"""
    SVG_CHEVRON_DOWN = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>"""
    SVG_CHEVRON_UP = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg>"""

    def get_svg_icon(self, svg_data):
        pixmap = QPixmap()
        pixmap.loadFromData(svg_data)
        return QIcon(pixmap)

    def get_sidebar_icon(self, icon_path):
        from PySide6.QtSvg import QSvgRenderer
        if not os.path.exists(icon_path):
            return QIcon()
        try:
            with open(icon_path, 'r', encoding='utf-8') as f:
                svg_data = f.read()
            
            # Normal State (#4B5563)
            svg_normal = svg_data.replace('currentColor', '#4B5563').replace('#000000', '#4B5563')
            renderer_normal = QSvgRenderer(QByteArray(svg_normal.encode('utf-8')))
            pixmap_normal = QPixmap(64, 64)
            pixmap_normal.fill(Qt.transparent)
            painter = QPainter(pixmap_normal)
            renderer_normal.render(painter)
            painter.end()
            
            # Selected/Active State (#FF5722)
            svg_selected = svg_data.replace('currentColor', '#FF5722').replace('#000000', '#FF5722')
            renderer_selected = QSvgRenderer(QByteArray(svg_selected.encode('utf-8')))
            pixmap_selected = QPixmap(64, 64)
            pixmap_selected.fill(Qt.transparent)
            painter = QPainter(pixmap_selected)
            renderer_selected.render(painter)
            painter.end()
            
            icon = QIcon()
            icon.addPixmap(pixmap_normal, QIcon.Normal, QIcon.Off)
            icon.addPixmap(pixmap_normal, QIcon.Normal, QIcon.On)
            icon.addPixmap(pixmap_selected, QIcon.Selected, QIcon.Off)
            icon.addPixmap(pixmap_selected, QIcon.Selected, QIcon.On)
            icon.addPixmap(pixmap_selected, QIcon.Active, QIcon.Off)
            icon.addPixmap(pixmap_selected, QIcon.Active, QIcon.On)
            return icon
        except Exception as e:
            print(f"Error creating sidebar state icon: {e}")
            return get_colored_icon(icon_path, "#4B5563")

    def toggle_password_visibility(self, line_edit, button):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_CLOSE))
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))

    def init_ui(self, active_page_idx):
        # Qt CSS 스코프 문제: 개별 위젯에 setStyleSheet()로 font-size/weight를 지정하면
        # font-family는 앱 전체 stylesheet가 아닌 시스템 기본값(맑은 고딕)으로 폴백됨.
        # 따라서 font-size/weight를 쓰는 모든 stylesheet에 font-family를 동적으로 주입해야 함.
        app_ff = QApplication.font().family()
        if not app_ff or app_ff == "sans-serif":
            app_ff = "Pretendard"

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 가로 배치 레이아웃 (사이드바 + 컨텐츠)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        
        # 1. 좌측 커스텀 사이드바
        self.sidebar_container = QFrame()
        self.sidebar_container.setFixedWidth(200)
        self.sidebar_container.setStyleSheet("QFrame { background-color: #F3F4F6; border: none; }")
        
        sidebar_layout = QVBoxLayout(self.sidebar_container)
        sidebar_layout.setContentsMargins(8, 12, 8, 12)
        sidebar_layout.setSpacing(6)
        
        sidebar_btn_style = f"""
            QPushButton {{
                text-align: left;
                padding: 12px 16px;
                border-radius: 8px;
                font-size: 15px;
                font-family: '{app_ff}';
                color: #4B5563;
                background-color: transparent;
                border: none;
                outline: none;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background-color: #E5E7EB;
                color: #1F2937;
            }}
            QPushButton:focus {{
                border: none;
                outline: none;
            }}
            QPushButton[active="true"] {{
                background-color: #FFECEC;
                color: #FF5722;
                font-weight: 600; /* SemiBold */
            }}
        """
        
        self.btn_nav_api = QPushButton(" API 키 설정")
        self.btn_nav_api.setIcon(self.get_sidebar_icon(config.ICON_KEY))
        self.btn_nav_api.setIconSize(QSize(18, 18))
        self.btn_nav_api.setCursor(Qt.PointingHandCursor)
        self.btn_nav_api.setFocusPolicy(Qt.NoFocus)
        self.btn_nav_api.setStyleSheet(sidebar_btn_style)
        
        self.btn_nav_storage = QPushButton(" 저장소 설정")
        self.btn_nav_storage.setIcon(self.get_sidebar_icon(config.ICON_FOLDER))
        self.btn_nav_storage.setIconSize(QSize(18, 18))
        self.btn_nav_storage.setCursor(Qt.PointingHandCursor)
        self.btn_nav_storage.setFocusPolicy(Qt.NoFocus)
        self.btn_nav_storage.setStyleSheet(sidebar_btn_style)
        
        self.btn_nav_idiom = QPushButton(" 관용구 설정")
        self.btn_nav_idiom.setIcon(self.get_sidebar_icon(config.ICON_IDIOM))
        self.btn_nav_idiom.setIconSize(QSize(18, 18))
        self.btn_nav_idiom.setCursor(Qt.PointingHandCursor)
        self.btn_nav_idiom.setFocusPolicy(Qt.NoFocus)
        self.btn_nav_idiom.setStyleSheet(sidebar_btn_style)
        
        self.btn_nav_usage = QPushButton(" 사용량 조회")
        self.btn_nav_usage.setIcon(self.get_sidebar_icon(config.ICON_INFO))
        self.btn_nav_usage.setIconSize(QSize(18, 18))
        self.btn_nav_usage.setCursor(Qt.PointingHandCursor)
        self.btn_nav_usage.setFocusPolicy(Qt.NoFocus)
        self.btn_nav_usage.setStyleSheet(sidebar_btn_style)
        
        sidebar_layout.addWidget(self.btn_nav_api)
        sidebar_layout.addWidget(self.btn_nav_storage)
        sidebar_layout.addWidget(self.btn_nav_idiom)
        sidebar_layout.addWidget(self.btn_nav_usage)
        sidebar_layout.addStretch()
        
        self.sidebar_buttons = [self.btn_nav_api, self.btn_nav_storage, self.btn_nav_idiom, self.btn_nav_usage]
        
        # 2. 우측 스택 위젯
        self.pages = QStackedWidget()
        self.pages.setStyleSheet("background-color: white;")
        
        # --- [페이지 1] API 키 설정 ---
        self.page_api = QWidget()
        api_layout = QVBoxLayout(self.page_api)
        api_layout.setContentsMargins(30, 25, 30, 25)
        api_layout.setSpacing(15)
        
        lbl_api_title = QLabel("API 키 프리셋 관리")
        lbl_api_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: #111827; font-family: '{app_ff}';")
        api_layout.addWidget(lbl_api_title)
        
        preset_row = QHBoxLayout()
        self.combo_presets = QComboBox()
        self.combo_presets.setObjectName("PresetCombo")
        self.combo_presets.setFixedHeight(36)
        self.combo_presets.setView(QListView())
        self.combo_presets.setItemDelegate(PopupItemDelegate())
        self.combo_presets.view().window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.combo_presets.view().window().setAttribute(Qt.WA_TranslucentBackground)
        
        if sys.platform == "darwin":
            self.combo_presets.setStyleSheet(f"QComboBox#PresetCombo {{ border: 1px solid #ccc; border-radius: 4px; padding-left: 10px; background: white; font-size: 13px; font-family: '{app_ff}'; }}")
        else:
            self.combo_presets.setStyleSheet(f"""
                QComboBox#PresetCombo {{
                    border: 1px solid #D1D5DB;
                    border-radius: 6px;
                    padding-left: 10px;
                    background: white;
                    font-size: 13px;
                    font-family: '{app_ff}';
                }}
                QComboBox#PresetCombo:hover {{ border-color: #FF5722; }}
            """)
            
        for preset_name in self.local_presets.keys():
            self.combo_presets.addItem(preset_name)
        self.combo_presets.setCurrentText(self.local_active)
        self.combo_presets.currentTextChanged.connect(self.on_preset_changed)
        
        btn_preset_add = QPushButton("추장" if False else "추가") # height sync
        btn_preset_add.setFixedSize(70, 36)
        btn_preset_add.setCursor(Qt.PointingHandCursor)
        btn_preset_add.clicked.connect(self.add_preset)
        btn_preset_add.setStyleSheet(f"QPushButton {{ background-color: #FF5722; color: white; border: none; border-radius: 6px; font-weight: bold; font-family: '{app_ff}'; }} QPushButton:hover {{ background-color: #E64A19; }}")
        
        btn_preset_del = QPushButton("삭제")
        btn_preset_del.setFixedSize(70, 36)
        btn_preset_del.setCursor(Qt.PointingHandCursor)
        btn_preset_del.clicked.connect(self.delete_preset)
        btn_preset_del.setStyleSheet(f"QPushButton {{ background-color: white; border: 1px solid #D1D5DB; border-radius: 6px; color: #4B5563; font-weight: bold; font-family: '{app_ff}'; }} QPushButton:hover {{ border-color: #EF4444; color: #EF4444; }}")
        
        preset_row.addWidget(self.combo_presets, 1)
        preset_row.addWidget(btn_preset_add)
        preset_row.addWidget(btn_preset_del)
        api_layout.addLayout(preset_row)
        
        keys_box = QFrame()
        keys_box.setStyleSheet("QFrame { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; }")
        keys_layout = QVBoxLayout(keys_box)
        keys_layout.setContentsMargins(15, 15, 15, 18) # 하단 여백 확보
        keys_layout.setSpacing(10)
        
        lbl_ocr = QLabel("Google Cloud API 키 (Vision + Gemini)")
        lbl_ocr.setStyleSheet(f"font-weight: bold; color: #FF5722; font-size: 13px; border: none; background: transparent; font-family: '{app_ff}';")
        
        row_ocr_input = QHBoxLayout()
        self.input_ocr = QLineEdit()
        self.input_ocr.setPlaceholderText("Google Cloud API Key")
        self.input_ocr.setEchoMode(QLineEdit.Password)
        self.input_ocr.setFixedHeight(36)
        self.input_ocr.setStyleSheet("QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding-left: 10px; background: white; } QLineEdit:focus { border: 2px solid #FF5722; }")
        self.input_ocr.textChanged.connect(self.save_temp_data)
        
        self.btn_toggle_ocr = QPushButton()
        self.btn_toggle_ocr.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))
        self.btn_toggle_ocr.setIconSize(QSize(20, 20))
        self.btn_toggle_ocr.setFixedSize(40, 36)
        self.btn_toggle_ocr.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_ocr.setStyleSheet("QPushButton { border: none; background: transparent; } QPushButton:hover { background-color: #E5E7EB; border-radius: 6px; }")
        self.btn_toggle_ocr.clicked.connect(lambda: self.toggle_password_visibility(self.input_ocr, self.btn_toggle_ocr))
        
        row_ocr_input.addWidget(self.input_ocr)
        row_ocr_input.addWidget(self.btn_toggle_ocr)
        keys_layout.addWidget(lbl_ocr)
        keys_layout.addLayout(row_ocr_input)
        
        self.btn_toggle_advanced = QPushButton("Google AI Studio API 키 별도 설정 (선택 사항)")
        self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_DOWN))
        self.btn_toggle_advanced.setIconSize(QSize(12, 12))
        self.btn_toggle_advanced.setStyleSheet(f"QPushButton {{ text-align: left; color: #6B7280; background: transparent; border: none; font-size: 12px; font-family: '{app_ff}'; }} QPushButton:hover {{ color: #1F2937; font-weight: bold; }}")
        self.btn_toggle_advanced.setToolTip("Google AI Studio에서 발급받은 API 키를 별도로 설정할 수 있습니다.\n설정 시 맞춤법 검사 용도로 사용됩니다.")
        self.btn_toggle_advanced.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_advanced.clicked.connect(self.toggle_advanced_mode)
        keys_layout.addWidget(self.btn_toggle_advanced)
        
        self.ai_container = QWidget()
        self.ai_container.setStyleSheet("border: none; background: transparent;")
        ai_layout = QVBoxLayout(self.ai_container)
        ai_layout.setContentsMargins(0, 5, 0, 5) # 하단 여백 추가로 잘림 현상 제거
        ai_layout.setSpacing(8)
        
        lbl_ai = QLabel("Google AI Studio API 키 (맞춤법 전용)")
        lbl_ai.setStyleSheet(f"font-weight: bold; color: #2563EB; font-size: 13px; border: none; font-family: '{app_ff}';")
        
        row_ai_input = QHBoxLayout()
        self.input_ai = QLineEdit()
        self.input_ai.setPlaceholderText("Google AI Studio API Key")
        self.input_ai.setEchoMode(QLineEdit.Password)
        self.input_ai.setFixedHeight(36)
        self.input_ai.setStyleSheet("QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding-left: 10px; background: white; } QLineEdit:focus { border: 2px solid #FF5722; }")
        self.input_ai.textChanged.connect(self.save_temp_data)
        
        self.btn_toggle_ai = QPushButton()
        self.btn_toggle_ai.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))
        self.btn_toggle_ai.setIconSize(QSize(20, 20))
        self.btn_toggle_ai.setFixedSize(40, 36)
        self.btn_toggle_ai.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_ai.setStyleSheet("QPushButton { border: none; background: transparent; } QPushButton:hover { background-color: #E5E7EB; border-radius: 6px; }")
        self.btn_toggle_ai.clicked.connect(lambda: self.toggle_password_visibility(self.input_ai, self.btn_toggle_ai))
        
        row_ai_input.addWidget(self.input_ai)
        row_ai_input.addWidget(self.btn_toggle_ai)
        ai_layout.addWidget(lbl_ai)
        ai_layout.addLayout(row_ai_input)
        
        keys_layout.addWidget(self.ai_container)
        api_layout.addWidget(keys_box)
        api_layout.addStretch()
        
        self.load_preset_to_ui(self.local_active)
        self.pages.addWidget(self.page_api)
        
        # --- [페이지 2] 저장소 설정 ---
        self.page_storage = QWidget()
        storage_layout = QVBoxLayout(self.page_storage)
        storage_layout.setContentsMargins(30, 25, 30, 25)
        storage_layout.setSpacing(15)
        
        lbl_storage_title = QLabel("프로젝트 저장소 설정")
        lbl_storage_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: #111827; font-family: '{app_ff}';")
        storage_layout.addWidget(lbl_storage_title)
        
        lbl_storage_desc = QLabel("작품/회차 데이터(대본 CSV, 엑셀, 원본 이미지 등)가 저장될 상위 디렉토리를 변경합니다.\n변경 시 이전 데이터 폴더들은 자동으로 이동하지 않으므로 주의가 필요합니다.")
        lbl_storage_desc.setStyleSheet(f"color: #6B7280; font-size: 12px; font-family: '{app_ff}';")
        storage_layout.addWidget(lbl_storage_desc)
        
        storage_box = QFrame()
        storage_box.setStyleSheet("QFrame { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; }")
        box_layout = QVBoxLayout(storage_box)
        box_layout.setContentsMargins(15, 15, 15, 15)
        box_layout.setSpacing(10)
        
        lbl_path_title = QLabel("기본 프로젝트 저장 경로")
        lbl_path_title.setStyleSheet(f"font-weight: bold; color: #374151; font-size: 13px; border: none; background: transparent; font-family: '{app_ff}';")
        box_layout.addWidget(lbl_path_title)
        
        path_row = QHBoxLayout()
        self.input_storage_path = QLineEdit()
        self.input_storage_path.setReadOnly(True)
        self.input_storage_path.setText(self.local_storage_dir)
        self.input_storage_path.setFixedHeight(36)
        self.input_storage_path.setStyleSheet("QLineEdit { border: 1px solid #D1D5DB; border-radius: 6px; padding-left: 10px; background: #F3F4F6; color: #4B5563; }")
        
        btn_browse_storage = QPushButton("폴더 선택...")
        btn_browse_storage.setFixedSize(105, 36) # 버튼 너비를 90에서 105로 확대하여 글자 잘림 해결
        btn_browse_storage.setCursor(Qt.PointingHandCursor)
        btn_browse_storage.clicked.connect(self.browse_storage_path)
        btn_browse_storage.setStyleSheet(f"QPushButton {{ background-color: #FF5722; color: white; border: none; border-radius: 6px; font-weight: bold; font-family: '{app_ff}'; }} QPushButton:hover {{ background-color: #E64A19; }}")
        
        path_row.addWidget(self.input_storage_path, 1)
        path_row.addWidget(btn_browse_storage)
        box_layout.addLayout(path_row)
        
        # 복구용 기본값 설정 링크 단추
        btn_reset_storage = QPushButton("↩ 기본값(내 문서)으로 초기화")
        btn_reset_storage.setCursor(Qt.PointingHandCursor)
        btn_reset_storage.setStyleSheet(f"QPushButton {{ text-align: left; color: #4B5563; border: none; background: transparent; font-size: 12px; text-decoration: underline; font-family: '{app_ff}'; }} QPushButton:hover {{ color: #FF5722; }}") # 폰트 크기 11px -> 12px로 1픽셀 상향 조정
        btn_reset_storage.clicked.connect(self.reset_storage_path)
        box_layout.addWidget(btn_reset_storage)
        
        storage_layout.addWidget(storage_box)

        # 2. 이전 버전 데이터 가져오기 (별개 박스로 분리)
        migration_box = QFrame()
        migration_box.setStyleSheet("QFrame { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; }")
        mig_box_layout = QVBoxLayout(migration_box)
        mig_box_layout.setContentsMargins(15, 15, 15, 15)
        mig_box_layout.setSpacing(10)

        # 이전 버전 데이터 가져오기 (마이그레이션) 안내 및 버튼
        lbl_mig_title = QLabel("이전 버전 데이터 가져오기")
        lbl_mig_title.setStyleSheet(f"font-weight: bold; color: #374151; font-size: 13px; border: none; background: transparent; font-family: '{app_ff}';")
        mig_box_layout.addWidget(lbl_mig_title)

        lbl_mig_desc = QLabel("이전 실행파일 버전(.exe)에 생성된 프로젝트 폴더(작품 및 회차 데이터가 모여있는 폴더) 데이터를\n안전하게 마이그레이션(가져오기) 합니다.")
        lbl_mig_desc.setStyleSheet(f"color: #6B7280; font-size: 12px; border: none; background: transparent; font-family: '{app_ff}';")
        mig_box_layout.addWidget(lbl_mig_desc)

        btn_migrate = QPushButton("이전 버전 데이터 마이그레이션 실행...")
        btn_migrate.setFixedHeight(36)
        btn_migrate.setCursor(Qt.PointingHandCursor)
        btn_migrate.setStyleSheet(f"""
            QPushButton {{
                background-color: white; 
                border: 1px solid #D1D5DB; 
                border-radius: 6px; 
                color: #374151;
                font-weight: bold; 
                font-family: '{app_ff}'; 
                font-size: 13px;
                margin-top: 5px;
            }} 
            QPushButton:hover {{ 
                background-color: #F9FAFB; 
                border-color: #9CA3AF; 
            }}
            QPushButton:pressed {{
                background-color: #F3F4F6;
            }}
        """)
        
        def run_migration():
            main_win = self.parent()
            if main_win and hasattr(main_win, 'migrate_old_projects'):
                main_win.migrate_old_projects()
            else:
                CustomMessageBox.warning(self, "알림", "마이그레이션 기능을 실행할 수 없습니다.")
                
        btn_migrate.clicked.connect(run_migration)
        mig_box_layout.addWidget(btn_migrate)
        
        storage_layout.addWidget(migration_box)
        storage_layout.addStretch()
        self.pages.addWidget(self.page_storage)
        
        # --- [페이지 3] 관용구 설정 ---
        self.page_idiom = QWidget()
        idiom_layout = QVBoxLayout(self.page_idiom)
        idiom_layout.setContentsMargins(30, 25, 30, 25)
        idiom_layout.setSpacing(12)
        
        lbl_idiom_title = QLabel("관용구(지문) 리스트 관리")
        lbl_idiom_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: #111827; font-family: '{app_ff}';")
        idiom_layout.addWidget(lbl_idiom_title)
        
        lbl_idiom_desc = QLabel(f"마우스 드래그로 순서를 편집할 수 있으며, 상위 10개는 {config.MODIFIER_NAME} + [숫자] 단축키로 본문에 고속 입력됩니다.")
        lbl_idiom_desc.setStyleSheet(f"color: #6B7280; font-size: 12px; font-family: '{app_ff}';")
        idiom_layout.addWidget(lbl_idiom_desc)
        
        idiom_input_row = QHBoxLayout()
        self.input_idiom_text = QLineEdit()
        self.input_idiom_text.setObjectName("IdiomInputText")
        self.input_idiom_text.setPlaceholderText("예: (속)")
        self.input_idiom_text.setFixedHeight(38) # 입력창 기준 높이 38px로 통일
        self.input_idiom_text.setStyleSheet("QLineEdit#IdiomInputText { border: 1px solid #D1D5DB; border-radius: 6px; padding-left: 10px; background: white; } QLineEdit#IdiomInputText:focus { border: 2px solid #FF5722; }")
        self.input_idiom_text.returnPressed.connect(self.add_idiom)
        
        btn_idiom_add = QPushButton("추가")
        btn_idiom_add.setFixedSize(70, 38) # 높이 38px로 동기화
        btn_idiom_add.setCursor(Qt.PointingHandCursor)
        btn_idiom_add.clicked.connect(self.add_idiom)
        btn_idiom_add.setStyleSheet(f"QPushButton {{ background-color: #FF5722; color: white; border: none; border-radius: 6px; font-weight: bold; font-family: '{app_ff}'; }} QPushButton:hover {{ background-color: #E64A19; }}")
        
        idiom_input_row.addWidget(self.input_idiom_text, 1)
        idiom_input_row.addWidget(btn_idiom_add)
        idiom_layout.addLayout(idiom_input_row)
        
        self.scroll_container = QFrame()
        self.scroll_container.setStyleSheet("QFrame { border: 1px solid #E5E7EB; border-radius: 8px; background-color: #F9FAFB; }")
        container_layout = QVBoxLayout(self.scroll_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(35)
        self.header_widget.setStyleSheet("QWidget { background-color: #F3F4F6; border: none; border-bottom: 1px solid #E5E7EB; border-top-left-radius: 7px; border-top-right-radius: 7px; }")
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(10, 0, 10, 0)
        self.header_layout.setSpacing(8)
        
        def create_header_box(text, width=None):
            box = QFrame()
            box.setStyleSheet("background: transparent; border: none;")
            lay = QHBoxLayout(box)
            lay.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setStyleSheet(f"color: #4B5563; font-size: 12px; font-weight: bold; border: none; font-family: '{app_ff}';")
            lay.addWidget(lbl)
            if width: box.setFixedWidth(width)
            return box
            
        self.header_layout.addWidget(create_header_box("이동", width=30))
        self.header_layout.addWidget(create_header_box("지문 내용"), 1)
        self.header_layout.addWidget(create_header_box("단축키", width=80))
        self.header_layout.addWidget(create_header_box("삭제", width=40))
        self.header_layout.addSpacing(12)
        container_layout.addWidget(self.header_widget)
        
        self.list_widget = DragDropListWidget(self)
        self.list_widget.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.list_widget.setStyleSheet("""
            QListWidget { background-color: transparent; border: none; outline: none; padding: 0px; margin: 0px; }
            QListWidget::item { background-color: transparent; border: none; padding: 0px; }
            QListWidget::item:selected { background-color: transparent; }
            QListWidget::drop-indicator { background-color: #FF5722; height: 3px; }
            QScrollBar:vertical { border: none; background: transparent; width: 12px; margin: 0; }
            QScrollBar::handle:vertical { background: #D1D5DB; border-radius: 6px; min-height: 20px; margin: 2px; }
            QScrollBar::handle:vertical:hover { background: #9CA3AF; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        container_layout.addWidget(self.list_widget)
        idiom_layout.addWidget(self.scroll_container)
        
        self.refresh_list()
        self.pages.addWidget(self.page_idiom)
        
        # --- [페이지 4] 사용량 조회 ---
        self.page_usage = QWidget()
        usage_layout = QVBoxLayout(self.page_usage)
        usage_layout.setContentsMargins(30, 25, 30, 25)
        usage_layout.setSpacing(15)
        
        # 타이틀 영역 + 연월 선택 콤보박스 가로 배치
        title_row = QHBoxLayout()
        lbl_usage_title = QLabel("API 사용량 조회")
        lbl_usage_title.setStyleSheet(f"font-size: 16px; font-weight: bold; color: #111827; font-family: '{app_ff}';")
        title_row.addWidget(lbl_usage_title)
        title_row.addStretch()
        
        self.combo_months = QComboBox()
        self.combo_months.setObjectName("MonthCombo")
        self.combo_months.setFixedHeight(36)
        self.combo_months.setFixedWidth(130)
        self.combo_months.setView(QListView())
        self.combo_months.setItemDelegate(PopupItemDelegate())
        self.combo_months.view().window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.combo_months.view().window().setAttribute(Qt.WA_TranslucentBackground)
        self.combo_months.setStyleSheet(f"""
            QComboBox#MonthCombo {{
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding-left: 10px;
                background-color: white;
                font-family: '{app_ff}';
                font-size: 13px;
                color: #374151;
            }}
            QComboBox#MonthCombo::drop-down {{
                border: none;
                width: 30px;
            }}
            QComboBox#MonthCombo::down-arrow {{
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #6B7280;
                width: 0;
                height: 0;
            }}
        """)
        self.combo_months.currentIndexChanged.connect(self.update_usage_table)
        title_row.addWidget(self.combo_months)
        usage_layout.addLayout(title_row)
        
        # 요약 카드 가로 배치
        cards_row = QHBoxLayout()
        cards_row.setSpacing(15)
        
        # 카드 1: 선택 월 총 사용량
        card1 = QFrame()
        card1.setStyleSheet("QFrame { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 8px; }")
        c1_layout = QVBoxLayout(card1)
        c1_layout.setContentsMargins(15, 12, 15, 12)
        self.lbl_usage_total_title = QLabel("총 사용 횟수")
        self.lbl_usage_total_title.setStyleSheet(f"font-size: 12px; color: #6B7280; font-family: '{app_ff}'; border: none; background: transparent;")
        self.lbl_usage_total = QLabel("0회")
        self.lbl_usage_total.setStyleSheet(f"font-size: 20px; font-weight: bold; color: #111827; font-family: '{app_ff}'; border: none; background: transparent;")
        c1_layout.addWidget(self.lbl_usage_total_title)
        c1_layout.addWidget(self.lbl_usage_total)
        
        # 카드 2: 선택 월 예상 비용
        card2 = QFrame()
        card2.setStyleSheet("QFrame { background-color: #FFF9F7; border: 1px solid #FFEFEA; border-radius: 8px; }")
        c2_layout = QVBoxLayout(card2)
        c2_layout.setContentsMargins(15, 12, 15, 12)
        self.lbl_usage_cost_title = QLabel("예상 비용")
        self.lbl_usage_cost_title.setStyleSheet(f"font-size: 12px; color: #FF5722; font-family: '{app_ff}'; border: none; background: transparent;")
        self.lbl_usage_cost = QLabel("약 0원")
        self.lbl_usage_cost.setStyleSheet(f"font-size: 20px; font-weight: bold; color: #FF5722; font-family: '{app_ff}'; border: none; background: transparent;")
        c2_layout.addWidget(self.lbl_usage_cost_title)
        c2_layout.addWidget(self.lbl_usage_cost)
        
        cards_row.addWidget(card1, 1)
        cards_row.addWidget(card2, 1)
        usage_layout.addLayout(cards_row)
        
        # 테이블 위젯 추가
        self.table_usage = QTableWidget()
        self.table_usage.setColumnCount(3)
        self.table_usage.setHorizontalHeaderLabels(["날짜", "사용 횟수", "예상 비용"])
        
        # 3단계 시트와 동일하게 강제 안티앨리어싱 및 폰트 렌더링 옵션 지정
        table_font = QFont(app_ff, 11)
        table_font.setStyleStrategy(QFont.PreferAntialias)
        table_font.setHintingPreference(QFont.PreferNoHinting)
        self.table_usage.setFont(table_font)
        
        self.table_usage.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_usage.setSelectionMode(QAbstractItemView.NoSelection)
        self.table_usage.setFocusPolicy(Qt.NoFocus)
        self.table_usage.verticalHeader().setVisible(False)
        self.table_usage.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 기본 헤더는 숨기고 글자 깨짐 및 렌더러 버그 방지를 위해 QLabel 기반 커스텀 프레임 헤더 구성
        self.table_usage.horizontalHeader().setVisible(False)
        self.table_usage.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        
        # 커스텀 테이블 헤더 컨테이너 구성 (QLabel 조합)
        self.custom_header = QFrame()
        self.custom_header.setFixedHeight(38)
        self.custom_header.setStyleSheet("""
            QFrame {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-bottom: none;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
            }
        """)
        custom_header_layout = QHBoxLayout(self.custom_header)
        custom_header_layout.setContentsMargins(0, 0, 0, 0)
        custom_header_layout.setSpacing(0)
        
        lbl_header_date = QLabel("날짜")
        lbl_header_count = QLabel("사용 횟수")
        lbl_header_cost = QLabel("예상 비용")
        
        # Qt stylesheet가 QFont 설정을 덮어쓰지 않도록 stylesheet에는 font 관련 프로퍼티를 완전히 제외합니다.
        header_lbl_style = """
            QLabel {
                color: #374151;
                background: transparent;
                border: none;
            }
        """
        
        # 선명하고 굵은 Pretendard 폰트를 위해 QFont 기반으로 직접 설정
        header_font = QFont(app_ff, 11)
        header_font.setBold(True)
        header_font.setStyleStrategy(QFont.PreferAntialias)
        header_font.setHintingPreference(QFont.PreferNoHinting)
        
        for lbl in [lbl_header_date, lbl_header_count, lbl_header_cost]:
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(header_font)
            lbl.setStyleSheet(header_lbl_style)
            
        custom_header_layout.addWidget(lbl_header_date, 1)
        custom_header_layout.addWidget(lbl_header_count, 1)
        custom_header_layout.addWidget(lbl_header_cost, 1)
        
        # 구분선 지정 (CSS로만 선 표현)
        lbl_header_date.setStyleSheet(header_lbl_style + " QLabel { border-right: 1px solid #E5E7EB; }")
        lbl_header_count.setStyleSheet(header_lbl_style + " QLabel { border-right: 1px solid #E5E7EB; }")
        
        # 스크롤바 영역 (12px) 만큼 오른쪽 마진 확보하여 열 정렬 맞춤
        scrollbar_spacer = QWidget()
        scrollbar_spacer.setFixedWidth(12)
        scrollbar_spacer.setStyleSheet("background: transparent; border: none;")
        custom_header_layout.addWidget(scrollbar_spacer)
        
        self.table_usage.setStyleSheet(f"""
            QTableWidget {{
                background-color: white;
                border: 1px solid #E5E7EB;
                border-top: none;
                border-radius: 0px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                gridline-color: #F3F4F6;
            }}
            QTableWidget::item {{
                border-bottom: 1px solid #F3F4F6;
                padding: 5px;
                color: #4B5563;
            }}
            QTableWidget::item:selected, QTableWidget::item:focus {{
                background-color: transparent;
                color: #4B5563;
                border: none;
                outline: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: transparent;
                width: 12px;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: #D1D5DB;
                border-radius: 6px;
                min-height: 20px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #9CA3AF;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)
        
        # 헤더와 테이블을 Spacing 0인 세로 레이아웃에 묶어 간격 없이 배치
        table_container_layout = QVBoxLayout()
        table_container_layout.setContentsMargins(0, 0, 0, 0)
        table_container_layout.setSpacing(0)
        table_container_layout.addWidget(self.custom_header)
        table_container_layout.addWidget(self.table_usage, 1)
        
        usage_layout.addLayout(table_container_layout, 1)
        
        # 하단 안내 문구
        lbl_info = QLabel("💡 Google Cloud API 단가 1회당 약 2원(0.0015 USD) 기준으로 계산한 예상 금액입니다.")
        lbl_info.setStyleSheet(f"color: #9CA3AF; font-size: 11px; font-family: '{app_ff}';")
        usage_layout.addWidget(lbl_info)
        
        self.pages.addWidget(self.page_usage)
        
        # 바디 레이아웃 배치
        body_layout.addWidget(self.sidebar_container)
        body_layout.addWidget(self.pages, 1)
        
        # 3. 하단 공통 버튼바
        bottom_frame = QFrame()
        bottom_frame.setFixedHeight(60)
        bottom_frame.setStyleSheet("QFrame { background-color: white; border-top: 1px solid #E5E7EB; }")
        bottom_layout = QHBoxLayout(bottom_frame)
        bottom_layout.setContentsMargins(25, 0, 25, 0)
        bottom_layout.setSpacing(10)
        bottom_layout.addStretch()
        
        btn_close = QPushButton("닫기")
        btn_close.setFixedSize(100, 38)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)
        btn_close.setStyleSheet(f"QPushButton {{ background-color: white; border: 1px solid #D1D5DB; border-radius: 6px; color: #4B5563; font-weight: bold; font-family: '{app_ff}'; }} QPushButton:hover {{ border-color: #FF5722; color: #FF5722; background-color: #FFF9F7; }}")
        
        bottom_layout.addWidget(btn_close)
        
        main_layout.addLayout(body_layout, 1)
        main_layout.addWidget(bottom_frame)
        


        # 4. 연동 이벤트 등록 및 초기 탭 지정
        self.btn_nav_api.clicked.connect(lambda: self.set_active_page(0))
        self.btn_nav_storage.clicked.connect(lambda: self.set_active_page(1))
        self.btn_nav_idiom.clicked.connect(lambda: self.set_active_page(2))
        self.btn_nav_usage.clicked.connect(lambda: self.set_active_page(3))
        
        if self.only_idioms:
            self.sidebar_container.setVisible(False)
            self.set_active_page(2)
        else:
            self.set_active_page(active_page_idx)

    def set_active_page(self, index):
        self.pages.setCurrentIndex(index)
        for i, btn in enumerate(self.sidebar_buttons):
            is_active = (i == index)
            btn.setProperty("active", "true" if is_active else "false")
            # 스타일 강제 갱신
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()
        if index == 3:
            self.load_usage_data()

    def load_usage_data(self):
        import json
        from datetime import datetime
        daily_path = os.path.join(STORAGE_DIR, "daily_api_usage.json")
        self.usage_history = {}
        
        if os.path.exists(daily_path):
            try:
                with open(daily_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.usage_history = data.get("history", {})
            except Exception as e:
                print(f"Error loading usage data in dialog: {e}")
                
        # 콤보박스 아이템 생성
        self.combo_months.blockSignals(True)
        self.combo_months.clear()
        
        # 현재 날짜 기준의 연-월도 항상 포함
        current_ym = datetime.now().strftime("%Y-%m")
        ym_set = {current_ym}
        for date_str in self.usage_history.keys():
            if len(date_str) >= 7:
                ym_set.add(date_str[:7])
                
        # 정렬하여 역순으로 목록 추가 (최신 월이 위로 가도록)
        sorted_ym = sorted(list(ym_set), reverse=True)
        for ym in sorted_ym:
            try:
                dt = datetime.strptime(ym, "%Y-%m")
                display_str = dt.strftime("%Y년 %m월")
            except Exception:
                display_str = ym
            self.combo_months.addItem(display_str, ym)
            
        self.combo_months.blockSignals(False)
        self.update_usage_table()

    def update_usage_table(self):
        selected_ym = self.combo_months.currentData()
        if not selected_ym:
            return
            
        # 선택된 월의 데이터 필터링
        monthly_data = []
        total_count = 0
        for date_str, count in self.usage_history.items():
            if date_str.startswith(selected_ym):
                monthly_data.append((date_str, count))
                total_count += count
                
        # 날짜 기준 내림차순 정렬
        monthly_data.sort(key=lambda x: x[0], reverse=True)
        
        # 요약 수치 갱신
        formatted_ym = selected_ym.replace('-', '.')
        self.lbl_usage_total_title.setText(f"{formatted_ym} 총 사용 횟수")
        self.lbl_usage_cost_title.setText(f"{formatted_ym} 예상 비용")
        
        self.lbl_usage_total.setText(f"{total_count}회")
        cost = total_count * 2
        self.lbl_usage_cost.setText(f"약 {cost:,}원")
        
        # 테이블 채우기
        self.table_usage.setRowCount(len(monthly_data))
        for row_idx, (date_str, count) in enumerate(monthly_data):
            # 날짜 셀
            item_date = QTableWidgetItem(date_str)
            item_date.setTextAlignment(Qt.AlignCenter)
            self.table_usage.setItem(row_idx, 0, item_date)
            
            # 사용 횟수 셀
            item_count = QTableWidgetItem(f"{count}회")
            item_count.setTextAlignment(Qt.AlignCenter)
            self.table_usage.setItem(row_idx, 1, item_count)
            
            # 예상 비용 셀
            item_cost = QTableWidgetItem(f"약 {count*2:,}원")
            item_cost.setTextAlignment(Qt.AlignCenter)
            self.table_usage.setItem(row_idx, 2, item_cost)

    # --- API 키 설정 로직 ---
    def on_preset_changed(self, text):
        if text:
            self.local_active = text
            self.load_preset_to_ui(text)
 
    def load_preset_to_ui(self, preset_name):
        data = self.local_presets.get(preset_name, {"ocr": "", "ai": "", "unified": True})
        
        self.input_ocr.blockSignals(True)
        self.input_ai.blockSignals(True)
        self.input_ocr.setText(data.get("ocr", ""))
        
        ui_ai = data.get("ui_ai", "")
        if not ui_ai and not data.get("unified", True):
            ui_ai = data.get("ai", "")
        self.input_ai.setText(ui_ai)
        
        # [신규 요구사항] AI Studio 키가 존재하는 경우에는 아코디언 자동 열림(is_unified=False)
        # 키가 입력되어 있지 않은 빈값일 경우에는 기본값(아코디언 닫힘=is_unified)을 따릅니다.
        if ui_ai.strip():
            self.is_unified = False
        else:
            self.is_unified = data.get("unified", True)
            
        self.input_ocr.blockSignals(False)
        self.input_ai.blockSignals(False)
        
        # UI 상태 동기화 (기록용 저장 차단)
        self.ai_container.setVisible(not self.is_unified)
        if self.is_unified:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_DOWN))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (선택 사항)")
        else:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_UP))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (닫기)")

    def toggle_advanced_mode(self):
        self.set_unified_mode(not self.is_unified)

    def set_unified_mode(self, is_unified):
        self.is_unified = is_unified
        self.ai_container.setVisible(not is_unified)
        
        if is_unified:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_DOWN))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (선택 사항)")
        else:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_UP))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (닫기)")
        self.save_temp_data()

    def save_temp_data(self):
        if self.local_active:
            ocr_val = self.input_ocr.text().strip()
            text_ai = self.input_ai.text().strip()
            actual_ai = ocr_val if self.is_unified else text_ai
            
            # AI Studio 키가 비어있는 경우, 아코디언 상태가 열려있더라도(is_unified=False)
            # 설정 파일에는 항상 unified=True(닫힘 상태)로 저장하여 다음 진입 시 불필요하게 열려있지 않도록 방지합니다.
            saved_unified = True if not text_ai else self.is_unified
            
            self.local_presets[self.local_active] = {
                "ocr": ocr_val,
                "ai": actual_ai,
                "ui_ai": text_ai,
                "unified": saved_unified
            }
            config.save_settings(self.local_presets, self.local_active)

    def add_preset(self):
        text, ok = QInputDialog.getText(self, "프리셋 추가", "새 프리셋 이름:")
        if ok and text:
            name = text.strip()
            if name in self.local_presets:
                CustomMessageBox.warning(self, "중복", "이미 존재하는 이름입니다.")
                return
            self.local_presets[name] = {"ocr": "", "ai": "", "ui_ai": "", "unified": True}
            self.combo_presets.addItem(name)
            self.combo_presets.setCurrentText(name)
            config.save_settings(self.local_presets, self.local_active)

    def delete_preset(self):
        if len(self.local_presets) <= 1:
            CustomMessageBox.warning(self, "알림", "최소 하나의 프리셋은 있어야 합니다.")
            return
        current = self.combo_presets.currentText()
        reply = CustomMessageBox.question(
            self,
            "삭제 확인",
            f"'{current}' 프리셋을 삭제하시겠습니까?",
            [CustomMessageBox.Yes, CustomMessageBox.No]
        )
        
        if reply == CustomMessageBox.Yes:
            del self.local_presets[current]
            self.combo_presets.removeItem(self.combo_presets.currentIndex())
            config.save_settings(self.local_presets, self.local_active)

    # --- 저장소 설정 로직 ---
    def browse_storage_path(self):
        dir_path = QFileDialog.getExistingDirectory(self, "저장 폴더 선택", self.local_storage_dir)
        if dir_path:
            norm_path = os.path.normpath(dir_path)
            if norm_path == self.local_storage_dir:
                return

            old_projects_dir = os.path.join(self.local_storage_dir, "projects")
            new_projects_dir = os.path.join(norm_path, "projects")

            has_old_projects = False
            if os.path.exists(old_projects_dir):
                try:
                    subdirs = [d for d in os.listdir(old_projects_dir) if os.path.isdir(os.path.join(old_projects_dir, d))]
                    if subdirs:
                        has_old_projects = True
                except Exception:
                    pass

            if has_old_projects:
                reply = CustomMessageBox.question(
                    self,
                    "프로젝트 복사",
                    "저장 위치가 변경되었습니다.\n기존 저장 위치에 있는 프로젝트 폴더들을 새 위치로 복사하시겠습니까?",
                    [CustomMessageBox.Yes, CustomMessageBox.No]
                )
                
                if reply == CustomMessageBox.Yes:
                    try:
                        import shutil
                        os.makedirs(new_projects_dir, exist_ok=True)
                        for d in os.listdir(old_projects_dir):
                            src_path = os.path.join(old_projects_dir, d)
                            dst_path = os.path.join(new_projects_dir, d)
                            if os.path.isdir(src_path):
                                shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
                            else:
                                shutil.copy2(src_path, dst_path)
                        CustomMessageBox.information(self, "완료", "기존 프로젝트 복사가 완료되었습니다.")
                    except Exception as e:
                        CustomMessageBox.critical(self, "오류", f"프로젝트 복사 중 오류가 발생했습니다:\n{e}")

            self.local_storage_dir = norm_path
            self.input_storage_path.setText(norm_path)
            config.update_project_storage_dir(norm_path)

    def reset_storage_path(self):
        self.local_storage_dir = config.DEFAULT_PROJECT_DIR
        self.input_storage_path.setText(config.DEFAULT_PROJECT_DIR)
        config.update_project_storage_dir(config.DEFAULT_PROJECT_DIR)

    # --- 관용구 설정 로직 ---
    def refresh_list(self):
        self.list_widget.clear()
        for i, idiom in enumerate(self.local_idioms):
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 45))
            card = IdiomCard(idiom, i, self)
            card.delete_signal.connect(self.delete_idiom_by_data)
            self.list_widget.setItemWidget(item, card)

    def save_idioms(self):
        for index, item in enumerate(self.local_idioms):
            if index < 9:
                item["key"] = str(index + 1)
            elif index == 9:
                item["key"] = "0"
            else:
                item["key"] = ""
        config.IDIOMS = self.local_idioms
        config.save_settings(config.API_PRESETS, config.ACTIVE_PRESET_NAME)

    def delete_idiom_by_data(self, data):
        if data in self.local_idioms:
            self.local_idioms.remove(data)
            self.refresh_list()
            self.save_idioms()

    def add_idiom(self):
        text = self.input_idiom_text.text().strip()
        if not text:
            CustomMessageBox.warning(self, "알림", "내용을 입력해주세요.")
            return
        self.local_idioms.append({"text": text, "key": ""})
        self.input_idiom_text.clear()
        self.refresh_list()
        self.save_idioms()

    def move_idiom(self, src, dst):
        if src >= 0 and dst >= 0 and src < len(self.local_idioms) and dst < len(self.local_idioms):
            item = self.local_idioms.pop(src)
            self.local_idioms.insert(dst, item)
            self.refresh_list()
            self.save_idioms()

# =================================================================
# 관용구 개별 카드 위젯 (IdiomCard)
# =================================================================
class IdiomCard(QFrame):
    delete_signal = Signal(dict)

    def __init__(self, data, index, parent=None):
        super().__init__(parent)
        self.data = data
        self.index = index
        self.setFixedHeight(45)
        self.setStyleSheet("background-color: transparent; border: none;")
        
        # Qt CSS 스코프 문제 해결: font-size/weight 사용 시 font-family 명시
        _app_ff = QApplication.font().family() or 'Pretendard'
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(8)
        
        self.lbl_handle = QLabel("☰")
        self.lbl_handle.setFixedWidth(30)
        self.lbl_handle.setAlignment(Qt.AlignCenter)
        self.lbl_handle.setStyleSheet(f"""
            QLabel {{
                color: #9ca3af; 
                font-size: 16px; 
                font-weight: bold;
                font-family: '{_app_ff}';
                border: none;
                background: transparent;
            }}
        """)
        self.lbl_handle.setCursor(Qt.SizeAllCursor)
        layout.addWidget(self.lbl_handle)
        
        self.frame_text = QFrame()
        self.frame_text.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #e5e7eb; border-radius: 6px; }
            QFrame:hover { border: 1px solid #FF5722; background-color: #fff9f7; }
        """)
        text_layout = QHBoxLayout(self.frame_text)
        text_layout.setContentsMargins(15, 0, 15, 0)
        self.lbl_text = QLabel(data["text"])
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet(f"font-size: 14px; color: #1f2937; border: none; background: transparent; font-family: '{_app_ff}';")
        text_layout.addWidget(self.lbl_text)
        layout.addWidget(self.frame_text, 1)
        
        self.frame_key = QFrame()
        self.frame_key.setFixedWidth(80)
        self.frame_key.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #e5e7eb; border-radius: 6px; }
            QFrame:hover { border: 1px solid #FF5722; }
        """)
        key_layout = QHBoxLayout(self.frame_key)
        key_layout.setContentsMargins(0, 0, 0, 0)
        
        if index < 9:
            key_text = f"{config.MODIFIER_NAME} + {index + 1}"
        elif index == 9:
            key_text = f"{config.MODIFIER_NAME} + 0"
        else:
            key_text = "-"
            
        self.lbl_key = QLabel(key_text)
        self.lbl_key.setAlignment(Qt.AlignCenter)
        self.lbl_key.setStyleSheet(f"color: #4b5563; font-weight: bold; font-size: 12px; border: none; background: transparent; font-family: '{_app_ff}';")
        key_layout.addWidget(self.lbl_key)
        layout.addWidget(self.frame_key)
        
        self.frame_del = QFrame()
        self.frame_del.setFixedWidth(40)
        self.frame_del.setStyleSheet("""
            QFrame { 
                background-color: #FF5722; 
                border: none; 
                border-radius: 6px; 
            }
            QFrame:hover { 
                background-color: #E64A19; 
            }
        """)
        del_layout = QHBoxLayout(self.frame_del)
        del_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_del = QPushButton()
        self.btn_del.setFixedSize(36, 36)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        
        icon_path = os.path.join(config.ASSETS_DIR, "close_white.svg").replace("\\", "/")
        icon_hover_path = os.path.join(config.ASSETS_DIR, "close_white_hover.svg").replace("\\", "/")
        self.btn_del.setStyleSheet(f"""
            QPushButton {{ 
                border: none; 
                background: transparent; 
                qproperty-icon: url("{icon_path}");
                qproperty-iconSize: 18px 18px;
            }}
            QPushButton:hover {{ 
                qproperty-icon: url("{icon_hover_path}");
            }}
        """)
        self.btn_del.clicked.connect(lambda: self.delete_signal.emit(self.data))
        del_layout.addWidget(self.btn_del)
        layout.addWidget(self.frame_del)

# =================================================================
# 드래그앤드롭 시 삽입 위치를 표시하는 오버레이 위젯 (DropOverlay)
# =================================================================
class DropOverlay(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WA_NoSystemBackground)
        self.line_y = -1
        self.hide()

    def paintEvent(self, event):
        if self.line_y != -1:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("#FF5722"), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
            painter.setPen(pen)
            
            margin = 10
            painter.drawLine(margin, self.line_y, self.width() - margin, self.line_y)

# =================================================================
# 드래그앤드롭 지원 QListWidget (DragDropListWidget)
# =================================================================
class DragDropListWidget(QListWidget):
    def __init__(self, parent_dialog, parent=None):
        super().__init__(parent)
        self.parent_dialog = parent_dialog
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(False)
        self.setDragDropMode(QAbstractItemView.InternalMove)
        self.drag_src_row = -1
        
        self.overlay = DropOverlay(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.viewport().geometry())

    def startDrag(self, supportedActions):
        from PySide6.QtGui import QCursor
        pos = self.viewport().mapFromGlobal(QCursor.pos())
        item = self.itemAt(pos)
        if not item:
            item = self.currentItem()
        if not item:
            return
            
        self.drag_src_row = self.row(item)
        card_widget = self.itemWidget(item)
        if not card_widget:
            super().startDrag(supportedActions)
            return
            
        pixmap = card_widget.grab()
        
        transparent_pixmap = QPixmap(pixmap.size())
        transparent_pixmap.fill(Qt.transparent)
        painter = QPainter(transparent_pixmap)
        painter.setOpacity(0.75)
        painter.drawPixmap(0, 0, pixmap)
        painter.end()
        
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-qabstractitemmodeldatalist", QByteArray())
        drag.setMimeData(mime_data)
        
        drag.setPixmap(transparent_pixmap)
        drag.setHotSpot(QPoint(25, transparent_pixmap.height() // 2))
        
        drag.exec(supportedActions)

    def dragMoveEvent(self, event):
        super().dragMoveEvent(event)
        self.overlay.setGeometry(self.viewport().geometry())
        
        from PySide6.QtGui import QCursor
        target_pos = self.viewport().mapFromGlobal(QCursor.pos())
        hover_item = self.itemAt(target_pos)
        
        if hover_item:
            rect = self.visualItemRect(hover_item)
            if target_pos.y() < rect.y() + rect.height() // 2:
                line_y = rect.y()
            else:
                line_y = rect.y() + rect.height()
            
            self.overlay.line_y = line_y
            self.overlay.show()
            self.overlay.update()
        else:
            if self.count() > 0:
                last_item = self.item(self.count() - 1)
                rect = self.visualItemRect(last_item)
                self.overlay.line_y = rect.y() + rect.height()
                self.overlay.show()
                self.overlay.update()
            else:
                self.overlay.hide()
                
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.overlay.line_y = -1
        self.overlay.hide()
        super().dragLeaveEvent(event)

    def dropEvent(self, event):
        self.overlay.line_y = -1
        self.overlay.hide()
        
        from PySide6.QtGui import QCursor
        target_pos = self.viewport().mapFromGlobal(QCursor.pos())
        hover_item = self.itemAt(target_pos)
        
        N = self.count()
        if N == 0:
            event.setDropAction(Qt.IgnoreAction)
            event.accept()
            return
            
        if hover_item:
            rect = self.visualItemRect(hover_item)
            hover_row = self.row(hover_item)
            if target_pos.y() < rect.y() + rect.height() // 2:
                L = hover_row
            else:
                L = hover_row + 1
        else:
            L = N
            
        src_row = self.drag_src_row
        
        if src_row >= 0:
            if L == src_row or L == src_row + 1:
                self.parent_dialog.refresh_list()
            elif L < src_row:
                self.parent_dialog.move_idiom(src_row, L)
            else:
                self.parent_dialog.move_idiom(src_row, L - 1)
            
        event.setDropAction(Qt.IgnoreAction)
        event.accept()

# =================================================================
class SettingsDialog(PreferencesDialog):
    def __init__(self, parent=None):
        super().__init__(parent, active_page_idx=0)

class IdiomSettingsDialog(PreferencesDialog):
    def __init__(self, parent=None):
        super().__init__(parent, active_page_idx=2)

# =================================================================
# TitleBarButton: SVG 아이콘 전용 프레임런스 버튼
# =================================================================
class TitleBarButton(QPushButton):
    def __init__(self, svg_normal, svg_hover, hover_bg_color, parent=None):
        super().__init__(parent)
        self.svg_normal = svg_normal
        self.svg_hover = svg_hover
        self.hover_bg_color = hover_bg_color
        
        self.setFixedSize(24, 24)
        self.setCursor(Qt.PointingHandCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 12px;
                padding: 0px;
                margin: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }}
            QPushButton:hover, QPushButton:focus {{
                background-color: {self.hover_bg_color};
                outline: none;
            }}
        """)
        self.update_icon(False)

    def update_icon(self, is_hover):
        from PySide6.QtSvg import QSvgRenderer
        from PySide6.QtCore import QByteArray, QRect
        from PySide6.QtGui import QIcon, QPixmap, QPainter
        
        svg_content = self.svg_hover if (is_hover and self.svg_hover) else self.svg_normal
        renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
        pixmap = QPixmap(24, 24)
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing, True)
        renderer.render(painter, QRect(4, 4, 16, 16))
        painter.end()
        
        self.setIcon(QIcon(pixmap))
        self.setIconSize(QSize(24, 24))

    def enterEvent(self, event):
        self.update_icon(True)
        super().enterEvent(event)
        if self.toolTip():
            from PySide6.QtGui import QHelpEvent, QCursor
            from PySide6.QtCore import QEvent, QPoint
            from PySide6.QtWidgets import QApplication
            
            help_event = QHelpEvent(QEvent.ToolTip, QPoint(0, 0), QCursor.pos())
            QApplication.sendEvent(self, help_event)

    def leaveEvent(self, event):
        self.update_icon(False)
        super().leaveEvent(event)

    def showEvent(self, event):
        self.update_icon(False)
        super().showEvent(event)

class MagnetToggleButton(TitleBarButton):
    def __init__(self, is_sticky=True, parent=None):
        self.is_sticky = is_sticky
        self.svg_active_normal = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>'
        self.svg_active_hover = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4F46E5" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>'
        self.svg_inactive_normal = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M15 9.34V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H7.89"/><path d="m2 2 20 20"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h11"/></svg>'
        self.svg_inactive_hover = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4B5563" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M15 9.34V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H7.89"/><path d="m2 2 20 20"/><path d="M9 9v1.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h11"/></svg>'
        
        super().__init__(self.svg_active_normal, self.svg_active_hover, "#E5E7EB", parent)
        self.update_magnet_state(is_sticky)

    def update_magnet_state(self, is_sticky):
        self.is_sticky = is_sticky
        if self.is_sticky:
            self.svg_normal = self.svg_active_normal
            self.svg_hover = self.svg_active_hover
            self.hover_bg_color = "#E0E7FF"
            self.setToolTip("고정 모드 활성화됨 (메인 창과 함께 이동)")
        else:
            self.svg_normal = self.svg_inactive_normal
            self.svg_hover = self.svg_inactive_hover
            self.hover_bg_color = "#D1D5DB"
            self.setToolTip("고정 모드 비활성화됨 (개별 이동)")
        
        self.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: none;
                border-radius: 12px;
                padding: 0px;
                margin: 0px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
            }}
            QPushButton:hover, QPushButton:focus {{
                background-color: {self.hover_bg_color};
                outline: none;
            }}
        """)
        self.update_icon(False)

# =================================================================
# 관용구 플로팅 뷰어 (FloatingIdiomViewer)
# =================================================================
class FloatingIdiomViewer(QDialog):
    idiom_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관용구 도우미")
        self.is_sticky = True # 자석(Sticky) 모드 활성화 상태
        self.show_help = False # 사용 안내 토글 상태 (기본값: 숨김)
        
        # 프레임리스 윈도우 및 투명 배경 설정
        self.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.resize(300, 450)
        
        self.init_ui()
        self.list_widget.setFocusPolicy(Qt.NoFocus)
        self.refresh_list()
        
        # 8방향 리사이즈 및 타이틀바 드래그 이동 등록
        from .window_resizer import FramelessWindowResizer
        self.resizer = FramelessWindowResizer(self, self.title_bar)
        
        self.search_bar.installEventFilter(self)

    def eventFilter(self, watched, event):
        from PySide6.QtCore import QEvent
        if watched == self.search_bar:
            if event.type() == QEvent.FocusIn:
                flags = self.windowFlags()
                if flags & Qt.WindowDoesNotAcceptFocus:
                    self.setWindowFlags(flags & ~Qt.WindowDoesNotAcceptFocus)
                    self.show()
            elif event.type() == QEvent.FocusOut:
                flags = self.windowFlags()
                if not (flags & Qt.WindowDoesNotAcceptFocus):
                    self.setWindowFlags(flags | Qt.WindowDoesNotAcceptFocus)
                    self.show()
        return super().eventFilter(watched, event)

    def toggle_sticky(self):
        self.is_sticky = not self.is_sticky
        self.btn_magnet.update_magnet_state(self.is_sticky)
        if self.is_sticky:
            parent = self.parent()
            if parent and hasattr(parent, 'geometry'):
                pos = (self.pos().x() - parent.x(), self.pos().y() - parent.y())
                parent._idiom_relative_pos = pos


    def hideEvent(self, event):
        parent = self.parent()
        if parent and hasattr(parent, 'geometry'):
            pos = (self.pos().x() - parent.x(), self.pos().y() - parent.y())
            size = (self.width(), self.height())
            parent._idiom_relative_pos = pos
            parent._idiom_size = size
            config.update_idiom_viewer_geometry(pos, size)
        super().hideEvent(event)

    def closeEvent(self, event):
        parent = self.parent()
        if parent and hasattr(parent, 'geometry'):
            pos = (self.pos().x() - parent.x(), self.pos().y() - parent.y())
            size = (self.width(), self.height())
            parent._idiom_relative_pos = pos
            parent._idiom_size = size
            config.update_idiom_viewer_geometry(pos, size)
        super().closeEvent(event)

    def moveEvent(self, event):
        parent = self.parent()
        if parent and hasattr(parent, 'geometry') and self.isVisible():
            if not getattr(self, '_is_moving_by_parent', False):
                pos = (self.pos().x() - parent.x(), self.pos().y() - parent.y())
                parent._idiom_relative_pos = pos
                size = parent._idiom_size if parent._idiom_size else (self.width(), self.height())
                config.update_idiom_viewer_geometry(pos, size)
        super().moveEvent(event)

    def resizeEvent(self, event):
        parent = self.parent()
        if parent and hasattr(parent, 'geometry') and self.isVisible():
            size = (self.width(), self.height())
            parent._idiom_size = size
            pos = (self.pos().x() - parent.x(), self.pos().y() - parent.y())
            parent._idiom_relative_pos = pos
            config.update_idiom_viewer_geometry(pos, size)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 1))
        super().paintEvent(event)

    def init_ui(self):
        # 1. 커스텀 타이틀바 생성
        self.title_bar = QFrame()
        self.title_bar.setObjectName("TitleBar")
        self.title_bar.setFixedHeight(34)
        self.title_bar.setStyleSheet("""
            QFrame#TitleBar {
                background-color: #FFFFFF;
                border-top-left-radius: 7px;
                border-top-right-radius: 7px;
                border-bottom: 1px solid #E5E7EB;
            }
        """)
        title_layout = QHBoxLayout(self.title_bar)
        title_layout.setContentsMargins(12, 0, 12, 0)
        title_layout.setSpacing(6)
        
        # Title icon using SVG
        lbl_icon = QLabel()
        lbl_icon.setFixedSize(14, 14)
        lbl_icon.setStyleSheet("background: transparent; border: none;")
        pixmap = get_colored_pixmap(config.ICON_IDIOM, "#1F2937", 14, 14)
        lbl_icon.setPixmap(pixmap)
        title_layout.addWidget(lbl_icon)
        
        lbl_title = QLabel("관용구 도우미")
        lbl_title.setStyleSheet("color: #1F2937; font-weight: 600; font-size: 13px; background: transparent; border: none; font-family: 'Pretendard';")
        title_layout.addWidget(lbl_title)
        
        # 도움말 (?) 버튼 추가 (타이틀 바로 옆에 배치)
        svg_help_normal = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4B5563" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>'
        svg_help_hover = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#FF5722" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><path d="M12 17h.01"/></svg>'
        self.btn_help = TitleBarButton(svg_help_normal, svg_help_hover, "#E5E7EB")
        
        is_mac = sys.platform == "darwin"
        shortcut_key = "⌥" if is_mac else "Alt"
        help_text = f"빠른 입력: 단축키({shortcut_key}+숫자) 혹은 더블 클릭으로 본문에 자동 삽입"
        self.btn_help.setToolTip(help_text)
        title_layout.addWidget(self.btn_help)
        
        title_layout.addStretch()
        
        # 자석 토글 버튼 추가
        self.btn_magnet = MagnetToggleButton(self.is_sticky)
        self.btn_magnet.clicked.connect(self.toggle_sticky)
        title_layout.addWidget(self.btn_magnet)
        
        # 설정 (톱니바퀴) 버튼 추가
        svg_settings_normal = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4B5563" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>'
        svg_settings_hover = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#FF5722" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.1a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/></svg>'
        self.btn_settings = TitleBarButton(svg_settings_normal, svg_settings_hover, "#E5E7EB")
        self.btn_settings.setToolTip("환경 설정 (관용구 및 기본 옵션 변경)")
        self.btn_settings.clicked.connect(self.open_preferences)
        title_layout.addWidget(self.btn_settings)
        
        # SVG 정의
        svg_close_normal = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#4B5563" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        svg_close_hover = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>'
        
        # 닫기 버튼
        btn_close = TitleBarButton(svg_close_normal, svg_close_hover, "#EF4444")
        btn_close.clicked.connect(self.close)
        title_layout.addWidget(btn_close)
        
        # 2. 메인 외곽 프레임
        self.main_frame = QFrame(self)
        self.main_frame.setObjectName("MainFrame")
        self.main_frame.setStyleSheet("""
            QFrame#MainFrame {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
            }
        """)
        
        main_layout = QVBoxLayout(self.main_frame)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.addWidget(self.title_bar)
        
        # 3. 내부 컨텐츠 영역
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(15, 15, 15, 15)
        content_layout.setSpacing(10)
        main_layout.addLayout(content_layout)
        
        # 4. 다이얼로그 본체 레이아웃
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(6, 6, 6, 6)
        outer_layout.addWidget(self.main_frame)
        
        # 이하 기존 search_bar 등 위젯 생성은 content_layout에 추가
        self.search_bar = SingleClickLineEdit()
        self.search_bar.setPlaceholderText("🔍 관용구 검색...")
        self.search_bar.setFixedHeight(36)
        self.search_bar.setClearButtonEnabled(True)

        self.search_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding-left: 10px;
                padding-right: 30px;
                background-color: #F9FAFB;
            }
            QLineEdit:focus {
                border: 2px solid #FF5722;
                background-color: white;
            }
        """ + "\n" + config.MODERN_MENU_STYLE)
        self.search_bar.textChanged.connect(self.filter_list)
        content_layout.addWidget(self.search_bar)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_clicked)
        self.list_widget.setStyleSheet("""
            QListWidget {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                background-color: white;
                outline: none;
            }
            QListWidget::item {
                padding: 12px;
                border-bottom: 1px solid #F3F4F6;
                font-size: 13px;
                color: #374151;
            }
            QListWidget::item:hover {
                background-color: #F9FAFB;
            }
            QListWidget::item:selected {
                background-color: #FFECEC;
                color: #FF4B4B;
                font-weight: bold;
                border: none;
            }
        """)
        content_layout.addWidget(self.list_widget)



    def refresh_list(self):
        self.list_widget.clear()
        for item in config.IDIOMS:
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 50))
            
            container = QWidget()
            container.setAttribute(Qt.WA_TransparentForMouseEvents)
            item_layout = QHBoxLayout(container)
            item_layout.setContentsMargins(15, 0, 15, 0)
            item_layout.setSpacing(10)
            
            lbl_text = QLabel(item['text'])
            lbl_text.setStyleSheet("font-size: 14px; font-weight: 500; color: #1F2937; border: none; background: transparent;")
            
            item_layout.addWidget(lbl_text, 1)
            
            if item.get('key'):
                key_text = f"{config.MODIFIER_NAME} + {item['key']}"
                lbl_key = QLabel(key_text)
                lbl_key.setAlignment(Qt.AlignCenter)
                lbl_key.setStyleSheet("""
                    QLabel {
                        background-color: #F3F4F6;
                        color: #6B7280;
                        border: 1px solid #E5E7EB;
                        border-radius: 4px;
                        padding: 2px 6px;
                        font-size: 11px;
                        font-weight: bold;
                        font-family: 'SF Pro Text', 'Pretendard';
                    }
                """)
                item_layout.addWidget(lbl_key)
            
            list_item.setData(Qt.UserRole, item['text'])
            
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, container)

    def filter_list(self, text=None):
        if text is None:
            text = self.search_bar.text()
            
        import unicodedata
        query = unicodedata.normalize('NFC', text.lower().strip())
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            data = item.data(Qt.UserRole)
            search_target = str(data).lower() if data else ""
            search_target_norm = unicodedata.normalize('NFC', search_target)
            item.setHidden(query != "" and query not in search_target_norm)

    def on_item_clicked(self, item):
        text = item.data(Qt.UserRole)
        self.idiom_selected.emit(text)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.search_bar.clear()
            event.accept()
        else:
            super().keyPressEvent(event)

    def open_preferences(self):
        parent = self.parent()
        dlg = PreferencesDialog(parent, active_page_idx=2, only_idioms=True)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_list()
            if parent and hasattr(parent, 'setup_idiom_shortcuts'):
                parent.setup_idiom_shortcuts()

# =================================================================
# 선택적 취소를 위한 플로팅 버튼 (FloatingUndoButton)
# =================================================================
class FloatingUndoButton(QPushButton):
    revert_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__("↩ 원래대로", parent)
        self.setFixedSize(90, 32)
        self.setCursor(Qt.PointingHandCursor)
        self.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: white;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #334155;
            }
        """)
        self.target_index = -1
        self.hide()
        self.clicked.connect(lambda: self.revert_requested.emit(self.target_index))

# =================================================================
# 맞춤법 검사 결과 비교 다이얼로그 (SpellCheckDialog)
# =================================================================
class SpellCheckDialog(QDialog):
    def __init__(self, original, corrected, parent=None, initial_vscroll=0):
        super().__init__(parent)
        self.initial_vscroll = initial_vscroll
        self.setWindowTitle("맞춤법 검사 결과 비교")
        self.resize(1000, 700)
        self.result_text = None
        self.diff_data = []
        
        layout = QVBoxLayout(self)
        
        info_label = QLabel("💡 수정된 부분에 커서를 두면 '원래대로' 되돌릴 수 있습니다 (✓: 띄어쓰기, ⁀: 붙여쓰기).")
        info_label.setStyleSheet("color: #2563EB; margin-bottom: 10px; font-weight: bold;")
        layout.addWidget(info_label)

        editor_layout = QHBoxLayout()
        
        scrollbar_style = """
            QScrollBar:vertical {
                border: none;
                background: #F1F5F9;
                width: 14px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: #94A3B8;
                min-height: 40px;
                border-radius: 7px;
                margin: 2px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748B;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                background: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """

        self.edit_org = QTextEdit()
        self.edit_org.setReadOnly(True)
        self.edit_org.setFont(QFont("Pretendard", 13))
        self.edit_org.setPlaceholderText("원본 텍스트")
        self.edit_org.setStyleSheet(f"QTextEdit {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; }} {scrollbar_style}")
        self.edit_org.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        self.edit_new = QTextEdit()
        self.edit_new.setFont(QFont("Pretendard", 13))
        self.edit_new.setPlaceholderText("교정된 텍스트")
        self.edit_new.setStyleSheet(f"QTextEdit {{ border: 1px solid #E2E8F0; border-radius: 8px; background-color: white; padding: 5px; }} {scrollbar_style}")
        self.edit_new.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        editor_layout.addWidget(self.edit_org)
        editor_layout.addWidget(self.edit_new)
        layout.addLayout(editor_layout)

        self.undo_btn = FloatingUndoButton(self.edit_new.viewport())
        self.undo_btn.revert_requested.connect(self.revert_segment)
        self.edit_new.cursorPositionChanged.connect(self.check_cursor_context)

        self._is_syncing = False
        def sync_scroll(source, target):
            if self._is_syncing: return
            self._is_syncing = True
            target.setValue(source.value())
            self._is_syncing = False

        self.edit_org.verticalScrollBar().valueChanged.connect(lambda: sync_scroll(self.edit_org.verticalScrollBar(), self.edit_new.verticalScrollBar()))
        self.edit_new.verticalScrollBar().valueChanged.connect(lambda: sync_scroll(self.edit_new.verticalScrollBar(), self.edit_org.verticalScrollBar()))
        self.edit_org.horizontalScrollBar().valueChanged.connect(lambda: sync_scroll(self.edit_org.horizontalScrollBar(), self.edit_new.horizontalScrollBar()))
        self.edit_new.horizontalScrollBar().valueChanged.connect(lambda: sync_scroll(self.edit_new.horizontalScrollBar(), self.edit_org.horizontalScrollBar()))

        self.show_diff(original, corrected)

        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedSize(100, 40)
        btn_cancel.clicked.connect(self.reject)
        
        btn_apply = QPushButton("교정 내용 적용")
        btn_apply.setFixedSize(130, 40)
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                font-weight: bold;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #F4511E;
            }
        """)
        btn_apply.clicked.connect(self.apply_changes)
        
        btn_layout.addStretch()
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)

    def get_granular_segments(self, org, new, tag_type):
        if tag_type == 'equal':
            return [('equal', org, new)]
        if not org:
            return [('insert', '', new)]
        if not new:
            return [('delete', org, '')]
        
        res = []
        org_words = re.findall(r'\s+|\S+', org)
        new_words = re.findall(r'\s+|\S+', new)
        
        max_len = max(len(org_words), len(new_words))
        for i in range(max_len):
            o_w = org_words[i] if i < len(org_words) else ""
            n_w = new_words[i] if i < len(new_words) else ""
            
            if o_w == n_w:
                res.append(('equal', o_w, n_w))
            elif not o_w:
                res.append(('insert', '', n_w))
            elif not n_w:
                res.append(('delete', o_w, ''))
            else:
                res.append(('replace', o_w, n_w))
        return res

    def show_diff(self, text1, text2):
        start_time = time.time()
        print(f"DEBUG: [SpellCheck] 결과 렌더링 시작 (원본 길이: {len(text1)}, 교정본 길이: {len(text2)})")
        
        self.diff_data = []
        d = difflib.SequenceMatcher(None, text1, text2)
        
        self.edit_org.blockSignals(True)
        self.edit_new.blockSignals(True)
        
        self.edit_org.clear()
        self.edit_new.clear()
        
        cursor_org = self.edit_org.textCursor()
        cursor_new = self.edit_new.textCursor()
        
        opcodes = d.get_opcodes()
        print(f"DEBUG: [SpellCheck] Diff 분석 완료 (Opcode 수: {len(opcodes)})")
        
        current_idx = 0
        self._is_syncing = True

        cursor_org.beginEditBlock()
        cursor_new.beginEditBlock()

        for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
            org_full = text1[i1:i2]
            new_full = text2[j1:j2]
            segments = self.get_granular_segments(org_full, new_full, tag)

            for s_tag, s_org, s_new in segments:
                if s_tag == 'equal':
                    cursor_org.insertText(s_org, QTextCharFormat())
                    cursor_new.insertText(s_new, QTextCharFormat())
                    continue

                diff_item = {'tag': s_tag, 'org': s_org, 'new': s_new, 'id': current_idx}
                self.diff_data.append(diff_item)

                fmt_org = QTextCharFormat()
                fmt_new = QTextCharFormat()
                
                if s_tag == 'replace':
                    fmt_org.setBackground(QColor("#FFCDD2")) 
                    fmt_org.setForeground(QColor("#B71C1C")) 
                    fmt_org.setFontStrikeOut(True)
                    
                    fmt_new.setBackground(QColor("#FFB74D")) 
                    fmt_new.setForeground(QColor("#000000")) 
                    fmt_new.setFontWeight(QFont.Bold)
                    fmt_new.setProperty(QTextFormat.UserProperty + 1, current_idx)
                    
                    cursor_org.insertText(s_org.replace(' ', '✓'), fmt_org)
                    cursor_new.insertText(s_new.replace(' ', '✓'), fmt_new)
                    
                elif s_tag == 'delete':
                    fmt_org.setBackground(QColor("#FFCDD2"))
                    fmt_org.setForeground(QColor("#B71C1C"))
                    fmt_org.setFontStrikeOut(True)
                    cursor_org.insertText(s_org.replace(' ', '✓'), fmt_org)
                    
                    fmt_new.setProperty(QTextFormat.UserProperty + 1, current_idx)
                    if s_org.strip() == "":
                        fmt_new.setBackground(QColor("#E0E7FF"))
                        fmt_new.setForeground(QColor("#4338CA"))
                        fmt_new.setFontWeight(QFont.Bold)
                        cursor_new.insertText("⁀", fmt_new)
                    else:
                        fmt_new.setBackground(QColor("#FFCDD2"))
                        fmt_new.setForeground(QColor("#B71C1C"))
                        cursor_new.insertText(s_org.replace(' ', '✓'), fmt_new)
                    
                elif s_tag == 'insert':
                    fmt_new.setBackground(QColor("#FFB74D"))
                    fmt_new.setForeground(QColor("#000000"))
                    fmt_new.setFontWeight(QFont.Bold)
                    fmt_new.setProperty(QTextFormat.UserProperty + 1, current_idx)
                    cursor_new.insertText(s_new.replace(' ', '✓'), fmt_new)
                
                current_idx += 1

        cursor_org.endEditBlock()
        cursor_new.endEditBlock()

        self.edit_org.blockSignals(False)
        self.edit_new.blockSignals(False)
        self._is_syncing = False
        
        print(f"DEBUG: [SpellCheck] 전체 렌더링 프로세스 완료 (총 소요 시간: {time.time() - start_time:.2f}초)")

        if self.initial_vscroll > 0:
            self.edit_org.verticalScrollBar().setValue(self.initial_vscroll)
            self.edit_new.verticalScrollBar().setValue(self.initial_vscroll)
        else:
            self.edit_org.verticalScrollBar().setValue(0)
            self.edit_new.verticalScrollBar().setValue(0)
            
            c1 = self.edit_org.textCursor()
            c1.movePosition(QTextCursor.Start)
            self.edit_org.setTextCursor(c1)

            c2 = self.edit_new.textCursor()
            c2.movePosition(QTextCursor.Start)
            self.edit_new.setTextCursor(c2)

    def resizeEvent(self, event):
        vbar = self.edit_new.verticalScrollBar()
        old_max = vbar.maximum()
        old_val = vbar.value()
        ratio = old_val / old_max if old_max > 0 else 0
        
        super().resizeEvent(event)
        QTimer.singleShot(10, lambda: vbar.setValue(int(vbar.maximum() * ratio)))

    def check_cursor_context(self):
        cursor = self.edit_new.textCursor()
        fmt = cursor.charFormat()
        diff_id = fmt.property(QTextFormat.UserProperty + 1)
        
        if diff_id is None:
            cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            diff_id = cursor.charFormat().property(QTextFormat.UserProperty + 1)
            cursor.movePosition(QTextCursor.PreviousCharacter)

        if diff_id is not None and isinstance(diff_id, int):
            rect = self.edit_new.cursorRect(cursor)
            btn_pos = rect.topLeft()
            
            target_y = btn_pos.y() - self.undo_btn.height() - 5
            if target_y < 0:
                target_y = rect.bottom() + 5
            
            btn_pos.setY(target_y)
            btn_pos.setX(max(5, btn_pos.x() - 20))
            
            self.undo_btn.move(btn_pos)
            self.undo_btn.target_index = diff_id
            self.undo_btn.show()
            self.undo_btn.raise_()
        else:
            self.undo_btn.hide()

    def revert_segment(self, diff_id):
        """특정 구역을 원본 텍스트로 되돌립니다."""
        item = next((x for x in self.diff_data if x["id"] == diff_id), None)
        if not item: return

        doc = self.edit_new.document()
        start_pos = -1
        end_pos = -1

        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                if hasattr(it, "fragment"):
                    fragment = it.fragment()
                    if fragment.isValid():
                        val = fragment.charFormat().property(QTextFormat.UserProperty + 1)
                        if val is not None and val == diff_id:
                            if start_pos == -1:
                                start_pos = fragment.position()
                            end_pos = fragment.position() + fragment.length()
                it += 1
            block = block.next()

        if start_pos != -1 and end_pos != -1 and start_pos < end_pos:
            org_text = item["org"]
            
            # 원본 텍스트가 순수 공백/줄바꿈이 아닌 실제 글자를 포함하는 경우,
            # 앞뒤 줄바꿈(\n)을 제거합니다.
            # - trailing \n: 문서에 이미 존재하는 블록 구분자와 중복 삽입되는 것을 방지
            # - leading \n:  위 블록의 \n과 org_text 앞의 \n이 겹쳐 빈 줄이 생기는 것을 방지
            if org_text.strip() != "":
                org_text = org_text.strip('\n')
            
            revert_cursor = self.edit_new.textCursor()
            revert_cursor.setPosition(start_pos)
            revert_cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
            revert_cursor.beginEditBlock()
            revert_cursor.insertText(org_text, QTextCharFormat())
            revert_cursor.endEditBlock()

        self.undo_btn.hide()

    def apply_changes(self):
        doc = self.edit_new.document()
        result_chunks = []
        
        block = doc.begin()
        while block.isValid():
            block_text = ""
            it = block.begin()
            while not it.atEnd():
                if hasattr(it, "fragment"):
                    fragment = it.fragment()
                    if fragment.isValid():
                        val = fragment.charFormat().property(QTextFormat.UserProperty + 1)
                        is_deleted_item = False
                        if val is not None and isinstance(val, int):
                            item = next((x for x in self.diff_data if x["id"] == val), None)
                            if item and item["tag"] == "delete":
                                is_deleted_item = True
                                
                        if not is_deleted_item:
                            block_text += fragment.text()
                it += 1
            result_chunks.append(block_text)
            block = block.next()
            
        text = "\n".join(result_chunks)
        text = text.replace("✓", " ")
        text = text.replace("⁀", "")
        
        self.result_text = text
        self.accept()

# =================================================================
# Windows ClearType 폰트 깨짐 방지 전용 커스텀 헤더뷰
# =================================================================
class ClearTypeHeaderView(QHeaderView):
    """Windows에서 QHeaderView 스타일시트 적용 시 ClearType(안티앨리어싱) 렌더링이
    비활성화되어 폰트가 깨져 보이는 Qt 고질 버그를 paintSection() 오버라이드로 해결."""
    def __init__(self, orientation, font, bg_color="#F9FAFB", text_color="#374151", parent=None):
        super().__init__(orientation, parent)
        self._section_font = font
        self._bg_color = QColor(bg_color)
        self._text_color = QColor(text_color)
        self._border_color = QColor("#E5E7EB")

    def paintSection(self, painter, rect, logical_index):
        painter.save()
        # 배경 채우기
        painter.setRenderHint(QPainter.Antialiasing, False)
        painter.fillRect(rect, self._bg_color)
        # 하단 경계선 그리기
        painter.setPen(QPen(self._border_color, 1))
        painter.drawLine(rect.left(), rect.bottom(), rect.right(), rect.bottom())
        # 텍스트 렌더링 - 안티앨리어싱 강제 활성화
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setFont(self._section_font)
        painter.setPen(self._text_color)
        label = self.model().headerData(logical_index, self.orientation(), Qt.DisplayRole)
        if label:
            text_rect = rect.adjusted(8, 0, -8, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignCenter, str(label))
        painter.restore()

# =================================================================
# 스마트 스크립트 병합 다이얼로그 (ScriptMergeDialog)
# =================================================================
class ScriptMergeDialog(QDialog):
    def __init__(self, current_script, new_lines, parent=None):
        """
        current_script: list of dict {'char': str, 'line': str}
        new_lines: list of str
        """
        super().__init__(parent)
        self.setWindowTitle("스마트 스크립트 병합")
        self.resize(1100, 750)
        self.merge_action = None  # "merge", "overwrite", or None
        
        self.current_script = current_script
        self.new_lines = new_lines
        
        # Calculate alignment
        self.aligned_data = self.align_scripts(current_script, new_lines)
        
        self.init_ui()

    def align_scripts(self, current_script, new_lines):
        def normalize_text(text):
            if not text:
                return ""
            return re.sub(r'[\s\W_]+', '', text)

        def calculate_similarity(s1, s2):
            return difflib.SequenceMatcher(None, s1, s2).ratio()

        norm_curr = [normalize_text(x["line"]) for x in current_script]
        norm_new = [normalize_text(x) for x in new_lines]
        
        sm = difflib.SequenceMatcher(None, norm_curr, norm_new)
        opcodes = sm.get_opcodes()
        
        alignment = []
        
        for tag, i1, i2, j1, j2 in opcodes:
            if tag == 'equal':
                for idx in range(i2 - i1):
                    curr_item = current_script[i1 + idx]
                    alignment.append({
                        "status": "equal",
                        "curr_char": curr_item["char"],
                        "curr_line": curr_item["line"],
                        "new_line": new_lines[j1 + idx],
                        "keep_char": True
                    })
            elif tag == 'delete':
                for idx in range(i2 - i1):
                    curr_item = current_script[i1 + idx]
                    alignment.append({
                        "status": "delete",
                        "curr_char": curr_item["char"],
                        "curr_line": curr_item["line"],
                        "new_line": "",
                        "keep_char": False
                    })
            elif tag == 'insert':
                for idx in range(j2 - j1):
                    alignment.append({
                        "status": "insert",
                        "curr_char": "",
                        "curr_line": "",
                        "new_line": new_lines[j1 + idx],
                        "keep_char": False
                    })
            elif tag == 'replace':
                curr_slice = current_script[i1:i2]
                new_slice = new_lines[j1:j2]
                
                used_new = set()
                paired_curr = {}
                
                for c_idx, c_item in enumerate(curr_slice):
                    best_similarity = 0.0
                    best_n_idx = -1
                    for n_idx, n_line in enumerate(new_slice):
                        if n_idx in used_new:
                            continue
                        sim = calculate_similarity(c_item["line"], n_line)
                        if sim > best_similarity:
                            best_similarity = sim
                            best_n_idx = n_idx
                    
                    # 0.70 similarity threshold for fuzzy matching
                    if best_similarity >= 0.70 and best_n_idx != -1:
                        paired_curr[c_idx] = best_n_idx
                        used_new.add(best_n_idx)
                
                for c_idx, c_item in enumerate(curr_slice):
                    if c_idx in paired_curr:
                        n_idx = paired_curr[c_idx]
                        alignment.append({
                            "status": "replace",
                            "curr_char": c_item["char"],
                            "curr_line": c_item["line"],
                            "new_line": new_slice[n_idx],
                            "keep_char": True
                        })
                    else:
                        alignment.append({
                            "status": "delete",
                            "curr_char": c_item["char"],
                            "curr_line": c_item["line"],
                            "new_line": "",
                            "keep_char": False
                        })
                for n_idx, n_line in enumerate(new_slice):
                    if n_idx not in used_new:
                        alignment.append({
                            "status": "insert",
                            "curr_char": "",
                            "curr_line": "",
                            "new_line": n_line,
                            "keep_char": False
                        })
                        
        return alignment

    def get_dialog_font(self, bold=False, strikeout=False, size_px=13, weight=None):
        app_font = QApplication.font()
        f_family = app_font.family()
        if f_family == "sans-serif" or not f_family:
            f_family = "Pretendard"
        font = QFont(f_family)
        font.setPixelSize(size_px)
        if weight is not None:
            font.setWeight(weight)
        else:
            font.setBold(bold)
        font.setStrikeOut(strikeout)
        font.setStyleStrategy(QFont.PreferAntialias)
        font.setHintingPreference(QFont.PreferNoHinting)
        return font

    def get_html_diff(self, text1, text2, mode='delete'):
        """
        기존 대사와 신규 대사 간의 차이점을 분석하여 하이라이트된 HTML 코드로 반환합니다.
        mode: 'delete' (기존 대사용 - 삭제/변경된 부분 빨간색 취소선)
              'insert' (가져올 대사용 - 추가/변경된 부분 초록색/주황색 배경)
        """
        s = difflib.SequenceMatcher(None, text1, text2)
        html = []
        for tag, i1, i2, j1, j2 in s.get_opcodes():
            if tag == 'equal':
                html.append(text1[i1:i2])
            elif tag == 'delete':
                if mode == 'delete':
                    html.append(f'<span style="color: #EF4444; background-color: #FEE2E2; text-decoration: line-through;">{text1[i1:i2]}</span>')
            elif tag == 'insert':
                if mode == 'insert':
                    html.append(f'<span style="color: #10B981; background-color: #ECFDF5; font-weight: bold;">{text2[j1:j2]}</span>')
            elif tag == 'replace':
                if mode == 'delete':
                    html.append(f'<span style="color: #EF4444; background-color: #FEE2E2; text-decoration: line-through;">{text1[i1:i2]}</span>')
                elif mode == 'insert':
                    html.append(f'<span style="color: #F59E0B; background-color: #FEF3C7; font-weight: bold;">{text2[j1:j2]}</span>')
        return "".join(html).replace("\n", "<br>")

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Info Header
        info_label = QLabel("💡 스텝 1의 새로운 대사와 현재 배정 상태를 비교합니다. 수정된 부분의 캐릭터 정보가 자동으로 보존됩니다.")
        info_label.setStyleSheet("color: #2563EB; font-weight: bold; font-size: 13px;")
        layout.addWidget(info_label)
        
        # Table
        self.table = QTableWidget()
        self.table.setFont(self.get_dialog_font(size_px=14))
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["", "기존 대사 (스텝 3)", "상태", "가져올 대사 (스텝 1)"])
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSelectionMode(QAbstractItemView.NoSelection)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        
        # Style header - ClearTypeHeaderView로 Windows 폰트 깨짐 근본 해결
        h_font = QFont(QApplication.font())
        h_font.setPointSize(11)
        h_font.setWeight(QFont.Medium)
        header = ClearTypeHeaderView(Qt.Horizontal, h_font, parent=self.table)
        self.table.setHorizontalHeader(header)
        header.setMinimumHeight(40)
        header.setSectionResizeMode(0, QHeaderView.Interactive)
        header.setSectionResizeMode(1, QHeaderView.Stretch)
        header.setSectionResizeMode(2, QHeaderView.Interactive)
        header.setSectionResizeMode(3, QHeaderView.Stretch)
        self.table.setColumnWidth(0, 110)
        self.table.setColumnWidth(2, 90)
        
        # Populate table
        self.table.setRowCount(len(self.aligned_data))
        for row_idx, item in enumerate(self.aligned_data):
            item_char = QTableWidgetItem(item['curr_char'] if item['curr_char'] else "")
            item_char.setFont(self.get_dialog_font(size_px=14))
            item_char.setTextAlignment(Qt.AlignCenter)
            
            # Status styling
            status_text = ""
            bg_color = ""
            fg_color = ""
            
            if item['status'] == 'equal':
                status_text = "유지"
                bg_color = "#E8F5E9"
                fg_color = "#2E7D32"
            elif item['status'] == 'replace':
                status_text = "수정됨"
                bg_color = "#FFF3E0"
                fg_color = "#EF6C00"
            elif item['status'] == 'insert':
                status_text = "추가됨"
                bg_color = "#E3F2FD"
                fg_color = "#1565C0"
            elif item['status'] == 'delete':
                status_text = "삭제됨"
                bg_color = "#FFEBEE"
                fg_color = "#C62828"
                
            item_status = QTableWidgetItem(status_text)
            item_status.setTextAlignment(Qt.AlignCenter)
            item_status.setBackground(QColor(bg_color))
            item_status.setForeground(QColor(fg_color))
            item_status.setFont(self.get_dialog_font(bold=True, size_px=14))
            
            if item['status'] == 'replace':
                # 수정됨 상태에서는 텍스트를 위젯(QLabel)으로 직접 렌더링하므로 중복 겹침 방지를 위해 빈 문자열로 생성
                item_exist = QTableWidgetItem("")
                item_new = QTableWidgetItem("")
            else:
                exist_text = item['curr_line'] if item['curr_line'] else ""
                item_exist = QTableWidgetItem(exist_text)
                item_exist.setFont(self.get_dialog_font(size_px=14))
                
                item_new = QTableWidgetItem(item['new_line'])
                item_new.setFont(self.get_dialog_font(size_px=14))
                
                # Delete/insert styles
                if item['status'] == 'delete':
                    item_char.setFont(self.get_dialog_font(strikeout=True, size_px=14))
                    item_char.setForeground(QColor("#94A3B8"))
                    item_exist.setFont(self.get_dialog_font(strikeout=True, size_px=14))
                    item_exist.setForeground(QColor("#94A3B8"))
                    item_new.setText("(삭제됨)")
                    item_new.setFont(self.get_dialog_font(strikeout=True, size_px=14))
                    item_new.setForeground(QColor("#94A3B8"))
                elif item['status'] == 'insert':
                    item_new.setFont(self.get_dialog_font(bold=True, size_px=14))
                    item_new.setForeground(QColor("#1565C0"))
            
            self.table.setItem(row_idx, 0, item_char)
            self.table.setItem(row_idx, 1, item_exist)
            self.table.setItem(row_idx, 2, item_status)
            self.table.setItem(row_idx, 3, item_new)
            
            # '수정됨' 상태인 경우, 기존 대사와 신규 대사 간의 차이점을 HTML로 시각화하여 라벨로 부착
            if item['status'] == 'replace':
                # 기존 대사
                exist_html = self.get_html_diff(item['curr_line'], item['new_line'], mode='delete')
                lbl_exist = QLabel(exist_html)
                lbl_exist.setFont(self.get_dialog_font(size_px=14))
                lbl_exist.setWordWrap(True)
                lbl_exist.setStyleSheet("padding: 2px; margin: 0px; background-color: transparent;")
                self.table.setCellWidget(row_idx, 1, lbl_exist)
                
                # 가져올 대사
                new_html = self.get_html_diff(item['curr_line'], item['new_line'], mode='insert')
                lbl_new = QLabel(new_html)
                lbl_new.setFont(self.get_dialog_font(size_px=14))
                lbl_new.setWordWrap(True)
                lbl_new.setStyleSheet("padding: 2px; margin: 0px; background-color: transparent;")
                self.table.setCellWidget(row_idx, 3, lbl_new)
            
        # 열 너비가 최종 결정된 후에 행 높이를 재계산하도록 타이머로 지연 호출 (QLabel의 워드랩 높이 계산 버그 방지)
        QTimer.singleShot(0, self.table.resizeRowsToContents)
        layout.addWidget(self.table)
        
        # Action buttons
        btn_layout = QHBoxLayout()
        
        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedHeight(40)
        btn_cancel.setFixedWidth(100)
        btn_cancel.clicked.connect(self.reject)
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-weight: 600;
                font-family: 'Pretendard', sans-serif;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
            }
        """)
        
        btn_overwrite = QPushButton("덮어쓰기 (전체 초기화)")
        btn_overwrite.setFixedHeight(40)
        btn_overwrite.setStyleSheet("""
            QPushButton {
                background-color: white;
                color: #DC2626;
                border: 1px solid #FCA5A5;
                border-radius: 4px;
                font-weight: 600;
                font-family: 'Pretendard', sans-serif;
                padding: 0 15px;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
            }
        """)
        btn_overwrite.clicked.connect(self.on_overwrite)
        
        btn_merge = QPushButton("스마트 병합 적용")
        btn_merge.setFixedHeight(40)
        btn_merge.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                border-radius: 4px;
                font-weight: 600;
                font-family: 'Pretendard', sans-serif;
                padding: 0 20px;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        btn_merge.clicked.connect(self.on_merge)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_overwrite)
        btn_layout.addWidget(btn_merge)
        
        layout.addLayout(btn_layout)
        
        app_font = QApplication.font()
        f_family = app_font.family()
        if f_family == "sans-serif" or not f_family:
            f_family = "Pretendard"
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self.table.setStyleSheet(f"""
            QTableWidget {{
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                gridline-color: #F3F4F6;
                background-color: white;
                font-family: '{f_family}', 'Malgun Gothic', 'Segoe UI', sans-serif;
                font-size: 14px;
            }}
            QTableWidget::item {{
                font-family: '{f_family}', 'Malgun Gothic', 'Segoe UI', sans-serif;
                font-size: 14px;
            }}
        """)


    def on_overwrite(self):
        reply = CustomMessageBox.question(
            self,
            "덮어쓰기 경고",
            "정말로 덮어쓰시겠습니까?\n이 작업은 기존 배정 내역(캐릭터 정보)을 모두 초기화하며 되돌릴 수 없습니다.",
            [CustomMessageBox.Yes, CustomMessageBox.No]
        )
        if reply == CustomMessageBox.Yes:
            self.merge_action = "overwrite"
            self.accept()

    def on_merge(self):
        self.merge_action = "merge"
        self.accept()

# =================================================================
# 회차 목록용 커스텀 위젯 (EpisodeItemWidget)
# =================================================================
class EpisodeItemWidget(QWidget):
    def __init__(self, name, status, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 4, 5, 4)
        
        self.container = QFrame()
        self.container.setObjectName("itemContainer")
        
        container_layout = QHBoxLayout(self.container)
        container_layout.setContentsMargins(15, 0, 15, 0)
        container_layout.setSpacing(10)

        # 폰트 깨짐 방지 안티앨리어싱 전략 주입
        item_font = QFont("Pretendard", 15)
        item_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        item_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            item_font.setWeight(QFont.Weight.Medium)

        self.lbl_name = QLabel(name)
        self.lbl_name.setFont(item_font)
        self.lbl_name.setStyleSheet("font-weight: 600; font-size: 15px; color: #374151; background: transparent;")
        
        self.lbl_status = QLabel(status)
        self.lbl_status.setFixedSize(80, 26)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        
        status_font = QFont("Pretendard", 11)
        status_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        status_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            status_font.setWeight(QFont.Weight.Bold)
        self.lbl_status.setFont(status_font)
        self.lbl_status.setStyleSheet(self.get_status_style(status))

        container_layout.addWidget(self.lbl_name)
        container_layout.addStretch()
        container_layout.addWidget(self.lbl_status)
        
        self.set_style(False)
        main_layout.addWidget(self.container)

    def set_style(self, selected):
        if selected:
            self.container.setStyleSheet("""
                QFrame#itemContainer {
                    background-color: #E0F2FE;
                    border: 2px solid #7DD3FC;
                    border-radius: 10px;
                }
            """)
            self.lbl_name.setStyleSheet("font-weight: 600; font-size: 15px; color: #0369A1; background: transparent; font-family: 'Pretendard';")
        else:
            self.container.setStyleSheet("""
                QFrame#itemContainer {
                    background-color: #F9FAFB;
                    border: 1px solid #D1D5DB;
                    border-radius: 10px;
                }
            """)
            self.lbl_name.setStyleSheet("font-weight: 600; font-size: 15px; color: #374151; background: transparent; font-family: 'Pretendard';")

    def get_status_style(self, status):
        if status == "분석 완료":
            return """
                background-color: #ECFDF5;
                color: #059669;
                border: 1px solid #10B981;
                border-radius: 13px;
                font-size: 11px;
                font-weight: bold;
            """
        elif status == "분석 대기중":
            return """
                background-color: #EFF6FF;
                color: #2563EB;
                border: 1px solid #3B82F6;
                border-radius: 13px;
                font-size: 11px;
                font-weight: bold;
            """
        else:
            return """
                background-color: #F3F4F6;
                color: #6B7280;
                border: 1px solid #D1D5DB;
                border-radius: 13px;
                font-size: 11px;
                font-weight: bold;
            """

# =================================================================
# 이미지 보기 다이얼로그 (ImageViewerDialog)
# =================================================================
class ImageViewerDialog(QDialog):
    def __init__(self, epi_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"이미지 보기 - {os.path.basename(epi_dir)}")
        self.resize(600, 800)
        self.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: #F9FAFB; border: none; }
            QScrollBar:vertical {
                border: none;
                background: #F3F4F6;
                width: 10px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                min-height: 20px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)
        self.scroll_area.verticalScrollBar().setSingleStep(150)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        self.image_labels = []
        self.original_pixmaps = []
        
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(0)
        
        self.load_images(epi_dir)
        self.content_layout.addStretch()
        
        self.scroll_area.setWidget(self.content_widget)
        layout.addWidget(self.scroll_area)

    def load_images(self, epi_dir):
        img_dir = os.path.join(epi_dir, "images")
        if not os.path.exists(img_dir):
            return
            
        valid_exts = {'.png', '.jpg', '.jpeg'}
        files = sorted([f for f in os.listdir(img_dir) if os.path.splitext(f.lower())[1] in valid_exts])
        
        for f in files:
            lbl = QLabel()
            lbl.setAlignment(Qt.AlignCenter)
            pixmap = QPixmap(os.path.join(img_dir, f))
            if not pixmap.isNull():
                self.image_labels.append(lbl)
                self.original_pixmaps.append(pixmap)
                self.content_layout.addWidget(lbl)
                
        self.scroll_area.viewport().installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj == self.scroll_area.viewport() and event.type() == QEvent.Resize:
            self.adjust_images()
        return super().eventFilter(obj, event)

    def adjust_images(self):
        target_width = self.scroll_area.viewport().width()
        if target_width > 0:
            for lbl, pixmap in zip(self.image_labels, self.original_pixmaps):
                lbl.setPixmap(pixmap.scaledToWidth(target_width, Qt.SmoothTransformation))

# =================================================================
# 작품 및 회차 관리 다이얼로그 (ProjectManagementDialog)
# =================================================================
class ProjectManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작품 및 회차 관리")
        self.setFixedSize(700, 700)
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        self.init_ui()
        self.refresh_projects()

    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        btn_style = """
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 12px;
                font-weight: 600;
                color: #374151;
                font-family: 'Pretendard';
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
            }
            QPushButton:pressed {
                background-color: #F3F4F6;
            }
        """
        
        del_btn_style = btn_style + " QPushButton { color: #EF4444; }"

        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        title_list_header = QWidget()
        title_list_layout = QHBoxLayout(title_list_header)
        title_list_layout.setContentsMargins(0, 0, 0, 5)
        title_list_layout.setSpacing(6)

        icon_lib = QLabel()
        icon_lib.setPixmap(get_icon(config.ICON_LIBRARY).pixmap(20, 20))
        lbl_lib_text = QLabel("작품 목록")
        lbl_lib_text.setStyleSheet("font-weight: 600; font-size: 15px; color: #111827; font-family: 'Pretendard';")

        title_list_layout.addWidget(icon_lib)
        title_list_layout.addWidget(lbl_lib_text)
        title_list_layout.addStretch()
        left_layout.addWidget(title_list_header)

        self.search_bar = SingleClickLineEdit()
        self.search_bar.setFont(QFont("Pretendard", 13))
        self.search_bar.setPlaceholderText("🔍 작품 검색...")
        self.search_bar.setFixedHeight(34)
        self.search_bar.setClearButtonEnabled(True)

        self.search_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding-left: 10px;
                padding-right: 30px;
                background-color: #F9FAFB;
                font-size: 13px;
                font-family: 'Pretendard';
            }
            QLineEdit:focus {
                border: 2px solid #FF5722;
                background-color: white;
            }
        """ + "\n" + config.MODERN_MENU_STYLE)
        self.search_bar.textChanged.connect(self.filter_projects)
        left_layout.addWidget(self.search_bar)
        
        self.list_titles = QListWidget()
        
        list_font = QFont("Pretendard", 13) # 기존 10에서 가독성을 높이기 위해 상향 조정
        list_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        list_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            list_font.setWeight(QFont.Weight.Medium)
        self.list_titles.setFont(list_font)
        self.list_titles.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                outline: none;
                padding: 5px;
                font-family: 'Pretendard';
            }
            QListWidget::item {
                height: 32px;
                padding-left: 12px;
                border-radius: 6px;
                margin-bottom: 2px;
                font-size: 13px;
                font-family: 'Pretendard';
            }
            QListWidget::item:hover {
                background-color: #F3F4F6;
            }
            QListWidget::item:selected {
                background-color: #FFECEC;
                color: #FF5722;
                font-weight: bold;
                font-family: 'Pretendard';
            }
        """)
        self.list_titles.currentTextChanged.connect(self.load_episodes)
        self.list_titles.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_titles.customContextMenuRequested.connect(self.show_project_context_menu)
        left_layout.addWidget(self.list_titles)

        btn_row_title = QHBoxLayout()
        self.btn_add_title = QPushButton("작품 추가")
        self.btn_del_title = QPushButton("삭제")
        
        self.btn_add_title.setStyleSheet(btn_style)
        self.btn_del_title.setStyleSheet(del_btn_style)
        
        self.btn_add_title.clicked.connect(self.add_title)
        self.btn_del_title.clicked.connect(self.delete_title)
        
        btn_row_title.addWidget(self.btn_add_title)
        btn_row_title.addWidget(self.btn_del_title)
        left_layout.addLayout(btn_row_title)
        
        layout.addWidget(left_panel, 2)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        epi_list_header = QWidget()
        epi_list_layout = QHBoxLayout(epi_list_header)
        epi_list_layout.setContentsMargins(0, 0, 0, 5)
        epi_list_layout.setSpacing(6)

        icon_epi = QLabel()
        icon_epi.setPixmap(get_icon(config.ICON_MOVIE).pixmap(20, 20))
        lbl_epi_text = QLabel("회차 목록")
        lbl_epi_text.setStyleSheet("font-weight: 600; font-size: 15px; color: #111827; font-family: 'Pretendard';")

        epi_list_layout.addWidget(icon_epi)
        epi_list_layout.addWidget(lbl_epi_text)
        epi_list_layout.addStretch()
        right_layout.addWidget(epi_list_header)
        
        self.epi_stack = QStackedWidget()
        
        self.empty_widget = QWidget()
        empty_box = QVBoxLayout(self.empty_widget)
        lbl_empty = QLabel("왼쪽 목록에서 작품을 선택해 주세요.")
        lbl_empty.setAlignment(Qt.AlignCenter)
        lbl_empty.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        empty_box.addStretch()
        empty_box.addWidget(lbl_empty)
        empty_box.addStretch()
        
        self.list_episodes = QListWidget()
        self.list_episodes.setFont(list_font)
        self.list_episodes.setSelectionMode(QListWidget.ExtendedSelection)
        self.list_episodes.setSpacing(5)
        self.list_episodes.setContextMenuPolicy(Qt.CustomContextMenu)
        self.list_episodes.customContextMenuRequested.connect(self.show_episode_context_menu)
        self.list_episodes.itemSelectionChanged.connect(self.on_episode_selection_changed)
        self.list_episodes.setStyleSheet("""
            QListWidget {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                outline: none;
                padding: 5px;
                font-family: 'Pretendard';
            }
            QListWidget::item {
                background: transparent;
                border: none;
                padding: 0;
            }
            QListWidget::item:selected {
                background: transparent;
                border: none;
            }
        """)
        
        self.epi_stack.addWidget(self.empty_widget)
        self.epi_stack.addWidget(self.list_episodes)
        right_layout.addWidget(self.epi_stack)

        btn_row_epi = QHBoxLayout()
        self.btn_add_epi = QPushButton("회차 추가")
        self.btn_del_epi = QPushButton("삭제")
        
        self.btn_add_epi.setStyleSheet(btn_style)
        self.btn_del_epi.setStyleSheet(del_btn_style)
        
        self.btn_add_epi.clicked.connect(self.add_episode)
        self.btn_del_epi.clicked.connect(self.delete_episode)
        
        btn_row_epi.addWidget(self.btn_add_epi)
        btn_row_epi.addWidget(self.btn_del_epi)
        right_layout.addLayout(btn_row_epi)

        layout.addWidget(right_panel, 3)

    def filter_projects(self, text):
        import unicodedata
        query = unicodedata.normalize('NFC', text.lower())
        for i in range(self.list_titles.count()):
            item = self.list_titles.item(i)
            item_text = unicodedata.normalize('NFC', item.text().lower())
            item.setHidden(query not in item_text)

    def on_episode_selection_changed(self):
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            widget = self.list_episodes.itemWidget(item)
            if widget:
                widget.set_style(item.isSelected())

    def refresh_projects(self):
        self.list_titles.clear()
        if os.path.exists(PROJECTS_DIR):
            titles = sorted([d for d in os.listdir(PROJECTS_DIR) 
                           if os.path.isdir(os.path.join(PROJECTS_DIR, d))])
            self.list_titles.addItems(titles)
        self.load_episodes("")

    def load_episodes(self, title):
        self.list_episodes.clear()
        if not title:
            self.epi_stack.setCurrentIndex(0)
            return
        
        self.epi_stack.setCurrentIndex(1)
        t_path = os.path.join(PROJECTS_DIR, title)
        if os.path.exists(t_path):
            exclude_dirs = {"images", "character_images", "cache", "temp"}
            episodes = sorted([d for d in os.listdir(t_path) 
                              if os.path.isdir(os.path.join(t_path, d)) and d not in exclude_dirs])
            
            for epi in episodes:
                epi_dir = os.path.join(t_path, epi)
                img_path = os.path.join(epi_dir, "images")
                
                has_images = os.path.exists(img_path) and os.listdir(img_path)
                has_txt = os.path.exists(os.path.join(epi_dir, "script.txt"))
                has_csv = os.path.exists(os.path.join(epi_dir, "script_data.csv"))
                
                if not has_images:
                    status = "대기중"
                elif not (has_txt or has_csv):
                    status = "분석 대기중"
                else:
                    status = "분석 완료"
                
                item = QListWidgetItem(self.list_episodes)
                widget = EpisodeItemWidget(epi, status)
                item.setSizeHint(QSize(0, 60))
                self.list_episodes.addItem(item)
                self.list_episodes.setItemWidget(item, widget)
                item.setData(Qt.UserRole, epi)
                item.setData(Qt.UserRole + 1, status)

    def add_title(self):
        name, ok = QInputDialog.getText(self, "작품 추가", "새로운 작품 이름을 입력하세요:")
        if ok and name.strip():
            path = os.path.join(PROJECTS_DIR, name.strip())
            if os.path.exists(path):
                CustomMessageBox.warning(self, "중복", "이미 존재하는 작품 이름입니다.")
                return
            os.makedirs(path, exist_ok=True)
            self.refresh_projects()

    def delete_title(self):
        current_item = self.list_titles.currentItem()
        if not current_item:
            return

        title = current_item.text()
        reply = CustomMessageBox.question(
            self,
            "작품 삭제",
            f"⚠️ '{title}'의 모든 데이터가 영구 삭제됩니다.\n정말로 진행하시겠습니까?",
            [CustomMessageBox.Yes, CustomMessageBox.No]
        )
        
        if reply == CustomMessageBox.Yes:
            project_path = os.path.join(PROJECTS_DIR, title)
            try:
                if os.path.exists(project_path):
                    import shutil
                    shutil.rmtree(project_path)
                self.refresh_projects()
                
                # 메인 창에 작품 삭제 알림
                mw = self.parent()
                if mw and hasattr(mw, 'handle_deleted_project'):
                    mw.handle_deleted_project(title)
            except Exception as e:
                CustomMessageBox.critical(self, "삭제 오류", f"삭제 중 오류 발생:\n{e}")

    def add_episode(self):
        title_item = self.list_titles.currentItem()
        if not title_item: return
        
        title = title_item.text()
        name, ok = QInputDialog.getText(self, "회차 추가", f"[{title}]의 새로운 회차 이름:")
        if ok and name.strip():
            path = os.path.join(PROJECTS_DIR, title, name.strip(), "images")
            if os.path.exists(os.path.join(PROJECTS_DIR, title, name.strip())):
                CustomMessageBox.warning(self, "중복", "이미 존재하는 회차입니다.")
                return
            os.makedirs(path, exist_ok=True)
            self.load_episodes(title)

    def show_project_context_menu(self, pos):
        item = self.list_titles.itemAt(pos)
        if not item: return
        
        project_name = item.text()
        
        menu = QMenu(self)
        menu.setFont(QApplication.font())
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #D1D5DB; padding: 3px; }
            QMenu::item { padding: 8px 10px 8px 25px; border-radius: 4px; color: #374151; font-size: 14px; margin: 2px 5px; }
            QMenu::item:selected { background-color: #FFECEC; color: #FF4B4B; }
            QMenu::item:disabled { color: #9CA3AF; }
            QMenu::separator { height: 1px; background: #E5E7EB; margin: 5px 10px; }
        """)
        
        action_open_folder = menu.addAction(get_icon(config.ICON_FOLDER), "폴더 열기")
        action_manage_chars = menu.addAction(get_icon(config.ICON_USER), "캐릭터 관리")
        
        action = menu.exec(self.list_titles.mapToGlobal(pos))
        if not action: return
        
        if action == action_open_folder:
            project_path = os.path.join(PROJECTS_DIR, project_name)
            if os.path.exists(project_path):
                open_path(project_path)
        elif action == action_manage_chars:
            dialog = GlobalCharacterSettingsDialog(self, project_name=project_name)
            if dialog.exec() == QDialog.Accepted:
                mw = self.parent()
                if mw and hasattr(mw, 'character_viewer') and mw.character_viewer and mw.character_viewer.isVisible():
                    if getattr(mw, 'current_title', '') == project_name:
                        mw.character_viewer.load_data()

    def show_episode_context_menu(self, pos):
        selected_items = self.list_episodes.selectedItems()
        if not selected_items: return
        
        title_item = self.list_titles.currentItem()
        if not title_item: return
        title = title_item.text()
        
        is_multiple = len(selected_items) > 1
        count = len(selected_items)
        epi_names = [item.data(Qt.UserRole) for item in selected_items]
        
        menu = QMenu(self)
        menu.setFont(QApplication.font())
        menu.setStyleSheet("""
            QMenu { background-color: white; border: 1px solid #D1D5DB; padding: 3px; }
            QMenu::item { padding: 8px 10px 8px 25px; border-radius: 4px; color: #374151; font-size: 14px; margin: 2px 5px; }
            QMenu::item:selected { background-color: #FFECEC; color: #FF4B4B; }
            QMenu::item:disabled { color: #9CA3AF; }
            QMenu::separator { height: 1px; background: #E5E7EB; margin: 5px 10px; }
        """)
        
        action_open_folder = menu.addAction(get_icon(config.ICON_FOLDER), "폴더 열기")
        action_view_image = menu.addAction(get_icon(config.ICON_FILE), "이미지 보기")
        action_view_image.setEnabled(not is_multiple)
        
        menu.addSeparator()
        txt_label = f"일괄 텍스트 저장 ({count}개)" if is_multiple else "텍스트 파일 저장"
        action_save_text = menu.addAction(get_icon(config.ICON_SAVE), txt_label)
        
        excel_label = f"일괄 엑셀 저장 ({count}개)" if is_multiple else "엑셀 파일 저장"
        action_save_excel = menu.addAction(get_icon(config.ICON_EXCEL), excel_label)
        
        has_ready = False
        for item in selected_items:
            status = item.data(Qt.UserRole + 1)
            if status and status != "대기중":
                has_ready = True
                break
        
        action_save_text.setEnabled(has_ready)
        action_save_excel.setEnabled(has_ready)
        action_view_image.setEnabled(not is_multiple and has_ready)
        
        menu.addSeparator()
        del_label = f"회차 삭제 ({count}개)" if is_multiple else "회차 삭제"
        action_delete = menu.addAction(get_icon(config.ICON_DELETE), del_label)
        
        action = menu.exec(self.list_episodes.mapToGlobal(pos))
        if not action: return
        
        if action == action_open_folder:
            for name in epi_names:
                epi_dir = os.path.join(PROJECTS_DIR, title, name)
                if os.path.exists(epi_dir): open_path(epi_dir)
        elif action == action_view_image:
            epi_dir = os.path.join(PROJECTS_DIR, title, epi_names[0])
            dialog = ImageViewerDialog(epi_dir, self)
            dialog.exec()
        elif action == action_save_text:
            self.batch_save_text()
        elif action == action_save_excel:
            self.batch_save_excel()
        elif action == action_delete:
            self.delete_episode()

    def delete_episode(self):
        title_item = self.list_titles.currentItem()
        selected_items = self.list_episodes.selectedItems()
        if not title_item or not selected_items: return
        
        title = title_item.text()
        count = len(selected_items)
        
        if count == 1:
            msg = f"⚠️ '{selected_items[0].data(Qt.UserRole)}'의 모든 데이터가 삭제됩니다.\n진행하시겠습니까?"
        else:
            msg = f"⚠️ 선택한 {count}개의 회차와 모든 데이터가 삭제됩니다.\n진행하시겠습니까?"

        reply = CustomMessageBox.question(
            self,
            "회차 삭제",
            msg,
            [CustomMessageBox.Yes, CustomMessageBox.No]
        )
        
        if reply == CustomMessageBox.Yes:
            import shutil
            success_count = 0
            deleted_episodes = []
            for item in selected_items:
                epi_name = item.data(Qt.UserRole)
                epi_path = os.path.join(PROJECTS_DIR, title, epi_name)
                try:
                    if os.path.exists(epi_path):
                        shutil.rmtree(epi_path)
                    success_count += 1
                    deleted_episodes.append(epi_name)
                except Exception as e:
                    print(f"Delete failed for {epi_name}: {e}")

            self.load_episodes(title)
            
            # 메인 창에 회차 삭제 알림
            if deleted_episodes:
                mw = self.parent()
                if mw and hasattr(mw, 'handle_deleted_episodes'):
                    mw.handle_deleted_episodes(title, deleted_episodes)

            if success_count < count:
                CustomMessageBox.warning(self, "삭제 완료", f"{count}개 중 {success_count}개 삭제 완료 (일부 실패)")

    def batch_save_text(self):
        title_item = self.list_titles.currentItem()
        selected_items = self.list_episodes.selectedItems()
        if not title_item or not selected_items: return
        
        title = title_item.text()
        count = len(selected_items)
        
        save_dir = None
        single_save_path = None
        
        if count == 1:
            epi_name = selected_items[0].data(Qt.UserRole)
            default_path = os.path.join(config.get_initial_dir(), f"{title}_{epi_name}_텍스트.txt")
            options = QFileDialog.Option(0) if platform.system() == "Darwin" else QFileDialog.DontConfirmOverwrite
            single_save_path, _ = QFileDialog.getSaveFileName(self, "텍스트 파일 저장", default_path, "Text Files (*.txt)", options=options)
            if not single_save_path: return
            config.update_last_save_dir(single_save_path)
            
            if os.path.exists(single_save_path):
                reply = CustomMessageBox.question(
                    self,
                    "파일 중복 확인",
                    f"'{os.path.basename(single_save_path)}' 파일이 이미 존재합니다.\n기존 파일을 대체할까요, 아니면 새 이름으로 저장할까요?",
                    ["덮어쓰기", "새 이름으로 저장", "취소"]
                )
                
                if reply == "덮어쓰기":
                    pass 
                elif reply == "새 이름으로 저장":
                    single_save_path = get_unique_path(single_save_path)
                else:
                    return
        else:
            save_dir = QFileDialog.getExistingDirectory(self, "텍스트 파일을 저장할 폴더 선택", config.get_initial_dir())
            if not save_dir: return
            config.update_last_save_dir(save_dir)
        
        success_count = 0
        overwrite_all = False
        skip_all = False
        auto_rename = False

        def get_unique_path(path):
            if not os.path.exists(path):
                return path
            base, ext = os.path.splitext(path)
            counter = 1
            while os.path.exists(f"{base}({counter}){ext}"):
                counter += 1
            return f"{base}({counter}){ext}"

        for item in selected_items:
            epi_name = item.data(Qt.UserRole)
            src_path = os.path.join(PROJECTS_DIR, title, epi_name, "script.txt")
            if os.path.exists(src_path):
                if count == 1:
                    dest_path = single_save_path
                else:
                    dest_filename = f"{title}_{epi_name}_텍스트.txt"
                    dest_path = os.path.join(save_dir, dest_filename)
                
                if count > 1 and os.path.exists(dest_path) and not overwrite_all:
                    if skip_all: continue
                    if overwrite_all: pass
                    elif auto_rename:
                        dest_path = get_unique_path(dest_path)
                    else:
                        dlg = CustomMessageBox(
                            self,
                            "파일 중복 확인",
                            f"파일이 이미 존재합니다:\n{dest_filename}",
                            "question",
                            ["덮어쓰기", "새 이름으로 저장", "건너뛰기", "취소"],
                            checkbox_text="이후 모든 중복 파일에 동일하게 적용"
                        )
                        dlg.exec()
                        clicked = dlg.result_button
                        is_checked = dlg.checkbox.isChecked() if dlg.checkbox else False
                        
                        if clicked == CustomMessageBox.Yes:
                            if is_checked: overwrite_all = True
                        elif clicked == "새 이름으로 저장":
                            if is_checked: auto_rename = True
                            dest_path = get_unique_path(dest_path)
                        elif clicked == CustomMessageBox.No:
                            if is_checked: skip_all = True
                            continue
                        elif clicked == CustomMessageBox.Cancel:
                            break

                try:
                    with open(src_path, "r", encoding="utf-8") as src_f:
                        content = src_f.read()
                    with open(dest_path, "w", encoding="utf-8") as dest_f:
                        dest_f.write(content)
                    success_count += 1
                except Exception as e:
                    print(f"Save failed for {epi_name}: {e}")
        
        if success_count == len(selected_items):
            if hasattr(self.parent(), 'toast'):
                self.parent().toast.show_message(f"📄 {success_count}개의 텍스트 파일 저장 완료")
        elif success_count > 0:
            CustomMessageBox.warning(self, "저장 완료 (일부 실패)", f"{len(selected_items)}개 중 {success_count}개 저장 성공\n(일부 파일 저장에 실패했습니다.)")

    def batch_save_excel(self):
        title_item = self.list_titles.currentItem()
        selected_items = self.list_episodes.selectedItems()
        if not title_item or not selected_items: return
        
        title = title_item.text()
        count = len(selected_items)
        
        save_dir = None
        single_save_path = None
        
        if count == 1:
            epi_name = selected_items[0].data(Qt.UserRole)
            default_path = os.path.join(config.get_initial_dir(), f"{title}_{epi_name}_스크립트.xlsx")
            options = QFileDialog.Option(0) if platform.system() == "Darwin" else QFileDialog.DontConfirmOverwrite
            single_save_path, _ = QFileDialog.getSaveFileName(self, "엑셀 파일 저장", default_path, "Excel Files (*.xlsx)", options=options)
            if not single_save_path: return
            config.update_last_save_dir(single_save_path)
            
            if os.path.exists(single_save_path):
                reply = CustomMessageBox.question(
                    self,
                    "파일 중복 확인",
                    f"'{os.path.basename(single_save_path)}' 파일이 이미 존재합니다.\n기존 파일을 대체할까요, 아니면 새 이름으로 저장할까요?",
                    ["덮어쓰기", "새 이름으로 저장", "취소"]
                )
                
                if reply == "덮어쓰기":
                    pass 
                elif reply == "새 이름으로 저장":
                    single_save_path = get_unique_path(single_save_path)
                else:
                    return
        else:
            save_dir = QFileDialog.getExistingDirectory(self, "엑셀 파일을 저장할 폴더 선택", config.get_initial_dir())
            if not save_dir: return
            config.update_last_save_dir(save_dir)
        
        success_count = 0
        overwrite_all = False
        skip_all = False
        auto_rename = False

        def get_unique_path(path):
            if not os.path.exists(path):
                return path
            base, ext = os.path.splitext(path)
            counter = 1
            while os.path.exists(f"{base}({counter}){ext}"):
                counter += 1
            return f"{base}({counter}){ext}"

        for item in selected_items:
            epi_name = item.data(Qt.UserRole)
            epi_dir = os.path.join(PROJECTS_DIR, title, epi_name)
            
            if os.path.exists(os.path.join(epi_dir, "script.txt")) or os.path.exists(os.path.join(epi_dir, "script_data.csv")):
                if count == 1:
                    dest_path = single_save_path
                else:
                    dest_filename = f"{title}_{epi_name}_스크립트.xlsx"
                    dest_path = os.path.join(save_dir, dest_filename)
                
                if count > 1 and os.path.exists(dest_path) and not overwrite_all:
                    if skip_all: continue
                    if overwrite_all: pass
                    elif auto_rename:
                        dest_path = get_unique_path(dest_path)
                    else:
                        dlg = CustomMessageBox(
                            self,
                            "파일 중복 확인",
                            f"파일이 이미 존재합니다:\n{os.path.basename(dest_path)}",
                            "question",
                            ["덮어쓰기", "새 이름으로 저장", "건너뛰기", "취소"],
                            checkbox_text="이후 모든 중복 파일에 동일하게 적용"
                        )
                        dlg.exec()
                        clicked = dlg.result_button
                        is_checked = dlg.checkbox.isChecked() if dlg.checkbox else False
                        
                        if clicked == CustomMessageBox.Yes:
                            if is_checked: overwrite_all = True
                        elif clicked == "새 이름으로 저장":
                            if is_checked: auto_rename = True
                            dest_path = get_unique_path(dest_path)
                        elif clicked == CustomMessageBox.No:
                            if is_checked: skip_all = True
                            continue
                        elif clicked == CustomMessageBox.Cancel:
                            break
                
                if excel_handler.save_episode_to_excel_final(self, epi_dir, title, epi_name, dest_path):
                    success_count += 1

        if count > 1:
            if success_count == count:
                if hasattr(self.parent(), 'toast'):
                    self.parent().toast.show_message(f"📊 {success_count}개의 엑셀 파일 저장 완료")
            else:
                CustomMessageBox.warning(self, "저장 완료 (일부 실패)", f"{count}개 중 {success_count}개 저장 성공\n(일부 파일 저장에 실패했습니다.)")


# =================================================================
# 업데이트 안내 다이얼로그 (UpdateDialog)
# =================================================================
class UpdateDialog(QDialog):
    def __init__(self, parent=None, version_tag="", release_notes=""):
        super().__init__(parent)
        self.setWindowTitle("업데이트 알림")
        self.setFixedSize(480, 420)
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # 1. 상단 안내
        self.lbl_title = QLabel("새로운 업데이트가 있습니다!")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #111827; font-family: 'Pretendard';")
        layout.addWidget(self.lbl_title)
        
        self.lbl_info = QLabel(f"최신 버전: {version_tag} (현재 버전: {config.APP_VERSION})")
        self.lbl_info.setStyleSheet("font-size: 13px; color: #4B5563; font-family: 'Pretendard';")
        layout.addWidget(self.lbl_info)
        
        # 2. 업데이트 변경점 내용 표시
        self.lbl_notes_title = QLabel("업데이트 내용:")
        self.lbl_notes_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #374151; font-family: 'Pretendard';")
        layout.addWidget(self.lbl_notes_title)
        
        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setMarkdown(release_notes if release_notes else "제공된 업데이트 정보가 없습니다.")
        self.txt_notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                background-color: #F9FAFB;
                padding: 10px;
                color: #374151;
                font-family: 'Pretendard';
                font-size: 13px;
            }
        """)
        layout.addWidget(self.txt_notes)
        
        # 3. 다운로드 진행 바 및 상태 레이블 (처음에는 숨김)
        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(8)
        
        self.lbl_status = QLabel("다운로드 대기 중...")
        self.lbl_status.setStyleSheet("font-size: 12px; color: #2563EB; font-weight: bold; font-family: 'Pretendard';")
        self.progress_layout.addWidget(self.lbl_status)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E5E7EB;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                background-color: #FF5722;
                border-radius: 4px;
            }
        """)
        self.progress_layout.addWidget(self.progress_bar)
        self.progress_container.setVisible(False)
        layout.addWidget(self.progress_container)
        
        # 4. 하단 버튼 바
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        
        self.btn_later = QPushButton("나중에")
        self.btn_later.setFixedSize(100, 36)
        self.btn_later.setCursor(Qt.PointingHandCursor)
        self.btn_later.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                font-weight: bold;
                color: #4B5563;
                font-family: 'Pretendard';
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
            }
        """)
        self.btn_later.clicked.connect(self.reject)
        self.button_layout.addWidget(self.btn_later)
        
        self.btn_update = QPushButton("업데이트 시작")
        self.btn_update.setFixedSize(130, 36)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                color: white;
                font-family: 'Pretendard';
            }
            QPushButton:hover {
                background-color: #E04E1D;
            }
        """)
        self.button_layout.addWidget(self.btn_update)
        
        layout.addLayout(self.button_layout)
        
        self.is_downloading = False

    def set_downloading_mode(self, active=True):
        self.is_downloading = active
        self.btn_later.setVisible(not active)
        self.btn_update.setVisible(not active)
        self.progress_container.setVisible(active)
        if active:
            self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
            self.show()

    def set_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.lbl_status.setText(text)

    def show_error(self, err_msg):
        self.set_downloading_mode(False)
        CustomMessageBox.critical(self, "업데이트 오류", f"업데이트 파일 다운로드 중 오류가 발생했습니다:\n{err_msg}")


# =================================================================
# 업데이트 완료 변경 내역 안내 다이얼로그 (WhatNewDialog)
# =================================================================
class WhatNewDialog(QDialog):
    def __init__(self, parent=None, version_tag="", release_notes=""):
        super().__init__(parent)
        self.setWindowTitle("업데이트 완료")
        self.setFixedSize(500, 480)
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 25, 25, 25)
        layout.setSpacing(15)
        
        # 1. 상단 타이틀 영역
        self.header_layout = QHBoxLayout()
        self.header_layout.setSpacing(15)
        
        self.lbl_party = QLabel("🎉")
        self.lbl_party.setStyleSheet("font-size: 28px; background: transparent; border: none;")
        self.header_layout.addWidget(self.lbl_party)
        
        self.title_text_layout = QVBoxLayout()
        self.title_text_layout.setSpacing(4)
        
        self.lbl_title = QLabel("성공적으로 업데이트되었습니다!")
        self.lbl_title.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF5722; font-family: 'Pretendard';")
        self.title_text_layout.addWidget(self.lbl_title)
        
        self.lbl_info = QLabel(f"새로운 v{version_tag} 버전으로 시작합니다.")
        self.lbl_info.setStyleSheet("font-size: 13px; color: #4B5563; font-family: 'Pretendard';")
        self.title_text_layout.addWidget(self.lbl_info)
        
        self.header_layout.addLayout(self.title_text_layout)
        self.header_layout.addStretch()
        layout.addLayout(self.header_layout)
        
        # 2. 업데이트 상세 변경점 표시
        self.lbl_notes_title = QLabel("새로운 변경 사항:")
        self.lbl_notes_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #374151; font-family: 'Pretendard';")
        layout.addWidget(self.lbl_notes_title)
        
        self.txt_notes = QTextEdit()
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setMarkdown(release_notes if release_notes else "제공된 업데이트 정보가 없습니다.")
        self.txt_notes.setStyleSheet("""
            QTextEdit {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: #F9FAFB;
                padding: 15px;
                color: #374151;
                font-family: 'Pretendard';
                font-size: 13px;
                line-height: 150%;
            }
        """)
        layout.addWidget(self.txt_notes)
        
        # 3. 하단 닫기 버튼
        self.button_layout = QHBoxLayout()
        self.button_layout.addStretch()
        
        self.btn_close = QPushButton("시작하기")
        self.btn_close.setFixedSize(120, 38)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                color: white;
                font-family: 'Pretendard';
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
            QPushButton:pressed {
                background-color: #D84315;
            }
        """)
        self.btn_close.clicked.connect(self.accept)
        self.button_layout.addWidget(self.btn_close)
        
        layout.addLayout(self.button_layout)
# 업데이트 알림 배너 (UpdateNotificationBanner) - 좌측 하단 슬라이드 업 팝업
# =================================================================
class UpdateNotificationBanner(QFrame):
    SVG_UPDATE_ICON = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FF5722" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
        <path d="M12 17V3"/>
        <path d="m6 11 6 6 6-6"/>
        <path d="M19 21H5"/>
    </svg>"""

    def __init__(self, parent, current_version, version_tag, release_notes, on_show_dialog, on_direct_update):
        super().__init__(parent)
        self.current_version = current_version
        self.version_tag = version_tag
        self.release_notes = release_notes
        self.on_show_dialog = on_show_dialog  # Callback takes auto_start (bool)
        self.on_direct_update = on_direct_update
        
        self.setObjectName("UpdateNotificationBanner")
        self.setFixedSize(420, 130)
        self.setStyleSheet("""
            QFrame#UpdateNotificationBanner {
                background-color: #FFFFFF;
                border: 1px solid #FFE5D9;
                border-radius: 12px;
            }
        """)
        
        # 그림자 효과 적용 (Premium UI)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 3)
        self.setGraphicsEffect(shadow)
        
        # 메인 레이아웃 (수직)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 12, 16, 12)
        main_layout.setSpacing(10)
        
        # [콘텐츠 레이아웃] (가로 배치: 아이콘 + 우측 수직 영역)
        content_layout = QHBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(12)
        
        # 1. SVG 아이콘 라벨 (수직 가운데 정렬)
        self.lbl_icon = QLabel()
        self.lbl_icon.setPixmap(self.get_svg_pixmap(self.SVG_UPDATE_ICON, 24, 24))
        self.lbl_icon.setFixedSize(24, 24)
        self.lbl_icon.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(self.lbl_icon, 0, Qt.AlignVCenter)
        
        # 2. 우측 수직 영역 (타이틀, 요약글, 진행률, 버튼 영역을 한데 묶음)
        right_layout = QVBoxLayout()
        right_layout.setSpacing(8)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # 타이틀: 새로운 업데이트가 있습니다! (현재버전 → 업뎃버전)
        self.lbl_title = QLabel(f"새로운 업데이트가 있습니다! (v{current_version} → {version_tag})")
        self.lbl_title.setStyleSheet("""
            QLabel {
                font-family: 'Pretendard';
                font-size: 13px;
                font-weight: bold;
                color: #111827;
            }
        """)
        right_layout.addWidget(self.lbl_title)
        
        # 본문 요약: 1~2줄
        summary_text = self.clean_release_notes(release_notes)
        self.lbl_summary = QLabel(summary_text)
        self.lbl_summary.setStyleSheet("""
            QLabel {
                font-family: 'Pretendard';
                font-size: 11px;
                color: #4B5563;
            }
        """)
        self.lbl_summary.setWordWrap(True)
        right_layout.addWidget(self.lbl_summary)
        
        # [진행률 컨테이너] (다운로드 시작 시 표시 - 우측 영역 내부 하단에 배치됨)
        self.progress_container = QWidget()
        self.progress_layout = QVBoxLayout(self.progress_container)
        self.progress_layout.setContentsMargins(0, 0, 0, 0)
        self.progress_layout.setSpacing(6)
        
        self.lbl_progress_status = QLabel("다운로드 대기 중...")
        self.lbl_progress_status.setStyleSheet("font-size: 12px; color: #2563EB; font-weight: bold; font-family: 'Pretendard';")
        self.progress_layout.addWidget(self.lbl_progress_status)
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(6)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E5E7EB;
                border-radius: 3px;
            }
            QProgressBar::chunk {
                background-color: #FF5722;
                border-radius: 3px;
            }
        """)
        self.progress_layout.addWidget(self.progress_bar)
        self.progress_container.setVisible(False)
        right_layout.addWidget(self.progress_container)
        
        # [하단 영역] 버튼 배치 (오른쪽 정렬 - 우측 영역 하단에 결합)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()
        
        # 자세히 보기 버튼
        self.btn_details = QPushButton("자세히 보기")
        self.btn_details.setFixedSize(95, 31)
        self.btn_details.setCursor(Qt.PointingHandCursor)
        self.btn_details.setStyleSheet("""
            QPushButton {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                color: #4B5563;
                font-family: 'Pretendard';
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
            }
        """)
        self.btn_details.clicked.connect(self.details_clicked)
        bottom_layout.addWidget(self.btn_details)
        
        # 바로 업데이트 버튼
        self.btn_update = QPushButton("업데이트")
        self.btn_update.setFixedSize(95, 31)
        self.btn_update.setCursor(Qt.PointingHandCursor)
        self.btn_update.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                border: none;
                border-radius: 6px;
                color: white;
                font-family: 'Pretendard';
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #E04E1D;
            }
        """)
        self.btn_update.clicked.connect(self.update_clicked)
        bottom_layout.addWidget(self.btn_update)
        
        right_layout.addLayout(bottom_layout)
        content_layout.addLayout(right_layout)
        main_layout.addLayout(content_layout)

        # 닫기 버튼 (우측 상단 절대 좌표 배치 - 모서리 쪽으로 더 밀어 밀착시킴)
        self.btn_close = QPushButton(self)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        self.btn_close.setFixedSize(20, 20)
        
        # 에셋 폴더 내의 close.svg 아이콘 설정
        close_icon = QIcon(os.path.join(config.ASSETS_DIR, "close.svg"))
        self.btn_close.setIcon(close_icon)
        self.btn_close.setIconSize(QSize(10, 10))
        
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
                border-radius: 4px;
            }
        """)
        self.btn_close.clicked.connect(self.hide_banner)
        self.btn_close.setGeometry(394, 6, 20, 20)
        self.btn_close.raise_()
        
        self.target_y = 0
        self.anim = None

    def get_svg_pixmap(self, svg_data, width, height):
        pixmap = QPixmap(width, height)
        pixmap.fill(Qt.transparent)
        pixmap.loadFromData(svg_data)
        return pixmap

    def clean_release_notes(self, notes):
        if not notes:
            return "새로운 업데이트 버전이 준비되었습니다."
        lines = []
        for line in notes.split("\n"):
            line = line.strip()
            if not line:
                continue
            # 마크다운 헤더 마크 제거
            line = re.sub(r'^#+\s*', '', line)
            # 마크다운 굵게/기울임/취소선/코드 포맷팅 제거
            line = re.sub(r'\*\*|__|\*|_|`|~~', '', line)
            # 리스트 아이템 마커 표준화
            line = re.sub(r'^[-\*\+]\s*', '• ', line)
            
            # 너무 긴 라인은 말줄임표 처리 (가로폭 352px 기준이므로 50자로 단축)
            if len(line) > 50:
                line = line[:48] + "..."
                
            lines.append(line)
            if len(lines) >= 2:
                break
        return "\n".join(lines) if lines else "새로운 업데이트 버전이 준비되었습니다."

    def update_clicked(self):
        if hasattr(self, 'on_direct_update') and self.on_direct_update:
            self.on_direct_update()

    def details_clicked(self):
        self.hide_banner()
        self.on_show_dialog(False)

    def set_downloading_mode(self, active=True):
        self.is_downloading = active
        self.btn_details.setVisible(not active)
        self.btn_update.setVisible(not active)
        self.lbl_summary.setVisible(not active)
        self.progress_container.setVisible(active)
        self.btn_close.setEnabled(not active)
        self.btn_close.setVisible(not active)
        
        # 다운로드 중일 때는 배너 박스 크기를 작게(85px로) 축소하여 불필요한 공백을 줄이고 균형감 확보
        if active:
            self.setFixedSize(420, 85)
        else:
            self.setFixedSize(420, 130)
            
        # 크기가 변경되었으므로 부모창 내에서의 y 위치(바닥 기준 위치)를 재정렬합니다.
        if self.parent():
            parent_rect = self.parent().rect()
            self.target_y = parent_rect.height() - self.height() - 20
            self.move(self.x(), self.target_y)

    def set_progress(self, percent, text):
        self.progress_bar.setValue(percent)
        self.lbl_progress_status.setText(text)

    def show_error(self, err_msg):
        self.set_downloading_mode(False)
        CustomMessageBox.critical(self, "업데이트 오류", f"업데이트 파일 다운로드 중 오류가 발생했습니다:\n{err_msg}")

    def show_banner(self):
        if not self.parent():
            return
        
        self.show()
        self.raise_()
        
        parent_rect = self.parent().rect()
        width = self.width()
        height = self.height()
        
        x = 20
        self.target_y = parent_rect.height() - height - 20
        
        # 시작 위치 (부모 창 하단 바깥쪽에서 대기)
        self.setGeometry(x, parent_rect.height(), width, height)
        
        # 슬라이드 업 애니메이션
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(400)
        self.anim.setStartValue(QPoint(x, parent_rect.height()))
        self.anim.setEndValue(QPoint(x, self.target_y))
        self.anim.setEasingCurve(QEasingCurve.OutCubic)
        self.anim.start()

    def hide_banner(self):
        if not self.parent():
            self.close()
            return
            
        parent_rect = self.parent().rect()
        x = self.x()
        
        # 슬라이드 다운 애니메이션
        self.anim = QPropertyAnimation(self, b"pos")
        self.anim.setDuration(300)
        self.anim.setStartValue(self.pos())
        self.anim.setEndValue(QPoint(x, parent_rect.height()))
        self.anim.setEasingCurve(QEasingCurve.InCubic)
        self.anim.finished.connect(self.close)
        self.anim.start()

    def update_position(self):
        if not self.parent() or not self.isVisible():
            return
        parent_rect = self.parent().rect()
        width = self.width()
        height = self.height()
        x = 20
        self.target_y = parent_rect.height() - height - 20
        
        # 애니메이션 동작 중인 경우 대상을 변경하고, 그렇지 않으면 즉시 지오메트리 조정
        if self.anim and self.anim.state() == QPropertyAnimation.Running:
            self.anim.setEndValue(QPoint(x, self.target_y))
        else:
            self.setGeometry(x, self.target_y, width, height)

class SVGCloseButton(QPushButton):
    SVG_CLOSE_NORMAL = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#4b5563" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>"""
    SVG_CLOSE_HOVER = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(22, 22)
        self.setCursor(Qt.PointingHandCursor)
        
        self.pix_normal = QPixmap()
        self.pix_normal.loadFromData(self.SVG_CLOSE_NORMAL)
        self.icon_normal = QIcon(self.pix_normal)
        
        self.pix_hover = QPixmap()
        self.pix_hover.loadFromData(self.SVG_CLOSE_HOVER)
        self.icon_hover = QIcon(self.pix_hover)
        
        self.setIcon(self.icon_normal)
        self.setIconSize(QSize(10, 10))
        
        self.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 11px;
                background-color: #f3f4f6;
            }
            QPushButton:hover {
                background-color: #FF5722;
            }
        """)

    def enterEvent(self, event):
        self.setIcon(self.icon_hover)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self.icon_normal)
        super().leaveEvent(event)

# =================================================================
# Apple 스타일 프로그램 정보 다이얼로그 (AboutDialog)
# =================================================================
class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Webtoon Scripter 제품 정보")
        self.setFixedSize(440, 510)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground) # 둥근 테두리 구현을 위한 투명화
        
        self.init_ui()

    def init_ui(self):
        # 외부 레이아웃 (마진 제거)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # 내부 카드 바디 (하얀색 배경 + 모던 스타일)
        self.body = QFrame()
        self.body.setObjectName("AboutBody")
        self.body.setStyleSheet("""
            QFrame#AboutBody {
                background-color: #ffffff;
                border: 1px solid #caced6;
                border-radius: 8px;
            }
        """)
        
        body_layout = QVBoxLayout(self.body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        # 1. 상단 커스텀 타이틀바
        title_bar = QWidget()
        title_bar.setFixedHeight(40)
        title_bar.setStyleSheet("background-color: #f1f3f9; border-top-left-radius: 7px; border-top-right-radius: 7px;")
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(15, 0, 15, 0)
        
        lbl_title_bar = QLabel("제품 정보")
        lbl_title_bar.setStyleSheet("font-size: 13px; font-weight: bold; color: #1f2937; background: transparent; border: none;")
        title_layout.addWidget(lbl_title_bar)
        title_layout.addStretch()
        
        btn_close_top = SVGCloseButton(title_bar)
        btn_close_top.setStyleSheet("""
            QPushButton {
                border: none;
                border-radius: 10px;
                background-color: transparent;
            }
            QPushButton:hover {
                background-color: #EF4444;
            }
        """)
        btn_close_top.clicked.connect(self.close)
        title_layout.addWidget(btn_close_top)
        
        body_layout.addWidget(title_bar)
        
        # 타이틀바 구분선
        sep_line = QFrame()
        sep_line.setFrameShape(QFrame.HLine)
        sep_line.setStyleSheet("background-color: #d1d5db; max-height: 1px; border: none;")
        body_layout.addWidget(sep_line)
        
        # 2. 메인 컨텐츠 영역
        content_widget = QWidget()
        content_layout = QVBoxLayout(content_widget)
        content_layout.setContentsMargins(30, 25, 30, 20)
        content_layout.setSpacing(10)
        
        # 상단 영역: 왼쪽 큰 아이콘 + 오른쪽 텍스트 블록
        header_row = QHBoxLayout()
        header_row.setSpacing(25)
        header_row.setContentsMargins(10, 0, 10, 0)
        
        # 1. 왼쪽 큰 아이콘
        lbl_logo = QLabel()
        lbl_logo.setFixedSize(110, 110)
        lbl_logo.setScaledContents(True)
        logo_path = os.path.join(config.ASSETS_DIR, "../app_icon/webtoo_scripter_yellow.png")
        if os.path.exists(logo_path):
            lbl_logo.setPixmap(QPixmap(logo_path))
        else:
            lbl_logo.setPixmap(get_icon(config.ICON_MOVIE).pixmap(110, 110))
            
        header_row.addWidget(lbl_logo, 0, Qt.AlignVCenter)
        
        # 2. 오른쪽 텍스트 영역
        text_block = QVBoxLayout()
        text_block.setSpacing(6)
        text_block.setAlignment(Qt.AlignVCenter)
        
        lbl_app_name = QLabel("Webtoon Scripter")
        lbl_app_name.setStyleSheet("color: #1e3a8a; font-size: 24px; font-weight: bold; font-family: 'Helvetica Neue', Arial; border: none; background: transparent; padding: 0; margin: 0;")
        text_block.addWidget(lbl_app_name)
        
        lbl_subtitle = QLabel("웹툰 대사 추출 및 편집 툴")
        lbl_subtitle.setStyleSheet("color: #4f46e5; font-size: 13px; font-weight: bold; border: none; background: transparent;")
        text_block.addWidget(lbl_subtitle)
        
        lbl_version = QLabel(f"Version {config.APP_VERSION}")
        lbl_version.setStyleSheet("color: #4b5563; font-size: 13px; border: none; background: transparent;")
        text_block.addWidget(lbl_version)
        
        py_version = platform.python_version()
        lbl_sub_version = QLabel(f"Python {py_version}")
        lbl_sub_version.setStyleSheet("color: #9ca3af; font-size: 11px; border: none; background: transparent;")
        text_block.addWidget(lbl_sub_version)
        
        lbl_tech = QLabel("Python + PySide6 + Cloud Vision + Gemini")
        lbl_tech.setStyleSheet("color: #6b7280; font-size: 11px; border: none; background: transparent;")
        text_block.addWidget(lbl_tech)
        
        header_row.addLayout(text_block, 1)
        content_layout.addLayout(header_row)
        
        content_layout.addSpacing(10)
        
        # 오픈소스 라이선스 헤더
        lbl_license_title = QLabel("오픈소스 라이선스")
        lbl_license_title.setStyleSheet("font-size: 14px; font-weight: bold; color: #1f2937; border: none; background: transparent;")
        content_layout.addWidget(lbl_license_title)
        
        # 라이선스 리스트 프레임
        license_list_widget = QWidget()
        license_list_layout = QVBoxLayout(license_list_widget)
        license_list_layout.setContentsMargins(0, 0, 0, 0)
        license_list_layout.setSpacing(0)
        
        licenses = [
            ("PySide6", "LGPLv3"),
            ("google-cloud-vision", "Apache-2.0"),
            ("google-generativeai", "Apache-2.0"),
            ("pillow (PIL)", "HPND"),
            ("openpyxl", "MIT"),
            ("opencv-python", "Apache-2.0")
        ]
        
        for i, (name, lic) in enumerate(licenses):
            row = QWidget()
            row.setMinimumHeight(32)
            row_layout = QHBoxLayout(row)
            row_layout.setContentsMargins(5, 8, 5, 8)
            
            lbl_name = QLabel(name)
            lbl_name.setStyleSheet("font-family: 'Helvetica Neue', Arial; font-size: 13px; color: #374151; background: transparent; border: none; padding: 0px; margin: 0px;")
            lbl_name.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            
            lbl_lic = QLabel(lic)
            lbl_lic.setStyleSheet("font-family: 'Helvetica Neue', Arial; font-size: 13px; color: #9ca3af; background: transparent; border: none; padding: 0px; margin: 0px;")
            lbl_lic.setAlignment(Qt.AlignVCenter | Qt.AlignRight)
            
            row_layout.addWidget(lbl_name)
            row_layout.addStretch()
            row_layout.addWidget(lbl_lic)
            
            license_list_layout.addWidget(row)
            
            # 구분선 (마지막 항목 제외)
            if i < len(licenses) - 1:
                row_line = QFrame()
                row_line.setFrameShape(QFrame.HLine)
                row_line.setStyleSheet("background-color: #f1f5f9; max-height: 1px; border: none;")
                license_list_layout.addWidget(row_line)
                
        content_layout.addWidget(license_list_widget)
        
        content_layout.addStretch()
        
        # 저작권 표기
        lbl_copyright = QLabel("© 2026 PAK JINWOO: Webtoon Scripter")
        lbl_copyright.setAlignment(Qt.AlignCenter)
        lbl_copyright.setStyleSheet("color: #9ca3af; font-size: 12px; border: none; background: transparent; margin-bottom: 10px;")
        content_layout.addWidget(lbl_copyright)
        
        # 하단 버튼 바 (우측 정렬)
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addStretch()
        
        btn_close_bottom = QPushButton("닫기")
        btn_close_bottom.setCursor(Qt.PointingHandCursor)
        btn_close_bottom.setStyleSheet("""
            QPushButton {
                background-color: #5d75d6;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                font-size: 13px;
                min-height: 28px;
                max-height: 28px;
                height: 28px;
                padding-left: 20px;
                padding-right: 20px;
            }
            QPushButton:hover {
                background-color: #4a62c4;
            }
            QPushButton:pressed {
                background-color: #3b50a6;
            }
        """)
        btn_close_bottom.clicked.connect(self.close)
        bottom_layout.addWidget(btn_close_bottom)
        
        content_layout.addLayout(bottom_layout)
        
        body_layout.addWidget(content_widget)
        main_layout.addWidget(self.body)

    def mousePressEvent(self, event):
        # 팝업 드래그 이동 지원
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self.drag_position)
            event.accept()


class TextCleanDialog(SpellCheckDialog):
    def __init__(self, original, cleaned, parent=None, initial_vscroll=0):
        super().__init__(original, cleaned, parent, initial_vscroll)
        self.setWindowTitle("텍스트 정리 결과 비교")
        self.resize(600, 700)
        
        # 왼쪽 교정 전 텍스트 창 숨김 (오른쪽 단일 창으로 넓게 시각화)
        self.edit_org.hide()
        
        # 안내 문구 및 적용 버튼 텍스트/스타일을 텍스트 정리에 어울리게 치환
        for label in self.findChildren(QLabel):
            if "수정된 부분" in label.text():
                label.setText("💡 정리(삭제/교정)된 단어에 마우스 커서를 두면 떠오르는 '원래대로' 버튼을 클릭하여 개별 복구할 수 있습니다.")
                label.setStyleSheet("color: #4F46E5; margin-bottom: 10px; font-weight: bold; font-family: 'Pretendard';")
                
        for btn in self.findChildren(QPushButton):
            if btn.text() == "교정 내용 적용":
                btn.setText("정리 내용 적용")
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4F46E5;
                        color: white;
                        font-weight: bold;
                        border-radius: 4px;
                    }
                    QPushButton:hover {
                        background-color: #4338CA;
                    }
                """)

    def apply_changes(self):
        """텍스트 정리 전용: 부모의 apply_changes 결과에서 연속 빈 줄을 제거합니다."""
        super().apply_changes()
        if self.result_text is not None:
            import re as _re
            # 2개 이상 연속 줄바꿈(= 빈 줄 1개 이상)을 줄바꿈 하나로 압축
            # 삭제된 블록이 있던 자리에 남는 빈 줄을 자동으로 붙여줍니다.
            self.result_text = _re.sub(r'\n{2,}', '\n', self.result_text)
            # 텍스트 앞뒤 공백 제거
            self.result_text = self.result_text.strip()


# =================================================================
# 프리미엄 디자인 커스텀 입력 다이얼로그 (QInputDialog 대체용)
# =================================================================
class CustomInputDialog(QDialog):
    def __init__(self, title, label_text, placeholder_text="", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(360, 180)
        self.validator = None
        
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)
        
        self.lbl_text = QLabel(label_text)
        self.lbl_text.setStyleSheet("font-size: 14px; font-weight: 600; color: #1F2937; font-family: 'Pretendard';")
        layout.addWidget(self.lbl_text)
        
        self.input_field = SingleClickLineEdit()
        self.input_field.setPlaceholderText(placeholder_text)
        self.input_field.setFixedHeight(38)
        self.input_field.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding-left: 10px;
                font-size: 13px;
                color: #374151;
                background-color: #F9FAFB;
                font-family: 'Pretendard';
            }
            QLineEdit:focus {
                border: 2px solid #FF5722;
                background-color: white;
            }
        """)
        layout.addWidget(self.input_field)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        self.btn_cancel = QPushButton("취소")
        self.btn_cancel.setFixedHeight(38)
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #F3F4F6;
                color: #4B5563;
                font-weight: bold;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                font-family: 'Pretendard';
            }
            QPushButton:hover {
                background-color: #E5E7EB;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)
        
        self.btn_ok = QPushButton("확인")
        self.btn_ok.setFixedHeight(38)
        self.btn_ok.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                font-family: 'Pretendard';
            }
            QPushButton:hover {
                background-color: #F4511E;
            }
        """)
        self.btn_ok.clicked.connect(self.on_accept)
        
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)
        
        # 엔터 키는 keyPressEvent에서 직접 처리합니다.
        
    def get_text(self):
        return self.input_field.text().strip()

    def on_accept(self):
        text = self.get_text()
        if not text:
            from PySide6.QtCore import QTimer
            QTimer.singleShot(0, lambda: (
                CustomMessageBox.warning(self, "경고", "이름을 입력해주세요."),
                self.input_field.setFocus()
            ))
            return
        if self.validator:
            is_valid, err_msg = self.validator(text)
            if not is_valid:
                from PySide6.QtCore import QTimer
                QTimer.singleShot(0, lambda: (
                    CustomMessageBox.warning(self, "중복 경고", err_msg),
                    self.input_field.setFocus()
                ))
                return
        self.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            self.on_accept()
            event.accept()
        else:
            super().keyPressEvent(event)

    @classmethod
    def get_input(cls, parent, title, label_text, placeholder_text="", validator=None):
        dlg = cls(title, label_text, placeholder_text, parent)
        dlg.validator = validator
        # 활성화 시 포커스를 텍스트 필드로 자동 설정
        dlg.input_field.setFocus()
        if dlg.exec() == QDialog.Accepted:
            return dlg.get_text(), True
        return "", False


# =================================================================
# ⌨️ 단축키 도움말 다이얼로그 (ShortcutHelpDialog)
# =================================================================
class ShortcutHelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("단축키 도움말")
        self.setModal(True)
        self.resize(460, 520)
        self.setWindowFlags(Qt.Dialog | Qt.WindowCloseButtonHint)
        self.setStyleSheet("QDialog { background-color: #FFFFFF; }")
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Title / Description Layout with SVG Icon
        title_layout = QHBoxLayout()
        title_layout.setSpacing(8)
        title_layout.setContentsMargins(0, 0, 0, 0)
        
        lbl_title_icon = QLabel()
        lbl_title_icon.setFixedSize(20, 20)
        lbl_title_icon.setPixmap(get_colored_pixmap(config.ICON_KEYBOARD, "#4F46E5", 20, 20))
        title_layout.addWidget(lbl_title_icon)
        
        title_lbl = QLabel("단축키 도움말")
        title_lbl.setStyleSheet("font-size: 18px; font-weight: bold; color: #111827; font-family: 'Pretendard';")
        title_layout.addWidget(title_lbl)
        title_layout.addStretch()
        
        layout.addLayout(title_layout)

        desc_lbl = QLabel("Webtoon Scripter에서 제공하는 단축키 목록입니다.\n단축키를 활용하여 작업 시간을 획기적으로 줄여보세요.")
        desc_lbl.setStyleSheet("font-size: 13px; color: #6B7280; font-family: 'Pretendard';")
        layout.addWidget(desc_lbl)

        # Scroll Area for shortcuts list
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: #FAFAFA;
            }
        """)

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(16, 16, 16, 16)
        container_layout.setSpacing(20)
        container_layout.setAlignment(Qt.AlignTop)

        # OS 판단에 따른 단축키 이름 매핑 함수
        is_mac = sys.platform == "darwin"
        ctrl_key = "⌘" if is_mac else "Ctrl"
        alt_key = "⌥" if is_mac else "Alt"
        shift_key = "⇧" if is_mac else "Shift"

        # Shortcut Groups with SVG Icons and Colors
        groups = [
            ("화면 및 도구 토글", config.ICON_MENU, "#3B82F6", [
                (f"{ctrl_key} + B", "사이드바 열기 / 닫기"),
                (f"{ctrl_key} + J", "관용구 도우미 창 토글"),
                (f"{ctrl_key} + K", "캐릭터 도우미 창 토글"),
                (f"{ctrl_key} + N", "새 작업 (심플 모드)"),
            ]),
            ("대본 표(테이블) 편집", config.ICON_EXCEL, "#10B981", [
                (f"{ctrl_key} + Z", "실행 취소 (Undo)"),
                (f"{ctrl_key} + {shift_key} + Z", "다시 실행 (Redo)"),
                (f"{ctrl_key} + C", "선택한 셀 내용 복사"),
                (f"{ctrl_key} + V", "선택한 셀 내용 붙여넣기"),
                ("Delete / Backspace", "선택 내용 지우기"),
                ("Enter / Return", "텍스트 확정 후 아래쪽 셀로 이동"),
                (f"{shift_key} + Enter", "현재 커서 위치에서 행 분리 (셀 나누기)"),
                (f"{ctrl_key} + M", "선택한 2개 이상의 셀(행) 합치기 (셀 병합)"),
            ]),
            ("웹툰 뷰어 스크롤 및 이동", config.ICON_MOVE_VERTICAL, "#6B7280", [
                (f"Home, {ctrl_key} + ↑", "스크롤 최상단으로 이동"),
                (f"End, {ctrl_key} + ↓", "스크롤 최하단으로 이동"),
            ]),
            ("관용구 자동 입력", config.ICON_LIBRARY, "#F59E0B", [
                (f"{alt_key} + [숫자]", "지정된 관용구 삽입"),
            ])
        ]

        for group_title, icon_path, icon_color, items in groups:
            group_box = QFrame()
            group_box.setStyleSheet("QFrame { background-color: transparent; border: none; }")
            group_layout = QVBoxLayout(group_box)
            group_layout.setContentsMargins(0, 0, 0, 0)
            group_layout.setSpacing(8)

            header_layout = QHBoxLayout()
            header_layout.setContentsMargins(0, 0, 0, 0)
            header_layout.setSpacing(6)

            lbl_grp_icon = QLabel()
            lbl_grp_icon.setFixedSize(14, 14)
            lbl_grp_icon.setPixmap(get_colored_pixmap(icon_path, icon_color, 14, 14))
            header_layout.addWidget(lbl_grp_icon)

            lbl_group_title = QLabel(group_title)
            lbl_group_title.setStyleSheet("font-size: 13px; font-weight: bold; color: #4B5563; font-family: 'Pretendard';")
            header_layout.addWidget(lbl_group_title)
            header_layout.addStretch()

            header_widget = QWidget()
            header_widget.setStyleSheet("QWidget { border-bottom: 1px solid #E5E7EB; background: transparent; }")
            header_w_layout = QVBoxLayout(header_widget)
            header_w_layout.setContentsMargins(0, 0, 0, 4)
            header_w_layout.addLayout(header_layout)

            group_layout.addWidget(header_widget)

            grid = QGridLayout()
            grid.setSpacing(8)
            grid.setColumnStretch(0, 1) # 설명이 왼쪽에 와서 더 넓은 공간 할당
            grid.setColumnStretch(1, 0) # 단축키 배지는 오른쪽에 붙음

            for row_idx, (keys, action_desc) in enumerate(items):
                lbl_desc = QLabel(action_desc)
                lbl_desc.setStyleSheet("font-size: 13px; color: #374151; font-family: 'Pretendard';")
                grid.addWidget(lbl_desc, row_idx, 0, Qt.AlignLeft | Qt.AlignVCenter)

                # 단축키 키 조합을 위한 배지 레이아웃
                badge_widget = QWidget()
                badge_widget.setStyleSheet("background: transparent; border: none;")
                badge_layout = QHBoxLayout(badge_widget)
                badge_layout.setContentsMargins(0, 0, 0, 0)
                badge_layout.setSpacing(4)

                key_groups = keys.split(", ")
                for g_idx, key_group in enumerate(key_groups):
                    parts = key_group.split(" + ")
                    for p_idx, part in enumerate(parts):
                        part_lbl = QLabel(part)
                        part_lbl.setStyleSheet("""
                            QLabel {
                                background-color: #F3F4F6;
                                color: #374151;
                                border: 1px solid #E5E7EB;
                                border-radius: 4px;
                                padding: 3px 6px;
                                font-size: 11px;
                                font-weight: bold;
                                font-family: 'Pretendard', sans-serif;
                            }
                        """)
                        badge_layout.addWidget(part_lbl)
                        if p_idx < len(parts) - 1:
                            plus_lbl = QLabel("+")
                            plus_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: bold;")
                            badge_layout.addWidget(plus_lbl)
                    
                    if g_idx < len(key_groups) - 1:
                        or_lbl = QLabel("/")
                        or_lbl.setStyleSheet("color: #9CA3AF; font-size: 11px; font-weight: bold; margin-left: 4px; margin-right: 4px;")
                        badge_layout.addWidget(or_lbl)

                grid.addWidget(badge_widget, row_idx, 1, Qt.AlignRight | Qt.AlignVCenter)

            group_layout.addLayout(grid)
            container_layout.addWidget(group_box)

        scroll_area.setWidget(container)
        layout.addWidget(scroll_area)

        # Close button at the bottom
        btn_close = QPushButton("닫기")
        btn_close.setFixedHeight(38)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #1F2937;
                color: white;
                font-weight: bold;
                border: none;
                border-radius: 6px;
                font-family: 'Pretendard';
            }
            QPushButton:hover {
                background-color: #111827;
            }
        """)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.accept()
            event.accept()
        else:
            super().keyPressEvent(event)

class OnboardingMigrationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("이전 버전 데이터 가져오기")
        self.setFixedSize(450, 330)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        self.setFont(QApplication.font())
        self.setStyleSheet("QDialog { background-color: white; }")
        
        self.init_ui()

    def init_ui(self):
        app_ff = QApplication.font().family() or 'Pretendard'
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 24, 20, 24)
        layout.setSpacing(18)

        # Header section
        lbl_title = QLabel("Webtoon Scripter v3.0 시작")
        lbl_title.setStyleSheet(f"font-size: 18px; font-weight: bold; color: #111827; font-family: '{app_ff}';")
        layout.addWidget(lbl_title)

        # Card container (styled like settings pages cards)
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #F9FAFB; border: 1px solid #E5E7EB; border-radius: 10px; }")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 16, 18, 16)
        card_layout.setSpacing(12)

        lbl_mig_title = QLabel("이전 버전 데이터 마이그레이션")
        lbl_mig_title.setStyleSheet(f"font-weight: bold; color: #FF5722; font-size: 14px; border: none; background: transparent; font-family: '{app_ff}';")
        card_layout.addWidget(lbl_mig_title)

        lbl_mig_desc = QLabel("이전 실행파일 버전(.exe)에 생성된 프로젝트 폴더\n(작품 및 회차 데이터가 모여있는 폴더) 데이터를\n현재 프로그램으로 안전하게 가져오시겠습니까?")
        lbl_mig_desc.setStyleSheet(f"color: #4B5563; font-size: 13px; border: none; background: transparent; font-family: '{app_ff}'; line-height: 140%;")
        card_layout.addWidget(lbl_mig_desc)

        lbl_tip = QLabel("💡 나중에도 [설정 -> 저장소 설정] 메뉴에서 언제든 실행할 수 있습니다.")
        lbl_tip.setStyleSheet(f"color: #4B5563; font-size: 12px; font-weight: 500; border: none; background: transparent; font-family: '{app_ff}';")
        card_layout.addWidget(lbl_tip)

        layout.addWidget(card)

        # Action Buttons Layout (styled like PreferencesDialog bottom buttons)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        
        btn_no = QPushButton("나중에 하기")
        btn_no.setFixedHeight(40)
        btn_no.setCursor(Qt.PointingHandCursor)
        btn_no.setStyleSheet(f"""
            QPushButton {{ 
                background-color: white; 
                border: 1px solid #D1D5DB; 
                border-radius: 6px; 
                color: #4B5563; 
                font-weight: bold; 
                font-size: 13px;
                font-family: '{app_ff}'; 
            }} 
            QPushButton:hover {{ 
                border-color: #FF5722; 
                color: #FF5722; 
                background-color: #FFF9F7;
            }}
            QPushButton:pressed {{ 
                background-color: #FFEFEA; 
            }}
        """)
        btn_no.clicked.connect(self.reject)

        btn_yes = QPushButton("이전 데이터 가져오기")
        btn_yes.setFixedHeight(40)
        btn_yes.setCursor(Qt.PointingHandCursor)
        btn_yes.setStyleSheet(f"""
            QPushButton {{ 
                background-color: #FF5722; 
                color: white; 
                border: none; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 13px;
                font-family: '{app_ff}'; 
            }} 
            QPushButton:hover {{ 
                background-color: #E64A19; 
            }}
            QPushButton:pressed {{ 
                background-color: #D84315; 
            }}
        """)
        btn_yes.clicked.connect(self.accept)

        btn_layout.addWidget(btn_yes, 1)
        btn_layout.addWidget(btn_no, 1)
        layout.addLayout(btn_layout)




