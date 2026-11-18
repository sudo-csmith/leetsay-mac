"""The card steps off the text box only a short way and only when it is a
dictation card (as Windows): just above or below the box, at most 240
points, never when the dictation was started by clicking the pill (the card
stays under the mouse), and never for the pill or a message."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app("Fusion")
from PySide6 import QtCore
m.mic_permission = lambda: m.MIC_OK
m.SOUNDS = False
d = m.Dictation(app)
ov = d.overlay


def place(started_by_click=False, mode="recording", box_below=10, height=40):
    ov.avoid(None)
    if mode == "recording":
        ov.show_recording("App", "")
    else:
        ov.show_message("Hello", ms=None)
    ov.click_started = started_by_click
    pump(0.4)
    home = ov.pos()
    x, y, w, h = ov._card
    top = home.y() + int(y) + box_below
    box = QtCore.QRect(home.x() + int(x), top, int(w), height)
    ov.avoid(box)
    pump(0.5)
    return home, ov.pos()


home, now = place()
check("a dictation card steps off the box", now != home, (home, now))
check("... a short way (at most 240 points)", abs(now.y() - home.y()) <= 240,
      now.y() - home.y())
home, now = place(started_by_click=True)
check("started by clicking the pill: the card stays", now == home, (home, now))
home, now = place(mode="message")
check("a message never moves", now == home, (home, now))
home, now = place(box_below=-300, height=700)        # a box far taller than the card
check("never a long way across the screen", abs(now.y() - home.y()) <= 240,
      now.y() - home.y())
ov.avoid(None)
finish()
