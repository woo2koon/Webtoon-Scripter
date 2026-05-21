# widgets/dialogs.py
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
    QInputDialog, QMessageBox, QAbstractItemView, QApplication, QStackedWidget,
    QFileDialog, QCheckBox, QMenu, QScrollArea, QGraphicsOpacityEffect, QTextEdit
)
from PySide6.QtCore import Qt, Signal, QPoint, QSize, QMimeData, QByteArray, QTimer, QEvent
from PySide6.QtGui import (
    QPixmap, QIcon, QDrag, QPainter, QColor, QPen, QFont, QAction, QKeySequence,
    QTextCharFormat, QTextFormat, QTextCursor
)

import config
from config import PROJECTS_DIR
from utils import get_icon, get_colored_icon, open_path
from .common import PopupItemDelegate, SingleClickLineEdit
from .character import GlobalCharacterSettingsDialog

# =================================================================
# API 키 프리셋 관리 다이얼로그 (SettingsDialog)
# =================================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 키 프리셋 관리")
        self.setFixedWidth(550)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        self.local_presets = config.API_PRESETS.copy()
        self.local_active = config.ACTIVE_PRESET_NAME
        self.is_unified = False
        
        self.init_ui()
    
    SVG_EYE_OPEN = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>"""
    SVG_EYE_CLOSE = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>"""
    SVG_CHEVRON_DOWN = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 9l6 6 6-6"/></svg>"""
    SVG_CHEVRON_UP = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M18 15l-6-6-6 6"/></svg>"""

    def get_svg_icon(self, svg_data):
        """SVG 데이터를 QIcon으로 변환하는 헬퍼 함수"""
        pixmap = QPixmap()
        pixmap.loadFromData(svg_data)
        return QIcon(pixmap)
    
    def toggle_password_visibility(self, line_edit, button):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_CLOSE))
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))

    def init_ui(self):
        layout = QVBoxLayout(self)
        self.setStyleSheet("")
        layout.setContentsMargins(25, 20, 25, 30) 
        layout.setSpacing(12) 

        preset_group = QVBoxLayout()
        preset_group.setContentsMargins(0, 0, 0, 0)
        preset_group.setSpacing(8)
        
        preset_header = QWidget()
        preset_header_layout = QHBoxLayout(preset_header)
        preset_header_layout.setContentsMargins(0, 5, 0, 0) 
        preset_header_layout.setSpacing(4) 

        icon_preset = QLabel()
        icon_preset.setPixmap(get_icon(config.ICON_KEY).pixmap(18, 18))

        lbl_preset = QLabel("프리셋 선택")
        lbl_preset.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")

        preset_header_layout.addWidget(icon_preset)
        preset_header_layout.addWidget(lbl_preset)
        preset_header_layout.addStretch()

        preset_group.addWidget(preset_header)

        row_preset = QHBoxLayout()
        self.combo_presets = QComboBox()
        self.combo_presets.setObjectName("PresetCombo")
        self.combo_presets.setFixedHeight(33)

        self.combo_presets.setView(QListView()) 
        self.combo_presets.setItemDelegate(PopupItemDelegate())

        self.combo_presets.view().window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.combo_presets.view().window().setAttribute(Qt.WA_TranslucentBackground)

        self.combo_presets.setStyleSheet("""
            QComboBox#PresetCombo {
                combobox-popup: 0;
                border: 1px solid #ccc;
                border-radius: 4px;
                padding-left: 10px;
                background: white;
                min-height: 33px;
                max-height: 33px;
                height: 33px;
            }
            QComboBox QAbstractItemView {
                border: 1px solid #ddd;
                border-radius: 8px;
                background-color: white;
                outline: 0;
                padding: 2px;
            }
            QComboBox QAbstractItemView::item {
                font-family: 'Pretendard';
                min-height: 30px;
                padding: 5px;
                margin: 1px;
                border-radius: 5px;
            }
        """)

        self.combo_presets.addItems(list(self.local_presets.keys()))
        self.combo_presets.setCurrentText(self.local_active)
        self.combo_presets.currentTextChanged.connect(self.on_preset_changed)
        
        btn_add = QPushButton("추가")
        btn_add.setFixedSize(60, 33)
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(self.add_preset)
        
        btn_del = QPushButton("삭제")
        btn_del.setFixedSize(60, 33)
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(self.delete_preset)
        
        row_preset.addWidget(self.combo_presets)
        row_preset.addWidget(btn_add)
        row_preset.addWidget(btn_del)
        preset_group.addLayout(row_preset)
        
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #ddd; margin: 0px;") 
        preset_group.addWidget(line)
        
        layout.addLayout(preset_group)

        keys_layout = QVBoxLayout()
        
        lbl_ocr = QLabel("Google Cloud API 키 (Vision + Gemini)")
        lbl_ocr.setStyleSheet("font-weight: bold; color: #555;")
        
        row_ocr_input = QHBoxLayout()
        self.input_ocr = QLineEdit()
        self.input_ocr.setPlaceholderText("Google Cloud API Key")
        self.input_ocr.setEchoMode(QLineEdit.Password)
        self.input_ocr.setFixedHeight(36)
        self.input_ocr.textChanged.connect(self.save_temp_data)
        
        self.btn_toggle_ocr = QPushButton()
        self.btn_toggle_ocr.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))
        self.btn_toggle_ocr.setIconSize(QSize(20, 20))
        self.btn_toggle_ocr.setFixedSize(40, 36)
        self.btn_toggle_ocr.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_ocr.setStyleSheet("""
            QPushButton { border: none; background: transparent; }
            QPushButton:hover { background-color: #f0f0f0; border-radius: 4px; }
        """)
        self.btn_toggle_ocr.clicked.connect(lambda: self.toggle_password_visibility(self.input_ocr, self.btn_toggle_ocr))
        
        row_ocr_input.addWidget(self.input_ocr)
        row_ocr_input.addWidget(self.btn_toggle_ocr)
        
        keys_layout.addWidget(lbl_ocr)
        keys_layout.addLayout(row_ocr_input)
        keys_layout.addSpacing(5)
        
        self.btn_toggle_advanced = QPushButton("Google AI Studio API 키 별도 설정 (선택 사항)")
        self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_DOWN))
        self.btn_toggle_advanced.setIconSize(QSize(12, 12))
        self.btn_toggle_advanced.setStyleSheet("""
            QPushButton {
                text-align: left;
                color: #666;
                background: transparent;
                border: none;
                font-size: 13px;
                padding: 5px 0;
            }
            QPushButton:hover { color: #333; font-weight: bold; }
        """)
        self.btn_toggle_advanced.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_advanced.setToolTip("Google AI Studio에서 발급받은 API 키를 별도로 설정할 수 있습니다.\n설정 시 맞춤법 검사 용도로 사용됩니다.")
        self.btn_toggle_advanced.clicked.connect(self.toggle_advanced_mode)
        keys_layout.addWidget(self.btn_toggle_advanced)
        
        keys_layout.addSpacing(5)

        self.ai_container = QWidget()
        ai_layout = QVBoxLayout(self.ai_container)
        ai_layout.setContentsMargins(0, 5, 0, 5)
        ai_layout.setSpacing(8)

        lbl_ai = QLabel("Google AI Studio API 키 (맞춤법 전용)")
        lbl_ai.setStyleSheet("font-weight: bold; color: #2ecc71;")
        
        row_ai_input = QHBoxLayout()
        self.input_ai = QLineEdit()
        self.input_ai.setPlaceholderText("Google AI Studio API Key")
        self.input_ai.setEchoMode(QLineEdit.Password)
        self.input_ai.setFixedHeight(36)
        self.input_ai.textChanged.connect(self.save_temp_data)
        
        self.input_ocr.textChanged.connect(self.sync_keys)
        
        self.btn_toggle_ai = QPushButton()
        self.btn_toggle_ai.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))
        self.btn_toggle_ai.setIconSize(QSize(20, 20))
        self.btn_toggle_ai.setFixedSize(40, 36)
        self.btn_toggle_ai.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_ai.setStyleSheet("""
            QPushButton { border: none; background: transparent; }
            QPushButton:hover { background-color: #f0f0f0; border-radius: 4px; }
        """)
        self.btn_toggle_ai.clicked.connect(lambda: self.toggle_password_visibility(self.input_ai, self.btn_toggle_ai))
        
        row_ai_input.addWidget(self.input_ai)
        row_ai_input.addWidget(self.btn_toggle_ai)
        
        ai_layout.addWidget(lbl_ai)
        ai_layout.addLayout(row_ai_input)
        
        keys_layout.addWidget(self.ai_container)
        
        layout.addLayout(keys_layout)
        
        layout.addSpacing(25)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        btn_save = QPushButton("설정 저장")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedSize(120, 40)
        btn_save.clicked.connect(self.save_final)
        
        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedSize(80, 40)
        btn_cancel.clicked.connect(self.reject)
        
        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_cancel)
        layout.addLayout(btn_layout)

        self.load_preset_to_ui(self.local_active)

    def on_preset_changed(self, text):
        if text:
            self.local_active = text
            self.load_preset_to_ui(text)
 
    def load_preset_to_ui(self, preset_name):
        data = self.local_presets.get(preset_name, {"ocr": "", "ai": "", "unified": True})
        self.is_unified = data.get("unified", True)
        
        self.input_ocr.blockSignals(True)
        self.input_ai.blockSignals(True)
        
        self.input_ocr.setText(data.get("ocr", ""))
        ui_ai = data.get("ui_ai", "")
        if not ui_ai and not self.is_unified:
            ui_ai = data.get("ai", "")
        
        self.input_ai.setText(ui_ai)
        
        self.input_ocr.blockSignals(False)
        self.input_ai.blockSignals(False)
        
        self.set_unified_mode(self.is_unified)

    def toggle_advanced_mode(self):
        self.set_unified_mode(not self.is_unified)

    def set_unified_mode(self, is_unified):
        self.is_unified = is_unified
        self.ai_container.setVisible(not is_unified)

        QApplication.processEvents()
        self.resize(550, self.sizeHint().height())

        if is_unified:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_DOWN))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (선택 사항)")
        else:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_UP))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (닫기)")

        self.save_temp_data()

    def sync_keys(self):
        pass

    def save_temp_data(self):
        if self.local_active:
            ocr_val = self.input_ocr.text().strip()
            text_ai = self.input_ai.text().strip()
            
            actual_ai = ocr_val if self.is_unified else text_ai
            
            self.local_presets[self.local_active] = {
                "ocr": ocr_val,
                "ai": actual_ai,
                "ui_ai": text_ai,
                "unified": self.is_unified
            }

    def add_preset(self):
        text, ok = QInputDialog.getText(self, "프리셋 추가", "새 프리셋 이름:")
        if ok and text:
            name = text.strip()
            if name in self.local_presets:
                QMessageBox.warning(self, "중복", "이미 존재하는 이름입니다.")
                return
            self.local_presets[name] = {"ocr": "", "ai": ""}
            self.combo_presets.addItem(name)
            self.combo_presets.setCurrentText(name)
            self.input_ocr.setFocus()

    def delete_preset(self):
        if len(self.local_presets) <= 1:
            QMessageBox.warning(self, "알림", "최소 하나의 프리셋은 있어야 합니다.")
            return
        current = self.combo_presets.currentText()
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("삭제 확인")
        msg_box.setText(f"'{current}' 프리셋을 삭제하시겠습니까?")
        msg_box.setIcon(QMessageBox.Question)
        btn_yes = msg_box.addButton("예", QMessageBox.YesRole)
        btn_no = msg_box.addButton("아니오", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_yes:
            del self.local_presets[current]
            self.combo_presets.removeItem(self.combo_presets.currentIndex())

    def save_final(self):
        config.save_settings(self.local_presets, self.local_active)
        QMessageBox.information(self, "저장 완료", f"'{self.local_active}' 프리셋이 적용되었습니다.")
        self.accept()

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
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 3, 10, 3)
        layout.setSpacing(8)
        
        self.lbl_handle = QLabel("☰")
        self.lbl_handle.setFixedWidth(30)
        self.lbl_handle.setAlignment(Qt.AlignCenter)
        self.lbl_handle.setStyleSheet("""
            QLabel {
                color: #9ca3af; 
                font-size: 16px; 
                font-weight: bold;
                border: none;
                background: transparent;
            }
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
        self.lbl_text.setStyleSheet("font-size: 14px; color: #1f2937; border: none; background: transparent;")
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
        self.lbl_key.setStyleSheet("color: #4b5563; font-weight: bold; font-size: 12px; border: none; background: transparent;")
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
        
        self.overlay = DropOverlay(self.viewport())

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.overlay.setGeometry(self.viewport().rect())

    def startDrag(self, supportedActions):
        self.drag_src_row = self.currentRow()
        if self.drag_src_row < 0:
            return
            
        item = self.currentItem()
        if not item:
            return
            
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
        
        target_pos = event.position().toPoint()
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
        
        target_pos = event.position().toPoint()
        hover_item = self.itemAt(target_pos)
        
        N = self.count()
        if N == 0:
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
            
        event.accept()

# =================================================================
# 관용구 설정 다이얼로그 (IdiomSettingsDialog)
# =================================================================
class IdiomSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관용구(지문) 설정")
        self.setFixedSize(520, 500)
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        self.local_idioms = [item.copy() for item in config.IDIOMS]
        
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        
        lbl_title = QLabel("자주 사용하는 괄호 지문과 단축키를 관리하세요.")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937;")
        header_layout.addWidget(lbl_title)

        lbl_desc = QLabel(f"{config.MODIFIER_NAME} + [키]를 누르면 해당 지문이 즉시 입력됩니다.")
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 13px;")
        header_layout.addWidget(lbl_desc)
        
        layout.addLayout(header_layout)

        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 5, 0, 5)
        input_layout.setSpacing(8)

        self.input_text = QLineEdit()
        self.input_text.setObjectName("IdiomInputText")
        self.input_text.setPlaceholderText("예: (속)") 
        self.input_text.setFixedHeight(33) 
        self.input_text.setStyleSheet("""
            QLineEdit#IdiomInputText {
                min-height: 33px;
                max-height: 33px;
                height: 33px;
                border-radius: 6px;
            }
        """)
        
        btn_add = QPushButton("추가")
        btn_add.setFixedSize(70, 33) 
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 3px;
                font-weight: bold;
                padding: 0px;
                text-align: center;
                min-height: 33px;
                max-height: 33px;
                height: 33px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """)
        btn_add.clicked.connect(self.add_idiom)

        input_layout.addWidget(self.input_text, 1)
        input_layout.addWidget(btn_add)
        layout.addLayout(input_layout)

        self.scroll_container = QFrame()
        self.scroll_container.setStyleSheet("""
            QFrame { border: 1px solid #e5e7eb; border-radius: 8px; background-color: #f9fafb; }
        """)
        container_layout = QVBoxLayout(self.scroll_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(35)
        self.header_widget.setStyleSheet("""
            QWidget { background-color: #f3f4f6; border: none; border-bottom: 1px solid #e5e7eb; border-top-left-radius: 7px; border-top-right-radius: 7px; }
        """)
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
            lbl.setStyleSheet("color: #4b5563; font-size: 11px; font-weight: bold; border: none;")
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
            QListWidget {
                background-color: transparent;
                border: none;
                outline: none;
                padding: 0px;
                margin: 0px;
            }
            QListWidget::item {
                background-color: transparent;
                border: none;
                padding: 0px;
            }
            QListWidget::item:selected {
                background-color: transparent;
            }
            QListWidget::drop-indicator {
                background-color: #FF5722;
                height: 3px;
            }
            QScrollBar:vertical { 
                border: none; background: transparent; width: 12px; margin: 0;
            }
            QScrollBar::handle:vertical { 
                background: #d1d5db; border-radius: 6px; min-height: 20px; margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #9ca3af; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        container_layout.addWidget(self.list_widget)
        layout.addWidget(self.scroll_container)

        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        btn_save = QPushButton("설정 저장")
        btn_save.setFixedSize(110, 28)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                min-height: 28px;
                max-height: 28px;
                height: 28px;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """)
        btn_save.clicked.connect(self.save_and_close)
        
        btn_close = QPushButton("닫기")
        btn_close.setFixedSize(80, 28)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #ffffff;
                color: #4b5563;
                border: 1px solid #d1d5db;
                border-radius: 4px;
                font-weight: bold;
                min-height: 28px;
                max-height: 28px;
                height: 28px;
            }
            QPushButton:hover {
                border-color: #FF5722;
                color: #FF5722;
                background-color: #fff9f7;
            }
        """)
        btn_close.clicked.connect(self.reject)
        
        bottom_layout.addWidget(btn_save)
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)

    def refresh_list(self):
        self.list_widget.clear()
        for i, idiom in enumerate(self.local_idioms):
            item = QListWidgetItem(self.list_widget)
            item.setSizeHint(QSize(0, 45))
            card = IdiomCard(idiom, i, self)
            card.delete_signal.connect(self.delete_idiom_by_data)
            self.list_widget.setItemWidget(item, card)

    def delete_idiom_by_data(self, data):
        if data in self.local_idioms:
            self.local_idioms.remove(data)
            self.refresh_list()

    def add_idiom(self):
        text = self.input_text.text().strip()
        if not text:
            QMessageBox.warning(self, "알림", "내용을 입력해주세요.")
            return

        self.local_idioms.append({"text": text, "key": ""})
        self.input_text.clear()
        self.refresh_list()

    def move_idiom(self, src, dst):
        if src >= 0 and dst >= 0 and src < len(self.local_idioms) and dst < len(self.local_idioms):
            item = self.local_idioms.pop(src)
            self.local_idioms.insert(dst, item)
            self.refresh_list()

    def save_and_close(self):
        for index, item in enumerate(self.local_idioms):
            if index < 9:
                item["key"] = str(index + 1)
            elif index == 9:
                item["key"] = "0"
            else:
                item["key"] = ""
        config.IDIOMS = self.local_idioms
        config.save_settings(config.API_PRESETS, config.ACTIVE_PRESET_NAME)
        self.accept()

