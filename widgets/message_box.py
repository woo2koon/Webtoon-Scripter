# widgets/message_box.py
import sys
import platform
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame, QApplication
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QFont, QIcon, QPixmap

import config
from utils import get_colored_pixmap

class CustomMessageBox(QDialog):
    # QMessageBox 대체를 위한 버튼 역할 상수 모사
    Yes = 0x00004000
    No = 0x00010000
    Ok = 0x00000400
    Cancel = 0x00400000
    
    Warning = "warning"
    Information = "information"
    Question = "question"
    Critical = "critical"

    def __init__(self, parent=None, title="알림", text="", icon_type="information", buttons=None, checkbox_text=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        self.setWindowTitle(title)
        self.setMinimumWidth(420)
        self.setMaximumWidth(580)
        
        # OS별 알림음 재생
        try:
            if sys.platform == "win32":
                import ctypes
                # MB_ICONERROR = 0x10, MB_ICONQUESTION = 0x20, MB_ICONWARNING = 0x30, MB_ICONINFORMATION = 0x40
                sound_type = 0x40 # 기본 정보음
                if icon_type == "warning":
                    sound_type = 0x30
                elif icon_type == "critical":
                    sound_type = 0x10
                elif icon_type == "question":
                    sound_type = 0x20
                ctypes.windll.user32.MessageBeep(sound_type)
            else:
                QApplication.beep()
        except Exception as e:
            print(f"Error playing system alert sound: {e}")
            
        self.result_button = CustomMessageBox.Cancel
        app_ff = QApplication.font().family() or 'Pretendard'
        
        # 기본 팝업 백그라운드 및 다이얼로그 폰트 지정
        self.setFont(QApplication.font())
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #ffffff;
            }}
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setSizeConstraint(QVBoxLayout.SetFixedSize)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(20)
        
        # 컨텐츠 영역 (아이콘 + 텍스트)
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # 1. 아이콘 생성
        icon_label = QLabel()
        icon_label.setFixedSize(42, 42)
        icon_label.setAlignment(Qt.AlignCenter)
        
        # 유형에 맞는 SVG 아이콘 매핑
        icon_path = ""
        icon_color = "#3B82F6" # Default info blue
        if icon_type == "warning":
            icon_path = config.ICON_WARNING
            icon_color = "#F59E0B" # Amber
        elif icon_type == "question":
            icon_path = config.ICON_INFO
            icon_color = "#3B82F6" # Blue
        elif icon_type == "critical":
            icon_path = config.ICON_WARNING
            icon_color = "#EF4444" # Red
        else: # info
            icon_path = config.ICON_INFO
            icon_color = "#10B981" # Green
            
        try:
            pixmap = get_colored_pixmap(icon_path, icon_color, 42, 42)
            icon_label.setPixmap(pixmap)
        except Exception as e:
            print(f"Error loading message box icon: {e}")
            
        content_layout.addWidget(icon_label, 0, Qt.AlignTop)
        
        # 2. 텍스트 라벨
        text_label = QLabel(text)
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        text_label.setStyleSheet(f"""
            QLabel {{
                font-family: '{app_ff}';
                font-size: 14px;
                color: #374151;
                background: transparent;
                border: none;
                padding: 4px 0px;
            }}
        """)
        content_layout.addWidget(text_label, 1)
        main_layout.addLayout(content_layout)
        
        # 2.5 체크박스 (있을 경우 추가)
        self.checkbox = None
        if checkbox_text:
            from PySide6.QtWidgets import QCheckBox
            self.checkbox = QCheckBox(checkbox_text)
            self.checkbox.setStyleSheet(f"""
                QCheckBox {{
                    font-family: '{app_ff}';
                    font-size: 13px;
                    color: #4B5563;
                    margin-left: 57px;
                }}
            """)
            main_layout.addWidget(self.checkbox)
            
        # 3. 하단 버튼 영역
        buttons_layout = QHBoxLayout()
        buttons_layout.setSpacing(8)
        buttons_layout.addStretch()
        
        button_style = f"""
            QPushButton {{
                min-width: 80px;
                padding: 8px 16px;
                border-radius: 6px;
                font-family: '{app_ff}';
                font-size: 15px;
                font-weight: bold;
            }}
            QPushButton#PrimaryBtn {{
                background-color: #FF5722;
                color: white;
                border: none;
            }}
            QPushButton#PrimaryBtn:hover {{
                background-color: #E64A19;
            }}
            QPushButton#SecondaryBtn {{
                background-color: white;
                border: 1px solid #D1D5DB;
                color: #4B5563;
            }}
            QPushButton#SecondaryBtn:hover {{
                border-color: #FF5722;
                color: #FF5722;
                background-color: #FFF9F7;
            }}
        """
        
        if not buttons:
            buttons = [CustomMessageBox.Ok]
            
        for btn_type in buttons:
            if btn_type == CustomMessageBox.Ok:
                btn = QPushButton("확인")
                btn.setObjectName("PrimaryBtn")
                btn.clicked.connect(lambda: self.on_button_clicked(CustomMessageBox.Ok))
            elif btn_type == CustomMessageBox.Yes:
                btn = QPushButton("예")
                btn.setObjectName("PrimaryBtn")
                btn.clicked.connect(lambda: self.on_button_clicked(CustomMessageBox.Yes))
            elif btn_type == CustomMessageBox.No:
                btn = QPushButton("아니오")
                btn.setObjectName("SecondaryBtn")
                btn.clicked.connect(lambda: self.on_button_clicked(CustomMessageBox.No))
            elif btn_type == CustomMessageBox.Cancel:
                btn = QPushButton("취소")
                btn.setObjectName("SecondaryBtn")
                btn.clicked.connect(lambda: self.on_button_clicked(CustomMessageBox.Cancel))
            else:
                btn = QPushButton(str(btn_type))
                btn.setObjectName("SecondaryBtn")
                btn.clicked.connect(lambda b=btn_type: self.on_button_clicked(b))
                
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet(button_style)
            buttons_layout.addWidget(btn)
            
        main_layout.addLayout(buttons_layout)
        self.adjustSize()
        
    def on_button_clicked(self, role):
        self.result_button = role
        if role in (CustomMessageBox.Ok, CustomMessageBox.Yes):
            self.accept()
        else:
            self.reject()
            
    # --- 정적 모사 메서드들 ---
    @staticmethod
    def information(parent, title, text, buttons=None):
        dlg = CustomMessageBox(parent, title, text, "information", buttons or [CustomMessageBox.Ok])
        dlg.exec()
        return dlg.result_button

    @staticmethod
    def warning(parent, title, text, buttons=None):
        dlg = CustomMessageBox(parent, title, text, "warning", buttons or [CustomMessageBox.Ok])
        dlg.exec()
        return dlg.result_button

    @staticmethod
    def critical(parent, title, text, buttons=None):
        dlg = CustomMessageBox(parent, title, text, "critical", buttons or [CustomMessageBox.Ok])
        dlg.exec()
        return dlg.result_button

    @staticmethod
    def question(parent, title, text, buttons=None, default_button=None):
        # QMessageBox.question 모사용
        if buttons is None:
            buttons = [CustomMessageBox.Yes, CustomMessageBox.No]
        dlg = CustomMessageBox(parent, title, text, "question", buttons)
        dlg.exec()
        return dlg.result_button
