import os
import sys
import threading
import time
import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw
import logging
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Callable, Optional

logger = logging.getLogger(__name__)

class MountainTray:
    def __init__(self, session_id: str, data_root: str = "data"):
        self.icon = None
        self.stop_event = threading.Event()
        self.session_id = session_id
        self.data_root = Path(data_root).absolute()
        
        # State for menu items
        self.last_capture_time = "Never"
        self.start_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.capture_count = 0
        self.current_status = "Initializing..."

    def create_image(self, width=64, height=64, color1="blue", color2="white"):
        """Creates a simple placeholder icon like transit-tracker."""
        image = Image.new('RGB', (width, height), color1)
        dc = ImageDraw.Draw(image)
        dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
        dc.rectangle((0, height // 2, width // 2, height), fill=color2)
        return image

    def on_quit(self, icon, item):
        logger.info("Quitting tray...")
        self.stop_event.set()
        icon.stop()

    def on_open_folder(self, icon, item):
        """Opens the specific session data directory in Finder."""
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(self.data_root)])
        else:
            subprocess.Popen(["xdg-open", str(self.data_root)])

    def update_state(self, status: str = None, success: bool = True):
        """Updates the internal state of the tray icon."""
        if success:
            self.last_capture_time = datetime.now().strftime("%H:%M:%S")
            self.capture_count += 1
        
        if status:
            self.current_status = status
        
        if self.icon:
            self.icon.update_menu()

    def setup_tray(self):
        # Use simpler static strings first to rule out dynamic text issues
        menu = pystray.Menu(
            item(lambda _: f"Status: {self.current_status}", None, enabled=False),
            item(lambda _: f"UUID: {self.session_id}", None, enabled=False),
            item(lambda _: f"Start Date: {self.start_date_str}", None, enabled=False),
            item(lambda _: f"Last Capture: {self.last_capture_time}", None, enabled=False),
            item(lambda _: f"Capture Count: {self.capture_count}", None, enabled=False),
            pystray.Menu.SEPARATOR,
            item(f"Folder: {self.data_root.name}", self.on_open_folder),
            pystray.Menu.SEPARATOR,
            item('Quit Capture Job', self.on_quit)
        )
        
        # Use a simpler name for the icon
        self.icon = pystray.Icon(
            "mountain_collector",
            self.create_image(),
            f"Mountain Collector ({self.session_id})",
            menu
        )

    def run(self, service_func: Callable, interval: int):
        """Runs the tray icon and the service function loop."""
        self.setup_tray()
        
        def service_loop():
            self.current_status = "Running"
            while not self.stop_event.is_set():
                try:
                    self.current_status = "Capturing..."
                    if self.icon: self.icon.update_menu()
                    
                    success = service_func()
                    
                    self.update_state(status="Idle", success=success)
                    
                    for _ in range(interval):
                        if self.stop_event.is_set():
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Error in service loop: {e}")
                    self.current_status = "Error"
                    if self.icon: self.icon.update_menu()
                    time.sleep(10)
        
        t = threading.Thread(target=service_loop, daemon=True)
        t.start()

        logger.info("Starting icon.run()...")
        self.icon.run()
        logger.info("icon.run() has returned.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tray = MountainTray("test-uuid")
    tray.run(lambda: True, 5)
