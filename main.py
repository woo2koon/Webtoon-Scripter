# main.py
import pandas as pd
import sys
import os
import re
import shutil
import subprocess
import platform
import unicodedata
from utils import get_icon
from copy import copy
from openpyxl import load_workbook
from openpyxl.worksheet.datavalidation import DataValidation
from ai_worker import SpellCheckWorker
from widgets import SpellCheckDialog
from widgets import ProjectManagementDialog, HoverIconButton

from PySide6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                               QHBoxLayout, QLabel, QPushButton, QComboBox, 
                               QLineEdit, QTextEdit, QTabWidget, QSplitter, 
                               QTableWidget, QTableWidgetItem, QHeaderView, 
                               QFileDialog, QMessageBox, QProgressBar, QFrame, 
                               QMenu, QListWidgetItem, QListWidget, QListView, 
                               QScrollArea, QCheckBox, QGridLayout, QStackedWidget,
                               QDialog, QFormLayout, QInputDialog, QGraphicsOpacityEffect,
                               QRadioButton, QWidgetAction, QToolButton, QToolTip, QSizePolicy)
from PySide6.QtCore import (Qt, QTimer, QSize, QPropertyAnimation, QEasingCurve, 
                            QAbstractAnimation, QEvent, QPoint, QMimeData)
from PySide6.QtGui import (QCursor, QFontDatabase, QFont, QTextCursor, QAction, 
                           QDragEnterEvent, QDropEvent, QIcon, QShortcut, QKeySequence,
                           QPainter, QPixmap, QColor, QPen, QPalette)
import config

from config import BASE_DIR, ASSETS_DIR, CACHE_DIR, PROJECTS_DIR, TEMPLATE_PATH, MODERN_STYLE
from utils import restore_template, natural_sort_key
from widgets import ResponsiveLabel, ClickableComboBox, WebtoonScrollArea, PopupItemDelegate, CharacterRow, SpreadsheetTable, ExcelTextDelegate, CharacterListContainer
from ocr_worker import OCRWorker

# 디렉토리 생성
if not os.path.exists(BASE_DIR): os.makedirs(BASE_DIR)
if not os.path.exists(ASSETS_DIR): os.makedirs(ASSETS_DIR)
if not os.path.exists(CACHE_DIR): os.makedirs(CACHE_DIR)

restore_template()




from widgets import FileDropListWidget, DropOverlay, SmartTextEdit, ToastMessage, SettingsDialog, IdiomSettingsDialog

