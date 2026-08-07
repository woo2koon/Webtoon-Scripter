import os
import sys
import json
import base64
import requests

def load_api_key():
    settings_path = "settings.json"
    if os.path.exists(settings_path):
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                active_preset = data.get("active_preset", "Default")
                presets = data.get("presets", {})
                preset_data = presets.get(active_preset, {})
                # settings.json의 presets -> Default -> ai 키를 먼저 탐색합니다.
                api_key = preset_data.get("ai", "")
                if api_key:
                    return api_key
        except Exception as e:
            print(f"settings.json 읽기 오류: {e}")
            
    # 환경변수에서 가져오기 시도
    return os.environ.get("GEMINI_API_KEY", "")

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def test_gemini_ocr(image_path, model="gemini-3.5-flash"):
    api_key = load_api_key()
    if not api_key:
        print("에러: settings.json에 AI API 키가 설정되어 있지 않거나 환경변수 GEMINI_API_KEY가 없습니다.")
        print("앱의 [설정] > [API 키 설정]에서 'AI API Key'를 입력했는지 확인하세요.")
        sys.exit(1)

    print(f"--------------------------------------------------")
    print(f"[분석 대상 이미지] {image_path}")
    print(f"[사용 모델] {model}")
    print(f"--------------------------------------------------")

    # 이미지 확장자에 따른 mimeType 매핑
    ext = os.path.splitext(image_path)[1].lower()
    if ext in ['.jpg', '.jpeg']:
        mime_type = "image/jpeg"
    elif ext == '.png':
        mime_type = "image/png"
    elif ext == '.webp':
        mime_type = "image/webp"
    else:
        mime_type = "image/jpeg"

    try:
        base64_image = encode_image(image_path)
    except Exception as e:
        print(f"❌ 이미지 로딩/인코딩 에러: {e}")
        return

    # 제미나이 멀티모달 프롬프트 설정 (구조화된 JSON 반환 요청)
    prompt = """
    너는 웹툰/만화 컷 이미지의 오디오 스크립트 작성 및 문자분석 전문가야.
    이미지에서 텍스트를 추출하고 분석해줘.

    [작업 규칙]
    1. 웹툰 컷의 읽기 순서(보통 위에서 아래, 말풍선 흐름)에 맞춰 자연스럽게 텍스트를 검출해라.
    2. 모든 대사(말풍선), 내레이션(설명 박스), 효과음(의성어/의태어 등 배경 텍스트)을 포함해라.
    3. 결과는 반드시 한국어로 구성하고 아래 JSON 스키마 구조를 만족해야 한다.
    4. 응답에는 마크다운 기호(예: ```json)나 기타 부가 텍스트 없이 오직 순수한 JSON 문자열만 반환해라.

    [JSON Schema]
    {
      "results": [
        {
          "index": 1,
          "type": "speech or narration or sfx or etc",
          "speaker": "말하는 캐릭터 이름 혹은 식별 가능한 특징",
          "text": "추출한 대사 텍스트 그대로 기재 (줄바꿈이 있는 경우 한 줄로 공백 구분하여 연결)",
          "visual_context": "캐릭터의 표정이나 말풍선의 모양새 또는 간단한 상황 설명"
        }
      ]
    }
    """

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": prompt},
                    {
                        "inlineData": {
                            "mimeType": mime_type,
                            "data": base64_image
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.1
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }

    try:
        # 타임아웃을 넉넉히 60초로 지정
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.json()
            try:
                content_text = result['candidates'][0]['content']['parts'][0]['text']
                parsed_json = json.loads(content_text.strip())
                
                # 결과를 UTF-8 JSON 파일로 저장합니다.
                output_file = "gemini_ocr_result.json"
                with open(output_file, "w", encoding="utf-8") as out_f:
                    json.dump(parsed_json, out_f, indent=2, ensure_ascii=False)
                
                print("\n[분석 성공 - Gemini API OCR 결과]")
                print(f"결과가 '{output_file}' 파일에 UTF-8 인코딩으로 저장되었습니다. 파일을 열어 한글 결과를 확인해 보세요.")
                
                # 콘솔 인코딩 에러 방지를 위해 ascii 세이프하게 출력
                print("\n[미리보기 (텍스트만 추출)]")
                for idx, item in enumerate(parsed_json.get("results", [])):
                    text = item.get("text", "")
                    speaker = item.get("speaker", "알 수 없음")
                    # 인코딩 문제에 대비해 에러 핸들링
                    try:
                        print(f"[{idx+1}] {speaker}: {text}")
                    except UnicodeEncodeError:
                        print(f"[{idx+1}] {speaker.encode('utf-8')}: {text.encode('utf-8')}")
            except Exception as parse_err:
                print(f"\n[API 응답 JSON 파싱 실패] {parse_err}")
                raw_err_file = "gemini_raw_error.txt"
                with open(raw_err_file, "w", encoding="utf-8") as err_f:
                    err_f.write(content_text)
                print(f"오류가 있는 원본 데이터가 '{raw_err_file}' 파일에 저장되었습니다.")
                if 'candidates' in result:
                    print("수신 데이터 일부:")
                    print(content_text[:300] + "...")
                else:
                    print(result)
        else:
            print(f"[API 호출 실패] (HTTP {response.status_code})")
            print(response.text)
    except Exception as e:
        print(f"[네트워크/서버 요청 에러] {e}")

if __name__ == "__main__":
    # 기본 테스트 이미지 경로 설정 (실제 프로젝트 폴더 내 이미지)
    default_img = "projects/최강의 냄새/60화/images/001.jpg"
    
    # 아규먼트로 경로가 있으면 해당 경로 사용
    img_path = sys.argv[1] if len(sys.argv) > 1 else default_img
    
    if not os.path.exists(img_path):
        print(f"오류: 이미지 파일을 찾을 수 없습니다: {img_path}")
        print("사용법: python test_gemini_ocr.py [원하는_이미지_경로]")
    else:
        test_gemini_ocr(img_path)
