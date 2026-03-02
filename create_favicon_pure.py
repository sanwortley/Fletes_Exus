from PIL import Image, ImageDraw, ImageFont
import os

def create_pure_silhouette_favicon(source_path, output_path, text="F&M"):
    # This script will create a more solid version of the favicon for readability
    truck = Image.open(source_path).convert("RGBA")
    
    size = 256
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    
    # 1. We will draw the silhouette as a SOLID shape 
    # To do this, we can take the alpha mask of the resized truck
    alpha = truck_resized.split()[3]
    # Create a solid gold layer the same size as truck
    gold_layer = Image.new("RGBA", (new_w, new_h), (211, 161, 41, 255))
    
    # Use the truck alpha as a mask, but fill the gaps in the cage area
    # Or just use the original truck and drawing over the cage
    favicon.paste(gold_layer, (offset_x, offset_y), alpha)
    
    draw = ImageDraw.Draw(favicon)
    gold_color = (211, 161, 41, 255)
    
    # Fill the cage area solid
    # Cargo box coordinates (approximate based on the Porter style truck)
    cargo_x1 = offset_x + int(new_w * 0.40)
    cargo_y1 = offset_y + int(new_h * 0.28)
    cargo_x2 = offset_x + int(new_w * 0.98)
    cargo_y2 = offset_y + int(new_h * 0.82)
    
    draw.rectangle([cargo_x1, cargo_y1, cargo_x2, cargo_y2], fill=gold_color)
    
    # Now add the white text in the center of the cargo box
    try:
        font = ImageFont.truetype("arialbd.ttf", int(new_h * 0.35))
    except:
        font = ImageFont.load_default()
        
    center_x = (cargo_x1 + cargo_x2) // 2
    center_y = (cargo_y1 + cargo_y2) // 2
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw_text = bbox[2] - bbox[0]
    th_text = bbox[3] - bbox[1]
    
    draw.text((center_x - tw_text//2, center_y - th_text//2), text, font=font, fill="white")
    
    favicon.save(output_path, "PNG")
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_camion_pure.png"

create_pure_silhouette_favicon(source, output)
print("Pure silhouette favicon created.")
