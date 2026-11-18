"""Settings: every page shown in turn; the window keeps ONE size for all
pages (owner: a height changing per page didn't look smooth on a Mac) and
fits the screen. Pictures saved when LEETSAY_TEST_OUT is set. (Was tabstest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app()
d = m.Dictation(app)
w = m.SettingsWindow(d)
w.show()
out = out_dir("tabs")
sizes = {}
for i, name in enumerate(m.SettingsWindow.TABS):
    w.show_tab(name)
    app.processEvents()
    w._fit_height()
    app.processEvents()
    w.grab().save(os.path.join(out, f"{i}_{name}.png"))
    sizes[name] = (w.width(), w.height())
    say(f"{name:8} {w.width()} x {w.height()}")
check("one size for every page", len(set(sizes.values())) == 1, sizes)
room = (w.screen() or app.primaryScreen()).availableGeometry()
check("fits the screen", all(h <= room.height() for _w, h in sizes.values()),
      f"screen {room.width()} x {room.height()}")
finish()
