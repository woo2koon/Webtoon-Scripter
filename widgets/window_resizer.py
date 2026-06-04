# widgets/window_resizer.py
from PySide6.QtCore import Qt, QObject, QPoint, QRect, QEvent
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QWidget

class FramelessWindowResizer(QObject):
    """
    프레임리스 창(Frameless Window)의 8방향 테두리 크기 조절(Resize) 및 
    커스텀 타이틀바 영역을 통한 창 이동(Move)을 처리하는 공통 이벤트 필터 클래스.
    """
    def __init__(self, window, titlebar_widget=None, edge_width=6):
        super().__init__(window)
        self.window = window
        self.titlebar_widget = titlebar_widget
        self.edge_width = edge_width
        
        self.is_resizing = False
        self.is_moving = False
        self.drag_start_pos = QPoint()
        self.window_start_geometry = QRect()
        self.resize_direction = None # 'L', 'R', 'T', 'B', 'TL', 'TR', 'BL', 'BR'
        
        # 마우스 트래킹 활성화
        self.window.setMouseTracking(True)
        if self.titlebar_widget:
            self.titlebar_widget.setMouseTracking(True)
            self.titlebar_widget.installEventFilter(self)
            
        self.window.installEventFilter(self)
    def _install_filter_on_children(self):
        from PySide6.QtWidgets import QWidget
        for child in self.window.findChildren(QWidget):
            child.installEventFilter(self)
            child.setMouseTracking(True)

    def eventFilter(self, obj, event):
        # 1. 타이틀바 드래그를 통한 창 이동 처리 (크기 조절 중이 아닐 때만 작동)
        if not self.is_resizing and self.titlebar_widget:
            is_titlebar_event = (obj == self.titlebar_widget) or (hasattr(self.titlebar_widget, 'isAncestorOf') and self.titlebar_widget.isAncestorOf(obj))
            
            if event.type() == QEvent.MouseButtonPress:
                if event.button() == Qt.LeftButton and is_titlebar_event:
                    # 대화형 위젯(예: 버튼) 클릭 시에는 드래그 이동을 방지
                    from PySide6.QtWidgets import QAbstractButton
                    curr = obj
                    is_button = False
                    while curr and curr != self.titlebar_widget:
                        if isinstance(curr, QAbstractButton):
                            is_button = True
                            break
                        curr = curr.parent()
                    
                    if not is_button:
                        self.is_moving = True
                        self.drag_start_pos = event.globalPosition().toPoint() - self.window.pos()
                        event.accept()
                        return True
            elif event.type() == QEvent.MouseButtonRelease:
                if event.button() == Qt.LeftButton and self.is_moving:
                    self.is_moving = False
                    event.accept()
                    return True
            elif event.type() == QEvent.MouseMove:
                if self.is_moving:
                    new_pos = event.globalPosition().toPoint() - self.drag_start_pos
                    
                    parent = self.window.parent()
                    is_sticky = getattr(self.window, 'is_sticky', False)
                    if is_sticky and parent and hasattr(parent, 'frameGeometry'):
                        # 메인 창의 실제 시각적 영역(DWM 확장 프레임 경계 고려) 가져오기
                        p_rect = None
                        import sys
                        if sys.platform == "win32":
                            try:
                                import ctypes
                                from ctypes import wintypes
                                dwmapi = ctypes.WinDLL("dwmapi")
                                DWMWA_EXTENDED_FRAME_BOUNDS = 9
                                rect = wintypes.RECT()
                                hwnd = int(parent.winId())
                                result = dwmapi.DwmGetWindowAttribute(
                                    hwnd,
                                    DWMWA_EXTENDED_FRAME_BOUNDS,
                                    ctypes.byref(rect),
                                    ctypes.sizeof(rect)
                                )
                                if result == 0:
                                    p_rect = QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
                            except Exception:
                                pass
                        
                        if p_rect is None:
                            parent_geo = parent.frameGeometry()
                            margin_l = 8 if sys.platform == "win32" else 0
                            margin_r = 8 if sys.platform == "win32" else 0
                            margin_b = 8 if sys.platform == "win32" else 0
                            margin_t = 0
                            p_rect = QRect(
                                parent_geo.left() + margin_l,
                                parent_geo.top() + margin_t,
                                parent_geo.width() - margin_l - margin_r,
                                parent_geo.height() - margin_t - margin_b
                            )
                        
                        p_left = p_rect.left()
                        p_right = p_rect.x() + p_rect.width() - 1
                        p_top = p_rect.top()
                        p_bottom = p_rect.y() + p_rect.height() - 1
                        
                        w = self.window.width()
                        h = self.window.height()
                        SNAP_THRESHOLD = 12
                        
                        # 1. 가로 방향(X) 스냅 처리
                        # (A) 도우미 창의 왼쪽 테두리(v_left = x + 6)가 메인 창의 오른쪽 테두리(p_right + 1)에 밀착 스냅
                        if abs((new_pos.x() + 6) - (p_right + 1)) < SNAP_THRESHOLD:
                            new_pos.setX(p_right - 5)
                        # (B) 도우미 창의 오른쪽 테두리(v_right = x + w - 7)가 메인 창의 왼쪽 테두리(p_left - 1)에 밀착 스냅
                        elif abs((new_pos.x() + w - 7) - (p_left - 1)) < SNAP_THRESHOLD:
                            new_pos.setX(p_left - w + 6)
                        # (C) 도우미 창의 왼쪽 테두리가 메인 창의 왼쪽 테두리와 수직 일치 스냅
                        elif abs((new_pos.x() + 6) - p_left) < SNAP_THRESHOLD:
                            new_pos.setX(p_left - 6)
                        # (D) 도우미 창의 오른쪽 테두리가 메인 창의 오른쪽 테두리와 수직 일치 스냅
                        elif abs((new_pos.x() + w - 7) - p_right) < SNAP_THRESHOLD:
                            new_pos.setX(p_right - w + 7)
                            
                        # 2. 세로 방향(Y) 스냅 처리
                        # (A) 도우미 창의 위쪽 테두리(v_top = y + 6)가 메인 창의 아래쪽 테두리(p_bottom + 1)에 밀착 스냅
                        if abs((new_pos.y() + 6) - (p_bottom + 1)) < SNAP_THRESHOLD:
                            new_pos.setY(p_bottom - 5)
                        # (B) 도우미 창의 아래쪽 테두리(v_bottom = y + h - 7)가 메인 창의 위쪽 테두리(p_top - 1)에 밀착 스냅
                        elif abs((new_pos.y() + h - 7) - (p_top - 1)) < SNAP_THRESHOLD:
                            new_pos.setY(p_top - h + 6)
                        # (C) 도우미 창의 아래쪽 테두리가 메인 창의 아래쪽 테두리와 수평 일치 스냅
                        elif abs((new_pos.y() + h - 7) - p_bottom) < SNAP_THRESHOLD:
                            new_pos.setY(p_bottom - h + 7)
                        # (D) 도우미 창의 위쪽 테두리가 메인 창의 위쪽 테두리와 수평 일치 스냅
                        elif abs((new_pos.y() + 6) - p_top) < SNAP_THRESHOLD:
                            new_pos.setY(p_top - 6)
                            
                    self.window.move(new_pos)
                    event.accept()
                    return True

        # 2. 8방향 테두리 크기 조절 처리 (창 본체 및 자식 위젯 통합 처리)
        # 마우스 호버 시 경계 조절 커서 업데이트 (드래깅 중이 아닐 때)
        if not self.is_resizing:
            if event.type() in (QEvent.MouseMove, QEvent.Enter):
                global_pos = QCursor.pos()
                local_pos = self.window.mapFromGlobal(global_pos)
                direction = self._get_resize_direction(local_pos)
                if direction:
                    self.resize_direction = direction
                    self._update_cursor(direction)
                    if obj != self.window:
                        # 자식 위젯의 기본 커서로 덮어씌워지는 현상을 방지
                        self.window.setCursor(self.window.cursor())
                else:
                    # 크기 조절 영역을 벗어났으면 즉시 커서 복원
                    self.window.unsetCursor()
                    self.resize_direction = None

        # 마우스 클릭: 크기 조절 작동 시작
        if event.type() == QEvent.MouseButtonPress:
            if event.button() == Qt.LeftButton:
                global_pos = QCursor.pos()
                local_pos = self.window.mapFromGlobal(global_pos)
                direction = self._get_resize_direction(local_pos)
                if direction:
                    self.is_resizing = True
                    self.resize_direction = direction
                    self.drag_start_pos = event.globalPosition().toPoint()
                    self.window_start_geometry = self.window.geometry()
                    event.accept()
                    return True

        # 마우스 드래그: 크기 변경 계산 수행
        elif event.type() == QEvent.MouseMove:
            if self.is_resizing:
                delta = event.globalPosition().toPoint() - self.drag_start_pos
                new_geo = QRect(self.window_start_geometry)
                
                min_w = self.window.minimumWidth() or 100
                min_h = self.window.minimumHeight() or 100
                max_w = self.window.maximumWidth() or 16777215
                max_h = self.window.maximumHeight() or 16777215
                
                if 'R' in self.resize_direction:
                    w = max(min_w, min(max_w, self.window_start_geometry.width() + delta.x()))
                    new_geo.setWidth(w)
                if 'L' in self.resize_direction:
                    w = max(min_w, min(max_w, self.window_start_geometry.width() - delta.x()))
                    new_geo.setX(self.window_start_geometry.right() - w + 1)
                if 'B' in self.resize_direction:
                    h = max(min_h, min(max_h, self.window_start_geometry.height() + delta.y()))
                    new_geo.setHeight(h)
                if 'T' in self.resize_direction:
                    h = max(min_h, min(max_h, self.window_start_geometry.height() - delta.y()))
                    new_geo.setY(self.window_start_geometry.bottom() - h + 1)
                    
                parent = self.window.parent()
                is_sticky = getattr(self.window, 'is_sticky', False)
                if is_sticky and parent and hasattr(parent, 'frameGeometry'):
                    # 메인 창의 실제 시각적 영역(DWM 확장 프레임 경계 고려) 가져오기
                    p_rect = None
                    import sys
                    if sys.platform == "win32":
                        try:
                            import ctypes
                            from ctypes import wintypes
                            dwmapi = ctypes.WinDLL("dwmapi")
                            DWMWA_EXTENDED_FRAME_BOUNDS = 9
                            rect = wintypes.RECT()
                            hwnd = int(parent.winId())
                            result = dwmapi.DwmGetWindowAttribute(
                                hwnd,
                                DWMWA_EXTENDED_FRAME_BOUNDS,
                                ctypes.byref(rect),
                                ctypes.sizeof(rect)
                            )
                            if result == 0:
                                p_rect = QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
                        except Exception:
                            pass
                    
                    if p_rect is None:
                        parent_geo = parent.frameGeometry()
                        margin_l = 8 if sys.platform == "win32" else 0
                        margin_r = 8 if sys.platform == "win32" else 0
                        margin_b = 8 if sys.platform == "win32" else 0
                        margin_t = 0
                        p_rect = QRect(
                            parent_geo.left() + margin_l,
                            parent_geo.top() + margin_t,
                            parent_geo.width() - margin_l - margin_r,
                            parent_geo.height() - margin_t - margin_b
                        )
                    
                    p_left = p_rect.left()
                    p_right = p_rect.x() + p_rect.width() - 1
                    p_top = p_rect.top()
                    p_bottom = p_rect.y() + p_rect.height() - 1
                    
                    # 1. 오른쪽 변 (R) 조절 시 스냅 및 클램핑
                    if 'R' in self.resize_direction:
                        # (A) 메인 창의 왼쪽에 도우미 창이 있었던 경우 -> 메인 창 왼쪽 경계에 딱 밀착 및 차단
                        if self.window_start_geometry.right() - 6 <= p_left:
                            target_right = p_left - 1
                            current_v_right = new_geo.left() + new_geo.width() - 7
                            if current_v_right >= target_right - 10:
                                w = target_right + 7 - new_geo.left()
                                if min_w <= w <= max_w:
                                    new_geo.setWidth(w)
                        # (B) 메인 창의 오른쪽에 있고 메인 창의 오른쪽 경계와 라인을 수직 정렬하는 경우
                        else:
                            target_right = p_right
                            current_v_right = new_geo.left() + new_geo.width() - 7
                            if abs(current_v_right - target_right) < 10:
                                w = target_right + 7 - new_geo.left()
                                if min_w <= w <= max_w:
                                    new_geo.setWidth(w)
                                    
                    # 2. 왼쪽 변 (L) 조절 시 스냅 및 클램핑
                    if 'L' in self.resize_direction:
                        # (A) 메인 창의 오른쪽에 도우미 창이 있었던 경우 -> 메인 창 오른쪽 경계에 딱 밀착 및 차단
                        if self.window_start_geometry.left() + 6 >= p_right:
                            target_left = p_right + 1
                            current_v_left = new_geo.left() + 6
                            if current_v_left <= target_left + 10:
                                new_left = target_left - 6
                                w = self.window_start_geometry.right() - new_left + 1
                                if min_w <= w <= max_w:
                                    new_geo.setX(new_left)
                                    new_geo.setWidth(w)
                        # (B) 메인 창의 왼쪽에 있고 메인 창의 왼쪽 경계와 라인을 수직 정렬하는 경우
                        else:
                            target_left = p_left
                            current_v_left = new_geo.left() + 6
                            if abs(current_v_left - target_left) < 10:
                                new_left = target_left - 6
                                w = self.window_start_geometry.right() - new_left + 1
                                if min_w <= w <= max_w:
                                    new_geo.setX(new_left)
                                    new_geo.setWidth(w)
                                    
                    # 3. 아래쪽 변 (B) 조절 시 스냅 및 클램핑
                    if 'B' in self.resize_direction:
                        # (A) 메인 창의 위에 도우미 창이 있었던 경우 -> 메인 창 위쪽 경계에 딱 밀착 및 차단
                        if self.window_start_geometry.bottom() - 6 <= p_top:
                            target_bottom = p_top - 1
                            current_v_bottom = new_geo.top() + new_geo.height() - 7
                            if current_v_bottom >= target_bottom - 10:
                                h = target_bottom + 7 - new_geo.top()
                                if min_h <= h <= max_h:
                                    new_geo.setHeight(h)
                        # (B) 메인 창의 아래(혹은 수평)에 있고 메인 창의 아래 경계와 라인을 수평 정렬하는 경우
                        else:
                            target_bottom = p_bottom
                            current_v_bottom = new_geo.top() + new_geo.height() - 7
                            if abs(current_v_bottom - target_bottom) < 10:
                                h = target_bottom + 7 - new_geo.top()
                                if min_h <= h <= max_h:
                                    new_geo.setHeight(h)
                                    
                    # 4. 위쪽 변 (T) 조절 시 스냅 및 클램핑
                    if 'T' in self.resize_direction:
                        # (A) 메인 창의 아래에 도우미 창이 있었던 경우 -> 메인 창 아래쪽 경계에 딱 밀착 및 차단
                        if self.window_start_geometry.top() + 6 >= p_bottom:
                            target_top = p_bottom + 1
                            current_v_top = new_geo.top() + 6
                            if current_v_top <= target_top + 10:
                                new_top = target_top - 6
                                h = self.window_start_geometry.bottom() - new_top + 1
                                if min_h <= h <= max_h:
                                    new_geo.setY(new_top)
                                    new_geo.setHeight(h)
                        # (B) 메인 창의 위(혹은 수평)에 있고 메인 창의 위쪽 경계와 라인을 수평 정렬하는 경우
                        else:
                            target_top = p_top
                            current_v_top = new_geo.top() + 6
                            if abs(current_v_top - target_top) < 10:
                                new_top = target_top - 6
                                h = self.window_start_geometry.bottom() - new_top + 1
                                if min_h <= h <= max_h:
                                    new_geo.setY(new_top)
                                    new_geo.setHeight(h)
                                
                self.window.setGeometry(new_geo)
                event.accept()
                return True

        # 마우스 뗌: 크기 조절 완료
        elif event.type() == QEvent.MouseButtonRelease:
            if event.button() == Qt.LeftButton:
                if self.is_resizing:
                    self.is_resizing = False
                    self.resize_direction = None
                    self.window.unsetCursor()
                    event.accept()
                    return True

        elif event.type() == QEvent.Leave:
            if obj == self.window and not self.is_resizing:
                self.window.unsetCursor()
                self.resize_direction = None

        return super().eventFilter(obj, event)

    def _get_resize_direction(self, pos):
        """마우스 로컬 좌표를 기반으로 8방향 조절 영역 판단"""
        w = self.window.width()
        h = self.window.height()
        ew = self.edge_width
        cw = 15 # 모서리 판정 영역을 15px로 확장하여 감도를 높임
        
        x = pos.x()
        y = pos.y()
        
        # 1. 4개 모서리(Corner) 판정 우선
        top_corner = y < cw
        bottom_corner = y > (h - cw)
        left_corner = x < cw
        right_corner = x > (w - cw)
        
        if top_corner and left_corner:
            return "TL"
        if top_corner and right_corner:
            return "TR"
        if bottom_corner and left_corner:
            return "BL"
        if bottom_corner and right_corner:
            return "BR"
            
        # 2. 모서리가 아니면 일반 4개 변(Edge) 판정 (ew=6px)
        left = x < ew
        right = x > (w - ew)
        top = y < ew
        bottom = y > (h - ew)
        
        if top: return "T"
        if bottom: return "B"
        if left: return "L"
        if right: return "R"
        
        return None

    def _update_cursor(self, direction):
        """방향에 적합한 커서 모양 적용"""
        if not direction:
            self.window.unsetCursor()
            return
            
        if direction in ("TL", "BR"):
            self.window.setCursor(Qt.SizeFDiagCursor)
        elif direction in ("TR", "BL"):
            self.window.setCursor(Qt.SizeBDiagCursor)
        elif direction in ("T", "B"):
            self.window.setCursor(Qt.SizeVerCursor)
        elif direction in ("L", "R"):
            self.window.setCursor(Qt.SizeHorCursor)
