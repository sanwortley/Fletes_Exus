from PIL import Image, ImageDraw, ImageFont
import os

def create_fym_truck_favicon_v2(source_path, output_path):
    # Abrimos el logo original del camión
    truck = Image.open(source_path).convert("RGBA")
    
    # Creamos un lienzo cuadrado transparente
    size = 512
    favicon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Posición centrada
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    
    # Pegamos el camión completo como base
    favicon.paste(truck_resized, (offset_x, offset_y), truck_resized)
    
    draw = ImageDraw.Draw(favicon)
    gold_color = (211, 161, 41, 255) # Dorado de la marca
    
    # Dibujamos un bloque SOLIDO para la carga (TAPANDO las rejas)
    # Definimos el área de la caja (cargo)
    cargo_x1 = offset_x + int(new_w * 0.40)
    cargo_y1 = offset_y + int(new_h * 0.28)
    cargo_x2 = offset_x + new_w
    cargo_y2 = offset_y + int(new_h * 0.85)
    
    # Bloque sólido dorado
    draw.rounded_rectangle([cargo_x1, cargo_y1, cargo_x2, cargo_y2], radius=12, fill=gold_color)
    
    # Agregamos el texto "FYM" en blanco
    try:
        # Buscamos una fuente pesada
        font = ImageFont.truetype("arialbd.ttf", int((cargo_y2 - cargo_y1) * 0.65))
    except:
        font = ImageFont.load_default()
        
    text = "FYM"
    bbox = draw.textbbox((0, 0), text, font=font)
    t_w = bbox[2] - bbox[0]
    t_h = bbox[3] - bbox[1]
    
    text_x = cargo_x1 + (cargo_x2 - cargo_x1 - t_w) // 2
    text_y = cargo_y1 + (cargo_y2 - cargo_y1 - t_h) // 2 - bbox[1]
    
    draw.text((text_x, text_y), text, font=font, fill="white")
    
    # Guardamos los resultados
    favicon.save(output_path, "PNG")
    # Generamos tamaños estándar para favicons
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")
    favicon.resize((16, 16)).save(output_path.replace(".png", "_16.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_fym_final.png"

create_fym_truck_favicon_v2(source, output)
print("Favicon FYM Final generado.")
