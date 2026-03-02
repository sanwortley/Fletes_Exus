from PIL import Image, ImageDraw, ImageFont
import os

def generate_pro_favicon(size, output_path):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # Background: Rounded rectangle GOLD
    gold_color = (211, 161, 41, 255)
    corner_radius = size // 10
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=corner_radius, fill=gold_color)
    
    # Text Setup
    try:
        # Bold font from system
        font_upper = ImageFont.truetype("arialbd.ttf", int(size * 0.22))
        font_mid = ImageFont.truetype("arialbd.ttf", int(size * 0.16))
        font_lower = ImageFont.truetype("arialbd.ttf", int(size * 0.20))
    except:
        font_upper = font_mid = font_lower = ImageFont.load_default()
    
    # Draw FLETES
    draw.text((size//2, size*0.25), "FLETES", fill="white", font=font_upper, anchor="mm")
    # Draw Y
    draw.text((size//2, size*0.50), "Y", fill="white", font=font_mid, anchor="mm")
    # Draw MUDANZAS
    draw.text((size//2, size*0.75), "MUDANZAS", fill="white", font=font_lower, anchor="mm")
    
    img.save(output_path, format="PNG")

base_dir = r"c:\Exus MVP\Exus\frontend\images"
generate_pro_favicon(32, os.path.join(base_dir, "favicon_pro_32.png"))
generate_pro_favicon(64, os.path.join(base_dir, "favicon_pro_64.png"))
generate_pro_favicon(16, os.path.join(base_dir, "favicon_pro_16.png"))
print("Professional favicons generated successfully.")
