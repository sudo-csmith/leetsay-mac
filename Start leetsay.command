#!/bin/zsh
# Double-click to start leetsay (test version). Keep this window open while
# using it; closing the window or pressing Ctrl+C stops leetsay.
cd "$(dirname "$0")"
export PYTHONDONTWRITEBYTECODE=1
echo "leetsay is starting. Look for its icon in the menu bar at the top of the screen."
echo "Close this window to stop leetsay."
exec .venv/bin/python -I leetsay_mac.py 2>/dev/null
