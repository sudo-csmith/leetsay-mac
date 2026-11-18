"""The 0.2.3 port: 1. full-screen detection reads real window data (a huge
screen is never covered; a window's own spot is); 2. "Stay in the app I
started in": the starting app comes back on the 3rd request and gets the
text; never comes back -> 4 requests, nothing typed, the text kept (only
with Missed text safety on); the app has quit -> refused at once; a new
dictation meanwhile -> the old words are dropped; 3. the live preview is
cleaned like the final text; 4. the idle pill steps aside for a full-screen
app (a notice still shows) and comes back; with the setting on it stays;
5. the setting moves in the settings line. No speech model needed.
(Was port023test.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time
import numpy as np

m = load_app()
from PySide6.QtCore import QTimer, QRect
app = qt_app(None)


class FakeScreen:
    def __init__(s, r): s.r = r
    def geometry(s): return s.r


class W:
    def __init__(s, r): s.s = FakeScreen(r)
    def screen(s): return s.s


# 1. full-screen detection with real window data
def some_window():
    """(pid, x, y, w, h) of a normal window of another app on screen, or None."""
    info = m.CGWindowListCopyWindowInfo(1 | 16, 0)
    if not info:
        return None
    try:
        for i in range(m.CFArrayGetCount(info)):
            dd = m.CFArrayGetValueAtIndex(info, i)
            pid = m._cf_int(dd, "kCGWindowOwnerPID")
            if m._cf_int(dd, "kCGWindowLayer") != 0 or not pid or pid == os.getpid():
                continue
            r = m._CGRect()
            bounds = m.CFDictionaryGetValue(dd, m._ax_name("kCGWindowBounds"))
            if bounds and m.CGRectMakeWithDictionaryRepresentation(bounds, m.byref(r)) \
                    and r.w > 8 and r.h > 8:
                return pid, int(r.x), int(r.y), int(r.w), int(r.h)
    finally:
        m.CFRelease(info)
    return None


real_front = m.front_pid
win = some_window()
if win:
    pid, x, y, w, h = win
    m.front_pid = lambda: pid
    check("a huge screen is never covered", m.fullscreen_app_in_front(W(QRect(0, 0, 100000, 100000))) is False)
    check("a window covers a 2x2 spot inside it",
          m.fullscreen_app_in_front(W(QRect(x + 2, y + 2, 2, 2))) is True)
    check("not a spot outside every window of it",
          m.fullscreen_app_in_front(W(QRect(-50000, -50000, 2, 2))) is False)
    m.front_pid = real_front
else:
    say("note: no ordinary window on screen (a fresh CI machine?): real-window part not tried")
check("our own process is never 'full-screen'",
      (lambda: (setattr(m, "front_pid", lambda: os.getpid()),
                m.fullscreen_app_in_front(W(QRect(0, 0, 2, 2))))[1])() is False)

# the controller
log = []
m.type_text = lambda t: (log.append(("type", t)), None)[1]
m.press_key = lambda k: log.append(("key", k))
m.focused_text_box = lambda: "yes"
m.mic_permission = lambda: m.MIC_OK
m.SOUNDS = False
FRONT = {"pid": 100}
m.front_pid = lambda: FRONT["pid"]
d = m.Dictation(app)

# 2. return to the starting app: it comes back on the 3rd request
acts = []


def act_late(pid):
    acts.append(time.monotonic())
    if len(acts) == 3:
        QTimer.singleShot(80, lambda: FRONT.update(pid=pid))
    return True


m.activate_app = act_late
m.KEEP_LAST = True
d.target_pid = 100
FRONT["pid"] = 200
log.clear()
t0 = time.monotonic()
d._deliver("hello there ", "")
came = wait_until(lambda: log, 15)
pump(0.5)                                         # no more requests after it came back
say("came back on try 3:", len(acts), "requests,", [round(a - t0, 2) for a in acts], log)
check("came back on the 3rd request and typed there",
      came and len(acts) == 3 and log[0] == ("type", "hello there "), (len(acts), log))

GAVE_UP = "Couldn't get back"
acts.clear(); log.clear(); d.forget()
m.activate_app = lambda pid: (acts.append(time.monotonic()), True)[1]
d.target_pid = 100
FRONT["pid"] = 200
t0 = time.monotonic()
d._deliver("secret words ", "")
gave_up = wait_until(lambda: GAVE_UP in str(d.overlay.message or ""), 15)
say("gave up:", len(acts), "requests over", round(acts[-1] - t0, 2) if acts else None,
    "s; typed:", log, "; message:", repr(d.overlay.message), "; kept:", repr(d.last_dictation()))
check("never came back: gave up and said so", gave_up)
check("never came back: 4 requests", len(acts) == 4, len(acts))
check("never came back: nothing typed", not log, log)
check("never came back: the text is kept", d.last_dictation() == "secret words",
      repr(d.last_dictation()))

m.KEEP_LAST = False
d.forget(); acts.clear()
d.overlay.message = ""
d.target_pid = 100
d._deliver("not kept ", "")
wait_until(lambda: GAVE_UP in str(d.overlay.message or ""), 15)
check("Missed text safety off -> not kept", d.last_dictation() == "", repr(d.last_dictation()))

acts.clear()
d.overlay.message = ""
m.activate_app = lambda pid: (acts.append(1), False)[1]
d.target_pid = 100
d._deliver("x ", "")
wait_until(lambda: GAVE_UP in str(d.overlay.message or ""), 15)
check("app gone: one request, refused at once, nothing typed",
      len(acts) == 1 and not log, (len(acts), log))

acts.clear()
m.activate_app = lambda pid: (acts.append(1), True)[1]
d.target_pid = 100
d._deliver("old ", "")
d.target_pid = 300                               # a new dictation has started
pump(1.5)
check("new dictation meanwhile: the old words are dropped",
      len(acts) == 1 and not log, (len(acts), log))
FRONT["pid"] = 100


# 3. live preview cleaned like the final text
class FakeModel:
    def recognize(s, a, sample_rate):
        return "um so I said uh hello at 3.47 p.m."


d.model = FakeModel()
got = []
d.live_text.connect(lambda s, t: got.append(t))
d.recording = True
d.live_busy = True
d._live_run(np.zeros(16000, np.float32), 16000, 7)
app.processEvents()
d.recording = False
want = m.clean_text("um so I said uh hello at 3.47 p.m.")
say("live preview:", got, "| final clean:", want)
check("live preview cleaned like the final text", got and got[0] == want, got)
d.model = None

# 4. the idle pill steps aside for a full-screen app and comes back
m.ALWAYS_SHOW = True
m.PILL_OVER_FULLSCREEN = False
COVER = {"on": False}
m.fullscreen_app_in_front = lambda w: COVER["on"]
d.hotkey.port = 1                                # as if typing were allowed (setup done)
o = d.overlay
o.show_idle()
wait_until(lambda: o.isVisible() and o.mode == "idle" and o.fade_target > 0, 10)
say("idle pill:", o.isVisible(), o.mode, o.fade_target)
COVER["on"] = True
d._step_aside_check()
check("full-screen app in front -> stepped aside",
      wait_until(lambda: o.stepped_aside and o.fade_target == 0, 10), (o.stepped_aside, o.fade_target))
o.show_message("A notice", ms=500)
app.processEvents()
check("a notice still shows", o.isVisible() and o.fade_target > 0, (o.isVisible(), o.mode))
check("after the notice, still aside",
      wait_until(lambda: o.fade_target == 0, 10) and o.stepped_aside,
      (o.mode, o.fade_target, o.stepped_aside))
COVER["on"] = False
d._step_aside_check()
check("full-screen app gone -> back",
      wait_until(lambda: not o.stepped_aside and o.fade_target > 0 and o.mode == "idle", 10),
      (o.stepped_aside, o.mode, o.fade_target))
m.PILL_OVER_FULLSCREEN = True
COVER["on"] = True
d._step_aside_check()
pump(0.3)
check("setting on -> stays", o.fade_target > 0 and not o.stepped_aside)

# 5. the setting moves in the settings line
check("pill_over_fullscreen in the settings line", "pill_over_fullscreen" in m._PORTABLE_CHECKS)
finish()
