import sys
import os
from PySide6.QtWidgets import (
    QWidget, QHBoxLayout, QLineEdit, QLabel, QPushButton, QFrame, QApplication, QSizePolicy, QComboBox
)
from PySide6.QtCore import Qt, Signal, QEvent, QSize
from PySide6.QtGui import QColor, QFont, QKeySequence, QTextCursor, QBrush, QIcon, QPixmap
from PySide6.QtWidgets import QTextEdit, QTableWidget, QAbstractItemView

import config
from utils import get_colored_pixmap

class SearchWidget(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.text_edit = None
        self.table_widget = None
        
        self.matches = []
        self.current_match_idx = -1
        self.original_cell_brushes = {}
        
        self.init_ui()
        self.hide()
        
    def init_ui(self):
        self.setObjectName("SearchWidget")
        self.setStyleSheet("""
            QFrame#SearchWidget {
                background-color: #FFFFFF;
                border: 1px solid #DADCE0;
                border-radius: 8px;
            }
        """)
        
        # Drop shadow effect
        from PySide6.QtWidgets import QGraphicsDropShadowEffect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QColor(0, 0, 0, 25))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignVCenter)
        
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("문서에서 검색")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedWidth(160)
        self.search_input.setFixedHeight(30)
        self.search_input.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #DADCE0;
                border-radius: 4px;
                padding: 0px 8px;
                font-size: 13px;
                color: #3C4043;
                background-color: #FFFFFF;
                font-family: 'Pretendard', -apple-system, sans-serif;
                height: 30px;
                min-height: 30px;
                max-height: 30px;
            }
            QLineEdit:focus {
                border: 2px solid #FF5722;
            }
        """)
        
        self.search_input.textChanged.connect(self.on_text_changed)
        self.search_input.returnPressed.connect(self.find_next)
        layout.addWidget(self.search_input, alignment=Qt.AlignVCenter)
        
        self.lbl_status = QLabel("0/0")
        self.lbl_status.setFixedWidth(40)
        self.lbl_status.setFixedHeight(24)
        self.lbl_status.setStyleSheet("""
            QLabel {
                font-size: 11px;
                color: #70757A;
                font-family: 'Pretendard', sans-serif;
                padding: 0;
            }
        """)
        self.lbl_status.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.lbl_status, alignment=Qt.AlignVCenter)
        
        btn_style = """
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #F1F3F4;
            }
            QPushButton:pressed {
                background-color: #E8EAED;
            }
        """
        
        self.btn_prev = QPushButton()
        self.btn_prev.setStyleSheet(btn_style)
        self.btn_prev.setCursor(Qt.PointingHandCursor)
        
        icon_prev = QIcon()
        icon_prev.addPixmap(get_colored_pixmap(os.path.join(config.ASSETS_DIR, "chevron-up.svg"), "#5F6368", 16, 16), QIcon.Normal, QIcon.Off)
        icon_prev.addPixmap(get_colored_pixmap(os.path.join(config.ASSETS_DIR, "chevron-up.svg"), "#FF5722", 16, 16), QIcon.Active, QIcon.Off)
        self.btn_prev.setIcon(icon_prev)
        self.btn_prev.setIconSize(QSize(16, 16))
        
        self.btn_prev.clicked.connect(self.find_prev)
        layout.addWidget(self.btn_prev, alignment=Qt.AlignVCenter)
        
        self.btn_next = QPushButton()
        self.btn_next.setStyleSheet(btn_style)
        self.btn_next.setCursor(Qt.PointingHandCursor)
        
        icon_next = QIcon()
        icon_next.addPixmap(get_colored_pixmap(os.path.join(config.ASSETS_DIR, "chevron-down.svg"), "#5F6368", 16, 16), QIcon.Normal, QIcon.Off)
        icon_next.addPixmap(get_colored_pixmap(os.path.join(config.ASSETS_DIR, "chevron-down.svg"), "#FF5722", 16, 16), QIcon.Active, QIcon.Off)
        self.btn_next.setIcon(icon_next)
        self.btn_next.setIconSize(QSize(16, 16))
        
        self.btn_next.clicked.connect(self.find_next)
        layout.addWidget(self.btn_next, alignment=Qt.AlignVCenter)
        
        # Vertical divider line
        self.divider = QFrame()
        self.divider.setFrameShape(QFrame.VLine)
        self.divider.setFrameShadow(QFrame.Plain)
        self.divider.setFixedWidth(1)
        self.divider.setFixedHeight(20)
        self.divider.setStyleSheet("background-color: #DADCE0; border: none;")
        layout.addWidget(self.divider, alignment=Qt.AlignVCenter)
        
        self.btn_close = QPushButton()
        self.btn_close.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
                border-radius: 4px;
                min-width: 26px;
                max-width: 26px;
                min-height: 26px;
                max-height: 26px;
                padding: 0;
            }
            QPushButton:hover {
                background-color: #FEE2E2;
            }
            QPushButton:pressed {
                background-color: #FCA5A5;
            }
        """)
        self.btn_close.setCursor(Qt.PointingHandCursor)
        
        icon_close = QIcon()
        icon_close.addPixmap(get_colored_pixmap(os.path.join(config.ASSETS_DIR, "close.svg"), "#5F6368", 13, 13), QIcon.Normal, QIcon.Off)
        icon_close.addPixmap(get_colored_pixmap(os.path.join(config.ASSETS_DIR, "close.svg"), "#D93025", 13, 13), QIcon.Active, QIcon.Off)
        self.btn_close.setIcon(icon_close)
        self.btn_close.setIconSize(QSize(13, 13))
        
        self.btn_close.clicked.connect(self.hide_search)
        layout.addWidget(self.btn_close, alignment=Qt.AlignVCenter)
        
        self.setFixedSize(360, 56)
        
    def set_text_edit_target(self, text_edit):
        self.text_edit = text_edit
        self.table_widget = None
        self.setParent(text_edit)
        text_edit.search_widget = self
        text_edit.installEventFilter(self)
        self.reposition()
        
    def set_table_target(self, table_widget):
        self.table_widget = table_widget
        self.text_edit = None
        self.setParent(table_widget)
        table_widget.search_widget = self
        table_widget.installEventFilter(self)
        self.reposition()

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Resize:
            self.reposition()
        return super().eventFilter(obj, event)

    def reposition(self):
        target = self.text_edit or self.table_widget
        if target and self.isVisible():
            y_offset = 10
            if self.table_widget:
                y_offset = self.table_widget.horizontalHeader().height() + 10
            
            self.move(
                target.width() - self.width() - 13,
                y_offset
            )

    def show_search(self):
        self.show()
        self.reposition()
        self.raise_()
        self.search_input.setFocus()
        self.search_input.selectAll()
        self.on_text_changed()

    def hide_search(self):
        self.hide()
        self.clear_highlights()
        if self.text_edit:
            self.text_edit.setFocus()
        elif self.table_widget:
            self.table_widget.setFocus()

    def clear_highlights(self):
        self.matches.clear()
        self.current_match_idx = -1
        self.lbl_status.setText("0/0")
        
        if self.text_edit:
            self.text_edit.setExtraSelections([])
        elif self.table_widget:
            # Restore regular cells
            for (r, c), original_brush in self.original_cell_brushes.items():
                item = self.table_widget.item(r, c)
                if item:
                    item.setBackground(original_brush)
            self.original_cell_brushes.clear()
            
            # Reset active combobox style
            if hasattr(self, 'last_active_combo') and self.last_active_combo:
                try:
                    style = getattr(self, 'last_active_combo_style', "")
                    self.last_active_combo.setStyleSheet(style)
                except RuntimeError:
                    pass
                self.last_active_combo = None
                self.last_active_combo_style = ""

    def on_text_changed(self):
        self.clear_highlights()
        query = self.search_input.text().strip()
        if not query:
            return
            
        if self.text_edit:
            doc = self.text_edit.document()
            cursor = doc.find(query, 0)
            
            while not cursor.isNull():
                self.matches.append(cursor)
                cursor = doc.find(query, cursor)
                
            if self.matches:
                self.current_match_idx = 0
                self.highlight_text_matches()
                
        elif self.table_widget:
            self.table_widget.blockSignals(True)
            try:
                # Search all cells (Dialogue and Character name from combobox)
                for r in range(self.table_widget.rowCount()):
                    for c in range(self.table_widget.columnCount()):
                        text = ""
                        if c == 0:
                            combo = self.table_widget.cellWidget(r, 0)
                            if combo and isinstance(combo, QComboBox):
                                text = combo.currentText()
                        else:
                            item = self.table_widget.item(r, c)
                            if item:
                                text = item.text()
                                
                        if text and query.lower() in text.lower():
                            self.matches.append((r, c))
                            
                if self.matches:
                    self.current_match_idx = 0
                    self.highlight_table_matches(activate=False)
            finally:
                self.table_widget.blockSignals(False)

    def highlight_text_matches(self):
        if not self.text_edit or not self.matches:
            return
            
        selections = []
        for idx, cursor in enumerate(self.matches):
            selection = QTextEdit.ExtraSelection()
            if idx == self.current_match_idx:
                selection.format.setBackground(QColor("#FF9100")) # Active match: Orange
                selection.format.setForeground(Qt.white)
                
                # Center cursor in viewport without showing active gray selection override
                scroll_cursor = QTextCursor(cursor)
                scroll_cursor.clearSelection()
                self.text_edit.setTextCursor(scroll_cursor)
            else:
                selection.format.setBackground(QColor("#FFE082")) # Regular match: Gold
                selection.format.setForeground(Qt.black)
            selection.cursor = cursor
            selections.append(selection)
            
        self.text_edit.setExtraSelections(selections)
        self.lbl_status.setText(f"{self.current_match_idx + 1} / {len(self.matches)}")

    def highlight_table_matches(self, activate=False):
        if not self.table_widget or not self.matches:
            return
            
        print(f"[DEBUG] highlight_table_matches called. Matches: {self.matches}, Current Match Index: {self.current_match_idx}, Activate: {activate}")
            
        # First save original backgrounds of newly found matches
        for r, c in self.matches:
            item = self.table_widget.item(r, c)
            if item and (r, c) not in self.original_cell_brushes:
                self.original_cell_brushes[(r, c)] = item.background()
                
        # Highlight all matched cells (both columns) with regular match color (Gold)
        for r, c in self.matches:
            item = self.table_widget.item(r, c)
            if item:
                item.setBackground(QBrush(QColor("#FFE082")))

        # Reset any previously styled active combobox
        if hasattr(self, 'last_active_combo') and self.last_active_combo:
            try:
                style = getattr(self, 'last_active_combo_style', "")
                self.last_active_combo.setStyleSheet(style)
            except RuntimeError:
                pass
            self.last_active_combo = None
            self.last_active_combo_style = ""

        # Apply active match styling & focus
        if 0 <= self.current_match_idx < len(self.matches):
            r, c = self.matches[self.current_match_idx]
            
            # Highlight active cell item background to Orange
            item = self.table_widget.item(r, c)
            if item:
                item.setBackground(QBrush(QColor("#FF9100"))) # Active match: Orange
                
            if c == 0:
                combo = self.table_widget.cellWidget(r, 0)
                if combo and isinstance(combo, QComboBox):
                    self.last_active_combo = combo
                    self.last_active_combo_style = combo.styleSheet()
                    
                    # Style active combobox with orange border, keeping transparent bg so the cell's orange background shows!
                    # Append active border style to existing stylesheet rules
                    combo.setStyleSheet(self.last_active_combo_style + "\nQComboBox { border: 2px solid #FF9100; border-radius: 4px; background-color: transparent; }")
                    
                    if activate:
                        self.table_widget.setCurrentCell(r, 0)
                        combo.setFocus()
                        # Scroll using the dialogue item in the same row
                        dummy_item = self.table_widget.item(r, 1)
                        if dummy_item:
                            self.table_widget.scrollToItem(dummy_item, QAbstractItemView.PositionAtCenter)
            else:
                if item:
                    if activate:
                        self.table_widget.setCurrentCell(r, c)
                        self.table_widget.scrollToItem(item, QAbstractItemView.PositionAtCenter)
                        
        self.table_widget.viewport().update()
        self.lbl_status.setText(f"{self.current_match_idx + 1} / {len(self.matches)}")

    def find_next(self):
        if not self.matches:
            return
        self.current_match_idx = (self.current_match_idx + 1) % len(self.matches)
        if self.text_edit:
            self.highlight_text_matches()
        elif self.table_widget:
            self.highlight_table_matches(activate=True)

    def find_prev(self):
        if not self.matches:
            return
        self.current_match_idx = (self.current_match_idx - 1 + len(self.matches)) % len(self.matches)
        if self.text_edit:
            self.highlight_text_matches()
        elif self.table_widget:
            self.highlight_table_matches(activate=True)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_search()
            event.accept()
        elif event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() == Qt.ShiftModifier:
                self.find_prev()
            else:
                self.find_next()
            event.accept()
        else:
            super().keyPressEvent(event)
