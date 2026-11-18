"""Beta: glow round the text box (as Windows 0.2.4, d363cc8/8bfc8a4).
While dictating, with "Glow round the text box" on, a soft glow is drawn
round the focused text box (outside it only), the card steps off the box,
and "Listening" at the pointer gives way to the glow; nothing covering more
than half its window is framed; a gap under 0.6 s keeps it; after letting
go it stays still while the words go in. VS Code frames the whole chat
card. Setting dictation_mark ("pointer" default, "frame"; an older "off"
also turns Listening/Typing off), on Settings > Beta. macOS is not asked:
the box's place is given to the code as macOS would give it."""
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app("Fusion")
from PySide6 import QtCore
check("off by default (\"pointer\")", m.DICTATION_MARK == "pointer")
m.mic_permission = lambda: m.MIC_OK
m.front_pid = lambda: 4242
m.DICTATION_MARK = "frame"
m.TEXTBOX_ONLY = True
d = m.Dictation(app)
d.watchdog.stop()
d.hotkey.physically_down = lambda: True
d.recording, d.lt_active, d.target_pid = True, False, 4242
d.overlay.box_missing = False
d.overlay.show_recording("App", "")
pump(0.2)
home = d.overlay.pos()
card = d.overlay._card
box_y = home.y() + int(card[1]) + 10            # a box right under the card
rect = (home.x() + card[0], box_y, home.x() + card[0] + 300, box_y + 40)
window = (rect[0] - 200, rect[1] - 400, rect[2] + 200, rect[3] + 300)

d._update_frame("yes", (rect, window))
pump(0.3)
check("the glow shows round the box", d.frame_on and d.box_glow is not None
      and d.box_glow.isVisible(), d.frame_on)
g = d.box_glow.geometry()
check("its window holds the box with room to spare",
      g.contains(QtCore.QRect(int(rect[0]), int(rect[1]), 300, 40)), g)
img = d.box_glow.grab().toImage()
inside = img.pixelColor(int(rect[0] - g.x() + 150), int(rect[1] - g.y() + 20))
check("nothing is drawn inside the box", inside.alpha() == 0, inside.alpha())
pump(0.4)
check("the card stepped off the box", d.overlay.pos() != home, (home, d.overlay.pos()))
d._pointer_hint(False)
check("\"Listening\" gives way to the glow", d.pointer_badge is None
      or d.pointer_badge.target == 0.0 or d.pointer_badge.text != "Listening")

d._frame_seen = time.monotonic()                 # seen just now ...
d._update_frame("yes", None)                     # ... then a moment with no answer
check("a gap under 0.6 s keeps it", d.frame_on)
d._frame_seen = time.monotonic() - 1.0
d._update_frame("yes", None)
check("a longer gap: it goes", not d.frame_on)
pump(0.4)
check("the card goes back home", d.overlay.pos() == home, (home, d.overlay.pos()))

big = (window[0] + 5, window[1] + 5, window[2] - 5, window[3] - 5)
d._update_frame("yes", (big, window))
check("not round something covering most of its window", not d.frame_on)
d.overlay.box_missing = True
d._update_frame("yes", (rect, window))
check("not while there is no text box", not d.frame_on)
d.overlay.box_missing = False
m.front_pid = lambda: 1
d._update_frame("yes", (rect, window))
check("not when another app is in front", not d.frame_on)
m.front_pid = lambda: 4242

d._update_frame("yes", (rect, window))
d.recording = False
d.reading_since = time.monotonic()
d._pointer_off(typing=True)
check("let go: the glow stays, still, while the words go in",
      d.frame_on and d.box_glow.target == 1.0 and d.box_glow.live is False)
d.reading_since = None
wait_until(lambda: not d.frame_on, 3)
check("... and goes once they are in", not d.frame_on)

m.app_bundle_id = lambda pid: "com.microsoft.VSCode"
check("VS Code: the whole chat card", m.app_bundle_id(1) in d.WHOLE_CARD_APPS)
check("the place asked is only position and size (no text)",
      "AXValue" not in open(m.__file__).read().split("def focused_box_rect")[1].split("def ")[0])
r = m.focused_box_rect()
check("asking macOS here doesn't fail (None without permission)", r is None or len(r) == 2, r)

import json, base64
def line(dd):
    return "leetsay-settings-1:" + base64.urlsafe_b64encode(json.dumps(dd).encode()).decode().rstrip("=")
check("in the settings line", m.read_settings_line(line({"dictation_mark": "frame"}))[0]
      == {"dictation_mark": "frame"})
m.save_setting("dictation_mark", "off")
m.apply_config()
check("an older \"off\": no glow, no Listening/Typing",
      m.DICTATION_MARK == "pointer" and m.POINTER_STATUS is False)
m.save_setting("dictation_mark", "pointer")
m.apply_config()
m.POINTER_STATUS = True
w = m.SettingsWindow(d)
from PySide6.QtWidgets import QCheckBox
box = [b for b in w.findChildren(QCheckBox) if b.text() == "Glow round the text box"]
check("on Settings > Beta", bool(box) and "Beta" in m.SettingsWindow.TABS)
if box:
    box[0].setChecked(True)
    check("ticking it: \"frame\"", m._config.get("dictation_mark") == "frame")
    box[0].setChecked(False)
    check("unticking it: \"pointer\"", m._config.get("dictation_mark") == "pointer")
finish()
