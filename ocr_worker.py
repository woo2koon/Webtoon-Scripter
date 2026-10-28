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
from utils import clean_korean_text, save_ocr_boxes, load_ocr_boxes

class OCRAPIError(Exception):
    """API 호출 실패 시 사용자에게 원인을 알리기 위한 예외"""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code

def parse_gemini_error_message(status_code, response_text):
    """Gemini API 에러 코드 및 응답을 분석하여 명확하고 친절한 한국어 안내 문구를 반환합니다."""
    error_detail = ""
    try:
        err_json = json.loads(response_text)
        if "error" in err_json:
            error_detail = err_json["error"].get("message", "")
    except Exception:
        error_detail = response_text

    if status_code in (401, 400, 403) or "API key not valid" in error_detail or "API_KEY_INVALID" in error_detail:
        return (
            "🔑 API 키가 유효하지 않습니다.\n\n"
            "입력하신 API 키가 정확하지 않거나 삭제된 키입니다.\n"
            "[설정 열기] 버튼을 눌러 정확한 Google Cloud or AI Studio API 키를 다시 등록해 주세요."
        )
    elif status_code == 402 or "depleted" in error_detail:
        return (
            "💳 API 선불 크레딧이 모두 소진되었습니다.\n\n"
            "Google AI Studio 결제 정책으로 인해 선불 잔액이 $0이면 호출이 차단됩니다.\n"
            "• 해결 방법 1: https://aistudio.google.com/projects 에서 크레딧을 충전하세요.\n"
            "• 해결 방법 2: https://aistudio.google.com/apikey 에서 새 프로젝트로 무료 키를 발급받아 등록하세요."
        )
    elif status_code == 404:
        return (
            "🚫 설정된 Gemini AI 모델을 찾을 수 없거나 사용이 중단되었습니다.\n\n"
            f"• 상세 내용: {error_detail}\n"
            "• 최신 모델로 업데이트가 필요합니다."
        )
    elif status_code == 429:
        return (
            "⏳ API 분당 호출 한도(Rate Limit)를 초과했습니다.\n\n"
            "잠시(약 1~2분) 기다리신 후 다시 시도해 주세요."
        )
    elif status_code >= 500:
        return (
            f"☁️ Google Gemini 서버에 일시적인 장애가 발생했습니다 (HTTP {status_code}).\n\n"
            "잠시 후 다시 시도해 주세요."
        )
    else:
        return f"⚠️ Gemini API 호출 오류 (HTTP {status_code}):\n{error_detail}"

def parse_vision_error_message(status_code, response_text):
    """Google Vision API 에러 분석 문구 반환"""
    error_detail = ""
    try:
        err_json = json.loads(response_text)
        if "error" in err_json:
            error_detail = err_json["error"].get("message", "")
    except Exception:
        error_detail = response_text

    if status_code in (400, 403):
        return (
            "🔑 Google Vision API 키가 유효하지 않거나 비활성화되어 있습니다.\n\n"
            f"• 상세 내용: {error_detail}\n\n"
            "[설정]에서 Google Cloud 콘솔에 Cloud Vision API가 사용 설정되어 있는지 확인해 주세요."
        )
    elif status_code == 429:
        return "⏳ Google Vision API 호출 한도를 초과했습니다. 잠시 후 다시 시도해 주세요."
    else:
        return f"⚠️ Google Vision API 호출 오류 (HTTP {status_code}):\n{error_detail}"

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
    current_key = config.OCR_API_KEY
    if not current_key:
        raise OCRAPIError("Google Vision API 키가 설정되지 않았습니다.\n[설정]에서 API 키를 등록해 주세요.")
        
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
    
    try:
        # 연결 풀링을 사용해 구글 서버와 더 빠르게 통신
        res = session.post(f"https://vision.googleapis.com/v1/images:annotate?key={current_key}", json=req, timeout=20)
    except requests.exceptions.Timeout:
        raise OCRAPIError("Google Vision API 응답 시간이 초과되었습니다.\n인터넷 연결 상태를 확인해 주세요.")
    except Exception as e:
        raise OCRAPIError(f"Google Vision API 네트워크 통신 오류: {e}")
    
    if res.status_code != 200:
        err_msg = parse_vision_error_message(res.status_code, res.text)
        raise OCRAPIError(err_msg, status_code=res.status_code)
    
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

