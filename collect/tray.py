import logging
import subprocess
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Optional

import rumps

logger = logging.getLogger(__name__)

_SECS_PER_DAY = 86400


class MountainTray(rumps.App):
    def __init__(self, session_id: str, data_root: str = "data", interval: int = 600):
        super().__init__("Mountain Collector", title="🗻", quit_button=None)
        self.session_id = session_id
        self.data_root = Path(data_root).absolute()
        self.interval = interval
        self.daily_target = _SECS_PER_DAY // max(interval, 1)

        self.capture_count = 0
        self.current_status = "Initializing..."
        self._stop_event = threading.Event()
        self._next_capture_at: Optional[datetime] = None

        self.status_item = rumps.MenuItem(f"Status: {self.current_status}")
        self.progress_item = rumps.MenuItem(self._progress_str())
        self.next_item = rumps.MenuItem(self._next_str())
        self.session_item = rumps.MenuItem(f"Session: {self.session_id}")

        self.menu = [
            self.status_item,
            self.progress_item,
            self.next_item,
            rumps.separator,
            self.session_item,
            rumps.separator,
            rumps.MenuItem("Open Data Folder", callback=self.on_open_folder),
            rumps.separator,
            rumps.MenuItem("Quit Capture Job", callback=self.on_quit),
        ]

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _progress_str(self) -> str:
        pct = min(100, int(self.capture_count / self.daily_target * 100))
        return f"Progress: {self.capture_count}/{self.daily_target} ({pct}%)"

    def _next_str(self) -> str:
        if self._next_capture_at is None:
            return "Next Capture: —"
        return f"Next Capture: {self._next_capture_at.strftime('%H:%M:%S')}"

    # ------------------------------------------------------------------
    # State update (called from service loop thread)
    # ------------------------------------------------------------------

    def update_state(self, status: str = None, success: bool = True):
        if success:
            self.capture_count += 1
            self._next_capture_at = datetime.now() + timedelta(seconds=self.interval)
        if status:
            self.current_status = status
        self.status_item.title = f"Status: {self.current_status}"
        self.progress_item.title = self._progress_str()
        self.next_item.title = self._next_str()

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def on_open_folder(self, _):
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(self.data_root)])
        else:
            subprocess.Popen(["xdg-open", str(self.data_root)])

    def on_quit(self, _):
        logger.info("Quitting tray...")
        self._stop_event.set()
        rumps.quit_application()

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, service_func: Callable, interval: int = None):
        """Runs the tray icon; service_func is called on each capture cycle."""
        if interval is not None:
            self.interval = interval
            self.daily_target = _SECS_PER_DAY // max(interval, 1)

        logger.info("Starting icon.run()...")

        def service_loop():
            self.current_status = "Running"
            while not self._stop_event.is_set():
                try:
                    self.update_state(status="Capturing...", success=False)
                    success = service_func()
                    self.update_state(status="Idle", success=success)
                    for _ in range(self.interval):
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
    tray = MountainTray("test-uuid", interval=600)
    tray.run(lambda: True)
