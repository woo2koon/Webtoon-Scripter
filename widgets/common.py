# widgets/common.py
import os
import json
import platform
import re
import unicodedata

from PySide6.QtWidgets import (
    QLabel, QComboBox, QListView, QStyledItemDelegate, QScrollArea, QFrame,
    QHBoxLayout, QLineEdit, QPushButton, QWidget, QSizePolicy, QTextEdit,
    QTableWidget, QAbstractItemView, QTableWidgetItem, QApplication, QHeaderView,
    QGraphicsOpacityEffect, QMenu, QDialog, QVBoxLayout, QInputDialog,
    QListWidget, QListWidgetItem, QStackedWidget, QFileDialog, QCheckBox,
    QStyleOptionViewItem, QStyle
)
from PySide6.QtCore import (
    Qt, QEvent, Signal, QTimer, QSize, QEasingCurve, QPropertyAnimation,
    QRect, QRectF, QMimeData, QModelIndex, QByteArray, QPointF, QPoint
)
from PySide6.QtGui import (
    QPixmap, QDrag, QPainter, QColor, QPen, QFont, QAction, QIcon,
    QRegion, QBrush, QLinearGradient, QTextCharFormat, QTextFormat,
    QTextCursor, QKeySequence, QPainterPath, QPolygonF, QCursor
)
from PySide6.QtSvg import QSvgRenderer

import config
from config import ROLE_OPTIONS, AGE_OPTIONS, GENDER_OPTIONS, PROJECTS_DIR
from utils import get_icon, get_colored_icon, open_path, get_colored_pixmap

# =================================================================
# 이미지 비율 유지 라벨
# =================================================================
class ResponsiveLabel(QLabel):
    request_reanalysis = Signal(str, QWidget)  # Emits (image_path, label_widget)

    def __init__(self, pixmap_path, parent=None):
        super().__init__(parent)
        self.pixmap_path = pixmap_path
        self.original_pixmap = QPixmap(pixmap_path)
        self.setPixmap(self.original_pixmap)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        self._is_resizing = False
        
    def resizeEvent(self, event):
        if not self._is_resizing and not self.original_pixmap.isNull() and self.width() > 0:
            aspect_ratio = self.original_pixmap.height() / self.original_pixmap.width()
            target_height = int(self.width() * aspect_ratio)
            if self.height() != target_height:
                self._is_resizing = True
                self.setFixedHeight(target_height)
                self._is_resizing = False
        super().resizeEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        menu.setFont(QApplication.font())
        menu.setStyleSheet(config.MODERN_MENU_STYLE)
        
        action_reanalyze = QAction(get_icon(config.ICON_MESSAGE_CIRCLE), "부분 영역 재분석", self)
        action_reanalyze.triggered.connect(lambda: self.request_reanalysis.emit(self.pixmap_path, self))
        menu.addAction(action_reanalyze)
        menu.exec(self.mapToGlobal(pos))

