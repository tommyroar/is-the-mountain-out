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

REFRESH_INTERVAL = 10  # seconds between state file reads


class MountainTray(rumps.App):
    def __init__(self, data_root: str = "data", session_id: Optional[str] = None):
        name = f"Mountain Collector ({session_id})" if session_id else "Mountain Collector"
        super().__init__(name, title="🗻", quit_button=None)
        self.data_root = Path(data_root).absolute()
        self._last_state: Optional[CollectorState] = None

        # --- Static menu skeleton ---
        self.progress_bar_item = rumps.MenuItem("—")
        self.status_item       = rumps.MenuItem("Status: —")
        self.progress_item     = rumps.MenuItem("Progress: —")
        self.last_capture_item = rumps.MenuItem("Last Capture: —")
        self.next_item         = rumps.MenuItem("Next Capture: —")
        self.final_item        = rumps.MenuItem("Final Capture: —")
        self.session_item      = rumps.MenuItem("Session: —")
        self.open_item         = rumps.MenuItem("Open Index File", callback=self._on_open_folder)
        self.menu = [
            self.progress_bar_item,
            rumps.separator,
            self.status_item,
            self.progress_item,
            self.last_capture_item,
            self.next_item,
            self.final_item,
            rumps.separator,
            self.session_item,
            rumps.separator,
            self.open_item,
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
        # Progress bar as the first item in the menu
        bar_len = 20
        filled_len = int(round(bar_len * state.pct_complete / 100))
        bar = "█" * filled_len + "░" * (bar_len - filled_len)
        self.progress_bar_item.title = f"[{bar}] {state.pct_complete}%"

        self.status_item.title   = f"Status: {state.status}"
        total_str = str(state.plan_total) if state.plan_total > 0 else "?"
        self.progress_item.title = (
            f"Progress: {state.capture_count}/{total_str} ({state.pct_complete}%)"
        )
        last_str = _fmt_time(state.last_capture_at) or "—"
        self.last_capture_item.title = f"Last Capture: {last_str}"
        next_str = _fmt_time(state.next_capture_at) or "—"
        self.next_item.title         = f"Next Capture: {next_str}"
        final_str = _fmt_time(state.final_capture_at) or "—"
        self.final_item.title        = f"Final Capture: {final_str}"
        self.session_item.title = f"Session: {state.session_id}"
        if state.session_labels_file:
            self.open_item.title = f"Open {state.session_labels_file}"
        else:
            self.open_item.title = "Open Index File"

    # ------------------------------------------------------------------
    # Menu callbacks
    # ------------------------------------------------------------------

    def _on_open_folder(self, _):
        target = self._last_state.session_labels_file if self._last_state and self._last_state.session_labels_file else None
        if sys.platform == "darwin":
            if target and Path(target).exists():
                subprocess.Popen(["open", "-R", target])  # reveal file in Finder
            else:
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
        self._refresh()          # populate immediately on startup
        self._timer.start()
        super().run()


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _fmt_time(iso: Optional[str]) -> Optional[str]:
    """Format an ISO-8601 UTC string as local 'Mar 15 06:38' or 'Today 06:38', or None."""
    if not iso:
        return None
    try:
        from datetime import datetime, timezone
        dt = datetime.fromisoformat(iso).astimezone()
        today = datetime.now(dt.tzinfo).date()
        if dt.date() == today:
            return f"Today {dt.strftime('%H:%M')}"
        return dt.strftime("%b %-d %H:%M")
    except Exception:
        return None


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    MountainTray().run()
