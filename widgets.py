# widgets.py
from PySide6.QtWidgets import (QLabel, QComboBox, QListView, QStyledItemDelegate, 
                               QScrollArea, QFrame, QHBoxLayout, QLineEdit, 
                               QPushButton, QWidget, QSizePolicy, QTextEdit,
                               QTableWidget, QAbstractItemView, QTableWidgetItem, QApplication, QHeaderView,
                               QGraphicsOpacityEffect, QMenu, QDialog, QVBoxLayout, QMessageBox, QInputDialog,
                               QListWidget, QListWidgetItem, QStackedWidget, QFileDialog, QCheckBox)
from PySide6.QtCore import Qt, QEvent, Signal, QTimer, QSize, QEasingCurve, QPropertyAnimation, QRect, QRectF, QMimeData, QModelIndex
from PySide6.QtGui import (
    QPixmap, QDrag, QPainter, QColor, QPen, QFont, QAction, QIcon,
    QRegion, QBrush, QLinearGradient, QTextCharFormat, QTextFormat,
    QTextCursor, QKeySequence
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtCore import QByteArray
import re
import unicodedata
import os
import platform
from config import ROLE_OPTIONS, AGE_OPTIONS, GENDER_OPTIONS, PROJECTS_DIR
from utils import get_icon, get_colored_icon, open_path
import config
import excel_handler

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

    def wheelEvent(self, event):
        # [추가] 휠 조작으로 값이 바뀌기 전 백 swap
        self._trigger_undo_backup()
        super().wheelEvent(event)

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
        # [핵심] 콤보박스 본체나 내부 입력창 어디서든 Ctrl+Z 감지
        if obj in (self, self.lineEdit()):
            if event.type() == QEvent.KeyPress:
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
                image: url(assets/dropdown-arrow.svg);
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
    def __init__(self, parent=None):
        super().__init__(parent)

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

    # 4. 수정한 글자를 다시 셀에 저장하는 함수입니다.
    def setModelData(self, editor, model, index):
        # [추가] 변경되기 전 상태를 undo 스택에 저장
        table = self.parent()
        if table and hasattr(table, 'save_state_for_undo'):
            table.save_state_for_undo()
            
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
        
        # [추가] 드래그 앤 드롭 설정 (행 이동용)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDragDropOverwriteMode(False)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)

        self.setAlternatingRowColors(True)
        self.setSelectionMode(QAbstractItemView.ContiguousSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.verticalHeader().setMinimumSectionSize(47)
        self.verticalHeader().setDefaultSectionSize(47)
        self.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

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
        
        # [추가] 드래그 인디케이터용 변수
        self.drop_target_row = None
        
        # [추가] 실행취소/다시실행 스택
        self.undo_stack = []
        self.redo_stack = []
        self.is_undoing = False

    def get_table_state(self):
        """현재 테이블의 전체 상태(캐릭터 콤보, 대사)를 리스트로 반환"""
        state = []
        try:
            for r in range(self.rowCount()):
                combo_text = ""
                widget = self.cellWidget(r, 0)
                if isinstance(widget, QComboBox):
                    combo_text = widget.currentText()
                
                item = self.item(r, 1)
                text = item.text() if item else ""
                
                state.append({"combo": combo_text, "text": text})
        except Exception as e:
            print(f"Error in get_table_state: {e}")
        return state

    def restore_table_state(self, state):
        """주어진 상태(state)로 테이블을 복구 (성능 최적화 버전)"""
        # [추가] 편집 중인 에디터가 있다면 안전하게 닫기 (commitData 경고 방지)
        if self.state() == QAbstractItemView.EditingState:
            self.setCurrentIndex(QModelIndex()) 
            
        self.is_undoing = True
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        
        # 행 개수가 다르면 조정
        if self.rowCount() != len(state):
            self.setRowCount(len(state))
        
        mw = self.window()
        char_names = []
        if hasattr(mw, 'get_character_list'):
            char_names = mw.get_character_list()
            
        for r, row_data in enumerate(state):
            # 콤보박스 재사용 또는 생성
            widget = self.cellWidget(r, 0)
            if isinstance(widget, QComboBox):
                if widget.currentText() != row_data["combo"]:
                    widget.setCurrentText(row_data["combo"])
            else:
                if hasattr(mw, 'create_table_combo'):
                    combo = mw.create_table_combo(char_names, row_data["combo"])
                    self.setCellWidget(r, 0, combo)
            
            # 텍스트 재사용 또는 생성
            old_item = self.item(r, 1)
            if old_item:
                if old_item.text() != row_data["text"]:
                    old_item.setText(row_data["text"])
            else:
                self.setItem(r, 1, QTableWidgetItem(row_data["text"]))
            
        self.setUpdatesEnabled(True) # [추가] 화면 갱신 재개
        self.blockSignals(False)
        self.is_undoing = False
        self.setFocus() # [추가] 포커스 강제 확보
        
        if hasattr(mw, 'save_script_data'):
            # 저장 시 resizeRowsToContents가 호출되므로 여기서 따로 호출하지 않음
            mw.save_script_data()

    def save_state_for_undo(self):
        """현재 상태를 undo_stack에 저장"""
        if self.is_undoing:
            return
        state = self.get_table_state()
        
        # [최적화] 마지막 저장 상태와 동일하면 저장하지 않음
        if self.undo_stack and self.undo_stack[-1] == state:
            return
            
        self.undo_stack.append(state)
        self.redo_stack.clear()
        
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return
            
        # 편집 중이라면 현재 내용을 확정
        if self.state() == QAbstractItemView.EditingState:
            self.setCurrentIndex(QModelIndex()) 
            
        current_state = self.get_table_state()
        
        # [지능형 Undo] 현재와 다른 상태가 나올 때까지 스택을 거슬러 올라감
        while self.undo_stack:
            previous_state = self.undo_stack.pop()
            if previous_state != current_state:
                self.redo_stack.append(current_state)
                self.restore_table_state(previous_state)
                return

    def redo(self):
        if not self.redo_stack:
            return
            
        # 편집 중이라면 현재 내용을 확정
        if self.state() == QAbstractItemView.EditingState:
            self.setCurrentIndex(QModelIndex())

        current_state = self.get_table_state()
        
        # [지능형 Redo] 현재와 다른 상태가 나올 때까지 스택을 앞으로 보냄
        while self.redo_stack:
            next_state = self.redo_stack.pop()
            if next_state != current_state:
                self.undo_stack.append(current_state)
                self.restore_table_state(next_state)
                return

    def dragEnterEvent(self, event):
        if event.source() == self:
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.source() == self:
            event.setDropAction(Qt.MoveAction)
            event.accept()
            row = self.rowAt(event.pos().y())
            if row == -1: row = self.rowCount()
            
            if self.drop_target_row != row:
                self.drop_target_row = row
                self.viewport().update()
        else:
            super().dragMoveEvent(event)

    def dragLeaveEvent(self, event):
        self.drop_target_row = None
        self.viewport().update()
        super().dragLeaveEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        # [추가] 드래그 중일 때 삽입될 위치에 파란색 선(인디케이터) 그리기
        if self.drop_target_row is not None:
            painter = QPainter(self.viewport())
            pen = QPen(QColor("#1a73e8"), 3) # 파란색, 두께 3px
            painter.setPen(pen)
            
            if self.drop_target_row < self.rowCount():
                y = self.rowViewportPosition(self.drop_target_row)
            else:
                last_row = self.rowCount() - 1
                y = self.rowViewportPosition(last_row) + self.rowHeight(last_row)
                
            painter.drawLine(0, y, self.viewport().width(), y)

    def dropEvent(self, event):
        """드래그 앤 드롭으로 행 전체를 이동시키는 로직 (커스텀 위젯 대응)"""
        self.drop_target_row = None
        self.viewport().update()

        if event.source() != self or not (event.dropAction() & (Qt.MoveAction | Qt.CopyAction)):
            return

        # [추가] 상태 저장 (드롭 전)
        self.save_state_for_undo()

        # 1. 대상 위치 파악
        target_row = self.rowAt(event.pos().y())
        if target_row == -1: target_row = self.rowCount()
        
        # 2. 선택된 행들 파악
        selected_rows = sorted(list(set(index.row() for index in self.selectedIndexes())), reverse=True)
        if not selected_rows: return
        
        # 3. 데이터 백업 (콤보박스 포함)
        rows_data = []
        for r in sorted(selected_rows):
            row_content = []
            for c in range(self.columnCount()):
                item = self.item(r, c)
                text = item.text() if item else ""
                
                # 0번 컬럼(캐릭터)의 콤보박스 상태 저장
                combo_text = ""
                if c == 0:
                    widget = self.cellWidget(r, c)
                    if isinstance(widget, QComboBox):
                        combo_text = widget.currentText()
                
                row_content.append({"text": text, "combo": combo_text})
            rows_data.append(row_content)
            
        # 4. 행 삭제 및 삽입
        # 삭제 전 target_row 보정 (삭제되는 행이 target 위에 있으면 인덱스 감소)
        for r in selected_rows:
            if r < target_row:
                target_row -= 1
            self.removeRow(r)
            
        # 삽입
        for i, row_content in enumerate(rows_data):
            new_r = target_row + i
            self.insertRow(new_r)
            for c, data in enumerate(row_content):
                # 텍스트 복구
                new_item = QTableWidgetItem(data["text"])
                self.setItem(new_r, c, new_item)
                
                # 캐릭터 콤보박스 복구
                if c == 0:
                    # 메인 윈도우의 캐릭터 목록을 가져와야 함 (부모의 부모... 접근)
                    mw = self.window()
                    char_names = []
                    # [수정] main.py와 함수 이름 통일
                    if hasattr(mw, 'get_character_list'):
                        char_names = mw.get_character_list()
                    
                    # main.py의 create_table_combo와 유사한 로직
                    if hasattr(mw, 'create_table_combo'):
                        combo = mw.create_table_combo(char_names, data["combo"])
                        self.setCellWidget(new_r, c, combo)
        
        # [추가] 이동 완료 후 자동 저장 호출
        mw = self.window()
        if hasattr(mw, 'save_script_data'):
            mw.save_script_data()

        self.selectRow(target_row) # 이동 후 선택 상태 유지
        self.setFocus() # [추가] 단축키가 바로 작동하도록 포커스 확보
        
        # [핵심] 이동이 완전히 끝난 상태를 다음 편집을 위한 기준점으로 강제 저장하지 않고,
        # 다음 액션이 발생할 때 현재(이동 후) 상태가 이전(이동 전) 상태와 다르다는 것을 
        # 확실히 인지하도록 처리합니다.
        
        # [핵심 수정] Qt의 기본 MoveAction이 원본을 한 번 더 지우지 않도록 Ignore 처리
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        
        # [추가] 이동이 완전히 끝난 후의 상태를 스택에 한 번 더 기록하여
        # 이후의 텍스트 수정이 이 '이동된 위치'를 기준으로 취소될 수 있게 합니다.
        self.save_state_for_undo()

    def keyPressEvent(self, event):
        # [추가] Undo / Redo 단축키 감지
        if event.modifiers() & Qt.ControlModifier:
            if event.modifiers() & Qt.ShiftModifier and event.key() == Qt.Key_Z:
                self.redo()
                event.accept()
                return
            elif event.key() == Qt.Key_Z:
                self.undo()
                event.accept()
                return

        if event.matches(QKeySequence.Copy):
            self.copy_selection()
            return
        if event.matches(QKeySequence.Paste):
            self.save_state_for_undo() # [추가] 붙여넣기 전 상태 저장
            self.paste_selection()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.save_state_for_undo() # [추가] 지우기 전 상태 저장
            self.delete_selection()
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

    def delete_selection(self):
        """선택된 셀들의 내용을 지웁니다 (콤보박스 포함)"""
        for item in self.selectedItems():
            item.setText("")
        # 콤보박스 지우기 (선택된 셀이 0번 컬럼인 경우)
        for index in self.selectedIndexes():
            if index.column() == 0:
                widget = self.cellWidget(index.row(), 0)
                if isinstance(widget, QComboBox):
                    widget.setCurrentIndex(-1)
        
        # 저장 유도
        mw = self.window()
        if hasattr(mw, 'save_script_data'):
            mw.save_script_data()

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
import re
import difflib
import time
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTextEdit, 
QLabel, QPushButton, QMessageBox, QFrame, QWidget)
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
        info_label = QLabel("💡 수정된 부분에 커서를 두면 '원래대로' 되돌릴 수 있습니다 (✓: 띄어쓰기, ⁀: 붙여쓰기).")
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
        self.edit_org.setFont(QFont("Pretendard", 13))
        self.edit_org.setPlaceholderText("원본 텍스트")
        self.edit_org.setStyleSheet(f"QTextEdit {{ background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; }} {scrollbar_style}")
        self.edit_org.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        # 2. 교정본 에디터 (오른쪽 - 핵심 위젯)
        self.edit_new = QTextEdit()
        self.edit_new.setFont(QFont("Pretendard", 13))
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

        # [핵심] 스크롤 동기화 (무한 루프 방지를 위해 락 사용)
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
        start_time = time.time()
        print(f"DEBUG: [SpellCheck] 결과 렌더링 시작 (원본 길이: {len(text1)}, 교정본 길이: {len(text2)})")
        
        self.diff_data = []
        d = difflib.SequenceMatcher(None, text1, text2)
        
        # 신호 차단하여 이벤트 루프 간섭 방지
        self.edit_org.blockSignals(True)
        self.edit_new.blockSignals(True)
        
        self.edit_org.clear()
        self.edit_new.clear()
        
        cursor_org = self.edit_org.textCursor()
        cursor_new = self.edit_new.textCursor()
        
        diff_start = time.time()
        opcodes = d.get_opcodes()
        print(f"DEBUG: [SpellCheck] Diff 분석 완료 (Opcode 수: {len(opcodes)})")
        
        current_idx = 0
        self._is_syncing = True # 렌더링 중 스크롤 동기화 차단
        
        # [기능 개선] 띄어쓰기와 글자 교정을 완벽히 분리하기 위한 정밀 분할 로직
        def get_granular_segments(org, new, tag_type):
            if tag_type == 'equal':
                return [('equal', org, new)]
            if not org:
                return [('insert', '', new)]
            if not new:
                return [('delete', org, '')]
            
            # 교체(replace) 구역: 단어 단위로 쪼개서 매칭 시도
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

        # [성능 최적화] 대량의 텍스트 삽입 시 발생하는 레이아웃 계산을 억제하기 위해 에딧 블록 사용
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
                    
                    if s_org.strip() == "":
                        fmt_new.setBackground(QColor("#E0E7FF"))
                        fmt_new.setForeground(QColor("#4338CA"))
                        fmt_new.setFontWeight(QFont.Bold)
                        fmt_new.setProperty(QTextFormat.UserProperty + 1, current_idx)
                        cursor_new.insertText("⁀", fmt_new)
                    
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
        self._is_syncing = False # 렌더링 완료 후 동기화 해제
        
        print(f"DEBUG: [SpellCheck] 전체 렌더링 프로세스 완료 (총 소요 시간: {time.time() - start_time:.2f}초)")

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
        # 현재 커서 위치의 문자 포맷에서 diff_id 속성을 즉시 확인 (O(1) 성능)
        fmt = cursor.charFormat()
        diff_id = fmt.property(QTextFormat.UserProperty + 1)
        
        # 만약 커서 왼쪽 문자에 정보가 없다면 오른쪽 문자도 확인 (커서가 단어 사이에 있을 때 대비)
        if diff_id is None:
            cursor.movePosition(QTextCursor.NextCharacter, QTextCursor.KeepAnchor)
            diff_id = cursor.charFormat().property(QTextFormat.UserProperty + 1)
            cursor.movePosition(QTextCursor.PreviousCharacter) # 원래대로

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
        # 시각적 피드백을 위해 넣은 부호들을 다시 복구/제거
        text = text.replace("✓", " ")
        text = text.replace("⁀", "")
        
        self.result_text = text
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

# --- [회차 목록용 커스텀 위젯] ---
class EpisodeItemWidget(QWidget):
    def __init__(self, name, status, parent=None):
        super().__init__(parent)
        self.setFixedHeight(60) # 전체 셀 높이 약간 축소
        
        # 메인 레이아웃 (아이템 간의 간격을 위해 여백 설정)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 4, 5, 4)
        
        # [그룹화 상자] 실제 아이템의 배경과 테두리를 담당
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
        
        self.set_style(False) # [위치 수정] 라벨 생성 후 스타일 설정
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
        else: # 대기중
            return """
                background-color: #F3F4F6;
                color: #6B7280;
                border: 1px solid #D1D5DB;
                border-radius: 13px;
                font-size: 11px;
                font-weight: bold;
            """

import os

class ImageViewerDialog(QDialog):
    def __init__(self, epi_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"이미지 보기 - {os.path.basename(epi_dir)}")
        self.resize(600, 800)
        self.setMinimumSize(400, 400)
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
        self.scroll_area.verticalScrollBar().setSingleStep(150) # 스크롤 간격 넓게 조정
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff) # 가로 스크롤바 완전히 숨김
        
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
                
                # 초기 렌더링은 resizeEvent가 담당하므로 임시로 빈 라벨만 추가
                self.content_layout.addWidget(lbl)
                
        # 뷰포트 크기 변화 감지를 위한 이벤트 필터 설치
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

class ProjectManagementDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("작품 및 회차 관리")
        self.setFixedSize(700, 700)
        # MSWindowsFixedSizeDialogHint를 사용하여 윈도우 네이티브 비활성화 처리 시도
        self.setWindowFlags(Qt.Dialog | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        # 1. UI를 먼저 생성 (self.list_titles 등이 여기서 만들어짐)
        self.init_ui()
        # 2. UI 생성 후 데이터를 채움
        self.refresh_projects()

    def init_ui(self):
        # 메인 레이아웃
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        # 공통 버튼 스타일
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

        # --- [왼쪽: 작품(Title) 관리] ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(10)

        # 헤더
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

        # 검색바
        self.search_bar = QLineEdit()
        self.search_bar.setFont(QFont("Pretendard", 13))
        self.search_bar.setPlaceholderText("🔍 작품 검색...")
        self.search_bar.setFixedHeight(34)
        self.search_bar.setClearButtonEnabled(True) # [추가] 지우기 버튼 활성화
        self.search_bar.setStyleSheet("""
            QLineEdit {
                border: 1px solid #D1D5DB;
                border-radius: 6px;
                padding-left: 10px;
                padding-right: 5px;
                background-color: #F9FAFB;
                font-size: 13px;
                font-family: 'Pretendard';
            }
            QLineEdit:focus {
                border: 2px solid #FF5722;
                background-color: white;
            }
        """)
        self.search_bar.textChanged.connect(self.filter_projects)
        left_layout.addWidget(self.search_bar)
        
        # 작품 목록
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
        left_layout.addWidget(self.list_titles)

        # 버튼 행
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

        # --- [오른쪽: 회차(Episode) 관리] ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(10)

        # 헤더
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
        
        # 회차 목록 스택 (Empty State 지원)
        self.epi_stack = QStackedWidget()
        
        # 1. Empty State
        self.empty_widget = QWidget()
        empty_box = QVBoxLayout(self.empty_widget)
        lbl_empty = QLabel("왼쪽 목록에서 작품을 선택해 주세요.")
        lbl_empty.setAlignment(Qt.AlignCenter)
        lbl_empty.setStyleSheet("color: #9CA3AF; font-size: 14px;")
        empty_box.addStretch()
        empty_box.addWidget(lbl_empty)
        empty_box.addStretch()
        
        # 2. 리스트 위젯
        self.list_episodes = QListWidget()
        self.list_episodes.setSelectionMode(QListWidget.ExtendedSelection) # [추가] 다중 선택 활성화
        self.list_episodes.setSpacing(5) # [수정] 간격을 5px로 조정
        self.list_episodes.setContextMenuPolicy(Qt.CustomContextMenu) # 컨텍스트 메뉴 활성화
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

        # 버튼 행
        # 버튼 행 (필수 버튼만 남김)
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


    # --- [비즈니스 로직] ---

    def filter_projects(self, text):
        """작품 목록 실시간 필터링"""
        for i in range(self.list_titles.count()):
            item = self.list_titles.item(i)
            item.setHidden(text.lower() not in item.text().lower())

    def on_episode_selection_changed(self):
        """회차 선택 변경 시 커스텀 위젯의 스타일 갱신"""
        for i in range(self.list_episodes.count()):
            item = self.list_episodes.item(i)
            widget = self.list_episodes.itemWidget(item)
            if widget:
                widget.set_style(item.isSelected())

    def refresh_projects(self):
        """프로젝트 폴더를 스캔하여 좌측 리스트를 갱신"""
        self.list_titles.clear()
        if os.path.exists(PROJECTS_DIR):
            titles = sorted([d for d in os.listdir(PROJECTS_DIR) 
                           if os.path.isdir(os.path.join(PROJECTS_DIR, d))])
            self.list_titles.addItems(titles)
        self.load_episodes("") # 초기화

    def load_episodes(self, title):
        """선택한 작품의 회차 목록을 우측 리스트에 표시 (커스텀 위젯 적용)"""
        self.list_episodes.clear()
        if not title:
            self.epi_stack.setCurrentIndex(0)
            return
        
        self.epi_stack.setCurrentIndex(1)
        t_path = os.path.join(PROJECTS_DIR, title)
        if os.path.exists(t_path):
            episodes = sorted([d for d in os.listdir(t_path) 
                             if os.path.isdir(os.path.join(t_path, d))])
            
            for epi in episodes:
                epi_dir = os.path.join(t_path, epi)
                img_path = os.path.join(epi_dir, "images")
                script_path = os.path.join(epi_dir, "script_data.csv")
                
                # 3단계 상태 로직
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
                item.setSizeHint(QSize(0, 60)) # [수정] 60px로 조정
                self.list_episodes.addItem(item)
                self.list_episodes.setItemWidget(item, widget)
                # 데이터 보관용
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
        """작품 삭제: 폴더 존재 여부를 체크하여 에러 방지"""
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
        
        # [추가] 대기중 상태(데이터 없음)인 경우 저장 버튼 비활성화
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
            for item in selected_items:
                epi_name = item.data(Qt.UserRole)
                epi_path = os.path.join(PROJECTS_DIR, title, epi_name)
                try:
                    if os.path.exists(epi_path):
                        shutil.rmtree(epi_path)
                    success_count += 1
                except Exception as e:
                    print(f"Delete failed for {epi_name}: {e}")

            self.load_episodes(title)
            if success_count < count:
                QMessageBox.warning(self, "삭제 완료", f"{count}개 중 {success_count}개 삭제 완료 (일부 실패)")

    def batch_save_text(self):
        """선택한 회차들을 개별 텍스트 파일로 저장"""
        title_item = self.list_titles.currentItem()
        selected_items = self.list_episodes.selectedItems()
        if not title_item or not selected_items: return
        
        title = title_item.text()
        count = len(selected_items)
        
        save_dir = None
        single_save_path = None
        
        if count == 1:
            epi_name = selected_items[0].data(Qt.UserRole)
            # 마지막 저장 경로를 고려한 기본 경로 설정
            default_path = os.path.join(config.get_initial_dir(), f"{title}_{epi_name}_텍스트.txt")
            # [맥 네이티브 창 복구] 
            options = QFileDialog.Option(0) if platform.system() == "Darwin" else QFileDialog.DontConfirmOverwrite
            single_save_path, _ = QFileDialog.getSaveFileName(self, "텍스트 파일 저장", default_path, "Text Files (*.txt)", options=options)
            if not single_save_path: return
            config.update_last_save_dir(single_save_path)
            
            if os.path.exists(single_save_path):
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("파일 중복 확인")
                msg_box.setText(f"'{os.path.basename(single_save_path)}' 파일이 이미 존재합니다.")
                msg_box.setInformativeText("기존 파일을 대체할까요, 아니면 새 이름으로 저장할까요?")
                
                # 버튼 순서: [덮어쓰기] [새 이름으로 저장] [취소]
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
                
                # 일괄 저장일 때만 중복 체크 로직 실행 (개별 저장은 대화창에서 이미 처리함)
                if count > 1 and os.path.exists(dest_path) and not overwrite_all:
                    if skip_all: continue
                    if overwrite_all: pass # 아래 로직 실행
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
                        # btn_yes는 그냥 통과하여 아래 저장 로직 실행

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
        """선택한 회차들을 템플릿 기반 엑셀 파일로 저장"""
        title_item = self.list_titles.currentItem()
        selected_items = self.list_episodes.selectedItems()
        if not title_item or not selected_items: return
        
        title = title_item.text()
        count = len(selected_items)
        
        save_dir = None
        single_save_path = None
        
        if count == 1:
            epi_name = selected_items[0].data(Qt.UserRole)
            # 마지막 저장 경로를 고려한 기본 경로 설정
            default_path = os.path.join(config.get_initial_dir(), f"{title}_{epi_name}_스크립트.xlsx")
            # [맥 네이티브 창 복구]
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
            
            # script.txt나 script_data.csv 중 하나라도 있어야 저장 가능
            if os.path.exists(os.path.join(epi_dir, "script.txt")) or os.path.exists(os.path.join(epi_dir, "script_data.csv")):
                if count == 1:
                    dest_path = single_save_path
                else:
                    dest_filename = f"{title}_{epi_name}_스크립트.xlsx"
                    dest_path = os.path.join(save_dir, dest_filename)
                
                # 일괄 저장일 때만 중복 체크
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
                
                # 템플릿 기반 저장 로직 호출 (excel_handler 사용)
                if excel_handler.save_episode_to_excel_final(self, epi_dir, title, epi_name, dest_path):
                    success_count += 1

        if count > 1:
            if success_count == count:
                if hasattr(self.parent(), 'toast'):
                    self.parent().toast.show_message(f"📊 {success_count}개의 엑셀 파일 저장 완료")
            else:
                QMessageBox.warning(self, "저장 완료 (일부 실패)", f"{count}개 중 {success_count}개 저장 성공\n(일부 파일 저장에 실패했습니다.)")


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
        font = QFont()
        font.setFamilies(["Pretendard", "-apple-system", "Helvetica Neue", "Segoe UI", "Malgun Gothic", "sans-serif"])
        font.setPointSize(24)
        font.setBold(True)
        font.setStyleStrategy(QFont.PreferAntialias)
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

    def contextMenuEvent(self, event):
        # 1. 표준 컨텍스트 메뉴 생성
        menu = self.createStandardContextMenu()
        
        # 2. 영문 메뉴 항목들을 친근한 한국어로 동적 맵핑
        for action in menu.actions():
            text = action.text()
            clean_text = text.replace("&", "")
            
            if clean_text == "Undo":
                action.setText("되돌리기 (&U)")
            elif clean_text == "Redo":
                action.setText("다시 실행 (&R)")
            elif clean_text == "Cut":
                action.setText("잘라내기 (&T)")
            elif clean_text == "Copy":
                action.setText("복사 (&C)")
            elif clean_text == "Paste":
                action.setText("붙여넣기 (&P)")
            elif clean_text == "Delete":
                action.setText("삭제 (&D)")
            elif clean_text == "Select All":
                action.setText("모두 선택 (&A)")
                
        # 3. 메뉴 표시
        menu.exec(event.globalPos())


# =======================================================
# 토스트 메시지 (애니메이션 충돌 방지 완벽 버전)
# =======================================================
class ToastMessage(QWidget):
    def __init__(self, parent):
        super().__init__(parent, Qt.ToolTip | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_StyledBackground, True)
        
        # 메인 레이아웃
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # 배경 프레임
        self.bg_frame = QFrame()
        self.bg_frame.setStyleSheet("""
            QFrame {
                background-color: #282C34;
                border-radius: 18px;
            }
        """)
        frame_layout = QVBoxLayout(self.bg_frame)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        
        # 메시지 라벨
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
        
        # 1. 투명도 효과 설정
        self.opacity_effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self.opacity_effect)
        
        # 2. 애니메이션 설정
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
        
        # 기존에 남아있을 수 있는 '숨기기' 예약 취소
        # (시그널 연결 대신 타이머를 사용하여 경고 발생 원인을 제거함)
            
        self.lbl_text.setText(text)
        self.lbl_text.adjustSize()
        self.adjustSize()
        
        # 부모 위젯의 하단 중앙에 배치 (스크린 좌표 기준)
        if self.parent():
            parent_geom = self.parent().frameGeometry()
            x = parent_geom.x() + (parent_geom.width() - self.width()) // 2
            y = parent_geom.y() + parent_geom.height() - self.height() - 80
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
        # 애니메이션 시작
        self.anim.start()
        
        # 애니메이션이 끝나는 시점(600ms)에 맞춰서 위젯을 숨기도록 타이머 설정
        # (시그널 연결 해제 시 발생하는 RuntimeWarning을 원천 차단)
        QTimer.singleShot(600, self.hide)