# =================================================================
class ClickableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.ClickFocus) # [수정] 스크롤 시 자동 포커스(클릭되는 현상) 방지하기 위해 ClickFocus로 설정
        self.setEditable(True) 
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setCursor(Qt.ArrowCursor)
        self.lineEdit().setFocusPolicy(Qt.ClickFocus) # [수정] 내부 입력창도 스크롤 시 포커스 방지
        self.lineEdit().installEventFilter(self)
        self.installEventFilter(self) # [추가] 자기 자신에게도 필터 설치
        self.setView(QListView())
        
        # Apply application-wide dynamic font and size
        combo_font = QFont("Pretendard")
        if platform.system().lower() == "darwin":
            combo_font.setPixelSize(14)
        else:
            combo_font.setPointSize(11)
        combo_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        combo_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            combo_font.setWeight(QFont.Weight.Medium)
        self.setFont(combo_font)
        if self.lineEdit():
            self.lineEdit().setFont(combo_font)
        
        # 뷰에 폰트와 엘라이드 모드 명시적 지정
        self.view().setFont(combo_font)
        self.view().setTextElideMode(Qt.TextElideMode.ElideRight)
            
        self.setItemDelegate(PopupItemDelegate())
        self.refresh_callback = None 
        self._popup_hidden_recently = False

    def setView(self, view):
        super().setView(view)
        if view:
            combo_font = QFont("Pretendard")
            if platform.system().lower() == "darwin":
                combo_font.setPixelSize(14)
            else:
                combo_font.setPointSize(11)
            combo_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
            combo_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
            if platform.system() == "Windows":
                combo_font.setWeight(QFont.Weight.Medium)
            view.setFont(combo_font)
            view.setTextElideMode(Qt.TextElideMode.ElideRight)
            
            # QListView에 직접 스타일시트 강제 설정
            if platform.system().lower() == "darwin":
                view.setStyleSheet("""
                    QListView {
                        font-family: 'Pretendard';
                        font-size: 14px;
                        background-color: #FFFFFF;
                        border: 1px solid #D1D5DB;
                        border-radius: 6px;
                        padding: 4px;
                    }
                    QListView::item {
                        font-family: 'Pretendard';
                        font-size: 14px;
                    }
                """)
            else:
                view.setStyleSheet("""
                    QListView {
                        font-family: 'Pretendard';
                        font-size: 15px;
                        background-color: #FFFFFF;
                        border: 1px solid #D1D5DB;
                        border-radius: 6px;
                        padding: 4px;
                    }
                    QListView::item {
                        font-family: 'Pretendard';
                        font-size: 15px;
                    }
                """)
            
            popup_win = view.window()
            if popup_win:
                popup_win.setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
                popup_win.setAttribute(Qt.WA_TranslucentBackground)
                popup_win.setFont(combo_font)

    def showPopup(self):
        # [추가] 콤보박스가 열려서 값이 바뀌기 직전의 상태 저장
        self._trigger_undo_backup()
        super().showPopup()
        combo_font = QFont("Pretendard")
        if platform.system().lower() == "darwin":
            combo_font.setPixelSize(14)
        else:
            combo_font.setPointSize(11)
        combo_font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        combo_font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            combo_font.setWeight(QFont.Weight.Medium)
        self.view().setFont(combo_font)
        self.view().setTextElideMode(Qt.TextElideMode.ElideRight)
        popup_win = self.view().window()
        if popup_win and popup_win is not self:
            popup_win.setFont(combo_font)

    def mousePressEvent(self, event):
        # [추가] 클릭 시에도 백업 (직접 입력이나 휠 조작 전 대비)
        self._trigger_undo_backup()
        super().mousePressEvent(event)

    def _trigger_undo_backup(self):
        """메인 윈도우의 테이블에 Undo 백업 요청"""
        mw = self.window()
        if hasattr(mw, 'table_script') and hasattr(mw.table_script, 'save_state_for_undo'):
            mw.table_script.save_state_for_undo()

    def hidePopup(self):
        super().hidePopup()
        self._popup_just_hidden = True
        QTimer.singleShot(50, self._clear_popup_just_hidden)

    def _clear_popup_just_hidden(self):
        self._popup_just_hidden = False

    def wheelEvent(self, event):
        # 이벤트를 ignore() 하면 콤보박스 값이 바뀌는 대신, 
        # 부모 위젯인 테이블이 시원하게 스크롤됩니다.
        event.ignore()

    def set_refresh_callback(self, func):
        self.refresh_callback = func

    def eventFilter(self, obj, event):
        # [핵심] 콤보박스 본체나 내부 입력창 어디서든 Ctrl+Z 및 방향키 감지
        if obj in (self, self.lineEdit()):
            if event.type() == QEvent.KeyPress:
                # 1. Ctrl+Z / Ctrl+Shift+Z 실행 취소/다시 실행 처리
                if event.modifiers() & Qt.ControlModifier:
                    # 부모 위젯들을 거슬러 올라가서 SpreadsheetTable 찾기
                    target_table = None
                    p = self.parent()
                    while p:
                        if isinstance(p, QTableWidget): # SpreadsheetTable은 QTableWidget 상속
                            target_table = p
                            break
                        p = p.parent()
                    
                    if target_table and hasattr(target_table, 'undo'):
                        if event.modifiers() & Qt.ShiftModifier and event.key() == Qt.Key_Z:
                            target_table.redo()
                            return True
                        elif event.key() == Qt.Key_Z:
                            target_table.undo()
                            return True
                
                # 2. 방향키 상하좌우 처리 (팝업이 닫혀 있을 때 부모 테이블로 키 이벤트 바이패스)
                elif event.key() in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right) and not (event.modifiers() & (Qt.ControlModifier | Qt.AltModifier | Qt.ShiftModifier)):
                    if not self.view().isVisible():
                        target_table = None
                        p = self.parent()
                        while p:
                            if isinstance(p, QTableWidget):
                                target_table = p
                                break
                            p = p.parent()
                        if target_table:
                            # 테이블로 키 이벤트를 토스하여 셀 상하좌우 이동을 수행하게 함
                            QApplication.sendEvent(target_table, event)
                            return True # 콤보박스 자체의 기본 키 동작 차단

        if obj == self.lineEdit():
            if event.type() == QEvent.MouseButtonPress:
                if getattr(self, '_popup_just_hidden', False):
                    # 마우스 클릭으로 인해 방금 팝업이 닫혔다면, 다가오는 릴리스 이벤트를 무시합니다.
                    self._ignore_next_release = True
                    self._popup_just_hidden = False
                return True
            
            elif event.type() == QEvent.MouseButtonRelease:
                if getattr(self, '_ignore_next_release', False):
                    self._ignore_next_release = False
                else:
                    self._toggle_popup()
                return True

            elif event.type() in (QEvent.MouseMove, QEvent.MouseButtonDblClick, QEvent.DragEnter, QEvent.DragMove, QEvent.DragLeave, QEvent.Drop):
                # 드래그, 더블클릭 블록 지정 및 드래그 앤 드롭 동작 완전 차단
                return True
                    
        return super().eventFilter(obj, event)

    def _toggle_popup(self):
        if self.refresh_callback:
            current_text = self.currentText()
            try:
                new_items = self.refresh_callback()
                self.blockSignals(True) 
                self.clear()
                self.addItems(new_items)
                self.setCurrentText(current_text) 
                self.blockSignals(False)
                if current_text == "": self.setCurrentIndex(-1)
            except: pass
        if self.view().isVisible(): self.hidePopup()
        else: self.showPopup()

