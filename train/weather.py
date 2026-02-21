import requests
from metar import Metar
import torch
from typing import Optional, List

class WeatherFetcher:
    def __init__(self, station_id: str = "KSEA"):
        self.station_id = station_id
        self.base_url = f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{station_id.upper()}.TXT"

    def fetch_latest_metar(self) -> Optional[str]:
        try:
            response = requests.get(self.base_url, timeout=10)
            if response.status_code == 200:
                # METAR text is usually on the second line
                lines = response.text.strip().split('\n')
                return lines[-1] if lines else None
        except Exception as e:
            print(f"Error fetching METAR: {e}")
        return None

    def get_weather_vector(self) -> torch.Tensor:
        """
        Extracts visibility and ceiling into a 2D normalized vector.
        Defaults to [0, 0] if fetching fails.
        """
        metar_text = self.fetch_latest_metar()
        vis = 0.0
        ceil = 0.0
        
        if metar_text:
            try:
                obs = Metar.Metar(metar_text)
                # Visibility in miles (capped at 10)
                if obs.vis:
                    vis = min(obs.vis.value('SM'), 10.0) / 10.0
                
                # Ceiling in hundreds of feet (capped at 10000ft)
                if obs.sky:
                    # Find the lowest broken or overcast layer
                    layers = [l for l in obs.sky if l[0] in ['BKN', 'OVC']]
                    if layers:
                        ceil = min(layers[0][1].value('FT'), 10000.0) / 10000.0
                    else:
                        ceil = 1.0 # Clear sky
                else:
                    ceil = 1.0
            except Exception as e:
                print(f"Error parsing METAR: {e}")
        
        return torch.tensor([vis, ceil], dtype=torch.float32)

if __name__ == "__main__":
    fetcher = WeatherFetcher("KSEA")
    print(f"Weather Vector: {fetcher.get_weather_vector()}")