def clean_and_parse_json(text):
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # ```json 이나 ``` 로 시작하는 마크다운 블록 제거
        first_newline = cleaned.find("\n")
        if first_newline != -1:
            cleaned = cleaned[first_newline:].strip()
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return json.loads(cleaned)

def call_gemini_api_raw(png_bytes):
    active_key = config.AI_API_KEY
    if not active_key:
        return []

    system_prompt = """너는 웹툰/만화 컷 이미지 분석 및 대사 추출 전문가야.
제시된 만화 컷 이미지에서 모든 대사 텍스트를 정확하게 추출해줘.

[작업 규칙]
1. 웹툰 컷의 자연스러운 독서 흐름(위에서 아래, 말풍선 흐름)에 맞춰 순서대로 텍스트를 검출해라.
2. 모든 대사(말풍선), 내레이션(설명 박스), 효과음(의성어/의태어 등 배경 글자)을 누락 없이 글자 그대로 추출해라.
3. 절대 임의로 대사를 수정하거나 보정하지 말고, 이미지에 보이는 텍스트를 오타, 사투리, 특수문자를 포함하여 글자 그대로 필사해라.
4. 각 대사의 위치를 나타내는 2D 바운딩 박스 [ymin, xmin, ymax, xmax] (0~1000 정규화 정수)를 box_2d 필드에 포함해라.
5. 결과는 아래 JSON 스키마 구조를 100% 만족시켜라.
"""

    b64_data = base64.b64encode(png_bytes).decode('utf-8')
    parts = [
        {"text": system_prompt},
        {"text": "분석할 만화 컷 이미지:"},
        {
            "inlineData": {
                "mimeType": "image/png",
                "data": b64_data
            }
        }
    ]

    # responseSchema를 강제하여 JSON 문법 및 특수문자 이스케이프 강제 규격화
    schema = {
        "type": "OBJECT",
        "properties": {
            "results": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "index": {"type": "INTEGER"},
                        "text": {"type": "STRING"},
                        "box_2d": {
                            "type": "ARRAY",
                            "items": {"type": "INTEGER"},
                            "description": "Bounding box [ymin, xmin, ymax, xmax] normalized to 0-1000"
                        }
                    },
                    "required": ["index", "text"]
                }
            }
        },
        "required": ["results"]
    }

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": schema,
            "temperature": 0.1,
            "maxOutputTokens": 8192
        }
    }

    model = getattr(config, 'GEMINI_MODEL', 'gemini-3.1-flash-lite')
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={active_key}"
    headers = {"Content-Type": "application/json"}

    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
    except requests.exceptions.Timeout:
        raise OCRAPIError("Google Gemini API 응답 시간이 초과되었습니다.\n인터넷 연결 상태를 확인해 주세요.")
    except Exception as e:
        raise OCRAPIError(f"Google Gemini API 네트워크 통신 오류: {e}")

    if res.status_code == 200:
        try:
            res_data = res.json()
            content_text = res_data['candidates'][0]['content']['parts'][0]['text']
            parsed_json = clean_and_parse_json(content_text)
            results = parsed_json.get("results", [])
            output = []
            for item in results:
                if isinstance(item, dict):
                    txt = item.get("text", "").strip()
                    if txt:
                        b2d = item.get("box_2d")
                        output.append({"text": txt, "box_2d": b2d})
                elif isinstance(item, str) and item.strip():
                    output.append({"text": item.strip(), "box_2d": None})
            return output
        except Exception as e:
            raise OCRAPIError(f"Gemini 응답 데이터 해석 실패: {e}")
    else:
        err_msg = parse_gemini_error_message(res.status_code, res.text)
        print(f"Gemini API 에러 (HTTP {res.status_code}): {res.text}")
        raise OCRAPIError(err_msg, status_code=res.status_code)