# =================================================================
# 뷰어 확대/축소 배지 (ZoomBadge)
# =================================================================
class ZoomBadge(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: rgba(30, 41, 59, 0.9);
                color: #FFFFFF;
                font-family: 'Pretendard';
                font-size: 13px;
                font-weight: bold;
                border-radius: 14px;
                padding: 6px 14px;
                border: 1px solid rgba(255, 255, 255, 0.15);
            }
        """)
        self.hide()
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def show_zoom(self, percent_text, viewport_w):
        self.setText(percent_text)
        self.adjustSize()
        x = max(10, viewport_w - self.width() - 20)
        y = 20
        self.move(x, y)
        self.raise_()
        self.show()
        self.timer.start(1200)

# =================================================================
# 스크롤 뷰
# =================================================================
class WebtoonScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_adjusting = False
        self.stable_ratio = 0.0
        self.zoom_factor = 1.0
        self.min_zoom = 1.0  # 100% 이하로는 축소 불가
        self.max_zoom = 5.0

        self._is_panning = False
        self._pan_start_pos = QPoint()
        self._pan_start_h = 0
        self._pan_start_v = 0

        self.setAlignment(Qt.AlignHCenter | Qt.AlignTop)
        self.zoom_badge = ZoomBadge(self.viewport())

        # 사용자가 직접 스크롤할 때만 비율을 업데이트하여 리사이즈 중의 간섭을 방지합니다.
        self.verticalScrollBar().valueChanged.connect(self._update_stable_ratio)
        # 리사이즈 등으로 인해 스크롤 범위가 변할 때 즉시 비율을 적용하여 깜빡임을 방지합니다.
        self.verticalScrollBar().rangeChanged.connect(self._on_range_changed)

    def _update_stable_ratio(self):
        if not self.is_adjusting:
            vbar = self.verticalScrollBar()
            m = vbar.maximum()
            if m > 0:
                self.stable_ratio = vbar.value() / m

    def _on_range_changed(self, min_val, max_val):
        # 리사이즈 중이거나 이미지를 로딩 중일 때 비율을 유지합니다.
        if self.is_adjusting and self.stable_ratio > 0:
            self.verticalScrollBar().setValue(int(max_val * self.stable_ratio))

    def zoom_in(self, anchor_pos=None):
        new_factor = min(self.max_zoom, self.zoom_factor * 1.15)
        self.set_zoom_factor(new_factor, anchor_pos)

    def zoom_out(self, anchor_pos=None):
        if self.zoom_factor <= 1.0:
            return  # 100% 이하로는 축소 불가
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

        # 앵커 마우스 좌표: 마우스 포인터가 가리키고 있는 뷰포트 내 지점
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
        self.is_adjusting = True

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
            self._update_stable_ratio()
            self.is_adjusting = False

        QTimer.singleShot(0, apply_scroll)

        pct = int(round(self.zoom_factor * 100))
        label_text = f"{pct}% (화면 맞춤)" if self.zoom_factor == 1.0 else f"{pct}%"
        self.zoom_badge.show_zoom(label_text, vp.width())

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
                if hasattr(event, 'globalPosition'):
                    g_pos = event.globalPosition().toPoint()
                else:
                    g_pos = QCursor.pos()
                mouse_pos = self.viewport().mapFromGlobal(g_pos)
                if delta > 0:
                    self.zoom_in(mouse_pos)
                else:
                    self.zoom_out(mouse_pos)
                event.accept()
                return

        # Shift + Wheel = 가로 스크롤
        if modifiers & Qt.ShiftModifier:
            delta = event.angleDelta().y() or event.angleDelta().x()
            new_val = self.horizontalScrollBar().value() - int(delta)
            self.horizontalScrollBar().setValue(new_val)
            event.accept()
            return

        # 일반 휠 스크롤 (세로 및 트랙패드 가로 스크롤 지원)
        delta_y = event.angleDelta().y()
        delta_x = event.angleDelta().x()
        if delta_y != 0:
            new_value = self.verticalScrollBar().value() - int(delta_y)
            self.verticalScrollBar().setValue(new_value)
        if delta_x != 0:
            new_value = self.horizontalScrollBar().value() - int(delta_x)
            self.horizontalScrollBar().setValue(new_value)
        event.accept()

    def keyPressEvent(self, event):
        modifiers = event.modifiers()
        is_ctrl_or_cmd = bool(modifiers & (Qt.ControlModifier | Qt.MetaModifier))
        if is_ctrl_or_cmd:
            if event.key() in (Qt.Key_0, Qt.Key_ParenRight):
                self.reset_zoom()
                event.accept()
                return
            elif event.key() in (Qt.Key_Plus, Qt.Key_Equal):
                self.zoom_in()
                event.accept()
                return
            elif event.key() in (Qt.Key_Minus, Qt.Key_Underscore):
                self.zoom_out()
                event.accept()
                return
        super().keyPressEvent(event)

    def get_scroll_ratio(self):
        return self.stable_ratio

    def set_scroll_ratio(self, ratio):
        if ratio <= 0: return
        self.stable_ratio = ratio
        self.is_adjusting = True
        # 레이아웃이 완전히 정해진 후 적용하기 위해 지연 실행
        QTimer.singleShot(100, lambda: self._apply_ratio(ratio))

    def _apply_ratio(self, ratio):
        vbar = self.verticalScrollBar()
        m = vbar.maximum()
        if m > 0:
            vbar.setValue(int(m * ratio))
        self.is_adjusting = False

    def resizeEvent(self, event):
        # 리사이즈 시작 시 잠금
        self.is_adjusting = True
        super().resizeEvent(event)
        content = self.widget()
        if content:
            if self.zoom_factor == 1.0:
                content.setMinimumWidth(0)
                content.setMaximumWidth(16777215)
                content.resize(self.viewport().width(), content.height())
            else:
                target_w = int(self.viewport().width() * self.zoom_factor)
                content.setFixedWidth(target_w)
        if hasattr(self, 'zoom_badge') and self.zoom_badge.isVisible():
            x = max(10, self.viewport().width() - self.zoom_badge.width() - 20)
            self.zoom_badge.move(x, 20)
        # 리사이즈 완료 후 잠금 해제 (연속 리사이즈 시 계속 연장됨)
        QTimer.singleShot(100, self._stop_adjusting)

    def _stop_adjusting(self):
        self.is_adjusting = False

# =================================================================
# 팝업 리스트 델리게이트
# =================================================================
class PopupItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        if platform.system().lower() == "darwin":
            size.setHeight(40)
        else:
            size.setHeight(36)
        return size

    def initStyleOption(self, option, index):
        """렌더링 직전에 호출되는 올바른 훅 지점에서 Pretendard 폰트를 강제 적용합니다.
        paint()에서 option.font를 수정하는 것은 이미 style 엔진이 폰트를 읽은 후이므로
        효과가 없습니다. initStyleOption이 올바른 방법입니다."""
        super().initStyleOption(option, index)
        font = QFont("Pretendard")
        if platform.system().lower() == "darwin":
            font.setPixelSize(14)
        else:
            font.setPointSize(11)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            font.setWeight(QFont.Weight.Medium)
        option.font = font

    def paint(self, painter, option, index):
        painter.save()
        # 안티앨리어싱 명시적 활성화 (글자 깨짐 방지 핵심)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.setRenderHint(QPainter.TextAntialiasing, True)
        
        # Pretendard 폰트 설정
        font = QFont("Pretendard")
        if platform.system().lower() == "darwin":
            font.setPixelSize(14)
        else:
            font.setPointSize(11)
        font.setStyleStrategy(QFont.StyleStrategy.PreferAntialias)
        font.setHintingPreference(QFont.HintingPreference.PreferNoHinting)
        if platform.system() == "Windows":
            font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        
        # 상태별 색상 매핑
        from PySide6.QtWidgets import QStyle
        is_selected = bool(option.state & QStyle.State_Selected)
        is_hover = bool(option.state & QStyle.State_MouseOver)
        
        if is_selected:
            bg_color = QColor("#fff0f0") # 연한 분홍 배경
            text_color = QColor("#111827") # 고대비 어두운 텍스트
        elif is_hover:
            bg_color = QColor("#fff8f8") # 더 연한 호버 배경
            text_color = QColor("#111827") # 고대비 어두운 텍스트
        else:
            bg_color = QColor("#ffffff")
            text_color = QColor("#333333")
            
        # 배경 (둥근 모서리 적용)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(bg_color))
        rect = option.rect.adjusted(1, 1, -1, -1)
        painter.drawRoundedRect(rect, 5, 5)
        
        # 텍스트 그리기
        text = index.data(Qt.DisplayRole)
        if text:
            painter.setPen(QPen(text_color))
            # 패딩 10px 부여
            text_rect = rect.adjusted(10, 0, -10, 0)
            painter.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, text)
            
        painter.restore()

# =================================================================
# 호버 아이콘 버튼
# =================================================================
class HoverIconButton(QPushButton):
    def __init__(self, text, icon_path, normal_color="#333333", hover_color="#FF4B4B", parent=None):
        super().__init__(text, parent)
        self.icon_path = icon_path
        self.normal_icon = get_colored_icon(icon_path, normal_color)
        self.hover_icon = get_colored_icon(icon_path, hover_color)
        
        self.setIcon(self.normal_icon)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        self.setIcon(self.hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.setIcon(self.normal_icon)
        super().leaveEvent(event)

# =================================================================
# 부분 영역 지정을 위한 반투명 드래그 오버레이 (SelectionOverlay)
# =================================================================
class SelectionOverlay(QWidget):
    area_selected = Signal(QRect)
    closed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.start_pos = None
        self.end_pos = None
        self.is_dragging = False
        self.setCursor(Qt.CrossCursor)
        self.hide()

    def hide(self):
        super().hide()
        self.closed.emit()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # 전체 영역 크기
        full_rect = self.rect()

        if self.start_pos and self.end_pos:
            rect = QRect(self.start_pos, self.end_pos).normalized()

            # QPainterPath로 어두운 영역 설정 (전체 영역 - 선택 영역)
            from PySide6.QtGui import QPainterPath
            path = QPainterPath()
            path.addRect(QRectF(full_rect))
            
            sub_path = QPainterPath()
            sub_path.addRect(QRectF(rect))
            
            # 전체 영역에서 드래그 사각형을 뺍니다
            draw_path = path.subtracted(sub_path)

            # 도려낸 어두운 영역 칠하기
            dim_color = QColor(0, 0, 0, 100)
            painter.fillPath(draw_path, QBrush(dim_color))

            # 테두리 그리기 (오렌지 점선)
            border_pen = QPen(QColor("#FF5722"), 2, Qt.DashLine)
            painter.setPen(border_pen)
            painter.setBrush(Qt.NoBrush)
            painter.drawRect(rect)
        else:
            # 드래그 전에는 전체를 어둡게 표시
            dim_color = QColor(0, 0, 0, 100)
            painter.fillRect(full_rect, dim_color)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_pos = event.pos()
            self.end_pos = event.pos()
            self.is_dragging = True
            self.setFocus()  # ESC 키 입력을 바로 잡아채도록 포커스 획득
            self.update()

    def mouseMoveEvent(self, event):
        if self.is_dragging:
            self.end_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.is_dragging:
            self.end_pos = event.pos()
            self.is_dragging = False
            
            rect = QRect(self.start_pos, self.end_pos).normalized()
            if rect.width() > 5 and rect.height() > 5:
                self.area_selected.emit(rect)
            
            self.start_pos = None
            self.end_pos = None
            self.releaseKeyboard()
            self.hide()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.start_pos = None
            self.end_pos = None
            self.is_dragging = False
            self.releaseKeyboard()
            self.hide()
            event.accept()
        else:
            super().keyPressEvent(event)

# =================================================================
# 부분 영역 재분석 가이드 말풍선 메시지
# =================================================================
class ReanalysisGuideBubble(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 10, 12, 10)  # 화살표 공간 확보를 위해 왼쪽 마진을 크게 줌
        
        self.lbl_text = QLabel("텍스트가 있는 부분을 드래그해서 분석합니다.\n(취소: ESC)")
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 13px;
                font-weight: bold;
                font-family: 'Pretendard';
                background: transparent;
                border: none;
            }
        """)
        layout.addWidget(self.lbl_text)
        self.adjustSize()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        w = self.width()
        h = self.height()
        
        arrow_width = 8
        arrow_height = 12
        
        path = QPainterPath()
        rect = QRectF(arrow_width, 0, w - arrow_width, h)
        path.addRoundedRect(rect, 8, 8)
        
        # 왼쪽을 가리키는 삼각형
        triangle = QPolygonF([
            QPointF(0, h / 2),
            QPointF(arrow_width, h / 2 - arrow_height / 2),
            QPointF(arrow_width, h / 2 + arrow_height / 2)
        ])
        path.addPolygon(triangle)
        
        # 선명한 오렌지 색상 브랜드 컬러
        painter.fillPath(path, QBrush(QColor("#FF5722")))

