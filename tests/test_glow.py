"""Screen-edge glow (bottom and all edges) in Finder's icon colour, the
"No text box" badge at the pointer, and the menu bar icon with voice levels:
drawn without errors. Pictures saved when LEETSAY_TEST_OUT is set. (Was
glowtest; it used another app's icon, now Finder's, which every Mac has.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
from PySide6 import QtCore, QtGui
app = qt_app(None)
out = out_dir("glow")
icon = m.mac_app_icon("/System/Library/CoreServices/Finder.app")
must("Finder's icon read", icon is not None and not icon.isNull())
colour = m.icon_colour(icon.pixmap(256, 256))
check("a colour taken from the icon", colour is not None and colour.isValid(),
      colour.name() if colour is not None else None)
area = QtCore.QRect(0, 0, 900, 560)
for edges, want in (("bottom", 1), ("all", 4)):
    m.SCREEN_GLOW_EDGES = edges
    g = m.ScreenGlow()
    g.start(colour, area)
    for i in range(60):
        g.step(0.6, True)
    canvas = QtGui.QImage(900, 560, QtGui.QImage.Format_ARGB32_Premultiplied)
    canvas.fill(QtGui.QColor("#1e1f24"))
    p = QtGui.QPainter(canvas)
    for strip in g.strips:
        if strip.isVisible():
            p.setOpacity(strip.windowOpacity())
            p.drawPixmap(strip.geometry().topLeft(), strip.grab())
    p.end()
    canvas.save(os.path.join(out, f"screen_glow_{edges}.png"))
    shown = sum(s.isVisible() for s in g.strips)
    check(f"glow on {edges}: {want} strip(s) shown", shown == want, shown)
    g.stop()
b = m.PointerBadge()
b.show()
pic = b.grab()
check("pointer badge drawn", not pic.isNull() and b.width() > 0, b.size())
pic.save(os.path.join(out, "badge.png"))
tray = m.menu_bar_icon(levels=[0.2, 0.1]).pixmap(36, 36)
check("menu bar icon with levels drawn", not tray.isNull())
tray.save(os.path.join(out, "tray_quiet.png"))
finish()
