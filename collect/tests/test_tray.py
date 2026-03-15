"""Tests for MountainTray — mocks rumps so no GUI event loop is needed."""
import sys
import types
import threading
import time
from unittest.mock import MagicMock, patch, call
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

# Now safe to import
from collect.tray import MountainTray  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tray(tmp_path):
    return MountainTray(session_id="test-session-123", data_root=str(tmp_path))


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_initial_title_is_mountain_emoji(tray):
    assert tray.title == "🗻"


def test_initial_status(tray):
    assert "Initializing" in tray.status_item.title


def test_initial_capture_count_zero(tray):
    assert tray.capture_count == 0
    assert "0" in tray.count_item.title


def test_session_id_shown_in_menu(tray):
    assert "test-session-123" in tray.session_item.title


def test_update_state_increments_count_on_success(tray):
    tray.update_state(status="Idle", success=True)
    assert tray.capture_count == 1
    assert "1" in tray.count_item.title


def test_update_state_does_not_increment_on_failure(tray):
    tray.update_state(status="Error", success=False)
    assert tray.capture_count == 0


def test_update_state_sets_last_capture_time(tray):
    assert tray.last_capture_time == "Never"
    tray.update_state(success=True)
    assert tray.last_capture_time != "Never"
    assert "Last Capture" in tray.last_capture_item.title


def test_update_state_updates_status_label(tray):
    tray.update_state(status="Capturing...", success=False)
    assert "Capturing..." in tray.status_item.title


def test_on_quit_sets_stop_event(tray):
    assert not tray._stop_event.is_set()
    tray.on_quit(None)
    assert tray._stop_event.is_set()


def test_on_quit_calls_rumps_quit(tray):
    _rumps_stub.quit_application.reset_mock()
    tray.on_quit(None)
    _rumps_stub.quit_application.assert_called_once()


def test_service_loop_calls_service_func(tray):
    calls = []

    def fake_service():
        calls.append(1)
        if len(calls) >= 2:
            tray._stop_event.set()
        return True

    # Run with interval=0 so it loops fast
    t = threading.Thread(target=tray.run, args=(fake_service, 0), daemon=True)
    t.start()
    t.join(timeout=3)

    assert len(calls) >= 2


def test_service_loop_stops_on_stop_event(tray):
    tray._stop_event.set()
    calls = []

    def fake_service():
        calls.append(1)
        return True

    t = threading.Thread(target=tray.run, args=(fake_service, 0), daemon=True)
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

    with patch("time.sleep"):  # skip actual sleeps in error handler
        t = threading.Thread(target=tray.run, args=(flaky_service, 0), daemon=True)
        t.start()
        t.join(timeout=3)

    assert call_count[0] >= 2  # recovered and called again
