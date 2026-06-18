# partial_ocr_worker.py
import io
from PIL import Image
from PySide6.QtCore import QThread, Signal
import config
from ocr_worker import preprocess_image_for_ocr, call_google_api_raw

class PartialOCRWorker(QThread):
    finished = Signal(list, bool)  # Emits (results, success)

    def __init__(self, img_path, x, y, w, h):
        super().__init__()
        self.img_path = img_path
        self.x = x
        self.y = y
        self.w = w
        self.h = h

    def run(self):
        try:
            print(f"\n[부분 OCR 스레드] 시작: 이미지={self.img_path}, 영역=(x:{self.x}, y:{self.y}, w:{self.w}, h:{self.h})")

            # 이미지 크롭 및 전처리
            with Image.open(self.img_path) as img:
                img_w, img_h = img.size
                x_clamped = max(0, min(self.x, img_w))
                y_clamped = max(0, min(self.y, img_h))
                w_clamped = max(1, min(self.w, img_w - x_clamped))
                h_clamped = max(1, min(self.h, img_h - y_clamped))

                cropped = img.crop((x_clamped, y_clamped, x_clamped + w_clamped, y_clamped + h_clamped))
            
            print(f"[부분 OCR 스레드] 크롭 완료 (실제 크기: {cropped.size}). 전처리 시작...")
            preprocessed = preprocess_image_for_ocr(cropped)
            buf = io.BytesIO()
            preprocessed.save(buf, format="PNG")
            png_bytes = buf.getvalue()

            # API 호출
            print("[부분 OCR 스레드] 구글 비전 API 호출 전송 중...")
            results = call_google_api_raw(png_bytes)
            print(f"[부분 OCR 스레드] API 응답 수신 완료 (인식된 블록 수: {len(results)}개)")
            self.finished.emit(results, True)
        except Exception as e:
            print(f"[부분 OCR 스레드] 에러 발생: {e}")
            import traceback
            traceback.print_exc()
            self.finished.emit([], False)
