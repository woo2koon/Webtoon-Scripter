# widgets/table.py
import json

from PySide6.QtWidgets import (
    QTableWidget, QTableWidgetItem, QAbstractItemView, QHeaderView,
    QComboBox, QLineEdit, QStyledItemDelegate, QApplication, QPushButton
)
from PySide6.QtCore import Qt, QTimer, Signal, QModelIndex
from PySide6.QtGui import QPainter, QColor, QPen, QKeySequence, QFont

import config

class UndoStateList(list):
    """list를 상속받아 동적 속성(auto_added_chars 등) 부여가 가능하도록 만든 상태 리스트 클래스"""
    pass

class SheetCellLineEdit(QLineEdit):
    def __init__(self, parent=None, delegate=None, index=None):
        super().__init__(parent)
        self.delegate = delegate
        self.index = index

    def keyPressEvent(self, event):
        # Shift + Enter 감지 시 내용분리 (셀 나누기) 기능 수행
        if event.key() in (Qt.Key_Return, Qt.Key_Enter) and (event.modifiers() & Qt.ShiftModifier):
            main_win = self.window()
            if main_win and hasattr(main_win, 'split_script_row'):
                cursor_pos = self.cursorPosition()
                full_text = self.text()
                left_text = full_text[:cursor_pos]
                right_text = full_text[cursor_pos:]
                
                # 에디터의 전체 텍스트를 먼저 확정하여 실행 취소(Undo) 스택에 전체 내용이 보존되도록 함
                self.setText(full_text)
                if self.delegate:
                    self.delegate.commitData.emit(self)
                    self.delegate.closeEditor.emit(self, QStyledItemDelegate.NoHint)
                
                # 메인 윈도우의 내용분리 기능 호출 (에디터가 완전히 닫히고 정리된 후 실행되도록 지연 호출)
                row_idx = self.index.row()
                QTimer.singleShot(50, lambda: main_win.split_script_row(row_idx, left_text, right_text))
                event.accept()
                return
        super().keyPressEvent(event)

class ExcelTextDelegate(QStyledItemDelegate):
    def __init__(self, parent=None):
        super().__init__(parent)

    def createEditor(self, parent, option, index):
        editor = SheetCellLineEdit(parent, delegate=self, index=index)
        
        # 글로벌 컨텍스트 메뉴에서 셀 에디터를 식별하고 분할 명령을 실행하기 위한 프로퍼티 설정
        editor.setProperty("is_sheet_editor", True)
        editor.setProperty("cell_row", index.row())
        editor.setProperty("delegate", self)

        editor.setStyleSheet("""
            QLineEdit { 
                border: 2px solid #ff4b4b; 
                border-radius: 0px;
                padding: 0px; 
                background-color: white;
                font-family: 'Pretendard';
                font-size: 15px;
            }
        """ + "\n" + config.MODERN_MENU_STYLE)
        editor.setAlignment(Qt.AlignVCenter) 

        # 커서 위치 실시간 추적 (포커스를 가진 상태에서 이동한 것만 유효)
        def on_cursor_changed(old_pos, new_pos):
            if editor.hasFocus():
                main_win = editor.window()
                if main_win:
                    main_win.last_sheet_editor_cursor_pos = new_pos
                    main_win.last_sheet_editor_cell = (index.row(), index.column())
                    
        editor.cursorPositionChanged.connect(on_cursor_changed)
        return editor

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def setModelData(self, editor, model, index):
        table = self.parent()
        if table and hasattr(table, 'save_state_for_undo'):
            table.save_state_for_undo()
        model.setData(index, editor.text(), Qt.EditRole)

    def setEditorData(self, editor, index):
        text = index.model().data(index, Qt.EditRole) or ""
        editor.setText(str(text))
        QTimer.singleShot(0, lambda: editor.end(False))

