# widgets/verification_dialog.py
import os
import json
import re
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QSplitter, QTextEdit, QComboBox, QCheckBox, QFrame,
    QLineEdit, QProgressBar, QSizePolicy, QApplication, QMessageBox,
    QMenu, QGraphicsDropShadowEffect
)
from PySide6.QtCore import Qt, Signal, QPoint, QRect, QSize, QTimer, QEvent
from PySide6.QtGui import (
    QPixmap, QPainter, QColor, QPen, QBrush, QFont, QCursor, QIcon,
    QFontMetrics
)

import config
from utils import (
    get_icon, get_colored_icon, get_colored_pixmap,
    load_ocr_boxes, save_ocr_boxes, natural_sort_key
)
from .common import ZoomBadge, HoverIconButton
from .dialogs import get_episode_images


# =================================================================
# 1. 인라인 대사 편집 에디터 (Enter=다음, Shift+Enter=줄바꿈)
# =================================================================
class VerificationTextEdit(QTextEdit):
    enter_pressed = Signal()
    navigate_up = Signal()
    navigate_down = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFont(QFont("Pretendard", 11))
        self.setFixedHeight(56)
        self.setStyleSheet("""
            QTextEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 6px 8px;
                background-color: #FFFFFF;
                color: #111827;
                font-size: 14px;
                line-height: 1.4;
            }
            QTextEdit:focus {
                border: 2px solid #2563EB;
                background-color: #FFFFFF;
            }
        """)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                super().keyPressEvent(event)
            else:
                self.enter_pressed.emit()
                event.accept()
                return
        elif event.key() == Qt.Key_Up:
            cursor = self.textCursor()
            if cursor.blockNumber() == 0:
                self.navigate_up.emit()
                event.accept()
                return
            super().keyPressEvent(event)
        elif event.key() == Qt.Key_Down:
            cursor = self.textCursor()
            doc = self.document()
            if cursor.blockNumber() >= doc.blockCount() - 1:
                self.navigate_down.emit()
                event.accept()
                return
            super().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


# =================================================================
# 2. 이미지 위 말풍선 렌더링 & 인터랙션 라벨
# =================================================================
class VerificationImageLabel(QLabel):
    box_clicked = Signal(dict)
    new_box_created = Signal(int, list)  # (image_index, [x1, y1, x2, y2])

    def __init__(self, img_path, image_index, parent=None):
        super().__init__(parent)
        self.img_path = img_path
        self.image_index = image_index
        self.original_pixmap = QPixmap(img_path)
        self.setPixmap(self.original_pixmap)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setMouseTracking(True)

        self.items = []
        self.active_item_id = None
        self.show_badges = True

        self._is_selecting = False
        self._select_start = QPoint()
        self._select_current = QPoint()
        self._is_resizing = False

    def minimumSizeHint(self):
        return QSize(400, 200)

    def sizeHint(self):
        if not self.original_pixmap.isNull() and self.original_pixmap.width() > 0:
            return QSize(700, int(700 * (self.original_pixmap.height() / self.original_pixmap.width())))
        return QSize(700, 1000)

    def resizeEvent(self, event):
        if not self._is_resizing and not self.original_pixmap.isNull() and self.width() > 0:
            aspect_ratio = self.original_pixmap.height() / self.original_pixmap.width()
            target_height = int(self.width() * aspect_ratio)
            if self.height() != target_height:
                self._is_resizing = True
                self.setFixedHeight(target_height)
                self._is_resizing = False
        super().resizeEvent(event)

    def set_items(self, all_items, active_id=None, show_badges=True):
        self.items = [item for item in all_items if item.get('image_index') == self.image_index]
        self.active_item_id = active_id
        self.show_badges = show_badges
        self.update()

    def _get_item_rect(self, item):
        """원본 이미지 픽셀 좌표를 현재 라벨 디스플레이 좌표계로 변환"""
        if self.original_pixmap.isNull() or self.original_pixmap.width() <= 0:
            return QRect()
        scale_x = self.width() / float(self.original_pixmap.width())
        scale_y = self.height() / float(self.original_pixmap.height())
        box = item.get('box', [0, 0, 100, 100])
        rx = int(box[0] * scale_x)
        ry = int(box[1] * scale_y)
        rw = max(10, int((box[2] - box[0]) * scale_x))
        rh = max(10, int((box[3] - box[1]) * scale_y))
        return QRect(rx, ry, rw, rh)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.original_pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        badge_font = QFont("Pretendard", 9, QFont.Bold)
        painter.setFont(badge_font)

        # 1. 말풍선 박스 및 뱃지 그리기
        for item in self.items:
            rect = self._get_item_rect(item)
            if rect.isEmpty():
                continue

            item_id = item.get('id', 0)
            is_active = (item_id == self.active_item_id)
            is_verified = item.get('is_verified', False)

            if is_active:
                pen = QPen(QColor("#2563EB"), 3, Qt.SolidLine)
                brush = QBrush(QColor(37, 99, 235, 55))
                badge_bg = QColor("#2563EB")
            elif is_verified:
                pen = QPen(QColor("#10B981"), 2, Qt.SolidLine)
                brush = QBrush(QColor(16, 185, 129, 30))
                badge_bg = QColor("#10B981")
            else:
                pen = QPen(QColor("#8B5CF6"), 2, Qt.SolidLine)
                brush = QBrush(QColor(139, 92, 246, 25))
                badge_bg = QColor("#8B5CF6")

            # 바운딩 박스 사각형 그리기
            painter.setPen(pen)
            painter.setBrush(brush)
            painter.drawRoundedRect(rect, 4, 4)

            # 뱃지 번호 라벨 그리기
            if self.show_badges:
                badge_text = f"#{item_id} ✓" if is_verified else f"#{item_id}"
                fm = QFontMetrics(badge_font)
                text_w = fm.horizontalAdvance(badge_text) + 10
                text_h = 18

                bx = rect.x()
                by = max(2, rect.y() - text_h - 2)
                badge_rect = QRect(bx, by, text_w, text_h)

                painter.setPen(Qt.NoPen)
                painter.setBrush(QBrush(badge_bg))
                painter.drawRoundedRect(badge_rect, 4, 4)

                painter.setPen(QColor("#FFFFFF"))
                painter.drawText(badge_rect, Qt.AlignCenter, badge_text)

        # 2. 마우스 드래그로 영역 생성 중인 경우
        if self._is_selecting:
            sel_rect = QRect(self._select_start, self._select_current).normalized()
            painter.setPen(QPen(QColor("#F97316"), 2, Qt.DashLine))
            painter.setBrush(QBrush(QColor(249, 115, 22, 55)))
            painter.drawRect(sel_rect)

        painter.end()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            pos = event.pos()
            # 1. 클릭 위치가 기존 박스 위인지 확인
            clicked_item = None
            for item in reversed(self.items):  # 위에 그려진 것 우선
                rect = self._get_item_rect(item)
                if rect.contains(pos):
                    clicked_item = item
                    break

            if clicked_item:
                self.box_clicked.emit(clicked_item)
                event.accept()
                return

            # 2. 빈 공간 클릭 시 드래그 영역 생성 시작
            self._is_selecting = True
            self._select_start = pos
            self._select_current = pos
            self.update()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._is_selecting:
            self._select_current = event.pos()
            self.update()
            event.accept()
            return
        else:
            # 호버 시 마우스 커서 변화
            pos = event.pos()
            hovering_box = any(self._get_item_rect(item).contains(pos) for item in self.items)
            if hovering_box:
                self.setCursor(Qt.PointingHandCursor)
            else:
                self.setCursor(Qt.CrossCursor)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._is_selecting and event.button() == Qt.LeftButton:
            self._is_selecting = False
            rect = QRect(self._select_start, self._select_current).normalized()
            self.update()

            if rect.width() >= 15 and rect.height() >= 15:
                if self.original_pixmap.width() > 0 and self.original_pixmap.height() > 0:
                    scale_x = self.width() / float(self.original_pixmap.width())
                    scale_y = self.height() / float(self.original_pixmap.height())
                    ox1 = int(rect.x() / scale_x)
                    oy1 = int(rect.y() / scale_y)
                    ox2 = int((rect.x() + rect.width()) / scale_x)
                    oy2 = int((rect.y() + rect.height()) / scale_y)
                    self.new_box_created.emit(self.image_index, [ox1, oy1, ox2, oy2])
            event.accept()
            return
        super().mouseReleaseEvent(event)


