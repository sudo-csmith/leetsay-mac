"""The pop-up's accent ring is crisp: the card sits on whole screen pixels
and the ring is a filled band of whole screen pixels at rest (as Windows:
2 at 100 %, 3 on a Retina screen), so its straight
edges have no half-lit rows of pixels. Drawn at Retina scale (2 screen
pixels per point) and at 1, with no glow and no travelling light, and the
column of pixels through the top edge of the ring is read. Picture saved
when LEETSAY_TEST_OUT is set."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
scale = os.environ.get("RING_SCALE")
if scale is None:
    # Each scale in its own process (Qt reads the scale once at start).
    import subprocess
    ok = True
    for s in ("2", "1"):
        env = dict(os.environ, RING_SCALE=s, QT_SCALE_FACTOR=s)
        r = subprocess.run([sys.executable, "-I", "-u", os.path.abspath(__file__)], env=env)
        ok = ok and r.returncode == 0
    sys.exit(0 if ok else 1)

from _common import *
import time

m = load_app()
from PySide6.QtGui import QColor
app = qt_app()
m.CARD_STYLE = "clean"
m.ACCENT_OUTLINE, m.OUTLINE_LIGHT = True, False
m.SOUNDS = False
d = m.Dictation(app)
ov = d.overlay
ov.show_recording("Finder", "")
for _ in range(3):
    ov.fade = 1.0
    ov.grab()
    time.sleep(0.25)
for _ in range(8):
    ov.fade = 1.0
    ov.ring = 0.0
    ov._tick()
ov.fade, ov.ring = 1.0, 0.0
img = ov.grab().toImage()
ratio = img.devicePixelRatio()
say(f"scale {scale}: {ratio} screen pixels per point")
check("drawn at the asked scale", abs(ratio - float(scale)) < 0.01, ratio)
x, y, w, h = ov._card
col = int((x + w / 2) * ratio)
top = int(round(y * ratio))
accent = QColor(m.ACCENT)
rows = []
for py in range(top - 6, top + 2):
    c = img.pixelColor(col, py)
    # How much of the accent colour this pixel holds (0 none, 1 all).
    near = 1.0 - min(1.0, (abs(c.red() - accent.red()) + abs(c.green() - accent.green())
                           + abs(c.blue() - accent.blue())) / 120.0)
    rows.append((py - top, c.alpha(), round(near, 2)))
say("rows above the card's top edge (offset, alpha, accent share):", rows)
full = [r for r in rows if r[1] >= 250 and r[2] >= 0.9]
# A half-lit ring pixel: partly the accent colour (the card's soft shadow
# beyond the ring holds none of it and is not counted).
soft = [r for r in rows if 0.15 < r[2] < 0.85 or (r[2] >= 0.85 and r[1] < 235)]
want = max(2, int(round(1.6 * ratio)))
check(f"the ring is {want} whole screen pixels at rest", len(full) == want, full)
check("no half-lit rows at the ring's edges", not soft, soft)
if os.environ.get("LEETSAY_TEST_OUT"):
    img.save(os.path.join(out_dir("crisp-ring"), f"ring-x{scale}.png"))
finish()
