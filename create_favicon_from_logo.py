from PIL import Image, ImageDraw, ImageFont
import os

def create_truck_favicon(source_path, output_path, text="F&M"):
    # Open the existing truck logo
    truck = Image.open(source_path).convert("RGBA")
    
    # Create a square canvas for the favicon (e.g., 256x256 for high res scaling)
    size = 256
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    
    # Resize truck to fit the square nicely
    # Maintain aspect ratio
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Paste truck in center
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    favicon.paste(truck_resized, (offset_x, offset_y), truck_resized)
    
    # Add text in the "middle" of the truck
    # The middle of the truck body is roughly the center of the cargo area
    draw = ImageDraw.Draw(favicon)
    
    # Find a bold font
    try:
        font = ImageFont.truetype("arialbd.ttf", int(new_h * 0.25))
    except:
        font = ImageFont.load_default()
        
    # We'll put F&M in white inside the truck silhouette
    # The silhouette is gold #D3A129. White text looks good.
    
    # Calculate text position (center of the cargo area relative to the truck)
    # Cargo area is roughly the right 2/3 of the truck
    cargo_center_x = offset_x + int(new_w * 0.6)
    cargo_center_y = offset_y + int(new_h * 0.5)
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw_text = bbox[2] - bbox[0]
    th_text = bbox[3] - bbox[1]
    
    draw.text((cargo_center_x - tw_text//2, cargo_center_y - th_text//2), text, font=font, fill=(255, 255, 255, 255))
    
    # Save as PNG
    favicon.save(output_path, "PNG")
    
    # Also save small sizes
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")
    favicon.resize((16, 16)).save(output_path.replace(".png", "_16.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_camion_fm.png"

create_truck_favicon(source, output)
print("Favicon created successfully.")
