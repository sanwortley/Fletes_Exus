from PIL import Image, ImageDraw, ImageFont
import os

def create_truck_favicon_v3(source_path, output_path, text="F&M"):
    truck = Image.open(source_path).convert("RGBA")
    
    size = 256
    # Square transparent background
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    
    # Position for the "solid box" behind F&M
    # Roughly the lower half of the cargo area
    box_x1 = offset_x + int(new_w * 0.40)
    box_y1 = offset_y + int(new_h * 0.45)
    box_x2 = offset_x + int(new_w * 0.95)
    box_y2 = offset_y + int(new_h * 0.85)

    draw = ImageDraw.Draw(favicon)
    gold_color = (211, 161, 41, 255) # Our brand gold
    
    # 1. First, paste the truck
    favicon.paste(truck_resized, (offset_x, offset_y), truck_resized)
    
    # 2. Draw a solid rectangle over the "bars" region where text will sit
    # To make it look like part of the truck, we can make it a rounded rect
    draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=10, fill=gold_color)
    
    # 3. Add the white text
    try:
        font = ImageFont.truetype("arialbd.ttf", int(new_h * 0.30))
    except:
        font = ImageFont.load_default()
        
    center_x = (box_x1 + box_x2) // 2
    center_y = (box_y1 + box_y2) // 2
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw_text = bbox[2] - bbox[0]
    th_text = bbox[3] - bbox[1]
    
    draw.text((center_x - tw_text//2, center_y - th_text//2), text, font=font, fill="white")
    
    favicon.save(output_path, "PNG")
    # For favicons, 32x32 is usually standard as the best compromise
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_camion_solid.png"

create_truck_favicon_v3(source, output)
print("Solid cargo favicon created.")
