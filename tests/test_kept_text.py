"""Missed text safety: with no text box, nothing is typed but the dictation
is kept; a quick tap of the hotkey types it again; so does the extra
"type again" key; with the safety off, a tap types nothing. Typing goes into
a list; the text box answer is faked. (Was kepttest.) Paste mode needs a
real clipboard and is not tried here (see test_pasteboard.py)."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

need_model()
m = load_app()
app = qt_app(None)
log = []
m.type_text = lambda t: (log.append(("type", t)), None)[1]
m.press_key = lambda k: (log.append(("key", k)), None)[1]
BOX = {"v": "no"}
m.focused_text_box = lambda: BOX["v"]
m.front_pid = lambda: 100
m.mic_permission = lambda: m.MIC_OK
m.LIVE_PREVIEW = False
m.KEEP_LAST = True
m.SOUNDS = False
d = m.Dictation(app)
load_model(d)
audio, words = speech("short")
HELD = {"s": 5}
fake_recorder(d, held_seconds=lambda: HELD["s"])
d.hotkey.physically_down = lambda: False

d.on_press(); feed(d, audio); d.on_release()
came = wait_until(lambda: d.reading_since is None and d.last_dictation(), 30)
say("no text box ->", log, "| notice:", repr(d.overlay.message))
check("no text box: the dictation is kept", came, repr(d.last_dictation()))
check("no text box: nothing typed", not log, log)
check("no text box: the notice says so", "No text box" in str(d.overlay.message or ""),
      repr(d.overlay.message))
ok, found = heard(d.last_dictation(), words)
check("kept text holds the words", ok, found)

BOX["v"] = "yes"
HELD["s"] = 0.1                                  # a quick tap
d.on_press(); d.on_release()
check("tap types it again", wait_until(lambda: log, 15), log[:1])
check("tap: typed the kept words", log and log[0][0] == "type"
      and log[0][1].strip() == d.last_dictation().strip(), log[:1])
log.clear()
d.on_paste_again()
check("the type-again key types it again", wait_until(lambda: log, 15), log[:1])
log.clear()
m.KEEP_LAST = False
d.on_press(); d.on_release()
pump(0.6)
check("safety off: a tap types nothing", not log, log)
finish()
