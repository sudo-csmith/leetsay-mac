"""Type as you speak, steady flow: each batch of confirmed words is spread
evenly until the next batch usually arrives (learnt per dictation, 0.35-1.2
s, start 0.7 s; at least about 12 letters a second; more than 40 letters
waiting = catch up). First the spread of one batch, then a spoken recording
played in real time: letters go in during a good part of the speaking time
(it was about 20 % on the owner's recordings, now about 50-70 %), the words
are all there and nothing is typed twice."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time

m = load_app()
D = m.Dictation
check("spread between 0.35 and 1.2 s", D.LT_FLOW == (0.35, 1.2), D.LT_FLOW)

need_model()
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
d = m.Dictation(app)
load_model(d)
fake_recorder(d)
d.hotkey.physically_down = lambda: True
audio, key = speech("speech")

# 1. One batch of 30 letters, nothing learnt yet: spread over about 0.7 s.
d.on_press()
feed_real_time(d, audio[:RATE // 2], 640)
d.live_timer.stop()                      # only this batch
d.lt_box = ("yes", time.monotonic() + 60)
typed.clear()
stamps.clear()
d._queue_words("one two three four five six".split())
start = time.monotonic()
wait_until(lambda: not d.lt_pending, 3)
spent = time.monotonic() - start
say(f"a batch of {len(''.join(typed))} letters went in over {spent:.2f} s in {len(typed)} bits")
check("one batch is spread out, not typed at once", spent > 0.4 and len(typed) > 5,
      (round(spent, 2), len(typed)))
check("... and done well within 1.2 s", spent < 1.2, round(spent, 2))
d.on_cancel()
pump(0.5)

# 2. Spoken, real time.
typed.clear()
stamps.clear()
d.on_press()
feed_real_time(d, audio, 640)
let_go = time.monotonic()
during = list(stamps)
d.on_release()
wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
pump(1.5)
full = "".join(typed)
say("TYPED:", full)
if during:
    slots = max(1, int((let_go - during[0]) / 0.1))
    share = len({int((s - during[0]) / 0.1) for s in during}) / slots
else:
    share = 0.0
say(f"letters went in during {share:.0%} of the speaking time (from the first letter)")
check("letters flow during much of the speaking time", share >= 0.4, f"{share:.0%}")
check("spoken: the words are there", heard(full, key)[0], full)
plain = plain_words(full)
runs = [tuple(plain[i:i + 3]) for i in range(len(plain) - 2)]
check("spoken: nothing typed twice", not [r for r in runs if runs.count(r) > 1])
finish()
