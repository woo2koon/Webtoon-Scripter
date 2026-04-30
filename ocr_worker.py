import os
import io
import time
import json
import base64
import hashlib
import requests
import concurrent.futures
from PIL import Image
from PySide6.QtCore import QThread, Signal
import config
from config import CACHE_DIR
from utils import clean_korean_text 

# [필수] HTTP 연결 재사용을 위한 세션 객체
session = requests.Session()

def call_google_api_raw(png_bytes):
    """구글 비전 API에 직접 이미지 데이터를 보내 텍스트를 추출합니다."""
    try:
        current_key = config.OCR_API_KEY
        if not current_key: return []
            
        image_content = base64.b64encode(png_bytes).decode("utf-8")
        req = {"requests": [{"image": {"content": image_content}, "features": [{"type": "DOCUMENT_TEXT_DETECTION"}]}]}
        
        # 연결 풀링을 사용해 구글 서버와 더 빠르게 통신
        res = session.post(f"https://vision.googleapis.com/v1/images:annotate?key={current_key}", json=req, timeout=15)
        
        if res.status_code != 200: return []
        
        blocks_found = []
        result = res.json()
        responses = result.get("responses", [])

        if responses and "fullTextAnnotation" in responses[0]:
            for page in responses[0]["fullTextAnnotation"]["pages"]:
                for block in page["blocks"]:
                    block_text = ""
                    for p in block["paragraphs"]:
                        for w in p["words"]:
                            for s in w["symbols"]:
                                block_text += s["text"]
                                if "property" in s and "detectedBreak" in s["property"]:
                                    break_type = s["property"]["detectedBreak"]["type"]
                                    if break_type in ["SPACE", "SURE_SPACE", "EOL_SURE_SPACE", "LINE_BREAK"]:
                                        block_text += " "
                    
                    cleaned = clean_korean_text(block_text)
                    vs = block["boundingBox"]["vertices"]
                    if cleaned:
                        blocks_found.append({
                            "text": cleaned, 
                            "y": min(v.get("y", 0) for v in vs), 
                            "bottom": max(v.get("y", 0) for v in vs),
                            "x1": min(v.get("x", 0) for v in vs), 
                            "x2": max(v.get("x", 0) for v in vs)
                        })
        return blocks_found
    except Exception as e:
        print(f"API Error: {e}")
        return []

def get_ocr_data_smart(cache_key, png_bytes, force=False):
    """[수정됨] 누락되었던 캐싱 및 API 호출 제어 함수"""
    cache_path = os.path.join(CACHE_DIR, cache_key + ".json")
    if force or not os.path.exists(cache_path):
        data = call_google_api_raw(png_bytes)
        if data:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        return data, True 
    with open(cache_path, "r", encoding="utf-8") as f:
        return json.load(f), False