# =================================================================
# 관용구 플로팅 뷰어 (FloatingIdiomViewer)
# =================================================================
class FloatingIdiomViewer(QDialog):
    idiom_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관용구 도우미")
        self.setWindowFlags(Qt.Tool | Qt.WindowCloseButtonHint)
        self.setMinimumSize(300, 450)
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

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
        layout.addWidget(self.search_bar)

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
        layout.addWidget(self.list_widget)

        lbl_info = QLabel(f"💡 단축키({config.MODIFIER_NAME}+키) 혹은 더블 클릭하면 자동 삽입됩니다.")
        lbl_info.setStyleSheet("color: #6B7280; font-size: 11px; font-family: 'Pretendard';")
        layout.addWidget(lbl_info)

    def refresh_list(self):
        self.list_widget.clear()
        for item in config.IDIOMS:
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 50))
            
            container = QWidget()
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
        
        def get_granular_segments(org, new, tag_type):
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

        cursor_org.beginEditBlock()
        cursor_new.beginEditBlock()

        for idx, (tag, i1, i2, j1, j2) in enumerate(opcodes):
            org_full = text1[i1:i2]
            new_full = text2[j1:j2]
            segments = get_granular_segments(org_full, new_full, tag)

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
                        fmt_new.setFontStrikeOut(True)
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
            revert_cursor = self.edit_new.textCursor()
            revert_cursor.setPosition(start_pos)
            revert_cursor.setPosition(end_pos, QTextCursor.KeepAnchor)
            revert_cursor.beginEditBlock()
            revert_cursor.insertText(item["org"], QTextCharFormat())
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

        self.lbl_name = QLabel(name)
        self.lbl_name.setFont(QFont("Pretendard", 15))
        self.lbl_name.setStyleSheet("font-weight: bold; font-size: 15px; color: #374151; background: transparent;")
        
        self.lbl_status = QLabel(status)
        self.lbl_status.setFixedSize(80, 26)
        self.lbl_status.setAlignment(Qt.AlignCenter)
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
            self.lbl_name.setStyleSheet("font-weight: bold; font-size: 15px; color: #0369A1; background: transparent; font-family: 'Pretendard';")
        else:
            self.container.setStyleSheet("""
                QFrame#itemContainer {
                    background-color: #F9FAFB;
                    border: 1px solid #D1D5DB;
                    border-radius: 10px;
                }
            """)
            self.lbl_name.setStyleSheet("font-weight: bold; font-size: 15px; color: #374151; background: transparent; font-family: 'Pretendard';")

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
                font-weight: bold;
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
        lbl_lib_text.setStyleSheet("font-weight: bold; font-size: 15px; color: #111827; font-family: 'Pretendard';")

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
        self.list_titles.setFont(QFont("Pretendard", 10))
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
        lbl_epi_text.setStyleSheet("font-weight: bold; font-size: 15px; color: #111827; font-family: 'Pretendard';")

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
                QMessageBox.warning(self, "중복", "이미 존재하는 작품 이름입니다.")
                return
            os.makedirs(path, exist_ok=True)
            self.refresh_projects()

    def delete_title(self):
        current_item = self.list_titles.currentItem()
        if not current_item:
            return

        title = current_item.text()
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("작품 삭제")
        msg_box.setText(f"⚠️ '{title}'의 모든 데이터가 영구 삭제됩니다.\n정말로 진행하시겠습니까?")
        msg_box.setIcon(QMessageBox.Warning)
        btn_yes = msg_box.addButton("예", QMessageBox.YesRole)
        btn_no = msg_box.addButton("아니오", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_yes:
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
                QMessageBox.critical(self, "삭제 오류", f"삭제 중 오류 발생:\n{e}")

    def add_episode(self):
        title_item = self.list_titles.currentItem()
        if not title_item: return
        
        title = title_item.text()
        name, ok = QInputDialog.getText(self, "회차 추가", f"[{title}]의 새로운 회차 이름:")
        if ok and name.strip():
            path = os.path.join(PROJECTS_DIR, title, name.strip(), "images")
            if os.path.exists(os.path.join(PROJECTS_DIR, title, name.strip())):
                QMessageBox.warning(self, "중복", "이미 존재하는 회차입니다.")
                return
            os.makedirs(path, exist_ok=True)
            self.load_episodes(title)

    def show_project_context_menu(self, pos):
        item = self.list_titles.itemAt(pos)
        if not item: return
        
        project_name = item.text()
        
        menu = QMenu(self)
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

        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("회차 삭제")
        msg_box.setText(msg)
        msg_box.setIcon(QMessageBox.Warning)
        btn_yes = msg_box.addButton("예", QMessageBox.YesRole)
        btn_no = msg_box.addButton("아니오", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        
        if msg_box.clickedButton() == btn_yes:
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
                QMessageBox.warning(self, "삭제 완료", f"{count}개 중 {success_count}개 삭제 완료 (일부 실패)")

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
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("파일 중복 확인")
                msg_box.setText(f"'{os.path.basename(single_save_path)}' 파일이 이미 존재합니다.")
                msg_box.setInformativeText("기존 파일을 대체할까요, 아니면 새 이름으로 저장할까요?")
                
                btn_yes = msg_box.addButton("덮어쓰기", QMessageBox.ActionRole)
                btn_rename = msg_box.addButton("새 이름으로 저장", QMessageBox.ActionRole)
                btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
                
                msg_box.setDefaultButton(btn_rename)
                msg_box.exec()
                clicked = msg_box.clickedButton()
                
                if clicked == btn_yes:
                    pass 
                elif clicked == btn_rename:
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
                        msg_box = QMessageBox(self)
                        msg_box.setWindowTitle("파일 중복 확인")
                        msg_box.setText(f"파일이 이미 존재합니다:\n{dest_filename}")
                        msg_box.setInformativeText("어떻게 처리할까요?")
                        
                        cb_apply_all = QCheckBox("이후 모든 중복 파일에 동일하게 적용")
                        msg_box.setCheckBox(cb_apply_all)
                        
                        btn_yes = msg_box.addButton("덮어쓰기", QMessageBox.YesRole)
                        btn_rename = msg_box.addButton("새 이름으로 저장", QMessageBox.ActionRole)
                        btn_no = msg_box.addButton("건너뛰기", QMessageBox.NoRole)
                        btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
                        msg_box.setDefaultButton(btn_rename)
                        
                        msg_box.exec()
                        clicked = msg_box.clickedButton()
                        is_checked = cb_apply_all.isChecked()
                        
                        if clicked == btn_yes:
                            if is_checked: overwrite_all = True
                        elif clicked == btn_rename:
                            if is_checked: auto_rename = True
                            dest_path = get_unique_path(dest_path)
                        elif clicked == btn_no:
                            if is_checked: skip_all = True
                            continue
                        elif clicked == btn_cancel:
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
            QMessageBox.warning(self, "저장 완료 (일부 실패)", f"{len(selected_items)}개 중 {success_count}개 저장 성공\n(일부 파일 저장에 실패했습니다.)")

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
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("파일 중복 확인")
                msg_box.setText(f"'{os.path.basename(single_save_path)}' 파일이 이미 존재합니다.")
                msg_box.setInformativeText("기존 파일을 대체할까요, 아니면 새 이름으로 저장할까요?")
                
                btn_yes = msg_box.addButton("덮어쓰기", QMessageBox.ActionRole)
                btn_rename = msg_box.addButton("새 이름으로 저장", QMessageBox.ActionRole)
                btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
                
                msg_box.setDefaultButton(btn_rename)
                msg_box.exec()
                clicked = msg_box.clickedButton()
                
                if clicked == btn_yes:
                    pass 
                elif clicked == btn_rename:
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
                        msg_box = QMessageBox(self)
                        msg_box.setWindowTitle("파일 중복 확인")
                        msg_box.setText(f"파일이 이미 존재합니다:\n{os.path.basename(dest_path)}")
                        msg_box.setInformativeText("어떻게 처리할까요?")
                        
                        cb_apply_all = QCheckBox("이후 모든 중복 파일에 동일하게 적용")
                        msg_box.setCheckBox(cb_apply_all)
                        
                        btn_yes = msg_box.addButton("덮어쓰기", QMessageBox.YesRole)
                        btn_rename = msg_box.addButton("새 이름으로 저장", QMessageBox.ActionRole)
                        btn_no = msg_box.addButton("건너뛰기", QMessageBox.NoRole)
                        btn_cancel = msg_box.addButton("취소", QMessageBox.RejectRole)
                        msg_box.setDefaultButton(btn_rename)
                        
                        msg_box.exec()
                        clicked = msg_box.clickedButton()
                        is_checked = cb_apply_all.isChecked()
                        
                        if clicked == btn_yes:
                            if is_checked: overwrite_all = True
                        elif clicked == btn_rename:
                            if is_checked: auto_rename = True
                            dest_path = get_unique_path(dest_path)
                        elif clicked == btn_no:
                            if is_checked: skip_all = True
                            continue
                        elif clicked == btn_cancel:
                            break
                
                if excel_handler.save_episode_to_excel_final(self, epi_dir, title, epi_name, dest_path):
                    success_count += 1

        if count > 1:
            if success_count == count:
                if hasattr(self.parent(), 'toast'):
                    self.parent().toast.show_message(f"📊 {success_count}개의 엑셀 파일 저장 완료")
            else:
                QMessageBox.warning(self, "저장 완료 (일부 실패)", f"{count}개 중 {success_count}개 저장 성공\n(일부 파일 저장에 실패했습니다.)")
