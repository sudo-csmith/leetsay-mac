"""Settings: every page, and every part of a page split into parts, shown in
turn; the window keeps ONE size for all of them (General sets it: no page or
part is taller, as Windows) and fits the screen. Long pages are split into
parts with pills at the top, as Windows: Typing (Text / Where your words go),
Pop-up (While dictating / Between dictations), Look (Colours / Glow), Audio
(Microphone / Sounds), Privacy (Updates & data / Help). Pictures saved when
LEETSAY_TEST_OUT is set. (Was tabstest.)"""
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
PARTS = {"Typing": ["Text", "Where your words go"],
         "Pop-up": ["While dictating", "Between dictations"],
         "Look": ["Colours", "Glow"],
         "Audio": ["Microphone", "Sounds"],
         "Privacy": ["Updates & data", "Help"]}
check("pages as Windows (the Pill page is part of Pop-up)", "Pill" not in m.SettingsWindow.TABS,
      m.SettingsWindow.TABS)
sizes = {}
for i, name in enumerate(m.SettingsWindow.TABS):
    w.show_tab(name)
    app.processEvents()
    holder = w._tabs.currentWidget().widget()
    pills = [b for b in holder.findChildren(m.SubTabPill)]
    titles = [b._title for b in pills]
    if name in PARTS:
        check(f"{name}: parts {PARTS[name]}", titles == PARTS[name], titles)
    else:
        check(f"{name}: no parts", not titles, titles)
    for k in range(max(1, len(pills))):
        if pills:
            pills[k].click()
        app.processEvents()
        w._fit_height()
        app.processEvents()
        label = name + (" - " + titles[k] if pills else "")
        w.grab().save(os.path.join(out, f"{i}_{k}_{name}.png"))
        area = w._tabs.currentWidget()
        fits = area.verticalScrollBar().maximum() == 0
        sizes[label] = (w.width(), w.height())
        say(f"{label:32} {w.width()} x {w.height()}  {'fits' if fits else 'SCROLLS'}")
        check(f"{label}: fits without scrolling", fits)
    if pills:
        pills[0].click()
check("one size for every page and part", len(set(sizes.values())) == 1, sizes)
room = (w.screen() or app.primaryScreen()).availableGeometry()
check("fits the screen", all(h <= room.height() for _w, h in sizes.values()),
      f"screen {room.width()} x {room.height()}")
finish()