# =================================================================
# 드롭 오버레이 (메인용/드래그용)
# =================================================================
class DropOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        from PySide6.QtWidgets import QLabel
        self.lbl_text = QLabel("파일을 여기에 드롭하세요", self)
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet("""
            QLabel {
                font-family: 'Pretendard', '-apple-system', 'Helvetica Neue', 'Segoe UI', sans-serif;
                font-size: 27px;
                font-weight: bold;
                color: #1E293B;
                background: transparent;
                border: none;
            }
        """)
        
        self.hide()
        self.snapshot = None 

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # 이미지 크기(100px) 증가 및 겹침 방지를 위해 텍스트의 y 위치를 조절하여 간격을 넓힙니다.
        y_pos = self.height() // 2 + 25
        self.lbl_text.setGeometry(0, y_pos, self.width(), 45)

    def set_snapshot(self, pixmap):
        self.snapshot = pixmap
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.snapshot:
            painter.drawPixmap(0, 0, self.snapshot)

        tint_color = QColor(251, 146, 60, 100) 
        painter.fillRect(self.rect(), tint_color)

        border_pen = QPen(QColor("#FB923C"), 4, Qt.DashLine)
        painter.setPen(border_pen)
        margin = 15
        painter.drawRoundedRect(
            margin, margin, 
            self.width() - margin * 2, 
            self.height() - margin * 2, 
            12, 12
        )

        svg_path = config.ICON_AVATAR_UPLOAD
        icon_size = 100 # 80에서 100으로 25% 크기 증가
        cx = (self.width() - icon_size) // 2
        cy = (self.height() - icon_size) // 2 - 45 # 텍스트와의 겹침 방지 및 여백 확보를 위해 위치 조정
        svg_pix = get_colored_pixmap(svg_path, "#1E293B", icon_size, icon_size)
        painter.drawPixmap(cx, cy, svg_pix)

    def dragEnterEvent(self, event):
        print("DEBUG: DropOverlay dragEnterEvent")
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.hide()

    def dropEvent(self, event):
        self.hide()
        mw = self.window()
        if hasattr(mw, 'file_list_widget'):
            mw.file_list_widget.set_highlight(False)
            
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            files = [u.toLocalFile() for u in urls]
            
            if hasattr(mw, 'process_image_files'):
                mw.process_image_files(files)
        else:
            event.ignore()

