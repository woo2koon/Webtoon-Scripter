# ai_worker.py
import requests
import json
import time
from PySide6.QtCore import QThread, Signal
import config 

class SpellCheckWorker(QThread):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, original_text):
        super().__init__()
        self.original_text = original_text

    def run(self):
        start_time = time.time()
        # config에서 활성화된 키를 가져옵니다. 
        active_key = config.AI_API_KEY
        
        if not active_key:
            self.error.emit("AI API 키가 없습니다. [파일] > [설정]을 확인해주세요.")
            return

        # [모델 변경] Gemini 2.0 Flash에서 Gemini 3.1 Flash Lite로 경로를 수정했습니다.
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite-preview:generateContent?key={active_key}"

        prompt_text = f"""
        너는 한국어 웹툰 대사 교정 전문가야.
        아래 [원본 텍스트]의 '맞춤법'과 '띄어쓰기'만 정확하게 교정해줘.
        
        [절대 규칙]
        1. 의미, 어조, 형태를 절대 바꾸지 마. (교정 외 수정 금지)
        2. 오직 교정된 결과 텍스트만 출력해. 부가 설명, 인사말, 마크다운 기호(```) 절대 금지.
        3. 동일한 단어를 반복하거나 말을 더듬는 증상(예: 시간에서시간간간)을 절대 보이지 마.
        4. 줄바꿈 구조를 원본과 100% 동일하게 유지해.
        5. 교정할 내용이 없다면 원본을 그대로 출력해.

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
            # 타임아웃 30초 추가
            response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
            duration = time.time() - start_time
            print(f"DEBUG: [SpellCheck] AI 응답 수신 완료 (소요 시간: {duration:.2f}초, 상태 코드: {response.status_code})")
            
            if response.status_code == 200:
                result = response.json()
                try:
                    corrected_text = result['candidates'][0]['content']['parts'][0]['text'].strip()
                    self.finished.emit(corrected_text)
                except (KeyError, IndexError, TypeError):
                    print("DEBUG: [SpellCheck] AI 응답 구조 해석 실패")
                    self.error.emit("AI 응답 해석 실패: 데이터 구조가 변경되었거나 내용이 없습니다.")
            elif response.status_code == 429:
                print("DEBUG: [SpellCheck] AI 호출 한도 초과 (429)")
                self.error.emit("AI 호출 한도 초과: 잠시 후 다시 시도해주세요.")
            else:
                print(f"DEBUG: [SpellCheck] AI 호출 실패 ({response.status_code}): {response.text}")
                self.error.emit(f"AI 호출 실패 ({response.status_code}): {response.text}")
        except requests.exceptions.Timeout:
            print("DEBUG: [SpellCheck] AI 응답 시간 초과 (Timeout)")
            self.error.emit("AI 응답 시간 초과: 네트워크 상태를 확인해주세요.")
        except Exception as e:
            print(f"DEBUG: [SpellCheck] 네트워크 오류 발생: {str(e)}")
            self.error.emit(f"네트워크 오류: {str(e)}")