import os
import json
import subprocess

def test_compile():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    test_dir = os.path.join(base_dir, "TestIcon.xcassets")
    appiconset_dir = os.path.join(test_dir, "AppIcon.appiconset")
    
    os.makedirs(appiconset_dir, exist_ok=True)
    
    # Copy dummy 1024x1024 images
    src_icons_dir = os.path.join(base_dir, "../app_icons")
    import shutil
    shutil.copy(os.path.join(src_icons_dir, "webtoon scripter_icontemplate.png"), os.path.join(appiconset_dir, "icon_light.png"))
    shutil.copy(os.path.join(src_icons_dir, "webtoon scripter_dark.png.png"), os.path.join(appiconset_dir, "icon_dark.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-ClearLight-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_clear_light.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-ClearDark-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_clear_dark.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-TintedLight-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_tinted_light.png"))
    shutil.copy(os.path.join(src_icons_dir, "Untitled-iOS-TintedDark-1024x1024@1x.png"), os.path.join(appiconset_dir, "icon_tinted_dark.png"))

    # Contents.json main
    with open(os.path.join(test_dir, "Contents.json"), "w") as f:
        json.dump({"info": {"version": 1, "author": "xcode"}}, f)
        
    # We will test various JSON mappings to see what actool accepts without errors.
    # 1. Any (Light)
    # 2. Dark (Luminosity: Dark)
    # 3. Clear Light (Presentation: Clear)
    # 4. Clear Dark (Presentation: Clear, Luminosity: Dark)
    # 5. Tinted Light (Luminosity: Tinted / Presentation: Tinted)
    # 6. Tinted Dark (Luminosity: Tinted, Luminosity: Dark)
    
    images = []
    # Any
    images.append({"size": "1024x1024", "idiom": "mac", "filename": "icon_light.png", "scale": "1x"})
    # Dark
    images.append({
        "size": "1024x1024", "idiom": "mac", "filename": "icon_dark.png", "scale": "1x",
        "appearances": [{"appearance": "luminosity", "value": "dark"}]
    })
    # Clear Light
    images.append({
        "size": "1024x1024", "idiom": "mac", "filename": "icon_clear_light.png", "scale": "1x",
        "appearances": [{"appearance": "presentation", "value": "clear"}]
    })
    # Clear Dark
    images.append({
        "size": "1024x1024", "idiom": "mac", "filename": "icon_clear_dark.png", "scale": "1x",
        "appearances": [{"appearance": "presentation", "value": "clear"}, {"appearance": "luminosity", "value": "dark"}]
    })
    # Tinted Light
    images.append({
        "size": "1024x1024", "idiom": "mac", "filename": "icon_tinted_light.png", "scale": "1x",
        "appearances": [{"appearance": "luminosity", "value": "tinted"}]
    })
    # Tinted Dark
    images.append({
        "size": "1024x1024", "idiom": "mac", "filename": "icon_tinted_dark.png", "scale": "1x",
        "appearances": [{"appearance": "luminosity", "value": "tinted"}, {"appearance": "luminosity", "value": "dark"}]
    })
    
    contents = {"images": images, "info": {"version": 1, "author": "xcode"}}
    with open(os.path.join(appiconset_dir, "Contents.json"), "w") as f:
        json.dump(contents, f, indent=2)
        
    print("Testing actool compilation...")
    cmd = [
        "actool", "--compile", "build/test_icon", 
        "--platform", "macosx", "--minimum-deployment-target", "13.0", 
        "--app-icon", "AppIcon", "--output-partial-info-plist", "build/test_icon/partial.plist",
        os.path.join(base_dir, "TestIcon.xcassets")
    ]
    os.makedirs("build/test_icon", exist_ok=True)
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:", res.stdout)
    print("STDERR:", res.stderr)
    print("Exit code:", res.returncode)

if __name__ == "__main__":
    test_compile()