# =================================================================
# =================================================================
# 플랫 아이템 델리게이트 (선택/포커스 시 3D 볼록 테두리 제거)
# =================================================================
class FlatItemDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        opt = QStyleOptionViewItem(option)
        opt.state &= ~QStyle.State_HasFocus
        super().paint(painter, opt, index)

# =================================================================
# 파일 드롭 리스트 위젯
# =================================================================
class FileDropListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        self.setItemDelegate(FlatItemDelegate(self))
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        scrollbar_style = """
            QScrollBar:horizontal {
                border: none;
                background: #F3F4F6;
                height: 8px;
                margin: 0px 2px 2px 2px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal {
                background: #D1D5DB;
                min-width: 25px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #9CA3AF;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                width: 0px;
                height: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
            QScrollBar:vertical {
                border: none;
                background: #F3F4F6;
                width: 8px;
                margin: 2px 2px 2px 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #D1D5DB;
                min-height: 25px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #9CA3AF;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                width: 0px;
                height: 0px;
                background: none;
                border: none;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
            QScrollBar::corner {
                background: transparent;
            }
        """

        self.normal_style = f"""
            QListWidget {{ 
                border: 1px solid #d1d5db; 
                background: white; 
                border-radius: 4px; 
                padding: 5px; 
                color: #333; 
                outline: none;
            }}
            QListWidget::item {{ 
                border: none;
                outline: none;
                padding: 6px 8px;
                border-radius: 4px;
            }}
            QListWidget::item:focus {{
                border: none;
                outline: none;
            }}
            QListWidget::item:selected {{ 
                background-color: #FFECEC; 
                color: #FF4B4B; 
                border: none;
                outline: none;
            }}
            QListWidget::item:selected:focus {{ 
                background-color: #FFECEC; 
                color: #FF4B4B; 
                border: none;
                outline: none;
            }}
            {scrollbar_style}
        """

        self.active_style = f"""
            QListWidget {{ 
                border: 2px dashed #FB923C; /* 오렌지색 점선 */
                background: #FFF7ED;        /* 아주 연한 오렌지색 배경 */
                border-radius: 6px; 
                outline: none;
            }}
            QListWidget::item {{ 
                border: none;
                outline: none;
                padding: 6px 8px;
                border-radius: 4px;
            }}
            QListWidget::item:focus {{
                border: none;
                outline: none;
            }}
            QListWidget::item:selected {{ 
                background-color: #FFECEC; 
                color: #FF4B4B; 
                border: none;
                outline: none;
            }}
            QListWidget::item:selected:focus {{ 
                background-color: #FFECEC; 
                color: #FF4B4B; 
                border: none;
                outline: none;
            }}
            {scrollbar_style}
        """
        self.setStyleSheet(self.normal_style)

        self.overlay_label = QLabel("📂 여기에 파일을 놓으세요", self)
        self.overlay_label.setAlignment(Qt.AlignCenter)
        self.overlay_label.setStyleSheet("""
            color: #FB923C; 
            font-weight: bold; 
            font-size: 15px; 
            background: transparent;
        """)
        self.overlay_label.hide()
        self.overlay_label.setAttribute(Qt.WA_TransparentForMouseEvents)

    def delete_selected_items(self):
        selected_items = self.selectedItems()
        if not selected_items: return

        mw = self.window()
        try:
            e_path, i_path, _ = mw.get_paths()
            abs_i_path = os.path.abspath(i_path) if i_path else ""
        except Exception as e:
            print(f"경로 획득 실패: {e}")
            return

        if not e_path:
            return

        # 1. episode_info.json 로드 (외부 참조 모드 메타데이터 확인)
        info_file = os.path.join(e_path, "episode_info.json")
        has_info = os.path.exists(info_file)
        info_data = {}
        external_images = []
        is_external_mode = False
        if has_info:
            try:
                with open(info_file, "r", encoding="utf-8") as f:
                    info_data = json.load(f)
                    if "external_images" in info_data:
                        is_external_mode = True
                        external_images = list(info_data.get("external_images", []))
            except Exception as e:
                print(f"episode_info.json 로드 실패: {e}")

        # 설정이 원본 유지 모드인 경우에도 외부 참조 모드로 판정
        if not getattr(config, 'COPY_IMAGES_TO_PROJECT', True):
            is_external_mode = True

        deleted_count = 0
        external_updated = False

        for item in selected_items:
            display_text = item.text()
            file_name = display_text.replace("📄", "").strip()
            norm_target_name = unicodedata.normalize('NFC', os.path.normcase(file_name))

            stored_path = item.data(Qt.UserRole)
            norm_stored_path = unicodedata.normalize('NFC', os.path.normcase(os.path.abspath(stored_path))) if stored_path else ""

            # (A) 외부 참조 모드인 경우:
            # 컴퓨터의 원본 파일은 지우지 않고 안전하게 보존하며, 회차의 외부 참조 목록에서만 제거!
            matched_external = None
            if is_external_mode and external_images:
                for ext_p in external_images:
                    norm_ext_abs = unicodedata.normalize('NFC', os.path.normcase(os.path.abspath(ext_p)))
                    norm_ext_base = unicodedata.normalize('NFC', os.path.normcase(os.path.basename(ext_p)))
                    if norm_stored_path and norm_stored_path == norm_ext_abs:
                        matched_external = ext_p
                        break
                    elif norm_target_name == norm_ext_base:
                        matched_external = ext_p
                        break

            if matched_external:
                external_images.remove(matched_external)
                external_updated = True
                deleted_count += 1
                continue

            # (B) 기본 복사 모드인 경우: images/ 폴더 안의 복사본 파일 직접 삭제
            full_path = stored_path if stored_path and os.path.exists(stored_path) else os.path.join(abs_i_path, file_name)
            if full_path and os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    deleted_count += 1
                except Exception as e:
                    print(f"삭제 실패 ({file_name}): {e}")
            else:
                # 파일명이 직접 일치하는 경우도 탐색
                deleted_by_name = False
                if abs_i_path and os.path.exists(abs_i_path):
                    for f in os.listdir(abs_i_path):
                        if unicodedata.normalize('NFC', os.path.normcase(f)) == norm_target_name:
                            try:
                                os.remove(os.path.join(abs_i_path, f))
                                deleted_count += 1
                                deleted_by_name = True
                                break
                            except Exception:
                                pass
                if not deleted_by_name:
                    print(f"❌ 파일을 찾을 수 없습니다: {file_name}")

        # 외부 참조 목록 갱신 저장
        if external_updated:
            info_data["external_images"] = external_images
            try:
                with open(info_file, "w", encoding="utf-8") as f:
                    json.dump(info_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"episode_info.json 갱신 실패: {e}")

        # 삭제 후 목록 및 뷰어 갱신
        if hasattr(mw, 'load_images'):
            mw.load_images()
        if hasattr(mw, 'load_data'):
            mw.load_data()
            
        if hasattr(mw, 'toast'):
            mw.toast.show_message(f"✨ {deleted_count}개의 파일 삭제 완료")

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.delete_selected_items()
            event.accept()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, pos):
        item = self.itemAt(pos)
        if item and not item.isSelected():
            self.clearSelection()
            item.setSelected(True)
            self.setCurrentItem(item)

        selected_items = self.selectedItems()
        if not selected_items:
            return

        menu = QMenu(self)
        menu.setFont(QApplication.font())
        count = len(selected_items)
        del_label = f"선택한 파일 지우기 ({count}개)" if count > 1 else "선택한 파일 지우기"
        delete_action = QAction(get_icon(config.ICON_DELETE), del_label, self)
        delete_action.triggered.connect(self.delete_selected_items)
        menu.addAction(delete_action)
        menu.exec(self.mapToGlobal(pos))

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            mw = self.window()
            if hasattr(mw, 'overlay'):
                mw.overlay.setGeometry(mw.rect())
                mw.overlay.show()
                mw.overlay.raise_()
            
            self.set_highlight(True)
            event.accept()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if event.mimeData().hasUrls():
            self.set_highlight(True)
            event.accept()
        else:
            event.ignore()

    def dragLeaveEvent(self, event):
        self.set_highlight(False)

    def dropEvent(self, event):
        self.set_highlight(False)
        if event.mimeData().hasUrls():
            event.accept()
            files = [u.toLocalFile() for u in event.mimeData().urls()]
            mw = self.window()
            if hasattr(mw, 'process_image_files'):
                mw.process_image_files(files)
        else:
            event.ignore()

    def set_highlight(self, active: bool):
        if active:
            self.setStyleSheet(self.active_style)
            self.overlay_label.show()
        else:
            self.setStyleSheet(self.normal_style)
            self.overlay_label.hide()

    def resizeEvent(self, event):
        self.overlay_label.setGeometry(0, 0, self.width(), self.height())
        super().resizeEvent(event)

        if hasattr(self, 'btn_toggle') and hasattr(self, 'sidebar'):
            margin_right = 10 
            margin_top = 10   
            
            new_x = self.sidebar.width() - self.btn_toggle.width() - margin_right
            if new_x < 0: new_x = 10
            self.btn_toggle.move(new_x, margin_top)
            self.btn_toggle.raise_()

