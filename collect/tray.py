import logging
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

import rumps

logger = logging.getLogger(__name__)


class MountainTray(rumps.App):
    def __init__(self, session_id: str, data_root: str = "data"):
        super().__init__("Mountain Collector", title="🗻", quit_button=None)
        self.session_id = session_id
        self.data_root = Path(data_root).absolute()
        self.start_date_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.capture_count = 0
        self.last_capture_time = "Never"
        self.current_status = "Initializing..."
        self._stop_event = threading.Event()

        self.status_item = rumps.MenuItem(f"Status: {self.current_status}")
        self.session_item = rumps.MenuItem(f"Session: {self.session_id}")
        self.start_item = rumps.MenuItem(f"Started: {self.start_date_str}")
        self.last_capture_item = rumps.MenuItem(f"Last Capture: {self.last_capture_time}")
        self.count_item = rumps.MenuItem(f"Captures: {self.capture_count}")

        self.menu = [
            self.status_item,
            self.session_item,
            self.start_item,
            self.last_capture_item,
            self.count_item,
            rumps.separator,
            rumps.MenuItem("Open Data Folder", callback=self.on_open_folder),
            rumps.separator,
            rumps.MenuItem("Quit Capture Job", callback=self.on_quit),
        ]

    def update_state(self, status: str = None, success: bool = True):
        """Called by the service loop after each capture."""
        if success:
            self.last_capture_time = datetime.now().strftime("%H:%M:%S")
            self.capture_count += 1
        if status:
            self.current_status = status
        self.status_item.title = f"Status: {self.current_status}"
        self.last_capture_item.title = f"Last Capture: {self.last_capture_time}"
        self.count_item.title = f"Captures: {self.capture_count}"

    def on_open_folder(self, _):
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(self.data_root)])
        else:
            subprocess.Popen(["xdg-open", str(self.data_root)])

    def on_quit(self, _):
        logger.info("Quitting tray...")
        self._stop_event.set()
        rumps.quit_application()

    def run(self, service_func: Callable, interval: int):
        """Runs the tray icon and the service function loop in a background thread."""
        logger.info("Starting icon.run()...")

        def service_loop():
            self.current_status = "Running"
            while not self._stop_event.is_set():
                try:
                    self.update_state(status="Capturing...", success=False)
                    success = service_func()
                    self.update_state(status="Idle", success=success)
                    for _ in range(interval):
                        if self._stop_event.is_set():
                            break
                        time.sleep(1)
                except Exception as e:
                    logger.error(f"Error in service loop: {e}")
                    self.update_state(status="Error", success=False)
                    time.sleep(10)

        t = threading.Thread(target=service_loop, daemon=True)
        t.start()
        super().run()
        logger.info("icon.run() has returned.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tray = MountainTray("test-uuid")
    tray.run(lambda: True, 5)
