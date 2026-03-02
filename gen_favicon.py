from PIL import Image, ImageDraw, ImageFont
import os

def make_favicon(size=64, output_path=None):
    # Fondo dorado
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Fondo redondeado dorado
    radius = size // 6
    color_gold = (211, 161, 41, 255)
    draw.rounded_rectangle([0, 0, size-1, size-1], radius=radius, fill=color_gold)

    # Texto F&M
    text = "F&M"
    font_size = int(size * 0.38)

    try:
        # Intentar fuente bold del sistema
        font = ImageFont.truetype("arialbd.ttf", font_size)
    except:
        try:
            font = ImageFont.truetype("Arial Bold.ttf", font_size)
        except:
            font = ImageFont.load_default()

    # Centrar texto
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (size - text_w) // 2
    y = (size - text_h) // 2 - bbox[1]

    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255))
    img.save(output_path, format="PNG")
    print(f"Favicon guardado: {output_path} ({size}x{size})")

base = r"c:\Exus MVP\Exus\frontend\images"

make_favicon(64, os.path.join(base, "favicon_fm_64.png"))
make_favicon(32, os.path.join(base, "favicon_fm_32.png"))
make_favicon(16, os.path.join(base, "favicon_fm_16.png"))

print("Listo!")
