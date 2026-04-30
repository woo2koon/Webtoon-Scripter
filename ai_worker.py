# ai_worker.py
import requests
import json
from PySide6.QtCore import QThread, Signal
import config 

class SpellCheckWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, original_text):
        super().__init__()
        self.original_text = original_text

    def run(self):
        # config에서 활성화된 키를 가져옵니다. 
        active_key = config.AI_API_KEY
        
        if not active_key:
            self.error.emit("AI API 키가 없습니다. [파일] > [설정]을 확인해주세요.")
            return

        # [모델 변경] Gemini 2.0 Flash에서 Gemini 3.1 Flash Lite로 경로를 수정했습니다.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={active_key}"

        prompt_text = f"""
        너는 한국어 웹툰 대사 교정 전문가야.
        아래 [원본 텍스트]의 '맞춤법'과 '띄어쓰기'만 교정해줘.
        
        [규칙]
        1. 의미, 어조, 사투리, 비속어, 밈은 절대 바꾸지 마. (형태 유지)
        2. 오직 교정된 결과 텍스트만 출력해. 부가 설명 금지.
        3. 줄바꿈 구조를 원본과 100% 동일하게 유지해.

        [원본 텍스트]
        {self.original_text}
        """

        payload = {
            "contents": [{"parts": [{"text": prompt_text}]}],
            "generationConfig": {
                "temperature": 0.0  # 교정의 일관성을 위해 0.0으로 유지합니다.
            }
        }
        headers = {'Content-Type': 'application/json'}

        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
            if response.status_code == 200:
                result = response.json()
                try:
                    corrected_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    self.finished.emit(corrected_text)
                except (KeyError, IndexError):
                    self.error.emit("AI 응답 해석 실패: 데이터 구조가 변경되었을 수 있습니다.")
            elif response.status_code == 429:
                self.error.emit("AI 호출 한도 초과: 일일 할당량(500회)을 확인해주세요.")
            else:
                self.error.emit(f"AI 호출 실패 ({response.status_code}): {response.text}")
        except Exception as e:
            self.error.emit(f"네트워크 오류: {e}")