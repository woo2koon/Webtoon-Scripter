from PIL import Image
import os

# 1. Windows Icon (.ico) conversion
win_png = "app_icon/webtoon_scripter_icon_windows.png"
win_ico = "app_icon/webtoon_scripter_icon_windows.ico"

if os.path.exists(win_png):
    print(f"Converting {win_png} to {win_ico}...")
    img = Image.open(win_png)
    img.save(win_ico, format="ICO", sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    print("Windows ICO conversion complete!")
else:
    print(f"Warning: {win_png} does not exist. Skipping Windows ICO conversion.")

# 2. macOS Icon (.icns) conversion (with Apple HIG padding guidelines)
mac_png = "app_icons/webtoon_scripter_icon_black_modified_mac.png"
mac_icns = "app_icon/webtoon_scripter_icon_mac.icns"

if os.path.exists(mac_png):
    print(f"Converting {mac_png} to {mac_icns} with Apple HIG margins...")
    img = Image.open(mac_png)
    
    # macOS App Icon 가이드라인: 1024x1024 캔버스 기준 
    # 실제 본체 이미지(스쿼클)는 약 82% 크기인 824x824 크기로 줄여서 정중앙에 배치하고,
    # 상하좌우에 100px씩 투명 여백(Padding)을 주어야 독(Dock)이나 애플리케이션 폴더에서 다른 앱들과 크기가 조화를 이룹니다.
    target_canvas_size = 1024
    content_size = 824
    
    w, h = img.size
    scale = min(content_size / w, content_size / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    
    # 고품질 Lanczos 필터로 축소
    resized_img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # 1024x1024 투명 캔버스 생성
    canvas = Image.new("RGBA", (target_canvas_size, target_canvas_size), (0, 0, 0, 0))
    
    # 정중앙 계산 후 배치
    paste_x = (target_canvas_size - new_w) // 2
    paste_y = (target_canvas_size - new_h) // 2
    
    canvas.paste(resized_img, (paste_x, paste_y), resized_img if resized_img.mode == 'RGBA' else None)
    canvas.save(mac_icns, format="ICNS")
    
    print("macOS ICNS conversion complete (with 100px margins on all sides)!")
else:
    print(f"Warning: {mac_png} does not exist. Skipping macOS ICNS conversion.")
