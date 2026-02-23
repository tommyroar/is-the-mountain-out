import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Precise Web Mercator for Mapbox @2x (512px tiles)
def lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, img_w, img_h):
    world_size = 512 * (2 ** zoom)
    
    def x_from_lon(l):
        return (l + 180) * (world_size / 360)
    
    def y_from_lat(l):
        r = math.radians(l)
        # Note: top is 0, bottom is world_size
        return (1 - (math.log(math.tan(r) + 1/math.cos(r)) / math.pi)) / 2 * world_size

    cx, cy = x_from_lon(center_lon), y_from_lat(center_lat)
    tx, ty = x_from_lon(lon), y_from_lat(lat)
    
    return (tx - cx) + (img_w / 2), (ty - cy) + (img_h / 2)

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
    
    # 3. Combined Shadow Layer
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

    # Calculate geographic center of ALL points
    all_lats = [t['lat'] for t in targets]
    all_lons = [t['lon'] for t in targets]
    avg_lat, avg_lon = sum(all_lats)/3, sum(all_lons)/3

    width, height, zoom = 1000, 800, 8
    print(f"Requesting Mapbox base (Zoom {zoom}). center={avg_lat},{avg_lon}")
    
    # URL including markers so we can verify positions visually (they'll be under the callouts)
    markers_url = f"pin-s-m+f44336({mtn['longitude']},{mtn['latitude']}),pin-s-c+2196f3({cam['longitude']},{cam['latitude']}),pin-s-w+4caf50({weather['longitude']},{weather['latitude']})"
    url = f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/{markers_url}/{avg_lon},{avg_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    
    res = requests.get(url, headers={"Referer": "https://tommyroar.github.io"})
    if res.status_code != 200: return print(f"Error: {res.status_code}")
    
    img = Image.open(io.BytesIO(res.content)).convert("RGBA")
    
    try:
        font_b = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
        font_s = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except: font_b = font_s = ImageFont.load_default()

    for t in targets:
        px, py = lat_lon_to_pixel(t['lat'], t['lon'], avg_lat, avg_lon, zoom, width*2, height*2)
        draw_callout(img, px, py, t['hex'], t['name'], f"{t['lat']:.4f}, {t['lon']:.4f}", font_b, font_s)

    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Accurate emoji-callout map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
