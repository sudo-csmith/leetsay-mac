"""The screen glow takes the colour of the app you dictate into, also the
first time an app is seen in a session, when its icon arrives a moment
after the card (it used to stay in the accent colour then)."""
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
from PySide6.QtGui import QColor
m.mic_permission = lambda: m.MIC_OK
m.SOUNDS = False
m.ACCENT = "#4DA3FF"
m.SCREEN_GLOW = True
m.GLOW_FROM_APP = True
FINDER = "/System/Library/CoreServices/Finder.app"
m.front_app = lambda: ("Finder", FINDER)
d = m.Dictation(app)
d.hotkey.port = 1
d.model = object()
d.model_event.set()
fake_recorder(d)
colours = []
real = d.screen_glow.start
d.screen_glow.start = lambda c, a: (colours.append(QColor(c).name()), real(c, a))[1]
must("Finder's icon not seen yet", FINDER not in m._app_icons)
d.on_press()
wait_until(lambda: d.overlay.app_colour is not None and len(colours) >= 2, 5)
icon = d.overlay.app_colour and QColor(d.overlay.app_colour).name()
check("the icon's colour arrived", icon is not None, icon)
check("the glow ends in the icon's colour", colours and colours[-1] == icon, colours)
check("... not the accent colour", icon != m.ACCENT.lower(), icon)
d.on_cancel()
pump(0.3)
colours.clear()
d.on_press()                                   # icon known now: right colour at once
pump(0.2)
check("second time: the icon's colour straight away", colours and colours[0] == icon, colours)
finish()
