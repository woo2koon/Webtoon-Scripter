# widgets.py
from PySide6.QtWidgets import (QLabel, QComboBox, QListView, QStyledItemDelegate, 
                               QScrollArea, QFrame, QHBoxLayout, QLineEdit, 
                               QPushButton, QWidget, QSizePolicy, QTextEdit,
                               QTableWidget, QAbstractItemView, QTableWidgetItem, QApplication, QHeaderView,
                               QGraphicsOpacityEffect, QMenu, QDialog, QVBoxLayout, QMessageBox, QInputDialog)
from PySide6.QtCore import Qt, QEvent, Signal, QTimer, QSize, QEasingCurve, QPropertyAnimation, QRect, QRectF, QMimeData
from PySide6.QtGui import (
    QPixmap, QDrag, QPainter, QColor, QPen, QFont, QAction, QIcon,
    QRegion, QBrush, QLinearGradient, QTextCharFormat, QTextFormat,
    QTextCursor, QKeySequence
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray
import re
import unicodedata
from config import ROLE_OPTIONS, AGE_OPTIONS, GENDER_OPTIONS, PROJECTS_DIR
from utils import get_icon, get_colored_icon
import config

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
        self.lineEdit().setCursor(Qt.PointingHandCursor)
        self.lineEdit().installEventFilter(self)
        self.setView(QListView())
        
        delegate = QStyledItemDelegate()
        self.setItemDelegate(delegate)
        self.refresh_callback = None 

    def wheelEvent(self, event):
        # 이벤트를 ignore() 하면 콤보박스 값이 바뀌는 대신, 
        # 부모 위젯인 테이블이 시원하게 스크롤됩니다.
        event.ignore()

    def set_refresh_callback(self, func):
        self.refresh_callback = func

    def eventFilter(self, obj, event):
        if obj == self.lineEdit():
            import sys
            is_mac = sys.platform == "darwin"
            
            if is_mac:
                # Mac: Press 시 팝업을 열면 곧이은 Release 이벤트를 팝업창이 흡수해 즉시 닫히는 현상 발생
                # 따라서 Press 이벤트를 먹어치우고(소비), 실제 팝업 오픈은 Release에서 처리
                if event.type() == QEvent.MouseButtonPress:
                    return True
                elif event.type() == QEvent.MouseButtonRelease:
                    self._toggle_popup()
                    return True
            else:
                # Windows 등: 기존처럼 Press에서 바로 열어도 무방함
                if event.type() == QEvent.MouseButtonPress:
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

class PopupItemDelegate(QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = super().sizeHint(option, index)
        size.setHeight(36)
        return size

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
            if not handle: return
            
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
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5) 
        layout.setSpacing(10) 
        WIDGET_HEIGHT = 45 

        BASIC_BOX_STYLE = """
            border: 1px solid #d1d5db; border-radius: 6px; background-color: white; 
            padding-left: 10px; font-family: 'Pretendard', sans-serif; font-size: 14px; color: #333333;
        """
        FOCUS_STYLE = "border: 1px solid #ff4b4b;"
        FULL_COMBO_STYLE = f"""
            QComboBox {{ {BASIC_BOX_STYLE} }}
            QComboBox:focus {{ {FOCUS_STYLE} }}
            QComboBox::drop-down {{ border: none; width: 30px; background: transparent; }}
            QComboBox QAbstractItemView {{ font-family: 'Pretendard'; background-color: white; border: 1px solid #d1d5db; selection-background-color: #ffecec; selection-color: #ff4b4b; outline: none; padding: 4px; }}
            QComboBox QAbstractItemView::item {{ min-height: 35px; padding: 5px; margin: 2px 0px; }}
        """

        self.lbl_drag = DragHandle(self)
        layout.addWidget(self.lbl_drag)

        self.input_name = QLineEdit(name)
        self.input_name.setPlaceholderText("이름")
        self.input_name.setFixedHeight(WIDGET_HEIGHT)
        self.input_name.setStyleSheet(f"QLineEdit {{ {BASIC_BOX_STYLE} }} QLineEdit:focus {{ {FOCUS_STYLE} }}")
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

        self.btn_delete = QPushButton("삭제")
        self.btn_delete.setFixedSize(60, WIDGET_HEIGHT)
        self.btn_delete.setCursor(Qt.PointingHandCursor)
        self.btn_delete.setStyleSheet("QPushButton { border: none; background-color: #ff4b4b; color: white; border-radius: 6px; font-weight: bold; font-size: 13px; font-family: 'Pretendard', sans-serif; } QPushButton:hover { background-color: #e03e3e; }")
        self.btn_delete.clicked.connect(lambda: self.delete_signal.emit(self))
        layout.addWidget(self.btn_delete)

    def get_data(self):
        return { "Character": self.input_name.text(), "Role": self.combo_role.currentText(), "Age": self.combo_age.currentText(), "Gender": self.combo_gender.currentText() }

class ExcelTextDelegate(QStyledItemDelegate):
    # 1. 편집기(QLineEdit)를 만드는 함수입니다.
    def createEditor(self, parent, option, index):
        editor = QLineEdit(parent)
        # 주황색 테두리와 글자 중앙 정렬 스타일을 입힙니다.
        editor.setStyleSheet("""
            QLineEdit { 
                border: 2px solid #FF5722; 
                padding: 0px; 
                background-color: white;
                font-family: 'Pretendard';
                font-size: 15px;
            }
        """)
        # 글자가 위아래 중앙에 오도록 정렬합니다.
        editor.setAlignment(Qt.AlignVCenter) 
        return editor

    # 2. [핵심] 입력창의 크기를 셀 전체(60px)에 맞게 꽉 채우는 함수입니다.
    # 이 함수는 createEditor 바깥에(같은 높이에) 있어야 합니다!
    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    # 3. 셀에 있던 글자를 편집기에 넣어주는 함수입니다.
    def setEditorData(self, editor, index):
        value = index.data(Qt.EditRole)
        if value:
            editor.setText(str(value))

    # 4. 수정한 글자를 다시 셀에 저장하는 함수입니다.
    def setModelData(self, editor, model, index):
        model.setData(index, editor.text(), Qt.EditRole)

    def setEditorData(self, editor, index):
        # 셀의 데이터를 가져와서 에디터에 넣습니다.
        text = index.model().data(index, Qt.EditRole) or ""
        editor.setText(str(text))
        
        # [수정] end(False)를 사용하여 선택 없이 커서만 맨 뒤로 보냅니다.
        # 타이머를 써야 기본 전체 선택 동작을 확실히 덮어쓸 수 있습니다.
        QTimer.singleShot(0, lambda: editor.end(False))

    def setModelData(self, editor, model, index):
        # [에러 해결] QLineEdit은 toPlainText()가 아니라 text()를 사용합니다.
        model.setData(index, editor.text(), Qt.EditRole)

# =================================================================
# [수정됨] 엑셀형 테이블 위젯 (패딩 제거 및 정렬 수정)
# =================================================================
class SpreadsheetTable(QTableWidget):
    def __init__(self, rows=0, columns=0, parent=None):
        super().__init__(rows, columns, parent)
        
        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        # widgets.py 내 SpreadsheetTable 클래스 안에서
        self.verticalHeader().setMinimumSectionSize(47) # 최소 높이를 50으로 확보
        self.verticalHeader().setDefaultSectionSize(47) # 기본 높이도 50으로 설정
        self.verticalHeader().setSectionResizeMode(QHeaderView.Interactive) # 사용자가 조절 가능하게
                
        # [수정] padding을 0px로 설정하여 위젯이 꽉 차게 만듦
        self.setStyleSheet("""
            QTableWidget {
                gridline-color: #e0e0e0;
                background-color: white;
                selection-background-color: #e8f0fe;
                selection-color: black;
                font-size: 13px;
                outline: none;
            }
            /* 텍스트 아이템 패딩 조절 */
            QTableWidget::item { padding-left: 5px; padding-right: 5px; } 
            QTableWidget::item:focus { border: 2px solid #1a73e8; }
        """)

    def keyPressEvent(self, event):
        if event.matches(QKeySequence.Copy):
            self.copy_selection()
            return
        if event.matches(QKeySequence.Paste):
            self.paste_selection()
            return
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            current_row = self.currentRow()
            current_col = self.currentColumn()
            if current_row < self.rowCount() - 1:
                self.setCurrentCell(current_row + 1, current_col)
            else:
                self.clearSelection()
            return
        if event.key() == Qt.Key_Delete:
            for item in self.selectedItems():
                item.setText("")
            return
        super().keyPressEvent(event)

    def copy_selection(self):
        selection = self.selectedRanges()
        if not selection: return
        r_range = selection[0]
        top_row, bottom_row = r_range.topRow(), r_range.bottomRow()
        left_col, right_col = r_range.leftColumn(), r_range.rightColumn()
        copied_text = ""
        for r in range(top_row, bottom_row + 1):
            row_data = []
            for c in range(left_col, right_col + 1):
                item = self.item(r, c)
                row_data.append(item.text() if item else "")
            copied_text += "\t".join(row_data) + "\n"
        QApplication.clipboard().setText(copied_text)

    def paste_selection(self):
        text = QApplication.clipboard().text()
        if not text: return
        rows = text.split('\n')
        if rows and not rows[-1]: rows.pop()
        start_row, start_col = self.currentRow(), self.currentColumn()
        if start_row < 0 or start_col < 0: return
        needed_rows = start_row + len(rows)
        if needed_rows > self.rowCount(): self.setRowCount(needed_rows)
        for i, row_text in enumerate(rows):
            cols = row_text.split('\t')
            for j, col_text in enumerate(cols):
                r, c = start_row + i, start_col + j
                if c < self.columnCount():
                    self.setItem(r, c, QTableWidgetItem(col_text.strip()))

    # widgets.py 맨 아래에 추가하세요
import difflib
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, QLabel, QPushButton, QMessageBox, QFrame, QWidget
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QTextCharFormat, QTextCursor, QColor, QFont, QTextFormat

# [NEW] 선택적 취소를 위한 플로팅 버튼
class FloatingUndoButton(QPushButton):
    revert_requested = Signal(int) # index 전달

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

class SpellCheckDialog(QDialog):
    def __init__(self, original, corrected, parent=None, initial_vscroll=0):
        super().__init__(parent)
        self.initial_vscroll = initial_vscroll
        self.setWindowTitle("맞춤법 검사 결과 비교")
        self.resize(1000, 700)
        self.result_text = None
        self.diff_data = [] # {tag, org, new, id}
        
        layout = QVBoxLayout(self)
        
        # 안내 문구
        info_label = QLabel("💡 수정된 부분에 커서를 두면 '원래대로' 되돌릴 수 있는 버튼이 나타납니다.")
        info_label.setStyleSheet("color: #2563EB; margin-bottom: 10px; font-weight: bold;")
        layout.addWidget(info_label)

        # 비교 에디터 영역
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

        # 1. 원본 에디터 (왼쪽)
        self.edit_org = QTextEdit()
        self.edit_org.setReadOnly(True)
        self.edit_org.setPlaceholderText("원본 텍스트")
        self.edit_org.setStyleSheet(f"QTextEdit {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; }} {scrollbar_style}")
        self.edit_org.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 2. 교정본 에디터 (오른쪽 - 핵심 위젯)
        self.edit_new = QTextEdit()
        self.edit_new.setPlaceholderText("교정된 텍스트")
        self.edit_new.setStyleSheet(f"QTextEdit {{ border: 1px solid #E2E8F0; border-radius: 8px; background-color: white; padding: 5px; }} {scrollbar_style}")
        self.edit_new.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        editor_layout.addWidget(self.edit_org)
        editor_layout.addWidget(self.edit_new)
        layout.addLayout(editor_layout)

        # [핵심] 플로팅 버튼 초기화 (viewport 위에 배치)
        self.undo_btn = FloatingUndoButton(self.edit_new.viewport())
        self.undo_btn.revert_requested.connect(self.revert_segment)
        self.edit_new.cursorPositionChanged.connect(self.check_cursor_context)

        # [추가] 스크롤 동기화
        self.edit_org.verticalScrollBar().valueChanged.connect(self.edit_new.verticalScrollBar().setValue)
        self.edit_new.verticalScrollBar().valueChanged.connect(self.edit_org.verticalScrollBar().setValue)
        self.edit_org.horizontalScrollBar().valueChanged.connect(self.edit_new.horizontalScrollBar().setValue)
        self.edit_new.horizontalScrollBar().valueChanged.connect(self.edit_org.horizontalScrollBar().setValue)

        # 3. Diff 분석 및 표시
        self.show_diff(original, corrected)

        # 버튼 영역
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
        self.diff_data = []
        d = difflib.SequenceMatcher(None, text1, text2)
        
        # 신호 차단하여 이벤트 루프 간섭 방지
        self.edit_org.blockSignals(True)
        self.edit_new.blockSignals(True)
        
        self.edit_org.clear()
        self.edit_new.clear()
        
        cursor_org = self.edit_org.textCursor()
        cursor_new = self.edit_new.textCursor()
        
        current_idx = 0
        for tag, i1, i2, j1, j2 in d.get_opcodes():
            org_full = text1[i1:i2]
            new_full = text2[j1:j2]

            # [기능 개선] 띄어쓰기와 글자 교정을 완벽히 분리하기 위한 정밀 분할 로직
            def get_granular_segments(org, new, tag_type):
                if tag_type == 'equal':
                    return [('equal', org, new)]
                
                # 1. 공통 접두사/접미사 추출하여 equal로 분리
                pre_i = 0
                while pre_i < len(org) and pre_i < len(new) and org[pre_i] == new[pre_i]:
                    pre_i += 1
                prefix = org[:pre_i]
                
                suf_i = 0
                while suf_i < len(org)-pre_i and suf_i < len(new)-pre_i and org[-1-suf_i] == new[-1-suf_i]:
                    suf_i += 1
                suffix = org[len(org)-suf_i:] if suf_i > 0 else ""
                
                mid_org = org[pre_i:len(org)-suf_i] if suf_i > 0 else org[pre_i:]
                mid_new = new[pre_i:len(new)-suf_i] if suf_i > 0 else new[pre_i:]
                
                res = []
                if prefix: res.append(('equal', prefix, prefix))
                
                # 2. 중간 부분(실제 차이점)을 공백과 글자 단위로 강제 분리
                if not mid_org and not mid_new:
                    pass
                elif not mid_org:
                    for p in re.findall(r' +|[^ ]+', mid_new):
                        res.append(('insert', '', p))
                elif not mid_new:
                    for p in re.findall(r' +|[^ ]+', mid_org):
                        res.append(('delete', p, ''))
                else:
                    # 교체(replace) 구역: 공백과 글자 덩어리를 분리하여 각각 매칭
                    org_parts = re.findall(r' +|[^ ]+', mid_org)
                    new_parts = re.findall(r' +|[^ ]+', mid_new)
                    
                    o_idx = 0
                    for n_p in new_parts:
                        if n_p.strip() == "": # 공백 덩어리인 경우
                            # 공백은 별도의 삽입/삭제 또는 교체로 처리
                            if o_idx < len(org_parts) and org_parts[o_idx].strip() == "":
                                res.append(('replace', org_parts[o_idx], n_p))
                                o_idx += 1
                            else:
                                res.append(('insert', '', n_p))
                        else: # 글자 덩어리인 경우
                            # 앞선 공백들을 먼저 처리(삭제)
                            while o_idx < len(org_parts) and org_parts[o_idx].strip() == "":
                                res.append(('delete', org_parts[o_idx], ''))
                                o_idx += 1
                            
                            if o_idx < len(org_parts):
                                res.append(('replace', org_parts[o_idx], n_p))
                                o_idx += 1
                            else:
                                res.append(('insert', '', n_p))
                    # 남은 원본 덩어리 삭제 처리
                    while o_idx < len(org_parts):
                        res.append(('delete', org_parts[o_idx], ''))
                
                if suffix: res.append(('equal', suffix, suffix))
                return res

            segments = get_granular_segments(org_full, new_full, tag)

            for s_tag, s_org, s_new in segments:
                if s_tag == 'equal':
                    cursor_org.insertText(s_org, QTextCharFormat())
                    cursor_new.insertText(s_new, QTextCharFormat())
                    continue

                # 개별 세그먼트에 대한 메타데이터 저장 (독립적인 ID 부여)
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
                    
                elif s_tag == 'insert':
                    fmt_new.setBackground(QColor("#FFB74D"))
                    fmt_new.setForeground(QColor("#000000"))
                    fmt_new.setFontWeight(QFont.Bold)
                    fmt_new.setProperty(QTextFormat.UserProperty + 1, current_idx)
                    cursor_new.insertText(s_new.replace(' ', '✓'), fmt_new)
                
                current_idx += 1

        self.edit_org.blockSignals(False)
        self.edit_new.blockSignals(False)

        # [추가] 처음 실행 시 맨 위로 스크롤 고정 (또는 이전 위치 복구)
        if self.initial_vscroll > 0:
            self.edit_org.verticalScrollBar().setValue(self.initial_vscroll)
            self.edit_new.verticalScrollBar().setValue(self.initial_vscroll)
        else:
            self.edit_org.verticalScrollBar().setValue(0)
            self.edit_new.verticalScrollBar().setValue(0)
            
            # 커서 위치도 맨 앞으로 이동
            c1 = self.edit_org.textCursor()
            c1.movePosition(QTextCursor.Start)
            self.edit_org.setTextCursor(c1)

            c2 = self.edit_new.textCursor()
            c2.movePosition(QTextCursor.Start)
            self.edit_new.setTextCursor(c2)

    def resizeEvent(self, event):
        # 리사이즈 시 현재 스크롤의 상대적 위치(비율) 계산
        vbar = self.edit_new.verticalScrollBar()
        old_max = vbar.maximum()
        old_val = vbar.value()
        ratio = old_val / old_max if old_max > 0 else 0
        
        super().resizeEvent(event)
        
        # 레이아웃 재계산 시간을 벌기 위해 아주 짧은 지연 후 위치 복구
        QTimer.singleShot(10, lambda: vbar.setValue(int(vbar.maximum() * ratio)))


    def check_cursor_context(self):
        cursor = self.edit_new.textCursor()
        pos = cursor.position()
        doc = self.edit_new.document()
        diff_id = None

        block = doc.begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                if hasattr(it, "fragment"):
                    fragment = it.fragment()
                    if fragment.isValid():
                        if fragment.position() <= pos <= fragment.position() + fragment.length():
                            val = fragment.charFormat().property(QTextFormat.UserProperty + 1)
                            if val is not None:
                                diff_id = val
                it += 1
            block = block.next()

        if diff_id is not None and isinstance(diff_id, int):
            rect = self.edit_new.cursorRect(cursor)
            btn_pos = rect.topLeft()
            
            # 버튼을 커서 위에 배치하되, 뷰포트 상단을 벗어나면 아래에 배치
            target_y = btn_pos.y() - self.undo_btn.height() - 5
            if target_y < 0:
                # 첫 줄이거나 상단 공간이 부족하면 텍스트 아래쪽에 배치
                target_y = rect.bottom() + 5
            
            btn_pos.setY(target_y)
            btn_pos.setX(max(5, btn_pos.x() - 20)) # X도 0보다 크게 보장 (여백 5px)
            
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
        # HTML 태그가 섞일 수 있으므로 toPlainText()로 순수 텍스트만 가져옴
        text = self.edit_new.toPlainText()
        # 시각적 피드백을 위해 넣은 체크 표시를 다시 띄어쓰기로 복구
        self.result_text = text.replace("✓", " ")
        self.accept()

import os
import shutil
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                             QListWidget, QPushButton, QMessageBox, QInputDialog)
from PySide6.QtCore import Qt
# config.py에서 PROJECTS_DIR를 가져온다고 가정합니다.
# from config import PROJECTS_DIR 