# 메인 윈도우
# =======================================================
class WebtoonManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Webtoon Script Manager v{config.APP_VERSION}") 
        self.resize(1600, 950)
        self.current_title = ""
        self.current_episode = ""
        self.is_simple_mode = False
        self.api_call_count = 0 
        self.zoom_step = 0
        self.overlay = DropOverlay(self)
        
        self.init_ui()
        self.refresh_project_list()
        self.idiom_shortcuts = []
        self.setup_idiom_shortcuts()

        self.sidebar_anim = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self.sidebar_anim.setDuration(300)
        self.sidebar_anim.setEasingCurve(QEasingCurve.InOutSine)

        self.sidebar_anim.valueChanged.connect(self.update_button_pos)

        self.shortcut_sidebar = QShortcut(QKeySequence("Ctrl+B"), self)
        self.shortcut_sidebar.activated.connect(self.toggle_sidebar)

        self.update_button_pos()
        
        # [추가] 모든 UI가 생성된 후 API 호출수 로드
        self.load_api_count()
        
        # 앱 실행 시 기존 작업 내역 확인 및 모드 복원
        # 2단계: 모드 체크 및 기존 작업 확인 (지연 호출)
        QTimer.singleShot(0, lambda: self.check_existing_work(is_startup=True))

    def update_button_pos(self):
        """사이드바의 현재 너비에 맞춰 버튼 위치를 실시간으로 이동시킵니다."""
        if hasattr(self, 'btn_toggle') and hasattr(self, 'sidebar'):
            # 사이드바의 현재 너비를 가져옵니다.
            current_sidebar_width = self.sidebar.width()
            margin_right = 10 

            # [수정] OS별 상단 마진 대응
            if platform.system() == "Windows":
                # 윈도우는 메뉴바 높이(약 30px)를 고려하여 45px 정도로 설정합니다.
                # '설정' 메뉴바 아래로 버튼을 안전하게 대피시킵니다.
                margin_top = 45 
            else:
                # 맥은 기존처럼 상단에 바짝 붙여줍니다.
                margin_top = 15
            
            # 버튼의 X 좌표 = 사이드바 너비 - 버튼 너비 - 마진
            new_x = current_sidebar_width - self.btn_toggle.width() - margin_right
            
            # 버튼 이동
            self.btn_toggle.move(new_x, margin_top)
            self.btn_toggle.raise_()

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # [수정] 오버레이 크기와 위치를 강제로 다시 잡고 표시
            self.overlay.setGeometry(self.rect())
            self.overlay.show()
            self.overlay.raise_()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            if not self.overlay.isVisible():
                self.overlay.show()
                self.overlay.raise_()
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        # [수정] 메인 윈도우의 leave 이벤트는 무시합니다. (오버레이가 직접 관리)
        self.file_list_widget.set_highlight(False)

    def dropEvent(self, event):
        # [수정] 오버레이 숨기고 파일 직접 처리
        if hasattr(self, 'overlay'):
            self.overlay.hide()
        
        self.file_list_widget.set_highlight(False)
        
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            files = [u.toLocalFile() for u in urls]
            self.process_image_files(files)
        else:
            event.ignore()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'overlay'):
            self.overlay.setGeometry(self.rect()) 
            self.overlay.raise_()

    def clear_simple_mode_cache(self):
        simple_dir = os.path.join(CACHE_DIR, "simple_mode")
        if os.path.exists(simple_dir):
            for f in os.listdir(simple_dir):
                file_path = os.path.join(simple_dir, f)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    print(f"Failed to delete {f}: {e}")

    def check_existing_work(self, is_startup=False):
        # 1. 앱 시작 시: 전체 모드(프로젝트 모드)라면 심플 모드 체크를 하지 않습니다.
        if is_startup and not getattr(config, 'IS_SIMPLE_MODE', False):
            return
            
        # 2. 심플 모드로 시작할 때: UI를 먼저 전환합니다.
        if is_startup and getattr(config, 'IS_SIMPLE_MODE', False):
            self.toggle_simple_mode(show_toast=False, check_work=False)

        simple_dir = os.path.join(CACHE_DIR, "simple_mode")
        has_work = False
        
        if os.path.exists(simple_dir):
            files = os.listdir(simple_dir)
            if any(f.endswith(('.png', '.jpg', '.jpeg')) for f in files) or os.path.exists(os.path.join(simple_dir, "script.txt")):
                has_work = True
        
        if has_work:
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('기존 작업 불러오기')
            msg_box.setText('심플 모드에 기존 작업 내용이 있습니다.\n이어서 작업하시겠습니까?\n(아니오를 누르면 기존 내용을 삭제하고 새로 시작합니다.)')
            
            btn_yes = msg_box.addButton(" 예 ", QMessageBox.ActionRole)
            btn_no = msg_box.addButton(" 아니오 ", QMessageBox.ActionRole)
            
            msg_box.setDefaultButton(btn_yes)
            msg_box.exec()

            if msg_box.clickedButton() == btn_no:
                self.clear_simple_mode_cache()
                self.clear_workspace()
                self.load_images()
                self.load_data()
            # '예'를 누른 경우는 이미 toggle_simple_mode 등에서 로드가 완료되었으므로 추가 로드가 필요 없습니다.
            
    def prompt_clear_workspace(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('새 작업 시작')
        msg_box.setText('이미지와 텍스트를 모두 지우고 새 작업을 시작하시겠습니까?')
        
        btn_yes = msg_box.addButton(" 예 ", QMessageBox.ActionRole)
        btn_no = msg_box.addButton(" 아니오 ", QMessageBox.ActionRole)
        
        msg_box.setDefaultButton(btn_no) # 실수 방지를 위해 '아니오'를 기본값으로
        msg_box.exec()

        if msg_box.clickedButton() == btn_yes:
            self.analysis_menu.hide()
            if getattr(self, 'is_simple_mode', False):
                self.clear_simple_mode_cache()
            self.clear_workspace()
            self.load_images()
            self.load_data()
            self.toast.show_message("🗑️ 기존 작업이 지워지고 새 작업이 시작되었습니다.")

    def eventFilter(self, source, event):
        # [안전장치 추가] 햄버거 버튼 툴팁 로직
        if hasattr(self, 'btn_toggle') and source == self.btn_toggle:
            if event.type() == QEvent.Enter:
                tooltip_text = self.btn_toggle.toolTip()
                if tooltip_text:
                    QToolTip.showText(QCursor.pos(), tooltip_text, self.btn_toggle)
                return True

        # [안전장치 추가] 텍스트 에디터 관련 로직
        if hasattr(self, 'text_editor') and self.text_editor is not None:
            if source in [self.text_editor, self.text_editor.viewport()]:
                # ... 기존 로직 ...
                pass

        return super().eventFilter(source, event)
    
    def open_management_system(self):
        # 1. 현재 선택된 텍스트를 가져옵니다. (없으면 빈 문자열)
        current_title = self.combo_project.currentText()
        current_episode = self.combo_episode.currentText()

        dialog = ProjectManagementDialog(self)
        dialog.exec()

        self.combo_project.blockSignals(True)
        self.combo_episode.blockSignals(True)

        # 2. 목록을 싹 비우고 새로 가져옵니다.
        self.combo_project.clear()
        project_list = self.get_project_list()
        self.combo_project.addItems(project_list)

        # 3. [핵심] 원래 아무것도 선택되지 않은 상태였다면 (-1)로 강제 초기화
        if not current_title:
            self.combo_project.setCurrentIndex(-1)
            self.combo_episode.clear()
            self.combo_episode.setCurrentIndex(-1)
        else:
            # 이전에 선택한 게 있었다면 그 값으로 복구
            self.combo_project.setCurrentText(current_title)
            self.combo_episode.clear()
            self.combo_episode.addItems(self.get_episode_list())
            
            if current_episode:
                self.combo_episode.setCurrentText(current_episode)
            else:
                self.combo_episode.setCurrentIndex(-1)

        self.combo_project.blockSignals(False)
        self.combo_episode.blockSignals(False)
    
    # [main.py 에 추가]
    def get_project_list(self):
        """PROJECTS_DIR 폴더 안의 작품 목록을 반환합니다."""
        if not os.path.exists(config.PROJECTS_DIR): return []
        return sorted([d for d in os.listdir(config.PROJECTS_DIR) 
                      if os.path.isdir(os.path.join(config.PROJECTS_DIR, d))])

    def get_episode_list(self):
        """현재 선택된 작품 안의 회차 목록을 반환합니다."""
        title = self.combo_project.currentText()
        if not title: return []
        t_path = os.path.join(config.PROJECTS_DIR, title)
        if not os.path.exists(t_path): return []
        return sorted([d for d in os.listdir(t_path) 
                      if os.path.isdir(os.path.join(t_path, d))])

    def init_ui(self):
        self.create_menu()
        
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.setAcceptDrops(True)

        # -----------------------------------------------------------
        # 1. 통합 사이드바 설정 (최소 50px 유지 구조)
        # -----------------------------------------------------------
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setMinimumWidth(50)   # 접혔을 때의 너비
        self.sidebar.setMaximumWidth(280)  # 펼쳤을 때의 너비
        
        # 사이드바 전체 수직 레이아웃
        self.side_layout = QVBoxLayout(self.sidebar)
        self.side_layout.setAlignment(Qt.AlignTop)
        self.side_layout.setContentsMargins(0, 0, 0, 0) # 외곽 여백 제거
        self.side_layout.setSpacing(0)

        # [수정] 상단 헤더 영역 (아이콘 + 제목 글자)
        self.side_header = QWidget()
        self.side_header.setFixedHeight(80)
        header_layout = QHBoxLayout(self.side_header)
        header_layout.setContentsMargins(20, 18, 15, 0) 
        
        # 1. 제목 컨테이너 생성 (아이콘과 글자를 하나로 묶음)
        self.title_container = QWidget()
        title_inner_layout = QHBoxLayout(self.title_container)
        title_inner_layout.setContentsMargins(0, 0, 0, 0)
        title_inner_layout.setSpacing(8) # 아이콘과 글자 사이의 간격

        # 2. 아이콘 라벨 (SVG 아이콘 적용)
        self.icon_label = QLabel()
        # config.ICON_MOVIE에 정의된 슬레이트 아이콘을 가져옵니다.
        self.icon_label.setPixmap(get_icon(config.ICON_MOVIE).pixmap(22, 22))

        # 3. 글자 라벨 (기존 스타일 유지)
        self.lbl_side_title = QLabel("작품/회차 선택")
        self.lbl_side_title.setStyleSheet("font-weight: bold; font-size: 15px; color: #374151;")

        # 컨테이너 내부에 아이콘과 글자 순서대로 추가
        title_inner_layout.addWidget(self.icon_label)
        title_inner_layout.addWidget(self.lbl_side_title)
        
        # 4. 헤더 레이아웃에 완성된 컨테이너 추가
        header_layout.addWidget(self.title_container)
        header_layout.addStretch() # 오른쪽 공간 밀어내기 (버튼 자리를 비워줌)
        
        self.side_layout.addWidget(self.side_header)

        # [수정] config에 정의된 ICON_MENU 사용하기
        self.btn_toggle = QPushButton("", self) # 텍스트는 지우고 아이콘만 넣습니다.
        
        # get_icon 함수를 사용하여 아이콘 설정
        self.btn_toggle.setIcon(get_icon(config.ICON_MENU))
        self.btn_toggle.setIconSize(QSize(20, 20)) # 햄버거 메뉴에 적당한 크기
        
        self.btn_toggle.setFixedSize(32, 32)
        self.btn_toggle.setCursor(Qt.PointingHandCursor)

        self.btn_toggle.setToolTip("사이드바 닫기")
        self.btn_toggle.installEventFilter(self)
        
        # [스타일] 테두리를 없애서 더 현대적인 느낌을 줍니다.
        self.btn_toggle.setStyleSheet("""
            QPushButton { 
                background: transparent; 
                border: none; 
                border-radius: 6px; 
                padding: 0px;           
                text-align: center;
            }
            QPushButton:hover { 
                background-color: #F3F4F6; 
            }
            QToolTip { 
                background-color: white; 
                color: black; 
                border: 1px solid #D1D5DB; 
                padding: 3px 8px; 
                border-radius: 4px;
                font-family: 'Pretendard'; 
                font-size: 12px;
            }
        """)
        self.btn_toggle.clicked.connect(self.toggle_sidebar)

        self.setStyleSheet(self.styleSheet() + """
            QToolTip { 
                background-color: #374151; 
                color: white; 
                border: 1px solid #1F2937;
                padding: 3px 8px;
                border-radius: 4px;
                border-radius: 4px;
                font-size: 12px;
            }
        """)
        
        # 버튼을 일단 맨 위로 올립니다.
        self.btn_toggle.raise_()
        
        # 초기 위치 설정 (x: 240, y: 25 정도)
        self.btn_toggle.move(240, 10)
        
        # 사이드바 전체 레이아웃에 헤더 추가
        self.side_layout.addWidget(self.side_header)

        # [B] 사이드바 본문 (접힐 때 이 안의 내용이 통째로 hide 됩니다)
        self.sidebar_body = QWidget()
        # 실제 내용물이 들어갈 레이아웃 (기존 side_layout 역할을 함)
        body_layout = QVBoxLayout(self.sidebar_body)
        body_layout.setContentsMargins(20, 0, 20, 20)
        body_layout.setSpacing(12)

        # --- [기존 사이드바 요소들을 body_layout에 추가] ---
        
        lbl_p = QLabel("작품 선택")
        lbl_p.setObjectName("LabelBold")
        body_layout.addWidget(lbl_p)
        
        self.combo_project = ClickableComboBox()
        self.combo_project.setView(QListView()) 
        self.combo_project.setItemDelegate(PopupItemDelegate())
        self.combo_project.currentTextChanged.connect(self.on_project_change)
        self.combo_project.set_refresh_callback(self.get_project_list)
        body_layout.addWidget(self.combo_project)
        
        row_proj = QHBoxLayout()
        row_proj.setSpacing(6)
        self.input_new_project = QLineEdit()
        self.input_new_project.setPlaceholderText("새 작품명")
        self.input_new_project.setFixedHeight(38)
        self.input_new_project.setStyleSheet("border: 1px solid #D1D5DB; border-radius: 4px; padding-left: 10px;")
        
        btn_add_proj = QPushButton() 
        btn_add_proj.setFixedSize(38, 38)
        plus_icon_path = os.path.join(ASSETS_DIR, "plus.svg")
        if os.path.exists(plus_icon_path): btn_add_proj.setIcon(QIcon(plus_icon_path))
        btn_add_proj.setIconSize(QSize(22, 22))
        btn_add_proj.setStyleSheet("background-color: #FF5722; border-radius: 3px;")
        btn_add_proj.clicked.connect(self.create_project)
        
        row_proj.addWidget(self.input_new_project)
        row_proj.addWidget(btn_add_proj)
        body_layout.addLayout(row_proj)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #e5e7eb; margin: 10px 0;")
        body_layout.addWidget(line)
        
        lbl_e = QLabel("회차 선택")
        lbl_e.setObjectName("LabelBold")
        body_layout.addWidget(lbl_e)
        
        self.combo_episode = ClickableComboBox()
        self.combo_episode.setView(QListView())
        self.combo_episode.setItemDelegate(PopupItemDelegate())
        self.combo_episode.currentTextChanged.connect(self.on_episode_change)
        self.combo_episode.set_refresh_callback(self.get_episode_list)
        body_layout.addWidget(self.combo_episode)
        
        row_ep = QHBoxLayout()
        row_ep.setSpacing(6)
        self.input_new_episode = QLineEdit()
        self.input_new_episode.setPlaceholderText("새 회차명")
        self.input_new_episode.setFixedHeight(38)
        self.input_new_episode.setStyleSheet("border: 1px solid #D1D5DB; border-radius: 4px; padding-left: 10px;")

        btn_add_ep = QPushButton()
        btn_add_ep.setFixedSize(38, 38)
        if os.path.exists(plus_icon_path): btn_add_ep.setIcon(QIcon(plus_icon_path))
        btn_add_ep.setIconSize(QSize(22, 22))
        btn_add_ep.setStyleSheet("background-color: #FF5722; border-radius: 3px;")
        btn_add_ep.clicked.connect(self.create_episode)
        
        row_ep.addWidget(self.input_new_episode)
        row_ep.addWidget(btn_add_ep)
        body_layout.addLayout(row_ep)
        
        body_layout.addSpacing(15)
        
        # 1. 파일 목록 제목 및 아이콘 (기존 유지)
        files_title_container = QWidget()
        files_title_layout = QHBoxLayout(files_title_container)
        files_title_layout.setContentsMargins(0, 0, 0, 0)
        files_title_layout.setSpacing(4)

        icon_files = QLabel()
        icon_files.setPixmap(get_icon(config.ICON_FOLDER).pixmap(20, 20))
        lbl_files = QLabel("업로드 된 파일")
        lbl_files.setObjectName("LabelBold")

        files_title_layout.addWidget(icon_files)
        files_title_layout.addWidget(lbl_files)
        files_title_layout.addStretch()
        body_layout.addWidget(files_title_container)

        # 2. 파일 목록 리스트 (숫자 3을 지우거나 1로 수정하여 너무 커지지 않게 함)
        self.file_list_widget = FileDropListWidget(self)
        self.file_list_widget.setStyleSheet("""
            QListWidget {
                border: 2px solid #E5E7EB; 
                border-radius: 8px;
                background-color: white;
                outline: 0;
                padding: 5px;
            }
            QListWidget::item {
                padding: 10px;
                border-radius: 1px;
                color: #374151;
            }
            /* 선택되었을 때의 스타일: 배경색을 더 진하게, 테두리 추가 */
            QListWidget::item:selected {
                background-color: #FFEDD5; /* 연한 오렌지(Orange 100) - 기존보다 진함 */
                color: #EA580C;           /* 진한 오렌지 글씨색 */
                border: 1px solid #FB923C; /* 선택된 항목에 얇은 실선 테두리 추가 */
                font-weight: bold;         /* 선택된 항목은 굵게 표시 */
            }

            /* 마우스 올렸을 때(Hover)도 약간 더 진하게 */
            QListWidget::item:hover {
                background-color: #F3F4F6;
            }

            /* --- 가로 스크롤바 심플하게 스타일링 --- */
            QScrollBar:horizontal {
                height: 8px;            /* 스크롤바 두께 (얇게) */
                background: #F1F1F1;
                border-radius: 4px;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:horizontal {
                background: #D1D5DB;    /* 스크롤바 바 컬러 */
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #9CA3AF;
            }
            /* 화살표 버튼 제거 */
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        """)

        # 추가 팁: 포커스 되었을 때의 점선 테두리 아예 안 보이게 설정
        self.file_list_widget.setFocusPolicy(Qt.NoFocus)
        body_layout.addWidget(self.file_list_widget, 1) # 숫자 1은 '적당히 늘어나라'는 뜻입니다.

       # 3. [수정] QPushButton 대신 QToolButton으로 교체하여 스플릿 기능 구현
        self.btn_start = QToolButton()
        self.btn_start.setText("분석 시작")
        self.btn_start.setPopupMode(QToolButton.MenuButtonPopup) # 이 설정이 '좌우 분리'를 만듭니다.
        self.btn_start.setFixedHeight(50)
        self.btn_start.setCursor(Qt.PointingHandCursor)
        # 사이드바 너비에 맞춰 꽉 차게 설정
        self.btn_start.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self.btn_start.setStyleSheet("""
            QToolButton {
                background-color: #FF5722;
                color: white;
                font-size: 16px;
                font-weight: bold;
                border-radius: 4px;
                padding: 5px;
                border: none;
                margin: 5px 0px;
                padding-right: 35px;
            }
            QToolButton:hover { background-color: #F97316; }
            
            /* 화살표가 담기는 오른쪽 영역 */
            QToolButton::menu-button {
                border-left: 1px solid rgba(255, 255, 255, 0.4);
                width: 35px;
                border-top-right-radius: 8px;
                border-bottom-right-radius: 8px;
            }

            /* [수정] 화살표 아이콘 설정 */
            QToolButton::menu-arrow {
                /* image: none; <- 이 줄을 삭제하거나 아래처럼 기본 위치를 잡아줍니다 */
                subcontrol-position: center center;
                subcontrol-origin: padding;
                width: 12px;
                height: 12px;
                /* 흰색 화살표 아이콘 파일이 있다면 여기에 경로를 넣으세요 */
                /* image: url(white_arrow.png); */
            }
        """)

        # 2. 드롭다운 메뉴 및 내부 위젯 구성
        self.analysis_menu = QMenu(self)
        self.analysis_menu.setStyleSheet("""
            QMenu {
                background-color: white;
                border: 1px solid #111827;
                border-radius: 8px;
                padding: 5px;
            }
        """)

        # 메뉴 안에 들어갈 커스텀 컨테이너
        menu_widget = QWidget()
        menu_layout = QVBoxLayout(menu_widget)
        menu_layout.setContentsMargins(10, 10, 10, 10)
        menu_layout.setSpacing(8)

        # 기존 변수명(self.radio_fast 등)을 그대로 써서 분석 로직이 깨지지 않게 합니다.
        self.radio_fast = QRadioButton("빠른모드(고정 절단)")
        self.radio_smart = QRadioButton("스마트 모드(컷 단위)")
        
        line = QFrame() # 구분선
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #E5E7EB; margin: 4px 0;")
        
        self.check_reanalyze = QCheckBox("새로 분석하기")

        # [추가] 마우스를 올렸을 때 나타날 툴팁 설정
        self.check_reanalyze.setToolTip("기존 결과를 무시하고 새로 분석합니다. API가 소모됩니다.")
        
        # 스타일 설정
        option_style = """
            QRadioButton, QCheckBox { font-size: 13px; color: #374151; }
            QToolTip { 
                background-color: white; 
                color: black; 
                border: 1px solid #D1D5DB; 
                padding: 3px 8px; 
                border-radius: 4px;
                font-family: 'Pretendard'; 
                font-size: 12px;
            }
        """
        self.radio_fast.setStyleSheet(option_style)
        self.radio_smart.setStyleSheet(option_style)
        self.check_reanalyze.setStyleSheet(option_style)
        self.radio_fast.setChecked(True)

        menu_layout.addWidget(self.radio_fast)
        menu_layout.addWidget(self.radio_smart)
        menu_layout.addWidget(line)
        menu_layout.addWidget(self.check_reanalyze)

        # 3. 위젯을 메뉴에 심기
        menu_action = QWidgetAction(self.analysis_menu)
        menu_action.setDefaultWidget(menu_widget)
        self.analysis_menu.addAction(menu_action)

        # 4. 버튼과 메뉴 연결 및 레이아웃 추가
        self.btn_start.setMenu(self.analysis_menu)
        self.btn_start.clicked.connect(self.run_ocr)
        body_layout.addWidget(self.btn_start)

        self.analysis_menu.aboutToShow.connect(self.adjust_menu_position)

        # 4. [중요] 구분선을 버튼 바로 아래에 추가
        line_bottom = QFrame()
        line_bottom.setFrameShape(QFrame.HLine)
        line_bottom.setFrameShadow(QFrame.Plain) # 3D 입체감을 없애고 평면으로 설정
        line_bottom.setFixedHeight(1)            # 높이를 딱 1픽셀로 고정
        
        # color 대신 background-color를 쓰는 것이 훨씬 확실합니다.
        line_bottom.setStyleSheet("""
            background-color: #E5E7EB; 
            margin: 15px 0; /* 위아래 여백을 15px로 줘서 숨통을 틔워줍니다 */
        """)
        body_layout.addWidget(line_bottom)

        # 5. [핵심] 여기서 스트레치를 넣어서 위 요소들을 모두 위로 밀어올립니다!
        body_layout.addStretch()

        # 6. API 호출 수 (타이틀 크기 업 + 왼쪽 정렬 최적화)
        lbl_api_title = QLabel("이번 작업 API 호출 수")
        lbl_api_title.setStyleSheet("""
            color: #6B7280; 
            font-size: 14px;      /* 12px에서 14px로 살짝 키웠습니다 */
            font-weight: 500;
            margin-left: 0px;
            padding-left: 0px;
        """)
        # 레이아웃 안에서 확실히 왼쪽으로 붙도록 설정
        lbl_api_title.setAlignment(Qt.AlignLeft) 
        body_layout.addWidget(lbl_api_title)

        self.lbl_api_count = QLabel("0회")
        self.lbl_api_count.setStyleSheet("""
            color: #111827; 
            font-size: 38px;      
            font-weight: 900; 
            padding-bottom: 5px;
            margin-left: -9px;    /* [핵심] 시각적으로 왼쪽 벽에 딱 붙게 음수 마진 적용 */
            padding-left: 0px;
        """)
        self.lbl_api_count.setAlignment(Qt.AlignLeft)
        body_layout.addWidget(self.lbl_api_count)

        # 7. [마무리] 완성된 body가 담긴 sidebar_body를 side_layout에 추가
        # 여기서 추가적인 addStretch()는 필요 없습니다. 이미 body_layout 안에서 해결했으니까요!
        self.side_layout.addWidget(self.sidebar_body)

        # 최종 메인 레이아웃 추가
        main_layout.addWidget(self.sidebar)


        # -----------------------------------------------------------
        # 2. 작업 공간 (Workspace)
        # -----------------------------------------------------------
        workspace = QWidget()
        work_layout = QVBoxLayout(workspace)
        work_layout.setContentsMargins(25, 15, 25, 25) 
        work_layout.setSpacing(15)
        
        main_layout.addWidget(workspace, 1) # workspace가 남은 공간을 다 차지함
        
       # ============================================================
        # [수정] 상단 툴바 정렬 최적화
        # ============================================================
        # toolbar_frame = QWidget()
        # 3줄 타이틀과 버튼 그룹을 수용하기 위해 높이를 100px로 권장합니다.
        #toolbar_frame.setFixedHeight(100) 
        
        #toolbar_frame.setStyleSheet("""
        #    QWidget {
        #        background-color: white;
        #        border: 1px solid #E5E7EB; 
        #        border-radius: 12px;        
        #    }
        # """)
        
        # toolbar_layout = QHBoxLayout(toolbar_frame)
        # 상하 여백을 0으로 하고 정렬 기능을 사용하여 중앙을 맞춥니다.
        #toolbar_layout.setContentsMargins(30, 0, 30, 0) 
        #toolbar_layout.setSpacing(0) 
        
        #title_box = QWidget()
        #title_box.setStyleSheet("background: transparent; border: none;")
        #title_layout = QVBoxLayout(title_box)
        #title_layout.setContentsMargins(0, 0, 0, 0)
        #title_layout.setSpacing(0) 
        #title_layout.setAlignment(Qt.AlignVCenter)

        #title_font = "font-size: 20px; font-weight: 900; color: #111827; font-family: Pretendard; margin: 0; padding: 0;"
        #lbl_1 = QLabel("Webtoon")
        #lbl_1.setStyleSheet(title_font)
        #lbl_2 = QLabel("Script")
        #lbl_2.setStyleSheet(title_font)
        #lbl_3 = QLabel("Manager")
        #lbl_3.setStyleSheet(title_font)

        #title_layout.addWidget(lbl_1)
        #title_layout.addWidget(lbl_2)
        #title_layout.addWidget(lbl_3)

        # 타이틀 박스를 수직 중앙에 배치
        #toolbar_layout.addWidget(title_box, 0, Qt.AlignVCenter)
        
        # 중간 빈 공간 (왼쪽과 오른쪽을 밀어냄)
        #toolbar_layout.addStretch() 

        # -----------------------------------------------------------
        # 2. 오른쪽 버튼 뭉터기 (수직 중앙 정렬 및 에러 수정)
        # -----------------------------------------------------------
        right_group = QWidget()
        right_group.setStyleSheet("background: transparent; border: none;")
        right_layout = QHBoxLayout(right_group)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(20) 
        
        # (A) 이미지 추가 버튼 (기존 스타일 유지)
        # btn_upload = QPushButton(" 이미지 추가") 
        # btn_upload.setIcon(get_icon(config.ICON_UPLOAD)) # 아이콘 설정
        # btn_upload.setIconSize(QSize(20, 20)) # 적절한 크기로 조정
        # btn_upload.setCursor(Qt.PointingHandCursor)
        # btn_upload.setFixedSize(140, 48)
        # btn_upload.setStyleSheet("""
        #    QPushButton {
        #        background-color: white; border: 2px solid #FF5722; color: #FF5722;            
        #       font-weight: bold; border-radius: 8px; font-size: 14px;
        #    }
        #    QPushButton:hover { background-color: #FFF5F2; }
        # """)
        # btn_upload.clicked.connect(self.upload_images)
        # right_layout.addWidget(btn_upload, 0, Qt.AlignTop)

        # [핵심] (B) 레이아웃 박스를 '먼저' 생성하여 Pylance 에러를 해결합니다!
        # -----------------------------------------------------------
        
        
        # -----------------------------------------------------------
        # 전체 툴바에 추가 (정의된 analysis_box를 사용)
        #right_layout.addWidget(analysis_box, 0, Qt.AlignVCenter)
        #toolbar_layout.addWidget(right_group, 0, Qt.AlignVCenter)
        
        #work_layout.addWidget(toolbar_frame)
        
        self.status_container = QWidget()
        self.status_container.setFixedHeight(30) # 높이를 조금 더 확보
        status_layout = QHBoxLayout(self.status_container)
        status_layout.setContentsMargins(10, 0, 10, 0)
        status_layout.setSpacing(15)
        
        # 상태 메시지 폰트 및 색상 강조
        self.lbl_status = QLabel("대기 중...")
        self.lbl_status.setStyleSheet("""
            QLabel {
                color: #2563EB; 
                font-size: 13px; 
                font-weight: 800;
                font-family: 'Pretendard';
            }
        """)
        status_layout.addWidget(self.lbl_status, 3) # 메시지 영역에 더 많은 비중 할당
        
        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E5E7EB;
                border-radius: 4px;
            }
            Q ProgressBar::chunk {
                background-color: #2563EB;
                border-radius: 4px;
            }
        """)
        status_layout.addWidget(self.progress_bar, 7)
        
        self.status_container.setVisible(False)
        work_layout.addWidget(self.status_container)

        splitter = QSplitter(Qt.Horizontal)
        splitter.setHandleWidth(20)  # ★ [핵심 1] 간격을 20px로 넓힘 (피그마의 Gap 역할)
        splitter.setChildrenCollapsible(False) # 한쪽이 완전히 사라지지 않게 방지
        
        # ★ [핵심 2] 핸들(구분선)을 투명하게 만들어서 '여백'처럼 보이게 함
        splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: transparent; 
            }
        """)
        
        # 1. 오른쪽 영역을 담을 메인 컨테이너 생성
        self.viewer_container = QWidget()
        self.viewer_container.setStyleSheet("background-color: white; border-radius: 8px;")
        # 1. 오른쪽 영역 컨테이너 (QStackedWidget으로 변경!)
        # [수정] background-color를 white에서 #F9FAFB로 변경
        self.viewer_stack = QStackedWidget()
        self.viewer_stack.setObjectName("ViewerStack")
        self.viewer_stack.setFrameShape(QFrame.NoFrame)
        # padding: 1px를 추가하여 내부 위젯이 테두리 선을 덮지 않도록 보호합니다.
        self.viewer_stack.setStyleSheet("#ViewerStack { background-color: #F9FAFB; border-radius: 8px; border: 1px solid #D1D5DB; padding: 1px; }")

        # ---------------------------------------------------------
        # [Index 0] 초기 안내 화면 (empty_widget) 수정 버전
        # ---------------------------------------------------------
        # [수정] background를 white에서 transparent 또는 #F9FAFB로 변경
        self.empty_widget = QWidget()
        self.empty_widget.setStyleSheet("border: none; background: transparent; border-radius: 8px;") # 바닥(stack) 색이 보이게 투명 처리
        
        empty_vbox = QVBoxLayout(self.empty_widget)
        empty_vbox.addStretch(1) # 위쪽 여백

        # 1. 안내 문구 수정
        lbl_info = QLabel("이미지 추가 버튼을 누르거나<br>드래그 앤 드롭으로 이미지를 추가하세요")
        lbl_info.setStyleSheet("color: #6B7280; font-size: 15px; font-weight: 500; border: none; background: transparent;")
        lbl_info.setAlignment(Qt.AlignCenter)
        empty_vbox.addWidget(lbl_info) # 바로 메인 레이아웃에 추가

        empty_vbox.addSpacing(20) # 문구와 버튼 사이 간격

        # 2. 중앙 이미지 추가 버튼 (스타일 유지)
        self.btn_viewer_add = QPushButton(" 이미지 추가")
        # 2. 아이콘 설정 (진우님이 정의하신 ICON_UPLOAD 사용)
        self.btn_viewer_add.setIcon(get_icon(config.ICON_UPLOAD)) 
        self.btn_viewer_add.setIconSize(QSize(24, 24)) # 아이콘 크기 조절
        
        self.btn_viewer_add.setFixedSize(180, 60)
        self.btn_viewer_add.setCursor(Qt.PointingHandCursor)
        
        # 3. 스타일시트 수정 (dashed -> solid로 변경)
        self.btn_viewer_add.setStyleSheet("""
            QPushButton {
                background-color: #FFF7ED; 
                color: #FB923C;
                border: 2px solid #FB923C; /* 점선을 실선으로 변경 */
                border-radius: 12px;
                font-size: 18px;
                font-weight: bold;
                text-align: center;      /* 글자 중앙 정렬 */
                padding-left: 0px;       /* 왼쪽 패딩 초기화 */
                padding-right: 5px;
            }
            QPushButton:hover {
                background-color: #FFEDD5; 
                border: 2px solid #F97316;
                color: #F97316;
            }
            QPushButton:pressed {
                background-color: #FFEDD5;
            }
        """)
        
        # 4. 기존 함수 연결
        self.btn_viewer_add.clicked.connect(self.upload_images)

        empty_vbox.addWidget(self.btn_viewer_add, 0, Qt.AlignCenter) # 버튼도 바로 추가
        
        empty_vbox.addStretch(1) # 아래쪽 여백

        # ---------------------------------------------------------
        # [Index 1] 실제 웹툰 이미지가 보일 스크롤 영역
        # ---------------------------------------------------------
        self.scroll_area = WebtoonScrollArea()
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setWidgetResizable(True)
        # 내부 뷰포트와 스크롤 영역 자체에 라운드를 주어 이미지가 뚫고 나가지 않게 함
        self.scroll_area.setStyleSheet("""
            QScrollArea { border: none; background: transparent; border-radius: 8px; }
            QWidget { border-radius: 8px; }
        """) 
        self.scroll_area.viewport().setStyleSheet("background: transparent; border-radius: 8px;")
        
        scroll_content = QWidget()
        self.image_layout = QVBoxLayout(scroll_content)
        self.image_layout.setAlignment(Qt.AlignTop)
        self.image_layout.setSpacing(0)
        self.image_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_area.setWidget(scroll_content)

        # ---------------------------------------------------------
        # 스택에 두 페이지를 추가합니다. (순서 중요!)
        # ---------------------------------------------------------
        self.viewer_stack.addWidget(self.empty_widget) # Index 0
        self.viewer_stack.addWidget(self.scroll_area)  # Index 1

        # 스플리터에 이 스택 위젯을 추가!
        splitter.addWidget(self.viewer_stack)

        self.tabs = QTabWidget()

        # [수정] 탭 스타일 (QTabWidget::tab-bar를 사용한 강제 이동)
        self.tabs.setStyleSheet("""
            /* 1. [핵심] 탭 바 전체 위치를 오른쪽으로 10px 밈 */
            QTabWidget::tab-bar {
                left: 15px; /* 이 숫자를 늘리면 더 오른쪽으로 갑니다 */
            }

            /* 2. 탭 바 정렬 */
            QTabBar {
                background: transparent;
                qproperty-drawBase: 0;
            }
            
            /* 3. 개별 탭 버튼 디자인 */
            QTabBar::tab {
                background: transparent;
                color: #888888;
                font-size: 15px;
                font-weight: bold;
                padding: 10px 15px;
                border-bottom: 3px solid transparent;
                margin-right: 5px;
                font-family: 'Pretendard';
            }
            
            /* 4. 선택된 탭 */
            QTabBar::tab:selected {
                color: #FF5722;
                border-bottom: 3px solid #FF5722;
            }
            
            QTabBar::tab:hover {
                color: #FF8A65;
            }
            
            /* 5. 내용 박스 테두리 */
            QTabWidget::pane {
                border: 1px solid #D1D5DB;
                border-radius: 8px;
                background-color: white;
                /* 탭 바가 이동했으므로, 내용 박스와 겹치지 않게 top 조절 */
                top: -1px; 
            }
        """)

        self.text_editor = SmartTextEdit()
        self.text_editor.setFrameShape(QFrame.NoFrame)
        self.text_editor.setAcceptDrops(True)
        self.text_editor.textChanged.connect(self.save_text_content)
        self.text_editor.setStyleSheet("line-height: 160%;") 
        current_font = QApplication.font()
        current_font.setPointSize(11) 
        self.text_editor.setFont(current_font)
        
        # [Step 1] 텍스트 탭 (피그마 디자인 적용: 3단 분리형)
        tab1_widget = QWidget()
        tab1_layout = QVBoxLayout(tab1_widget)
        # 전체 여백을 줘서 박스가 너무 꽉 차지 않게 함
        tab1_layout.setContentsMargins(15, 15, 15, 15) 
        tab1_layout.setSpacing(10) # 각 요소 사이 간격
        
        # ---------------------------------------------------------
        # 1. 상단 툴바 (오른쪽 정렬로 변경)
        # ---------------------------------------------------------
        top_toolbar = QHBoxLayout()
        top_toolbar.setContentsMargins(0, 0, 0, 0)
        
        # ★ [핵심] 빈 공간(스프링)을 맨 앞에 둡니다. -> 모든 요소를 오른쪽으로 밀어버림
        top_toolbar.addStretch() 
        
        # [번호 제거 버튼] (이제 오른쪽 그룹에 합류)
        btn_remove_num = QPushButton("번호제거")
        btn_remove_num.setFixedSize(80, 32)
        btn_remove_num.setCursor(Qt.PointingHandCursor)
        btn_remove_num.setStyleSheet("""
            QPushButton { 
                border: 1px solid #D1D5DB; 
                background-color: white; 
                border-radius: 4px; 
                color: #374151; 
                font-size: 13px; 
                font-weight: bold;
            } 
            QPushButton:hover { background-color: #F3F4F6; border-color: #9CA3AF; } 
            QPushButton:pressed { background-color: #E5E7EB; }
        """)
        btn_remove_num.clicked.connect(self.remove_line_numbers)
        top_toolbar.addWidget(btn_remove_num)
        
        # [간격 추가] 번호제거 버튼과 줌 컨트롤 사이를 조금 띄워줍니다.
        top_toolbar.addSpacing(20) 
        
        # [줌 컨트롤 그룹]
        lbl_zoom = QLabel("텍스트 배율:")
        lbl_zoom.setStyleSheet("color: #4B5563; font-size: 13px; font-weight: bold; margin-right: 5px;")
        
        self.lbl_zoom_val = QLabel("100%")
        self.lbl_zoom_val.setStyleSheet("color: #111827; font-weight: 800; font-size: 13px; margin-right: 10px;")

        # 줌 버튼 스타일
        zoom_btn_style = """
            QPushButton { 
                border: 1px solid #D1D5DB; 
                background-color: white; 
                border-radius: 4px; 
                color: #374151; 
                font-weight: bold;
                font-size: 14px;
                padding: 0px;
                margin: 0px;
                text-align: center;
            } 
            QPushButton:hover { background-color: #F3F4F6; border-color: #9CA3AF; } 
            QPushButton:pressed { background-color: #E5E7EB; }
        """
        
        btn_zoom_out = QPushButton("-")
        btn_zoom_out.setFixedSize(32, 32)
        btn_zoom_out.setStyleSheet(zoom_btn_style)
        btn_zoom_out.clicked.connect(self.text_zoom_out)
        
        btn_zoom_reset = QPushButton("초기화")
        btn_zoom_reset.setFixedSize(60, 32)
        btn_zoom_reset.setStyleSheet(zoom_btn_style)
        btn_zoom_reset.clicked.connect(self.text_zoom_reset)
        
        btn_zoom_in = QPushButton("+")
        btn_zoom_in.setFixedSize(32, 32)
        btn_zoom_in.setStyleSheet(zoom_btn_style)
        btn_zoom_in.clicked.connect(self.text_zoom_in)
        
        top_toolbar.addWidget(lbl_zoom)
        top_toolbar.addWidget(self.lbl_zoom_val) 
        top_toolbar.addWidget(btn_zoom_out)
        top_toolbar.addWidget(btn_zoom_reset)
        top_toolbar.addWidget(btn_zoom_in)
        
        tab1_layout.addLayout(top_toolbar)

        # ---------------------------------------------------------
        # 2. 텍스트 에디터 (가운데 큰 박스)
        # ---------------------------------------------------------
        self.text_editor = SmartTextEdit()
        self.text_editor.setFrameShape(QFrame.NoFrame)
        self.text_editor.textChanged.connect(self.save_text_content)
        
        # [핵심] 에디터 자체에 둥근 테두리를 줍니다. (피그마 스타일)
        self.text_editor.setStyleSheet("""
            QTextEdit {
                border: 1px solid #D1D5DB; /* 회색 테두리 */
                border-radius: 8px;        /* 둥근 모서리 */
                padding: 1px;             /* 안쪽 여백 */
                background-color: white;   /* 흰색 배경 */
                line-height: 160%;         /* 줄 간격 */
                color: #333333;            /* 글자색 */
            }
        """)
        
        current_font = QApplication.font()
        current_font.setPointSize(11) 
        self.text_editor.setFont(current_font)
        
        tab1_layout.addWidget(self.text_editor)

        # ---------------------------------------------------------
        # 3. 하단 버튼 바 (AI검사 & 저장) - 박스 바깥에 위치
        # ---------------------------------------------------------
        step1_bottom_bar = QHBoxLayout()
        step1_bottom_bar.setContentsMargins(0, 5, 0, 0) # 위쪽 여백 살짝 줌
        
        self.btn_simple_start = QToolButton()
        self.btn_simple_start.setText("분석 시작")
        self.btn_simple_start.setPopupMode(QToolButton.MenuButtonPopup)
        self.btn_simple_start.setFixedSize(140, 32)
        self.btn_simple_start.setCursor(Qt.PointingHandCursor)
        self.btn_simple_start.setStyleSheet("""
            QToolButton {
                background-color: #FF5722; color: white;
                font-weight: bold; border-radius: 4px; font-size: 14px; border: none;
                padding-right: 30px;
            }
            QToolButton:hover { background-color: #F97316; }
            QToolButton::menu-button {
                border-left: 1px solid rgba(255, 255, 255, 0.4);
                width: 30px;
                border-top-right-radius: 4px;
                border-bottom-right-radius: 4px;
            }
            QToolButton::menu-arrow {
                subcontrol-position: center center;
                subcontrol-origin: padding;
                width: 12px; height: 12px;
            }
        """)
        self.btn_simple_start.clicked.connect(self.run_ocr)
        self.btn_simple_start.setMenu(self.analysis_menu)
        self.btn_simple_start.hide()
        
        step1_bottom_bar.addWidget(self.btn_simple_start)
        step1_bottom_bar.addStretch()
        
        # AI 맞춤법 검사 버튼
        btn_ai_check = QPushButton(" AI 맞춤법 검사") # 텍스트 살짝 수정
        btn_ai_check.setIcon(get_icon(config.ICON_CHECK))
        btn_ai_check.setIconSize(QSize(18, 18))
        btn_ai_check.setCursor(Qt.PointingHandCursor)
        btn_ai_check.setFixedHeight(32)
        btn_ai_check.setToolTip(
            "AI가 문맥을 분석하여 맞춤법과 띄어쓰기를 교정합니다.<br>"
            "<span style='color: #ff4b4b;'>※ 문장이 의도와 다르게 변형될 수 있으니 확인 후 적용해 주세요.</span>"
        )
        btn_ai_check.setStyleSheet("""
            QPushButton {
                background-color: #FFF9C4; 
                border: 1px solid #FBC02D; 
                color: #5D4037;            
                font-weight: bold;
                border-radius: 4px;
                padding: 0 15px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #FFF59D; }
            QPushButton:pressed { background-color: #FFF176; }
            QToolTip { 
                background-color: white; 
                color: black; 
                border: 1px solid #D1D5DB; 
                padding: 3px 8px; 
                border-radius: 4px;
                font-family: 'Pretendard'; 
                font-size: 12px;
            }
        """)
        btn_ai_check.clicked.connect(self.run_spell_check)

        # 저장 버튼
        btn_save_txt = QPushButton(" 텍스트 파일로 저장")
        btn_save_txt.setCursor(Qt.PointingHandCursor)
        btn_save_txt.setFixedHeight(32)
        btn_save_txt.setIcon(get_icon(config.ICON_SAVE))
        btn_save_txt.setIconSize(QSize(18, 18)) # 텍스트와 균형이 맞도록 18~20px 추천
        btn_save_txt.setStyleSheet("""
            QPushButton { 
                border: 1px solid #D1D5DB; 
                background-color: white; 
                border-radius: 4px; 
                padding: 0 15px; 
                font-weight: bold; 
                color: #333; 
                font-size: 13px; 
            } 
            QPushButton:hover { background-color: #F3F4F6; border-color: #9CA3AF; } 
            QPushButton:pressed { background-color: #E5E7EB; }
        """)
        btn_save_txt.clicked.connect(self.save_text_to_file)
        
        step1_bottom_bar.addWidget(btn_ai_check) 
        step1_bottom_bar.addSpacing(10)
        step1_bottom_bar.addWidget(btn_save_txt)
        
        tab1_layout.addLayout(step1_bottom_bar)
        
        self.tabs.addTab(tab1_widget, "Step 1. 텍스트")
        
        tab2_widget = QWidget()
        tab2_layout = QVBoxLayout(tab2_widget)
        tab2_layout.setContentsMargins(5, 5, 5, 5)
        
        top_bar_step2 = QHBoxLayout()
        top_bar_step2.addStretch()
        btn_add_char = QPushButton("+ 캐릭터 추가")
        btn_add_char.setObjectName("PrimaryBtn")
        btn_add_char.setFixedWidth(108)
        btn_add_char.clicked.connect(lambda: self.add_character_card())
        top_bar_step2.addWidget(btn_add_char)
        tab2_layout.addLayout(top_bar_step2)

        header_frame = QFrame()
        header_frame.setStyleSheet("background-color: #2c3e50; border-radius: 4px; border: none;") 
        header_frame.setFixedHeight(45) 
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(10, 0, 10, 0)
        header_layout.setSpacing(10)
        
        lbl_style = "color: white; font-weight: bold; font-size: 14px;"
        
        lbl_drag_spacer = QLabel()
        lbl_drag_spacer.setFixedWidth(24)
        header_layout.addWidget(lbl_drag_spacer)
        
        lbl_name = QLabel("캐릭터 이름")
        lbl_name.setStyleSheet(lbl_style)
        lbl_name.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_name, 3) 
        lbl_role = QLabel("역할")
        lbl_role.setStyleSheet(lbl_style)
        lbl_role.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_role, 2) 
        lbl_age = QLabel("연령")
        lbl_age.setStyleSheet(lbl_style)
        lbl_age.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_age, 2) 
        lbl_gender = QLabel("성별")
        lbl_gender.setStyleSheet(lbl_style)
        lbl_gender.setAlignment(Qt.AlignCenter)
        header_layout.addWidget(lbl_gender, 2) 
        lbl_empty = QLabel("삭제") 
        lbl_empty.setStyleSheet(lbl_style)
        lbl_empty.setAlignment(Qt.AlignCenter)
        lbl_empty.setFixedWidth(60)
        header_layout.addWidget(lbl_empty)
        tab2_layout.addWidget(header_frame)

        scroll_area_char = QScrollArea()
        scroll_area_char.setWidgetResizable(True)
        scroll_area_char.setStyleSheet("background-color: #f8f9fa; border: none;") 
        self.char_container = CharacterListContainer()
        self.char_container.order_changed_signal.connect(self.save_char_data)
        self.char_layout = self.char_container.layout()
        scroll_area_char.setWidget(self.char_container)
        tab2_layout.addWidget(scroll_area_char)
        self.tabs.addTab(tab2_widget, "Step 2. 캐릭터")
        
        self.table_script = SpreadsheetTable()
        self.table_script.setColumnCount(2)
        self.table_script.setHorizontalHeaderLabels(["캐릭터", "대사"])
        self.table_script.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_script.setColumnWidth(0, 150)
        self.table_script.verticalHeader().setVisible(True) 
        self.table_script.setItemDelegateForColumn(1, ExcelTextDelegate(self.table_script))
        self.table_script.itemChanged.connect(lambda item: self.save_script_data())
        self.table_script.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_script.customContextMenuRequested.connect(self.show_script_context_menu)
        # 1. 먼저 자동 조절 기능을 끕니다.
        self.table_script.verticalHeader().setSectionResizeMode(QHeaderView.Interactive) 

        # 2. 기본 높이를 설정합니다. (진우님 추천 사이즈: 50~60)
        self.table_script.verticalHeader().setDefaultSectionSize(60) 

        # 3. (중요) 혹시 모르니 전체 행에 강제로 적용합니다.
        for i in range(self.table_script.rowCount()):
            self.table_script.setRowHeight(i, 60)

        # --- [기존 코드 교체 시작] ---
        tab3_widget = QWidget()
        tab3_layout = QVBoxLayout(tab3_widget)
        tab3_layout.setContentsMargins(15, 15, 15, 15) # 1. 전체 여백을 넉넉하게 줍니다.
        tab3_layout.setSpacing(15) # 각 요소 간 간격

        # A. 상단 툴바 (기존과 동일)
        top_bar = QHBoxLayout()
        self.lbl_step3_status = QLabel("")
        self.lbl_step3_status.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 13px;")
        top_bar.addWidget(self.lbl_step3_status)
        top_bar.addStretch()
        
        btn_add_script_row = QPushButton("+ 행 추가")
        btn_add_script_row.setObjectName("PrimaryBtn")
        btn_add_script_row.setFixedWidth(85)
        btn_add_script_row.clicked.connect(self.add_script_row)
        
        # [수정] QPushButton 대신 HoverIconButton 사용
        self.btn_load_script = HoverIconButton(
            " Step 1 가져오기", 
            config.ICON_REFRESH,
            normal_color="#333333", # 평소 색상
            hover_color="#FF4B4B"    # 호버 시 변할 색상 (포인트 레드)
        )
        self.btn_load_script.setIconSize(QSize(16, 16))
        self.btn_load_script.setFixedHeight(32) # 높이 유지

        # 기존 테두리와 배경 스타일 유지
        # (글자색 color 속성은 HoverIconButton 내부에서 자동으로 관리하므로 제외합니다)
        self.btn_load_script.setStyleSheet("""
            QPushButton { 
                border: 1px solid #D1D5DB; 
                background-color: white; 
                border-radius: 4px; 
                padding: 0 15px; 
                font-size: 13px; 
                font-family: 'Pretendard', sans-serif;
            } 
            QPushButton:hover { 
                background-color: #FFF5F2; 
                border-color: #9CA3AF; 
            } 
            QPushButton:pressed { 
                background-color: #E5E7EB; 
            }
        """)
        
        self.btn_load_script.clicked.connect(self.load_script_to_table) # 연결 유지
        
        top_bar.addWidget(btn_add_script_row)
        top_bar.addWidget(self.btn_load_script)
        tab3_layout.addLayout(top_bar)

        # B. [핵심] 에디터 컨테이너 (흰색 박스) 생성
        editor_container = QFrame()
        editor_container.setObjectName("EditorContainer") # 스타일 적용을 위한 이름
        editor_container.setStyleSheet("""
            #EditorContainer {
                background-color: white;
                /* 1. 둥근 모서리를 없애고 상하 경계선만 깔끔하게 남깁니다 */
                border-top: 1px solid #E5E7EB;
                border-bottom: 1px solid #E5E7EB;
                border-left: none;
                border-right: none;
            }
        """)
        
        container_layout = QVBoxLayout(editor_container)
        container_layout.setContentsMargins(0, 0, 0, 0) # 테두리와 테이블 사이 미세 간격

        # 테이블 설정 (기존 코드 이동)
        self.table_script = SpreadsheetTable()
        self.table_script.setColumnCount(2)
        self.table_script.setHorizontalHeaderLabels(["캐릭터", "대사"])
        self.table_script.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_script.setColumnWidth(0, 150)
        self.table_script.verticalHeader().setVisible(True)
        self.table_script.setItemDelegateForColumn(1, ExcelTextDelegate(self.table_script))
        self.table_script.itemChanged.connect(lambda item: self.save_script_data())
        self.table_script.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table_script.customContextMenuRequested.connect(self.show_script_context_menu)
        # 테이블 테두리를 없애 컨테이너와 하나처럼 보이게 합니다.
        self.table_script.setStyleSheet("""
            QTableWidget {
                border: none;
                gridline-color: #F3F4F6;
                background-color: white;
                /* [추가] 글자 크기를 15px~16px 정도로 키워보세요 */
                font-size: 15px; 
                font-family: 'Pretendard';
            }
            QHeaderView::section {
                background-color: #F9FAFB;
                border-bottom: 1px solid #E5E7EB;
                border-right: 1px solid #E5E7EB;
                padding: 5px;
                font-weight: bold;
                /* 헤더 글자 크기도 함께 조절하면 균형이 맞습니다 */
                font-size: 13px; 
            }
        """) 

        container_layout.addWidget(self.table_script)
        tab3_layout.addWidget(editor_container) # 컨테이너를 메인 레이아웃에 추가

        # C. 하단 액션바 (버튼 영역)
        bottom_action_bar = QHBoxLayout()
        bottom_action_bar.addStretch() # 버튼을 오른쪽으로 밀어줍니다.

        self.btn_excel_download = QPushButton(" 엑셀 파일 다운로드")
        self.btn_excel_download.setCursor(Qt.PointingHandCursor)
        self.btn_excel_download.setFixedHeight(32)
        self.btn_excel_download.setIcon(get_icon(config.ICON_EXCEL))
        self.btn_excel_download.setIconSize(QSize(18, 18))
        # 스텝 1의 '텍스트 파일로 저장' 버튼과 동일한 스타일
        self.btn_excel_download.setStyleSheet("""
            QPushButton { 
                border: 1px solid #D1D5DB; 
                background-color: white; 
                border-radius: 4px; 
                padding: 0 15px; 
                font-weight: bold; 
                color: #333; 
                font-size: 13px; 
                /* 맥북 환경을 고려해 폰트를 Pretendard로 지정하면 더 깔끔합니다 */
                font-family: 'Pretendard', sans-serif;
            } 
            QPushButton:hover { 
                background-color: #F3F4F6; 
                border-color: #9CA3AF; 
            } 
            QPushButton:pressed { 
                background-color: #E5E7EB; 
            }
        """)
        self.btn_excel_download.clicked.connect(self.export_excel) 
        
        bottom_action_bar.addWidget(self.btn_excel_download)
        tab3_layout.addLayout(bottom_action_bar)
        
        self.tabs.addTab(tab3_widget, "Step 3. 배정")
        # --- [기존 코드 교체 끝] ---
        
        splitter.addWidget(self.tabs)
        splitter.setSizes([450, 900])
        work_layout.addWidget(splitter)
        main_layout.addWidget(workspace)
        
        # [핵심] 토스트 메시지 초기화 (이게 없어서 에러가 났던 것입니다!)
        self.toast = ToastMessage(self)

        self.btn_toggle.raise_()

        self.load_images()

    def update_viewer_background(self, has_images):
        bg_color = "white" if has_images else "#F9FAFB"
        self.viewer_stack.setStyleSheet(f"#ViewerStack {{ background-color: {bg_color}; border-radius: 8px; border: 1px solid #D1D5DB; padding: 1px; }}")


    def create_menu(self):
        menubar = self.menuBar()
        
        # 파일 메뉴
        file_menu = menubar.addMenu("파일(&F)")
        
        # 새 작업(심플 모드) 액션 추가
        self.action_new_simple = QAction("새 작업 (심플 모드)", self)
        self.action_new_simple.setShortcut("Ctrl+N")
        self.action_new_simple.triggered.connect(self.prompt_clear_workspace)
        self.action_new_simple.setVisible(self.is_simple_mode) # 모드에 따라 숨김/표시
        file_menu.addAction(self.action_new_simple)
        
        file_menu.addSeparator()

        # 3. '작품 관리' 액션을 파일 메뉴에 추가합니다.
        manage_action = file_menu.addAction("작품 관리(&M)")
        manage_action.triggered.connect(self.open_management_system)
        
        # 심플 모드 토글 추가
        self.action_simple_mode = file_menu.addAction("심플 모드 전환")
        self.action_simple_mode.triggered.connect(self.toggle_simple_mode)

        file_menu.addSeparator() 
        
        action_exit = QAction("종료", self)
        action_exit.triggered.connect(self.close)
        file_menu.addAction(action_exit)

        # 설정 메뉴
        settings_menu = menubar.addMenu("설정(&S)")

        # [순서 변경] 관용구 설정을 맨 위로
        action_idiom = QAction("관용구(지문) 설정", self)
        action_idiom.triggered.connect(self.open_idiom_settings_dialog)
        settings_menu.addAction(action_idiom)

        settings_menu.addSeparator()

        # API 키 설정을 아래로
        action_settings = QAction("API 키 설정", self)
        action_settings.setShortcut("Ctrl+,")
        action_settings.triggered.connect(self.open_settings_dialog)
        settings_menu.addAction(action_settings)

    def open_settings_dialog(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def open_idiom_settings_dialog(self):
        dlg = IdiomSettingsDialog(self)
        if dlg.exec() == QDialog.Accepted:
            self.setup_idiom_shortcuts()
            self.toast.show_message("✅ 관용구 설정이 저장되었습니다.", 2000)

    def setup_idiom_shortcuts(self):
        """설정된 관용구들에 대해 Alt + 숫자 단축키를 생성합니다."""
        # 기존 단축키 제거
        for sc in self.idiom_shortcuts:
            sc.setEnabled(False)
            sc.deleteLater()
        self.idiom_shortcuts = []

        # 신규 단축키 등록
        for item in config.IDIOMS:
            key_seq = f"Alt+{item['key']}"
            shortcut = QShortcut(QKeySequence(key_seq), self)
            # lambda 캡처 문제를 피하기 위해 default value 사용
            shortcut.activated.connect(lambda t=item['text']: self.handle_idiom_trigger(t))
            self.idiom_shortcuts.append(shortcut)

    def handle_idiom_trigger(self, text):
        """단축키가 눌렸을 때의 동작: 포커스된 에디터가 있으면 삽입, 없으면 클립보드 복사"""
        focused_widget = QApplication.focusWidget()
        
        # 1. 텍스트 입력 위젯(SmartTextEdit, QTextEdit, QLineEdit 등)인 경우
        if isinstance(focused_widget, (QTextEdit, QLineEdit, SmartTextEdit)):
            focused_widget.insertPlainText(text) if hasattr(focused_widget, 'insertPlainText') else focused_widget.insert(text)
        else:
            # 2. 그 외의 경우 클립보드에 복사
            QApplication.clipboard().setText(text)

    def toggle_simple_mode(self, show_toast=True, check_work=True):
        # 모드 전환 전 현재 모드의 스크롤 위치 저장
        self.save_viewer_state()
        
        self.is_simple_mode = not self.is_simple_mode
        config.IS_SIMPLE_MODE = self.is_simple_mode      # 메뉴 텍스트 및 가시성을 현재 상태에 맞춰 변경
        if hasattr(self, 'action_simple_mode'):
            self.action_simple_mode.setText("전체 모드 전환" if self.is_simple_mode else "심플 모드 전환")
        if hasattr(self, 'action_new_simple'):
            self.action_new_simple.setVisible(self.is_simple_mode)
        
        # [수정] 위젯이 존재하는지 확인 후 로드
        if hasattr(self, 'lbl_api_count'):
            self.load_api_count()
            
        if self.is_simple_mode:
            self.sidebar.hide()
            self.btn_toggle.hide()
            self.tabs.tabBar().hide()
            self.tabs.setCurrentIndex(0)
            self.btn_simple_start.show()
            self.tabs.setStyleSheet("""
                QTabWidget::pane {
                    border: 1px solid #D1D5DB;
                    border-radius: 8px;
                    background-color: white;
                    margin-top: 2px;
                }
            """)
            self.clear_workspace()
            self.load_images()
            self.load_data()
            self.load_viewer_state() # 새 모드의 스크롤 위치 복구
            
            # [추가] 전체 모드에서 심플 모드로 전환 시, 기존 작업이 있다면 묻습니다.
            if check_work:
                self.check_existing_work(is_startup=False)

            if show_toast:
                self.toast.show_message("✨ 심플 모드가 켜졌습니다. 드롭하여 바로 텍스트를 추출하세요.", 3000)
        else:
            self.sidebar.show()
            self.btn_toggle.show()
            self.tabs.tabBar().show()
            self.btn_simple_start.hide()
            self.tabs.setStyleSheet("""
                /* 1. [핵심] 탭 바 전체 위치를 오른쪽으로 10px 밈 */
                QTabWidget::tab-bar {
                    left: 15px; /* 이 숫자를 늘리면 더 오른쪽으로 갑니다 */
                }

                /* 2. 탭 바 정렬 */
                QTabBar {
                    background: transparent;
                    qproperty-drawBase: 0;
                }
                
                /* 3. 개별 탭 버튼 디자인 */
                QTabBar::tab {
                    background: transparent;
                    color: #888888;
                    font-size: 15px;
                    font-weight: bold;
                    padding: 10px 15px;
                    border-bottom: 3px solid transparent;
                    margin-right: 5px;
                    font-family: 'Pretendard';
                }
                
                /* 4. 선택된 탭 */
                QTabBar::tab:selected {
                    color: #FF5722;
                    border-bottom: 3px solid #FF5722;
                }
                
                QTabBar::tab:hover {
                    color: #FF8A65;
                }
                
                /* 5. 내용 박스 테두리 */
                QTabWidget::pane {
                    border: 1px solid #D1D5DB;
                    border-radius: 8px;
                    background-color: white;
                    /* 탭 바가 이동했으므로, 내용 박스와 겹치지 않게 top 조절 */
                    top: -1px; 
                }
            """)
            self.clear_workspace()
            self.load_images()
            self.load_data()
            self.load_viewer_state() # 새 모드의 스크롤 위치 복구
            
            if show_toast:
                self.toast.show_message("🏢 전체 모드로 전환되었습니다.", 3000)
                
        # 상태를 설정 파일에 저장
        config.save_settings(config.API_PRESETS, config.ACTIVE_PRESET_NAME, is_simple_mode=self.is_simple_mode)

    def get_paths(self):
        if getattr(self, 'is_simple_mode', False):
            simple_dir = os.path.join(CACHE_DIR, "simple_mode")
            os.makedirs(simple_dir, exist_ok=True)
            return simple_dir, simple_dir, os.path.join(simple_dir, "script.txt")

        if not self.current_title or not self.current_episode: return None, None, None
        # [수정] 경로의 뿌리를 PROJECTS_DIR로 변경
        t_path = os.path.join(PROJECTS_DIR, self.current_title)
        e_path = os.path.join(t_path, self.current_episode)
        i_path = os.path.join(e_path, "images")
        os.makedirs(i_path, exist_ok=True)
        return e_path, i_path, os.path.join(e_path, "script.txt")

    def refresh_project_list(self):
        self.combo_project.blockSignals(True)
        self.combo_project.clear()
        # [수정] BASE_DIR 대신 PROJECTS_DIR 내부 폴더만 검색합니다.
        if os.path.exists(PROJECTS_DIR):
            projects = sorted([d for d in os.listdir(PROJECTS_DIR) 
                              if os.path.isdir(os.path.join(PROJECTS_DIR, d))])
            self.combo_project.addItems(projects)
            
        self.combo_project.setCurrentIndex(-1) 
        self.combo_project.blockSignals(False)
        self.clear_workspace()

    def create_project(self):
        name = self.input_new_project.text().strip()
        if name:
            # [수정] projects 폴더 안에 새 작품 폴더를 만듭니다.
            os.makedirs(os.path.join(PROJECTS_DIR, name), exist_ok=True)
            self.refresh_project_list()
            self.combo_project.setCurrentText(name)
            self.input_new_project.clear()

    def on_project_change(self, text):
        if not text: return
        self.current_title = text
        self.current_episode = "" 
        self.refresh_episode_list()

    def refresh_episode_list(self):
        self.combo_episode.blockSignals(True)
        self.combo_episode.clear()
        
        if self.current_title:
            # [수정] BASE_DIR이 아니라 PROJECTS_DIR을 뿌리로 잡습니다.
            from config import PROJECTS_DIR
            t_path = os.path.join(PROJECTS_DIR, self.current_title)
            
            # 폴더가 존재하는지 한 번 더 확인하여 에러를 방지합니다.
            if os.path.exists(t_path):
                eps = sorted([d for d in os.listdir(t_path) 
                             if os.path.isdir(os.path.join(t_path, d))], 
                             key=natural_sort_key)
                self.combo_episode.addItems(eps)

        self.combo_episode.setCurrentIndex(-1)
        self.combo_episode.blockSignals(False)
        self.clear_workspace()

    def create_episode(self):
        if not self.current_title:
            self.toast.show_message("⚠️ 작품 등록을 먼저 진행해주세요!", 2000)
            return

        name = self.input_new_episode.text().strip()
        if not name:
            self.toast.show_message("⚠️ 회차 이름을 입력해주세요.", 2000)
            return

        episode_path = os.path.join(PROJECTS_DIR, self.current_title, name)
        if os.path.exists(episode_path):
            self.toast.show_message("⚠️ 이미 존재하는 회차 이름입니다.", 2000)
            return

        os.makedirs(episode_path, exist_ok=True)
        self.refresh_episode_list()
        self.combo_episode.setCurrentText(name)
        self.input_new_episode.clear()
        self.toast.show_message(f"✅ '{name}' 회차가 생성되었습니다!")

    def on_episode_change(self, text):
        if not text: return
        
        # [추가] 이전 회차의 스크롤 위치 저장
        self.save_viewer_state()
            
        self.current_episode = text
        self.load_images()
        self.load_data()
        
        # [추가] 새 회차의 스크롤 위치 복구 및 API 호출수 불러오기
        self.load_viewer_state()
        self.load_api_count()

    def save_viewer_state(self):
        """현재 웹툰 뷰어의 스크롤 위치(비율)를 파일로 저장합니다."""
        try:
            p_path, _, _ = self.get_paths()
            if not p_path or not os.path.exists(p_path): return
            
            ratio = self.scroll_area.get_scroll_ratio()
            if ratio <= 0: return
            
            import json
            meta_path = os.path.join(p_path, "viewer_state.json")
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump({"scroll_ratio": ratio}, f)
        except Exception as e:
            print(f"DEBUG: 스크롤 위치 저장 실패 -> {e}")

    def load_viewer_state(self):
        """파일에서 스크롤 위치(비율)를 읽어와 뷰어에 적용합니다."""
        try:
            p_path, _, _ = self.get_paths()
            if not p_path: return
            
            import json
            meta_path = os.path.join(p_path, "viewer_state.json")
            if os.path.exists(meta_path):
                with open(meta_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    ratio = data.get("scroll_ratio", 0.0)
                    self.scroll_area.set_scroll_ratio(ratio)
        except Exception as e:
            print(f"DEBUG: 스크롤 위치 로드 실패 -> {e}")

    def closeEvent(self, event):
        """프로그램 종료 시 현재 상태를 저장합니다."""
        self.save_viewer_state()
        super().closeEvent(event)

    def keyPressEvent(self, event):
        """단축키 처리 (Home/End, Ctrl+Up/Down)"""
        # 1. Ctrl(또는 Cmd) 조합키 체크
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_Up:
                self.scroll_area.verticalScrollBar().setValue(0)
                event.accept()
                return
            elif event.key() == Qt.Key_Down:
                self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
                event.accept()
                return

        # 2. Home / End 키 (에디터 포커스가 없을 때만)
        if not self.text_editor.hasFocus():
            if event.key() == Qt.Key_Home:
                self.scroll_area.verticalScrollBar().setValue(0)
                event.accept()
                return
            elif event.key() == Qt.Key_End:
                self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
                event.accept()
                return
        
        super().keyPressEvent(event)

    def clear_workspace(self):
        # 스크롤 위치 초기화
        self.scroll_area.verticalScrollBar().setValue(0)
        
        while self.image_layout.count():
            child = self.image_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
            
        self.text_editor.blockSignals(True)
        self.text_editor.clear()
        self.text_editor.blockSignals(False)
        
        while self.char_layout.count():
            child = self.char_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        self.table_script.setRowCount(0)
        self.file_list_widget.clear()

    # [수정] 통합된 이미지 처리 함수 (버튼 + 드래그앤드롭 공용)
    def process_image_files(self, file_paths):
        if not getattr(self, 'is_simple_mode', False) and not self.current_episode:
             self.toast.show_message("⚠️ 이미지를 추가하려면 먼저 '회차'를 선택해주세요!")
             return
        
        _, i_path, _ = self.get_paths()
        valid_extensions = ('.png', '.jpg', '.jpeg')
        processed_count = 0
        duplicate_count = 0
        
        for fname in file_paths:
            base_name = os.path.basename(fname)
            dest_path = os.path.join(i_path, base_name)
            
            # 중복 체크
            if os.path.exists(dest_path):
                duplicate_count += 1
                continue

            if fname.lower().endswith(valid_extensions) and not base_name.startswith('.'):
                try:
                    shutil.copy(fname, i_path)
                    processed_count += 1
                except Exception as e:
                    print(f"파일 복사 실패: {fname} ({e})")

        if processed_count > 0:
            self.load_images()
            if duplicate_count > 0:
                self.toast.show_message(f"✅ {processed_count}개 추가 (중복 {duplicate_count}개 제외)")
            else:
                self.toast.show_message(f"✅ 이미지 {processed_count}장이 추가되었습니다!")
        elif duplicate_count > 0:
            self.toast.show_message("이미 추가한 파일입니다.")

    def upload_images(self):
        file_names, _ = QFileDialog.getOpenFileNames(self, "이미지 선택", "", "Images (*.png *.jpg *.jpeg)")
        if file_names:
            self.process_image_files(file_names)

    def load_images(self):
        # 1. 기존 위젯 및 리스트 청소
        while self.image_layout.count():
            child = self.image_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        
        self.file_list_widget.clear() 

        # 2. 경로 체크
        _, i_path, _ = self.get_paths()
        if not i_path or not os.path.exists(i_path):
            # 경로가 아예 없거나 프로젝트가 안 열렸을 때도 회색 배경이어야 합니다.
            self.update_viewer_background(False) # [추가 1]
            self.viewer_stack.setCurrentIndex(0)
            return

        # 파일 목록 가져오기
        files = sorted([f for f in os.listdir(i_path) 
                       if f.lower().endswith(('png','jpg','jpeg')) and not f.startswith('.')], 
                       key=natural_sort_key)

        # 3. 파일 유무 판별 및 배경색 업데이트
        has_images = len(files) > 0
        self.update_viewer_background(has_images) # [추가 2 - 핵심 위치]

        if not has_images:
            self.viewer_stack.setCurrentIndex(0)
        else:
            self.viewer_stack.setCurrentIndex(1)
            
            for f in files:
                # (A) 중앙 뷰어에 이미지 추가
                lbl_img = ResponsiveLabel(os.path.join(i_path, f))
                self.image_layout.addWidget(lbl_img)

                # (B) 사이드바 리스트에도 추가
                item = QListWidgetItem(f" {f}")
                item.setIcon(get_icon(config.ICON_FILE)) 
                self.file_list_widget.addItem(item)

        

    def run_ocr(self):
        # 1. 파일 경로 및 대상 확인
        _, i_path, _ = self.get_paths()
        files = sorted([os.path.join(i_path, f) for f in os.listdir(i_path) 
                    if f.lower().endswith(('png','jpg')) and not f.startswith('.')], 
                   key=natural_sort_key)
        if not files: return

        # 2. '새로 분석하기' 체크 여부를 먼저 파악합니다.
        force_mode = self.check_reanalyze.isChecked()

        # 디버그용 출력 (터미널에서 확인해보세요)
        print(f"DEBUG: 빠른모드 체크상태 -> {self.radio_fast.isChecked()}")
        print(f"DEBUG: 스마트모드 체크상태 -> {self.radio_smart.isChecked()}")

        if self.radio_fast.isChecked():
            mode = "FAST"
        elif self.radio_smart.isChecked(): # else 대신 elif로 명확하게 확인
            mode = "SMART"
        else:
            mode = "FAST" # 예외 상황 대비

        # -----------------------------------------------------------
        # [조건부 안전장치] 
        # '새로 분석하기'가 꺼져 있고 + 에디터에 글이 있을 때만 묻습니다.
        # -----------------------------------------------------------
        if not force_mode and self.text_editor.toPlainText().strip():
            reply = QMessageBox.question(
                self, 
                "분석 확인", 
                "⚠️ 이미 분석된 내용이나 수정 중인 텍스트가 있습니다.\n"
                "다시 분석을 시작하면 Step 1의 모든 정보가 초기화됩니다.\n\n"
                "그래도 진행하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No 
            )
            
            # 사용자가 'No'를 누르면 여기서 바로 함수를 종료합니다.
            if reply == QMessageBox.No:
                return
        
        # 5. [실행] 이제 모든 준비가 끝났습니다! 분석 로직으로 전달합니다.
        print(f">>> [{mode}] 모드로 분석을 시작합니다. (새로고침: {force_mode})")
        # 여기서 실제 분석 로직 함수를 호출하세요.
        # self.start_extraction(files, mode, force_mode)

        # -----------------------------------------------------------
        
        # 3. 분석 시작 시 UI 상태 변경
        self.btn_start.setEnabled(False)
        self.status_container.setVisible(True)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        
        # 분석 모드(빠른/스마트) 결정
        analysis_mode = "smart" if self.radio_smart.isChecked() else "fast"
        
        # 워커 생성 및 실행
        self.worker = OCRWorker(files, mode=analysis_mode, force_mode=force_mode)
        self.worker.progress_val.connect(self.progress_bar.setValue)
        self.worker.progress_text.connect(self.lbl_status.setText)
        self.worker.api_used.connect(self.increment_api_counter)
        self.worker.finished_ocr.connect(self.on_ocr_finished)
        self.worker.start()

    def adjust_menu_position(self):
        """Qt의 자동 배치 로직이 끝난 직후, 메뉴를 강제로 위로 가둡니다."""
        # 1. 일단 메뉴가 보이지 않게 투명하게 만듭니다 (잔상 방지)
        self.analysis_menu.setWindowOpacity(0.0)
        
        # 2. 아주 미세한 지연(1ms) 후에 위치를 옮기는 함수를 실행합니다.
        # 이렇게 해야 Qt가 '아래'로 배치한 직후에 우리가 '위'로 가로챌 수 있습니다.
        QTimer.singleShot(1, self._force_move_menu_up)

    def _force_move_menu_up(self):
        """실제로 메뉴를 위로 옮기고 투명도를 복구하는 함수"""
        if not self.analysis_menu.isVisible():
            return
            
        # 메뉴 크기 재계산
        self.analysis_menu.adjustSize()
        
        # 현재 모드에 따라 기준이 될 버튼 선택
        target_btn = self.btn_simple_start if getattr(self, 'is_simple_mode', False) else self.btn_start
        
        # 버튼의 화면상 절대 위치 구하기
        button_pos = target_btn.mapToGlobal(QPoint(0, 0))
        
        # [위치 계산] 버튼 위로 띄우기
        x = button_pos.x() + target_btn.width() - self.analysis_menu.width()
        y = button_pos.y() - self.analysis_menu.height() - 5
        
        # 강제 이동
        self.analysis_menu.move(x, y)
        
        # 이제 자리를 잡았으니 짜잔! 하고 보여줍니다.
        self.analysis_menu.setWindowOpacity(1.0)
        # 확실히 위에 보이도록 레이어 우선순위 높임
        self.analysis_menu.raise_()

    def increment_api_counter(self):
        self.api_call_count += 1
        if hasattr(self, 'lbl_api_count'):
            self.lbl_api_count.setText(f"{self.api_call_count}회")
        self.save_api_count() # [추가] 호출 시마다 즉시 저장

    def load_api_count(self):
        """현재 회차의 API 호출 수를 파일에서 불러옵니다."""
        self.api_call_count = 0
        try:
            if getattr(self, 'is_simple_mode', False):
                e_path = os.path.join(CACHE_DIR, "simple_mode")
            else:
                e_path, _, _ = self.get_paths()
            
            if e_path and os.path.exists(os.path.join(e_path, "api_count.json")):
                import json
                with open(os.path.join(e_path, "api_count.json"), "r", encoding='utf-8') as f:
                    data = json.load(f)
                    self.api_call_count = data.get("api_call_count", 0)
        except Exception as e:
            print(f"Error loading API count: {e}")
        
        if hasattr(self, 'lbl_api_count'):
            self.lbl_api_count.setText(f"{self.api_call_count}회")

    def save_api_count(self):
        """현재 회차의 API 호출 수를 파일로 저장합니다."""
        try:
            if getattr(self, 'is_simple_mode', False):
                e_path = os.path.join(CACHE_DIR, "simple_mode")
            else:
                e_path, _, _ = self.get_paths()
            
            if e_path:
                os.makedirs(e_path, exist_ok=True)
                import json
                with open(os.path.join(e_path, "api_count.json"), "w", encoding='utf-8') as f:
                    json.dump({"api_call_count": self.api_call_count}, f)
        except Exception as e:
            print(f"Error saving API count: {e}")

    def on_ocr_finished(self, lines):
        text = "\n".join(lines)
        self.text_editor.setText(text)
        self.btn_start.setEnabled(True)
        self.lbl_status.setText("분석 완료!")
        self.progress_bar.setValue(100)
        QTimer.singleShot(1500, lambda: self.status_container.setVisible(False))
        self.save_text_content()
        self.check_reanalyze.setChecked(False)

    def save_text_content(self):
        if not getattr(self, 'is_simple_mode', False) and not self.current_episode: return
        _, _, s_path = self.get_paths()
        if s_path:
            with open(s_path, 'w', encoding='utf-8') as f: f.write(self.text_editor.toPlainText())

    def create_table_combo(self, items, current_text=""):
        combo = ClickableComboBox()
        combo.addItems(items)
        if current_text and current_text in items:
            combo.setCurrentText(current_text)
        else:
            combo.setCurrentIndex(-1)
        
        combo.setStyleSheet("""
            QComboBox {
                border: none;
                border-radius: 0px;
                background-color: transparent;
                padding-left: 5px;
            }
            QComboBox::drop-down {
                border: none;
                background-color: transparent;
                width: 20px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #d1d5db;
                background-color: white;
            }
        """)
        line_edit = combo.lineEdit()
        if line_edit:
            line_edit.setTextMargins(0, 0, 0, 0)
            
        # [복구] 기존에 누락되었던 콜백 및 저장 신호 연결
        combo.set_refresh_callback(self.get_character_list)
        combo.currentTextChanged.connect(lambda text: self.save_script_data())
        
        return combo

    def add_character_card(self, name="", age="", gender="", role=""):
        card = CharacterRow(name, age, gender, role)
        card.delete_signal.connect(self.remove_character_card)
        card.input_name.textChanged.connect(self.save_char_data)
        card.combo_role.currentTextChanged.connect(self.save_char_data)
        card.combo_age.currentTextChanged.connect(self.save_char_data)
        card.combo_gender.currentTextChanged.connect(self.save_char_data)
        self.char_layout.addWidget(card)
        self.save_char_data()

    def remove_character_card(self, card_widget):
        card_widget.deleteLater()
        self.char_layout.removeWidget(card_widget)
        QTimer.singleShot(100, self.save_char_data)

    def insert_script_row_at(self, row_idx):
        if row_idx < 0: row_idx = self.table_script.rowCount()
        self.table_script.insertRow(row_idx)
        
        combo = self.create_table_combo(self.get_character_list())
        combo.set_refresh_callback(self.get_character_list)
        combo.currentTextChanged.connect(lambda text: self.save_script_data())

        self.table_script.setCellWidget(row_idx, 0, combo)
        self.table_script.setItem(row_idx, 1, QTableWidgetItem(""))
        
        # [추가] 행 추가 직후 즉시 저장은 충돌 위험이 있으므로 아주 짧게 지연 호출
        QTimer.singleShot(10, self.save_script_data)

    def get_character_list(self):
        chars = []
        for i in range(self.char_layout.count()):
            widget = self.char_layout.itemAt(i).widget()
            if isinstance(widget, CharacterRow):
                name = widget.input_name.text().strip()
                if name: chars.append(name)
        return chars

    def show_script_context_menu(self, pos):
        menu = QMenu()
        # [추가] 최상단에 실행취소 / 다시실행 추가 (아이콘 적용)
        undo_action = menu.addAction(get_icon(config.ICON_UNDO), "실행취소 (Ctrl+Z)")
        redo_action = menu.addAction(get_icon(config.ICON_REDO), "다시실행 (Ctrl+Shift+Z)")
        menu.addSeparator()

        action_insert_above = menu.addAction(get_icon(config.ICON_ARROW_UP), "위에 행 추가")
        action_insert_below = menu.addAction(get_icon(config.ICON_ARROW_DOWN), "아래에 행 추가")
        menu.addSeparator()
        merge_action = menu.addAction(get_icon(config.ICON_LINK), "내용 합치기 (텍스트 연결)")
        menu.addSeparator()
        delete_action = menu.addAction("행 삭제")
        delete_action.setIcon(get_icon(config.ICON_DELETE))
        
        action = menu.exec(QCursor.pos())
        if not action: return

        # [추가] 실행취소/다시실행 처리
        if action == undo_action:
            self.table_script.undo()
            return
        elif action == redo_action:
            self.table_script.redo()
            return
        
        selected_ranges = self.table_script.selectedRanges()
        if not selected_ranges: return

        top_row = selected_ranges[0].topRow()
        bottom_row = selected_ranges[-1].bottomRow()
        
        rows = set()
        for r in selected_ranges:
            for i in range(r.topRow(), r.bottomRow() + 1):
                rows.add(i)
        rows = sorted(list(rows))

        if action == delete_action:
            self.table_script.save_state_for_undo() # [추가] 상태 백업
            for r in reversed(rows):
                self.table_script.removeRow(r)
            self.save_script_data()

        elif action == action_insert_above:
            self.table_script.save_state_for_undo() # [추가] 상태 백업
            self.insert_script_row_at(top_row)
        
        elif action == action_insert_below:
            self.table_script.save_state_for_undo() # [추가] 상태 백업
            self.insert_script_row_at(bottom_row + 1)
            
        elif action == merge_action:
            if len(rows) < 2:
                QMessageBox.warning(self, "알림", "합칠 행을 2개 이상 선택해주세요.")
                return
            self.table_script.save_state_for_undo() # [추가] 상태 백업
            combined_text = []
            for r in rows:
                item = self.table_script.item(r, 1) 
                if item and item.text().strip():
                    combined_text.append(item.text().strip())
            full_text = " ".join(combined_text)
            self.table_script.setItem(rows[0], 1, QTableWidgetItem(full_text))
            for r in reversed(rows[1:]):
                self.table_script.removeRow(r)
            self.save_script_data()

    def add_script_row(self):
        self.table_script.save_state_for_undo() # [추가] 상태 백업
        self.insert_script_row_at(self.table_script.rowCount())

    def load_script_to_table(self):
        if self.table_script.rowCount() > 0:
            reply = QMessageBox.question(
                self, 
                "초기화 확인", 
                "역할 배정 정보가 초기화 됩니다.\n 그래도 Step 1 내용을 가져오시겠습니까?",
                QMessageBox.Yes | QMessageBox.No, 
                QMessageBox.No 
            )
            if reply == QMessageBox.No: return

        self.table_script.save_state_for_undo() # [추가] 상태 백업

        text = self.text_editor.toPlainText()
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        clean_lines = [re.sub(r'^(\[\d+\]|\d+\.)\s*', '', line).strip() for line in lines]
        self.table_script.blockSignals(True)
        self.table_script.setRowCount(len(clean_lines))
        char_list = self.get_character_list()
        for i, line in enumerate(clean_lines):
            combo = self.create_table_combo(char_list)
            combo.set_refresh_callback(self.get_character_list)
            combo.currentTextChanged.connect(lambda text: self.save_script_data())
            
            self.table_script.setCellWidget(i, 0, combo)
            self.table_script.setItem(i, 1, QTableWidgetItem(line))
        self.table_script.blockSignals(False)
        self.table_script.resizeRowsToContents() 
        self.save_script_data()

    def save_script_data(self, *args):
        import pandas as pd
        e_path, _, _ = self.get_paths()
        if not e_path: return
        rows = []
        for i in range(self.table_script.rowCount()):
            combo_widget = self.table_script.cellWidget(i, 0)
            char_name = ""
            if combo_widget and isinstance(combo_widget, QComboBox):
                char_name = combo_widget.currentText()
            line_item = self.table_script.item(i, 1)
            line_text = line_item.text() if line_item else ""
            rows.append({'Character': char_name, 'Line': line_text})
        df = pd.DataFrame(rows)
        df.to_csv(os.path.join(e_path, "script_data.csv"), index=False, encoding='utf-8-sig')
        self.table_script.resizeRowsToContents()
        self.lbl_step3_status.setText("💾 저장 완료")
        QTimer.singleShot(1500, lambda: self.lbl_step3_status.setText(""))

    def save_char_data(self):
        import pandas as pd
        e_path, _, _ = self.get_paths()
        if not e_path: return
        rows = []
        for i in range(self.char_layout.count()):
            widget = self.char_layout.itemAt(i).widget()
            if isinstance(widget, CharacterRow):
                rows.append(widget.get_data())
        df = pd.DataFrame(rows)
        df.to_csv(os.path.join(e_path, "character_info.csv"), index=False, encoding='utf-8-sig')

    def load_data(self):
        import pandas as pd
        e_path, _, s_path = self.get_paths()
        if not e_path or not s_path: return # 경로가 없으면 로드 중단

        self.text_editor.blockSignals(True)
        if os.path.exists(s_path):
            with open(s_path, 'r', encoding='utf-8') as f: self.text_editor.setText(f.read())
        else: self.text_editor.clear()
        self.text_editor.blockSignals(False)
        while self.char_layout.count():
            child = self.char_layout.takeAt(0)
            if child.widget(): child.widget().deleteLater()
        c_csv = os.path.join(e_path, "character_info.csv")
        if os.path.exists(c_csv):
            df = pd.read_csv(c_csv, keep_default_na=False)
            for _, row in df.iterrows():
                self.add_character_card(
                    name=str(row.get('Character','')),
                    age=str(row.get('Age','')),
                    gender=str(row.get('Gender','')),
                    role=str(row.get('Role',''))
                )
        
        # 3. 스크립트 테이블 데이터 로드
        self.table_script.blockSignals(True)
        self.table_script.setRowCount(0)
        s_csv = os.path.join(e_path, "script_data.csv")
        
        # [수정] 통합된 get_character_list 사용
        char_list = self.get_character_list()
        
        if os.path.exists(s_csv):
            df = pd.read_csv(s_csv, keep_default_na=False)
            for _, row in df.iterrows():
                r = self.table_script.rowCount()
                self.table_script.insertRow(r)
                
                # 캐릭터 콤보박스
                combo = self.create_table_combo(char_list, str(row.get('Character','')))
                self.table_script.setCellWidget(r, 0, combo)
                
                # 대사
                self.table_script.setItem(r, 1, QTableWidgetItem(str(row.get('Line',''))))
        
        self.table_script.blockSignals(False)
        self.table_script.resizeRowsToContents()

    def export_excel(self):
        from excel_handler import export_to_excel
        export_to_excel(self)

    def update_zoom_style(self):
        current_pct = 100 + (self.zoom_step * 10)
        self.lbl_zoom_val.setText(f"{current_pct}%")
        base_size = 14
        scale = 1.0 + (self.zoom_step * 0.1)
        new_size = int(base_size * scale)
        if new_size < 8: new_size = 8
        self.text_editor.setStyleSheet(f"line-height: 160%; font-size: {new_size}px;")

    def text_zoom_in(self):
        self.zoom_step += 1
        self.update_zoom_style()

    def text_zoom_out(self):
        self.zoom_step -= 1
        self.update_zoom_style()

    def text_zoom_reset(self):
        self.zoom_step = 0
        self.update_zoom_style()

    def save_text_to_file(self):
        content = self.text_editor.toPlainText()
        if not content.strip():
            self.toast.show_message("⚠️ 저장할 텍스트 내용이 없습니다.", 2000) # 토스트 사용
            return
        if self.current_title and self.current_episode:
            default_filename = f"{self.current_title}_{self.current_episode}_텍스트.txt"
        else:
            default_filename = "script.txt"
            
        # 마지막 저장 경로를 고려한 기본 경로 설정
        default_path = os.path.join(config.get_initial_dir(), default_filename)
        
        # [맥 네이티브 창 복구]
        options = QFileDialog.Option(0) if platform.system() == "Darwin" else QFileDialog.DontConfirmOverwrite
        save_path, _ = QFileDialog.getSaveFileName(self, "텍스트 파일로 저장", default_path, "Text Files (*.txt);;All Files (*)", options=options)
        
        if save_path:
            config.update_last_save_dir(save_path)
            if os.path.exists(save_path):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("파일 중복 확인")
                msg_box.setText(f"'{os.path.basename(save_path)}' 파일이 이미 존재합니다.")
                msg_box.setInformativeText("기존 파일을 대체할까요, 아니면 새 이름으로 저장할까요?")
                
                # 버튼 순서 조정: [덮어쓰기] [새 이름으로 저장] [취소]
                btn_yes = msg_box.addButton("덮어쓰기", QMessageBox.ActionRole)
                btn_rename = msg_box.addButton("새 이름으로 저장", QMessageBox.ActionRole)
                btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
                msg_box.setDefaultButton(btn_rename)
                
                msg_box.exec()
                clicked = msg_box.clickedButton()
                
                if clicked == btn_yes:
                    pass 
                elif clicked == btn_rename:
                    base, ext = os.path.splitext(save_path)
                    counter = 1
                    while os.path.exists(f"{base}({counter}){ext}"):
                        counter += 1
                    save_path = f"{base}({counter}){ext}"
                else: # 취소
                    return

            try:
                with open(save_path, 'w', encoding='utf-8') as f: f.write(content)
                self.toast.show_message("✅ 텍스트 파일이 저장되었습니다!", 2000) # 토스트 사용
            except Exception as e: QMessageBox.critical(self, "오류", f"저장 중 오류가 발생했습니다.\n{e}")

    def remove_line_numbers(self):
        cursor = self.text_editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        full_text = self.text_editor.toPlainText()
        new_text = re.sub(r'(?m)^(\[\d+\]|\d+\.)\s*', '', full_text)
        cursor.insertText(new_text)
        cursor.endEditBlock()

    def run_spell_check(self):
        text = self.text_editor.toPlainText().strip()
        if not text:
             self.toast.show_message("⚠️ 검사할 텍스트가 없습니다.", 2000)
             return

        # 스마트 캐시 확인: 변경된 텍스트가 없으면 이전 결과 바로 띄우기
        if hasattr(self, '_last_spellcheck_original') and hasattr(self, '_last_spellcheck_corrected'):
            if self._last_spellcheck_original == text:
                self.toast.show_message("⚡ 기존 분석 결과를 불러옵니다.", 2000)
                # 이전 캐시 결과로 즉시 다이얼로그 호출 (AI 무시)
                original_text = self.text_editor.toPlainText()
                # 이전 스크롤 위치 기억 (없으면 0)
                vscroll = getattr(self, '_last_spellcheck_vscroll', 0)
                dlg = SpellCheckDialog(original_text, self._last_spellcheck_corrected, self, initial_vscroll=vscroll)
                
                dlg.exec() # 결과 저장 여부와 상관없이 현재 스크롤은 저장
                self._last_spellcheck_vscroll = dlg.edit_new.verticalScrollBar().value()
                
                if dlg.result(): # Accepted
                    self.text_editor.setText(dlg.result_text)
                    self.save_text_content() 
                    self.toast.show_message("✅ 맞춤법 교정이 완료되었습니다!", 2000)
                    self._last_spellcheck_original = None
                    self._last_spellcheck_corrected = None
                    self._last_spellcheck_vscroll = 0
                return

        self.status_container.setVisible(True)
        self.lbl_status.setText("AI가 맞춤법을 검사하고 있습니다...")
        self.progress_bar.setRange(0, 0) 

        self.ai_worker = SpellCheckWorker(text)
        self.ai_worker.finished.connect(self.on_spell_check_finished)
        self.ai_worker.error.connect(self.on_spell_check_error)
        self.ai_worker.start()

    def on_spell_check_finished(self, corrected_text):
        self.status_container.setVisible(False)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(100)

        original_text = self.text_editor.toPlainText()
        
        # 결과 캐시 저장 (새 검사이므로 스크롤은 0부터 시작)
        self._last_spellcheck_original = original_text.strip()
        self._last_spellcheck_corrected = corrected_text
        self._last_spellcheck_vscroll = 0

        dlg = SpellCheckDialog(original_text, corrected_text, self, initial_vscroll=0)
        dlg.exec()
        self._last_spellcheck_vscroll = dlg.edit_new.verticalScrollBar().value()
        
        if dlg.result(): # Accepted
            self.text_editor.setText(dlg.result_text)
            self.save_text_content() 
            self.toast.show_message("✅ 맞춤법 교정이 완료되었습니다!", 2000)
            # 적용 시 캐시 초기화
            self._last_spellcheck_original = None
            self._last_spellcheck_corrected = None
            self._last_spellcheck_vscroll = 0

    def on_spell_check_error(self, err_msg):
         self.status_container.setVisible(False)
         QMessageBox.critical(self, "오류", err_msg)

    def toggle_sidebar(self):
        width = self.sidebar.width()
        
        if width > 100: # 접기 (280 -> 50)
            self.sidebar_anim.setStartValue(280)
            self.sidebar_anim.setEndValue(50)

            self.btn_toggle.setToolTip("사이드바 열기")
            
            # 제목과 본문만 숨깁니다.
            self.title_container.hide() 
            self.sidebar_body.hide()
            
            # [추가] 접히는 순간에도 버튼을 강제로 보여주고 맨 위로 올립니다.
            self.btn_toggle.show()
            self.btn_toggle.raise_()
        else: # 펼치기 (50 -> 280)
            self.sidebar_anim.setStartValue(50)
            self.sidebar_anim.setEndValue(280)

            self.btn_toggle.setToolTip("사이드바 닫기")

            self.title_container.show()
            self.sidebar_body.show()
            
        self.sidebar_anim.start()


if __name__ == "__main__":
    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.Round)
    app = QApplication(sys.argv)
    
    # [추가] 메뉴 및 드롭다운 애니메이션 효과 끄기 (즉시 표시)
    app.setEffectEnabled(Qt.UI_AnimateMenu, False)
    app.setEffectEnabled(Qt.UI_AnimateCombo, False)
    app.setEffectEnabled(Qt.UI_AnimateTooltip, False) # 툴팁도 즉시 나타나게 함
    
    app.setFont(QFont("Pretendard", 10))
    
    app.setStyle("Fusion")

    # 툴팁 배경 버그 해결을 위한 팔레트 강제 설정

    palette = app.palette()
    tooltip_bg = QColor("#2D3748") # 진한 회색
    tooltip_fg = QColor("white")   # 흰색 글자
    
    # 모든 그룹(Active, Inactive, Disabled)에 대해 배경/글자색 지정
    palette.setColor(QPalette.All, QPalette.ToolTipBase, tooltip_bg)
    palette.setColor(QPalette.All, QPalette.ToolTipText, tooltip_fg)
    app.setPalette(palette)
    
    font_filename = "Pretendard.ttf"
    font_path = os.path.join(ASSETS_DIR, font_filename)
    font_id = QFontDatabase.addApplicationFont(font_path)
    
    if font_id != -1:
        font_family = QFontDatabase.applicationFontFamilies(font_id)[0]
        font = QFont(font_family, 11) 
    else:
        font = QFont("sans-serif", 10)
    
    font.setStyleStrategy(QFont.PreferAntialias) 
    font.setHintingPreference(QFont.PreferNoHinting)
    app.setFont(font)

    TOOLTIP_STYLE = """
        QToolTip {
        background: #2D3748; 
        color: white;
        border: 1px solid #FFFFFF; 
        border-radius: 4px;
        padding: 3px 8px;
        font-family: 'Pretendard';
        font-size: 13px;
    }
"""
    app.setStyleSheet(MODERN_STYLE + "\n" + TOOLTIP_STYLE)
    
    window = WebtoonManager()
    window.show()
    sys.exit(app.exec())