class OCRWorker(QThread):
    progress_val = Signal(int)
    progress_text = Signal(str)
    finished_ocr = Signal(list)
    api_used = Signal()

    def __init__(self, image_paths, mode="fast", force_mode=False):
        super().__init__()
        self.image_paths = image_paths
        self.mode = mode # "fast" 또는 "smart"
        self.force_mode = force_mode
        self.is_running = True
        self.MERGE_THRESHOLD = 80 
        self.MAX_SLICE_HEIGHT = 2450 

    def find_panel_gap(self, img, start_y, max_h):
        """[스마트 모드] 컷 사이의 흰색 여백을 찾아 절단 지점 반환"""
        w, h = img.size
        target_y = min(start_y + max_h, h)
        if target_y == h: return h

        search_limit = max(start_y + (max_h // 2), target_y - 800)
        for y in range(target_y, search_limit, -5):
            line = img.crop((0, y, w, y + 1)).convert("L")
            extrema = line.getextrema()
            if extrema == (255, 255):
                return y
        return target_y

    def run(self):
        full_results = []
        total_files = len(self.image_paths)
        global_counter = 1
        cumulative_height_offset = 0 
        
        for idx, img_path in enumerate(self.image_paths):
            if not self.is_running: break
            filename = os.path.basename(img_path)
            
            try:
                with Image.open(img_path) as img:
                    w, h = img.size
                    current_y = 0
                    slice_idx = 0
                    tasks = []

                    while current_y < h:
                        if self.mode == "smart":
                            self.progress_text.emit(f"🔍 [{filename}] 컷 경계 분석 중...")
                            cut_y = self.find_panel_gap(img, current_y, self.MAX_SLICE_HEIGHT)
                        else:
                            cut_y = min(current_y + self.MAX_SLICE_HEIGHT, h)
                        
                        cropped = img.crop((0, current_y, w, cut_y))
                        buf = io.BytesIO()
                        cropped.save(buf, format="PNG")
                        png_bytes = buf.getvalue()
                        
                        tasks.append({
                            "bytes": png_bytes,
                            "offset": cumulative_height_offset + current_y,
                            "key": f"{hashlib.md5(png_bytes).hexdigest()}_slice_{slice_idx}"
                        })
                        current_y = cut_y
                        slice_idx += 1

                    self.progress_text.emit(f"🚀 [{filename}] {self.mode.upper()} 병렬 분석 중...")
                    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                        future_to_task = {executor.submit(get_ocr_data_smart, t["key"], t["bytes"], self.force_mode): t for t in tasks}
                        for future in concurrent.futures.as_completed(future_to_task):
                            task = future_to_task[future]
                            blocks, is_api_called = future.result()
                            if is_api_called: self.api_used.emit()
                            for b in blocks:
                                b_copy = b.copy()
                                b_copy['y'] += task["offset"]
                                b_copy['bottom'] += task["offset"]
                                full_results.append(b_copy)
                    
                    cumulative_height_offset += h + 50
            except Exception as e:
                print(f"OCR Error: {e}")
                
            self.progress_val.emit(int((idx + 1) / total_files * 90))

        # [수정] 무조건적인 Y축 정렬 제거 및 그룹화 로직으로 바로 전달
        self.progress_text.emit("📝 말풍선 그룹화 및 대사 복원 중...")
        merged_lines = self.merge_close_blocks(full_results)
        final_lines = [f"[{global_counter + i}] {line}" for i, line in enumerate(merged_lines)]
        
        self.progress_val.emit(100)
        self.finished_ocr.emit(final_lines)

    def merge_close_blocks(self, results):
        if not results: return []

        valid_results = [b for b in results if b['bottom'] > b['y']]
        if not valid_results: return [b['text'] for b in results]
            
        avg_height = sum(b['bottom'] - b['y'] for b in valid_results) / len(valid_results)
        
        # 임계값 설정
        Y_THRESH = avg_height * 1.5
        X_STRICT = avg_height * 0.8
        X_LOOSE = avg_height * 2.0

        groups = []

        for block in results:
            matched_groups = []
            for i, group in enumerate(groups):
                for g_block in group:
                    dx = max(0, max(block['x1'], g_block['x1']) - min(block['x2'], g_block['x2']))
                    dy = max(0, max(block['y'], g_block['y']) - min(block['bottom'], g_block['bottom']))
                    overlap_x = min(block['x2'], g_block['x2']) - max(block['x1'], g_block['x1'])
                    
                    # 매칭 조건 (수직 우선)
                    is_match = False
                    if overlap_x > 0 and dy < Y_THRESH:
                        is_match = True
                    elif dx < X_STRICT and dy < (avg_height * 0.5):
                        is_match = True

                    if is_match:
                        if i not in matched_groups: matched_groups.append(i)
                        break

            if not matched_groups:
                groups.append([block])
            else:
                # [수정 완료] 변수 이름을 first_idx로 통일했습니다.
                first_idx = matched_groups[0]
                groups[first_idx].append(block)
                for other_idx in reversed(matched_groups[1:]):
                    groups[first_idx].extend(groups[other_idx])
                    del groups[other_idx]

        # 그룹 정렬 및 텍스트 합치기
        groups.sort(key=lambda g: min(b['y'] for b in g) + (min(b['x1'] for b in g) * 0.5))

        final_merged = []
        for group in groups:
            # 같은 말풍선 안에서도 비슷한 높이면 왼쪽부터 합치도록 미세 조정
            group.sort(key=lambda b: (int(b['y'] // (avg_height * 0.5)), b['x1']))
            merged_text = " ".join(b['text'] for b in group)
            final_merged.append(merged_text)

        return final_merged

    def stop(self):
        self.is_running = False