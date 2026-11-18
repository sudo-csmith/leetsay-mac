"""Beta: point at a text box to use it (as Windows 0.2.4, df17f0a). While
the card says "No text box selected", resting the mouse 0.5 s on a spot
(moves under 4 px still count) asks once per spot to select the text box
there, only in the app the dictation started in; off by default; needs
Text box detection; on Settings > Beta; in the settings line. macOS is not
asked here: the selecting call is replaced and its arguments checked."""
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app("Fusion")
from PySide6 import QtGui
check("off by default", m.POINT_TO_TYPE is False)
m.mic_permission = lambda: m.MIC_OK
m.front_pid = lambda: 4242
m.POINT_TO_TYPE, m.TEXTBOX_ONLY = True, True
asked = []
m.select_text_box_at = lambda x, y, pid: (asked.append((x, y, pid)), True)[1]

cursor = [100, 200]
QtGui.QCursor.pos = staticmethod(lambda: __import__("PySide6.QtCore", fromlist=["QPoint"])
                                 .QPoint(*cursor))
d = m.Dictation(app)
d.watchdog.stop()
d.recording, d.target_pid = True, 4242
d.overlay.box_missing = True


def tick(n=1, gap=0.0):
    for _ in range(n):
        d._point_to_type()
        if gap:
            time.sleep(gap)
    pump(0.05)


tick()                                          # first sight of this spot
d.ptt["since"] -= 0.3
tick()
check("not before 0.5 s of resting", not asked, asked)
cursor[0] += 3                                  # a small move still counts as resting
d.ptt["since"] -= 0.3
tick()
check("after 0.5 s: the text box under the pointer is selected",
      asked == [(103, 200, 4242)], asked)
d.ptt["since"] -= 2
tick(3)
check("once per spot", len(asked) == 1, asked)
cursor[0] += 20                                 # moved: a new spot
tick()
d.ptt["since"] -= 0.6
tick()
check("a new spot is asked about again", len(asked) == 2, asked)

asked.clear()
d.overlay.box_missing = False
d.ptt.update(pos=None, tried=False)
tick(); d.ptt["since"] -= 1; tick()
check("not while a text box is selected", not asked)
d.overlay.box_missing = True
m.front_pid = lambda: 1
tick(); d.ptt["since"] -= 1; tick()
check("not when another app is in front", not asked)
m.front_pid = lambda: 4242
m.TEXTBOX_ONLY = False
tick(); d.ptt["since"] -= 1; tick()
check("needs Text box detection", not asked)
m.TEXTBOX_ONLY = True
m.POINT_TO_TYPE = False
tick(); d.ptt["since"] -= 1; tick()
check("off: never", not asked)
m.POINT_TO_TYPE = True
d.recording = False
tick(); d.ptt["since"] -= 1; tick()
check("only while dictating", not asked)

real = load_app().select_text_box_at
check("leetsay's own windows are never selected", real(10, 10, os.getpid()) is False)
check("nothing there / no permission: False, no error", real(-5000, -5000, 4242) is False)

import json, base64
line = "leetsay-settings-1:" + base64.urlsafe_b64encode(json.dumps(
    {"point_to_type": True}).encode()).decode().rstrip("=")
check("in the settings line", m.read_settings_line(line)[0] == {"point_to_type": True})
w = m.SettingsWindow(d)
from PySide6.QtWidgets import QCheckBox
box = [b for b in w.findChildren(QCheckBox) if b.text() == "Point at a text box to use it"]
check("on Settings > Beta", bool(box))
finish()
