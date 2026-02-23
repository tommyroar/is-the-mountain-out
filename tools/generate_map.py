import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Precise Web Mercator Projection
# For @2x images, the world width at zoom Z is 512 * 2^Z pixels.
def get_world_coords(lat, lon, zoom):
    scale = 512 * (2 ** zoom)
    x = (lon + 180) * (scale / 360)
    lat_rad = math.radians(lat)
    y = (scale / (2 * math.pi)) * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))
    return x, y

def lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, img_w, img_h):
    tx, ty = get_world_coords(lat, lon, zoom)
    cx, cy = get_world_coords(center_lat, center_lon, zoom)
    return (tx - cx) + (img_w / 2), (ty - cy) + (img_h / 2)

def draw_callout(img, draw, px, py, emoji_hex, title, subtitle, font_bold, font_small):
    # 1. Fetch Emoji (Twemoji 72x72)
    emoji_url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{emoji_hex}.png"
    emoji_img = Image.open(io.BytesIO(requests.get(emoji_url).content)).convert("RGBA").resize((56, 56))
    
    # 2. Layout
    title_w = draw.textbbox((0, 0), title, font=font_bold)[2]
    sub_w = draw.textbbox((0, 0), subtitle, font=font_small)[2]
    text_w = max(title_w, sub_w)
    
    padding = 16
    box_w = 56 + text_w + (padding * 3)
    box_h = 56 + (padding * 2)
    
    bx, by = int(px - box_w / 2), int(py - box_h - 40)
    
    # 3. Shadow Layer
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    off = 6
    s_poly = [(bx+off, by+off), (bx+box_w+off, by+off), (bx+box_w+off, by+box_h+off), 
              (px+15+off, by+box_h+off), (px+off, py+off), (px-15+off, by+box_h+off), (bx+off, by+box_h+off)]
    s_draw.rounded_rectangle([bx+off, by+off, bx+box_w+off, by+box_h+off], radius=12, fill=(0,0,0,80))
    s_draw.polygon(s_poly, fill=(0,0,0,80))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(10)), (0,0), shadow.filter(ImageFilter.GaussianBlur(10)))

    # 4. Bubble
    bubble_poly = [(px-15, by+box_h), (px, py), (px+15, by+box_h)]
    draw.rounded_rectangle([bx, by, bx+box_w, by+box_h], radius=12, fill=(255,255,255,250), outline=(0,0,0,30), width=2)
    draw.polygon(bubble_poly, fill=(255,255,255,250), outline=(0,0,0,30))
    draw.polygon(bubble_poly, fill=(255,255,255,250)) # Hide overlap
    
    # 5. Content
    img.paste(emoji_img, (bx+padding, by+padding), emoji_img)
    draw.text((bx+padding+56+padding, by+padding-2), title, font=font_bold, fill=(20,20,20))
    draw.text((bx+padding+56+padding, by+padding+32), subtitle, font=font_small, fill=(120,120,120))
    
    # 6. Target Point (Small confirmation dot)
    draw.ellipse([px-4, py-4, px+4, py+4], fill=(0,0,0,150))

def generate_map():
    with open("mountain.toml", "rb") as f: config = tomllib.load(f)
    with open("mapbox.key", "r") as f: token = f.read().strip()

    # Points
    mtn, cam, weather = config['mountain'], config['webcam'], config['weather']
    targets = [
        {"name": "Mount Rainier", "lat": mtn['latitude'], "lon": mtn['longitude'], "hex": "1f3d4"},
        {"name": "UW ATG Webcam", "lat": cam['latitude'], "lon": cam['longitude'], "hex": "1f3a5"},
        {"name": "KSEA METAR", "lat": weather['latitude'], "lon": weather['longitude'], "hex": "1f6ec"}
    ]

    # Calculate geographic center of ALL points
    all_lats = [t['lat'] for t in targets]
    all_lons = [t['lon'] for t in targets]
    avg_lat, avg_lon = sum(all_lats)/3, sum(all_lons)/3

    # Fetch @2x background
    width, height, zoom = 1000, 800, 8
    print(f"Requesting map background (Zoom {zoom})...")
    url = f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/{avg_lon},{avg_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    res = requests.get(url, headers={"Referer": "https://tommyroar.github.io"})
    
    img = Image.open(io.BytesIO(res.content)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    try:
        font_b = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
        font_s = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 20)
    except: font_b = font_s = ImageFont.load_default()

    for t in targets:
        px, py = lat_lon_to_pixel(t['lat'], t['lon'], avg_lat, avg_lon, zoom, width*2, height*2)
        draw_callout(img, draw, px, py, t['hex'], t['name'], f"{t['lat']:.4f}, {t['lon']:.4f}", font_b, font_s)

    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Accurately annotated map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