# =================================================================
# 스마트 텍스트 에디터
# =================================================================
class SmartTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

    def keyPressEvent(self, event):
        if event.modifiers() == (Qt.ControlModifier | Qt.ShiftModifier) and event.key() == Qt.Key_Z:
            self.redo()
            event.accept()
        else:
            super().keyPressEvent(event)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            mw = self.window()
            if hasattr(mw, 'overlay'):
                mw.overlay.setGeometry(mw.rect())
                mw.overlay.show()
                mw.overlay.raise_()
            event.accept()
        else:
            super().dragEnterEvent(event)

    def insertFromMimeData(self, source):
        if source.hasUrls():
            mw = self.window()
            if hasattr(mw, 'process_image_files'):
                urls = source.urls()
                files = [u.toLocalFile() for u in urls]
                image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if image_files:
                    mw.process_image_files(image_files)
        elif source.hasText():
            # 웹 브라우저 등에서 복사한 서식(HTML, 스타일)이 포함된 Rich Text를 무시하고 순수 텍스트(Plain Text)로만 붙여넣기
            self.insertPlainText(source.text())
        else:
            super().insertFromMimeData(source)

    def contextMenuEvent(self, event):
        menu = self.createStandardContextMenu()
        actions = menu.actions()
        for action in actions:
            text = action.text()
            clean_text = text.replace("&", "")
            clean_text_lower = clean_text.lower()
            
            if "undo" in clean_text_lower or "되돌리기" in clean_text_lower or "실행 취소" in clean_text_lower or "실행취소" in clean_text_lower:
                action.setText("되돌리기 (&U)")
                action.setShortcut(QKeySequence("Ctrl+Z"))
            elif "redo" in clean_text_lower or "다시 실행" in clean_text_lower or "다시실행" in clean_text_lower:
                redo_action = QAction("다시 실행 (&R)", self)
                redo_action.setIcon(action.icon())
                redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))
                redo_action.setEnabled(action.isEnabled())
                redo_action.triggered.connect(self.redo)
                menu.insertAction(action, redo_action)
                menu.removeAction(action)
            elif "cut" in clean_text_lower or "잘라내기" in clean_text_lower:
                action.setText("잘라내기 (&T)")
                action.setShortcut(QKeySequence("Ctrl+X"))
            elif "copy" in clean_text_lower or "복사" in clean_text_lower:
                action.setText("복사 (&C)")
                action.setShortcut(QKeySequence("Ctrl+C"))
            elif "paste" in clean_text_lower or "붙여넣기" in clean_text_lower:
                action.setText("붙여넣기 (&P)")
                action.setShortcut(QKeySequence("Ctrl+V"))
            elif "delete" in clean_text_lower or "삭제" in clean_text_lower:
                action.setText("삭제 (&D)")
            elif "select all" in clean_text_lower or "모두 선택" in clean_text_lower or "모두선택" in clean_text_lower:
                action.setText("모두 선택 (&A)")
                action.setShortcut(QKeySequence("Ctrl+A"))
                
        menu.exec(event.globalPos())