# widgets.py에 추가
# [widgets.py] HoverIconButton 클래스 수정
class HoverIconButton(QPushButton):
    def __init__(self, text, icon_path, normal_color="#333333", hover_color="#FF4B4B", parent=None):
        super().__init__(text, parent)
        self.icon_path = icon_path
        self.normal_icon = get_colored_icon(icon_path, normal_color)
        self.hover_icon = get_colored_icon(icon_path, hover_color)
        
        self.setIcon(self.normal_icon)
        self.setCursor(Qt.PointingHandCursor)

    def enterEvent(self, event):
        # [수정] setStyleSheet를 지우고 아이콘만 바꿉니다.
        self.setIcon(self.hover_icon)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # [수정] setStyleSheet를 지우고 아이콘만 바꿉니다.
        self.setIcon(self.normal_icon)
        super().leaveEvent(event)

class ProjectManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작품 및 회차 관리")
        self.setFixedSize(700, 700)
        
        # 1. UI를 먼저 생성 (self.list_titles 등이 여기서 만들어짐)
        self.init_ui()
        # 2. UI 생성 후 데이터를 채움
        self.refresh_projects()

    def init_ui(self):
        # 메인 레이아웃
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 15, 20, 20)
        layout.setSpacing(15)

        # --- [왼쪽: 작품(Title) 관리] ---
        left_layout = QVBoxLayout()
        # [수정] "📚 작품 목록" 라벨을 아이콘+텍스트 컨테이너로 교체
        title_list_header = QWidget()
        title_list_layout = QHBoxLayout(title_list_header)
        title_list_layout.setContentsMargins(0, 5, 0, 5) # 상하 여백 살짝 조절
        title_list_layout.setSpacing(4)

        # 1. 아이콘 라벨 (상수: ICON_LIBRARY)
        icon_lib = QLabel()
        icon_lib.setPixmap(get_icon(config.ICON_LIBRARY).pixmap(20, 20))

        # 2. 텍스트 라벨 (이모지 제거)
        lbl_lib_text = QLabel("작품 목록")
        lbl_lib_text.setStyleSheet("font-weight: bold; color: #333;")

        title_list_layout.addWidget(icon_lib)
        title_list_layout.addWidget(lbl_lib_text)
        title_list_layout.addStretch()

        left_layout.addWidget(title_list_header)
        
        # --- [왼쪽: 작품 목록 스타일 수정] ---
        self.list_titles = QListWidget()
        self.list_titles.setStyleSheet("""
            QListWidget {
                font-family: 'Pretendard'; /* [핵심] 폰트 지정 */
                font-size: 14px;
                color: #333;
                outline: none;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                height: 30px; /* 항목 높이 확보 */
                padding-left: 8px;
                border-bottom: 1px solid #F3F4F6;
                border-radius: 4px;
                margin-bottom: 1px;
            }
            QListWidget::item:hover {
                background-color: #F9FAFB;
            }
            QListWidget::item:selected {
                background-color: #FFECEC; /* 진우님 포인트 컬러 연한 배경 */
                color: #FF4B4B;           /* 진우님 포인트 컬러 글자 */
                font-weight: bold;
            }
        """)
        self.list_titles.currentTextChanged.connect(self.load_episodes)
        left_layout.addWidget(self.list_titles)

        btn_row_title = QHBoxLayout()
        self.btn_add_title = QPushButton("작품 추가")
        self.btn_del_title = QPushButton("작품 삭제")
        self.btn_del_title.setStyleSheet("color: #ff4b4b; font-weight: bold;")
        
        self.btn_add_title.clicked.connect(self.add_title)
        self.btn_del_title.clicked.connect(self.delete_title)
        
        btn_row_title.addWidget(self.btn_add_title)
        btn_row_title.addWidget(self.btn_del_title)
        left_layout.addLayout(btn_row_title)
        
        layout.addLayout(left_layout, 1)

        # --- [오른쪽: 회차(Episode) 관리] ---
        right_layout = QVBoxLayout()
        # 1. 아이콘 헤더 영역 (🎬 이모지 대신 SVG 아이콘)
        epi_list_header = QWidget()
        epi_list_layout = QHBoxLayout(epi_list_header)
        epi_list_layout.setContentsMargins(0, 5, 0, 5)
        epi_list_layout.setSpacing(6)

        # 아이콘 (상수: ICON_MOVIE)
        icon_epi = QLabel()
        icon_epi.setPixmap(get_icon(config.ICON_MOVIE).pixmap(20, 20))

        # 텍스트 라벨
        lbl_epi_text = QLabel("회차 및 생성 현황")
        lbl_epi_text.setStyleSheet("font-weight: bold; color: #333;")

        epi_list_layout.addWidget(icon_epi)
        epi_list_layout.addWidget(lbl_epi_text)
        epi_list_layout.addStretch()

        right_layout.addWidget(epi_list_header)
        
        # --- [오른쪽: 회차 목록 스타일 수정] ---
        self.list_episodes = QListWidget()
        self.list_episodes.setStyleSheet("""
            QListWidget {
                font-family: 'Pretendard'; /* [핵심] 폰트 지정 */
                font-size: 14px;
                color: #333;
                outline: none;
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                height: 34px;
                padding-left: 8px;
                border-bottom: 1px solid #F3F4F6;
                border-radius: 4px;
                margin-bottom: 1px;
            }
            QListWidget::item:selected {
                background-color: #E1F5FE;
                color: #0288D1;
                font-weight: bold;
            }
        """)
        right_layout.addWidget(self.list_episodes)

        btn_row_epi = QHBoxLayout()
        self.btn_add_epi = QPushButton("회차 추가")
        self.btn_del_epi = QPushButton("회차 삭제")
        self.btn_del_epi.setStyleSheet("color: #ff4b4b;")
        
        self.btn_add_epi.clicked.connect(self.add_episode)
        self.btn_del_epi.clicked.connect(self.delete_episode)
        
        btn_row_epi.addWidget(self.btn_add_epi)
        btn_row_epi.addWidget(self.btn_del_epi)
        right_layout.addLayout(btn_row_epi)

        layout.addLayout(right_layout, 2)

    # --- [비즈니스 로직] ---

    def refresh_projects(self):
        """프로젝트 폴더를 스캔하여 좌측 리스트를 갱신"""
        self.list_titles.clear()
        if os.path.exists(PROJECTS_DIR):
            titles = sorted([d for d in os.listdir(PROJECTS_DIR) 
                           if os.path.isdir(os.path.join(PROJECTS_DIR, d))])
            self.list_titles.addItems(titles)

    def load_episodes(self, title):
        """선택한 작품의 회차 목록을 우측 리스트에 표시"""
        self.list_episodes.clear()
        if not title: return
        
        t_path = os.path.join(PROJECTS_DIR, title)
        if os.path.exists(t_path):
            episodes = sorted([d for d in os.listdir(t_path) 
                             if os.path.isdir(os.path.join(t_path, d))])
            
            for epi in episodes:
                img_path = os.path.join(t_path, epi, "images")
                # '준비됨' 대신 더 직관적인 상태 표시
                status = "✅ 생성완료" if os.path.exists(img_path) and os.listdir(img_path) else "⏳ 대기중"
                self.list_episodes.addItem(f"{epi}  |  {status}")

    def add_title(self):
        name, ok = QInputDialog.getText(self, "작품 추가", "새로운 작품 이름을 입력하세요:")
        if ok and name.strip():
            path = os.path.join(PROJECTS_DIR, name.strip())
            os.makedirs(path, exist_ok=True)
            self.refresh_projects()

    def delete_title(self):
        """작품 삭제: 폴더 존재 여부를 체크하여 에러 방지"""
        current_item = self.list_titles.currentItem()
        if not current_item:
            return

        title = current_item.text()
        reply = QMessageBox.warning(self, "작품 삭제", 
                                  f"⚠️ '{title}'의 모든 데이터가 영구 삭제됩니다.\n정말로 진행하시겠습니까?",
                                  QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            project_path = os.path.join(PROJECTS_DIR, title)
            
            try:
                # 1. 실제 폴더가 존재하는지 먼저 확인!
                if os.path.exists(project_path):
                    shutil.rmtree(project_path)
                    print(f"물리적 삭제 완료: {project_path}")
                else:
                    # 폴더가 없으면 메시지만 출력하고 넘어감
                    print(f"이미 삭제된 폴더입니다: {project_path}")

                # 2. 어떤 경우든 UI 리스트는 최신화 (유령 항목 제거)
                self.refresh_projects()
                self.list_episodes.clear()
                
            except Exception as e:
                QMessageBox.critical(self, "삭제 오류", f"삭제 중 예상치 못한 오류 발생:\n{e}")

    def add_episode(self):
        title_item = self.list_titles.currentItem()
        if not title_item: return
        
        title = title_item.text()
        name, ok = QInputDialog.getText(self, "회차 추가", f"[{title}]의 새로운 회차 이름:")
        if ok and name.strip():
            path = os.path.join(PROJECTS_DIR, title, name.strip(), "images")
            os.makedirs(path, exist_ok=True)
            self.load_episodes(title)

    def delete_episode(self):
        """회차 삭제 로직: 폴더 존재 여부를 체크하여 유령 항목 에러 방지"""
        title_item = self.list_titles.currentItem()
        epi_item = self.list_episodes.currentItem()
        
        if title_item and epi_item:
            title = title_item.text()
            # "55화 | ✅ 생성완료" 형태에서 회차명(55화)만 추출
            epi = epi_item.text().split('|')[0].strip()
            
            reply = QMessageBox.warning(self, "회차 삭제", 
                                      f"'{epi}' 회차의 모든 데이터를 삭제하시겠습니까?",
                                      QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                # 삭제할 회차의 전체 경로 생성
                epi_path = os.path.join(PROJECTS_DIR, title, epi)
                
                try:
                    # 1. [핵심] 폴더가 실제로 하드디스크에 존재하는지 확인
                    if os.path.exists(epi_path):
                        shutil.rmtree(epi_path)
                        print(f"회차 삭제 완료: {epi_path}")
                    else:
                        # 폴더가 없더라도 당황하지 않고 리스트에서만 지우도록 유도
                        print(f"이미 삭제된 경로입니다: {epi_path}")

                    # 2. 어떤 경우든 UI 리스트를 새로고침하여 '유령 항목' 제거
                    self.load_episodes(title)
                    
                except Exception as e:
                    # 권한 문제나 파일 사용 중일 때를 대비한 알림
                    QMessageBox.critical(self, "삭제 오류", f"회차 삭제 중 오류가 발생했습니다:\n{e}")


# [main.py] FileDropListWidget 클래스 (수정)

class FileDropListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)
        
        # 우클릭 메뉴 설정
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.show_context_menu)
        
        # 1. 평상시 스타일
        self.normal_style = """
            QListWidget { 
                border: 1px solid #d1d5db; 
                background: white; 
                border-radius: 4px; 
                padding: 5px; 
                color: #333; 
            }
        """

        # 2. [수정] 드래그 시 활성화되는 오렌지 스타일
        self.active_style = """
            QListWidget { 
                border: 2px dashed #FB923C; /* 오렌지색 점선 */
                background: #FFF7ED;        /* 아주 연한 오렌지색 배경 */
                border-radius: 6px; 
            }
        """
        self.setStyleSheet(self.normal_style)

        # 3. [수정] 중앙 오버레이 라벨 색상 변경
        self.overlay_label = QLabel("📂 여기에 파일을 놓으세요", self)
        self.overlay_label.setAlignment(Qt.AlignCenter)
        # 파란색(#3B82F6)을 오렌지색(#FB923C)으로 바꿨습니다.
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
            # 1. 경로 획득 및 정규화
            _, i_path, _ = mw.get_paths()
            abs_i_path = os.path.abspath(i_path)
        except Exception as e:
            print(f"경로 획득 실패: {e}")
            return

        deleted_count = 0
        for item in selected_items:
            # 2. 파일명 추출 (더 강력한 필터링)
            display_text = item.text()
            
            # 이모지뿐만 아니라 앞뒤 모든 공백을 제거합니다.
            # 만약 "📄 1화_001.jpg" 라면 "1화_001.jpg"만 남깁니다.
            file_name = display_text.replace("📄", "").strip()
            
            # 맥 전용: 한글 자모 분리 현상(NFD) 해결
            file_name = unicodedata.normalize('NFC', file_name)
            
            full_path = os.path.join(abs_i_path, file_name)

            # [디버그용] 실제 어떤 경로를 찾는지 터미널에 출력합니다.
            print(f"DEBUG: 삭제 시도 경로 -> {full_path}")

            if os.path.exists(full_path):
                try:
                    os.remove(full_path)
                    deleted_count += 1
                    self.takeItem(self.row(item)) # 실물 삭제 성공 시에만 리스트에서 제거
                except Exception as e:
                    print(f"삭제 실패 ({file_name}): {e}")
            else:
                # 파일이 없다고 뜰 때의 정밀 진단
                print(f"❌ 파일을 찾을 수 없습니다: {file_name}")
                print(f"   ㄴ 상위 폴더 존재 여부: {os.path.exists(abs_i_path)}")
        
        # 중앙 뷰어 및 데이터 새로고침
        if hasattr(mw, 'load_images'):
            mw.load_images()
        if hasattr(mw, 'load_data'):
            mw.load_data()
            
        if hasattr(mw, 'toast'):
            mw.toast.show_message(f"✨ {deleted_count}개의 파일 삭제 완료")

    # [수정] 윈도우 표준에 맞춰 Backspace 삭제 기능 제거
    def keyPressEvent(self, event):
        # 오직 Delete 키로만 삭제 가능하게 변경
        if event.key() == Qt.Key_Delete:
            self.delete_selected_items()
        else:
            super().keyPressEvent(event)

    # [수정] 우클릭 메뉴 문구 간소화
    def show_context_menu(self, pos):
        menu = QMenu(self)
        
        # [수정] QAction 생성 시 아이콘(ICON_DELETE)을 추가합니다.
        delete_action = QAction(get_icon(config.ICON_DELETE), "선택한 파일 지우기", self)
        
        delete_action.triggered.connect(self.delete_selected_items)
        menu.addAction(delete_action)
        menu.exec(self.mapToGlobal(pos))

    # --- 드래그앤드롭 이벤트 (기존 유지) ---
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            # [수정] 메인 윈도우의 오버레이도 함께 띄워줌
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

        # 3. [새로 추가] 사이드바 토글 버튼 위치 고정하기
        # 사이드바가 접히거나 펴질 때 버튼이 우측 상단에 딱 붙어 있게 합니다.
        if hasattr(self, 'btn_toggle') and hasattr(self, 'sidebar'):
            margin_right = 10 # 우측 여백
            margin_top = 10   # 상단 여백 (아까 정한 25px)
            
            # 버튼의 새로운 X 좌표 = 사이드바 현재 너비 - 버튼 너비 - 오른쪽 마진
            new_x = self.sidebar.width() - self.btn_toggle.width() - margin_right

            if new_x < 0: new_x = 10

            self.btn_toggle.move(new_x, margin_top)
            
            # 버튼을 항상 맨 위로 올리기 (다른 위젯에 가려지지 않게)
            self.btn_toggle.raise_()



