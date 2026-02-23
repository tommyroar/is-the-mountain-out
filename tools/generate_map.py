import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Precise Web Mercator Projection for Mapbox @2x
# The world is 512 * 2^zoom pixels wide/high at @2x
def lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, img_w, img_h):
    scale = 512 * (2 ** zoom)
    
    def get_x(l): return (l + 180) * (scale / 360)
    def get_y(l):
        lat_rad = math.radians(l)
        return (scale / (2 * math.pi)) * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))

    cx, cy = get_x(center_lon), get_y(center_lat)
    tx, ty = get_x(lon), get_y(lat)
    
    return (tx - cx) + (img_w / 2), (ty - cy) + (img_h / 2)

def draw_callout(img, draw, px, py, emoji, title, subtitle, font_emoji, font_bold, font_small):
    # 1. Calculate Text Dimensions
    title_bbox = draw.textbbox((0, 0), title, font=font_bold)
    sub_bbox = draw.textbbox((0, 0), subtitle, font=font_small)
    text_w = max(title_bbox[2], sub_bbox[2])
    text_h = (title_bbox[3] - title_bbox[1]) + (sub_bbox[3] - sub_bbox[1]) + 4
    
    padding = 18
    emoji_size = 60
    box_w = emoji_size + text_w + (padding * 3)
    box_h = max(emoji_size, text_h) + (padding * 2)
    
    # Position bubble centered above the point
    bx, by = int(px - box_w / 2), int(py - box_h - 45)
    
    # 2. Draw Shadow Layer
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    s_draw = ImageDraw.Draw(shadow)
    off = 8
    s_bx, s_by = bx + off, by + off
    s_poly = [(s_bx, s_by), (s_bx+box_w, s_by), (s_bx+box_w, s_by+box_h), 
              (px+20+off, s_by+box_h), (px+off, py+off), (px-20+off, s_by+box_h), (s_bx, s_by+box_h)]
    s_draw.rounded_rectangle([s_bx, s_by, s_bx + box_w, s_by + box_h], radius=15, fill=(0, 0, 0, 70))
    s_draw.polygon(s_poly, fill=(0, 0, 0, 70))
    img.paste(shadow.filter(ImageFilter.GaussianBlur(12)), (0, 0), shadow.filter(ImageFilter.GaussianBlur(12)))

    # 3. Draw Bubble (White with thin outline)
    bubble_poly = [(px - 20, by + box_h), (px, py), (px + 20, by + box_h)]
    draw.rounded_rectangle([bx, by, bx + box_w, by + box_h], radius=15, fill=(255, 255, 255, 250), outline=(0, 0, 0, 40), width=2)
    draw.polygon(bubble_poly, fill=(255, 255, 255, 250), outline=(0, 0, 0, 40))
    draw.polygon(bubble_poly, fill=(255, 255, 255, 250)) # Hide overlap line
    
    # 4. Content
    # Use native system emoji
    draw.text((bx + padding, by + padding - 5), emoji, font=font_emoji, fill=(255, 255, 255))
    draw.text((bx + padding + emoji_size + padding, by + padding), title, font=font_bold, fill=(30, 30, 30))
    draw.text((bx + padding + emoji_size + padding, by + padding + 38), subtitle, font=font_small, fill=(120, 120, 120))
    
    # 5. Target validation dot
    draw.ellipse([px-5, py-5, px+5, py+5], fill=(0, 0, 0, 180))

def generate_map():
    with open("mountain.toml", "rb") as f: config = tomllib.load(f)
    with open("mapbox.key", "r") as f: token = f.read().strip()

    mtn, cam, weather = config['mountain'], config['webcam'], config['weather']
    targets = [
        {"name": "Mount Rainier", "lat": mtn['latitude'], "lon": mtn['longitude'], "emoji": "🏔️"},
        {"name": "UW ATG Webcam", "lat": cam['latitude'], "lon": cam['longitude'], "emoji": "🎥"},
        {"name": "KSEA METAR", "lat": weather['latitude'], "lon": weather['longitude'], "emoji": "🛬"}
    ]

    # Geographic center of targets
    avg_lat = sum(t['lat'] for t in targets) / 3
    avg_lon = sum(t['lon'] for t in targets) / 3

    width, height, zoom = 1000, 800, 8.0
    print(f"Fetching Mapbox base (Zoom {zoom})...")
    url = f"https://api.mapbox.com/styles/v1/mapbox/outdoors-v12/static/{avg_lon},{avg_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    res = requests.get(url, headers={"Referer": "https://tommyroar.github.io"})
    
    img = Image.open(io.BytesIO(res.content)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    # macOS Fonts
    try:
        font_emoji = ImageFont.truetype("/System/Library/Fonts/Apple Color Emoji.ttc", 54)
        font_bold = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 32)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except:
        font_emoji = font_bold = font_small = ImageFont.load_default()

    for t in targets:
        px, py = lat_lon_to_pixel(t['lat'], t['lon'], avg_lat, avg_lon, zoom, width*2, height*2)
        draw_callout(img, draw, px, py, t['emoji'], t['name'], f"{t['lat']:.4f}, {t['lon']:.4f}", font_emoji, font_bold, font_small)

    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Accurate emoji-callout map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
