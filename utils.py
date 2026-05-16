# utils.py
import re
import os
import base64
import subprocess
import platform
from config import TEMPLATE_PATH, EXCEL_TEMPLATE_BASE64

from PySide6.QtCore import Qt, QByteArray, QSize # Qt, QByteArray는 여기에
from PySide6.QtGui import QIcon, QPixmap, QPainter # QPixmap, QPainter는 여기에
from PySide6.QtSvg import QSvgRenderer # [핵심] SVG 렌더러는 별도 모듈입니다.

from PySide6.QtGui import QIcon
import os

def get_icon(file_path):
    """기본 아이콘 로더 (기존 코드 복구)"""
    if not os.path.exists(file_path):
        return QIcon()
    return QIcon(file_path)

def get_colored_icon(file_path, color):
    """SVG 색상을 주입하여 QIcon으로 반환 (새로운 기능)"""
    if not os.path.exists(file_path):
        return QIcon()

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            svg_data = f.read()
        
        # 'currentColor'나 기본 검정색(#000000)을 원하는 색으로 치환합니다
        new_svg = svg_data.replace('currentColor', color).replace('#000000', color)
        
        # SVG를 픽스맵으로 그리기 위해 렌더러와 페인터 사용
        renderer = QSvgRenderer(QByteArray(new_svg.encode('utf-8')))
        pixmap = QPixmap(64, 64) # 고해상도 베이스 생성
        pixmap.fill(Qt.transparent)
        
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        
        return QIcon(pixmap)
    except Exception as e:
        print(f"SVG 색상 변환 중 오류 발생: {e}")
        return QIcon(file_path) # 실패 시 원본 아이콘이라도 반환

def restore_template():
    if not os.path.exists(TEMPLATE_PATH):
        try:
            if len(EXCEL_TEMPLATE_BASE64) > 100:
                with open(TEMPLATE_PATH, "wb") as f:
                    f.write(base64.b64decode(EXCEL_TEMPLATE_BASE64))
        except: pass

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split('([0-9]+)', s)]

def clean_korean_text(text):
    if not text: return ""
    
    # 1. 기본 공백 정리
    text = re.sub(r'\s+', ' ', text).strip()

    # -----------------------------------------------------------------
    # [NEW] 숫자 환각(Hallucination) 제거 필터
    # -----------------------------------------------------------------
    # (1) 같은 숫자가 2번 이상 반복되는 숫자만 있는 경우 제거
    # 예: "000", "888", "1111" 등 배경 패턴 오인식 대응
    if re.fullmatch(r'(\d)\1+', text):
        return ""
    
    # (2) 의미 없는 단독 숫자 노이즈 제거
    # 배경의 작은 점이 "8"이나 "0"으로 인식되는 경우 (글자 수가 1이고 숫자인 경우)
    if len(text) == 1 and text.isdigit():
        return ""
    # -----------------------------------------------------------------

    # 2. 문장 부호 앞 공백 제거 (예: "안녕 !" -> "안녕!")
    text = re.sub(r'\s+([.,!?~])', r'\1', text)
    
    # 3. 안전한 단일 조사 붙이기
    safe_single_particles = "을를이가은는의에로와과도"
    text = re.sub(f'(?<=[가-힣])\\s+([{safe_single_particles}][\\s.,!?]?)', r'\1', text)
    
    # 4. 자주 떨어지는 어미 붙이기 (반복 수행)
    split_targets = "졌겼쳤켰었았였었구나라네어어요아해지게고서"
    for _ in range(3):
        text = re.sub(f'(?<=[가-힣])\\s+([{split_targets}][\\s.,!?]?)', r'\1', text)

    # 5. 강력한 접착제 리스트 (앞 글자와 무조건 붙임)
    strong_glues = [
        "이라고", "라고", "이라는", "라는", "이란", "란", "려면", "으려면", 
        "었구나", "았구나", "했구나", "였구나", "겠구나", "구나", "졌구나",
        "웠네", "았네", "었네", "했네", "왔네", "갔네", "지만", "하지만", 
        "하다", "한", "합니다", "해요", "해", "했어", "해서", "해라", "할",
        "잖아요", "잖아", "잖", "단", "다는", "단다", "달라", 
        "이었고", "였고", "이었어", "였어", "였지", 
        "겼어", "쳤어", "졌어", "켰어", "던", "었던", "았던", "했던", 
        "인가", "인가요", "텐데", "을텐데", "ㄹ텐데", "건가", "던가",
        "에게", "한테", "께", "에서", "으로", "하고", "이랑", "처럼", "만큼", "마냥", "보다",
        "더러", "보고", "까지", "부터", "조차", "마저", "밖에", "커녕", "대로", "치고",
        "이다", "입니다", "입니까", "이며", "이고", "이나", "이나마", "이라서", "라서",
        "습니다", "됩니다", "군요", "네요", "데요", "지요", "래요",
        "아요", "어요", "게요", "세요", "예요", "이에요", "거야", "거예요",
        "테니까", "을수록", "ㄹ수록", "는데", "은데", "던데", "ㄴ데", "니까", "으니까", 
        "므로", "길래", "아서", "어서", "여서", "다가", "면서", "으면서", "도록", "려고", 
        "으려고", "고자", "을까", "을래", "을지", "을게", "느라",
        "들", "들이", "들은", "들에게", "끼리", "투성이", "어치", "짜리", "님", 
        "없이", "같이", "있게", "없게", "답게", "스럽게", 
        "봤어", "줬어", "됐어", "났어", "왔어", "갔어",
        "말고", "말아", "않아", "않고", "못해", 
        "싶어", "싶다", "싶었", "싶니", "싶은",
        "버려", "버렸", "버리고", 
        "해줘", "해봐", "해놔", "해둬", 
        "하지마", "보지마", "가지마", "먹지마", 
        "될까", "될게", "될지", 
        "인가봐", "나봐", "가봐", 
        "다구", "라구", "자구", 
        "냐고", "다고", "라고", "자고", 
        "주세요", "주십시오", "줄게", "줄래",
        "걸", "게", "지", 
        "시키다", "당하다", "되다", "받다" 
    ]
    
    pattern = r'(?<=[가-힣])\s+(' + '|'.join(map(re.escape, strong_glues)) + r')'
    text = re.sub(pattern, r'\1', text)
    
    return text.strip()

