from PIL import Image, ImageDraw, ImageFont, ImageChops
import os

def create_solid_truck_with_text(source_path, output_path, text="F&M"):
    # Open the logo
    truck = Image.open(source_path).convert("RGBA")
    
    # Resize for high resolution square canvas
    size = 512
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # 1. Create a SOLID version of the truck silhouette
    # We want to fill the "holes" in the cargo area
    alpha = truck_resized.split()[3]
    # Small trick to fill holes - if we want it real solid
    # We'll just draw a box over the cargo area on the gold layer
    gold_solid = Image.new("RGBA", (new_w, new_h), (211, 161, 41, 255))
    
    # Create the base truck on transparent background
    truck_solid = Image.new("RGBA", (new_w, new_h), (0, 0, 0, 0))
    truck_solid.paste(gold_solid, (0, 0), alpha)
    
    # Manually fill the cage area to make it a solid block for the text
    draw_solid = ImageDraw.Draw(truck_solid)
    # Cargo box rough area in the resized image context
    cage_x1, cage_y1 = int(new_w * 0.40), int(new_h * 0.30)
    cage_x2, cage_y2 = int(new_w * 0.98), int(new_h * 0.82)
    draw_solid.rectangle([cage_x1, cage_y1, cage_x2, cage_y2], fill=(211, 161, 41, 255))
    
    # 2. Create the final square favicon
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    favicon.paste(truck_solid, (offset_x, offset_y), truck_solid)
    
    # 3. Add text
    draw = ImageDraw.Draw(favicon)
    try:
        font = ImageFont.truetype("arialbd.ttf", int(new_h * 0.35))
    except:
        font = ImageFont.load_default()
        
    # Center text in the cargo area
    center_x = offset_x + (cage_x1 + cage_x2) // 2
    center_y = offset_y + (cage_y1 + cage_y2) // 2
    
    bbox = draw.textbbox((0, 0), text, font=font)
    t_w = bbox[2] - bbox[0]
    t_h = bbox[3] - bbox[1]
    
    draw.text((center_x - t_w//2, center_y - t_h//2), text, font=font, fill="white")
    
    # Save results
    favicon.save(output_path, "PNG")
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_truck_solid_fm.png"

create_solid_truck_with_text(source, output)
print("Finished creating solid truck favicon.")
