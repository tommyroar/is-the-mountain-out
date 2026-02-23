import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Precise Web Mercator Projection for Mapbox @2x
# Mapbox static images use 512x512 tiles for @2x zoom calculation.
def project(lat, lon, zoom):
    world_size = 512 * (2 ** zoom)
    x = (lon + 180) * (world_size / 360)
    lat_rad = math.radians(lat)
    y = (world_size / (2 * math.pi)) * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))
    return x, y

def generate_map():
    with open("mountain.toml", "rb") as f: config = tomllib.load(f)
    with open("mapbox.key", "r") as f: token = f.read().strip()

    mtn, cam, weather = config['mountain'], config['webcam'], config['weather']
    targets = [
        {"name": "Mount Rainier", "lat": mtn['latitude'], "lon": mtn['longitude'], "emoji": "🏔️"},
        {"name": "UW ATG Webcam", "lat": cam['latitude'], "lon": cam['longitude'], "emoji": "🎥"},
        {"name": "KSEA METAR", "lat": weather['latitude'], "lon": weather['longitude'], "emoji": "🛬"}
    ]

    zoom = 8.0
    width, height = 1000, 800
    
    # Calculate Mercator center of all points
    world_coords = [project(t['lat'], t['lon'], zoom) for t in targets]
    avg_world_x = sum(c[0] for c in world_coords) / len(world_coords)
    avg_world_y = sum(c[1] for c in world_coords) / len(world_coords)
    
    # Convert center back to Lat/Lon for Mapbox URL
    world_size = 512 * (2 ** zoom)
    center_lon = (avg_world_x / world_size * 360) - 180
    center_lat = math.degrees(2 * math.atan(math.exp(math.pi * (1 - 2 * avg_world_y / world_size))) - math.pi / 2)

    print(f"Requesting Mapbox background (Zoom {zoom})...")
    url = f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/{center_lon},{center_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    res = requests.get(url, headers={"Referer": "https://tommyroar.github.io"})
    if res.status_code != 200: return print(f"Error: {res.status_code}")

    img = Image.open(io.BytesIO(res.content)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    try:
        font_emoji = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 48)
        font_bold = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 18)
    except: font_emoji = font_bold = font_small = ImageFont.load_default()

    for i, t in enumerate(targets):
        tx, ty = project(t['lat'], t['lon'], zoom)
        # Pixel coordinates relative to the requested center
        px = (tx - avg_world_x) + (width) # width*2/2
        py = (ty - avg_world_y) + (height) # height*2/2
        
        # 1. Shadow
        shadow_mask = Image.new("RGBA", img.size, (0,0,0,0))
        s_draw = ImageDraw.Draw(shadow_mask)
        # Draw shadow under emoji and text
        s_draw.ellipse([px-30, py-30, px+30, py+30], fill=(0,0,0,120))
        img.paste(shadow_mask.filter(ImageFilter.GaussianBlur(10)), (0,0), shadow_mask.filter(ImageFilter.GaussianBlur(10)))

        # 2. Emoji
        draw.text((px - 24, py - 24), t['emoji'], font=font_emoji, fill=(255,255,255))
        
        # 3. Label
        label_name = t['name']
        label_coords = f"{t['lat']:.4f}, {t['lon']:.4f}"
        
        # Offset label based on position to avoid overlapping (simple logic)
        lx, ly = px + 40, py - 20
        
        # Label background
        nw, nh = draw.textbbox((0,0), label_name, font=font_bold)[2:]
        cw, ch = draw.textbbox((0,0), label_coords, font=font_small)[2:]
        bg_w = max(nw, cw) + 20
        draw.rectangle([lx-5, ly-5, lx+bg_w, ly+ch+nh+15], fill=(255,255,255,220), outline=(0,0,0,40))
        
        # Label text
        draw.text((lx, ly), label_name, font=font_bold, fill=(20,20,20))
        draw.text((lx, ly + nh + 5), label_coords, font=font_small, fill=(80,80,80))

    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Professionally annotated emoji map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
