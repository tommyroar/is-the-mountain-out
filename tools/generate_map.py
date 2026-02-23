import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Precise Web Mercator Projection
# World size at Zoom 0 is 256. At @2x Zoom Z, it is 512 * 2^Z.
def project(lat, lon, zoom):
    scale = 512 * (2 ** zoom)
    x = (lon + 180) * (scale / 360)
    lat_rad = math.radians(lat)
    y = (scale / (2 * math.pi)) * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))
    return x, y

def draw_callout(img, px, py, emoji_hex, title, subtitle, font_bold, font_small):
    draw = ImageDraw.Draw(img)
    
    # 1. Fetch Emoji (Twemoji 72x72)
    emoji_url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{emoji_hex}.png"
    emoji_img = Image.open(io.BytesIO(requests.get(emoji_url).content)).convert("RGBA").resize((60, 60))
    
    # 2. Dimensions
    title_w = draw.textbbox((0, 0), title, font=font_bold)[2]
    sub_w = draw.textbbox((0, 0), subtitle, font=font_small)[2]
    text_w = max(title_w, sub_w)
    
    padding = 18
    box_w = 60 + text_w + (padding * 3)
    box_h = 60 + (padding * 2)
    
    bx, by = int(px - box_w / 2), int(py - box_h - 45)
    
    # 3. Unified Shadow Layer
    shadow_img = Image.new("RGBA", img.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow_img)
    off = 8
    shadow_poly = [(px - 20 + off, by + box_h + off), (px + off, py + off), (px + 20 + off, by + box_h + off)]
    s_draw.rounded_rectangle([bx + off, by + off, bx + box_w + off, by + box_h + off], radius=15, fill=(0, 0, 0, 80))
    s_draw.polygon(shadow_poly, fill=(0, 0, 0, 80))
    img.paste(shadow_img.filter(ImageFilter.GaussianBlur(10)), (0, 0), shadow_img.filter(ImageFilter.GaussianBlur(10)))

    # 4. Bubble & Pointer
    pointer_poly = [(px - 20, by + box_h), (px, py), (px + 20, by + box_h)]
    draw.rounded_rectangle([bx, by, bx + box_w, by + box_h], radius=15, fill=(255, 255, 255, 250), outline=(0, 0, 0, 40), width=2)
    draw.polygon(pointer_poly, fill=(255, 255, 255, 250), outline=(0, 0, 0, 40))
    draw.polygon(pointer_poly, fill=(255, 255, 255, 250)) # Hide bubble edge
    
    # 5. Content
    img.paste(emoji_img, (bx + padding, by + padding), emoji_img)
    draw.text((bx + padding + 60 + padding, by + padding - 2), title, font=font_bold, fill=(25, 25, 25))
    draw.text((bx + padding + 60 + padding, by + padding + 35), subtitle, font=font_small, fill=(110, 110, 110))
    
    # 6. Target dot
    draw.ellipse([px-5, py-5, px+5, py+5], fill=(0, 0, 0, 180))

def generate_map():
    with open("mountain.toml", "rb") as f: config = tomllib.load(f)
    with open("mapbox.key", "r") as f: token = f.read().strip()

    mtn, cam, weather = config['mountain'], config['webcam'], config['weather']
    targets = [
        {"name": "Mount Rainier", "lat": mtn['latitude'], "lon": mtn['longitude'], "hex": "1f3d4"},
        {"name": "UW ATG Webcam", "lat": cam['latitude'], "lon": cam['longitude'], "hex": "1f3a5"},
        {"name": "KSEA METAR", "lat": weather['latitude'], "lon": weather['longitude'], "hex": "1f6ec"}
    ]

    zoom = 8
    
    # Calculate visual center in Mercator space
    world_coords = [project(t['lat'], t['lon'], zoom) for t in targets]
    avg_world_x = sum(c[0] for c in world_coords) / len(world_coords)
    avg_world_y = sum(c[1] for c in world_coords) / len(world_coords)
    
    # Convert Mercator center back to Lat/Lon for the Mapbox URL
    world_size = 512 * (2 ** zoom)
    center_lon = (avg_world_x / world_size * 360) - 180
    center_lat = math.degrees(2 * math.atan(math.exp(math.pi * (1 - 2 * avg_world_y / world_size))) - math.pi / 2)

    width, height = 1000, 800
    print(f"Requesting map background (Zoom {zoom})...")
    
    url = f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/{center_lon},{center_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    res = requests.get(url, headers={"Referer": "https://tommyroar.github.io"})
    
    img = Image.open(io.BytesIO(res.content)).convert("RGBA")
    
    try:
        font_b = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
        font_s = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except: font_b = font_s = ImageFont.load_default()

    # Place callouts using same projection
    for t in targets:
        tx, ty = project(t['lat'], t['lon'], zoom)
        # Pixel coordinates relative to the calculated world center
        px = (tx - avg_world_x) + (width) # width*2/2
        py = (ty - avg_world_y) + (height) # height*2/2
        draw_callout(img, px, py, t['hex'], t['name'], f"{t['lat']:.4f}, {t['lon']:.4f}", font_b, font_s)

    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Accurate emoji-callout map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
