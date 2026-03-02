from PIL import Image, ImageDraw, ImageFont
import os

def create_fym_truck_favicon(source_path, output_path):
    # Abrimos el logo original del camión
    truck = Image.open(source_path).convert("RGBA")
    
    # Creamos un lienzo cuadrado de 512x512 para trabajar con alta calidad
    size = 512
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    
    tw, th = truck.size
    ratio = min(size / tw, (size*0.8) / th)
    new_w, new_h = int(tw * ratio), int(th * ratio)
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Posición centrada
    offset_x = (size - new_w) // 2
    offset_y = (size - new_h) // 2
    
    draw = ImageDraw.Draw(favicon)
    gold_color = (211, 161, 41, 255) # Dorado de la marca
    
    # 1. Pegamos solo la CABINA del camión (recortamos las rejas)
    # En la imagen original, la cabina ocupa aprox el primer 40% del ancho
    cab_width = int(new_w * 0.42)
    cab_img = truck_resized.crop((0, 0, cab_width, new_h))
    favicon.paste(cab_img, (offset_x, offset_y), cab_img)
    
    # 2. Pegamos las RUEDAS (para mantener la forma de camión)
    # Las ruedas están en la parte inferior. Simplemente usamos la capa alpha del original
    # pero solo en la zona de las ruedas
    wheels_y = int(new_h * 0.7)
    wheels_img = truck_resized.crop((0, wheels_y, new_w, new_h))
    favicon.paste(wheels_img, (offset_x, offset_y + wheels_y), wheels_img)

    # 3. Dibujamos un bloque SOLIDO para la carga (reemplazando las rejas)
    box_x1 = offset_x + cab_width - 5 # Un pequeño solape para que no haya hueco
    box_y1 = offset_y + int(new_h * 0.28)
    box_x2 = offset_x + new_w
    box_y2 = offset_y + wheels_y + 10 # Un poco debajo del inicio de las ruedas
    
    draw.rounded_rectangle([box_x1, box_y1, box_x2, box_y2], radius=8, fill=gold_color)
    
    # 4. Agregamos el texto "FYM" en blanco, bien grande y centrado en el bloque
    try:
        # Intentamos usar una fuente bold pesada para que destaque
        font = ImageFont.truetype("arialbd.ttf", int((box_y2 - box_y1) * 0.7))
    except:
        font = ImageFont.load_default()
        
    text = "FYM"
    bbox = draw.textbbox((0, 0), text, font=font)
    t_w = bbox[2] - bbox[0]
    t_h = bbox[3] - bbox[1]
    
    text_x = box_x1 + (box_x2 - box_x1 - t_w) // 2
    text_y = box_y1 + (box_y2 - box_y1 - t_h) // 2 - bbox[1]
    
    draw.text((text_x, text_y), text, font=font, fill="white")
    
    # Guardamos los resultados
    favicon.save(output_path, "PNG")
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")
    favicon.resize((16, 16)).save(output_path.replace(".png", "_16.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_fym_truck.png"

create_fym_truck_favicon(source, output)
print("Favicon FYM Truck generado exitosamente.")