# =================================================================
# 3. 우측 대사 카드 위젯
# =================================================================
class VerificationCardWidget(QFrame):
    clicked = Signal(dict)
    text_changed = Signal(dict, str)
    character_changed = Signal(dict, str)
    verified_toggled = Signal(dict, bool)
    request_split = Signal(dict)
    request_delete = Signal(dict)
    enter_next = Signal(dict)
    navigate_up = Signal(dict)
    navigate_down = Signal(dict)

    def __init__(self, item, characters=None, parent=None):
        super().__init__(parent)
        self.item = item
        self.characters = characters or []
        self.is_active = False

        self.setFrameShape(QFrame.StyledPanel)
        self.setup_ui()
        self.update_style()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(8)

        # 1. 상단 정보 바 (순번, 캐릭터 선택, 검수 상태, 퀵 버튼)
        top_layout = QHBoxLayout()
        top_layout.setSpacing(8)

        # 순번 뱃지
        self.lbl_id = QLabel(f"#{self.item.get('id', 0)}")
        self.lbl_id.setFixedWidth(36)
        self.lbl_id.setAlignment(Qt.AlignCenter)
        self.lbl_id.setStyleSheet("""
            QLabel {
                background-color: #EEF2F6;
                color: #374151;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
                padding: 3px 0px;
            }
        """)
        top_layout.addWidget(self.lbl_id)

        # 캐릭터 콤보박스
        self.combo_char = QComboBox()
        self.combo_char.setEditable(True)
        self.combo_char.setMinimumWidth(110)
        self.combo_char.setMaximumWidth(150)
        self.combo_char.setFont(QFont("Pretendard", 10))
        self.combo_char.setStyleSheet("""
            QComboBox {
                border: 1px solid #D1D5DB;
                border-radius: 4px;
                padding: 2px 6px;
                background: white;
                font-size: 13px;
            }
        """)
        self.combo_char.addItem("지정 안 됨")
        for c in self.characters:
            if c:
                self.combo_char.addItem(c)
        curr_char = self.item.get('character', '')
        if curr_char and curr_char in self.characters:
            self.combo_char.setCurrentText(curr_char)
        elif curr_char:
            self.combo_char.addItem(curr_char)
            self.combo_char.setCurrentText(curr_char)
        else:
            self.combo_char.setCurrentIndex(0)
        self.combo_char.currentTextChanged.connect(self._on_char_changed)
        top_layout.addWidget(self.combo_char)

        # 검수 완료 체크박스
        self.chk_verified = QCheckBox("검수 완료")
        self.chk_verified.setFont(QFont("Pretendard", 10, QFont.Medium))
        self.chk_verified.setChecked(self.item.get('is_verified', False))
        self.chk_verified.setStyleSheet("""
            QCheckBox {
                color: #4B5563;
                font-size: 13px;
                spacing: 5px;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox:checked {
                color: #059669;
                font-weight: bold;
            }
        """)
        self.chk_verified.toggled.connect(self._on_verified_toggled)
        top_layout.addWidget(self.chk_verified)

        top_layout.addStretch()

        # 도구 버튼들 (분할, 삭제)
        btn_split = HoverIconButton("", config.ICON_CUT, normal_color="#64748B", hover_color="#2563EB")
        btn_split.setToolTip("대사 2개로 분할")
        btn_split.setFixedSize(26, 26)
        btn_split.setIconSize(QSize(15, 15))
        btn_split.setStyleSheet("""
            QPushButton {
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                background-color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                border-color: #93C5FD;
            }
        """)
        btn_split.clicked.connect(lambda: self.request_split.emit(self.item))
        top_layout.addWidget(btn_split)

        btn_del = HoverIconButton("", config.ICON_DELETE, normal_color="#94A3B8", hover_color="#EF4444")
        btn_del.setToolTip("대사 삭제")
        btn_del.setFixedSize(26, 26)
        btn_del.setIconSize(QSize(15, 15))
        btn_del.setStyleSheet("""
            QPushButton {
                border: 1px solid #E2E8F0;
                border-radius: 4px;
                background-color: #FFFFFF;
            }
            QPushButton:hover {
                background-color: #FEF2F2;
                border-color: #FCA5A5;
            }
        """)
        btn_del.clicked.connect(lambda: self.request_delete.emit(self.item))
        top_layout.addWidget(btn_del)

        layout.addLayout(top_layout)

        # 2. 대사 편집 입력창
        self.txt_dialogue = VerificationTextEdit()
        self.txt_dialogue.setPlainText(self.item.get('text', ''))
        self.txt_dialogue.textChanged.connect(self._on_text_changed)
        self.txt_dialogue.enter_pressed.connect(lambda: self.enter_next.emit(self.item))
        self.txt_dialogue.navigate_up.connect(lambda: self.navigate_up.emit(self.item))
        self.txt_dialogue.navigate_down.connect(lambda: self.navigate_down.emit(self.item))
        layout.addWidget(self.txt_dialogue)

    def _on_text_changed(self):
        new_text = self.txt_dialogue.toPlainText()
        self.item['text'] = new_text
        self.text_changed.emit(self.item, new_text)

    def _on_char_changed(self, text):
        val = "" if text == "지정 안 됨" else text.strip()
        self.item['character'] = val
        self.character_changed.emit(self.item, val)

    def _on_verified_toggled(self, checked):
        self.item['is_verified'] = checked
        self.verified_toggled.emit(self.item, checked)
        self.update_style()

    def set_active(self, active):
        self.is_active = active
        self.update_style()
        if active:
            self.txt_dialogue.setFocus()
            cursor = self.txt_dialogue.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            self.txt_dialogue.setTextCursor(cursor)

    def update_style(self):
        if self.is_active:
            self.setStyleSheet("""
                VerificationCardWidget {
                    background-color: #EFF6FF;
                    border: 2px solid #2563EB;
                    border-radius: 8px;
                }
            """)
            self.lbl_id.setStyleSheet("""
                QLabel {
                    background-color: #2563EB;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    padding: 3px 0px;
                }
            """)
        elif self.item.get('is_verified', False):
            self.setStyleSheet("""
                VerificationCardWidget {
                    background-color: #F0FDF4;
                    border: 1px solid #86EFAC;
                    border-radius: 8px;
                }
            """)
            self.lbl_id.setStyleSheet("""
                QLabel {
                    background-color: #10B981;
                    color: white;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    padding: 3px 0px;
                }
            """)
        else:
            self.setStyleSheet("""
                VerificationCardWidget {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                }
                VerificationCardWidget:hover {
                    border: 1px solid #CBD5E1;
                    background-color: #F8FAFC;
                }
            """)
            self.lbl_id.setStyleSheet("""
                QLabel {
                    background-color: #EEF2F6;
                    color: #374151;
                    font-weight: bold;
                    font-size: 12px;
                    border-radius: 4px;
                    padding: 3px 0px;
                }
            """)

    def mousePressEvent(self, event):
        self.clicked.emit(self.item)
        super().mousePressEvent(event)


