# widgets/character.py
import json
import os
import random
import tempfile
import uuid
import re
import email
from email import policy
import urllib.parse
import base64

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QFrame, QListWidget, QListWidgetItem, QApplication,
    QDialog, QMenu, QFileDialog, QMessageBox, QTabWidget, QGridLayout,
    QScrollArea, QSlider, QToolTip
)
from PySide6.QtCore import Qt, Signal, QMimeData, QPoint, QSize, QRect, QRectF, QByteArray, QEvent
from PySide6.QtGui import (
    QPixmap, QDrag, QPainter, QColor, QPen, QFont, QIcon, QRegion, QAction, QBrush,
    QCursor, QGuiApplication
)
from PySide6.QtSvg import QSvgRenderer

import config
from config import ROLE_OPTIONS, AGE_OPTIONS, GENDER_OPTIONS
from utils import get_icon, get_colored_pixmap
from .common import ClickableComboBox, get_round_rect_pixmap, HoverIconButton, SingleClickLineEdit

# =================================================================
# 👤 SVG 기반 기본 아바타 플레이스홀더 생성 헬퍼
# =================================================================
def get_default_avatar_pixmap(w, h, radius=None, icon_color="#9CA3AF", bg_color="#F3F4F6", border_color="#E5E7EB"):
    """
    SVG 코드 기반의 기본 아바타 플레이스홀더 QPixmap을 동적으로 생성
    """
    if radius is None:
        radius = max(4, min(w, h) // 5)
        
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing, True)
    
    # 배경 및 테두리 그리기
    painter.setPen(QPen(QColor(border_color), 1))
    painter.setBrush(QColor(bg_color))
    painter.drawRoundedRect(QRectF(0.5, 0.5, w - 1, h - 1), radius, radius)
    
    # SVG User 아이콘 렌더링
    svg_content = f"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="{icon_color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>"""
    
    # 아이콘 크기는 아바타 크기의 약 55%
    icon_size = max(16, int(min(w, h) * 0.55))
    x = (w - icon_size) / 2.0
    y = (h - icon_size) / 2.0
    
    try:
        renderer = QSvgRenderer(QByteArray(svg_content.encode('utf-8')))
        renderer.render(painter, QRectF(x, y, icon_size, icon_size))
    except Exception as e:
        print(f"Failed to render default avatar SVG: {e}")
        # 예외 발생 시 간단한 머리/어깨 silhouette 폴백 그리기
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(icon_color))
        # Head
        hw = int(min(w, h) * 0.3)
        painter.drawEllipse(QRectF((w - hw) / 2.0, (h - hw) / 2.0 - hw * 0.5, hw, hw))
        # Shoulders
        from PySide6.QtGui import QPainterPath
        body_path = QPainterPath()
        sw = int(min(w, h) * 0.6)
        sh = int(min(w, h) * 0.3)
        bx = (w - sw) / 2.0
        by = (h + hw) / 2.0 - hw * 0.3
        body_path.moveTo(bx, by + sh)
        body_path.quadTo(bx, by, bx + sw * 0.2, by)
        body_path.lineTo(bx + sw * 0.8, by)
        body_path.quadTo(bx + sw, by, bx + sw, by + sh)
        body_path.closeSubpath()
        painter.drawPath(body_path)
        
    painter.end()
    return pix

# =================================================================
# 캐릭터 목록 드래그 컨테이너 및 핸들
# =================================================================
class CharacterListContainer(QWidget):
    order_changed_signal = Signal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setStyleSheet("background-color: transparent;")
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignTop)
        layout.setSpacing(5)
        layout.setContentsMargins(0, 10, 0, 10)
        self.drop_indicator_y = -1

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-character-row"):
            event.acceptProposedAction()
            
    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-character-row"):
            handle = event.source()
            row_widget = handle.parent() if handle else None
            drop_y = event.pos().y()
            layout = self.layout()
            
            # 드래그 중인 위젯을 제외한 위젯들만 리스트업
            widgets = []
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if w and w != row_widget:
                    widgets.append(w)
            
            found = False
            for w in widgets:
                center_y = w.y() + w.height() / 2.0
                if drop_y < center_y:
                    self.drop_indicator_y = w.y() - layout.spacing() / 2.0
                    found = True
                    break
            
            if not found:
                if len(widgets) > 0:
                    last_w = widgets[-1]
                    self.drop_indicator_y = last_w.y() + last_w.height() + layout.spacing() / 2.0
                else:
                    self.drop_indicator_y = 10
            
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.drop_indicator_y = -1
        self.update()
            
    def dropEvent(self, event):
        self.drop_indicator_y = -1
        self.update()
        if event.mimeData().hasFormat("application/x-character-row"):
            handle = event.source()
            
            # [수정] 외부(예: 글로벌 캐릭터 도우미 플로팅 창)에서 드롭한 경우
            if not handle or not hasattr(handle, "parent") or str(handle.objectName()) != "DragHandle":
                mime_text = event.mimeData().text()
                if mime_text:
                    try:
                        char_info = json.loads(mime_text)
                        mw = self.window()
                        if hasattr(mw, 'add_character_card_at'):
                            layout = self.layout()
                            widgets = []
                            for i in range(layout.count()):
                                w = layout.itemAt(i).widget()
                                if w: widgets.append(w)
                                
                            target_index = len(widgets)
                            for i, w in enumerate(widgets):
                                if event.pos().y() < w.y() + w.height() / 2.0:
                                    target_index = i
                                    break
                                    
                            mw.add_character_card_at(
                                target_index,
                                name=char_info.get("name", ""),
                                age=char_info.get("age", ""),
                                gender=char_info.get("gender", ""),
                                role=char_info.get("role", "")
                            )
                            event.acceptProposedAction()
                    except Exception as e:
                        print(f"외부 캐릭터 드롭 실패: {e}")
                return

            row_widget = handle.parent()
            drop_y = event.pos().y()
            layout = self.layout()
            
            # 드래그 중인 위젯을 제외한 나머지 위젯들 리스트업
            widgets = []
            for i in range(layout.count()):
                w = layout.itemAt(i).widget()
                if w and w != row_widget:
                    widgets.append(w)
            
            # 타겟 인덱스 계산 (어떤 위젯 앞에 놓을 것인가)
            target_index = len(widgets)
            for i, w in enumerate(widgets):
                if drop_y < w.y() + w.height() / 2.0:
                    target_index = i
                    break
            
            layout.removeWidget(row_widget)
            layout.insertWidget(target_index, row_widget)
            
            event.acceptProposedAction()
            self.order_changed_signal.emit()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.drop_indicator_y != -1:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor("#ff4b4b"), 3)
            painter.setPen(pen)
            painter.drawLine(10, self.drop_indicator_y, self.width() - 10, self.drop_indicator_y)

# =================================================================
# 드래그 핸들
# =================================================================
class DragHandle(QLabel):
    def __init__(self, parent=None):
        super().__init__("≡", parent)
        self.setObjectName("DragHandle")
        self.setStyleSheet("""
            QLabel#DragHandle {
                color: #6b7280; 
                font-weight: 900; 
                font-size: 24px; 
                padding: 0 5px;
            }
            QLabel#DragHandle:hover {
                color: #ff4b4b;
            }
        """)
        self.setCursor(Qt.OpenHandCursor)
        self.setFixedWidth(24)
        self.setAlignment(Qt.AlignCenter)
        self.drag_start_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.drag_start_pos = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if not (event.buttons() & Qt.LeftButton) or self.drag_start_pos is None:
            return
        if (event.pos() - self.drag_start_pos).manhattanLength() < QApplication.startDragDistance():
            return
            
        drag = QDrag(self)
        mime_data = QMimeData()
        mime_data.setData("application/x-character-row", b"")
        drag.setMimeData(mime_data)
        
        row_widget = self.parent() 
        pixmap = row_widget.grab()
        drag.setPixmap(pixmap)
        drag.setHotSpot(event.pos() + self.pos())
        
        row_widget.hide()
        drag.exec(Qt.MoveAction)
        row_widget.show()
        
        self.setCursor(Qt.OpenHandCursor)
        
    def mouseReleaseEvent(self, event):
        self.setCursor(Qt.OpenHandCursor)
        super().mouseReleaseEvent(event)

# =================================================================
# 캐릭터 입력 행
# =================================================================
class CharacterRow(QFrame):
    delete_signal = Signal(QWidget)

    def __init__(self, name="", age="", gender="", role="", parent=None):
        super().__init__(parent)
        self.setObjectName("CharacterRow")
        self.setStyleSheet("QFrame#CharacterRow { background-color: transparent; border: none; }")
        
        self.project_name = ""
        if parent:
            mw = parent.window()
            if hasattr(mw, 'current_title'):
                self.project_name = mw.current_title
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) 
        layout.setSpacing(10) 
        WIDGET_HEIGHT = 45 

        BASIC_BOX_STYLE = """
            border: 1px solid #d1d5db; border-radius: 6px; background-color: white; 
            padding-left: 10px; font-family: 'Pretendard', sans-serif; font-size: 14px; color: #333333;
        """
        FOCUS_STYLE = "border: 1px solid #ff4b4b;"
        dropdown_arrow_path = os.path.join(config.ASSETS_DIR, "dropdown-arrow.svg").replace("\\", "/")
        FULL_COMBO_STYLE = f"""
            QComboBox {{ 
                combobox-popup: 0;
                {BASIC_BOX_STYLE} 
            }}
            QComboBox:focus {{ {FOCUS_STYLE} }}
            QComboBox::drop-down {{ 
                border: none; background-color: #f9fafb; width: 30px; 
                border-top-right-radius: 5px; border-bottom-right-radius: 5px; 
            }}
            QComboBox::down-arrow {{ 
                image: url("{dropdown_arrow_path}");
                width: 12px; height: 12px; 
            }}
            QComboBox QAbstractItemView {{ 
                font-family: 'Pretendard'; 
                background-color: white; 
                border: 1px solid #9CA3AF; 
                border-radius: 8px; 
                selection-background-color: #ffecec; 
                selection-color: #ff4b4b; 
                outline: none; 
                padding: 4px; 
            }}
            QComboBox QAbstractItemView::item {{ 
                min-height: 35px; 
                padding: 5px; 
                margin: 2px 0px; 
                border-radius: 4px;
            }}
        """

        self.lbl_drag = DragHandle(self)
        layout.addWidget(self.lbl_drag)

        self.input_name = QLineEdit(name)
        self.input_name.setPlaceholderText("이름")
        self.input_name.setFixedHeight(WIDGET_HEIGHT)
        self.input_name.setStyleSheet(f"QLineEdit {{ {BASIC_BOX_STYLE} }} QLineEdit:focus {{ {FOCUS_STYLE} }}\n" + config.MODERN_MENU_STYLE)
        layout.addWidget(self.input_name, 3)

        self.combo_role = ClickableComboBox()
        self.combo_role.addItems(ROLE_OPTIONS)
        self.combo_role.setFixedHeight(WIDGET_HEIGHT)
        self.combo_role.setStyleSheet(FULL_COMBO_STYLE)
        if role in ROLE_OPTIONS: self.combo_role.setCurrentText(role)
        else: self.combo_role.setCurrentIndex(-1)
        layout.addWidget(self.combo_role, 2)

        self.combo_age = ClickableComboBox()
        self.combo_age.addItems(AGE_OPTIONS)
        self.combo_age.setFixedHeight(WIDGET_HEIGHT)
        self.combo_age.setStyleSheet(FULL_COMBO_STYLE)
        if age in AGE_OPTIONS: self.combo_age.setCurrentText(age)
        else: self.combo_age.setCurrentIndex(-1)
        layout.addWidget(self.combo_age, 2)

        self.combo_gender = ClickableComboBox()
        self.combo_gender.addItems(GENDER_OPTIONS)
        self.combo_gender.setFixedHeight(WIDGET_HEIGHT)
        self.combo_gender.setStyleSheet(FULL_COMBO_STYLE)
        if gender in GENDER_OPTIONS: self.combo_gender.setCurrentText(gender)
        else: self.combo_gender.setCurrentIndex(-1)
        layout.addWidget(self.combo_gender, 2)

        self.btn_register = QPushButton("등록")
        self.btn_register.setFixedSize(65, WIDGET_HEIGHT)
        self.btn_register.setCursor(Qt.PointingHandCursor)
        self.btn_register.setStyleSheet("""
            QPushButton {
                border: none; 
                background-color: #3B82F6; 
                color: white; 
                border-radius: 6px; 
                font-weight: bold; 
                font-size: 15px; 
                font-family: 'Pretendard', sans-serif;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
            QPushButton:disabled {
                background-color: #E5E7EB;
                color: #9CA3AF;
                border: none;
            }
        """)
        self.btn_register.clicked.connect(self.register_character)
        layout.addWidget(self.btn_register)

        self.btn_delete = QPushButton("삭제")
        self.btn_delete.setFixedSize(65, WIDGET_HEIGHT)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet("QPushButton { border: none; background-color: #ff4b4b; color: white; border-radius: 6px; font-weight: bold; font-size: 15px; font-family: 'Pretendard', sans-serif; padding: 0px; } QPushButton:hover { background-color: #e03e3e; }")
        self.btn_delete.clicked.connect(lambda: self.delete_signal.emit(self))
        layout.addWidget(self.btn_delete)

        self.last_valid_name = name.strip()
        self.input_name.textChanged.connect(self.check_registered_status)
        self.input_name.editingFinished.connect(self.validate_name)
        self.check_registered_status()

    def validate_name(self):
        new_name = self.input_name.text().strip()
        if not new_name:
            self.last_valid_name = ""
            return
            
        mw = self.window()
        if mw and hasattr(mw, 'char_layout'):
            duplicate_found = False
            for i in range(mw.char_layout.count()):
                item = mw.char_layout.itemAt(i)
                if item:
                    widget = item.widget()
                    if isinstance(widget, CharacterRow) and widget is not self:
                        if widget.input_name.text().strip() == new_name:
                            duplicate_found = True
                            break
            
            if duplicate_found:
                if hasattr(mw, 'toast'):
                    mw.toast.show_message(f"⚠️ '{new_name}' 캐릭터는 이미 추가되어 있습니다.", 1500)
                else:
                    QMessageBox.warning(self, "중복 경고", f"'{new_name}' 캐릭터는 이미 추가되어 있습니다.")
                
                # Revert text
                self.input_name.blockSignals(True)
                self.input_name.setText(self.last_valid_name)
                self.input_name.blockSignals(False)
                
                # Check registered status again for the reverted text
                self.check_registered_status()
            else:
                self.last_valid_name = new_name

    def check_registered_status(self):
        name = self.input_name.text().strip()
        if not name:
            # 이름이 빈값인 경우 콤보박스 선택 초기화
            self.combo_role.blockSignals(True)
            self.combo_age.blockSignals(True)
            self.combo_gender.blockSignals(True)
            self.combo_role.setCurrentIndex(-1)
            self.combo_age.setCurrentIndex(-1)
            self.combo_gender.setCurrentIndex(-1)
            self.combo_role.blockSignals(False)
            self.combo_age.blockSignals(False)
            self.combo_gender.blockSignals(False)
            
            self.btn_register.setEnabled(False)
            self.btn_register.setText("등록")
            return
            
        if not self.project_name:
            self.btn_register.setEnabled(False)
            self.btn_register.setText("등록")
            return
            
        chars = config.load_global_characters(self.project_name)
        
        # 이름과 일치하는 캐릭터 검색
        match_char = None
        for c in chars:
            if c.get("name", "").strip() == name:
                match_char = c
                break
        
        if match_char:
            self.btn_register.setEnabled(False)
            self.btn_register.setText("등록됨")
            
            # 정보 자동 완성
            role = match_char.get("role", "")
            age = match_char.get("age", "")
            gender = match_char.get("gender", "")
            
            # 콤보박스 자동 설정 (연쇄 신호 발생 차단하여 성능 최적화)
            from config import ROLE_OPTIONS, AGE_OPTIONS, GENDER_OPTIONS
            self.combo_role.blockSignals(True)
            self.combo_age.blockSignals(True)
            self.combo_gender.blockSignals(True)
            
            if role in ROLE_OPTIONS:
                self.combo_role.setCurrentText(role)
            if age in AGE_OPTIONS:
                self.combo_age.setCurrentText(age)
            if gender in GENDER_OPTIONS:
                self.combo_gender.setCurrentText(gender)
                
            self.combo_role.blockSignals(False)
            self.combo_age.blockSignals(False)
            self.combo_gender.blockSignals(False)
        else:
            self.btn_register.setEnabled(True)
            self.btn_register.setText("등록")

    def register_character(self):
        name = self.input_name.text().strip()
        if not name or not self.project_name: return
        
        chars = config.load_global_characters(self.project_name)
        exists = any(c.get("name", "") == name for c in chars)
        if not exists:
            role = self.combo_role.currentText() or "단역"
            age = self.combo_age.currentText() or "미상"
            gender = self.combo_gender.currentText() or "미상"
            
            new_char = {
                "name": name,
                "role": role,
                "age": age,
                "gender": gender,
                "color": "#3B82F6",
                "image_path": "",
                "memo": ""
            }
            chars.append(new_char)
            config.save_global_characters(self.project_name, chars)
            
            self.check_registered_status()
            
            mw = self.window()
            if mw:
                if hasattr(mw, 'get_character_list'):
                    mw.get_character_list()
                if hasattr(mw, 'character_viewer') and mw.character_viewer and mw.character_viewer.isVisible():
                    mw.character_viewer.load_data()
                if hasattr(mw, 'toast'):
                    mw.toast.show_message(f"✅ '{name}' 캐릭터가 정식 등록되었습니다.", 1500)

    def get_data(self):
        return { "Character": self.input_name.text(), "Role": self.combo_role.currentText(), "Age": self.combo_age.currentText(), "Gender": self.combo_gender.currentText() }

# =================================================================
# 드래그 앤 드롭을 지원하는 캐릭터 전용 QListWidget
# =================================================================
class DraggableCharacterListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setDragEnabled(True)
        self.setVerticalScrollMode(QListWidget.ScrollPerItem)
        self._wheel_accumulator = 0
        
    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        scrollbar = self.verticalScrollBar()
        if scrollbar and scrollbar.isVisible():
            self._wheel_accumulator += delta
            steps = 0
            while abs(self._wheel_accumulator) >= 120:
                if self._wheel_accumulator > 0:
                    steps += 1
                    self._wheel_accumulator -= 120
                else:
                    steps -= 1
                    self._wheel_accumulator += 120
            if steps != 0:
                scrollbar.setValue(scrollbar.value() - steps)
            event.accept()
        else:
            super().wheelEvent(event)

    def startDrag(self, supportedActions):
        item = self.currentItem()
        if not item:
            return
            
        char_info = item.data(Qt.UserRole)
        if not char_info:
            return
            
        mime_data = QMimeData()
        mime_data.setData("application/x-character-row", b"")
        mime_data.setText(json.dumps(char_info))
        
        drag = QDrag(self)
        drag.setMimeData(mime_data)
        
        pixmap = QPixmap(120, 36)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        color = QColor(char_info.get("color", "#3B82F6"))
        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, 120, 36, 6, 6)
        
        painter.setPen(QColor("white"))
        font = QFont("Pretendard", 10, QFont.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignCenter, char_info.get("name", "캐릭터"))
        painter.end()
        
        drag.setPixmap(pixmap)
        drag.setHotSpot(QPoint(60, 18))
        
        drag.exec(Qt.MoveAction)

# =================================================================
# 글로벌 캐릭터 설정을 보여주는 리스트형 아이템 카드 위젯
# =================================================================
class GlobalCharacterCard(QWidget):
    delete_clicked = Signal(str)
    edit_clicked = Signal(dict)

    def __init__(self, char_info, parent=None):
        super().__init__(parent)
        self.char_info = char_info
        self.project_name = getattr(parent, 'project_name', '')
        self.init_ui()
        
    def init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(12)
        
        self.setStyleSheet("""
            GlobalCharacterCard {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
        """)
        
        lbl_card_avatar = QLabel()
        lbl_card_avatar.setFixedSize(70, 70)
        lbl_card_avatar.setStyleSheet("border: none; background: transparent;")
        
        img_path = self.char_info.get("image_path", "")
        full_img_path = ""
        if img_path:
            full_img_path = os.path.join(config.PROJECTS_DIR, self.project_name, img_path)
            
        if full_img_path and os.path.exists(full_img_path):
            pix = QPixmap(full_img_path)
            if not pix.isNull():
                lbl_card_avatar.setPixmap(get_round_rect_pixmap(pix, 70, 70, 10))
            else:
                full_img_path = ""
                
        if not full_img_path:
            lbl_card_avatar.setPixmap(get_default_avatar_pixmap(70, 70, 10))
            
        layout.addWidget(lbl_card_avatar)
        
        info_layout = QVBoxLayout()
        info_layout.setSpacing(4)
        info_layout.setContentsMargins(0, 0, 0, 0)
        
        info_layout.addStretch()
        
        name_lbl = QLabel(self.char_info.get('name', ''))
        name_lbl.setStyleSheet("font-size: 17px; font-weight: 600; color: #111827; border: none; background: transparent;")
        info_layout.addWidget(name_lbl)
        
        memo = self.char_info.get('memo', '').strip()
        if memo:
            lbl_memo = QLabel(memo)
            lbl_memo.setStyleSheet("font-size: 12px; font-weight: bold; color: #EF4444; border: none; background: transparent;")
            info_layout.addWidget(lbl_memo)
            
        tags_layout = QHBoxLayout()
        tags_layout.setSpacing(6)
        tags_layout.setContentsMargins(0, 0, 0, 0)
        
        role = self.char_info.get('role', '단역')
        age = self.char_info.get('age', '미상')
        gender = self.char_info.get('gender', '미상')
        
        tag_style = "font-size: 11px; font-weight: 600; border-radius: 4px; padding: 2px 6px; border: 1px solid;"
        
        role_colors = {
            "주연": "background-color: #FEE2E2; color: #EF4444; border-color: #FCA5A5;",
            "조연": "background-color: #FEF3C7; color: #D97706; border-color: #FCD34D;",
            "단역": "background-color: #F3F4F6; color: #4B5563; border-color: #E5E7EB;"
        }
        
        lbl_role = QLabel(role)
        lbl_role.setStyleSheet(tag_style + role_colors.get(role, role_colors["단역"]))
        tags_layout.addWidget(lbl_role)
        
        lbl_age = QLabel(age)
        lbl_age.setStyleSheet(tag_style + "background-color: #E0F2FE; color: #0369A1; border-color: #BAE6FD;")
        tags_layout.addWidget(lbl_age)
        
        lbl_gender = QLabel(gender)
        lbl_gender.setStyleSheet(tag_style + "background-color: #F3E8FF; color: #7E22CE; border-color: #E9D5FF;")
        tags_layout.addWidget(lbl_gender)
        
        tags_layout.addStretch()
        info_layout.addLayout(tags_layout)
        
        info_layout.addStretch()
        
        layout.addLayout(info_layout, 1)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(6)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        
        btn_edit = QPushButton("수정")
        btn_edit.setFixedSize(52, 28)
        btn_edit.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
                color: #374151;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                border-color: #3B82F6;
                color: #3B82F6;
            }
        """)
        btn_edit.clicked.connect(lambda: self.edit_clicked.emit(self.char_info))
        btn_layout.addWidget(btn_edit)
        
        btn_del = QPushButton("삭제")
        btn_del.setFixedSize(52, 28)
        btn_del.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
                color: #EF4444;
                font-weight: bold;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #EF4444;
            }
        """)
        btn_del.clicked.connect(lambda: self.delete_clicked.emit(self.char_info.get("name", "")))
        btn_layout.addWidget(btn_del)
        
        layout.addLayout(btn_layout)

# =================================================================
# 👤 캐릭터 도우미 리스트 아이템 위젯 (CharacterListItemWidget)
# =================================================================
class CharacterListItemWidget(QWidget):
    def __init__(self, char, project_name, avatar_size=44, parent=None):
        super().__init__(parent)
        self.char = char
        self.project_name = project_name
        self.avatar_size = avatar_size
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet("background: transparent; border: none;")
        self.item_layout = QHBoxLayout(self)
        self.item_layout.setContentsMargins(12, 6, 12, 6)
        self.item_layout.setSpacing(12)
        
        self.lbl_item_avatar = QLabel()
        self.lbl_item_avatar.setStyleSheet("border: none; background: transparent;")
        self.item_layout.addWidget(self.lbl_item_avatar, 0, Qt.AlignVCenter)
        
        self.lbl_name = QLabel(self.char.get("name", ""))
        self.lbl_name.setStyleSheet("font-size: 16px; font-weight: 600; color: #1F2937; background: transparent;")
        self.item_layout.addWidget(self.lbl_name, 1, Qt.AlignVCenter)
        
        role = self.char.get("role", "단역")
        self.lbl_role = QLabel(role)
        self.lbl_role.setAlignment(Qt.AlignCenter)
        
        role_colors = {
            "주연": {"bg": "#FEE2E2", "text": "#EF4444", "border": "#FCA5A5"},
            "조연": {"bg": "#FEF3C7", "text": "#D97706", "border": "#FCD34D"},
            "단역": {"bg": "#F3F4F6", "text": "#4B5563", "border": "#E5E7EB"}
        }
        colors = role_colors.get(role, role_colors["단역"])
        
        self.lbl_role.setStyleSheet(f"""
            QLabel {{
                background-color: {colors['bg']};
                color: {colors['text']};
                border: 1px solid {colors['border']};
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: 600;
            }}
        """)
        self.item_layout.addWidget(self.lbl_role, 0, Qt.AlignVCenter)
        
        self.update_avatar(self.avatar_size)
        
    def update_avatar(self, size):
        self.avatar_size = size
        self.lbl_item_avatar.setFixedSize(size, size)
        
        img_path = self.char.get("image_path", "")
        full_img_path = ""
        if img_path:
            full_img_path = os.path.join(config.PROJECTS_DIR, self.project_name, img_path)
            
        if full_img_path and os.path.exists(full_img_path):
            pix = QPixmap(full_img_path)
            if not pix.isNull():
                radius = max(4, size // 5)
                self.lbl_item_avatar.setPixmap(get_round_rect_pixmap(pix, size, size, radius))
            else:
                full_img_path = ""
                
        if not full_img_path:
            radius = max(4, size // 5)
            self.lbl_item_avatar.setPixmap(get_default_avatar_pixmap(size, size, radius))

# =================================================================
# 더블클릭이 가능한 QLabel 서브클래스
# =================================================================
class DoubleClickableLabel(QLabel):
    doubleClicked = Signal()
    
    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        super().mouseDoubleClickEvent(event)

# =================================================================
# 👤 캐릭터 도우미 플로팅 위젯 (FloatingCharacterViewer)
# =================================================================
class FloatingCharacterViewer(QDialog):
    """작품 전체의 캐릭터 목록을 항상 위에 표시하며 드래그 앤 드롭 및 더블클릭 추가를 지원하는 플로팅 위젯"""
    character_selected = Signal(dict) # 캐릭터 선택 시 시그널

    def __init__(self, parent=None, project_name=""):
        super().__init__(parent)
        self.project_name = project_name
        self.avatar_size_all = config.AVATAR_SIZE_ALL
        self.avatar_size_current = config.AVATAR_SIZE_CURRENT
        self.setWindowTitle("👤 캐릭터 도우미")
        import sys
        if sys.platform == "darwin":
            self.setWindowFlags(Qt.Tool | Qt.WindowCloseButtonHint)
        else:
            self.setWindowFlags(Qt.Window | Qt.WindowMinimizeButtonHint | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)
        self.resize(340, 520)
        
        self.init_ui()
        self.load_data()
        
    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 10, 8, 10)
        layout.setSpacing(8)
        
        self.tabs = QTabWidget()
        
        # 탭바 우측 코너에 배치할 줌 컨트롤러 위젯
        zoom_widget = QWidget()
        zoom_widget.setStyleSheet("background: transparent; border: none;")
        zoom_layout = QHBoxLayout(zoom_widget)
        zoom_layout.setContentsMargins(0, 0, 6, 2)
        zoom_layout.setSpacing(3)
        
        btn_style = """
            QPushButton {
                background-color: #F3F4F6;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                color: #374151;
                font-weight: bold;
                font-size: 14px;
                min-width: 24px;
                max-width: 24px;
                min-height: 24px;
                max-height: 24px;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #E5E7EB;
                border-color: #9CA3AF;
            }
            QPushButton:pressed {
                background-color: #D1D5DB;
            }
            QPushButton:disabled {
                background-color: #F9FAFB;
                color: #D1D5DB;
                border-color: #E5E7EB;
            }
        """
        
        # 크기 표시 라벨 (왼쪽 배치) - 더블클릭 시 45px 초기화 지원
        self.lbl_size_display = DoubleClickableLabel(f"{self.avatar_size_all}px")
        self.lbl_size_display.setCursor(Qt.PointingHandCursor)
        self.lbl_size_display.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_size_display.setFixedWidth(36)
        self.lbl_size_display.setFixedHeight(24)
        self.lbl_size_display.setStyleSheet("font-size: 11px; font-weight: bold; color: #4B5563; border: none; background: transparent; padding-right: 4px;")
        self.lbl_size_display.setToolTip("현재 프로필 이미지 크기\n(더블클릭 시 45px로 초기화)")
        self.lbl_size_display.doubleClicked.connect(self.reset_zoom)
        zoom_layout.addWidget(self.lbl_size_display)
        
        # 마이너스 버튼
        self.btn_zoom_out = QPushButton("−")
        self.btn_zoom_out.setCursor(Qt.PointingHandCursor)
        self.btn_zoom_out.setStyleSheet(btn_style)
        self.btn_zoom_out.setToolTip("프로필 이미지 축소")
        self.btn_zoom_out.clicked.connect(self.zoom_out)
        zoom_layout.addWidget(self.btn_zoom_out)
        
        # 플러스 버튼
        self.btn_zoom_in = QPushButton("+")
        self.btn_zoom_in.setCursor(Qt.PointingHandCursor)
        self.btn_zoom_in.setStyleSheet(btn_style)
        self.btn_zoom_in.setToolTip("프로필 이미지 확대")
        self.btn_zoom_in.clicked.connect(self.zoom_in)
        zoom_layout.addWidget(self.btn_zoom_in)
        
        self.tabs.setCornerWidget(zoom_widget, Qt.TopRightCorner)
        
        self.tabs.setStyleSheet("""
            QTabBar {
                qproperty-drawBase: 0;
            }
            QTabWidget::pane {
                border: 1px solid #E5E7EB;
                border-top-left-radius: 0px;
                border-top-right-radius: 8px;
                border-bottom-left-radius: 8px;
                border-bottom-right-radius: 8px;
                background-color: #FFFFFF;
            }
            QTabBar::tab {
                background: #F3F4F6;
                border: 1px solid #E5E7EB;
                border-top-left-radius: 6px;
                border-top-right-radius: 6px;
                padding: 6px 8px;
                font-size: 12px;
                font-weight: 500;
                color: #4B5563;
                margin-right: 2px;
                margin-bottom: 0px;
            }
            QTabBar::tab:first {
                margin-left: 0px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                border-color: #E5E7EB;
                border-bottom: 2px solid #FFFFFF;
                font-weight: bold;
                color: #FF4B4B;
                margin-bottom: -2px;
            }
            QTabBar::tab:hover:!selected {
                background: #E5E7EB;
            }
        """)
        
        # 1. 전체 캐릭터 탭
        self.tab_all = QWidget()
        self.tab_all.setObjectName("tab_all")
        self.tab_all.setStyleSheet("QWidget#tab_all { background-color: #FFFFFF; border-radius: 8px; }")
        all_layout = QVBoxLayout(self.tab_all)
        all_layout.setContentsMargins(8, 8, 8, 8)
        all_layout.setSpacing(8)
        
        info_label = QLabel("💡 사용 안내\n• Step 2: 더블클릭 또는 드래그로 캐릭터 추가\n• Step 3: 대본 캐릭터 셀로 드래그하여 역할 배정")
        info_label.setStyleSheet("font-size: 11px; color: #6B7280; font-weight: 500; line-height: 140%;")
        all_layout.addWidget(info_label)
        
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        search_layout.setSpacing(6)
        
        self.search_bar = SingleClickLineEdit()
        self.search_bar.setPlaceholderText("🔍 캐릭터 이름 검색...")
        self.search_bar.setClearButtonEnabled(True)
        self.search_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 4px 30px 4px 10px;
                font-size: 13px;
                background-color: #F9FAFB;
                min-height: 28px;
                max-height: 28px;
            }
            QLineEdit:focus {
                border-color: #FF4B4B;
                background-color: #FFFFFF;
            }
        """ + "\n" + config.MODERN_MENU_STYLE)
        
        self.search_bar.textChanged.connect(self.filter_list)
        search_layout.addWidget(self.search_bar)
        
        all_layout.addLayout(search_layout)
        
        self.update_zoom_buttons_state()
        
        self.list_widget = DraggableCharacterListWidget(self)
        self.list_widget.setStyleSheet(self._list_stylesheet())
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        all_layout.addWidget(self.list_widget)
        
        self.tabs.addTab(self.tab_all, "전체 캐릭터")
        
        # 2. 현재 회차 탭
        self.tab_current = QWidget()
        self.tab_current.setObjectName("tab_current")
        self.tab_current.setStyleSheet("QWidget#tab_current { background-color: #FFFFFF; border-radius: 8px; }")
        current_layout = QVBoxLayout(self.tab_current)
        current_layout.setContentsMargins(8, 8, 8, 8)
        current_layout.setSpacing(8)
        
        current_info = QLabel("💡 사용 안내\n• 자동 등록: 대본 캐릭터 셀에 배정된 인물이 자동으로 노출됩니다.\n• 빠른 입력: 등장 비중이 높은 인물을 빠르게 드래그하여 입력합니다.")
        current_info.setStyleSheet("font-size: 11px; color: #6B7280; font-weight: 500; line-height: 140%;")
        current_layout.addWidget(current_info)
        
        self.list_widget_current = DraggableCharacterListWidget(self)
        self.list_widget_current.setStyleSheet(self._list_stylesheet())
        self.list_widget_current.itemDoubleClicked.connect(self.on_item_double_clicked)
        current_layout.addWidget(self.list_widget_current)
        
        self.tabs.addTab(self.tab_current, "현재 회차 등장인물")
        self.tabs.currentChanged.connect(self.on_tab_changed)
        
        layout.addWidget(self.tabs)
        
        self.btn_close = QPushButton("닫기")
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: #212529;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #000000;
            }
        """)
        self.btn_close.clicked.connect(self.close)
        layout.addWidget(self.btn_close)
        
    def _list_stylesheet(self):
        return """
            QListWidget {
                border: 1px solid #E5E7EB;
                border-radius: 8px;
                background-color: #FFFFFF;
                padding: 5px;
                outline: none;
            }
            QListWidget::item {
                border-radius: 6px;
                margin: 2px 0px;
                padding: 0px;
            }
            QListWidget::item:hover {
                background-color: #FFF5F5;
            }
            QListWidget::item:selected {
                background-color: #FFECEC;
                border: 1px solid #FFCDCD;
            }
        """

    def load_data(self):
        self.list_widget.clear()
        
        chars = config.load_global_characters(self.project_name)
        role_priority = {"주연": 0, "조연": 1, "단역": 2}
        chars.sort(key=lambda c: (role_priority.get(c.get("role", "단역"), 2), c.get("name", "")))
        
        for char in chars:
            name = char.get("name", "")
            if not name:
                continue
                
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, self.avatar_size_all + 16))
            
            container = CharacterListItemWidget(char, self.project_name, self.avatar_size_all, self)
            list_item.setData(Qt.UserRole, char)
            
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, container)
            
        self.filter_list()
        self.load_current_episode_characters()
        
    def load_current_episode_characters(self):
        self.list_widget_current.clear()
        
        mw = self.parent()
        if not mw or not hasattr(mw, 'table_script'):
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    mw = widget
                    break
        
        if not mw or not hasattr(mw, 'table_script'):
            return
            
        table = mw.table_script
        active_names = set()
        for r in range(table.rowCount()):
            combo = table.cellWidget(r, 0)
            if isinstance(combo, QComboBox):
                name = combo.currentText().strip()
                if name:
                    active_names.add(name)
            else:
                item = table.item(r, 0)
                if item:
                    name = item.text().strip()
                    if name:
                        active_names.add(name)
                        
        if hasattr(mw, 'get_character_list'):
            step2_names = mw.get_character_list()
            for name in step2_names:
                name_clean = name.strip()
                if name_clean:
                    active_names.add(name_clean)
                        
        if not active_names:
            return
            
        global_chars = config.load_global_characters(self.project_name)
        global_chars_dict = {c.get("name", ""): c for c in global_chars}
        
        role_priority = {"주연": 0, "조연": 1, "단역": 2}
        def get_current_char_sort_key(name):
            char = global_chars_dict.get(name)
            role = char.get("role", "단역") if char else "단역"
            return (role_priority.get(role, 2), name)
            
        sorted_names = sorted(list(active_names), key=get_current_char_sort_key)
        for name in sorted_names:
            char = global_chars_dict.get(name)
            if not char:
                char = {
                    "name": name,
                    "role": "단역",
                    "gender": "기타",
                    "age": "미정",
                    "image_path": "",
                    "color": "#6B7280"
                }
                
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, self.avatar_size_current + 16))
            
            container = CharacterListItemWidget(char, self.project_name, self.avatar_size_current, self)
            list_item.setData(Qt.UserRole, char)
            
            self.list_widget_current.addItem(list_item)
            self.list_widget_current.setItemWidget(list_item, container)

    def get_current_tab_avatar_size(self):
        if self.tabs.currentIndex() == 0:
            return self.avatar_size_all
        else:
            return self.avatar_size_current

    def set_current_tab_avatar_size(self, value):
        if self.tabs.currentIndex() == 0:
            self.avatar_size_all = value
            config.AVATAR_SIZE_ALL = value
        else:
            self.avatar_size_current = value
            config.AVATAR_SIZE_CURRENT = value
        config.save_settings()

    def on_tab_changed(self, index):
        current_size = self.get_current_tab_avatar_size()
        self.lbl_size_display.setText(f"{current_size}px")
        self.update_zoom_buttons_state()

    def on_avatar_size_changed(self, value):
        self.set_current_tab_avatar_size(value)
        self.lbl_size_display.setText(f"{value}px")
        
        if self.tabs.currentIndex() == 0:
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                widget = self.list_widget.itemWidget(item)
                if isinstance(widget, CharacterListItemWidget):
                    widget.update_avatar(value)
                    item.setSizeHint(QSize(0, value + 16))
            self.list_widget.doItemsLayout()
        else:
            for i in range(self.list_widget_current.count()):
                item = self.list_widget_current.item(i)
                widget = self.list_widget_current.itemWidget(item)
                if isinstance(widget, CharacterListItemWidget):
                    widget.update_avatar(value)
                    item.setSizeHint(QSize(0, value + 16))
            self.list_widget_current.doItemsLayout()
                
        self.update_zoom_buttons_state()

    def zoom_in(self):
        current_size = self.get_current_tab_avatar_size()
        new_size = min(80, current_size + 5)
        if new_size != current_size:
            self.on_avatar_size_changed(new_size)

    def zoom_out(self):
        current_size = self.get_current_tab_avatar_size()
        new_size = max(30, current_size - 5)
        if new_size != current_size:
            self.on_avatar_size_changed(new_size)

    def reset_zoom(self):
        current_size = self.get_current_tab_avatar_size()
        if current_size != 45:
            self.on_avatar_size_changed(45)

    def update_zoom_buttons_state(self):
        current_size = self.get_current_tab_avatar_size()
        self.btn_zoom_out.setEnabled(current_size > 30)
        self.btn_zoom_in.setEnabled(current_size < 80)

    def set_project_name(self, project_name):
        self.project_name = project_name
        self.load_data()
        
    def filter_list(self):
        import unicodedata
        query = unicodedata.normalize('NFC', self.search_bar.text().lower().strip())
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            char_info = item.data(Qt.UserRole)
            name = char_info.get("name", "").lower() if char_info else ""
            name_norm = unicodedata.normalize('NFC', name)
            item.setHidden(query != "" and query not in name_norm)
            
    def on_item_double_clicked(self, item):
        char_info = item.data(Qt.UserRole)
        if char_info:
            self.character_selected.emit(char_info)
            mw = self.parent()
            if not mw or not hasattr(mw, 'add_character_card'):
                for widget in QApplication.topLevelWidgets():
                    if widget.__class__.__name__ == 'MainWindow':
                        mw = widget
                        break
            
            if mw and hasattr(mw, 'add_character_card'):
                mw.add_character_card(
                    name=char_info.get("name", ""),
                    age=char_info.get("age", ""),
                    gender=char_info.get("gender", ""),
                    role=char_info.get("role", "")
                )



    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.search_bar.clear()
            event.accept()
        else:
            super().keyPressEvent(event)

# =================================================================
# 👥 캐릭터 통합 관리 다이얼로그 (GlobalCharacterSettingsDialog)
# =================================================================
class GlobalCharacterSettingsDialog(QDialog):
    """작품 전체의 캐릭터 데이터베이스를 추가, 수정, 삭제하고 색상을 관리하는 미려한 통합 관리 다이얼로그"""
    def __init__(self, parent=None, project_name=""):
        super().__init__(parent)
        self.project_name = project_name
        self.setWindowTitle("👥 캐릭터 관리")
        self.resize(580, 710)
        self.selected_color = "#3B82F6"
        self.editing_name = None
        
        self.init_ui()
        self.load_characters()
        
    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        form_widget = QWidget()
        form_widget.setObjectName("FormWidget")
        form_widget.setStyleSheet("""
            QWidget#FormWidget {
                background-color: #F9FAFB;
                border: 1px solid #E5E7EB;
                border-radius: 8px;
            }
            QLabel {
                font-weight: 500;
                color: #374151;
                border: none;
            }
        """)
        form_layout = QVBoxLayout(form_widget)
        form_layout.setSpacing(10)
        
        title_container = QWidget()
        title_container.setObjectName("TitleContainer")
        title_container.setStyleSheet("""
            QWidget#TitleContainer {
                background: transparent;
                border-bottom: 1px solid #E5E7EB;
                border-radius: 0px;
            }
        """)
        title_container_layout = QHBoxLayout(title_container)
        title_container_layout.setContentsMargins(0, 0, 0, 5)
        title_container_layout.setSpacing(6)
        
        lbl_title_icon = QLabel()
        lbl_title_icon.setFixedSize(16, 16)
        lbl_title_icon.setStyleSheet("border: none; background: transparent;")
        title_pix = get_colored_pixmap(config.ICON_USER, "#7C3AED", 16, 16)
        lbl_title_icon.setPixmap(title_pix)
        
        title_lbl = QLabel("캐릭터 추가 / 수정")
        title_lbl.setStyleSheet("font-size: 15px; font-weight: 600; color: #111827; border: none; background: transparent; padding: 0px;")
        
        title_container_layout.addWidget(lbl_title_icon)
        title_container_layout.addWidget(title_lbl)
        title_container_layout.addStretch()
        form_layout.addWidget(title_container)
        
        body_layout = QHBoxLayout()
        body_layout.setSpacing(15)
        body_layout.setContentsMargins(10, 5, 10, 5)
        
        avatar_layout = QVBoxLayout()
        avatar_layout.setAlignment(Qt.AlignBottom | Qt.AlignHCenter)
        avatar_layout.setSpacing(6)
        
        self.lbl_avatar = QLabel()
        self.lbl_avatar.setFixedSize(110, 110)
        self.lbl_avatar.setAlignment(Qt.AlignCenter)
        self.lbl_avatar.setStyleSheet("""
            QLabel {
                background-color: #F9FAFB;
                border: 2px dashed #9CA3AF;
                border-radius: 8px;
                padding: 0px;
            }
        """)
        self.lbl_avatar.setContextMenuPolicy(Qt.CustomContextMenu)
        self.lbl_avatar.customContextMenuRequested.connect(self.show_avatar_context_menu)
        avatar_layout.addWidget(self.lbl_avatar)
        
        self.avatar_btn_layout = QHBoxLayout()
        self.avatar_btn_layout.setSpacing(4)
        self.avatar_btn_layout.setContentsMargins(0, 0, 0, 0)
        
        self.btn_change_avatar = QPushButton("등록")
        self.btn_change_avatar.setCursor(Qt.PointingHandCursor)
        self.btn_change_avatar.setFixedSize(53, 22)
        self.btn_change_avatar.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
                color: #374151;
                font-weight: 500;
                padding: 0px;
            }
            QPushButton:hover {
                border-color: #3B82F6;
                color: #3B82F6;
            }
        """)
        self.btn_change_avatar.clicked.connect(self.select_profile_image)
        
        self.btn_delete_avatar = QPushButton("삭제")
        self.btn_delete_avatar.setCursor(Qt.PointingHandCursor)
        self.btn_delete_avatar.setFixedSize(53, 22)
        self.btn_delete_avatar.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                font-size: 12px;
                color: #EF4444;
                font-weight: 500;
                padding: 0px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #EF4444;
            }
        """)
        self.btn_delete_avatar.clicked.connect(self.delete_profile_image)
        
        self.avatar_btn_layout.addWidget(self.btn_change_avatar)
        self.avatar_btn_layout.addWidget(self.btn_delete_avatar)
        avatar_layout.addLayout(self.avatar_btn_layout)
        
        grid_layout = QGridLayout()
        grid_layout.setHorizontalSpacing(13)
        grid_layout.setVerticalSpacing(10)
        grid_layout.setContentsMargins(0, 0, 0, 0)
        grid_layout.setColumnStretch(1, 1)
        
        grid_layout.addWidget(QLabel("이름"), 0, 0)
        self.input_name = QLineEdit()
        self.input_name.setPlaceholderText("예: 밤, 쿤, 라헬")
        self.input_name.setStyleSheet("background-color: white; border: 1px solid #D1D5DB; border-radius: 4px; padding: 4px 8px; min-height: 28px;\n" + config.MODERN_MENU_STYLE)
        grid_layout.addWidget(self.input_name, 0, 1)
        
        grid_layout.addWidget(QLabel("역할"), 1, 0)
        
        dropdown_layout = QHBoxLayout()
        dropdown_layout.setContentsMargins(0, 0, 0, 0)
        dropdown_layout.setSpacing(0)
        
        self.combo_role = QComboBox()
        self.combo_role.addItems(["주연", "조연", "단역"])
        self.combo_role.setStyleSheet("background-color: white; border: 1px solid #D1D5DB; border-radius: 4px; padding: 4px; min-height: 28px;")
        self.combo_role.setFixedWidth(78)
        
        age_widget = QWidget()
        age_widget.setStyleSheet("background: transparent; border: none;")
        age_layout = QHBoxLayout(age_widget)
        age_layout.setContentsMargins(0, 0, 0, 0)
        age_layout.setSpacing(13)
        lbl_age = QLabel("연령")
        lbl_age.setStyleSheet("font-weight: 500; color: #374151; border: none;")
        self.combo_age = QComboBox()
        self.combo_age.addItems(config.AGE_OPTIONS)
        self.combo_age.setStyleSheet("background-color: white; border: 1px solid #D1D5DB; border-radius: 4px; padding: 4px; min-height: 28px;")
        self.combo_age.setFixedWidth(78)
        age_layout.addWidget(lbl_age)
        age_layout.addWidget(self.combo_age)
        
        gender_widget = QWidget()
        gender_widget.setStyleSheet("background: transparent; border: none;")
        gender_layout = QHBoxLayout(gender_widget)
        gender_layout.setContentsMargins(0, 0, 0, 0)
        gender_layout.setSpacing(13)
        lbl_gender = QLabel("성별")
        lbl_gender.setStyleSheet("font-weight: 500; color: #374151; border: none;")
        self.combo_gender = QComboBox()
        self.combo_gender.addItems(config.GENDER_OPTIONS)
        self.combo_gender.setStyleSheet("background-color: white; border: 1px solid #D1D5DB; border-radius: 4px; padding: 4px; min-height: 28px;")
        self.combo_gender.setFixedWidth(78)
        gender_layout.addWidget(lbl_gender)
        gender_layout.addWidget(self.combo_gender)
        
        dropdown_layout.addWidget(self.combo_role)
        dropdown_layout.addStretch(1)
        dropdown_layout.addWidget(age_widget)
        dropdown_layout.addStretch(1)
        dropdown_layout.addWidget(gender_widget)
        
        grid_layout.addLayout(dropdown_layout, 1, 1)
        
        grid_layout.addWidget(QLabel("메모"), 2, 0)
        self.input_memo = QLineEdit()
        self.input_memo.setPlaceholderText("캐릭터 특징 및 설정 메모 (생략 가능)")
        self.input_memo.setStyleSheet("background-color: white; border: 1px solid #D1D5DB; border-radius: 4px; padding: 4px 8px; min-height: 28px;\n" + config.MODERN_MENU_STYLE)
        grid_layout.addWidget(self.input_memo, 2, 1)
        
        body_layout.addLayout(avatar_layout)
        body_layout.addLayout(grid_layout, 1)
        body_layout.setAlignment(Qt.AlignBottom)
        
        form_layout.addLayout(body_layout)
        
        self.temp_image_path = None
        self.temp_orig_image_path = None
        self.temp_crop_rect = None
        self.set_avatar_pixmap(None)
        self.update_avatar_buttons()
        
        btn_form_layout = QHBoxLayout()
        btn_form_layout.setContentsMargins(15, 0, 15, 5)
        btn_form_layout.addStretch()
        
        self.btn_cancel_edit = QPushButton("취소")
        self.btn_cancel_edit.setVisible(False)
        self.btn_cancel_edit.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 6px 14px;
                font-weight: bold;
                color: #4B5563;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #F3F4F6;
            }
        """)
        self.btn_cancel_edit.clicked.connect(self.cancel_editing)
        btn_form_layout.addWidget(self.btn_cancel_edit)
        
        self.btn_submit = QPushButton("캐릭터 등록")
        self.btn_submit.setStyleSheet("""
            QPushButton {
                background-color: #FF4B4B;
                color: white;
                border: 1px solid transparent;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: bold;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #E03E3E;
            }
        """)
        self.btn_submit.clicked.connect(self.submit_character)
        btn_form_layout.addWidget(self.btn_submit)
        
        form_layout.addLayout(btn_form_layout)
        main_layout.addWidget(form_widget)
        
        list_header_layout = QHBoxLayout()
        list_header_layout.setContentsMargins(0, 0, 0, 0)
        list_header_layout.setSpacing(6)
        
        lbl_list_icon = QLabel()
        lbl_list_icon.setFixedSize(16, 16)
        lbl_list_icon.setStyleSheet("border: none; background: transparent;")
        list_pix = get_colored_pixmap(config.ICON_USER, "#7C3AED", 16, 16)
        lbl_list_icon.setPixmap(list_pix)
        
        list_title = QLabel("등록된 캐릭터 목록")
        list_title.setStyleSheet("font-size: 15px; font-weight: 600; color: #111827; border: none; background: transparent; padding: 0px;")
        
        list_header_layout.addWidget(lbl_list_icon)
        list_header_layout.addWidget(list_title)
        
        self.lbl_count = QLabel("(총 0명)")
        self.lbl_count.setStyleSheet("font-size: 13px; color: #6B7280; font-weight: 500; border: none; background: transparent;")
        list_header_layout.addWidget(self.lbl_count)
        list_header_layout.addStretch()
        
        self.btn_import = HoverIconButton(
            " 캐릭터 정보 가져오기",
            config.ICON_IMPORT,
            normal_color="#2563EB",
            hover_color="#1D4ED8"
        )
        self.btn_import.setIconSize(QSize(13, 13))
        self.btn_import.setToolTip("HTML/MHTML 파일로부터 캐릭터 정보를 가져옵니다.")
        self.btn_import.setStyleSheet("""
            QPushButton {
                background-color: #EFF6FF;
                border: 1px solid #BFDBFE;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
                color: #2563EB;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #DBEAFE;
                border-color: #2563EB;
                color: #1D4ED8;
            }
        """)
        self.btn_import.clicked.connect(self.import_characters_from_html)
        list_header_layout.addWidget(self.btn_import)
        
        self.btn_sync_all = HoverIconButton(
            " 모든 회차 동기화",
            config.ICON_REFRESH,
            normal_color="#EF4444",
            hover_color="#DC2626"
        )
        self.btn_sync_all.setIconSize(QSize(13, 13))
        self.btn_sync_all.setToolTip("수정된 성별, 나이, 역할, 색상 설정을 이미 생성된 기존 모든 회차에 일곽 적용합니다.")
        self.btn_sync_all.setStyleSheet("""
            QPushButton {
                background-color: #FFF5F5;
                border: 1px solid #FECACA;
                border-radius: 4px;
                padding: 4px 10px;
                font-size: 12px;
                font-weight: 500;
                color: #EF4444;
                min-height: 18px;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
                border-color: #EF4444;
                color: #DC2626;
            }
        """)
        self.btn_sync_all.clicked.connect(self.sync_all_episodes_confirm)
        list_header_layout.addWidget(self.btn_sync_all)
        
        list_section_layout = QVBoxLayout()
        list_section_layout.setContentsMargins(0, 0, 0, 0)
        list_section_layout.setSpacing(8)
        
        list_section_layout.addLayout(list_header_layout)
        
        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 0)
        self.search_input = SingleClickLineEdit()
        self.search_input.setFixedHeight(27)
        self.search_input.setPlaceholderText("🔍 캐릭터 이름, 역할 또는 메모 검색...")
        self.search_input.setClearButtonEnabled(True)

        self.search_input.setStyleSheet("""
            QLineEdit {
                background-color: white;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 2px 30px 2px 10px;
                font-size: 13px;
                color: #111827;
                min-height: 27px;
                max-height: 27px;
            }
            QLineEdit:focus {
                border-color: #3B82F6;
            }
        """)
        self.search_input.textChanged.connect(self.filter_characters)
        search_layout.addWidget(self.search_input)
        list_section_layout.addLayout(search_layout)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        scroll_area.setStyleSheet("border: 1px solid #E5E7EB; border-radius: 8px; background-color: #F9FAFB;")
        
        self.list_container = QWidget()
        self.list_container.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_container)
        self.list_layout.setContentsMargins(10, 10, 10, 10)
        self.list_layout.setSpacing(8)
        self.list_layout.setAlignment(Qt.AlignTop)
        
        scroll_area.setWidget(self.list_container)
        list_section_layout.addWidget(scroll_area, 1)
        
        main_layout.addLayout(list_section_layout, 1)
        
        footer_layout = QHBoxLayout()
        footer_layout.addStretch()
        btn_close = QPushButton("닫기")
        btn_close.setStyleSheet("""
            QPushButton {
                background-color: #212529;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 24px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #000000;
            }
        """)
        btn_close.clicked.connect(self.accept)
        footer_layout.addWidget(btn_close)
        main_layout.addLayout(footer_layout)
        
    def filter_characters(self, text):
        self.load_characters()

    def load_characters(self):
        while self.list_layout.count():
            child = self.list_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            
        chars = config.load_global_characters(self.project_name)
        self.lbl_count.setText(f"(총 {len(chars)}명)")
        
        role_priority = {"주연": 0, "조연": 1, "단역": 2}
        chars.sort(key=lambda c: (role_priority.get(c.get("role", "단역"), 2), c.get("name", "")))
        
        query = ""
        if hasattr(self, 'search_input'):
            import unicodedata
            query = unicodedata.normalize('NFC', self.search_input.text().strip().lower())
            
        visible_count = 0
        for char in chars:
            name = char.get("name", "")
            role = char.get("role", "단역")
            memo = char.get("memo", "")
            
            import unicodedata
            name_norm = unicodedata.normalize('NFC', name.lower())
            role_norm = unicodedata.normalize('NFC', role.lower())
            memo_norm = unicodedata.normalize('NFC', memo.lower())
            
            if query and not (query in name_norm or query in role_norm or query in memo_norm):
                continue
                
            if visible_count > 0:
                line = QWidget()
                line.setStyleSheet("background-color: #ECEEF1; min-height: 1px; max-height: 1px; border: none; margin: 4px 10px;")
                self.list_layout.addWidget(line)
                
            card = GlobalCharacterCard(char, self)
            card.delete_clicked.connect(self.delete_character)
            card.edit_clicked.connect(self.edit_character)
            self.list_layout.addWidget(card)
            visible_count += 1
            
        self.list_layout.addStretch(1)
            
        if query:
            self.lbl_count.setText(f"(검색 결과 {visible_count}명 / 총 {len(chars)}명)")
        else:
            self.lbl_count.setText(f"(총 {len(chars)}명)")
            
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            if hasattr(self, 'search_input') and self.search_input.text():
                self.search_input.clear()
            event.accept()
        else:
            super().keyPressEvent(event)
            
    def set_avatar_pixmap(self, img_path):
        if img_path and os.path.exists(img_path):
            pixmap = QPixmap(img_path)
            if not pixmap.isNull():
                round_pix = get_round_rect_pixmap(pixmap, 110, 110, 8)
                self.lbl_avatar.setPixmap(round_pix)
                self.lbl_avatar.setStyleSheet("""
                    QLabel {
                        border: 1px solid #D1D5DB;
                        border-radius: 8px;
                        background-color: #FFFFFF;
                        padding: 0px;
                    }
                """)
                self.temp_image_path = img_path
                return
                
        self.lbl_avatar.setStyleSheet("""
            QLabel {
                border: 2px dashed #9CA3AF;
                border-radius: 8px;
                background-color: #F9FAFB;
                padding: 0px;
            }
        """)
        
        default_pix = QPixmap(110, 110)
        default_pix.fill(Qt.transparent)
        
        painter = QPainter(default_pix)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        svg_pix = get_colored_pixmap(config.ICON_AVATAR_UPLOAD, "#6B7280", 32, 32)
        painter.drawPixmap(39, 25, svg_pix)
        
        font_text = QFont("Pretendard", 9, QFont.Bold)
        painter.setFont(font_text)
        painter.setPen(QColor("#6B7280"))
        painter.drawText(QRect(0, 68, 110, 20), Qt.AlignCenter, "이미지 추가")
        
        painter.end()
        
        self.lbl_avatar.setPixmap(default_pix)
        if img_path is None:
            self.temp_image_path = None

    def select_profile_image(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "프로필 이미지 선택", "",
            "이미지 파일 (*.png *.jpg *.jpeg *.webp)"
        )
        if file_path:
            crop_dlg = ImageCropDialog(file_path, self)
            if crop_dlg.exec() == QDialog.Accepted:
                cropped_pixmap = crop_dlg.cropped_pixmap
                if cropped_pixmap and not cropped_pixmap.isNull():
                    temp_dir = tempfile.gettempdir()
                    temp_crop_path = os.path.join(temp_dir, f"crop_{uuid.uuid4().hex[:8]}.png")
                    
                    cropped_pixmap.save(temp_crop_path, "PNG")
                    
                    self.temp_image_path = temp_crop_path
                    self.temp_orig_image_path = file_path
                    self.temp_crop_rect = crop_dlg.crop_rect_coords
                    
                    self.set_avatar_pixmap(temp_crop_path)
                    self.update_avatar_buttons()

    def adjust_profile_image(self):
        if not self.temp_orig_image_path or not os.path.exists(self.temp_orig_image_path):
            QMessageBox.warning(self, "경고", "원본 이미지를 찾을 수 없어 조절할 수 없습니다.")
            return
            
        crop_dlg = ImageCropDialog(self.temp_orig_image_path, self, initial_crop_rect=self.temp_crop_rect)
        if crop_dlg.exec() == QDialog.Accepted:
            cropped_pixmap = crop_dlg.cropped_pixmap
            if cropped_pixmap and not cropped_pixmap.isNull():
                temp_dir = tempfile.gettempdir()
                temp_crop_path = os.path.join(temp_dir, f"crop_{uuid.uuid4().hex[:8]}.png")
                
                cropped_pixmap.save(temp_crop_path, "PNG")
                
                self.temp_image_path = temp_crop_path
                self.temp_crop_rect = crop_dlg.crop_rect_coords
                
                self.set_avatar_pixmap(temp_crop_path)
                self.update_avatar_buttons()

    def delete_profile_image(self):
        self.set_avatar_pixmap(None)
        self.temp_image_path = "DELETE"
        self.temp_orig_image_path = "DELETE"
        self.temp_crop_rect = None
        self.update_avatar_buttons()

    def update_avatar_buttons(self):
        has_image = self.temp_orig_image_path is not None and self.temp_orig_image_path != "DELETE"
        
        self.avatar_btn_layout.removeWidget(self.btn_change_avatar)
        self.avatar_btn_layout.removeWidget(self.btn_delete_avatar)
        
        if not has_image:
            self.btn_change_avatar.setText("등록")
            self.btn_change_avatar.setFixedSize(110, 22)
            self.btn_change_avatar.setVisible(True)
            self.avatar_btn_layout.addWidget(self.btn_change_avatar)
            
            self.btn_delete_avatar.setVisible(False)
            self.lbl_avatar.setToolTip("")
        else:
            self.btn_change_avatar.setText("변경")
            self.btn_change_avatar.setFixedSize(53, 22)
            self.btn_change_avatar.setVisible(True)
            
            self.btn_delete_avatar.setFixedSize(53, 22)
            self.btn_delete_avatar.setVisible(True)
            
            self.avatar_btn_layout.addWidget(self.btn_change_avatar)
            self.avatar_btn_layout.addWidget(self.btn_delete_avatar)
            self.lbl_avatar.setToolTip("우클릭: 이미지 조정")

    def show_avatar_context_menu(self, pos):
        has_image = self.temp_orig_image_path is not None and self.temp_orig_image_path != "DELETE"
        if not has_image:
            return
            
        menu = QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #E5E7EB;
                border-radius: 6px;
                padding: 4px 0px;
            }
            QMenu::item {
                padding: 6px 20px;
                font-size: 14px;
                color: #374151;
            }
            QMenu::item:selected {
                background-color: #F3F4F6;
                color: #111827;
            }
        """)
        
        svg_str = """<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="lucide lucide-crop-icon lucide-crop"><path d="M6 2v14a2 2 0 0 0 2 2h14"/><path d="M18 22V8a2 2 0 0 0-2-2H2"/></svg>"""
        colored_svg = svg_str.replace('currentColor', '#374151')
        
        icon = QIcon()
        try:
            renderer = QSvgRenderer(QByteArray(colored_svg.encode('utf-8')))
            pixmap = QPixmap(16, 16)
            pixmap.fill(Qt.transparent)
            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.Antialiasing, True)
            renderer.render(painter)
            painter.end()
            icon = QIcon(pixmap)
        except Exception as e:
            print(f"SVG icon render failed: {e}")
            
        action_adjust = QAction(icon, "이미지 조정", self)
        action_adjust.triggered.connect(self.adjust_profile_image)
        menu.addAction(action_adjust)
        
        menu.exec(self.lbl_avatar.mapToGlobal(pos))

    def cancel_editing(self):
        self.editing_name = None
        self.input_name.setEnabled(True)
        self.input_name.clear()
        self.input_memo.clear()
        self.btn_submit.setText("캐릭터 등록")
        self.btn_cancel_edit.setVisible(False)
        self.selected_color = "#3B82F6"
        self.temp_image_path = None
        self.temp_orig_image_path = None
        self.temp_crop_rect = None
        self.set_avatar_pixmap(None)
        self.update_avatar_buttons()
        
    def edit_character(self, char_info):
        self.editing_name = char_info.get("name", "")
        self.input_name.setText(self.editing_name)
        self.input_name.setEnabled(True)
        
        self.combo_role.setCurrentText(char_info.get("role", "단역"))
        self.combo_age.setCurrentText(char_info.get("age", "미상"))
        self.combo_gender.setCurrentText(char_info.get("gender", "미상"))
        
        self.selected_color = char_info.get("color", "#3B82F6")
        self.input_memo.setText(char_info.get("memo", ""))
        
        img_path = char_info.get("image_path", "")
        orig_img_path = char_info.get("image_path_orig", "")
        crop_rect = char_info.get("crop_rect", None)
        if orig_img_path:
            full_orig_path = os.path.join(config.PROJECTS_DIR, self.project_name, orig_img_path)
        else:
            full_orig_path = ""
            
        if img_path:
            full_img_path = os.path.join(config.PROJECTS_DIR, self.project_name, img_path)
            self.set_avatar_pixmap(full_img_path)
            
            if full_orig_path and os.path.exists(full_orig_path):
                self.temp_image_path = full_img_path
                self.temp_orig_image_path = full_orig_path
                self.temp_crop_rect = crop_rect
            else:
                self.temp_image_path = full_img_path
                self.temp_orig_image_path = full_img_path
                self.temp_crop_rect = None
        else:
            self.set_avatar_pixmap(None)
            self.temp_image_path = None
            self.temp_orig_image_path = None
            self.temp_crop_rect = None
        
        self.btn_submit.setText("캐릭터 정보 수정")
        self.btn_cancel_edit.setVisible(True)
        self.update_avatar_buttons()
        
    def submit_character(self):
        name = self.input_name.text().strip()
        if not name:
            QMessageBox.warning(self, "입력 오류", "캐릭터 이름을 입력해주세요.")
            return
            
        chars = config.load_global_characters(self.project_name)
        
        if self.editing_name:
            if self.editing_name != name:
                if any(c.get("name", "").strip() == name for c in chars):
                    QMessageBox.warning(self, "중복 오류", f"'{name}' 캐릭터는 이미 등록되어 있습니다.")
                    return
        else:
            if any(c.get("name", "").strip() == name for c in chars):
                QMessageBox.warning(self, "중복 오류", f"'{name}' 캐릭터는 이미 등록되어 있습니다.")
                return
                
        img_dir = os.path.join(config.PROJECTS_DIR, self.project_name, "character_images")
        os.makedirs(img_dir, exist_ok=True)
        
        target_img_name = f"{name}.png"
        target_img_relative = f"character_images/{target_img_name}"
        target_img_absolute = os.path.join(config.PROJECTS_DIR, self.project_name, target_img_relative)
        
        target_orig_name = f"{name}_orig.png"
        target_orig_relative = f"character_images/{target_orig_name}"
        target_orig_absolute = os.path.join(config.PROJECTS_DIR, self.project_name, target_orig_relative)
        
        if self.editing_name and self.editing_name != name:
            existing = next((c for c in chars if c.get("name", "") == self.editing_name), None)
            if existing:
                old_img_rel = existing.get("image_path", "")
                old_orig_rel = existing.get("image_path_orig", "")
                
                old_img_abs = os.path.join(config.PROJECTS_DIR, self.project_name, old_img_rel) if old_img_rel else ""
                old_orig_abs = os.path.join(config.PROJECTS_DIR, self.project_name, old_orig_rel) if old_orig_rel else ""
                
                if self.temp_image_path and old_img_abs and os.path.abspath(self.temp_image_path) == os.path.abspath(old_img_abs):
                    if os.path.exists(old_img_abs):
                        try:
                            os.rename(old_img_abs, target_img_absolute)
                            self.temp_image_path = target_img_absolute
                        except Exception as e:
                            print(f"이미지 파일명 변경 실패: {e}")
                    if old_orig_abs and os.path.exists(old_orig_abs):
                        try:
                            os.rename(old_orig_abs, target_orig_absolute)
                            self.temp_orig_image_path = target_orig_absolute
                        except Exception as e:
                            print(f"원본 이미지 파일명 변경 실패: {e}")
                else:
                    if old_img_abs and os.path.exists(old_img_abs):
                        try: os.remove(old_img_abs)
                        except Exception as e: print(f"이전 이미지 삭제 실패: {e}")
                    if old_orig_abs and os.path.exists(old_orig_abs):
                        try: os.remove(old_orig_abs)
                        except Exception as e: print(f"이전 원본 이미지 삭제 실패: {e}")

        image_field_val = ""
        orig_image_field_val = ""
        saved_crop_rect = None
        
        if self.temp_image_path == "DELETE":
            if os.path.exists(target_img_absolute):
                try: os.remove(target_img_absolute)
                except Exception as e: print(f"이미지 삭제 실패: {e}")
            if os.path.exists(target_orig_absolute):
                try: os.remove(target_orig_absolute)
                except Exception as e: print(f"원본 이미지 삭제 실패: {e}")
            image_field_val = ""
            orig_image_field_val = ""
            saved_crop_rect = None
            
        elif self.temp_image_path and os.path.exists(self.temp_image_path):
            if os.path.abspath(self.temp_image_path) != os.path.abspath(target_img_absolute):
                try:
                    pix = QPixmap(self.temp_image_path)
                    if not pix.isNull():
                        scaled_pix = pix.scaled(150, 150, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
                        scaled_pix.save(target_img_absolute, "PNG")
                        image_field_val = target_img_relative
                    else:
                        image_field_val = ""
                except Exception as e:
                    print(f"이미지 리사이징 저장 실패: {e}")
                    image_field_val = ""
            else:
                image_field_val = target_img_relative
                
            if self.temp_orig_image_path and os.path.exists(self.temp_orig_image_path):
                if os.path.abspath(self.temp_orig_image_path) != os.path.abspath(target_orig_absolute):
                    try:
                        orig_pix = QPixmap(self.temp_orig_image_path)
                        if not orig_pix.isNull():
                            max_dimension = 1000
                            if orig_pix.width() > max_dimension or orig_pix.height() > max_dimension:
                                orig_w = orig_pix.width()
                                orig_h = orig_pix.height()
                                ratio = max_dimension / max(orig_w, orig_h)
                                orig_pix = orig_pix.scaled(
                                    max_dimension, max_dimension,
                                    Qt.KeepAspectRatio, Qt.SmoothTransformation
                                )
                                if self.temp_crop_rect:
                                    self.temp_crop_rect = [
                                        int(self.temp_crop_rect[0] * ratio),
                                        int(self.temp_crop_rect[1] * ratio),
                                        int(self.temp_crop_rect[2] * ratio),
                                        int(self.temp_crop_rect[3] * ratio)
                                    ]
                            orig_pix.save(target_orig_absolute, "PNG")
                            orig_image_field_val = target_orig_relative
                            saved_crop_rect = self.temp_crop_rect
                        else:
                            orig_image_field_val = ""
                            saved_crop_rect = None
                    except Exception as e:
                        print(f"원본 이미지 저장 실패: {e}")
                        orig_image_field_val = ""
                        saved_crop_rect = None
                else:
                    orig_image_field_val = target_orig_relative
                    saved_crop_rect = self.temp_crop_rect
            else:
                orig_image_field_val = ""
                saved_crop_rect = None
        else:
            if self.editing_name:
                existing = next((c for c in chars if c.get("name", "") == self.editing_name), None)
                if existing:
                    image_field_val = target_img_relative if existing.get("image_path", "") else ""
                    orig_image_field_val = target_orig_relative if existing.get("image_path_orig", "") else ""
                    saved_crop_rect = existing.get("crop_rect", None)
                    if self.temp_image_path == "DELETE":
                        image_field_val = ""
                        orig_image_field_val = ""
                        saved_crop_rect = None
            else:
                image_field_val = ""
                orig_image_field_val = ""
                saved_crop_rect = None
        
        if self.editing_name is None:
            new_char = {
                "name": name,
                "role": self.combo_role.currentText(),
                "age": self.combo_age.currentText(),
                "gender": self.combo_gender.currentText(),
                "color": self.selected_color,
                "memo": self.input_memo.text().strip(),
                "image_path": image_field_val,
                "image_path_orig": orig_image_field_val,
                "crop_rect": saved_crop_rect
            }
            chars.append(new_char)
            
        else:
            for c in chars:
                if c.get("name", "") == self.editing_name:
                    c["name"] = name
                    c["role"] = self.combo_role.currentText()
                    c["age"] = self.combo_age.currentText()
                    c["gender"] = self.combo_gender.currentText()
                    c["color"] = self.selected_color
                    c["memo"] = self.input_memo.text().strip()
                    c["image_path"] = image_field_val
                    c["image_path_orig"] = orig_image_field_val
                    c["crop_rect"] = saved_crop_rect
                    break
                    
        config.save_global_characters(self.project_name, chars)
        self.cancel_editing()
        self.load_characters()
        
        mw = self.window()
        if hasattr(mw, 'get_character_list'):
            mw.get_character_list()

    def delete_character(self, name):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("캐릭터 삭제")
        msg_box.setText(f"'{name}' 캐릭터를 정말 삭제하시겠습니까?")
        msg_box.setIcon(QMessageBox.Question)
        btn_yes = msg_box.addButton("예", QMessageBox.YesRole)
        btn_no = msg_box.addButton("아니오", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        if msg_box.clickedButton() == btn_yes:
            chars = config.load_global_characters(self.project_name)
            
            existing = next((c for c in chars if c.get("name", "") == name), None)
            if existing:
                if existing.get("image_path", ""):
                    img_abs = os.path.join(config.PROJECTS_DIR, self.project_name, existing["image_path"])
                    if os.path.exists(img_abs):
                        try: os.remove(img_abs)
                        except Exception as e: print(f"캐릭터 삭제 중 이미지 파일 삭제 오류: {e}")
                if existing.get("image_path_orig", ""):
                    orig_abs = os.path.join(config.PROJECTS_DIR, self.project_name, existing["image_path_orig"])
                    if os.path.exists(orig_abs):
                        try: os.remove(orig_abs)
                        except Exception as e: print(f"캐릭터 삭제 중 원본 이미지 파일 삭제 오류: {e}")
            
            chars = [c for c in chars if c.get("name", "") != name]
            config.save_global_characters(self.project_name, chars)
            self.load_characters()
            
            mw = self.window()
            if hasattr(mw, 'get_character_list'):
                mw.get_character_list()
                
    def sync_all_episodes_confirm(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("모든 회차 동기화")
        msg_box.setText("⚠️ 이 작업은 생성된 기존 모든 회차 폴더의 character_info.csv 파일을 검사하여,\n"
                        "현재 글로벌 DB에 저장된 나이, 성별, 역할 정보로 일괄 덮어쓰고 동기화합니다.\n"
                        "계속하시겠습니까?")
        msg_box.setIcon(QMessageBox.Question)
        btn_yes = msg_box.addButton("예", QMessageBox.YesRole)
        btn_no = msg_box.addButton("아니오", QMessageBox.NoRole)
        msg_box.setDefaultButton(btn_no)
        msg_box.exec()
        if msg_box.clickedButton() == btn_yes:
            self.sync_all_episodes()
            
    def sync_all_episodes(self):
        import pandas as pd
        
        chars = config.load_global_characters(self.project_name)
        char_map = {c["name"]: c for c in chars}
        
        t_path = os.path.join(config.PROJECTS_DIR, self.project_name)
        if not os.path.exists(t_path):
            return
            
        success_count = 0
        error_count = 0
        
        for ep_dir in os.listdir(t_path):
            ep_path = os.path.join(t_path, ep_dir)
            if not os.path.isdir(ep_path) or ep_dir in {"images", "character_images", "cache", "temp"}:
                continue
                
            c_csv = os.path.join(ep_path, "character_info.csv")
            if os.path.exists(c_csv):
                try:
                    df = pd.read_csv(c_csv, keep_default_na=False)
                    updated = False
                    
                    for idx, row in df.iterrows():
                        c_name = str(row.get('Character', '')).strip()
                        if c_name in char_map:
                            global_info = char_map[c_name]
                            
                            df.at[idx, 'Age'] = global_info.get("age", "미상")
                            df.at[idx, 'Gender'] = global_info.get("gender", "미상")
                            df.at[idx, 'Role'] = global_info.get("role", "단역")
                            updated = True
                            
                    if updated:
                        df.to_csv(c_csv, index=False, encoding='utf-8-sig')
                        success_count += 1
                except Exception as e:
                    print(f"회차 '{ep_dir}' 동기화 오류: {e}")
                    error_count += 1
                    
        QMessageBox.information(self, "동기화 완료", 
                                f"총 {success_count}개 회차의 캐릭터 정보 동기화가 성공적으로 완료되었습니다.\n"
                                f"(실패 회차 수: {error_count})")

    def import_characters_from_html(self):
        html_path, _ = QFileDialog.getOpenFileName(
            self, 
            "캐릭터 HTML/MHTML 파일 열기", 
            "", 
            "HTML/MHTML 파일 (*.html *.htm *.mhtml *.mht)"
        )
        if not html_path:
            return
            
        # 토스트 메시지 표시 및 UI 업데이트 강제 실행
        from PySide6.QtWidgets import QApplication
        mw = self.parent()
        if not mw or not hasattr(mw, 'toast'):
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    mw = widget
                    break
        if mw and hasattr(mw, 'toast') and mw.toast is not None:
            mw.toast.show_message("⏳ 캐릭터 및 이미지를 가져오는 중...", 10000, fade_speed=0)
            QApplication.processEvents()
            
        html_content = ""
        image_parts = {}
        
        try:
            if html_path.lower().endswith(('.mhtml', '.mht')):
                with open(html_path, 'rb') as f:
                    msg = email.message_from_binary_file(f, policy=policy.default)
                
                for part in msg.walk():
                    content_type = part.get_content_type()
                    content_location = part.get("Content-Location", "")
                    content_id = part.get("Content-ID", "")
                    
                    if content_type == "text/html":
                        if not html_content:
                            html_bytes = part.get_payload(decode=True)
                            charset = part.get_content_charset() or "utf-8"
                            html_content = html_bytes.decode(charset, errors='ignore')
                    elif content_type.startswith("image/"):
                        img_bytes = part.get_payload(decode=True)
                        key = content_location or content_id
                        if key:
                            image_parts[key] = img_bytes
            else:
                with open(html_path, 'r', encoding='utf-8', errors='ignore') as f:
                    html_content = f.read()
        except Exception as e:
            QMessageBox.critical(self, "가져오기 오류", f"MHTML 파일을 디코딩하는 중 오류가 발생했습니다:\n{str(e)}")
            return
            
        div_pattern = re.compile(
            r'<div\b[^>]*class\s*=\s*[\"\'][^\"\']*character-image[^\"\']*[\"\'][^>]*>', 
            re.IGNORECASE
        )
        matches = list(div_pattern.finditer(html_content))
        
        if not matches:
            QMessageBox.warning(
                self, 
                "파싱 실패", 
                "선택한 파일에서 유효한 캐릭터 정보를 찾지 못했습니다.\n"
                "올바른 캐릭터 정보 페이지 HTML/MHTML 파일인지 확인해 주세요."
            )
            return
            
        role_map = {
            "CHARACTER_ROLE_STARRING": "주연",
            "CHARACTER_ROLE_SUPPORTING": "조연",
            "CHARACTER_ROLE_MINOR": "단역"
        }
        
        gender_map = {
            "CHARACTER_GENDER_MALE": "남성",
            "CHARACTER_GENDER_FEAMLE": "여성",
            "CHARACTER_GENDER_FEMALE": "여성",
            "CHARACTER_GENDER_UNKNOWN": "미상"
        }
        
        age_map = {
            "CHARACTER_AGE_CHILD": "어린이",
            "CHARACTER_AGE_YOUTH": "청소년",
            "CHARACTER_AGE_MIDDLE": "청년",
            "CHARACTER_AGE_ADULT": "중년",
            "CHARACTER_AGE_OLD": "노년",
            "CHARACTER_AGE_SENIOR": "노년",
            "CHARACTER_AGE_UNKNOWN": "미상"
        }
        
        PASTEL_COLORS = [
            "#3B82F6", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", 
            "#EC4899", "#06B6D4", "#F97316", "#14B8A6", "#84CC16"
        ]
        
        global_chars = config.load_global_characters(self.project_name)
        char_map = {char["name"]: char for char in global_chars if "name" in char}
        
        img_dir = os.path.join(config.PROJECTS_DIR, self.project_name, "character_images")
        os.makedirs(img_dir, exist_ok=True)
        
        imported_count = 0
        updated_count = 0
        
        for match in matches:
            div_tag = match.group(0)
            
            def get_attr(attr_name):
                m = re.search(fr'{attr_name}\s*=\s*[\"\']([^\"\']*)[\"\']', div_tag, re.IGNORECASE)
                return m.group(1).strip() if m else ""
                
            name = get_attr("name")
            if not name:
                continue
                
            is_new = name not in char_map
            
            html_role = get_attr("role")
            html_gender = get_attr("gender")
            html_age = get_attr("age")
            
            mapped_role = role_map.get(html_role, "단역")
            mapped_gender = gender_map.get(html_gender, "미상")
            mapped_age = age_map.get(html_age, "미상")
            
            start_pos = match.start()
            end_pos = min(len(html_content), start_pos + 1200)
            div_block = html_content[start_pos:end_pos]
            
            img_src_match = re.search(r'<img\b[^>]*src\s*=\s*[\"\']([^\"\']*)[\"\']', div_block, re.IGNORECASE)
            img_src = img_src_match.group(1).strip() if img_src_match else ""
            
            img_rel_path = ""
            img_data = None
            if img_src:
                if img_src in image_parts:
                    img_data = image_parts[img_src]
                else:
                    import urllib.parse
                    img_src_decoded = urllib.parse.unquote(img_src)
                    src_dir = os.path.dirname(html_path)
                    local_img_path = os.path.join(src_dir, img_src_decoded)
                    if os.path.exists(local_img_path):
                        try:
                            with open(local_img_path, 'rb') as im_f:
                                img_data = im_f.read()
                        except Exception as e:
                            print("Local image read error:", e)
                            
                if img_data:
                    unique_id = uuid.uuid4().hex[:8]
                    img_filename = f"{name}_{unique_id}.png"
                    img_abs_path = os.path.join(img_dir, img_filename)
                    try:
                        with open(img_abs_path, 'wb') as im_w:
                            im_w.write(img_data)
                        img_rel_path = f"character_images/{img_filename}"
                    except Exception as e:
                        print("Save imported image error:", e)
            
            if is_new:
                char_color = PASTEL_COLORS[len(global_chars) % len(PASTEL_COLORS)]
                new_char = {
                    "name": name,
                    "role": mapped_role,
                    "gender": mapped_gender,
                    "age": mapped_age,
                    "image_path": img_rel_path,
                    "color": char_color
                }
                global_chars.append(new_char)
                char_map[name] = new_char
                imported_count += 1
            else:
                existing_char = char_map[name]
                existing_char["role"] = mapped_role
                existing_char["gender"] = mapped_gender
                existing_char["age"] = mapped_age
                
                if img_rel_path:
                    existing_char["image_path"] = img_rel_path
                
                updated_count += 1
            
        config.save_global_characters(self.project_name, global_chars)
        self.load_characters()
        
        mw = self.parent()
        if not mw or not hasattr(mw, 'add_character_card'):
            for widget in QApplication.topLevelWidgets():
                if widget.__class__.__name__ == 'MainWindow':
                    mw = widget
                    break
                    
        if mw and hasattr(mw, 'load_project_characters'):
            mw.load_project_characters()
            
        QMessageBox.information(
            self, 
            "가져오기 완료", 
            f"캐릭터 정보 가져오기가 완료되었습니다!\n\n- 신규 추가: {imported_count}명\n- 업데이트(프로필 포함): {updated_count}명"
        )

# =================================================================
# ✂️ 이미지 크롭 위젯 (CropWidget)
# =================================================================
class CropWidget(QWidget):
    """원본 이미지를 축소 핏하여 뿌리고, 그 위에 1:1 비율 고정 크롭 박스를 마우스로 제어하는 명품 정사각형 위젯"""
    def __init__(self, pixmap, parent=None, initial_crop_rect=None):
        super().__init__(parent)
        self.original_pixmap = pixmap
        self.scaled_pixmap = QPixmap()
        self.scale_factor = 1.0
        
        self.crop_rect = QRect(0, 0, 100, 100)
        self.is_dragging = False
        self.is_resizing = False
        self.active_handle = None
        self.drag_start_pos = QPoint()
        self.crop_start_rect = QRect()
        
        self.setMouseTracking(True)
        self.init_scale(initial_crop_rect)

    def init_scale(self, initial_crop_rect=None):
        if self.original_pixmap.isNull():
            return
            
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        
        target_w = 400
        ratio = target_w / orig_w
            
        self.scale_factor = ratio
        new_w = target_w
        new_h = int(orig_h * ratio)
        
        self.scaled_pixmap = self.original_pixmap.scaled(
            new_w, new_h, Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
        self.setFixedSize(new_w, new_h)
        
        if initial_crop_rect:
            rx, ry, rw, rh = initial_crop_rect
            
            # 1. 만약 저장된 크롭 영역이 현재 원본 이미지 크기보다 크다면 (예: 고해상도 상태에서 저장됨)
            # 이미지 비율에 맞춰 자동으로 크롭 영역 좌표를 축소 조절합니다.
            if rx + rw > orig_w or ry + rh > orig_h:
                scale_x = orig_w / (rx + rw) if (rx + rw) > 0 else 1.0
                scale_y = orig_h / (ry + rh) if (ry + rh) > 0 else 1.0
                scale = min(scale_x, scale_y)
                if scale < 1.0:
                    rx = int(rx * scale)
                    ry = int(ry * scale)
                    rw = int(rw * scale)
                    rh = int(rh * scale)
            
            # 2. 안전하게 이미지 경계 내로 클램핑
            rx = max(0, min(rx, orig_w - 1))
            ry = max(0, min(ry, orig_h - 1))
            rw = max(1, min(rw, orig_w - rx))
            rh = max(1, min(rh, orig_h - ry))
            
            crop_size_orig = min(rw, rh)
            
            # 최종 예외 처리: 크기가 너무 작아지면 기본값으로 처리
            if crop_size_orig < 5:
                crop_size = int(min(new_w, new_h) * 0.75)
                crop_size = max(crop_size, 80)
                cx = (new_w - crop_size) // 2
                cy = (new_h - crop_size) // 2
                self.crop_rect = QRect(cx, cy, crop_size, crop_size)
            else:
                cx = int(rx * ratio)
                cy = int(ry * ratio)
                cw = int(crop_size_orig * ratio)
                ch = cw
                cw = max(40, min(cw, new_w, new_h))
                ch = cw
                cx = max(0, min(cx, new_w - cw))
                cy = max(0, min(cy, new_h - ch))
                self.crop_rect = QRect(cx, cy, cw, ch)
        else:
            crop_size = int(min(new_w, new_h) * 0.75)
            crop_size = max(crop_size, 80)
            
            cx = (new_w - crop_size) // 2
            cy = (new_h - crop_size) // 2
            self.crop_rect = QRect(cx, cy, crop_size, crop_size)

    def paintEvent(self, event):
        if self.scaled_pixmap.isNull():
            return
            
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)
        
        painter.drawPixmap(0, 0, self.scaled_pixmap)
        
        from PySide6.QtGui import QPainterPath
        outer_path = QPainterPath()
        outer_path.addRect(QRectF(self.rect()))
        
        inner_path = QPainterPath()
        inner_path.addRect(QRectF(self.crop_rect))
        
        mask_path = outer_path.subtracted(inner_path)
        
        painter.fillPath(mask_path, QColor(0, 0, 0, 145))
        
        pen = QPen(QColor("#FF4B4B"), 1.8, Qt.SolidLine)
        painter.setPen(pen)
        painter.drawRect(self.crop_rect)
        
        grid_pen = QPen(QColor(255, 75, 75, 70), 1.0, Qt.DashLine)
        painter.setPen(grid_pen)
        step = self.crop_rect.width() // 3
        
        painter.drawLine(self.crop_rect.x() + step, self.crop_rect.y(), self.crop_rect.x() + step, self.crop_rect.bottom())
        painter.drawLine(self.crop_rect.x() + step * 2, self.crop_rect.y(), self.crop_rect.x() + step * 2, self.crop_rect.bottom())
        painter.drawLine(self.crop_rect.x(), self.crop_rect.y() + step, self.crop_rect.right(), self.crop_rect.y() + step)
        painter.drawLine(self.crop_rect.x(), self.crop_rect.y() + step * 2, self.crop_rect.right(), self.crop_rect.y() + step * 2)
        
        anchor_pen = QPen(QColor("#FF4B4B"), 3.5, Qt.SolidLine, Qt.SquareCap, Qt.MiterJoin)
        painter.setPen(anchor_pen)
        r = self.crop_rect
        L_len = min(15, r.width() // 4)
        
        painter.drawLine(r.x(), r.y(), r.x() + L_len, r.y())
        painter.drawLine(r.x(), r.y(), r.x(), r.y() + L_len)
        painter.drawLine(r.right(), r.y(), r.right() - L_len, r.y())
        painter.drawLine(r.right(), r.y(), r.right(), r.y() + L_len)
        painter.drawLine(r.x(), r.bottom(), r.x() + L_len, r.bottom())
        painter.drawLine(r.x(), r.bottom(), r.x(), r.bottom() - L_len)
        painter.drawLine(r.right(), r.bottom(), r.right() - L_len, r.bottom())
        painter.drawLine(r.right(), r.bottom(), r.right(), r.bottom() - L_len)

    def get_handle_at(self, pos):
        px, py = pos.x(), pos.y()
        
        tl = self.crop_rect.topLeft()
        tr = self.crop_rect.topRight()
        bl = self.crop_rect.bottomLeft()
        br = self.crop_rect.bottomRight()
        
        tol = 16
        if (pos - tl).manhattanLength() <= tol:
            return 'TL'
        if (pos - tr).manhattanLength() <= tol:
            return 'TR'
        if (pos - bl).manhattanLength() <= tol:
            return 'BL'
        if (pos - br).manhattanLength() <= tol:
            return 'BR'
            
        edge_tol = 8
        rect = self.crop_rect
        if abs(py - rect.top()) <= edge_tol and rect.left() <= px <= rect.right():
            return 'T'
        if abs(py - rect.bottom()) <= edge_tol and rect.left() <= px <= rect.right():
            return 'B'
        if abs(px - rect.left()) <= edge_tol and rect.top() <= py <= rect.bottom():
            return 'L'
        if abs(px - rect.right()) <= edge_tol and rect.top() <= py <= rect.bottom():
            return 'R'
            
        if rect.contains(pos):
            return 'MOVE'
            
        return None

    def mousePressEvent(self, event):
        pos = event.position().toPoint()
        handle = self.get_handle_at(pos)
        
        if handle in ('TL', 'TR', 'BL', 'BR', 'T', 'B', 'L', 'R'):
            self.is_resizing = True
            self.active_handle = handle
            self.drag_start_pos = pos
            self.crop_start_rect = QRect(self.crop_rect)
            
            if handle in ('TL', 'BR'):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ('TR', 'BL'):
                self.setCursor(Qt.SizeBDiagCursor)
            elif handle in ('T', 'B'):
                self.setCursor(Qt.SizeVerCursor)
            elif handle in ('L', 'R'):
                self.setCursor(Qt.SizeHorCursor)
                
        elif handle == 'MOVE':
            self.is_dragging = True
            self.active_handle = 'MOVE'
            self.drag_start_pos = pos
            self.crop_start_rect = QRect(self.crop_rect)
            self.setCursor(Qt.SizeAllCursor)

    def mouseMoveEvent(self, event):
        pos = event.position().toPoint()
        
        if not self.is_dragging and not self.is_resizing:
            handle = self.get_handle_at(pos)
            if handle in ('TL', 'BR'):
                self.setCursor(Qt.SizeFDiagCursor)
            elif handle in ('TR', 'BL'):
                self.setCursor(Qt.SizeBDiagCursor)
            elif handle in ('T', 'B'):
                self.setCursor(Qt.SizeVerCursor)
            elif handle in ('L', 'R'):
                self.setCursor(Qt.SizeHorCursor)
            elif handle == 'MOVE':
                self.setCursor(Qt.SizeAllCursor)
            else:
                self.setCursor(Qt.ArrowCursor)
            return

        if self.is_resizing:
            px, py = pos.x(), pos.y()
            rect = self.crop_start_rect
            
            if self.active_handle == 'BR':
                ax, ay = rect.x(), rect.y()
                new_size = px - ax
                new_size = max(60, new_size)
                new_size = min(new_size, self.width() - ax, self.height() - ay)
                self.crop_rect = QRect(ax, ay, new_size, new_size)
                
            elif self.active_handle == 'TL':
                ax, ay = rect.right(), rect.bottom()
                new_size = ax - px
                new_size = max(60, new_size)
                new_size = min(new_size, ax, ay)
                self.crop_rect = QRect(ax - new_size, ay - new_size, new_size, new_size)
                
            elif self.active_handle == 'TR':
                ax, ay = rect.x(), rect.bottom()
                new_size = px - ax
                new_size = max(60, new_size)
                new_size = min(new_size, self.width() - ax, ay)
                self.crop_rect = QRect(ax, ay - new_size, new_size, new_size)
                
            elif self.active_handle == 'BL':
                ax, ay = rect.right(), rect.y()
                new_size = ax - px
                new_size = max(60, new_size)
                new_size = min(new_size, ax, self.height() - ay)
                self.crop_rect = QRect(ax - new_size, ay, new_size, new_size)
                
            elif self.active_handle == 'R':
                new_w = px - rect.left()
                new_w = max(60, new_w)
                max_half_delta = min(rect.top(), self.height() - rect.bottom())
                new_w = min(new_w, self.width() - rect.left(), rect.width() + 2 * max_half_delta)
                half_delta = (new_w - rect.width()) // 2
                self.crop_rect = QRect(rect.left(), rect.top() - half_delta, new_w, new_w)
                
            elif self.active_handle == 'L':
                new_w = rect.right() - px
                new_w = max(60, new_w)
                max_half_delta = min(rect.top(), self.height() - rect.bottom())
                new_w = min(new_w, rect.right(), rect.width() + 2 * max_half_delta)
                half_delta = (new_w - rect.width()) // 2
                self.crop_rect = QRect(rect.right() - new_w, rect.top() - half_delta, new_w, new_w)
                
            elif self.active_handle == 'B':
                new_h = py - rect.top()
                new_h = max(60, new_h)
                max_half_delta = min(rect.left(), self.width() - rect.right())
                new_h = min(new_h, self.height() - rect.top(), rect.height() + 2 * max_half_delta)
                half_delta = (new_h - rect.height()) // 2
                self.crop_rect = QRect(rect.left() - half_delta, rect.top(), new_h, new_h)
                
            elif self.active_handle == 'T':
                new_h = rect.bottom() - py
                new_h = max(60, new_h)
                max_half_delta = min(rect.left(), self.width() - rect.right())
                new_h = min(new_h, rect.bottom(), rect.height() + 2 * max_half_delta)
                half_delta = (new_h - rect.height()) // 2
                self.crop_rect = QRect(rect.left() - half_delta, rect.bottom() - new_h, new_h, new_h)
                
            self.update()

        elif self.is_dragging:
            delta = pos - self.drag_start_pos
            new_x = self.crop_start_rect.x() + delta.x()
            new_y = self.crop_start_rect.y() + delta.y()
            
            new_x = max(0, min(new_x, self.width() - self.crop_rect.width()))
            new_y = max(0, min(new_y, self.height() - self.crop_rect.height()))
            
            self.crop_rect.moveTo(new_x, new_y)
            self.update()

    def mouseReleaseEvent(self, event):
        self.is_dragging = False
        self.is_resizing = False
        self.active_handle = None
        self.setCursor(Qt.ArrowCursor)

    def get_cropped_pixmap(self):
        if self.original_pixmap.isNull():
            return QPixmap()
            
        inv_scale = 1.0 / self.scale_factor
        
        rx = int(self.crop_rect.x() * inv_scale)
        ry = int(self.crop_rect.y() * inv_scale)
        rw = int(self.crop_rect.width() * inv_scale)
        rh = int(self.crop_rect.height() * inv_scale)
        
        rx = max(0, rx)
        ry = max(0, ry)
        rw = min(rw, self.original_pixmap.width() - rx)
        rh = min(rh, self.original_pixmap.height() - ry)
        
        cropped = self.original_pixmap.copy(rx, ry, rw, rh)
        return cropped.scaled(150, 150, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)

    def get_crop_rect_coords(self):
        if self.original_pixmap.isNull():
            return None
            
        inv_scale = 1.0 / self.scale_factor
        
        rx = int(self.crop_rect.x() * inv_scale)
        ry = int(self.crop_rect.y() * inv_scale)
        rw = int(self.crop_rect.width() * inv_scale)
        rh = int(self.crop_rect.height() * inv_scale)
        
        orig_w = self.original_pixmap.width()
        orig_h = self.original_pixmap.height()
        
        rx = max(0, min(rx, orig_w - 1))
        ry = max(0, min(ry, orig_h - 1))
        rw = max(1, min(rw, orig_w - rx))
        rh = max(1, min(rh, orig_h - ry))
        
        crop_size = min(rw, rh)
        return [rx, ry, crop_size, crop_size]

# =================================================================
# ✂️ 이미지 크롭 다이얼로그 (ImageCropDialog)
# =================================================================
class ImageCropDialog(QDialog):
    """인물 사진 등록 시, 얼굴 영역만 1:1 정사각형 비율로 정밀 드래그 지정하는 모던 크롭/선택 다이얼로그"""
    def __init__(self, file_path, parent=None, initial_crop_rect=None):
        super().__init__(parent)
        self.setWindowTitle("👤 프로필 이미지 표시 영역 지정 (1:1)")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint)
        self.setStyleSheet("background-color: #FFFFFF;")
        
        self.original_pixmap = QPixmap(file_path)
        self.cropped_pixmap = QPixmap()
        self.crop_rect_coords = None
        self.initial_crop_rect = initial_crop_rect
        
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(10)
        
        title_lbl = QLabel(
            "<div style='line-height: 140%;'>"
            "<span style='font-size: 15px; font-weight: bold; color: #111827;'>👤 프로필용 이미지 영역 지정하기</span><br>"
            "<span style='font-size: 11px; color: #6B7280; font-weight: normal;'>"
            "상자 안을 마우스로 드래그해 이동하고, 모서리나 사방의 변을 끌어<br>"
            "얼굴이 중앙에 오는 최상의 구도로 조절해 주세요 (1:1 비율 고정).</span>"
            "</div>"
        )
        title_lbl.setStyleSheet("margin: 0px; padding: 0px; border: none; background: transparent;")
        layout.addWidget(title_lbl)
        
        self.crop_container = QHBoxLayout()
        self.crop_container.addStretch()
        
        self.crop_widget = CropWidget(self.original_pixmap, self, self.initial_crop_rect)
        self.crop_container.addWidget(self.crop_widget)
        
        self.crop_container.addStretch()
        layout.addLayout(self.crop_container)
        
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)
        btn_layout.addStretch()
        
        btn_cancel = QPushButton("취소")
        btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 7px 16px;
                font-weight: bold;
                color: #4B5563;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
            }
        """)
        btn_cancel.clicked.connect(self.reject)
        
        btn_apply = QPushButton("크롭 적용")
        btn_apply.setStyleSheet("""
            QPushButton {
                background-color: #FF4B4B;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 7px 18px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #E03E3E;
            }
        """)
        btn_apply.clicked.connect(self.on_apply)
        
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_apply)
        layout.addLayout(btn_layout)
        
        img_h = self.crop_widget.height() if self.crop_widget else 300
        dialog_w = 540
        dialog_h = max(350, img_h + 135)
        self.resize(dialog_w, dialog_h)
 
    def on_apply(self):
        self.cropped_pixmap = self.crop_widget.get_cropped_pixmap()
        self.crop_rect_coords = self.crop_widget.get_crop_rect_coords()
        self.accept()