# [main.py] 기존 DropOverlay 클래스 자리에 덮어쓰기

class DropOverlay(QWidget):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAcceptDrops(True)
        # [수정] 배경 투명도 처리를 위해 속성 변경
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.hide()
        self.snapshot = None 

    def set_snapshot(self, pixmap):
        self.snapshot = pixmap
        self.update()

    def paintEvent(self, event):
        # print(f"DEBUG: DropOverlay paintEvent called - size: {self.size()}")
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.snapshot:
            painter.drawPixmap(0, 0, self.snapshot)

        # 1. 배경 틴트 (오렌지색 투명도 100)
        tint_color = QColor(251, 146, 60, 100) 
        painter.fillRect(self.rect(), tint_color)

        # 2. 테두리 (진한 오렌지색 점선)
        pen = QPen(QColor("#FB923C")) 
        pen.setWidth(4)  # 선 굵기 4px
        # [수정] 아주 촘촘한 대시 간격 조절 (선 3, 간격 2)
        pen.setDashPattern([3, 2])
        painter.setPen(pen)
        painter.setBrush(Qt.NoBrush)
        
        # 보더 래디우스 작게 (30 -> 12)
        rect_for_border = self.rect().adjusted(15, 15, -15, -15)
        painter.drawRoundedRect(rect_for_border, 12, 12)

        # 3. 안내 아이콘 (제공된 SVG)
        svg_code = """
        <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="#1E293B" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M10.3 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v10l-3.1-3.1a2 2 0 0 0-2.814.014L6 21"/>
            <path d="m14 19.5 3-3 3 3"/>
            <path d="M17 22v-5.5"/>
            <circle cx="9" cy="9" r="2"/>
        </svg>
        """
        renderer = QSvgRenderer(QByteArray(svg_code.encode('utf-8')))
        icon_size = 80
        icon_rect = QRect(
            (self.width() - icon_size) // 2,
            (self.height() - icon_size) // 2 - 40, # 중앙보다 약간 위
            icon_size,
            icon_size
        )
        renderer.render(painter, icon_rect)

        # 4. 안내 텍스트 (아이콘 아래에 배치)
        painter.setPen(QColor("#1E293B")) 
        font = QFont("Pretendard", 32, QFont.Bold)
        painter.setFont(font)
        
        text_rect = self.rect().adjusted(0, icon_size // 2 + 20, 0, 0)
        painter.drawText(text_rect, Qt.AlignCenter, "파일을 여기에 드롭하세요")

    def dragEnterEvent(self, event):
        print("DEBUG: DropOverlay dragEnterEvent")
        event.acceptProposedAction()

    def dragMoveEvent(self, event):
        event.acceptProposedAction()

    def dragLeaveEvent(self, event):
        self.hide()

    def dropEvent(self, event):
        self.hide()
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            urls = event.mimeData().urls()
            files = [u.toLocalFile() for u in urls]
            
            # 부모(WebtoonManager)의 파일 처리 함수 호출
            mw = self.window()
            if hasattr(mw, 'process_image_files'):
                mw.process_image_files(files)
        else:
            event.ignore()

# [main.py] SmartTextEdit 클래스 (최종_진짜_마지막.ver)
class SmartTextEdit(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)

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

    # [핵심] 에디터에 무언가가 '입력'되려는 순간을 가로챕니다.
    def insertFromMimeData(self, source):
        if source.hasUrls():
            # 1. 파일 경로가 들어오면? -> 입력하지 말고 이미지 처리로 넘겨버림!
            mw = self.window()
            if hasattr(mw, 'process_image_files'):
                urls = source.urls()
                files = [u.toLocalFile() for u in urls]
                image_files = [f for f in files if f.lower().endswith(('.png', '.jpg', '.jpeg', '.webp'))]
                if image_files:
                    mw.process_image_files(image_files)
            # 2. super()... 를 호출하지 않음으로써 텍스트 에디터에는 아무것도 안 써지게 만듦 (차단)
        else:
            # 3. 그냥 텍스트면? -> 정상적으로 입력
            super().insertFromMimeData(source)


# =======================================================
# 토스트 메시지 (애니메이션 충돌 방지 완벽 버전)
# =======================================================
class ToastMessage(QLabel):
    def __init__(self, parent):
        super().__init__(parent)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            QLabel {
                background-color: rgba(40, 44, 52, 230);
                color: white;
                padding: 10px 25px;
                border-radius: 18px;
                font-size: 14px;
                font-weight: bold;
                font-family: 'Pretendard';
            }
        """)
        self.hide()
        
        # 1. 투명도 효과 설정
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # 2. 애니메이션 설정 (opacity_effect를 대상으로 함)
        self.anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim.setEasingCurve(QEasingCurve.InOutSine) 
        
        # 3. 타이머 설정
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.fade_out)

    def show_message(self, text, duration=4000, fade_speed=400):
        """토스트 메시지를 화면에 띄웁니다."""
        self.timer.stop()
        self.anim.stop()
        
        # [안정성] 연결된 시그널을 안전하게 해제하여 중복 실행 에러 방지
        try:
            self.anim.finished.disconnect()
        except (TypeError, RuntimeError):
            pass
            
        self.setText(text)
        self.adjustSize()
        
        # 부모 위젯의 하단 중앙에 배치
        if self.parent():
            parent_rect = self.parent().geometry()
            x = (parent_rect.width() - self.width()) // 2
            y = parent_rect.height() - self.height() - 80
            self.move(x, y)
        
        self.show()
        # 나타나는 애니메이션 (0.0 -> 1.0)
        self.opacity_effect.setOpacity(0.0) 
        self.anim.setDuration(fade_speed)
        self.anim.setStartValue(0.0)
        self.anim.setEndValue(1.0)
        self.anim.start()
        
        # 4초(duration) 동안 유지 후 fade_out 호출
        self.timer.start(duration)

    def fade_out(self):
        """등장할 때처럼 부드럽게 사라지는 여운 효과입니다."""
        self.anim.stop()
        
        # 사라지는 건 등장(400ms)보다 조금 더 긴 600ms로 설정하여 부드러운 여운을 줍니다.
        self.anim.setDuration(600) 
        self.anim.setStartValue(self.opacity_effect.opacity())
        self.anim.setEndValue(0.0)
        
        # [핵심] 애니메이션이 완전히 끝난 뒤에만 위젯을 숨기도록 연결
        try:
            self.anim.finished.disconnect()
        except (TypeError, RuntimeError):
            pass
            
        self.anim.finished.connect(self.hide)
        self.anim.start()

# =======================================================
# 설정창 (프리셋)
# =======================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 키 프리셋 관리")
        self.setFixedSize(550, 400)
        
        self.local_presets = config.API_PRESETS.copy()
        self.local_active = config.ACTIVE_PRESET_NAME
        
        self.init_ui()
    
    # 전문적인 느낌의 얇은 선(Thin Line) 스타일 아이콘
    SVG_EYE_OPEN = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>"""
    SVG_EYE_CLOSE = b"""<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#666" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path><line x1="1" y1="1" x2="23" y2="23"></line></svg>"""

    def get_svg_icon(self, svg_data):
        """SVG 데이터를 QIcon으로 변환하는 헬퍼 함수"""
        pixmap = QPixmap()
        pixmap.loadFromData(svg_data)
        return QIcon(pixmap)
    
    def toggle_password_visibility(self, line_edit, button):
        if line_edit.echoMode() == QLineEdit.Password:
            line_edit.setEchoMode(QLineEdit.Normal)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_CLOSE)) # 눈 감은 아이콘으로 변경
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN)) # 다시 눈 뜬 아이콘으로

    def init_ui(self):
        layout = QVBoxLayout(self)
        # [수정 1] 메인 여백 최소화 (좌, 상, 우, 하) -> 상단(10)을 더 줄여보세요.
        layout.setContentsMargins(25, 15, 25, 10) 
        # [수정 2] 메인 섹션(프리셋 영역과 키 영역) 사이의 간격을 대폭 줄임
        layout.setSpacing(15) 

        # 1. 프리셋 선택 영역
        preset_group = QVBoxLayout()
        # [핵심 수정] 중첩 레이아웃 자체의 내부 여백과 간격을 0으로 초기화
        preset_group.setContentsMargins(0, 0, 0, 0)
        preset_group.setSpacing(8) # 글자와 입력창 사이 간격 (매우 좁게)
        
        # --- [수정 시작] 프리셋 선택 헤더 (📁 -> ICON_KEY) ---
        preset_header = QWidget()
        preset_header_layout = QHBoxLayout(preset_header)
        # 위쪽 여백(margin-top: 5px)을 컨테이너 마진으로 해결합니다
        preset_header_layout.setContentsMargins(0, 5, 0, 0) 
        # 지난번에 맞춘 '쫀득한' 간격 4px 적용
        preset_header_layout.setSpacing(4) 

        # 1. 아이콘 라벨 (상수: ICON_KEY)
        icon_preset = QLabel()
        icon_preset.setPixmap(get_icon(config.ICON_KEY).pixmap(18, 18))

        # 2. 텍스트 라벨 (이모지 제거)
        lbl_preset = QLabel("프리셋 선택")
        lbl_preset.setStyleSheet("font-size: 15px; font-weight: bold; color: #333;")

        preset_header_layout.addWidget(icon_preset)
        preset_header_layout.addWidget(lbl_preset)
        preset_header_layout.addStretch()

        preset_group.addWidget(preset_header)
        # --- [수정 끝] ---

        row_preset = QHBoxLayout()
        self.combo_presets = QComboBox()
        self.combo_presets.setFixedHeight(36)

        # [핵심 1] 맥의 중앙 팝업 대신 아래로 열리는 리스트 뷰를 강제 적용합니다.
        self.combo_presets.setView(QListView()) 

        # [핵심 2] 스타일시트로 드롭다운 위치를 아래(0)로 고정합니다.
        self.combo_presets.setStyleSheet("""
            QComboBox {
                combobox-popup: 0; /* 0으로 설정해야 아래로 열립니다. */
                border: 1px solid #ccc;
                border-radius: 4px;
                padding-left: 10px;
                background: white;
            }
            /* 드롭다운 목록창 스타일 */
            QComboBox QAbstractItemView {
                border: 1px solid #ddd;
                background-color: white;
                outline: 0;
            }
        """)

        self.combo_presets.addItems(list(self.local_presets.keys()))
        self.combo_presets.setCurrentText(self.local_active)
        self.combo_presets.currentTextChanged.connect(self.on_preset_changed)
        
        btn_add = QPushButton("추가")
        btn_add.setFixedSize(60, 36)
        btn_add.clicked.connect(self.add_preset)
        
        btn_del = QPushButton("삭제")
        btn_del.setFixedSize(60, 36)
        btn_del.clicked.connect(self.delete_preset)
        
        row_preset.addWidget(self.combo_presets)
        row_preset.addWidget(btn_add)
        row_preset.addWidget(btn_del)
        preset_group.addLayout(row_preset)
        
        # [수정 3] 구분선 주변 마진을 0으로 만들어 공간 낭비를 없앱니다.
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #ddd; margin: 0px;") 
        preset_group.addWidget(line)
        
        layout.addLayout(preset_group)

        # 2. 키 입력 영역 (OCR & AI)
        keys_layout = QVBoxLayout()
        
        # [OCR 키]
        lbl_ocr = QLabel("cloud.google.com (OCR용)")
        lbl_ocr.setStyleSheet("font-weight: bold; color: #555;")
        
        # 입력창과 버튼을 가로로 배치하기 위한 레이아웃
        row_ocr_input = QHBoxLayout()
        self.input_ocr = QLineEdit()
        self.input_ocr.setPlaceholderText("Google Cloud Vision API Key")
        self.input_ocr.setEchoMode(QLineEdit.Password)
        self.input_ocr.setFixedHeight(36)
        self.input_ocr.textChanged.connect(self.save_temp_data)
        
        # 버튼 생성 시 스타일과 초기 아이콘 설정
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
        keys_layout.addSpacing(10)

        # [AI 키]
        lbl_ai = QLabel("aistudio.google.com (맞춤법용)")
        lbl_ai.setStyleSheet("font-weight: bold; color: #2ecc71;")
        
        row_ai_input = QHBoxLayout()
        self.input_ai = QLineEdit()
        self.input_ai.setPlaceholderText("Google AI Studio API Key")
        self.input_ai.setEchoMode(QLineEdit.Password)
        self.input_ai.setFixedHeight(36)
        self.input_ai.textChanged.connect(self.save_temp_data)
        
        # SVG 아이콘을 적용한 AI 키 전용 눈 버튼
        self.btn_toggle_ai = QPushButton()
        self.btn_toggle_ai.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN))
        self.btn_toggle_ai.setIconSize(QSize(20, 20))
        self.btn_toggle_ai.setFixedSize(40, 36)
        self.btn_toggle_ai.setCursor(Qt.PointingHandCursor)
        self.btn_toggle_ai.setStyleSheet("""
            QPushButton { border: none; background: transparent; }
            QPushButton:hover { background-color: #f0f0f0; border-radius: 4px; }
        """)
        # OCR 버튼과 동일한 토글 함수를 사용하되, 인자만 AI용으로 넘겨줍니다.
        self.btn_toggle_ai.clicked.connect(lambda: self.toggle_password_visibility(self.input_ai, self.btn_toggle_ai))
        
        row_ai_input.addWidget(self.input_ai)
        row_ai_input.addWidget(self.btn_toggle_ai)
        
        keys_layout.addWidget(lbl_ai)
        keys_layout.addLayout(row_ai_input)
        
        layout.addLayout(keys_layout)

        layout.addStretch()

        # 3. 하단 버튼
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
        data = self.local_presets.get(preset_name, {"ocr": "", "ai": ""})
        self.input_ocr.blockSignals(True)
        self.input_ai.blockSignals(True)
        self.input_ocr.setText(data.get("ocr", ""))
        self.input_ai.setText(data.get("ai", ""))
        self.input_ocr.blockSignals(False)
        self.input_ai.blockSignals(False)

    def save_temp_data(self):
        if self.local_active:
            self.local_presets[self.local_active] = {
                "ocr": self.input_ocr.text().strip(),
                "ai": self.input_ai.text().strip()
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
        reply = QMessageBox.question(self, "삭제 확인", f"'{current}' 프리셋을 삭제하시겠습니까?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            del self.local_presets[current]
            self.combo_presets.removeItem(self.combo_presets.currentIndex())

    def save_final(self):
        config.save_settings(self.local_presets, self.local_active)
        QMessageBox.information(self, "저장 완료", f"'{self.local_active}' 프리셋이 적용되었습니다.")
        self.accept()

# =======================================================
