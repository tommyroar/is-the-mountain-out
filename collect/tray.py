"""
MountainTray — rumps menu bar app for the capture service.

Reads collector_state.json via a rumps.Timer; entirely decoupled from
the capture loop. Any process can update the state file and the menu
will reflect it within REFRESH_INTERVAL seconds.
"""
import logging
import subprocess
import sys
from pathlib import Path
from typing import Optional

import rumps

from collect.state import CollectorState, read_state

logger = logging.getLogger(__name__)

REFRESH_INTERVAL = 5  # seconds between state file reads

_CLASS_LABELS = {"0": "Not Out", "1": "Full", "2": "Partial"}


class MountainTray(rumps.App):
    def __init__(self, data_root: str = "data"):
        super().__init__("Mountain Collector", title="🗻", quit_button=None)
        self.data_root = Path(data_root).absolute()
        self._last_state: Optional[CollectorState] = None

        # --- Static menu skeleton ---
        self.status_item   = rumps.MenuItem("Status: —")
        self.progress_item = rumps.MenuItem("Progress: —")
        self.next_item     = rumps.MenuItem("Next Capture: —")
        self.session_item  = rumps.MenuItem("Session: —")
        self.labels_header = rumps.MenuItem("Labels:")
        self.label_items   = {k: rumps.MenuItem(f"  {_CLASS_LABELS[k]}: —") for k in _CLASS_LABELS}

        self.menu = [
            self.status_item,
            self.progress_item,
            self.next_item,
            rumps.separator,
            self.session_item,
            rumps.separator,
            self.labels_header,
            *self.label_items.values(),
            rumps.separator,
            rumps.MenuItem("Open Data Folder", callback=self._on_open_folder),
            rumps.separator,
            rumps.MenuItem("Quit Capture Job", callback=self._on_quit),
        ]

        self._timer = rumps.Timer(self._refresh, REFRESH_INTERVAL)

    # ------------------------------------------------------------------
    # Timer callback — reads state file and renders
    # ------------------------------------------------------------------

    def _refresh(self, _=None) -> None:
        state = read_state(self.data_root)
        if state is None:
            self.status_item.title = "Status: No state file found"
            return
        if state == self._last_state:
            return
        self._last_state = state
        self._render(state)

    def _render(self, state: CollectorState) -> None:
        self.status_item.title   = f"Status: {state.status}"
        self.progress_item.title = (
            f"Progress: {state.capture_count}/{state.daily_target} ({state.pct_complete}%)"
        )
        next_str = _fmt_time(state.next_capture_at) or "—"
        self.next_item.title    = f"Next Capture: {next_str}"
        self.session_item.title = f"Session: {state.session_id}"

        for k, item in self.label_items.items():
            count = state.label_counts.get(k, 0)
            item.title = f"  {_CLASS_LABELS[k]}: {count}"

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_open_folder(self, _):
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(self.data_root)])
        else:
            subprocess.Popen(["xdg-open", str(self.data_root)])

    def _on_quit(self, _):
        logger.info("Quitting tray...")
        rumps.quit_application()

    # ------------------------------------------------------------------
    # Entry point
    # ------------------------------------------------------------------

    def run(self):
        self._refresh()          # populate immediately before first tick
        self._timer.start()
        super().run()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _fmt_time(iso: Optional[str]) -> Optional[str]:
    """Format an ISO-8601 UTC string as local HH:MM:SS, or None."""
    if not iso:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso).astimezone()
        return dt.strftime("%H:%M:%S")
    except Exception:
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    MountainTray().run()
