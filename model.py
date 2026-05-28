import requests
import config # 진우님의 API 키가 들어있는 파일

# 1. 사용할 API 키 가져오기
api_key = config.AI_API_KEY

# 2. 모델 리스트를 가져오는 API 주소
url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"

try:
    response = requests.get(url)
    if response.status_code == 200:
        models = response.json().get('models', [])
        print("--- 사용 가능한 모델 목록 ---")
        for m in models:
            # 여기서 출력되는 'name' 값이 진짜 API 주소에 넣을 이름입니다.
            print(f"모델명: {m['name']} | 지원 기능: {m['supportedGenerationMethods']}")
    else:
        print(f"조회 실패: {response.status_code}")
except Exception as e:
    print(f"에러 발생: {e}")