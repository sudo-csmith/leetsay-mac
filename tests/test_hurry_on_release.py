"""Type as you speak: words still waiting go in straight after letting go
(about 0.3 s for 60 letters, the same pace as Windows; 0.46 s before), so
they are in before Return or Send is pressed, not only with the rest of the
last reading. First with words put in
waiting, then a spoken recording played in real time: the time from
letting go to nothing waiting, and the whole text."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time

need_model()
m = load_app()
app = qt_app(None)
typed, stamps = [], []


def fake_type(text):
    typed.append(text)
    stamps.append(time.monotonic())
    return None


m.type_text = fake_type
m.focused_text_box = lambda: "yes"
m.front_pid = lambda: 4242
m.mic_permission = lambda: m.MIC_OK
m.LIVE_TYPE, m.SOUNDS = True, False
m.LAST_WORD_MS = 1000                    # a long catch: the waiting words must not wait for it
d = m.Dictation(app)
load_model(d)
fake_recorder(d)
d.hotkey.physically_down = lambda: True
audio, key = speech("short")

# 1. Words waiting at the moment of letting go.
d.on_press()
feed_real_time(d, audio[:RATE], 640)
d.lt_box = ("yes", time.monotonic() + 30)
d.lt_pending = "and these words were waiting to be typed in, about sixty letters"
waiting = len(d.lt_pending)
d._flush_live()
let_go = time.monotonic()
d.on_release()
came = wait_until(lambda: not d.lt_pending or not d.recording, 2)
spent = time.monotonic() - let_go
say(f"{waiting} letters waiting went in {spent:.2f} s after letting go")
check("waiting words go in within 0.4 s of letting go", came and not d.lt_pending
      and spent < 0.4, f"{spent:.2f} s, left {len(d.lt_pending)}")
check("... before the last-word catch ends", d.recording or spent < m.LAST_WORD_MS / 1000)
wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
pump(1.0)

# 2. Spoken, real time: everything typed, nothing twice.
m.LAST_WORD_MS = 400
audio, key = speech("speech")
typed.clear()
stamps.clear()
d.on_press()
feed_real_time(d, audio, 640)
left = len(d.lt_pending)
let_go = time.monotonic()
d.on_release()
wait_until(lambda: not d.lt_pending or not d.recording, 2)
say(f"spoken: {left} letters waiting at letting go, all in after "
    f"{time.monotonic() - let_go:.2f} s")
wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
pump(1.5)
full = "".join(typed)
say("TYPED:", full)
check("spoken: the words are there", heard(full, key)[0], full)
plain = plain_words(full)
runs = [tuple(plain[i:i + 3]) for i in range(len(plain) - 2)]
check("spoken: nothing typed twice", not [r for r in runs if runs.count(r) > 1])
finish()