# =================================================================
# 엑셀형 테이블 위젯
# =================================================================
class SpreadsheetTable(QTableWidget):
    def __init__(self, rows=0, columns=0, parent=None):
        super().__init__(rows, columns, parent)
        
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
        self.verticalHeader().setDefaultAlignment(Qt.AlignCenter)

        app_font = QApplication.font()
        f_family = app_font.family()
        if f_family == "sans-serif" or not f_family:
            f_family = "Pretendard"
        table_font = QFont(f_family, 11)
        table_font.setStyleStrategy(QFont.PreferAntialias)
        table_font.setHintingPreference(QFont.PreferNoHinting)
        self.setFont(table_font)

        self.setStyleSheet(f"""
            QTableWidget {{
                gridline-color: #e0e0e0;
                background-color: white;
                selection-background-color: #e8f0fe;
                selection-color: black;
                font-family: '{f_family}', 'Malgun Gothic', 'Segoe UI', sans-serif;
                font-size: 14px;
                outline: none;
            }}
            QTableWidget::item {{ 
                padding-left: 5px; 
                padding-right: 5px; 
                font-family: '{f_family}', 'Malgun Gothic', 'Segoe UI', sans-serif;
                border-radius: 0px;
            }} 
            QTableWidget::item:focus {{ border: 2px solid #1a73e8; border-radius: 0px; }}
        """)
        
        self.drop_target_row = None
        self.undo_stack = []
        self.redo_stack = []
        self.is_undoing = False

    def clear_undo_stack(self):
        self.undo_stack.clear()
        self.redo_stack.clear()

    def get_table_state(self):
        state = UndoStateList()
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
        if self.state() == QAbstractItemView.EditingState:
            self.setCurrentIndex(QModelIndex()) 
            
        self.is_undoing = True
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        
        if self.rowCount() != len(state):
            self.setRowCount(len(state))
        
        mw = self.window()
        char_names = []
        if hasattr(mw, 'get_character_list'):
            char_names = mw.get_character_list()
            
        for r, row_data in enumerate(state):
            widget = self.cellWidget(r, 0)
            if isinstance(widget, QComboBox):
                if widget.currentText() != row_data["combo"]:
                    widget.setCurrentText(row_data["combo"])
            else:
                if hasattr(mw, 'create_table_combo'):
                    combo = mw.create_table_combo(char_names, row_data["combo"])
                    self.setCellWidget(r, 0, combo)
            
            old_item = self.item(r, 1)
            if old_item:
                if old_item.text() != row_data["text"]:
                    old_item.setText(row_data["text"])
            else:
                self.setItem(r, 1, QTableWidgetItem(row_data["text"]))
            
        self.setUpdatesEnabled(True)
        self.blockSignals(False)
        self.is_undoing = False
        self.setFocus()
        
        if hasattr(mw, 'save_script_data'):
            mw.save_script_data()

    def save_state_for_undo(self):
        if self.is_undoing:
            return
        state = self.get_table_state()
        
        if self.undo_stack and self.undo_stack[-1] == state:
            return
            
        self.undo_stack.append(state)
        self.redo_stack.clear()
        
        if len(self.undo_stack) > 50:
            self.undo_stack.pop(0)

    def undo(self):
        if not self.undo_stack:
            return
            
        if self.state() == QAbstractItemView.EditingState:
            self.setCurrentIndex(QModelIndex()) 
            
        current_state = self.get_table_state()
        
        while self.undo_stack:
            previous_state = self.undo_stack.pop()
            if previous_state != current_state:
                # 안전장치: 실행 취소로 복원될 상태가 0행(완전 초기화)이고,
                # 현재 테이블에 3행보다 많은 대본이 들어가 있는 상태라면,
                # 사용자 실수나 연타로 인한 데이터 유실을 방지하기 위해 0행으로의 되돌리기를 차단합니다.
                if len(previous_state) == 0 and len(current_state) > 3:
                    self.undo_stack.append(previous_state)  # 스택에 다시 넣어 원복
                    return
                
                # [실행취소 시 스텝 2 자동 추가된 캐릭터 연동 삭제]
                auto_chars = getattr(previous_state, "auto_added_chars", [])
                if auto_chars:
                    mw = self.window()
                    if mw and hasattr(mw, 'remove_character_card_only'):
                        for char_name in auto_chars:
                            mw.remove_character_card_only(char_name)
                    
                self.redo_stack.append(current_state)
                self.restore_table_state(previous_state)
                return

    def redo(self):
        if not self.redo_stack:
            return
            
        if self.state() == QAbstractItemView.EditingState:
            self.setCurrentIndex(QModelIndex())

        current_state = self.get_table_state()
        
        while self.redo_stack:
            next_state = self.redo_stack.pop()
            if next_state != current_state:
                self.undo_stack.append(current_state)
                self.restore_table_state(next_state)
                return

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat("application/x-character-row"):
            event.acceptProposedAction()
        elif event.source() == self:
            event.accept()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat("application/x-character-row"):
            event.acceptProposedAction()
        elif event.source() == self:
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
        if self.drop_target_row is not None:
            painter = QPainter(self.viewport())
            pen = QPen(QColor("#1a73e8"), 3)
            painter.setPen(pen)
            
            if self.drop_target_row < self.rowCount():
                y = self.rowViewportPosition(self.drop_target_row)
            else:
                last_row = self.rowCount() - 1
                y = self.rowViewportPosition(last_row) + self.rowHeight(last_row)
                
            painter.drawLine(0, y, self.viewport().width(), y)

    def dropEvent(self, event):
        self.drop_target_row = None
        self.viewport().update()

        if event.mimeData().hasFormat("application/x-character-row"):
            event.acceptProposedAction()
            mime_text = event.mimeData().text()
            if mime_text:
                try:
                    char_info = json.loads(mime_text)
                    char_name = char_info.get("name", "")
                    if char_name:
                        row = self.rowAt(event.pos().y())
                        
                        if row == -1:
                            mw = self.window()
                            if hasattr(mw, 'insert_script_row_at'):
                                mw.insert_script_row_at(-1)
                                row = self.rowCount() - 1
                                
                        if 0 <= row < self.rowCount():
                            self.save_state_for_undo()
                            combo = self.cellWidget(row, 0)
                            if isinstance(combo, QComboBox):
                                combo.setCurrentText(char_name)
                            else:
                                item = self.item(row, 0)
                                if item:
                                    item.setText(char_name)
                            
                            mw = self.window()
                            if hasattr(mw, 'save_script_data'):
                                mw.save_script_data()
                except Exception as e:
                    print("Error dropping character:", e)
            return

        if event.source() != self or not (event.dropAction() & (Qt.MoveAction | Qt.CopyAction)):
            return

        self.save_state_for_undo()

        target_row = self.rowAt(event.pos().y())
        if target_row == -1: target_row = self.rowCount()
        
        selected_rows = sorted(list(set(index.row() for index in self.selectedIndexes())), reverse=True)
        if not selected_rows: return
        
        rows_data = []
        for r in sorted(selected_rows):
            row_content = []
            for c in range(self.columnCount()):
                item = self.item(r, c)
                text = item.text() if item else ""
                
                combo_text = ""
                if c == 0:
                    widget = self.cellWidget(r, c)
                    if isinstance(widget, QComboBox):
                        combo_text = widget.currentText()
                
                row_content.append({"text": text, "combo": combo_text})
            rows_data.append(row_content)
            
        for r in selected_rows:
            if r < target_row:
                target_row -= 1
            self.removeRow(r)
            
        for i, row_content in enumerate(rows_data):
            new_r = target_row + i
            self.insertRow(new_r)
            for c, data in enumerate(row_content):
                new_item = QTableWidgetItem(data["text"])
                self.setItem(new_r, c, new_item)
                
                if c == 0:
                    mw = self.window()
                    char_names = []
                    if hasattr(mw, 'get_character_list'):
                        char_names = mw.get_character_list()
                    
                    if hasattr(mw, 'create_table_combo'):
                        combo = mw.create_table_combo(char_names, data["combo"])
                        self.setCellWidget(new_r, c, combo)
        
        mw = self.window()
        if hasattr(mw, 'save_script_data'):
            mw.save_script_data()

        self.selectRow(target_row)
        self.setFocus()
        
        event.setDropAction(Qt.IgnoreAction)
        event.accept()
        
        self.save_state_for_undo()

    def keyPressEvent(self, event):
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
            self.save_state_for_undo()
            self.paste_selection()
            return
        if event.key() in (Qt.Key_Delete, Qt.Key_Backspace):
            self.save_state_for_undo()
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
        for item in self.selectedItems():
            item.setText("")
        for index in self.selectedIndexes():
            if index.column() == 0:
                widget = self.cellWidget(index.row(), 0)
                if isinstance(widget, QComboBox):
                    widget.setCurrentIndex(-1)
        
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

# =================================================================
# 선택적 취소를 위한 플로팅 버튼
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
