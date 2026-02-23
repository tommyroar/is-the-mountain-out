import requests
import tomllib
import math
import io
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Geographic to Pixel Projection (Web Mercator)
def lat_lon_to_pixel(lat, lon, center_lat, center_lon, zoom, width, height):
    map_width = 256 * (2 ** zoom)
    def get_x(l): return (l + 180) * (map_width / 360)
    def get_y(l):
        lat_rad = math.radians(l)
        return (map_width / (2 * math.pi)) * (math.pi - math.log(math.tan(math.pi / 4 + lat_rad / 2)))
    
    center_x, center_y = get_x(center_lon), get_y(center_lat)
    target_x, target_y = get_x(lon), get_y(lat)
    
    return (target_x - center_x) * 2 + (width / 2), (target_y - center_y) * 2 + (height / 2)

def draw_callout(draw, img, px, py, emoji_hex, title, subtitle, font_bold, font_small):
    # 1. Fetch Emoji
    emoji_url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{emoji_hex}.png"
    emoji_img = Image.open(io.BytesIO(requests.get(emoji_url).content)).convert("RGBA").resize((64, 64))
    
    # 2. Calculate dimensions
    title_bbox = draw.textbbox((0, 0), title, font=font_bold)
    sub_bbox = draw.textbbox((0, 0), subtitle, font=font_small)
    text_w = max(title_bbox[2], sub_bbox[2])
    text_h = (title_bbox[3] - title_bbox[1]) + (sub_bbox[3] - sub_bbox[1]) + 5
    
    padding = 15
    box_w = 64 + text_w + (padding * 3)
    box_h = max(64, text_h) + (padding * 2)
    
    # Position bubble above the point
    bx = int(px - box_w / 2)
    by = int(py - box_h - 30) # 30px offset for pointer
    
    # 3. Create Callout + Shadow Layer
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d_overlay = ImageDraw.Draw(overlay)
    d_shadow = ImageDraw.Draw(shadow)
    
    bubble_shape = [bx, by, bx + box_w, by + box_h]
    pointer_shape = [(px - 15, by + box_h), (px + 15, by + box_h), (px, py)]
    
    # Draw Shadow (Offset and Blurred)
    shadow_offset = 6
    s_bx, s_by = bx + shadow_offset, by + shadow_offset
    d_shadow.rounded_rectangle([s_bx, s_by, s_bx + box_w, s_by + box_h], radius=15, fill=(0, 0, 0, 100))
    d_shadow.polygon([(p[0] + shadow_offset, p[1] + shadow_offset) for p in pointer_shape], fill=(0, 0, 0, 100))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))
    
    # Draw Bubble
    d_overlay.rounded_rectangle(bubble_shape, radius=15, fill=(255, 255, 255, 245), outline=(0, 0, 0, 40), width=2)
    d_overlay.polygon(pointer_shape, fill=(255, 255, 255, 245), outline=(0, 0, 0, 40))
    # Fill pointer again to hide the bubble outline overlap
    d_overlay.polygon(pointer_shape, fill=(255, 255, 255, 245))
    
    # 4. Composite and add content
    img.paste(shadow, (0, 0), shadow)
    img.paste(overlay, (0, 0), overlay)
    
    img.paste(emoji_img, (bx + padding, by + int((box_h - 64)/2)), emoji_img)
    draw.text((bx + padding + 64 + padding, by + padding), title, font=font_bold, fill=(20, 20, 20))
    draw.text((bx + padding + 64 + padding, by + padding + 35), subtitle, font=font_small, fill=(100, 100, 100))

def generate_map():
    with open("mountain.toml", "rb") as f: config = tomllib.load(f)
    with open("mapbox.key", "r") as f: token = f.read().strip()

    width, height, zoom = 1000, 800, 8
    style = "mapbox/outdoors-v12"
    
    mtn, cam, weather = config['mountain'], config['webcam'], config['weather']
    avg_lon, avg_lat = (mtn['longitude'] + cam['longitude']) / 2, (mtn['latitude'] + cam['latitude']) / 2

    print(f"Fetching map background (Zoom {zoom})...")
    url = f"https://api.mapbox.com/styles/v1/{style}/static/{avg_lon},{avg_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    img_res = requests.get(url, headers={"Referer": "https://tommyroar.github.io"})
    if img_res.status_code != 200: return print(f"Error: {img_res.status_code}")

    img = Image.open(io.BytesIO(img_res.content)).convert("RGBA")
    draw = ImageDraw.Draw(img)
    
    try:
        font_bold = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
        font_small = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
    except: font_bold = font_small = ImageFont.load_default()

    targets = [
        {"name": "Mount Rainier", "lat": mtn['latitude'], "lon": mtn['longitude'], "hex": "1f3d4"},
        {"name": "UW ATG Webcam", "lat": cam['latitude'], "lon": cam['longitude'], "hex": "1f3a5"},
        {"name": "KSEA METAR", "lat": weather['latitude'], "lon": weather['longitude'], "hex": "1f6ec"}
    ]

    for t in targets:
        px, py = lat_lon_to_pixel(t['lat'], t['lon'], avg_lat, avg_lon, zoom, width*2, height*2)
        draw_callout(draw, img, px, py, t['hex'], t['name'], f"{t['lat']:.4f}, {t['lon']:.4f}", font_bold, font_small)

    Path("assets").mkdir(exist_ok=True)
    img.save("assets/map.png")
    print("Callout-annotated map saved to assets/map.png")

if __name__ == "__main__":
    generate_map()
