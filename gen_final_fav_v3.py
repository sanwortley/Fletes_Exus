from PIL import Image, ImageDraw, ImageFont
import os

def create_final_style_favicon_v2(source_path, output_path):
    # Abrimos el logo original del camión
    truck_orig = Image.open(source_path).convert("RGBA")
    
    # Redimensionamos para trabajar con alta calidad
    size = 512
    favicon = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    
    draw = ImageDraw.Draw(favicon)
    gold_color = (211, 161, 41, 255) # Dorado de la marca
    
    # 1. Dibujamos el fondo dorado redondeado (como en la imagen de referencia)
    margin = 40
    # Esquinas bien redondeadas
    draw.rounded_rectangle([margin, margin, size-margin, size-margin], radius=85, fill=gold_color)
    
    # 2. Procesamos el camión para que sea BLANCO
    tw, th = truck_orig.size
    target_th = int((size - 2*margin) * 0.35)
    ratio = target_th / th
    new_w, new_h = int(tw * ratio), target_th
    truck_resized = truck_orig.resize((new_w, new_h), Image.Resampling.LANCZOS)
    
    # Forzar que el camión sea blanco usando su máscara alpha
    # Si la imagen no tiene alpha real, podemos usar el brillo para crear una máscara
    if truck_resized.mode == 'RGBA' and any(a < 255 for a in truck_resized.getdata(3)):
        # Tiene alpha real
        mask = truck_resized.split()[3]
    else:
        # No tiene alpha real (es fondo sólido), generamos máscara basada en color oscuro
        # El logo original es dorado sobre blanco, así que el color dorado es la máscara
        gray = truck_resized.convert("L")
        # Invertimos: lo oscuro (logo) se vuelve blanco (máscara)
        from PIL import ImageOps
        mask = ImageOps.invert(gray)
        # Ajustamos umbral para que sea binario y limpio
        mask = mask.point(lambda p: 255 if p > 100 else 0)

    white_layer = Image.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
    
    # 3. Pegamos el camión blanco en el centro superior
    truck_x = (size - new_w) // 2
    truck_y = margin + int((size - 2*margin) * 0.18)
    favicon.paste(white_layer, (truck_x, truck_y), mask)
    
    # 4. Texto "FYM" en Montserrat-style (Arial Bold es lo más cercano en sistema)
    try:
        font_size = int((size - 2*margin) * 0.32)
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        font = ImageFont.load_default()
        
    text = "FYM"
    # Usamos textbbox para centrar
    t_bbox = draw.textbbox((0, 0), text, font=font)
    t_w = t_bbox[2] - t_bbox[0]
    t_h = t_bbox[3] - t_bbox[1]
    
    text_x = (size - t_w) // 2
    # Posicionamos el texto para que tenga buen balance con el camión
    text_y = truck_y + new_h + int((size - 2*margin) * 0.02)
    
    draw.text((text_x, text_y), text, font=font, fill="white")
    
    # Guardamos en PNG
    favicon.save(output_path, "PNG")
    # Tamaños extra
    favicon.resize((192, 192)).save(output_path.replace(".png", "_192.png"), "PNG")
    favicon.resize((64, 64)).save(output_path.replace(".png", "_64.png"), "PNG")
    favicon.resize((32, 32)).save(output_path.replace(".png", "_32.png"), "PNG")
    favicon.resize((16, 16)).save(output_path.replace(".png", "_16.png"), "PNG")

source = r"c:\Exus MVP\Exus\frontend\images\logo_camion_nuevo.png"
output = r"c:\Exus MVP\Exus\frontend\images\favicon_fym_final_v2.png"

create_final_style_favicon_v2(source, output)
print("Favicon FYM Final V2 generado exitosamente.")