# =================================================================
# 4. 검수 모달 전용 줌/패닝 스크롤 영역
# =================================================================
class VerificationScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.zoom_badge = ZoomBadge(self.viewport())

        self.zoom_factor = 1.0
        self.min_zoom = 1.0
        self.max_zoom = 5.0

        self._is_panning = False
        self._pan_start_pos = QPoint()
        self._pan_start_h = 0
        self._pan_start_v = 0

        self.setStyleSheet("""
            QScrollArea { background-color: #1E293B; border: none; }
            QScrollBar:vertical {
                border: none;
                background: #0F172A;
                width: 10px;
            }
            QScrollBar::handle:vertical {
                background: #475569;
                border-radius: 5px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #64748B;
            }
            QScrollBar:horizontal {
                border: none;
                background: #0F172A;
                height: 10px;
            }
            QScrollBar::handle:horizontal {
                background: #475569;
                border-radius: 5px;
                min-width: 20px;
            }
        """)

    def sizeHint(self):
        return QSize(750, 800)

    def minimumSizeHint(self):
        return QSize(550, 400)

    def viewportEvent(self, event):
        t = event.type()
        if t == QEvent.MouseButtonPress:
            if event.button() == Qt.MiddleButton:
                self._is_panning = True
                self._pan_start_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                self._pan_start_h = self.horizontalScrollBar().value()
                self._pan_start_v = self.verticalScrollBar().value()
                self.viewport().setCursor(Qt.ClosedHandCursor)
                event.accept()
                return True
        elif t == QEvent.MouseMove:
            if self._is_panning:
                if not (event.buttons() & Qt.MiddleButton):
                    self._is_panning = False
                    self.viewport().unsetCursor()
                else:
                    cur_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                    delta = cur_pos - self._pan_start_pos
                    self.horizontalScrollBar().setValue(self._pan_start_h - delta.x())
                    self.verticalScrollBar().setValue(self._pan_start_v - delta.y())
                    event.accept()
                    return True
        elif t == QEvent.MouseButtonRelease:
            if event.button() == Qt.MiddleButton and self._is_panning:
                self._is_panning = False
                self.viewport().unsetCursor()
                event.accept()
                return True
        return super().viewportEvent(event)

    def wheelEvent(self, event):
        modifiers = event.modifiers()
        is_ctrl_or_cmd = bool(modifiers & (Qt.ControlModifier | Qt.MetaModifier))
        if is_ctrl_or_cmd:
            delta = event.angleDelta().y()
            if delta != 0:
                g_pos = event.globalPosition().toPoint() if hasattr(event, 'globalPosition') else event.globalPos()
                pos = self.viewport().mapFromGlobal(g_pos)
                if delta > 0:
                    self.zoom_in(pos)
                else:
                    self.zoom_out(pos)
                event.accept()
                return
        elif modifiers & Qt.ShiftModifier:
            delta = event.angleDelta().y() or event.angleDelta().x()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - int(delta))
            event.accept()
            return
        super().wheelEvent(event)

    def zoom_in(self, anchor_pos=None):
        self.set_zoom_factor(min(self.max_zoom, self.zoom_factor * 1.15), anchor_pos)

    def zoom_out(self, anchor_pos=None):
        if self.zoom_factor <= 1.0:
            return
        new_factor = max(1.0, self.zoom_factor / 1.15)
        if abs(new_factor - 1.0) < 0.03:
            new_factor = 1.0
        self.set_zoom_factor(new_factor, anchor_pos)

    def reset_zoom(self):
        self.set_zoom_factor(1.0)

    def set_zoom_factor(self, factor, anchor_pos=None):
        factor = max(self.min_zoom, min(self.max_zoom, factor))
        if abs(factor - 1.0) < 0.01:
            factor = 1.0
        if factor == self.zoom_factor and factor == 1.0:
            return

        content = self.widget()
        if not content:
            self.zoom_factor = factor
            return

        vp = self.viewport()
        vp_w = vp.width()
        vp_h = vp.height()
        if vp_w <= 0:
            self.zoom_factor = factor
            return

        if anchor_pos is None:
            anchor_pos = vp.mapFromGlobal(QCursor.pos())
        if not vp.rect().contains(anchor_pos):
            anchor_pos = QPoint(vp_w // 2, vp_h // 2)

        old_w = content.width()
        old_h = content.height()
        pt_in_content = content.mapFrom(vp, anchor_pos)
        ratio_x = (pt_in_content.x() / old_w) if old_w > 0 else 0.5
        ratio_y = (pt_in_content.y() / old_h) if old_h > 0 else 0.5

        self.zoom_factor = factor

        if self.zoom_factor == 1.0:
            content.setMinimumWidth(0)
            content.setMaximumWidth(16777215)
            content.resize(vp_w, content.height())
            target_w = vp_w
        else:
            target_w = int(vp_w * self.zoom_factor)
            content.setFixedWidth(target_w)

        content.adjustSize()

        new_w = target_w
        new_h = int(old_h * (target_w / old_w)) if old_w > 0 else content.height()

        new_pt_x = ratio_x * new_w
        new_pt_y = ratio_y * new_h

        new_hbar = int(new_pt_x - anchor_pos.x()) if new_w > vp_w else 0
        new_vbar = int(new_pt_y - anchor_pos.y())

        def apply_scroll():
            self.horizontalScrollBar().setValue(new_hbar)
            self.verticalScrollBar().setValue(new_vbar)

        QTimer.singleShot(0, apply_scroll)

        pct = int(round(self.zoom_factor * 100))
        label_text = f"{pct}% (화면 맞춤)" if self.zoom_factor == 1.0 else f"{pct}%"
        self.zoom_badge.show_zoom(label_text, vp.width())


# =================================================================
# 5. 스크립트 대조 검수 메인 다이얼로그 (ScriptVerificationDialog)
# =================================================================
class ScriptVerificationDialog(QDialog):
    def __init__(self, episode_dir, parent=None):
        super().__init__(parent)
        self.episode_dir = episode_dir
        self.image_files = []
        self.image_labels = []
        self.items = []
        self.characters = []
        self.card_widgets = []
        self.active_item_id = None
        self.current_filter = "all"  # "all", "unverified", "verified"
        self.show_badges = True

        epi_title = os.path.basename(episode_dir)
        self.setWindowTitle(f"🔍 스크립트 대조 검수 - {epi_title}")
        self.resize(1380, 880)
        self.setWindowFlags(Qt.Window | Qt.WindowMaximizeButtonHint | Qt.WindowCloseButtonHint)

        self.load_characters()
        self.setup_ui()
        self.load_data()

    def load_characters(self):
        """회차 캐릭터 정보 로드"""
        self.characters = []
        char_csv = os.path.join(self.episode_dir, "character_info.csv")
        if os.path.exists(char_csv):
            try:
                import pandas as pd
                df = pd.read_csv(char_csv)
                if 'name' in df.columns:
                    self.characters = [str(n).strip() for n in df['name'].dropna() if str(n).strip()]
                elif 'Name' in df.columns:
                    self.characters = [str(n).strip() for n in df['Name'].dropna() if str(n).strip()]
            except Exception as e:
                print(f"캐릭터 정보 로드 실패: {e}")

        # 부모 메인 윈도우에서 캐릭터 목록 보강
        if not self.characters and self.parent() and hasattr(self.parent(), 'get_character_list'):
            try:
                self.characters = self.parent().get_character_list()
            except Exception:
                pass

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._apply_initial_splitter_sizes)

    def _apply_initial_splitter_sizes(self):
        total_w = self.splitter.width() if self.splitter.width() > 0 else self.width()
        if total_w > 0:
            left_w = max(550, int(total_w * 0.55))
            right_w = max(400, total_w - left_w)
            self.splitter.setSizes([left_w, right_w])
        if hasattr(self, 'scroll_area'):
            self.scroll_area.set_zoom_factor(1.0)

    def setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------------------------------------------------
        # A. 상단 헤더 바
        # ---------------------------------------------------------
        header_widget = QWidget()
        header_widget.setFixedHeight(58)
        header_widget.setStyleSheet("background-color: #FFFFFF; border-bottom: 1px solid #E2E8F0;")
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(20, 0, 20, 0)
        header_layout.setSpacing(15)

        # 타이틀 & 회차명
        lbl_title = QLabel("🔍 스크립트 대조 검수")
        lbl_title.setFont(QFont("Pretendard", 15, QFont.Bold))
        lbl_title.setStyleSheet("color: #0F172A;")
        header_layout.addWidget(lbl_title)

        self.lbl_subtitle = QLabel(os.path.basename(self.episode_dir))
        self.lbl_subtitle.setFont(QFont("Pretendard", 11))
        self.lbl_subtitle.setStyleSheet("color: #64748B; background: #F1F5F9; border-radius: 4px; padding: 3px 8px;")
        header_layout.addWidget(self.lbl_subtitle)

        header_layout.addSpacing(15)

        # 진행도 게이지 & 텍스트
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFixedWidth(220)
        self.progress_bar.setFixedHeight(12)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #E2E8F0;
                border-radius: 6px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #10B981;
                border-radius: 6px;
            }
        """)
        header_layout.addWidget(self.progress_bar)

        self.lbl_progress_text = QLabel("검수 진행: 0 / 0 (0%)")
        self.lbl_progress_text.setFont(QFont("Pretendard", 11, QFont.Medium))
        self.lbl_progress_text.setStyleSheet("color: #334155;")
        header_layout.addWidget(self.lbl_progress_text)

        header_layout.addStretch()

        # 번호 뱃지 토글 버튼
        self.btn_toggle_badges = QPushButton("번호 뱃지 표시")
        self.btn_toggle_badges.setCheckable(True)
        self.btn_toggle_badges.setChecked(True)
        self.btn_toggle_badges.setFixedHeight(32)
        self.btn_toggle_badges.setStyleSheet("""
            QPushButton {
                border: 1px solid #CBD5E1;
                background-color: #F8FAFC;
                color: #334155;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:checked {
                background-color: #EFF6FF;
                border-color: #3B82F6;
                color: #2563EB;
            }
        """)
        self.btn_toggle_badges.toggled.connect(self.toggle_badges)
        header_layout.addWidget(self.btn_toggle_badges)

        # 줌 100% 리셋 버튼
        btn_zoom_reset = QPushButton("화면 맞춤")
        btn_zoom_reset.setFixedHeight(32)
        btn_zoom_reset.setStyleSheet("""
            QPushButton {
                border: 1px solid #CBD5E1;
                background-color: white;
                color: #334155;
                border-radius: 6px;
                padding: 0 12px;
                font-size: 13px;
            }
            QPushButton:hover { background-color: #F1F5F9; }
        """)
        btn_zoom_reset.clicked.connect(lambda: self.scroll_area.reset_zoom())
        header_layout.addWidget(btn_zoom_reset)

        main_layout.addWidget(header_widget)

        # ---------------------------------------------------------
        # B. 2분할 메인 스플리터 (좌: 뷰어 / 우: 검수 패널)
        # ---------------------------------------------------------
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #E2E8F0;
                width: 4px;
            }
            QSplitter::handle:hover {
                background-color: #3B82F6;
            }
        """)

        # 1. 좌측 뷰어 (웹툰 세로 스크롤)
        self.scroll_area = VerificationScrollArea()
        self.scroll_area.setMinimumWidth(550)
        self.viewer_content = QWidget()
        self.viewer_layout = QVBoxLayout(self.viewer_content)
        self.viewer_layout.setContentsMargins(0, 0, 0, 0)
        self.viewer_layout.setSpacing(0)
        self.viewer_layout.setAlignment(Qt.AlignTop)
        self.scroll_area.setWidget(self.viewer_content)
        self.splitter.addWidget(self.scroll_area)

        # 2. 우측 검수 작업창 패널
        right_panel = QWidget()
        right_panel.setMinimumWidth(400)
        right_panel.setStyleSheet("background-color: #F8FAFC;")
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(16, 14, 16, 14)
        right_layout.setSpacing(12)

        # 우측 상단 툴바: 검색창 & 필터 버튼
        tool_layout = QHBoxLayout()
        tool_layout.setSpacing(8)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 대사 또는 캐릭터 검색...")
        self.txt_search.setFixedHeight(34)
        self.txt_search.setFont(QFont("Pretendard", 10))
        self.txt_search.setStyleSheet("""
            QLineEdit {
                border: 1px solid #CBD5E1;
                border-radius: 6px;
                padding: 0 10px;
                background-color: white;
                font-size: 13px;
            }
            QLineEdit:focus { border: 2px solid #2563EB; }
        """)
        self.txt_search.textChanged.connect(self.filter_cards)
        tool_layout.addWidget(self.txt_search)

        # 필터 라디오/버튼 그룹
        self.btn_filter_all = QPushButton("전체")
        self.btn_filter_unverified = QPushButton("미검수")
        self.btn_filter_verified = QPushButton("완료")

        for btn, f_mode in [(self.btn_filter_all, "all"), (self.btn_filter_unverified, "unverified"), (self.btn_filter_verified, "verified")]:
            btn.setFixedHeight(34)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    border: 1px solid #D1D5DB;
                    border-radius: 6px;
                    padding: 0 10px;
                    background-color: white;
                    font-size: 13px;
                    font-weight: 500;
                    color: #475569;
                }
                QPushButton:checked {
                    background-color: #2563EB;
                    color: white;
                    border-color: #2563EB;
                    font-weight: bold;
                }
            """)
            btn.clicked.connect(lambda checked, m=f_mode: self.set_filter(m))
            tool_layout.addWidget(btn)

        self.btn_filter_all.setChecked(True)
        right_layout.addLayout(tool_layout)

        # 대사 카드 목록 스크롤 영역
        self.cards_scroll = QScrollArea()
        self.cards_scroll.setWidgetResizable(True)
        self.cards_scroll.setStyleSheet("QScrollArea { border: none; background: transparent; }")

        self.cards_container = QWidget()
        self.cards_layout = QVBoxLayout(self.cards_container)
        self.cards_layout.setContentsMargins(0, 0, 0, 0)
        self.cards_layout.setSpacing(10)
        self.cards_layout.setAlignment(Qt.AlignTop)

        self.cards_scroll.setWidget(self.cards_container)
        right_layout.addWidget(self.cards_scroll)

        # 대사 추가 버튼
        btn_add_card = QPushButton("+ 새 대사 직접 추가")
        btn_add_card.setFixedHeight(38)
        btn_add_card.setFont(QFont("Pretendard", 11, QFont.Bold))
        btn_add_card.setStyleSheet("""
            QPushButton {
                background-color: #FFFFFF;
                border: 2px dashed #CBD5E1;
                border-radius: 6px;
                color: #2563EB;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #EFF6FF;
                border-color: #93C5FD;
            }
        """)
        btn_add_card.clicked.connect(self.add_new_empty_card)
        right_layout.addWidget(btn_add_card)

        self.splitter.addWidget(right_panel)
        self.splitter.setStretchFactor(0, 55)
        self.splitter.setStretchFactor(1, 45)
        self.splitter.setSizes([760, 620])
        main_layout.addWidget(self.splitter)

        # ---------------------------------------------------------
        # C. 하단 액션 바
        # ---------------------------------------------------------
        bottom_widget = QWidget()
        bottom_widget.setFixedHeight(56)
        bottom_widget.setStyleSheet("background-color: #FFFFFF; border-top: 1px solid #E2E8F0;")
        bottom_layout = QHBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(20, 0, 20, 0)
        bottom_layout.setSpacing(12)

        # 단축키 안내
        lbl_shortcuts = QLabel("💡 단축키: [Enter: 저장 후 다음]  [Shift+Enter: 줄바꿈]  [휠 클릭 드래그: 화면 이동]  [Ctrl+휠: 확대/축소]")
        lbl_shortcuts.setFont(QFont("Pretendard", 10))
        lbl_shortcuts.setStyleSheet("color: #64748B;")
        bottom_layout.addWidget(lbl_shortcuts)

        bottom_layout.addStretch()

        # 원본으로 초기화 버튼
        btn_reset_raw = QPushButton(" OCR 원본으로 초기화")
        btn_reset_raw.setIcon(get_colored_icon(config.ICON_REFRESH, "#64748B"))
        btn_reset_raw.setIconSize(QSize(14, 14))
        btn_reset_raw.setFixedHeight(36)
        btn_reset_raw.setStyleSheet("""
            QPushButton {
                border: 1px solid #CBD5E1;
                background-color: white;
                color: #64748B;
                border-radius: 6px;
                padding: 0 14px;
                font-size: 13px;
                font-weight: 500;
            }
            QPushButton:hover { background-color: #FEE2E2; color: #DC2626; border-color: #FCA5A5; }
        """)
        btn_reset_raw.clicked.connect(self.reset_to_raw_ocr)
        bottom_layout.addWidget(btn_reset_raw)

        # 취소 버튼
        btn_cancel = QPushButton("취소")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet("""
            QPushButton {
                border: 1px solid #CBD5E1;
                background-color: white;
                color: #334155;
                border-radius: 6px;
                padding: 0 18px;
                font-size: 13px;
                font-weight: 600;
            }
            QPushButton:hover { background-color: #F1F5F9; }
        """)
        btn_cancel.clicked.connect(self.reject)
        bottom_layout.addWidget(btn_cancel)

        # 검수 완료 및 적용 버튼
        btn_apply = QPushButton(" 검수 완료 및 메인 반영")
        btn_apply.setIcon(get_colored_icon(config.ICON_SUCCESS, "#FFFFFF"))
        btn_apply.setIconSize(QSize(16, 16))
        btn_apply.setFixedHeight(36)
        btn_apply.setFont(QFont("Pretendard", 11, QFont.Bold))
        btn_apply.setStyleSheet("""
            QPushButton {
                border: none;
                background-color: #2563EB;
                color: white;
                border-radius: 6px;
                padding: 0 22px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #1D4ED8; }
            QPushButton:pressed { background-color: #1E40AF; }
        """)
        btn_apply.clicked.connect(self.apply_and_close)
        bottom_layout.addWidget(btn_apply)

        main_layout.addWidget(bottom_widget)

    # ---------------------------------------------------------
    # 데이터 로딩 및 동기화 로직
    # ---------------------------------------------------------
    def load_data(self):
        # 1. 이미지 로드
        self.image_files = get_episode_images(self.episode_dir)
        # 기존 뷰어 초기화
        for lbl in self.image_labels:
            lbl.deleteLater()
        self.image_labels = []

        if not self.image_files:
            empty_lbl = QLabel("등록된 이미지가 없습니다.")
            empty_lbl.setAlignment(Qt.AlignCenter)
            empty_lbl.setStyleSheet("color: #94A3B8; font-size: 16px; padding: 40px;")
            self.viewer_layout.addWidget(empty_lbl)
        else:
            for idx, img_p in enumerate(self.image_files):
                lbl = VerificationImageLabel(img_p, idx)
                lbl.box_clicked.connect(self.on_box_clicked)
                lbl.new_box_created.connect(self.on_new_box_created)
                self.image_labels.append(lbl)
                self.viewer_layout.addWidget(lbl)

        # 2. 대사 데이터 로드 (ocr_boxes.json)
        self.items = load_ocr_boxes(self.episode_dir)

        # 만약 ocr_boxes.json이 아직 없다면 script.txt 등에서 초기 복원
        if not self.items:
            self.items = self._fallback_load_from_script()

        self.rebuild_cards()
        self.update_image_boxes()
        self.update_progress()
        QTimer.singleShot(50, lambda: self.scroll_area.set_zoom_factor(1.0))

    def _fallback_load_from_script(self):
        """ocr_boxes.json이 없는 경우 script.txt 또는 script_data.csv에서 복원"""
        items = []
        raw_lines = []

        # 1. script_data.csv 확인
        csv_p = os.path.join(self.episode_dir, "script_data.csv")
        if os.path.exists(csv_p):
            try:
                import pandas as pd
                df = pd.read_csv(csv_p)
                for idx, row in df.iterrows():
                    c_name = str(row.get('Character', '')).strip() if pd.notna(row.get('Character')) else ""
                    c_line = str(row.get('Line', '')).strip() if pd.notna(row.get('Line')) else ""
                    if c_line:
                        raw_lines.append((c_name, c_line))
            except Exception:
                pass

        # 2. script.txt 확인
        if not raw_lines:
            txt_p = os.path.join(self.episode_dir, "script.txt")
            if os.path.exists(txt_p):
                with open(txt_p, "r", encoding="utf-8") as f:
                    lines = [l.strip() for l in f.readlines() if l.strip()]
                for l in lines:
                    clean = re.sub(r'^(\[\d+\]|\d+\.)\s*', '', l).strip()
                    if " : " in clean:
                        sp, dl = clean.split(" : ", 1)
                        raw_lines.append((sp.strip(), dl.strip()))
                    elif ":" in clean:
                        sp, dl = clean.split(":", 1)
                        raw_lines.append((sp.strip(), dl.strip()))
                    else:
                        raw_lines.append(("", clean))

        # 3. 이미지들에 대사들을 고르게 배정
        total_imgs = len(self.image_files) if self.image_files else 1
        for i, (char, text) in enumerate(raw_lines):
            img_idx = min(total_imgs - 1, int(i / max(1, len(raw_lines)) * total_imgs))
            img_file = os.path.basename(self.image_files[img_idx]) if self.image_files else ""
            items.append({
                "id": i + 1,
                "text": text,
                "character": char,
                "image_index": img_idx,
                "image_file": img_file,
                "box": [100, 200, 600, 350],
                "is_verified": False
            })

        return items

    def _create_card_widget(self, item):
        cw = VerificationCardWidget(item, self.characters, self.cards_container)
        cw.clicked.connect(self.on_card_clicked)
        cw.text_changed.connect(self.on_card_text_changed)
        cw.character_changed.connect(self.on_card_character_changed)
        cw.verified_toggled.connect(self.on_card_verified_toggled)
        cw.request_split.connect(self.split_card)
        cw.request_delete.connect(self.delete_card)
        cw.enter_next.connect(self.on_card_enter_next)
        cw.navigate_up.connect(self.on_card_navigate_up)
        cw.navigate_down.connect(self.on_card_navigate_down)
        return cw

    def rebuild_cards(self, preserve_scroll=True):
        """우측 대사 카드 리스트 전체 재생성 (초기 로드 또는 전체 갱신 시)"""
        old_scroll = self.cards_scroll.verticalScrollBar().value() if preserve_scroll else 0
        old_active_id = self.active_item_id

        for cw in self.card_widgets:
            cw.deleteLater()
        self.card_widgets = []

        for item in self.items:
            cw = self._create_card_widget(item)
            self.cards_layout.addWidget(cw)
            self.card_widgets.append(cw)

        self.filter_cards()

        if self.card_widgets:
            valid_ids = [it['id'] for it in self.items]
            target_id = old_active_id if (old_active_id in valid_ids) else self.items[0]['id']
            if preserve_scroll:
                self.active_item_id = target_id
                for cw in self.card_widgets:
                    cw.set_active(cw.item.get('id') == target_id)
                self.update_image_boxes()
                QTimer.singleShot(30, lambda: self.cards_scroll.verticalScrollBar().setValue(old_scroll))
            else:
                self.set_active_item(target_id, scroll_viewer=True, scroll_card=True)

    def update_image_boxes(self):
        """모든 이미지 라벨에 최신 박스 정보 갱신"""
        for lbl in self.image_labels:
            lbl.set_items(self.items, self.active_item_id, self.show_badges)

    def set_active_item(self, item_id, scroll_viewer=True, scroll_card=True):
        self.active_item_id = item_id

        # 1. 우측 카드 활성화 스타일 반영
        active_card = None
        for cw in self.card_widgets:
            is_cur = (cw.item.get('id') == item_id)
            cw.set_active(is_cur)
            if is_cur:
                active_card = cw

        # 2. 우측 리스트 스크롤
        if scroll_card and active_card and active_card.isVisible():
            self.cards_scroll.ensureWidgetVisible(active_card, 50, 50)

        # 3. 좌측 뷰어 박스 하이라이트 & 자동 스크롤
        self.update_image_boxes()
        if scroll_viewer:
            target_item = next((it for it in self.items if it.get('id') == item_id), None)
            if target_item:
                self.scroll_viewer_to_item(target_item)

    def scroll_viewer_to_item(self, item):
        """대사가 있는 이미지 및 위치로 스크롤"""
        img_idx = item.get('image_index', 0)
        if 0 <= img_idx < len(self.image_labels):
            lbl = self.image_labels[img_idx]
            box = item.get('box', [0, 0, 100, 100])
            if not lbl.original_pixmap.isNull() and lbl.original_pixmap.height() > 0:
                scale_y = lbl.height() / float(lbl.original_pixmap.height())
                rel_y = int(((box[1] + box[3]) / 2.0) * scale_y)
                lbl_y = lbl.mapTo(self.viewer_content, QPoint(0, 0)).y()
                target_v = lbl_y + rel_y - (self.scroll_area.viewport().height() // 2)
                self.scroll_area.verticalScrollBar().setValue(max(0, target_v))

    def on_card_clicked(self, item):
        self.set_active_item(item['id'], scroll_viewer=True, scroll_card=False)

    def on_box_clicked(self, item):
        self.set_active_item(item['id'], scroll_viewer=False, scroll_card=True)

    def on_card_text_changed(self, item, text):
        pass

    def on_card_character_changed(self, item, char):
        pass

    def on_card_verified_toggled(self, item, checked):
        self.update_image_boxes()
        self.update_progress()

    def on_card_enter_next(self, current_item):
        """Enter 키 입력 시: 현재 대사 검수 완료 처리 후 다음 대사로 자동 이동"""
        current_item['is_verified'] = True
        for cw in self.card_widgets:
            if cw.item.get('id') == current_item.get('id'):
                cw.chk_verified.setChecked(True)
                break

        self.update_progress()
        self.update_image_boxes()

        # 다음 대사 찾기
        cur_id = current_item.get('id')
        visible_items = [cw.item for cw in self.card_widgets if cw.isVisible()]
        next_item = None
        for i, it in enumerate(visible_items):
            if it.get('id') == cur_id and i + 1 < len(visible_items):
                next_item = visible_items[i + 1]
                break

        if next_item:
            self.set_active_item(next_item['id'], scroll_viewer=True, scroll_card=True)
        else:
            QApplication.beep()

    def on_card_navigate_up(self, current_item):
        visible_items = [cw.item for cw in self.card_widgets if cw.isVisible()]
        cur_id = current_item.get('id')
        for i, it in enumerate(visible_items):
            if it.get('id') == cur_id and i > 0:
                self.set_active_item(visible_items[i - 1]['id'], scroll_viewer=True, scroll_card=True)
                break

    def on_card_navigate_down(self, current_item):
        visible_items = [cw.item for cw in self.card_widgets if cw.isVisible()]
        cur_id = current_item.get('id')
        for i, it in enumerate(visible_items):
            if it.get('id') == cur_id and i + 1 < len(visible_items):
                self.set_active_item(visible_items[i + 1]['id'], scroll_viewer=True, scroll_card=True)
                break

    def on_new_box_created(self, image_index, box):
        """이미지에서 영역 드래그 시 새 말풍선 추가 (위젯 인라인 삽입으로 스크롤 보존)"""
        new_id = max([it.get('id', 0) for it in self.items], default=0) + 1
        img_file = os.path.basename(self.image_files[image_index]) if image_index < len(self.image_files) else ""
        new_item = {
            "id": new_id,
            "text": "",
            "character": "",
            "image_index": image_index,
            "image_file": img_file,
            "box": box,
            "is_verified": False
        }

        # 정렬 기준: image_index 순, 그리고 Y축 시작 좌표 순
        insert_idx = len(self.items)
        for idx, it in enumerate(self.items):
            if (it['image_index'] > image_index) or (it['image_index'] == image_index and it['box'][1] > box[1]):
                insert_idx = idx
                break

        self.items.insert(insert_idx, new_item)
        self._reindex_items()

        # 전체 재생성 대신 지정 위치에 카드 위젯만 삽입
        new_cw = self._create_card_widget(new_item)
        self.cards_layout.insertWidget(insert_idx, new_cw)
        self.card_widgets.insert(insert_idx, new_cw)

        # 번호 뱃지 갱신
        for card in self.card_widgets:
            card.lbl_id.setText(f"#{card.item['id']}")

        self.update_image_boxes()
        self.update_progress()

        # 방금 사용자가 직접 이미지에서 드래그했으므로 뷰어는 스크롤하지 않고 카드만 스크롤
        QTimer.singleShot(30, lambda: self.set_active_item(new_item['id'], scroll_viewer=False, scroll_card=True))

    def add_new_empty_card(self):
        """새 대사 직접 추가 (위젯 인라인 추가로 스크롤 보존)"""
        new_id = max([it.get('id', 0) for it in self.items], default=0) + 1
        cur_img_idx = 0
        if self.active_item_id:
            cur_item = next((it for it in self.items if it['id'] == self.active_item_id), None)
            if cur_item:
                cur_img_idx = cur_item.get('image_index', 0)

        img_file = os.path.basename(self.image_files[cur_img_idx]) if cur_img_idx < len(self.image_files) else ""
        new_item = {
            "id": new_id,
            "text": "",
            "character": "",
            "image_index": cur_img_idx,
            "image_file": img_file,
            "box": [100, 200, 500, 350],
            "is_verified": False
        }
        self.items.append(new_item)
        self._reindex_items()

        new_cw = self._create_card_widget(new_item)
        self.cards_layout.addWidget(new_cw)
        self.card_widgets.append(new_cw)

        for card in self.card_widgets:
            card.lbl_id.setText(f"#{card.item['id']}")

        self.update_image_boxes()
        self.update_progress()

        QTimer.singleShot(30, lambda: self.set_active_item(new_item['id'], scroll_viewer=True, scroll_card=True))

    def split_card(self, item):
        """대사 2개로 분할 (전체 재생성 없이 인라인 분할)"""
        text = item.get('text', '')
        parts = text.split('\n', 1) if '\n' in text else [text, ""]
        if len(parts) == 1 or not parts[1]:
            # 줄바꿈이 없으면 공백 기준으로 반 분할
            words = text.split(' ')
            if len(words) > 1:
                mid = len(words) // 2
                parts = [" ".join(words[:mid]), " ".join(words[mid:])]
            else:
                parts = [text, ""]

        item['text'] = parts[0]

        # 기존 카드 텍스트 업데이트
        cw_orig = next((w for w in self.card_widgets if w.item == item), None)
        if cw_orig:
            cw_orig.txt_dialogue.setPlainText(parts[0])

        idx = self.items.index(item)
        box = item.get('box', [100, 100, 400, 300])
        h_half = (box[3] - box[1]) // 2
        new_box = [box[0], box[1] + h_half, box[2], box[3]]

        new_item = {
            "id": item['id'] + 1,
            "text": parts[1],
            "character": item.get('character', ''),
            "image_index": item.get('image_index', 0),
            "image_file": item.get('image_file', ''),
            "box": new_box,
            "is_verified": False
        }
        self.items.insert(idx + 1, new_item)
        self._reindex_items()

        # 분할된 새 카드 위젯을 기존 위치 바로 뒤에 삽입 (전체 위젯 재생성 방지)
        new_cw = self._create_card_widget(new_item)
        self.cards_layout.insertWidget(idx + 1, new_cw)
        self.card_widgets.insert(idx + 1, new_cw)

        # 번호 뱃지 갱신
        for card in self.card_widgets:
            card.lbl_id.setText(f"#{card.item['id']}")

        self.update_image_boxes()
        self.update_progress()

        # 새로 분할된 카드로 포커스 및 스크롤
        QTimer.singleShot(30, lambda: self.set_active_item(new_item['id'], scroll_viewer=True, scroll_card=True))

    def delete_card(self, item):
        """대사 삭제 (삭제된 위치 주변 카드 유지 및 상단 튕김 방지)"""
        if len(self.items) <= 1:
            QMessageBox.information(self, "알림", "최소 1개의 대사는 유지되어야 합니다.")
            return

        reply = QMessageBox.question(
            self, "대사 삭제",
            f"대사 #{item['id']}를 삭제하시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            del_idx = self.items.index(item)
            self.items.remove(item)
            self._reindex_items()

            # 해당 카드 위젯만 레이아웃에서 제거 (전체 위젯 재생성 방지 -> 스크롤 유지)
            cw_to_del = next((w for w in self.card_widgets if w.item == item), None)
            if cw_to_del:
                self.cards_layout.removeWidget(cw_to_del)
                cw_to_del.deleteLater()
                self.card_widgets.remove(cw_to_del)

            # 남은 카드 번호 뱃지 갱신
            for card in self.card_widgets:
                card.lbl_id.setText(f"#{card.item['id']}")

            self.update_image_boxes()
            self.update_progress()

            # 삭제된 위치의 다음 대사(또는 마지막이면 이전 대사)를 활성화하여 그 위치에 머무름
            if self.items:
                next_idx = min(del_idx, len(self.items) - 1)
                next_item = self.items[next_idx]
                self.set_active_item(next_item['id'], scroll_viewer=True, scroll_card=True)

    def _reindex_items(self):
        for idx, it in enumerate(self.items):
            it['id'] = idx + 1

    def update_progress(self):
        total = len(self.items)
        verified = sum(1 for it in self.items if it.get('is_verified', False))
        pct = int((verified / max(1, total)) * 100)
        self.progress_bar.setValue(pct)
        self.lbl_progress_text.setText(f"검수 진행: {verified} / {total} ({pct}%)")

    def toggle_badges(self, checked):
        self.show_badges = checked
        self.update_image_boxes()

    def set_filter(self, mode):
        self.current_filter = mode
        self.btn_filter_all.setChecked(mode == "all")
        self.btn_filter_unverified.setChecked(mode == "unverified")
        self.btn_filter_verified.setChecked(mode == "verified")
        self.filter_cards()

    def filter_cards(self):
        query = self.txt_search.text().strip().lower()
        for cw in self.card_widgets:
            item = cw.item
            match_text = (query in item.get('text', '').lower()) or (query in item.get('character', '').lower())
            match_mode = True
            if self.current_filter == "unverified":
                match_mode = not item.get('is_verified', False)
            elif self.current_filter == "verified":
                match_mode = item.get('is_verified', False)

            cw.setVisible(match_text and match_mode)

    def reset_to_raw_ocr(self):
        reply = QMessageBox.warning(
            self, "초기화 확인",
            "모든 수정 내용을 취소하고 최초 OCR 분석 결과로 되돌리시겠습니까?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            boxes_p = os.path.join(self.episode_dir, "ocr_boxes.json")
            if os.path.exists(boxes_p):
                try:
                    os.remove(boxes_p)
                except Exception:
                    pass
            self.load_data()

    def apply_and_close(self):
        """검수 완료 데이터 저장 및 메인 창 반영"""
        # 1. ocr_boxes.json 저장
        save_ocr_boxes(self.episode_dir, self.items)

        # 2. 메인 윈도우의 Step 1(script.txt) 및 Step 3(script_data.csv / table) 반영
        mw = self.parent()
        clean_lines = [it.get('text', '').strip() for it in self.items if it.get('text', '').strip()]
        full_text = "\n".join(clean_lines)

        # script.txt 저장
        s_path = os.path.join(self.episode_dir, "script.txt")
        try:
            with open(s_path, "w", encoding="utf-8") as f:
                f.write(full_text)
        except Exception as e:
            print(f"script.txt 저장 오류: {e}")

        # script_data.csv 저장
        try:
            import pandas as pd
            csv_rows = []
            for it in self.items:
                c_name = it.get('character', '').strip()
                t_line = it.get('text', '').strip()
                if t_line:
                    csv_rows.append({'Character': c_name, 'Line': t_line})
            df = pd.DataFrame(csv_rows)
            df.to_csv(os.path.join(self.episode_dir, "script_data.csv"), index=False, encoding='utf-8-sig')
        except Exception as e:
            print(f"script_data.csv 저장 오류: {e}")

        # 메인 윈도우 UI 즉시 동기화
        if mw:
            if hasattr(mw, 'text_editor'):
                mw.text_editor.blockSignals(True)
                mw.text_editor.setPlainText(full_text)
                mw.text_editor.blockSignals(False)
            if hasattr(mw, 'load_data'):
                mw.load_data()
            if hasattr(mw, 'toast'):
                mw.toast.show_message("✨ 대조 검수 결과가 성공적으로 반영되었습니다.")

        self.accept()
