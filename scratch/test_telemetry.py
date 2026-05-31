# scratch/test_telemetry.py
import requests
import os
import platform
import sys

def send_usage_telemetry(daily_count):
    # -------------------------------------------------------------
    # [사용자 가이드]
    # 아래의 URL과 entry.XXXXXX 키값을 본인의 구글 설문지 정보로 변경해 주세요!
    # -------------------------------------------------------------
    
    # 1. 복사한 설문지 주소의 끝을 viewform -> formResponse 로 변경하여 입력합니다.
    # 예: https://docs.google.com/forms/u/0/d/e/1FAIpQLSfD.../formResponse
    form_url = "https://docs.google.com/forms/d/e/1FAIpQLSdxr9XETDAnsujmZF5GbEYrJfeGUU7PwuQoAFLd3I126SZ0AQ/formResponse"
    
    # 2. 질문 1(유저명)과 질문 2(호출수)의 고유 entry ID를 맵핑합니다.
    # 예: entry.123456789
    entry_id_user = "entry.1752713297"
    entry_id_count = "entry.930589908"
    
    # -------------------------------------------------------------

    # OS 사용자 이름 가져오기 (팀 내 식별자)
    try:
        username = os.getlogin()
    except Exception:
        username = platform.node()
        
    os_info = f"{username} ({platform.system()})"
    
    data = {
        entry_id_user: os_info,
        entry_id_count: str(daily_count)
    }
    
    print("▶ 구글 설문지로 전송 중...")
    print(f"   전송 데이터: {data}")
    
    try:
        response = requests.post(form_url, data=data, timeout=5)
        # HTTP 200이 뜨면 전송 완료입니다.
        if response.status_code == 200:
            print("✅ 전송 성공! 구글 설문지 응답 페이지나 연결된 스프레드시트를 확인해 보세요.")
        else:
            print(f"❌ 전송 실패 (상태 코드: {response.status_code})")
            print("   주소 혹은 entry ID가 정확한지 확인해 주세요.")
    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    # 테스트용 카운트 값
    test_count = 348
    
    print("=== 구글 설문지 백그라운드 전송 테스트 ===")
    send_usage_telemetry(test_count)
