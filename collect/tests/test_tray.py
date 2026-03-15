"""Tests for MountainTray — mocks rumps so no GUI event loop is needed."""
import sys
import types
from unittest.mock import MagicMock
import pytest

from collect.state import CollectorState, write_state, read_state, make_state


# ---------------------------------------------------------------------------
# Minimal rumps stub
# ---------------------------------------------------------------------------

def _make_rumps_stub():
    rumps_mod = types.ModuleType("rumps")

    class MenuItem:
        def __init__(self, title, callback=None):
            self.title = title
            self.callback = callback

    class Timer:
        def __init__(self, callback, interval):
            self.callback = callback
            self.interval = interval
        def start(self): pass
        def stop(self): pass

    class App:
        def __init__(self, name, title="", quit_button=None):
            self.name = name
            self.title = title
            self.menu = []
        def run(self): pass

    rumps_mod.App = App
    rumps_mod.MenuItem = MenuItem
    rumps_mod.Timer = Timer
    rumps_mod.separator = "---"
    rumps_mod.quit_application = MagicMock()
    return rumps_mod


_rumps_stub = _make_rumps_stub()
sys.modules["rumps"] = _rumps_stub

from collect.tray import MountainTray, _fmt_time  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def data_root(tmp_path):
    return tmp_path

@pytest.fixture()
def tray(data_root):
    return MountainTray(data_root=str(data_root))

@pytest.fixture()
def base_state():
    return CollectorState(
        session_id="abc123",
        status="Idle",
        capture_count=10,
        daily_target=144,
        interval_seconds=600,
        last_capture_at="2026-03-15T05:44:16+00:00",
        next_capture_at="2026-03-15T05:54:16+00:00",
        label_counts={"0": 100, "1": 5, "2": 20},
        updated_at="2026-03-15T05:44:17+00:00",
    )


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

def test_initial_title_is_mountain_emoji(tray):
    assert tray.title == "🗻"


def test_initial_status_placeholder(tray):
    assert "—" in tray.status_item.title


# ---------------------------------------------------------------------------
# State file read/write round-trip
# ---------------------------------------------------------------------------

def test_write_and_read_state_roundtrip(data_root, base_state):
    write_state(data_root, base_state)
    result = read_state(data_root)
    assert result == base_state


def test_read_state_returns_none_when_missing(data_root):
    assert read_state(data_root) is None


def test_write_is_atomic(data_root, base_state):
    """write_state uses a tmp file + rename — no partial reads."""
    write_state(data_root, base_state)
    path = data_root / "collector_state.json"
    assert path.exists()
    # No .tmp file should remain
    assert not (data_root / "collector_state.tmp").exists()


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def test_render_populates_status(tray, base_state):
    tray._render(base_state)
    assert "Idle" in tray.status_item.title


def test_render_populates_progress(tray, base_state):
    tray._render(base_state)
    assert "10/144" in tray.progress_item.title
    assert "6%" in tray.progress_item.title   # 10/144 = 6%


def test_render_populates_next_capture(tray, base_state):
    tray._render(base_state)
    assert "Next Capture:" in tray.next_item.title
    assert "—" not in tray.next_item.title


def test_render_populates_session(tray, base_state):
    tray._render(base_state)
    assert "abc123" in tray.session_item.title



def test_render_shows_placeholder_when_next_is_none(tray, base_state):
    base_state.next_capture_at = None
    tray._render(base_state)
    assert "—" in tray.next_item.title


# ---------------------------------------------------------------------------
# _refresh reads from state file
# ---------------------------------------------------------------------------

def test_refresh_reads_state_file(tray, data_root, base_state):
    write_state(data_root, base_state)
    tray._refresh()
    assert "Idle" in tray.status_item.title
    assert "abc123" in tray.session_item.title


def test_refresh_shows_error_when_no_state_file(tray):
    tray._refresh()
    assert "No state file" in tray.status_item.title


def test_refresh_skips_rerender_when_state_unchanged(tray, data_root, base_state):
    write_state(data_root, base_state)
    tray._refresh()
    # Mutate a menu item directly — a re-render would reset it
    tray.status_item.title = "SENTINEL"
    tray._refresh()   # same state object, should skip
    assert tray.status_item.title == "SENTINEL"


# ---------------------------------------------------------------------------
# pct_complete
# ---------------------------------------------------------------------------

def test_pct_complete_normal():
    s = make_state("s", "Idle", capture_count=72, interval_seconds=600)
    assert s.pct_complete == 50


def test_pct_complete_caps_at_100():
    s = make_state("s", "Idle", capture_count=999, interval_seconds=600)
    assert s.pct_complete == 100


def test_pct_complete_zero():
    s = make_state("s", "Idle", capture_count=0, interval_seconds=600)
    assert s.pct_complete == 0


# ---------------------------------------------------------------------------
# _fmt_time helper
# ---------------------------------------------------------------------------

def test_fmt_time_valid_iso():
    result = _fmt_time("2026-03-15T05:44:16+00:00")
    assert result is not None
    assert ":" in result


def test_fmt_time_none():
    assert _fmt_time(None) is None


def test_fmt_time_invalid():
    assert _fmt_time("not-a-date") is None