def open_path(path):
    """
    시스템 기본 프로그램으로 파일이나 폴더를 엽니다. (윈도우, 맥, 리눅스 공용)
    """
    if platform.system() == "Windows":
        os.startfile(path)
    elif platform.system() == "Darwin": # macOS
        subprocess.run(["open", path])
    else: # Linux
        subprocess.run(["xdg-open", path])

import xlwings as xw

def safe_excel_clean(file_path):
    """
    윈도우/맥 공용: 엑셀 파일을 백그라운드에서 열어 재저장합니다.
    NAS 경로(UNC) 문제를 해결하기 위해 경로 정규화를 수행합니다.
    """
    # 1. 경로 정규화 (윈도우의 // 형식을 각 OS에 맞게 교정)
    abs_path = os.path.abspath(file_path)
    if platform.system() == "Windows":
        abs_path = os.path.normpath(abs_path) # // 를 \\ 로 변환

    # 파일 존재 여부 최종 확인
    if not os.path.exists(abs_path):
        print(f"⚠️ 파일을 찾을 수 없습니다: {abs_path}")
        return False

    try:
        # 2. 엑셀 앱을 백그라운드(비가시 모드)로 실행
        app = xw.App(visible=False, add_book=False)
        
        # 윈도우에서 가끔 발생하는 인스턴스 충돌 방지
        if platform.system() == "Windows":
            app.display_alerts = False 
            
        try:
            wb = app.books.open(abs_path)
            wb.save()  # [핵심] 엑셀이 직접 저장하게 하여 메타데이터 갱신
            wb.close()
            print(f"✅ 엑셀 세탁 완료: {os.path.basename(abs_path)}")
            return True
        except Exception as e:
            print(f"❌ 엑셀 제어 중 오류: {e}")
            return False
        finally:
            app.quit() # 앱 종료 (매우 중요)
            
    except Exception as e:
        print(f"❌ 엑셀 앱 실행 실패: {e}")
        # 실패 시 차선책으로 일반 실행 시도
        try:
            open_path(abs_path)
        except:
            pass
        return False
