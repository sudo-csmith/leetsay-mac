"""A click on the download card when the download isn't moving opens the
help window (as on Windows), every time, also while the setup window is
open; "Try again" in it retries; "Manual download" shows the steps; a
right-click still retries at once. No network: the window and the retry
are replaced."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
m.mic_permission = lambda: m.MIC_OK
shown, answers, retried, manual = [], [], [], []
m.dialog = lambda title, text, buttons=("OK",), **kw: (
    shown.append((title, kw.get("headline"), buttons)), answers.pop(0) if answers else None)[1]
m.manual_download_steps = lambda: manual.append(1)
m.Dictation.retry_download = lambda self: retried.append(1)   # before it is wired up
d = m.Dictation(app)
d.downloading = True
d.download_blocked = True
d.overlay.show_message(d.BLOCKED, ms=None)
d.overlay.progress = 0.2
d.notice_action = d.download_clicked
w = m.SetupWindow(d)
w.show()
pump(0.2)

answers.append(None)                       # closed
d.overlay.notice_clicked.emit()
pump(0.1)
check("a click opens the help window", len(shown) == 1, shown)
check("its headline", shown and shown[0][1] == "The download has stopped moving")
check("it offers Try again and Manual download",
      shown and shown[0][2][:2] == ("Try again", "Manual download"), shown and shown[0][2])
answers.append("Try again")
d.overlay.notice_clicked.emit()
pump(0.1)
check("a second click opens it again (stays clickable)", len(shown) == 2)
check("Try again retries", retried == [1], retried)
answers.append("Manual download")
d.overlay.notice_clicked.emit()
pump(0.1)
check("Manual download shows the steps", manual == [1])
d.overlay.retry_wanted.emit()
pump(0.1)
check("a right-click still retries at once", retried == [1, 1], retried)
d.download_blocked = False
d.download_stuck = False
d.overlay.notice_clicked.emit()
pump(0.1)
check("while it is moving, a click opens nothing", len(shown) == 3)
finish()
