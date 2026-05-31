#!/bin/zsh
# Stopgap mountain-out notifier launcher for LaunchAgent
# com.tommydoerr.mountain-notifier (runs at :03/:18/:33/:48, a couple minutes
# after each cloud */15 inference tick writes state.json).
#
# Invoked as `/bin/zsh <this script>` — NOT `zsh -lc` — so launchd execs the
# FDA-granted /bin/zsh directly and skips login-shell profile sourcing, which
# hangs under launchd's minimal environment. launchd-spawned processes are
# TCC-gated from /Volumes; /bin/zsh has Full Disk Access (System Settings →
# Privacy & Security → Full Disk Access), and its children inherit access, so
# the venv python below can read the repo on /Volumes. Mirrors the proven
# observability/mountain/ingest.sh pattern.
set -uo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
REPO_DIR="/Volumes/dev/is-the-mountain-out"
cd "$REPO_DIR" || exit 1
echo "[$(date)] local-notifier starting"
.venv/bin/python tools/local_notifier.py --once
echo "[$(date)] local-notifier done (exit $?)"
