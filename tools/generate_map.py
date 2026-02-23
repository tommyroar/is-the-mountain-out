import requests
import tomllib
from pathlib import Path

def generate_map():
    # Load config
    with open("mountain.toml", "rb") as f:
        config = tomllib.load(f)
    
    # Load key
    with open("mapbox.key", "r") as f:
        token = f.read().strip()
    
    # Coordinates
    mtn = config['mountain']
    cam = config['webcam']
    weather = config['weather']
    
    # Using custom URL markers to render high-quality actual emojis
    # 🏔️ (Mountain), 🎥 (Webcam), 🛬 (METAR)
    # Using 72x72 Twemoji assets to reduce size by ~50% (from 160x160)
    def get_emoji_marker(hex_code, lon, lat):
        import urllib.parse
        emoji_url = f"https://cdnjs.cloudflare.com/ajax/libs/twemoji/14.0.2/72x72/{hex_code}.png"
        encoded_url = urllib.parse.quote(emoji_url, safe='')
        return f"url-{encoded_url}({lon},{lat})"

    markers = [
        get_emoji_marker("1f3d4", mtn['longitude'], mtn['latitude']), # 🏔️
        get_emoji_marker("1f3a5", cam['longitude'], cam['latitude']), # 🎥
        get_emoji_marker("1f6ec", weather['longitude'], weather['latitude']) # 🛬
    ]
    
    overlay = ",".join(markers)
    style = "mapbox/outdoors-v12"
    width, height = 800, 600
    
    # Calculate center between the two most distant points
    avg_lon = (mtn['longitude'] + cam['longitude']) / 2
    avg_lat = (mtn['latitude'] + cam['latitude']) / 2
    
    # Target zoom level
    zoom = 8
    
    url = f"https://api.mapbox.com/styles/v1/{style}/static/{overlay}/{avg_lon},{avg_lat},{zoom}/{width}x{height}@2x?access_token={token}"
    
    print(f"Requesting map from Mapbox (Zoom: {zoom})...")
    headers = {"Referer": "https://tommyroar.github.io"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        Path("assets").mkdir(exist_ok=True)
        with open("assets/map.png", "wb") as f:
            f.write(response.content)
        print("Map successfully saved to assets/map.png")
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

if __name__ == "__main__":
    generate_map()
