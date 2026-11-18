"""The pop-up in each state (idle loading/ready, hotkey pulse, a notice with
its x, recording into Finder with its real icon, wave and live words, no text
box, password field, transcribing, a message, the light look, the dot mark)
drawn without errors, the x closing a notice without running its action, and
the Pop-up and Look Settings pages. Pictures (and one sheet of them) saved
when LEETSAY_TEST_OUT is set. (Was popuptest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time

m = load_app()
from PySide6.QtGui import QImage, QPainter, QColor, QMouseEvent
from PySide6.QtCore import QRect, QPointF, Qt, QEvent
app = qt_app()
out = out_dir("popup")
d = m.Dictation(app)
ov = d.overlay
shots = []


def shot(name, settle=6, bg="#3a3f4a"):
    ov.fade = 1.0
    ov.grab()                      # first frame: starts any pill <-> card change
    time.sleep(0.3)                # let that change finish (0.2 s)
    ov.grab()
    for _ in range(settle):
        ov.fade = 1.0
        ov._tick()
    ov.fade = 1.0
    img = ov.grab().toImage()
    x, y, w, h = ov._card
    check(f"{name}: drawn", not img.isNull() and w > 0 and h > 0, f"card {int(w)}x{int(h)}")
    r = QRect(int(x) - 40, int(y) - 40, int(w) + 80, int(h) + 80).intersected(img.rect())
    pic = QImage(r.size(), QImage.Format_ARGB32)
    pic.fill(QColor(bg))
    p = QPainter(pic)
    p.drawImage(0, 0, img.copy(r))
    p.end()
    path = os.path.join(out, f"{len(shots):02d}_{name}.png")
    pic.save(path)
    shots.append(path)


ov.status = "busy"; ov.show_idle(); shot("idle_loading")
check("idle pill mode", ov.mode == "idle", ov.mode)
ov.status = "ok"; ov.show_idle(); shot("idle_ready")
ov.show_message(m.pretty(m.HOTKEY), ms=None, pulse=True)
ov.pulse_started = time.monotonic() - 0.3
shot("ready_pulse", settle=1)
ov.pulse_started = None
ran = []
d.notice("Switched it on? Click here to restart leetsay", stays=True,
         action=lambda: ran.append(1))
shot("notice_with_x")
check("a notice that stays has an x", ov.closable)
# the x closes it, without running the action
ov._press = QPointF(0, 0).toPoint()
c = ov._close_rect.center()
ev = QMouseEvent(QEvent.MouseButtonRelease, c, ov.mapToGlobal(c.toPoint()), Qt.LeftButton,
                 Qt.NoButton, Qt.NoModifier)
orig = ov._cursor_on_card
ov._cursor_on_card = lambda: True
ov.mouseReleaseEvent(ev)
ov._cursor_on_card = orig
say("after x click: closable", ov.closable, "fade target", ov.fade_target, "mode", ov.mode)
check("x click: the action did not run", not ran)
check("x click: the notice went", not ov.closable)

finder = "/System/Library/CoreServices/Finder.app"
ov.show_recording("Finder", finder)
check("Finder's icon found", ov.app_icon is not None)
check("glow colour from the icon", ov.app_colour is not None,
      ov.app_colour.name() if ov.app_colour else None)
check("recording mode", ov.mode != "idle", ov.mode)
d.recorder.peak = 0.3
for i in range(m.N_DOTS):
    ov.levels.append(0.15 + 0.6 * abs(((i * 7) % 11) / 11 - 0.5))
ov.set_live_text("Hello team, I wanted to share a quick update on the project")
for _ in range(40):
    ov._reveal_words()
shot("recording_words", settle=2)
ov.box_missing = True
ov.warning = ov._mic_warning()
shot("recording_no_text_box", settle=1)
ov.box_missing = "Password field: nothing will be typed"
shot("recording_password", settle=1)
ov.box_missing = False
ov.show_transcribing(); shot("transcribing", settle=3)
ov.show_message("Nothing heard", ms=None); shot("message")
check("message shown", ov.message == "Nothing heard", ov.message)
m.POPUP_BG = "#F8F8FA"
ov.show_recording("Finder", finder)
ov.set_live_text("The light look")
for _ in range(10):
    ov._reveal_words()
shot("recording_light", settle=2, bg="#c9ccd2")
ov.show_idle(); shot("idle_light", bg="#c9ccd2")
m.POPUP_BG = "#16171B"
m.PILL_MARK = "dot"; ov.show_idle(); shot("idle_dot")
m.PILL_MARK = "logo"

w = m.SettingsWindow(d)
w.show()
for title in ("Pop-up", "Look"):
    w.show_tab(title)
    app.processEvents(); w._fit_height(); app.processEvents()
    pic = w.grab()
    check(f"Settings page {title} drawn", not pic.isNull())
    pic.save(os.path.join(out, f"tab_{title}.png"))

imgs = [QImage(pth) for pth in shots]
W = max(i.width() for i in imgs) + 20
H = sum(i.height() + 10 for i in imgs) + 10
sheet = QImage(W, H, QImage.Format_ARGB32)
sheet.fill(QColor("#202228"))
p = QPainter(sheet)
y = 10
for i in imgs:
    p.drawImage(10, y, i)
    y += i.height() + 10
p.end()
sheet.save(os.path.join(out, "sheet.png"))
finish()
