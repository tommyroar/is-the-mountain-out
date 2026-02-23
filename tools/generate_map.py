import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# Geographic to Pixel Projection (Web Mercator)
def lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, width, height):
    # Standard Web Mercator constants
    map_width = 256 * (2 ** zoom)
    
    def get_x(l):
        return (l + 180) * (map_width / 360)
    
    def get_y(l):
        lat_rad = math.radians(l)
        return (map_width / (2 * math.pi)) * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))

    center_x = get_x(center_lon)
    center_y = get_y(center_lat)
    
    target_x = get_x(lon)
    target_y = get_y(lat)
    
    # Pixel coordinates relative to center
    pixel_x = (target_x - center_x) * 2 + (width / 2) # *2 for @2x
    pixel_y = (target_y - center_y) * 2 + (height / 2)
    
    return pixel_x, pixel_y

def generate_map():
    # Load config
    with open("mountain.toml", "rb") as f:
        config = tomllib.load(f)
    with open("mapbox.key", "r") as f:
        token = f.read().strip()

    # Settings
    width, height = 1000, 800
    zoom = 8
    style = "mapbox/outdoors-v12"
    
    mtn = config['mountain']
    cam = config['webcam']
    weather = config['weather']
    
    # Calculate center
    avg_lon = (mtn['longitude'] + cam['longitude']) / 2
    avg_lat = (mtn['latitude'] + cam['latitude']) / 2

    # 1. Download clean background
    print(f"Fetching clean map background (Zoom {zoom})...")
    url = f"https://api.mapbox.com/styles/v1/{style}/static/{avg_lon},{avg_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    headers = {"Referer": "https://tommyroar.github.io"}
    response = requests.get(url, headers=headers)
    
    if response.status_code != 200:
        print(f"Error: {response.status_code}\n{response.text}")
        return

    img = Image.open(io.BytesIO(response.content)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    # Load Fonts (macOS paths)
    try:
        font_bold = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except:
        font_bold = font_small = ImageFont.load_default()

    # Targets to draw
    targets = [
        {"name": "Mount Rainier", "lat": mtn['latitude'], "lon": mtn['longitude'], "hex": "1f3d4", "color": (244, 67, 54)},
        {"name": "UW ATG Webcam", "lat": cam['latitude'], "lon": cam['longitude'], "hex": "1f3a5", "color": (33, 150, 243)},
        {"name": "KSEA METAR", "lat": weather['latitude'], "lon": weather['longitude'], "hex": "1f6ec", "color": (76, 175, 80)}
    ]

    for t in targets:
        px, py = lat_lon_to_pixel(t['lat'], t['lon'], avg_lat, avg_lon, zoom, width*2, height*2)
        
        # 2. Draw Drop Shadow (Blurred black circle)
        shadow_size = 45
        draw.ellipse([px-shadow_size, py-shadow_size, px+shadow_size, py+shadow_size], fill=(0,0,0,80))
        
        # 3. Download and Draw Emoji
        emoji_url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{t['hex']}.png"
        e_res = requests.get(emoji_url)
        if e_res.status_code == 200:
            emoji_img = Image.open(io.BytesIO(e_res.content)).convert("RGBA")
            # Resize slightly if needed
            emoji_img = emoji_img.resize((72, 72))
            img.paste(emoji_img, (int(px-36), int(py-36)), emoji_img)

        # 4. Draw Label
        label_text = f"{t['name']}\n({t['lat']:.3f}, {t['lon']:.3f})"
        
        # Background box for readability
        tw, th = draw.textbbox((0, 0), label_text, font=font_small)[2:]
        draw.rectangle([px + 45, py - 30, px + 55 + tw, py + 10 + th], fill=(255,255,255,200), outline=(0,0,0,50))
        
        # Text
        draw.text((px + 50, py - 25), t['name'], font=font_bold, fill=(30, 30, 30))
        draw.text((px + 50, py + 10), f"{t['lat']:.4f}, {t['lon']:.4f}", font=font_small, fill=(100, 100, 100))

    # Save
    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Professionally annotated map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
