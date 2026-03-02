from PIL import Image, ImageDraw, ImageFont
import os

def create_final_style_favicon(source_path, output_path):
    # Abrimos el logo original del camión
    truck = Image.open(source_path).convert("RGBA")
    
    # Creamos un lienzo cuadrado de alta calidad (512x512)
    size = 512
    favicon = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    
    draw = ImageDraw.Draw(favicon)
    gold_color = (211, 161, 41, 255) # Dorado de la marca
    
    # 1. Dibujamos el fondo dorado redondeado (como en la imagen de referencia)
    # Dejamos un pequeño margen para que se vea bien
    margin = 40
    draw.rounded_rectangle([margin, margin, size-margin, size-margin], radius=80, fill=gold_color)
    
    # 2. Procesamos el camión para que sea BLANCO
    # Primero lo redimensionamos para que entre en la parte superior
    tw, th = truck.size
    # Queremos que ocupe aprox el 40-45% del alto total dentro del cuadro dorado
    target_th = int((size - 2*margin) * 0.35)
    ratio = target_th / th
    new_w, new_h = int(tw * ratio), target_th
    truck_resized = truck.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Convertimos el camión a blanco: tomamos el alfa y creamos una capa blanca con ese alfa
    white_truck = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
    alpha = truck_resized.split()[3]
    
    # 3. Pegamos el camión blanco en la parte superior del cuadro
    truck_x = (size - new_w) // 2
    truck_y = margin + int((size - 2*margin) * 0.15) # Un poco bajado del tope
    favicon.paste(white_truck, (truck_x, truck_y), alpha)
    
    # 4. Agregamos el texto "FYM" en la parte inferior
    try:
        # Usamos una fuente muy bold/pesada
        font_size = int((size - 2*margin) * 0.28)
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        font = ImageFont.load_default()
        
    text = "FYM"
    bbox = draw.textbbox((0, 0), text, font=font)
    t_w = bbox[2] - bbox[0]
    t_h = bbox[3] - bbox[1]
    
    text_x = (size - t_w) // 2
    # El texto va debajo del camión
    text_y = truck_y + new_h + int((size - 2*margin) * 0.05)
    
    draw.text((text_x, text_y), text, font=font, fill="white")
    
    # Guardamos los resultados
    favicon.save(output_path, "PNG")
    # Generamos los tamaños necesarios para Apple, Android y Web
    favicon.resize((192, 192)).save(output_path.replace(".png", "_192.png"), "PNG")
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")
    favicon.resize((16, 16)).save(output_path.replace(".png", "_16.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_final_truck_fym.png"

create_final_style_favicon(source, output)
print("Favicon Estilo Final (Camión Blanco + FYM) generado con éxito.")