# =================================================================
# 🖼️ 캐릭터 프로필 이미지 중복 교체 확인 다이얼로그 (ProfileImageOverwriteDialog)
# =================================================================
class ProfileImageOverwriteDialog(QDialog):
    """글로벌 캐릭터 마이그레이션 중 기존 이미지가 존재할 때 교체할지 묻는 다이얼로그"""
    def __init__(self, parent=None, char_name="", current_img_path="", new_pixmap=None):
        super().__init__(parent)
        self.char_name = char_name
        self.current_img_path = current_img_path
        self.new_pixmap = new_pixmap
        
        self.setWindowTitle("프로필 이미지 교체 확인")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        
        self.init_ui()
        
    def init_ui(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #FFFFFF;
            }
            QLabel {
                font-family: 'Pretendard', '-apple-system', 'Helvetica Neue', 'Segoe UI', sans-serif;
            }
        """)
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)
        
        # 상단 헤더 / 설명
        header_layout = QVBoxLayout()
        header_layout.setSpacing(6)
        
        title_lbl = QLabel(f"<span style='font-size: 16px; font-weight: bold; color: #1F2937;'>'{self.char_name}' 캐릭터의 프로필 이미지 교체</span>")
        desc_lbl = QLabel("<span style='font-size: 13px; color: #4B5563; line-height: 140%;'>이미 기존에 직접 추가된 프로필 이미지가 존재합니다.<br>마이그레이션되는 새 이미지로 교체하시겠습니까?</span>")
        desc_lbl.setWordWrap(True)
        
        header_layout.addWidget(title_lbl)
        header_layout.addWidget(desc_lbl)
        main_layout.addLayout(header_layout)
        
        # 이미지 가로 레이아웃
        images_layout = QHBoxLayout()
        images_layout.setSpacing(20)
        images_layout.setAlignment(Qt.AlignCenter)
        
        # 1. 기존 이미지 컨테이너
        current_container = QVBoxLayout()
        current_container.setSpacing(8)
        current_container.setAlignment(Qt.AlignCenter)
        
        lbl_current_title = QLabel("<span style='font-size: 11px; font-weight: bold; color: #6B7280;'>현재 프로필 이미지</span>")
        lbl_current_title.setAlignment(Qt.AlignCenter)
        
        lbl_current_img = QLabel()
        lbl_current_img.setFixedSize(150, 150)
        lbl_current_img.setStyleSheet("border: none; background: transparent;")
        
        pix_current = None
        if self.current_img_path and os.path.exists(self.current_img_path):
            pix_current = QPixmap(self.current_img_path)
            
        if pix_current and not pix_current.isNull():
            lbl_current_img.setPixmap(get_round_rect_pixmap(pix_current, 150, 150, 12))
        else:
            lbl_current_img.setPixmap(self.get_avatar_placeholder())
            
        current_container.addWidget(lbl_current_title)
        current_container.addWidget(lbl_current_img)
        
        # 2. 화살표
        arrow_lbl = QLabel("<span style='font-size: 24px; color: #9CA3AF;'>➔</span>")
        arrow_lbl.setAlignment(Qt.AlignCenter)
        
        # 3. 새 이미지 컨테이너
        new_container = QVBoxLayout()
        new_container.setSpacing(8)
        new_container.setAlignment(Qt.AlignCenter)
        
        lbl_new_title = QLabel("<span style='font-size: 11px; font-weight: bold; color: #3B82F6;'>적용되는 새 이미지</span>")
        lbl_new_title.setAlignment(Qt.AlignCenter)
        
        lbl_new_img = QLabel()
        lbl_new_img.setFixedSize(150, 150)
        lbl_new_img.setStyleSheet("border: none; background: transparent;")
        
        if self.new_pixmap and not self.new_pixmap.isNull():
            lbl_new_img.setPixmap(get_round_rect_pixmap(self.new_pixmap, 150, 150, 12))
        else:
            lbl_new_img.setPixmap(self.get_avatar_placeholder())
            
        new_container.addWidget(lbl_new_title)
        new_container.addWidget(lbl_new_img)
        
        images_layout.addLayout(current_container)
        images_layout.addWidget(arrow_lbl)
        images_layout.addLayout(new_container)
        
        main_layout.addLayout(images_layout)
        
        # 구분선
        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        sep.setFrameShadow(QFrame.Sunken)
        sep.setStyleSheet("color: #F3F4F6;")
        main_layout.addWidget(sep)
        
        # 하단 버튼부
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(8)
        
        # 왼쪽 버튼 그룹: 유지 관련
        btn_keep_all = QPushButton("모두 유지")
        btn_keep_all.setCursor(Qt.PointingHandCursor)
        btn_keep_all.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
                color: #6B7280;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
                color: #374151;
            }
        """)
        btn_keep_all.clicked.connect(lambda: self.done(13))
        
        btn_keep = QPushButton("유지")
        btn_keep.setCursor(Qt.PointingHandCursor)
        btn_keep.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                color: #374151;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #F9FAFB;
                border-color: #9CA3AF;
            }
        """)
        btn_keep.clicked.connect(lambda: self.done(11))
        
        btn_layout.addWidget(btn_keep_all)
        btn_layout.addWidget(btn_keep)
        
        btn_layout.addStretch()
        
        # 오른쪽 버튼 그룹: 교체 관련
        btn_replace = QPushButton("교체")
        btn_replace.setCursor(Qt.PointingHandCursor)
        btn_replace.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 8px 18px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #2563EB;
            }
        """)
        btn_replace.clicked.connect(lambda: self.done(10))
        
        btn_replace_all = QPushButton("모두 교체")
        btn_replace_all.setCursor(Qt.PointingHandCursor)
        btn_replace_all.setStyleSheet("""
            QPushButton {
                background-color: #E0E7FF;
                color: #4338CA;
                border: 1px solid #C7D2FE;
                border-radius: 6px;
                padding: 8px 14px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover {
                background-color: #C7D2FE;
                color: #3730A3;
            }
        """)
        btn_replace_all.clicked.connect(lambda: self.done(12))
        
        btn_layout.addWidget(btn_replace)
        btn_layout.addWidget(btn_replace_all)
        
        main_layout.addLayout(btn_layout)
        
        self.adjustSize()
        
    def get_avatar_placeholder(self, w=150, h=150, radius=12):
        """150x150 크기의 부드럽고 보기 좋은 기본 아바타 플레이스홀더를 동적으로 생성"""
        return get_default_avatar_pixmap(w, h, radius)

