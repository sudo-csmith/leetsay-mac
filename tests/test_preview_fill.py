"""The pop-up preview from Settings (Words shown, Narrow/Wide) fills the card
with sample words, so it shows exactly how many lines, and how wide, it will
be while you speak (as Windows). With one line, or "Show words as you speak"
off, no sample words. Pictures saved when LEETSAY_TEST_OUT is set."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time

m = load_app()
app = qt_app()
m.SOUNDS = False
d = m.Dictation(app)
ov = d.overlay
out = out_dir("preview-fill")


def preview(lines, wide, live=True):
    m.LIVE_PREVIEW, m.LIVE_LINES, m.WIDE_CARD = live, lines, wide
    d.refresh_popup()
    ov.preview(ms=None)
    for _ in range(3):
        ov.fade = 1.0
        ov.grab()
        time.sleep(0.25)
    for _ in range(10):
        ov.fade = 1.0
        ov._tick()
    img = ov.grab()
    img.save(os.path.join(out, f"lines{lines}-{'wide' if wide else 'narrow'}"
                               f"{'' if live else '-off'}.png"))
    return ov._card[2], ov._card[3]


sizes = {}
for lines in (1, 2, 3):
    for wide in (False, True):
        sizes[(lines, wide)] = preview(lines, wide)
        filled = [len(row) for row in ov.live_lines]
        say(f"{lines} line(s), {'wide' if wide else 'narrow'}: card {sizes[(lines, wide)]}, "
            f"rows of sample words {filled}")
        if lines > 1:
            check(f"{lines} lines {'wide' if wide else 'narrow'}: filled with sample words",
                  ov.preview_lines and len(ov.live_lines) == lines and all(filled), filled)
        else:
            check(f"1 line {'wide' if wide else 'narrow'}: no sample words",
                  not ov.preview_lines)
check("3 lines: taller than 2", sizes[(3, True)][1] > sizes[(2, True)][1], sizes)
check("wide: wider than narrow", sizes[(3, True)][0] > sizes[(3, False)][0], sizes)
preview(3, True, live=False)
check("words off: no sample words", not ov.preview_lines)
finish()