def get_gemini_ocr_data_smart(cache_key, png_bytes, force=False):
    cache_path = os.path.join(CACHE_DIR, "gemini_" + cache_key + ".json")
    if force or not os.path.exists(cache_path):
        data = call_gemini_api_raw(png_bytes)
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
    finished_verification_data = Signal(list)
    error = Signal(str)
    api_used = Signal()

    def __init__(self, image_paths, mode="fast", force_mode=False, engine="vision", project_dir=None):
        super().__init__()
        self.image_paths = image_paths
        self.mode = mode # "fast" 또는 "smart"
        self.force_mode = force_mode
        self.engine = engine # "vision" 또는 "gemini"
        self.project_dir = project_dir
        self.is_running = True
        self.MERGE_THRESHOLD = 80 
        self.MAX_SLICE_HEIGHT = 2450 
        self.verification_data = []

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
        vision_blocks = []
        global_counter = 1
        
        # 1. 램 부하 및 안전을 위해 이미지 높이 임계치(25,000px) 기준으로 청크 생성
        MAX_CHUNK_HEIGHT = 25000
        chunks = []
        current_chunk = []
        current_chunk_height = 0
        
        for img_path in self.image_paths:
            try:
                with Image.open(img_path) as img:
                    w, h = img.size
                
                # 단독 혹은 누적으로 임계치를 초과할 경우 청크 분할
                if current_chunk and (current_chunk_height + h > MAX_CHUNK_HEIGHT):
                    chunks.append(current_chunk)
                    current_chunk = []
                    current_chunk_height = 0
                
                current_chunk.append((img_path, w, h))
                current_chunk_height += h
            except Exception as e:
                print(f"이미지 정보 로드 실패: {img_path} ({e})")
        
        if current_chunk:
            chunks.append(current_chunk)
            
        total_chunks = len(chunks)
        cumulative_height_offset = 0
        image_global_ranges = []
        
        # 2. 각 청크별 처리 실행
        for chunk_idx, chunk in enumerate(chunks):
            if not self.is_running: break
            self.progress_text.emit(f"🔄 [그룹 {chunk_idx + 1}/{total_chunks}] 분석용 이미지 조립 중...")
            
            # 가로 최대 폭 및 총 높이 계산
            w_max = max(item[1] for item in chunk)
            chunk_total_h = sum(item[2] for item in chunk)
            
            # 메모리 병합 캔버스 생성 (흰색 배경)
            try:
                stitched_img = Image.new("RGB", (w_max, chunk_total_h), (255, 255, 255))
                current_y = 0
                for img_path, w, h in chunk:
                    with Image.open(img_path) as img:
                        # 이미지를 가로축 정중앙에 배치
                        x_offset = (w_max - w) // 2
                        stitched_img.paste(img, (x_offset, current_y))
                        image_global_ranges.append({
                            "path": img_path,
                            "y_start": cumulative_height_offset + current_y,
                            "y_end": cumulative_height_offset + current_y + h,
                            "w": w,
                            "h": h,
                            "x_offset": x_offset
                        })
                        current_y += h
            except Exception as e:
                print(f"이미지 병합 실패: {e}")
                continue
                
            # 3. 병합된 청크 캔버스 내에서 재분할 수행
            current_y = 0
            slice_idx = 0
            tasks = []
            
            while current_y < chunk_total_h:
                if self.mode == "smart":
                    self.progress_text.emit(f"🔍 [그룹 {chunk_idx + 1}/{total_chunks}] 안전 절단 경계 탐색 중...")
                    cut_y = self.find_panel_gap(stitched_img, current_y, self.MAX_SLICE_HEIGHT)
                else:
                    cut_y = min(current_y + self.MAX_SLICE_HEIGHT, chunk_total_h)
                
                cropped = stitched_img.crop((0, current_y, w_max, cut_y))
                preprocessed = preprocess_image_for_ocr(cropped)
                buf = io.BytesIO()
                preprocessed.save(buf, format="PNG")
                png_bytes = buf.getvalue()
                
                tasks.append({
                    "bytes": png_bytes,
                    "offset": cumulative_height_offset + current_y,
                    "slice_h": cut_y - current_y,
                    "slice_w": w_max,
                    "key": f"{hashlib.md5(png_bytes).hexdigest()}_slice_{chunk_idx}_{slice_idx}"
                })
                current_y = cut_y
                slice_idx += 1
                
            self.progress_text.emit(f"🚀 [그룹 {chunk_idx + 1}/{total_chunks}] 병렬 문자 추출 중... (0/{len(tasks)})")
            
            chunk_base_progress = int((chunk_idx / total_chunks) * 90)
            chunk_span_progress = int((1 / total_chunks) * 90)
            completed_tasks_count = 0
            total_tasks_count = max(1, len(tasks))

            api_error_raised = None

            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                if self.engine == "gemini":
                    future_to_task = {executor.submit(get_gemini_ocr_data_smart, t["key"], t["bytes"], self.force_mode): t for t in tasks}
                    slice_results = []
                    for future in concurrent.futures.as_completed(future_to_task):
                        if not self.is_running:
                            break
                        task = future_to_task[future]
                        try:
                            lines, is_api_called = future.result()
                            if is_api_called: self.api_used.emit()
                            slice_results.append((task, lines))
                        except OCRAPIError as oe:
                            api_error_raised = str(oe)
                            self.is_running = False
                            break
                        except Exception as e:
                            api_error_raised = f"분석 중 예상치 못한 오류 발생: {e}"
                            self.is_running = False
                            break
                        
                        completed_tasks_count += 1
                        current_pct = chunk_base_progress + int((completed_tasks_count / total_tasks_count) * chunk_span_progress)
                        self.progress_val.emit(min(90, current_pct))
                        self.progress_text.emit(f"🚀 [그룹 {chunk_idx + 1}/{total_chunks}] 문자 추출 중... ({completed_tasks_count}/{total_tasks_count})")
                    
                    if api_error_raised:
                        self.error.emit(api_error_raised)
                        return

                    # Y축 오프셋 순서대로 정렬하여 자연스러운 독서 흐름 보장
                    slice_results.sort(key=lambda x: x[0]["offset"])
                    for task, lines in slice_results:
                        total_lines = len(lines)
                        for k, item in enumerate(lines):
                            if isinstance(item, dict):
                                txt = item.get("text", "").strip()
                                box_2d = item.get("box_2d")
                            else:
                                txt = str(item).strip()
                                box_2d = None
                            if not txt:
                                continue
                            if box_2d and len(box_2d) == 4:
                                ymin, xmin, ymax, xmax = box_2d
                                abs_y1 = task["offset"] + int(ymin * task["slice_h"] / 1000.0)
                                abs_y2 = task["offset"] + int(ymax * task["slice_h"] / 1000.0)
                                abs_x1 = int(xmin * task["slice_w"] / 1000.0)
                                abs_x2 = int(xmax * task["slice_w"] / 1000.0)
                            else:
                                step = task["slice_h"] / max(1, total_lines)
                                abs_y1 = task["offset"] + int(k * step)
                                abs_y2 = task["offset"] + int((k + 0.8) * step)
                                abs_x1 = int(task["slice_w"] * 0.1)
                                abs_x2 = int(task["slice_w"] * 0.9)
                            full_results.append({
                                "text": txt,
                                "abs_box": (abs_x1, abs_y1, abs_x2, abs_y2)
                            })
                else:
                    future_to_task = {executor.submit(get_ocr_data_smart, t["key"], t["bytes"], self.force_mode): t for t in tasks}
                    for future in concurrent.futures.as_completed(future_to_task):
                        if not self.is_running:
                            break
                        task = future_to_task[future]
                        try:
                            blocks, is_api_called = future.result()
                            if is_api_called: self.api_used.emit()
                            for b in blocks:
                                b_copy = b.copy()
                                b_copy['y'] += task["offset"]
                                b_copy['bottom'] += task["offset"]
                                vision_blocks.append(b_copy)
                        except OCRAPIError as oe:
                            api_error_raised = str(oe)
                            self.is_running = False
                            break
                        except Exception as e:
                            api_error_raised = f"분석 중 예상치 못한 오류 발생: {e}"
                            self.is_running = False
                            break
                            
                        completed_tasks_count += 1
                        current_pct = chunk_base_progress + int((completed_tasks_count / total_tasks_count) * chunk_span_progress)
                        self.progress_val.emit(min(90, current_pct))
                        self.progress_text.emit(f"🚀 [그룹 {chunk_idx + 1}/{total_chunks}] 문자 추출 중... ({completed_tasks_count}/{total_tasks_count})")
                    
                    if api_error_raised:
                        self.error.emit(api_error_raised)
                        return
                        
            # 다음 청크 사이의 안전 여백 추가 (50px)
            cumulative_height_offset += chunk_total_h + 50
            self.progress_val.emit(int((chunk_idx + 1) / total_chunks * 90))
            
        if not self.is_running:
            return
            
        # 4. 결과 반환 및 좌표 매핑 처리
        if self.engine != "gemini":
            self.progress_text.emit("📝 말풍선 그룹화 및 대사 복원 중...")
            self.progress_val.emit(95)
            merged_lines, merged_boxes = self.merge_close_blocks(vision_blocks)
            for txt, box in zip(merged_lines, merged_boxes):
                full_results.append({
                    "text": txt,
                    "abs_box": box
                })

        self.progress_text.emit("📝 대사 및 위치 데이터 정리 중...")
        self.progress_val.emit(97)

        verification_items = []
        for i, item in enumerate(full_results):
            txt = item["text"]
            bx1, by1, bx2, by2 = item["abs_box"]
            by_mid = (by1 + by2) / 2.0
            matched_img = None
            for idx, img_info in enumerate(image_global_ranges):
                if img_info["y_start"] <= by_mid <= img_info["y_end"]:
                    matched_img = (idx, img_info)
                    break
            if not matched_img and image_global_ranges:
                matched_img = min(enumerate(image_global_ranges), key=lambda x: abs(x[1]["y_start"] - by_mid))
            
            if matched_img:
                img_idx, info = matched_img
                lx1 = max(0, min(info["w"], bx1 - info["x_offset"]))
                ly1 = max(0, min(info["h"], by1 - info["y_start"]))
                lx2 = max(0, min(info["w"], bx2 - info["x_offset"]))
                ly2 = max(0, min(info["h"], by2 - info["y_start"]))
                img_file = os.path.basename(info["path"])
                box = [int(lx1), int(ly1), int(lx2), int(ly2)]
            else:
                img_idx = 0
                img_file = os.path.basename(self.image_paths[0]) if self.image_paths else ""
                box = [0, 0, 100, 100]
            
            verification_items.append({
                "id": i + 1,
                "text": txt,
                "character": "",
                "image_index": img_idx,
                "image_file": img_file,
                "box": box,
                "is_verified": False
            })

        final_lines = [f"[{item['id']}] {item['text']}" for item in verification_items]
        self.verification_data = verification_items

        if self.project_dir:
            save_ocr_boxes(self.project_dir, verification_items)

        self.progress_val.emit(100)
        self.finished_verification_data.emit(verification_items)
        self.finished_ocr.emit(final_lines)

    def merge_close_blocks(self, results):
        if not results: return [], []

        valid_results = [b for b in results if b['bottom'] > b['y']]
        if not valid_results: 
            return [b['text'] for b in results], [(b.get('x1', 0), b.get('y', 0), b.get('x2', 100), b.get('bottom', 100)) for b in results]
            
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

        final_merged = []
        final_boxes = []
        for m in group_metadata:
            group = m['group']
            # 같은 말풍선 안에서도 비슷한 높이면 왼쪽부터 합치도록 미세 조정
            group.sort(key=lambda b: (int(b['y'] // (avg_height * 0.5)), b['x1']))
            merged_text = " ".join(b['text'] for b in group)
            final_merged.append(merged_text)
            final_boxes.append((m['x1'], m['y1'], m['x2'], m['y2']))

        return final_merged, final_boxes

    def stop(self):
        self.is_running = False