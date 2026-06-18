# partial_ocr_worker.py
import io
from PIL import Image
from PySide6.QtCore import QThread, Signal
import config
from ocr_worker import preprocess_image_for_ocr, call_google_api_raw

class PartialOCRWorker(QThread):
    finished = Signal(list, bool)  # Emits (results, success)

    def __init__(self, crop_tasks):
        """
        crop_tasks: List of dicts, each containing:
            - 'path': Path to the image file
            - 'x', 'y', 'w', 'h': Crop coordinates relative to the original image dimensions
        """
        super().__init__()
        self.crop_tasks = crop_tasks

    def run(self):
        try:
            print(f"\n[부분 OCR 스레드] 시작: 교차된 조각 수 = {len(self.crop_tasks)}개")
            
            cropped_images = []
            for idx, task in enumerate(self.crop_tasks):
                img_path = task['path']
                tx, ty, tw, th = task['x'], task['y'], task['w'], task['h']
                
                with Image.open(img_path) as img:
                    img_w, img_h = img.size
                    x_clamped = max(0, min(tx, img_w))
                    y_clamped = max(0, min(ty, img_h))
                    w_clamped = max(1, min(tw, img_w - x_clamped))
                    h_clamped = max(1, min(th, img_h - y_clamped))
                    
                    cropped_part = img.crop((x_clamped, y_clamped, x_clamped + w_clamped, y_clamped + h_clamped))
                    # Pillow lazy loading 방지용 메모리 로드
                    cropped_part.load()
                    cropped_images.append(cropped_part)
                    print(f"  - 조각 {idx + 1} 크롭 완료: 원본={img_path}, 영역=(x:{x_clamped}, y:{y_clamped}, w:{w_clamped}, h:{h_clamped})")

            if not cropped_images:
                self.finished.emit([], True)
                return

            # 메모리에서 세로 방향으로 병합 (Stitching)
            merged_width = max(img.width for img in cropped_images)
            merged_height = sum(img.height for img in cropped_images)
            
            merged_img = Image.new("RGB", (merged_width, merged_height), (255, 255, 255))
            current_y = 0
            for img in cropped_images:
                # 가로 기준 중앙 정렬 배치
                x_offset = (merged_width - img.width) // 2
                merged_img.paste(img, (x_offset, current_y))
                current_y += img.height

            print(f"[부분 OCR 스레드] 조각 병합 완료 (최종 크기: {merged_img.size}). 전처리 시작...")
            preprocessed = preprocess_image_for_ocr(merged_img)
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
