from PIL import Image
import os

img_path = r"app_icons\webtoon scripter_icontemplate.png"
if os.path.exists(img_path):
    img = Image.open(img_path)
    print("Dimensions:", img.size)
    print("Mode:", img.mode)
    # Check if there is alpha channel
    if img.mode == 'RGBA':
        bbox = img.getbbox()
        print("Alpha Bounding Box:", bbox)
else:
    print("Not found")