# =================================================================
# 토스트 메시지
# =================================================================
class ToastMessage(QWidget):
    def __init__(self, parent):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.bg_frame = QFrame()
        self.bg_frame.setFrameShape(QFrame.NoFrame)
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: #282C34;
                border-radius: 18px;
                border: none;
            }
        """)
        frame_layout = QHBoxLayout(self.bg_frame)
        frame_layout.setContentsMargins(18, 11, 18, 11)
        frame_layout.setSpacing(8)
        
        self.lbl_icon = QLabel()
        self.lbl_icon.setFixedSize(18, 18)
        self.lbl_icon.setStyleSheet("background: transparent; border: none;")
        self.lbl_icon.hide()
        
        self.lbl_text = QLabel()
        self.lbl_text.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Pretendard';
                background: transparent;
                border: none;
            }
        """)
        
        frame_layout.addWidget(self.lbl_icon)
        frame_layout.addWidget(self.lbl_text)
        layout.addWidget(self.bg_frame)
        
        self.hide()
        
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setEasingCurve(QEasingCurve.InOutSine) 
        
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)

    def show_message(self, text, duration=4000, fade_speed=400):
        self.timer.stop()
        self.anim.stop()
        
        # 이모지 검출 및 텍스트 정제
        clean_text = text
        emoji = ""
        for char in ["✅", "🗑️", "✨", "⚠️", "❌", "📄", "👥", "⏳", "📶", "🔄", "🚫", "🏢", "📊", "⚡"]:
            if clean_text.startswith(char):
                emoji = char
                clean_text = clean_text[len(char):].strip()
                break
                
        # 매칭되는 아이콘 표시
        if emoji:
            icon_path = ""
            icon_color = "#FFFFFF"
            if emoji == "✅":
                icon_path = config.ICON_SUCCESS
                icon_color = "#10B981" # 성공: 녹색
            elif emoji == "🗑️":
                icon_path = config.ICON_DELETE
                icon_color = "#EF4444" # 삭제: 빨간색
            elif emoji == "✨":
                icon_path = config.ICON_INFO
                icon_color = "#F59E0B" # 정보: 오렌지
            elif emoji == "⚠️":
                icon_path = config.ICON_WARNING
                icon_color = "#FBBF24" # 경고: 노란색
            elif emoji == "❌":
                icon_path = config.ICON_WARNING
                icon_color = "#EF4444" # 에러: 빨간색
            elif emoji == "📄":
                icon_path = config.ICON_FILE
                icon_color = "#3B82F6" # 파일: 파란색
            elif emoji == "👥":
                icon_path = config.ICON_USER
                icon_color = "#8B5CF6" # 캐릭터/사용자: 보라색
            elif emoji == "⏳":
                icon_path = config.ICON_REFRESH
                icon_color = "#9CA3AF" # 로딩/대기: 회색
            elif emoji == "📶":
                icon_path = config.ICON_ARROW_UP
                icon_color = "#3B82F6" # 정렬: 파란색
            elif emoji == "🔄":
                icon_path = config.ICON_REFRESH
                icon_color = "#3B82F6" # 새로고침/업데이트: 파란색
            elif emoji == "🚫":
                icon_path = config.ICON_WARNING
                icon_color = "#EF4444" # 중지/금지: 빨간색
            elif emoji == "🏢":
                icon_path = config.ICON_SETTINGS_COG
                icon_color = "#3B82F6" # 전체 모드: 파란색
            elif emoji == "📊":
                icon_path = config.ICON_EXCEL
                icon_color = "#10B981" # 엑셀: 녹색
            elif emoji == "⚡":
                icon_path = config.ICON_INFO
                icon_color = "#FBBF24" # 빠른처리/캐시: 노란색
                
            if icon_path:
                pix = get_colored_pixmap(icon_path, icon_color, 18, 18)
                self.lbl_icon.setPixmap(pix)
                self.lbl_icon.show()
            else:
                self.lbl_icon.hide()
        else:
            self.lbl_icon.hide()
            
        self.lbl_text.setText(clean_text)
        
        # 크기 자동 조절
        self.lbl_text.adjustSize()
        self.bg_frame.adjustSize()
        self.adjustSize()
        
        if self.parent():
            parent_geom = self.parent().frameGeometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + parent_geom.height() - self.height() - 80
            self.move(x, y)
        
        self.show()
        if fade_speed > 0:
            self.opacity_effect.setOpacity(0.0) 
            self.anim.setDuration(fade_speed)
            self.anim.setStartValue(0.0)
            self.anim.setEndValue(1.0)
            self.anim.start()
        else:
            self.opacity_effect.setOpacity(1.0)
        
        self.timer.start(duration)

    def fade_out(self):
        self.anim.stop()
        self.anim.setDuration(600) 
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        self.anim.start()
        
        QTimer.singleShot(600, self.hide)

