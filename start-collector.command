#!/bin/bash
# This script is intended to be run on macOS to launch the tray application.

# Get the directory where the script is located to find the project root.
cd "$(dirname "$0")"

# The command to run. We use the full path to 'uv' inside the virtual env
# and tell it to run the 'collect' command, which defaults to starting the tray.
# The 'exec' command replaces the shell process with the Python process.
exec ./.venv/bin/uv run collect
