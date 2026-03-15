"""Tests for MountainTray — mocks rumps so no GUI event loop is needed."""
import sys
import types
import threading
import time
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest


# ---------------------------------------------------------------------------
# Minimal rumps stub so tray.py can be imported without a macOS GUI session
# ---------------------------------------------------------------------------

def _make_rumps_stub():
    rumps_mod = types.ModuleType("rumps")

    class MenuItem:
        def __init__(self, title, callback=None):
            self.title = title
            self.callback = callback

    class App:
        def __init__(self, name, title="", quit_button=None):
            self.name = name
            self.title = title
            self.menu = []

        def run(self):
            pass  # no-op in tests

    rumps_mod.App = App
    rumps_mod.MenuItem = MenuItem
    rumps_mod.separator = "---"
    rumps_mod.quit_application = MagicMock()
    return rumps_mod


_rumps_stub = _make_rumps_stub()
sys.modules["rumps"] = _rumps_stub

from collect.tray import MountainTray  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tray(tmp_path):
    # 600s interval → 144 captures/day
    return MountainTray(session_id="test-session-123", data_root=str(tmp_path), interval=600)


# ---------------------------------------------------------------------------
# Basic identity tests
# ---------------------------------------------------------------------------

def test_initial_title_is_mountain_emoji(tray):
    assert tray.title == "🗻"


def test_initial_status(tray):
    assert "Initializing" in tray.status_item.title


def test_session_id_shown_in_menu(tray):
    assert "test-session-123" in tray.session_item.title


# ---------------------------------------------------------------------------
# Progress display tests
# ---------------------------------------------------------------------------

def test_daily_target_computed_from_interval(tray):
    assert tray.daily_target == 144  # 86400 // 600


def test_initial_progress_shows_zero(tray):
    assert "0/144" in tray.progress_item.title
    assert "0%" in tray.progress_item.title


def test_initial_next_capture_is_placeholder(tray):
    assert "—" in tray.next_item.title


def test_progress_updates_after_successful_capture(tray):
    tray.update_state(status="Idle", success=True)
    assert "1/144" in tray.progress_item.title
    assert "0%" in tray.progress_item.title  # 1/144 rounds to 0%


def test_progress_percentage_at_half(tray):
    for _ in range(72):
        tray.update_state(success=True)
    assert "72/144" in tray.progress_item.title
    assert "50%" in tray.progress_item.title


def test_progress_caps_at_100_percent(tray):
    for _ in range(200):
        tray.update_state(success=True)
    assert "100%" in tray.progress_item.title


def test_next_capture_set_after_successful_capture(tray):
    tray.update_state(success=True)
    assert "—" not in tray.next_item.title
    assert "Next Capture:" in tray.next_item.title


def test_next_capture_not_updated_on_failure(tray):
    tray.update_state(success=False)
    assert "—" in tray.next_item.title


def test_next_capture_not_updated_during_capturing_status(tray):
    tray.update_state(status="Capturing...", success=False)
    assert "—" in tray.next_item.title


# ---------------------------------------------------------------------------
# State update / count tests
# ---------------------------------------------------------------------------

def test_capture_count_increments_on_success(tray):
    tray.update_state(success=True)
    assert tray.capture_count == 1


def test_capture_count_does_not_increment_on_failure(tray):
    tray.update_state(success=False)
    assert tray.capture_count == 0


def test_status_label_updates(tray):
    tray.update_state(status="Capturing...", success=False)
    assert "Capturing..." in tray.status_item.title


def test_custom_interval_daily_target():
    t = MountainTray("s", interval=3600)
    assert t.daily_target == 24  # 86400 // 3600


# ---------------------------------------------------------------------------
# Quit / stop event tests
# ---------------------------------------------------------------------------

def test_on_quit_sets_stop_event(tray):
    assert not tray._stop_event.is_set()
    tray.on_quit(None)
    assert tray._stop_event.is_set()


def test_on_quit_calls_rumps_quit(tray):
    _rumps_stub.quit_application.reset_mock()
    tray.on_quit(None)
    _rumps_stub.quit_application.assert_called_once()


# ---------------------------------------------------------------------------
# Service loop tests
# ---------------------------------------------------------------------------

def test_service_loop_calls_service_func(tmp_path):
    fast_tray = MountainTray("s", data_root=str(tmp_path), interval=0)
    calls = []

    def fake_service():
        calls.append(1)
        if len(calls) >= 2:
            fast_tray._stop_event.set()
        return True

    t = threading.Thread(target=fast_tray.run, args=(fake_service,), daemon=True)
    t.start()
    t.join(timeout=3)

    assert len(calls) >= 2


def test_service_loop_stops_on_stop_event(tray):
    tray._stop_event.set()
    calls = []

    def fake_service():
        calls.append(1)
        return True

    t = threading.Thread(target=tray.run, args=(fake_service,), daemon=True)
    t.start()
    t.join(timeout=2)

    assert len(calls) == 0


def test_service_loop_handles_exception_without_crashing(tray):
    call_count = [0]

    def flaky_service():
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("boom")
        tray._stop_event.set()
        return True

    with patch("time.sleep"):
        t = threading.Thread(target=tray.run, args=(flaky_service,), daemon=True)
        t.start()
        t.join(timeout=3)

    assert call_count[0] >= 2
