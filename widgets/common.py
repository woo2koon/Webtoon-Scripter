# widgets/common.py
import os
import platform
import re
import unicodedata

from PySide6.QtWidgets import (
    QLabel, QComboBox, QListView, QStyledItemDelegate, QScrollArea, QFrame,
    QHBoxLayout, QLineEdit, QPushButton, QWidget, QSizePolicy, QTextEdit,
    QTableWidget, QAbstractItemView, QTableWidgetItem, QApplication, QHeaderView,
    QGraphicsOpacityEffect, QMenu, QDialog, QVBoxLayout, QMessageBox, QInputDialog,
    QListWidget, QListWidgetItem, QStackedWidget, QFileDialog, QCheckBox
)
from PySide6.QtCore import (
    Qt, QEvent, Signal, QTimer, QSize, QEasingCurve, QPropertyAnimation,
    QRect, QRectF, QMimeData, QModelIndex, QByteArray
)
from PySide6.QtGui import (
    QPixmap, QDrag, QPainter, QColor, QPen, QFont, QAction, QIcon,
    QRegion, QBrush, QLinearGradient, QTextCharFormat, QTextFormat,
    QTextCursor, QKeySequence
)
from PySide6.QtSvg import QSvgRenderer

import config
from config import ROLE_OPTIONS, AGE_OPTIONS, GENDER_OPTIONS, PROJECTS_DIR
from utils import get_icon, get_colored_icon, open_path, get_colored_pixmap

# =================================================================
# 이미지 비율 유지 라벨
# =================================================================
class ResponsiveLabel(QLabel):
    def __init__(self, pixmap_path, parent=None):
        super().__init__(parent)
        self.original_pixmap = QPixmap(pixmap_path)
        self.setPixmap(self.original_pixmap)
        self.setScaledContents(True)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Fixed)
        
    def resizeEvent(self, event):
        if not self.original_pixmap.isNull() and self.width() > 0:
            aspect_ratio = self.original_pixmap.height() / self.original_pixmap.width()
            target_height = int(self.width() * aspect_ratio)
            if self.height() != target_height:
                self.setFixedHeight(target_height)
        super().resizeEvent(event)

# =================================================================
# 클릭 시 데이터 새로고침 가능한 콤보박스
# =================================================================
class ClickableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setEditable(True) 
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setCursor(Qt.ArrowCursor)
        self.lineEdit().installEventFilter(self)
        self.installEventFilter(self) # [추가] 자기 자신에게도 필터 설치
        self.setView(QListView())
        
        # [추가] 프리미엄 드롭다운 스타일 (잔상 제거 및 라운드 대응)
        self.view().window().setWindowFlags(Qt.Popup | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint)
        self.view().window().setAttribute(Qt.WA_TranslucentBackground)

        delegate = QStyledItemDelegate()
        self.setItemDelegate(delegate)
        self.refresh_callback = None 
        self._popup_hidden_recently = False

    def showPopup(self):
        # [추가] 콤보박스가 열려서 값이 바뀌기 직전의 상태 저장
        self._trigger_undo_backup()
        super().showPopup()

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
# 스크롤 뷰
# =================================================================
class WebtoonScrollArea(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_adjusting = False
        self.stable_ratio = 0.0
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

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        new_value = self.verticalScrollBar().value() - int(delta)
        self.verticalScrollBar().setValue(new_value)
        event.accept()

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
        size.setHeight(36)
        return size

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
                font-size: 24px;
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
        icon_size = 80
        y_pos = (self.height() - icon_size) // 2 + 50
        self.lbl_text.setGeometry(0, y_pos, self.width(), 40)

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
        icon_size = 80
        cx = (self.width() - icon_size) // 2
        cy = (self.height() - icon_size) // 2 - 20
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
# 파일 드롭 리스트 위젯
# =================================================================
class FileDropListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        self.normal_style = """
            QListWidget { 
                border: 1px solid #d1d5db; 
                background: white; 
                border-radius: 4px; 
                padding: 5px; 
                color: #333; 
            }
        """

        self.active_style = """
            QListWidget { 
                border: 2px dashed #FB923C; /* 오렌지색 점선 */
                background: #FFF7ED;        /* 아주 연한 오렌지색 배경 */
                border-radius: 6px; 
            }
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
            _, i_path, _ = mw.get_paths()
            abs_i_path = os.path.abspath(i_path)
        except Exception as e:
            print(f"경로 획득 실패: {e}")
            return

        deleted_count = 0
        for item in selected_items:
            display_text = item.text()
            file_name = display_text.replace("📄", "").strip()
            file_name = unicodedata.normalize('NFC', file_name)
            full_path = os.path.join(abs_i_path, file_name)

            print(f"DEBUG: 삭제 시도 경로 -> {full_path}")

            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    deleted_count += 1
                    self.takeItem(self.row(item))
                except Exception as e:
                    print(f"삭제 실패 ({file_name}): {e}")
            else:
                print(f"❌ 파일을 찾을 수 없습니다: {file_name}")
                print(f"   ㄴ 상위 폴더 존재 여부: {os.path.exists(abs_i_path)}")
        
        if hasattr(mw, 'load_images'):
            mw.load_images()
        if hasattr(mw, 'load_data'):
            mw.load_data()
            
        if hasattr(mw, 'toast'):
            mw.toast.show_message(f"✨ {deleted_count}개의 파일 삭제 완료")

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Delete:
            self.delete_selected_items()
        else:
            super().keyPressEvent(event)

    def show_context_menu(self, pos):
        menu = QMenu(self)
        delete_action = QAction(get_icon(config.ICON_DELETE), "선택한 파일 지우기", self)
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
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: #282C34;
                border-radius: 18px;
            }
        """)
        frame_layout = QVBoxLayout(self.bg_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        
        self.lbl_text = QLabel()
        self.lbl_text.setAlignment(Qt.AlignCenter)
        self.lbl_text.setStyleSheet("""
            QLabel {
                color: white;
                padding: 10px 18px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Pretendard';
                background: transparent;
            }
        """)
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
        
        self.lbl_text.setText(text)
        self.lbl_text.adjustSize()
        self.adjustSize()
        
        if self.parent():
            parent_geom = self.parent().frameGeometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + parent_geom.height() - self.height() - 80
            self.move(x, y)
        
        self.show()
        self.opacity_effect.setOpacity(0.0) 
        self.anim.setDuration(fade_speed)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
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
