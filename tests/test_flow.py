"""A whole dictation with a spoken recording played in as the microphone
in real time (0.25 s pieces): the pop-up's live words change while
speaking, and the final text is typed (into a list) with the spoken words.
The microphone is never opened, nothing is really typed. (Was flowtest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time

need_model()
m = load_app()
app = qt_app(None)
typed = []
m.type_text = lambda text: typed.append(text)
m.focused_text_box = lambda: "yes"
m.mic_permission = lambda: m.MIC_OK
m.front_pid = lambda: 100
m.SOUNDS = False
d = m.Dictation(app)
load_model(d)
audio, words = speech("speech")
fake_recorder(d)
d.hotkey.physically_down = lambda: True          # as if the key is held
d.on_press()
check("recording", d.recording, d.overlay.mode)
shown = []


def note(t):
    text = d.overlay.live_target
    if text and (not shown or shown[-1][1] != text):
        shown.append((round(t, 1), text))


feed_real_time(d, audio, 4000, note)
say(f"live readings shown while speaking: {len(shown)}")
for t, text in shown[:3] + shown[-2:]:
    say(f"  at {t:4.1f}s: ...{text[-60:]}")
check("live words shown while speaking", len(shown) >= 2, len(shown))
let_go = time.monotonic()
d.on_release()
came = wait_until(lambda: typed, 60)
say(f"typed {time.monotonic() - let_go:.2f}s after letting go:")
say("  " + (typed[0] if typed else "NOTHING"))
check("typed after letting go", came)
ok, found = heard(typed[0] if typed else "", words)
check("the spoken words are in the text", ok, found)
check("one piece of text, ending with a space", len(typed) == 1 and typed[0].endswith(" "))
finish()