# =======================================================
# 설정창 (프리셋)
# =======================================================
class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("API 키 프리셋 관리")
        self.setFixedWidth(550) # 가로 폭만 다시 단단히 고정 (맥OS 축소 현상 방지)
        # 가변 높이를 위해 setFixedSize 삭제
        # MSWindowsFixedSizeDialogHint를 사용하여 윈도우 네이티브 비활성화 처리 시도
        # 높이 조절을 위해 MSWindowsFixedSizeDialogHint 제거
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        self.local_presets = config.API_PRESETS.copy()
        self.local_active = config.ACTIVE_PRESET_NAME
        self.is_unified = False # 통합 사용 여부 플래그
        
        self.init_ui()
    
    # 전문적인 느낌의 얇은 선(Thin Line) 스타일 아이콘
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
            button.setIcon(self.get_svg_icon(self.SVG_EYE_CLOSE)) # 눈 감은 아이콘으로 변경
        else:
            line_edit.setEchoMode(QLineEdit.Password)
            button.setIcon(self.get_svg_icon(self.SVG_EYE_OPEN)) # 다시 눈 뜬 아이콘으로

    def init_ui(self):
        layout = QVBoxLayout(self)
        
        # 전체 스타일 설정 (툴팁은 이제 전역 스타일을 따름)
        self.setStyleSheet("")

        # SetFixedSize 옵션 제거 (맥OS 렌더링 버그 원인)
        layout.setContentsMargins(25, 20, 25, 30) 
        layout.setSpacing(12) 


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
        
        # [OCR 키 -> Google Cloud API 키]
        lbl_ocr = QLabel("Google Cloud API 키 (Vision + Gemini)")
        lbl_ocr.setStyleSheet("font-weight: bold; color: #555;")
        
        # 입력창과 버튼을 가로로 배치하기 위한 레이아웃
        row_ocr_input = QHBoxLayout()
        self.input_ocr = QLineEdit()
        self.input_ocr.setPlaceholderText("Google Cloud API Key")
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
        keys_layout.addSpacing(5) # 간격 축소
        
        # [신규] 아코디언 토글 버튼
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

        # [AI 키 컨테이너 (기본 숨김)]
        self.ai_container = QWidget()
        ai_layout = QVBoxLayout(self.ai_container)
        # 상단 여백 5, 하단 여백 5 (하단 둥근 테두리 잘림 방지를 위한 핵심!)
        ai_layout.setContentsMargins(0, 5, 0, 5)
        ai_layout.setSpacing(8)

        # [AI 키]
        lbl_ai = QLabel("Google AI Studio API 키 (맞춤법 전용)")
        lbl_ai.setStyleSheet("font-weight: bold; color: #2ecc71;")
        
        row_ai_input = QHBoxLayout()
        self.input_ai = QLineEdit()
        self.input_ai.setPlaceholderText("Google AI Studio API Key")
        self.input_ai.setEchoMode(QLineEdit.Password)
        self.input_ai.setFixedHeight(36)
        self.input_ai.textChanged.connect(self.save_temp_data)
        
        # OCR 키 변경 시 통합 모드면 AI 키도 자동 업데이트
        self.input_ocr.textChanged.connect(self.sync_keys)
        
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
        
        ai_layout.addWidget(lbl_ai)
        ai_layout.addLayout(row_ai_input)
        
        keys_layout.addWidget(self.ai_container)
        
        layout.addLayout(keys_layout)
        
        # 버튼 영역과 입력창 사이에 확실한 여유 공간 (더 넉넉하게)
        layout.addSpacing(25)

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
        data = self.local_presets.get(preset_name, {"ocr": "", "ai": "", "unified": True}) # 기본값 True (통합)
        self.is_unified = data.get("unified", True)
        
        self.input_ocr.blockSignals(True)
        self.input_ai.blockSignals(True)
        
        self.input_ocr.setText(data.get("ocr", ""))
        # UI상으로는 'ui_ai'가 있으면 그걸 쓰고 없으면 'ai'를 쓰되, 
        # 통합 모드에서 저장된 'ai'가 'ocr'과 같다면 비워줌
        ui_ai = data.get("ui_ai", "")
        if not ui_ai and not self.is_unified:
            ui_ai = data.get("ai", "")
        
        self.input_ai.setText(ui_ai)
        
        self.input_ocr.blockSignals(False)
        self.input_ai.blockSignals(False)
        
        self.set_unified_mode(self.is_unified)

    def toggle_advanced_mode(self):
        # 아코디언 토글 (숨겨져 있으면 분리로, 열려 있으면 통합으로)
        self.set_unified_mode(not self.is_unified)

    def set_unified_mode(self, is_unified):
        self.is_unified = is_unified

        # 1. 위젯 표시/숨김 (동기적 처리로 들썩임 방지)
        self.ai_container.setVisible(not is_unified)

        # 2. 창 크기 즉각 재조정
        # adjustSize()는 창을 늘리기만 하고 줄이지는 않는 Qt의 특성이 있습니다.
        # 따라서 아코디언을 닫을 때 창이 쪼그라들도록 명시적으로 resize를 호출합니다.
        QApplication.processEvents() # 레이아웃 엔진 강제 업데이트
        self.resize(550, self.sizeHint().height())

        # 3. 텍스트 및 아이콘 업데이트
        if is_unified:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_DOWN))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (선택 사항)")
        else:
            self.btn_toggle_advanced.setIcon(self.get_svg_icon(self.SVG_CHEVRON_UP))
            self.btn_toggle_advanced.setText("Google AI Studio API 키 별도 설정 (닫기)")

        self.save_temp_data()
    def sync_keys(self):
        # [수정] 시각적 동기화 중단 (사용자 요청: 밑에 키가 안 보여야 함)
        pass

    def save_temp_data(self):
        if self.local_active:
            ocr_val = self.input_ocr.text().strip()
            ai_val = self.input_ai.text().strip()
            
            # 통합 모드일 경우 내부적으로는 AI 키에 OCR 키를 할당하여 저장하되,
            # UI상(ai_val)으로는 비어있을 수 있음
            actual_ai = ocr_val if self.is_unified else ai_val
            
            self.local_presets[self.local_active] = {
                "ocr": ocr_val,
                "ai": actual_ai, # 실제로 사용될 키
                "ui_ai": ai_val,  # UI상의 개별 키 값 보존용 (옵션)
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

# =======================================================
# =======================================================
# 관용구 개별 카드 위젯
# =======================================================
class IdiomCard(QFrame):
    delete_signal = Signal(dict)

    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.setFixedHeight(40) # 높이 살짝 축소
        self.setStyleSheet("background-color: transparent; border: none;")
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0) # 메인 레이아웃 여백 제거
        layout.setSpacing(8) # 박스 간 간격
        
        # 1. 지문 내용 박스
        self.frame_text = QFrame()
        self.frame_text.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #e5e7eb; border-radius: 6px; }
            QFrame:hover { border: 1px solid #FF5722; background-color: #fff9f7; }
        """)
        text_layout = QHBoxLayout(self.frame_text)
        text_layout.setContentsMargins(15, 0, 15, 0)
        self.lbl_text = QLabel(data["text"])
        self.lbl_text.setAlignment(Qt.AlignCenter) # 중앙 정렬 추가
        self.lbl_text.setStyleSheet("font-size: 14px; color: #1f2937; border: none; background: transparent;")
        text_layout.addWidget(self.lbl_text)
        layout.addWidget(self.frame_text, 1)
        
        # 2. 단축키 박스
        self.frame_key = QFrame()
        self.frame_key.setFixedWidth(100)
        self.frame_key.setStyleSheet("""
            QFrame { background-color: white; border: 1px solid #e5e7eb; border-radius: 6px; }
            QFrame:hover { border: 1px solid #FF5722; }
        """)
        key_layout = QHBoxLayout(self.frame_key)
        key_layout.setContentsMargins(0, 0, 0, 0)
        self.lbl_key = QLabel(f"Alt + {data['key'].upper()}")
        self.lbl_key.setAlignment(Qt.AlignCenter)
        self.lbl_key.setStyleSheet("color: #4b5563; font-weight: bold; font-size: 12px; border: none; background: transparent;")
        key_layout.addWidget(self.lbl_key)
        layout.addWidget(self.frame_key)
        
        # 3. 삭제 버튼 박스
        self.frame_del = QFrame()
        self.frame_del.setFixedWidth(40)
        self.frame_del.setStyleSheet("""
            QFrame { background-color: #e5e7eb; border: 1px solid #d1d5db; border-radius: 6px; }
            QFrame:hover { border: 1px solid #ef4444; background-color: #fee2e2; }
        """)
        del_layout = QHBoxLayout(self.frame_del)
        del_layout.setContentsMargins(0, 0, 0, 0)
        self.btn_del = QPushButton("✕")
        self.btn_del.setFixedSize(38, 38)
        self.btn_del.setCursor(Qt.PointingHandCursor)
        self.btn_del.setStyleSheet("""
            QPushButton { border: none; color: #9ca3af; font-size: 18px; background: transparent; }
            QPushButton:hover { color: #ef4444; }
        """)
        self.btn_del.clicked.connect(lambda: self.delete_signal.emit(self.data))
        del_layout.addWidget(self.btn_del)
        layout.addWidget(self.frame_del)

# 관용구 설정 다이얼로그
# =======================================================
class IdiomSettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관용구(지문) 설정")
        self.setFixedSize(520, 500) # 너비와 높이를 약간 조절
        self.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint)
        
        # 로컬 데이터 복사본 (취소 시 복구용)
        self.local_idioms = [item.copy() for item in config.IDIOMS]
        
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(25, 20, 25, 20)
        layout.setSpacing(15)

        # 1. 상단 제목 및 설명
        header_layout = QVBoxLayout()
        header_layout.setSpacing(5)
        
        lbl_title = QLabel("자주 사용하는 괄호 지문과 단축키를 관리하세요.")
        lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #1f2937;")
        header_layout.addWidget(lbl_title)

        lbl_desc = QLabel("Alt + [키]를 누르면 해당 지문이 즉시 입력됩니다.")
        lbl_desc.setStyleSheet("color: #6b7280; font-size: 13px;")
        header_layout.addWidget(lbl_desc)
        
        layout.addLayout(header_layout)

        # 2. [수정] 입력 영역 (박스 제거 및 높이 축소)
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 5, 0, 5)
        input_layout.setSpacing(8)

        self.input_text = QLineEdit()
        self.input_text.setPlaceholderText("예: (속)") 
        self.input_text.setFixedHeight(36) 
        
        self.input_key = QLineEdit()
        self.input_key.setPlaceholderText("단축키(숫자/영문)")
        self.input_key.setFixedWidth(140) 
        self.input_key.setFixedHeight(36) 
        self.input_key.setMaxLength(1) 
        self.input_key.setAlignment(Qt.AlignLeft | Qt.AlignVCenter) # 다시 왼쪽 정렬로 변경
        
        btn_add = QPushButton("추가")
        btn_add.setFixedSize(70, 36) 
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet("""
            QPushButton {
                background-color: #FF5722;
                color: white;
                border: none;
                border-radius: 4px;
                font-weight: bold;
                padding: 0px; /* 패딩 제거하여 시스템 기본 중앙 정렬 유도 */
                text-align: center;
            }
            QPushButton:hover {
                background-color: #E64A19;
            }
        """)
        btn_add.clicked.connect(self.add_idiom)

        input_layout.addWidget(self.input_text, 1)
        input_layout.addWidget(self.input_key)
        input_layout.addWidget(btn_add)
        layout.addLayout(input_layout)

        # 3. 리스트 영역 (테두리와 헤더를 포함하는 메인 컨테이너)
        self.scroll_container = QFrame()
        self.scroll_container.setStyleSheet("""
            QFrame { border: 1px solid #e5e7eb; border-radius: 8px; background-color: #f9fafb; }
        """)
        container_layout = QVBoxLayout(self.scroll_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)

        # [최종 해결] 헤더를 컨테이너 내부 최상단에 배치하여 너비 동기화
        self.header_widget = QWidget()
        self.header_widget.setFixedHeight(35)
        self.header_widget.setStyleSheet("""
            QWidget { background-color: #f3f4f6; border: none; border-bottom: 1px solid #e5e7eb; border-top-left-radius: 7px; border-top-right-radius: 7px; }
        """)
        self.header_layout = QHBoxLayout(self.header_widget)
        self.header_layout.setContentsMargins(10, 0, 10, 0) # 리스트 여백(10)과 일치
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

        self.header_layout.addWidget(create_header_box("지문 내용"), 1)
        self.header_layout.addWidget(create_header_box("단축키", width=100))
        self.header_layout.addWidget(create_header_box("삭제", width=40))
        
        # [정렬 핵심] 스크롤바(12px) 공간만큼 헤더 우측에도 고정 여백 추가
        self.header_layout.addSpacing(12)
        
        container_layout.addWidget(self.header_widget)

        # 4. 스크롤 영역
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.NoFrame)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn) # 항상 표시하여 정렬 고정
        self.scroll_area.setStyleSheet("""
            QScrollArea { background-color: transparent; border: none; }
            QScrollBar:vertical { 
                border: none; background: transparent; width: 12px; margin: 0;
            }
            QScrollBar::handle:vertical { 
                background: #d1d5db; border-radius: 6px; min-height: 20px; margin: 2px;
            }
            QScrollBar::handle:vertical:hover { background: #9ca3af; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        
        self.list_widget = QWidget()
        self.list_widget.setStyleSheet("background-color: transparent;")
        self.list_layout = QVBoxLayout(self.list_widget)
        self.list_layout.setContentsMargins(10, 10, 10, 10)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        
        self.scroll_area.setWidget(self.list_widget)
        container_layout.addWidget(self.scroll_area)
        layout.addWidget(self.scroll_container)

        # 4. 하단 버튼
        bottom_layout = QHBoxLayout()
        bottom_layout.addStretch()
        
        btn_save = QPushButton("설정 저장")
        btn_save.setObjectName("PrimaryBtn")
        btn_save.setFixedSize(110, 38)
        btn_save.setCursor(Qt.PointingHandCursor)
        btn_save.clicked.connect(self.save_and_close)
        
        btn_close = QPushButton("닫기")
        btn_close.setFixedSize(80, 38)
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.reject)
        
        bottom_layout.addWidget(btn_save)
        bottom_layout.addWidget(btn_close)
        layout.addLayout(bottom_layout)

    def refresh_list(self):
        # 기존 위젯들 제거 (Stretch 제외)
        while self.list_layout.count() > 1:
            item = self.list_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # 카드 추가
        for idiom in self.local_idioms:
            card = IdiomCard(idiom)
            card.delete_signal.connect(self.delete_idiom_by_data)
            self.list_layout.insertWidget(self.list_layout.count() - 1, card)

    def delete_idiom_by_data(self, data):
        if data in self.local_idioms:
            self.local_idioms.remove(data)
            self.refresh_list()

    def add_idiom(self):
        text = self.input_text.text().strip()
        key = self.input_key.text().strip().upper() # 대문자로 통일

        if not text or not key:
            QMessageBox.warning(self, "알림", "내용과 단축키를 모두 입력해주세요.")
            return

        # [수정] 영문자 또는 숫자만 허용
        if not key.isalnum():
            QMessageBox.warning(self, "알림", "단축키는 숫자 또는 영문자 1글자만 가능합니다.")
            return

        # 중복 체크 (대소문자 구분 없이)
        if any(item["key"].upper() == key for item in self.local_idioms):
            QMessageBox.warning(self, "알림", f"단축키 '{key}'는 이미 사용 중입니다.")
            return

        self.local_idioms.append({"text": text, "key": key})
        self.input_text.clear()
        self.input_key.clear()
        self.refresh_list()

    def delete_idiom(self):
        # 개별 카드에서 삭제 버튼을 누르므로 이 함수는 더 이상 사용되지 않거나
        # 다른 용도로 변경될 수 있습니다. 현재는 delete_idiom_by_data가 담당합니다.
        pass

    def save_and_close(self):
        config.IDIOMS = self.local_idioms
        config.save_settings(config.API_PRESETS, config.ACTIVE_PRESET_NAME)
        self.accept()

# =================================================================
# [신규] 관용구 플로팅 뷰어
# =================================================================
class FloatingIdiomViewer(QDialog):
    idiom_selected = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("관용구 도우미")
        # 윈도우 모드 + 항상 위 옵션 (비모달로 띄워야 함)
        self.setWindowFlags(Qt.Window | Qt.WindowStaysOnTopHint)
        self.setMinimumSize(300, 450)
        self.init_ui()
        self.refresh_list()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(10)

        # 검색 바
        self.search_bar = QLineEdit()
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
        """)
        self.search_bar.textChanged.connect(self.filter_list)
        layout.addWidget(self.search_bar)

        # 리스트 위젯
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

        lbl_info = QLabel("💡 단축키(Alt+키) 혹은 더블 클릭하면 자동 삽입됩니다.")
        lbl_info.setStyleSheet("color: #6B7280; font-size: 11px; font-family: 'Pretendard';")
        layout.addWidget(lbl_info)

    def refresh_list(self):
        self.list_widget.clear()
        for item in config.IDIOMS:
            # 리스트 아이템 객체 생성
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 50)) # 높이 확보
            
            # 커스텀 위젯 생성
            container = QWidget()
            item_layout = QHBoxLayout(container)
            item_layout.setContentsMargins(15, 0, 15, 0)
            item_layout.setSpacing(10)
            
            # 좌측: 관용구 텍스트
            lbl_text = QLabel(item['text'])
            lbl_text.setStyleSheet("font-size: 14px; font-weight: 500; color: #1F2937; border: none; background: transparent;")
            
            # 우측: 단축키 뱃지
            key_text = f"Alt + {item['key']}"
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
            
            item_layout.addWidget(lbl_text, 1) # 텍스트가 공간을 차지함
            item_layout.addWidget(lbl_key)
            
            # 데이터를 아이템 객체에 저장 (검색 및 선택용)
            list_item.setData(Qt.UserRole, item['text'])
            
            self.list_widget.addItem(list_item)
            self.list_widget.setItemWidget(list_item, container)

    def filter_list(self, text=None):
        if text is None:
            text = self.search_bar.text()
            
        query = text.lower().strip()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            # UserRole에 저장된 데이터로 검색
            data = item.data(Qt.UserRole)
            search_target = str(data).lower() if data else ""
            
            # 검색어가 있으면 필터링, 없으면 모두 표시
            item.setHidden(query != "" and query not in search_target)

    def on_item_clicked(self, item):
        text = item.data(Qt.UserRole)
        self.idiom_selected.emit(text)
