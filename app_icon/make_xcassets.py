import os
import json
import shutil

def create_xcassets():
    # 1. 경로 설정
    base_dir = os.path.dirname(os.path.abspath(__file__))
    xcassets_dir = os.path.join(base_dir, "AppIcon.xcassets")
    appiconset_dir = os.path.join(xcassets_dir, "AppIcon.appiconset")
    
    os.makedirs(appiconset_dir, exist_ok=True)
    
    # 2. AppIcon.xcassets/Contents.json 작성
    contents_main = {
        "info": {"version": 1, "author": "xcode"}
    }
    with open(os.path.join(xcassets_dir, "Contents.json"), "w") as f:
        json.dump(contents_main, f, indent=2)
        
    # 3. 이미지 복사
    src_icons_dir = os.path.join(base_dir, "../app_icons")
    
    # 테마별 파일 복사
    shutil.copy(os.path.join(src_icons_dir, "webtoon scripter_icontemplate.png"), os.path.join(appiconset_dir, "icon_light.png"))
    shutil.copy(os.path.join(src_icons_dir, "webtoon scripter_dark.png.png"), os.path.join(appiconset_dir, "icon_dark.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-ClearLight-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_clear_light.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-ClearDark-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_clear_dark.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-TintedLight-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_tinted_light.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-TintedDark-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_tinted_dark.png"))
    
    # 4. AppIcon.appiconset/Contents.json 작성
    # 모든 사이즈 정의
    sizes = [
        {"size": "16x16", "scales": ["1x", "2x"]},
        {"size": "32x32", "scales": ["1x", "2x"]},
        {"size": "128x128", "scales": ["1x", "2x"]},
        {"size": "256x256", "scales": ["1x", "2x"]},
        {"size": "512x512", "scales": ["1x", "2x"]}
    ]
    
    images = []
    
    # 헬퍼 함수: 모든 사이즈에 대해 특정 테마 이미지를 매핑
    def add_images(filename, appearances=None):
        for s in sizes:
            for scale in s["scales"]:
                img_dict = {
                    "size": s["size"],
                    "idiom": "mac",
                    "filename": "icon_" + filename + ".png",
                    "scale": scale
                }
                if appearances:
                    img_dict["appearances"] = appearances
                images.append(img_dict)
        
        # 1024x1024 사이즈 추가
        img_dict_1024 = {
            "size": "1024x1024",
            "idiom": "mac",
            "filename": "icon_" + filename + ".png",
            "scale": "1x"
        }
        if appearances:
            img_dict_1024["appearances"] = appearances
        images.append(img_dict_1024)

    # 1. Light (기본) - Appearances 없음
    add_images("light")
    
    # 2. Dark (다크) - 모든 사이즈에 다크 모드 매핑
    add_images("dark", [{"appearance": "luminosity", "value": "dark"}])
    
    # 3. Tinted Light
    add_images("tinted_light", [{"appearance": "luminosity", "value": "tinted"}])
    
    # 4. Tinted Dark
    add_images("tinted_dark", [{"appearance": "luminosity", "value": "tinted"}, 
                               {"appearance": "luminosity", "value": "dark"}])
            
    contents_appicon = {
        "images": images,
        "info": {"version": 1, "author": "xcode"}
    }
    with open(os.path.join(appiconset_dir, "Contents.json"), "w") as f:
        json.dump(contents_appicon, f, indent=2)
        
    print("AppIcon.xcassets 구조 생성 완료! (모든 해상도에 Dark/Tinted 완벽 대응)")

if __name__ == "__main__":
    create_xcassets()
