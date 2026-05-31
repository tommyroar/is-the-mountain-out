#!/usr/bin/env python3
"""Local stopgap notifier for mountain-out alerts.

The Cloudflare Worker publishes notifications to ntfy.sh anonymously, which is
rate-limited per source IP and returns HTTP 429 from Cloudflare's shared egress
IPs (see worker/src/index.ts and NOTIFICATIONS.md). Until the Worker's
NTFY_TOKEN secret is wired up (GitHub issue tracks the manual ntfy.sh account +
token registration), this utility delivers the notification from the operator's
home IP, which is not rate-limited.

It does NOT run inference. It polls the same public state.json the cloud Worker
already writes every */15 tick, and mirrors the Worker's notifyTransition logic:
fire exactly once on the Not Out -> visible (Full or Partial) transition.

Previous is_out is persisted to a small local state file so the transition is
detected across restarts and the same flip is never announced twice.

Usage:
    uv run python tools/local_notifier.py            # poll loop (default 300s)
    uv run python tools/local_notifier.py --once      # single check, then exit
    uv run python tools/local_notifier.py --interval 120
    uv run python tools/local_notifier.py --test      # send a test push and exit
"""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from pathlib import Path

import requests

# Hard wall-clock cap per check. requests timeouts are not reliably honored when
# this runs under launchd (the connect/TLS phase can hang well past the socket
# timeout), and a scheduled job must never hang and pile up. SIGALRM guarantees
# the process exits; the next */15 run retries.
WATCHDOG_SECONDS = 45


class _Watchdog(Exception):
    pass


def _run_guarded(fn) -> None:
    def _handler(signum, frame):
        raise _Watchdog(f"check exceeded {WATCHDOG_SECONDS}s; aborting")

    old = signal.signal(signal.SIGALRM, _handler)
    signal.alarm(WATCHDOG_SECONDS)
    try:
        fn()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)

# Public bucket URL the SPA also reads (web/.env.production: VITE_STATE_URL).
STATE_URL = "https://pub-66d3d1f139004e29b2afcb5fba49bdb3.r2.dev/state.json"
NTFY_URL = "https://ntfy.sh/"
REPO_ROOT = Path(__file__).resolve().parent.parent


def _main_worktree_root() -> Path:
    """The gitignored ntfy.key lives in the primary checkout, not in linked
    worktrees. Resolve the main worktree from git so the secret is found whether
    this runs from the main tree or a `.claude/worktrees/*` copy."""
    try:
        common = subprocess.check_output(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--path-format=absolute", "--git-common-dir"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        return Path(common).parent  # .../<main>/.git -> .../<main>
    except Exception:
        return REPO_ROOT


_SECRET_ROOT = _main_worktree_root()
# Look in the worktree first (for an override), then the main checkout.
TOPIC_FILE = REPO_ROOT / "ntfy.key"
TOKEN_FILE = REPO_ROOT / "ntfy-token.key"  # optional; raises rate limit if present
MAIN_TOPIC_FILE = _SECRET_ROOT / "ntfy.key"
MAIN_TOKEN_FILE = _SECRET_ROOT / "ntfy-token.key"
LOCAL_STATE_FILE = REPO_ROOT / "data" / "local_notifier_state.json"
DEFAULT_INTERVAL = 300  # seconds; matches the Worker's */15 cadence loosely


def _read_secret(path: Path) -> str | None:
    try:
        value = path.read_text().strip()
        return value or None
    except OSError:
        return None


def fetch_state(url: str = STATE_URL) -> dict:
    resp = requests.get(url, params={"t": int(time.time())}, timeout=15)
    resp.raise_for_status()
    return resp.json()


def load_prev_is_out() -> bool | None:
    try:
        return json.loads(LOCAL_STATE_FILE.read_text()).get("is_out")
    except (OSError, ValueError):
        return None


def save_prev_is_out(is_out: bool, timestamp_utc: str | None) -> None:
    LOCAL_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_STATE_FILE.write_text(
        json.dumps({"is_out": is_out, "timestamp_utc": timestamp_utc}) + "\n"
    )


def ntfy_publish(payload: dict) -> None:
    topic = _read_secret(TOPIC_FILE) or _read_secret(MAIN_TOPIC_FILE)
    if not topic:
        print(
            f"! no topic in {TOPIC_FILE} or {MAIN_TOPIC_FILE}; skipping notification",
            file=sys.stderr,
        )
        return
    headers = {"Content-Type": "application/json"}
    token = _read_secret(TOKEN_FILE) or _read_secret(MAIN_TOKEN_FILE)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.post(NTFY_URL, headers=headers, json={"topic": topic, **payload}, timeout=15)
    if not resp.ok:
        print(f"! ntfy publish {resp.status_code}: {resp.text[:200]}", file=sys.stderr)
        resp.raise_for_status()


def notify_transition(prev_is_out: bool | None, state: dict) -> bool:
    """Fire only on Not Out -> visible, mirroring worker/src/index.ts. Returns
    True if a notification was sent."""
    if not state.get("is_out"):
        return False
    if prev_is_out:  # was already out -> no transition
        return False
    conf = state.get("confidence") or {}
    visible = (conf.get("full") or 0) + (conf.get("partial") or 0)
    label = "Full" if state.get("class_name") == "full" else "Partial"
    ntfy_publish(
        {
            "title": "🏔️ THE MOUNTAIN IS OUT",
            "message": f"Mount Rainier is visible ({label}). Confidence: {visible * 100:.1f}%",
            "priority": 5,
            "tags": ["mountain_snow_capped"],
        }
    )
    return True


def check_once() -> None:
    state = fetch_state()
    prev = load_prev_is_out()
    is_out = bool(state.get("is_out"))
    ts = state.get("timestamp_utc")
    if prev is None:
        # Cold start: we have no prior reading, so we can't know this is a
        # transition. Seed silently rather than announce on startup.
        save_prev_is_out(is_out, ts)
        print(f"[{ts}] is_out={is_out} prev=None -> seeded (no notification)")
        return
    sent = notify_transition(prev, state)
    save_prev_is_out(is_out, ts)
    status = "NOTIFIED" if sent else "ok"
    print(f"[{ts}] is_out={is_out} prev={prev} -> {status}")


def send_test() -> None:
    ntfy_publish(
        {
            "title": "🏔️ Local notifier test",
            "message": "Test from tools/local_notifier.py on the operator's machine. "
            "If you see this, the local ntfy path is healthy.",
            "priority": 3,
            "tags": ["test_tube"],
        }
    )
    print("test notification sent")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--once", action="store_true", help="run a single check and exit")
    parser.add_argument("--test", action="store_true", help="send a test notification and exit")
    parser.add_argument(
        "--interval", type=int, default=DEFAULT_INTERVAL,
        help=f"poll interval in seconds (default {DEFAULT_INTERVAL})",
    )
    args = parser.parse_args()

    if args.test or args.once:
        try:
            _run_guarded(send_test if args.test else check_once)
        except Exception as e:
            print(f"! check failed: {e}", file=sys.stderr)
            raise SystemExit(1)
        return

    print(f"local_notifier polling {STATE_URL} every {args.interval}s (Ctrl-C to stop)")
    while True:
        try:
            _run_guarded(check_once)
        except Exception as e:  # network blip, malformed state, watchdog — log and keep going
            print(f"! check failed: {e}", file=sys.stderr)
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
