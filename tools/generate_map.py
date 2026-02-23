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
    # Mapbox requires the custom marker URLs to be double-percent-encoded.
    def get_emoji_marker(emoji, color_hex, lon, lat):
        import urllib.parse
        # Double encode the emoji character so it survives the Mapbox URL parsing
        encoded_emoji = urllib.parse.quote(emoji)
        emoji_url = f"https://emojicdn.elk.sh/{encoded_emoji}"
        # Final encoding for the Mapbox Static API overlay part
        encoded_url = urllib.parse.quote(emoji_url, safe='')
        return f"url-{encoded_url}({lon},{lat})"

    markers = [
        get_emoji_marker("🏔️", "f44336", mtn['longitude'], mtn['latitude']),
        get_emoji_marker("🎥", "2196f3", cam['longitude'], cam['latitude']),
        get_emoji_marker("🛬", "4caf50", weather['longitude'], weather['latitude'])
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