# =================================================================
# 이미지 라운드 처리 헬퍼
# =================================================================
def get_round_pixmap(pixmap, size=32):
    if pixmap.isNull():
        return pixmap
        
    target = QPixmap(size, size)
    target.fill(Qt.transparent)
    
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    path.addEllipse(0, 0, size, size)
    painter.setClipPath(path)
    
    scaled = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (size - scaled.width()) // 2
    y = (size - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    painter.end()
    
    return target

def get_round_rect_pixmap(pixmap, w, h, radius=8):
    if pixmap.isNull():
        return pixmap
        
    target = QPixmap(w, h)
    target.fill(Qt.transparent)
    
    painter = QPainter(target)
    painter.setRenderHint(QPainter.Antialiasing, True)
    painter.setRenderHint(QPainter.SmoothPixmapTransform, True)
    
    from PySide6.QtGui import QPainterPath
    path = QPainterPath()
    path.addRoundedRect(0, 0, w, h, radius, radius)
    painter.setClipPath(path)
    
    scaled = pixmap.scaled(w, h, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
    x = (w - scaled.width()) // 2
    y = (h - scaled.height()) // 2
    painter.drawPixmap(x, y, scaled)
    
    painter.setClipping(False)
    painter.setPen(QPen(QColor("#E5E7EB"), 1))
    painter.setBrush(Qt.NoBrush)
    painter.drawRoundedRect(0.5, 0.5, w - 1, h - 1, radius, radius)
    
    painter.end()
    
    return target

# =================================================================
# macOS 싱글클릭 지원 QLineEdit (포커스가 없어도 X버튼 클릭 시 즉시 지워지도록 처리)
# =================================================================
class SingleClickLineEdit(QLineEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._install_filter_on_children()
        
    def childEvent(self, event):
        super().childEvent(event)
        if event.type() == QEvent.ChildAdded:
            # 0ms timer ensures children are fully initialized and bound
            QTimer.singleShot(0, self._install_filter_on_children)

    def _install_filter_on_children(self):
        from PySide6.QtWidgets import QToolButton
        for child in self.findChildren(QToolButton):
            child.removeEventFilter(self)
            child.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PySide6.QtWidgets import QToolButton
        if isinstance(obj, QToolButton) or obj.inherits("QToolButton"):
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton:
                    self.clear()
                    event.accept()
                    return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, event):
        from PySide6.QtWidgets import QToolButton
        btn = self.findChild(QToolButton)
        if btn and btn.isVisible() and btn.geometry().contains(event.pos()):
            self.clear()
            event.accept()
            return
        super().mousePressEvent(event)

# =================================================================
# 회전하는 SVG 로딩 아이콘 라벨
# =================================================================
class SpinningIconLabel(QLabel):
    def __init__(self, icon_path, color="#FF5722", size=22, parent=None):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self.pixmap = get_colored_pixmap(icon_path, color, size, size)
        self.angle = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.rotate)
        self.timer.start(30)

    def rotate(self):
        self.angle = (self.angle + 8) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        
        # 중심점 기준 회전
        painter.translate(self.width() / 2, self.height() / 2)
        painter.rotate(self.angle)
        painter.translate(-self.width() / 2, -self.height() / 2)
        
        painter.drawPixmap(self.rect(), self.pixmap)

# =================================================================
# 프리미엄 디자인 커스텀 로딩 다이얼로그
# =================================================================
class ModernProgressDialog(QDialog):
    def __init__(self, label_text, cancel_button_text, minimum, maximum, parent=None):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint | Qt.WindowSystemMenuHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        self.minimum = minimum
        self.maximum = maximum
        self.value = minimum
        self.canceled = False
        
        self.init_ui(label_text, cancel_button_text)
        
    def init_ui(self, label_text, cancel_button_text):
        if cancel_button_text:
            self.setFixedSize(420, 170)
        elif self.maximum == 0:
            self.setFixedSize(420, 115)
        else:
            self.setFixedSize(420, 145)
        
        # 메인 레이아웃 (그림자 여백 확보를 위해 마진 설정)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 다이얼로그 바디 프레임
        self.body = QFrame(self)
        self.body.setObjectName("ProgressBody")
        self.body.setStyleSheet("""
            QFrame#ProgressBody {
                background-color: #FFFFFF;
                border: 1px solid #FFE5D9;
                border-radius: 12px;
            }
        """)
        
        # 고급스러운 그림자 효과 적용
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(0, 0, 0, 15))
        shadow.setOffset(0, 3)
        self.body.setGraphicsEffect(shadow)
        
        body_layout = QVBoxLayout(self.body)
        if cancel_button_text or self.maximum > 0:
            body_layout.setContentsMargins(24, 24, 24, 20)
        else:
            body_layout.setContentsMargins(24, 24, 24, 24)
        body_layout.setSpacing(16)
        
        # 로딩 메시지와 회전 아이콘을 정렬할 가로 레이아웃
        text_layout = QHBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(12)
        text_layout.setAlignment(Qt.AlignVCenter)
        
        # 로딩 스피너 추가 (config.ICON_REFRESH를 이용해 회전)
        self.spinner = SpinningIconLabel(config.ICON_REFRESH, color="#FF5722", size=22, parent=self.body)
        text_layout.addWidget(self.spinner)
        
        # 텍스트에서 이모지 제거
        clean_text = label_text
        if clean_text.startswith("⏳"):
            clean_text = clean_text[1:].strip()
        elif clean_text.startswith("⌛"):
            clean_text = clean_text[1:].strip()
            
        self.lbl_text = QLabel(clean_text, self.body)
        self.lbl_text.setStyleSheet("""
            font-family: 'Pretendard';
            font-size: 14px;
            font-weight: bold;
            color: #1F2937;
            background: transparent;
            border: none;
        """)
        self.lbl_text.setWordWrap(True)
        text_layout.addWidget(self.lbl_text, 1)
        
        body_layout.addLayout(text_layout)
        
        # 프로그레스바
        from PySide6.QtWidgets import QProgressBar
        self.progress_bar = QProgressBar(self.body)
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setRange(self.minimum, self.maximum)
        self.progress_bar.setValue(self.value)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                background-color: #F3F4F6;
                border-radius: 4px;
                border: none;
            }
            QProgressBar::chunk {
                background-color: #FF5722;
                border-radius: 4px;
            }
        """)
        body_layout.addWidget(self.progress_bar)
        
        # 하단 정보 및 버튼 레이아웃
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        
        # 진행 상태 텍스트
        init_percent = f"{int((self.value / self.maximum) * 100)}%" if self.maximum > 0 else ""
        self.lbl_percent = QLabel(init_percent, self.body)
        self.lbl_percent.setStyleSheet("""
            font-family: 'Pretendard';
            font-size: 12px;
            color: #6B7280;
            background: transparent;
            border: none;
        """)
        if self.maximum == 0:
            self.lbl_percent.hide()
        bottom_layout.addWidget(self.lbl_percent)
        bottom_layout.addStretch()
        
        # 중단(취소) 버튼
        if cancel_button_text:
            self.btn_cancel = QPushButton(cancel_button_text, self.body)
            self.btn_cancel.setFixedSize(70, 30)
            self.btn_cancel.setCursor(Qt.PointingHandCursor)
            self.btn_cancel.setStyleSheet("""
                QPushButton {
                    background-color: white;
                    border: 1px solid #D1D5DB;
                    border-radius: 6px;
                    color: #4B5563;
                    font-family: 'Pretendard';
                    font-size: 12px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #F9FAFB;
                    border-color: #9CA3AF;
                    color: #1F2937;
                }
            """)
            self.btn_cancel.clicked.connect(self.on_cancel_clicked)
            bottom_layout.addWidget(self.btn_cancel)
            
        if cancel_button_text or self.maximum > 0:
            body_layout.addLayout(bottom_layout)
        layout.addWidget(self.body)
        
    def on_cancel_clicked(self):
        self.canceled = True
        self.reject()
        
    def setValue(self, val):
        self.value = val
        self.progress_bar.setValue(val)
        if self.maximum == 0:
            self.lbl_percent.hide()
        else:
            percent = int((val / self.maximum) * 100) if self.maximum > 0 else 0
            self.lbl_percent.setText(f"{percent}%")
            self.lbl_percent.show()
        QApplication.processEvents()
        
    def setLabelText(self, text):
        clean_text = text
        if clean_text.startswith("⏳"):
            clean_text = clean_text[1:].strip()
        elif clean_text.startswith("⌛"):
            clean_text = clean_text[1:].strip()
        self.lbl_text.setText(clean_text)
        QApplication.processEvents()
        
    def wasCanceled(self):
        return self.canceled

