from PIL import Image, ImageDraw, ImageFont
import os

def create_truck_favicon_v2(source_path, output_path, text="F&M"):
    truck = Image.open(source_path).convert("RGBA")
    
    # Square canvas
    size = 256
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    
    # We want a more solid look for the cargo area to make the text readable
    # Let's draw the truck, then a solid box, then the text
    favicon.paste(truck_resized, (offset_x, offset_y), truck_resized)
    
    draw = ImageDraw.Draw(favicon)
    gold_color = (195, 149, 38, 255) # Slightly darker gold for contrast if needed, or same
    
    # Define cargo area box (roughly mid-right)
    box_x1 = offset_x + int(new_w * 0.45)
    box_y1 = offset_y + int(new_h * 0.35)
    box_x2 = offset_x + int(new_w * 0.90)
    box_y2 = offset_y + int(new_h * 0.70)
    
    # draw.rectangle([box_x1, box_y1, box_x2, box_y2], fill=gold_color)
    
    try:
        font = ImageFont.truetype("arialbd.ttf", int(new_h * 0.28))
    except:
        font = ImageFont.load_default()
        
    text_color = "white"
    
    # Center text in that cargo area
    center_x = (box_x1 + box_x2) // 2
    center_y = (box_y1 + box_y2) // 2
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw_text = bbox[2] - bbox[0]
    th_text = bbox[3] - bbox[1]
    
    # Drawing text with a small outline or shadow for readability on the "jaula"
    # Or just thicker text
    draw.text((center_x - tw_text//2, center_y - th_text//2), text, font=font, fill=text_color)
    
    favicon.save(output_path, "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")
    favicon.resize((16, 16)).save(output_path.replace(".png", "_16.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_camion_fmt.png"

create_truck_favicon_v2(source, output)
print("Enhanced favicon created.")
