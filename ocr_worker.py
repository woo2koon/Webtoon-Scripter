import os
import io
import time
import json
import base64
import hashlib
import requests
import concurrent.futures
from PIL import Image, ImageOps, ImageEnhance
from PySide6.QtCore import QThread, Signal
import config
from config import CACHE_DIR
from utils import clean_korean_text 

def preprocess_image_for_ocr(pil_img):
    """OCR 인식률 극대화를 위한 Pillow 기반 고성능 전처리 파이프라인 (2배 업스케일링 포함)"""
    try:
        w, h = pil_img.size
        # 1. 2배 업스케일링
        processed = pil_img.resize((w * 2, h * 2), Image.Resampling.LANCZOS)
        # 2. 그레이스케일 변환
        processed = processed.convert("L")
        # 3. 오토 콘트라스트 (상하위 2% 무시로 아웃라이어 제거)
        processed = ImageOps.autocontrast(processed, cutoff=2)
        # 4. 대비 증폭 (1.8배)
        contrast_enhancer = ImageEnhance.Contrast(processed)
        processed = contrast_enhancer.enhance(1.8)
        # 5. 샤프니스 선명화 (2.0배)
        sharpness_enhancer = ImageEnhance.Sharpness(processed)
        processed = sharpness_enhancer.enhance(2.0)
        return processed
    except Exception as e:
        print(f"이미지 전처리 실패 (원본으로 대체): {e}")
        return pil_img

# [필수] HTTP 연결 재사용을 위한 세션 객체
session = requests.Session()

def call_google_api_raw(png_bytes):
    """구글 비전 API에 직접 이미지 데이터를 보내 텍스트를 추출합니다."""
    try:
        current_key = config.OCR_API_KEY
        if not current_key: return []
            
        image_content = base64.b64encode(png_bytes).decode("utf-8")
        req = {
            "requests": [
                {
                    "image": {"content": image_content},
                    "features": [{"type": "DOCUMENT_TEXT_DETECTION"}],
                    "imageContext": {
                        "languageHints": ["ko"]
                    }
                }
            ]
        }
        
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
                        # 전처리 단계의 2배 업스케일링을 고려하여 좌표값을 다시 1/2로 보정합니다.
                        blocks_found.append({
                            "text": cleaned, 
                            "y": int(min(v.get("y", 0) for v in vs) / 2.0), 
                            "bottom": int(max(v.get("y", 0) for v in vs) / 2.0),
                            "x1": int(min(v.get("x", 0) for v in vs) / 2.0), 
                            "x2": int(max(v.get("x", 0) for v in vs) / 2.0)
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
                        preprocessed = preprocess_image_for_ocr(cropped)
                        buf = io.BytesIO()
                        preprocessed.save(buf, format="PNG")
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

        from functools import cmp_to_key

        # 각 그룹(말풍선)의 전체 바운딩 박스 정보 및 중심점 계산
        group_metadata = []
        for g in groups:
            y1 = min(b['y'] for b in g)
            y2 = max(b['bottom'] for b in g)
            x1 = min(b['x1'] for b in g)
            x2 = max(b['x2'] for b in g)
            group_metadata.append({
                'group': g,
                'y1': y1,
                'y2': y2,
                'x1': x1,
                'x2': x2,
                'yc': (y1 + y2) / 2.0,
                'xc': (x1 + x2) / 2.0,
                'h': y2 - y1
            })

        def compare_metadata(a, b):
            # 두 그룹의 Y축 중심점 간격 차이
            dy = abs(a['yc'] - b['yc'])
            # Y축 오버랩 높이 계산
            overlap_y = min(a['y2'], b['y2']) - max(a['y1'], b['y1'])
            min_h = min(a['h'], b['h'])
            
            # Y축이 상당히 겹치거나 Y축 중심선 차이가 평균 글자 크기 기준값 미만으로 미세한 경우 -> 동일 선상의 대화(좌우 배치)로 간주
            is_horizontal_layout = (dy < avg_height * 1.8) or (min_h > 0 and (overlap_y / min_h) > 0.3)
            
            if is_horizontal_layout:
                # 같은 라인에 있다면 더 왼쪽에 있는(X축 좌표가 작은) 대사가 무조건 먼저 읽힘
                if abs(a['xc'] - b['xc']) > 5:
                    return -1 if a['xc'] < b['xc'] else 1
            
            # 그 외의 세로 배치 관계는 위에서 아래로 순차 배치
            return -1 if a['yc'] < b['yc'] else 1

        # 커스텀 비교 정렬 적용
        group_metadata.sort(key=cmp_to_key(compare_metadata))
        sorted_groups = [m['group'] for m in group_metadata]

        final_merged = []
        for group in sorted_groups:
            # 같은 말풍선 안에서도 비슷한 높이면 왼쪽부터 합치도록 미세 조정
            group.sort(key=lambda b: (int(b['y'] // (avg_height * 0.5)), b['x1']))
            merged_text = " ".join(b['text'] for b in group)
            final_merged.append(merged_text)

        return final_merged

    def stop(self):
        self.is_running = False