"""Benchmark (not a test: it only prints numbers and never fails). Time from
letting go to the text being typed, normal mode with the live preview on.
The recording is fed in real time (0.1 s pieces) and let go at several
lengths, so the release lands at different points of a preview pass.
Run with: run_all.py --bench  (or give lengths in seconds as arguments).
(Was releasetime.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time

need_model()
m = load_app()
app = qt_app(None)
typed = []
m.type_text = lambda t: typed.append((time.monotonic(), t))
m.focused_text_box = lambda: "yes"
m.mic_permission = lambda: m.MIC_OK
m.front_pid = lambda: 100
m.LIVE_PREVIEW = True
m.LIVE_TYPE = False
m.SOUNDS = False
d = m.Dictation(app)
d._load_model()
app.processEvents()
if d.model is None:
    say("the model did not load:", d.model_error)
    os._exit(0)
d.hotkey.port = 1
audio, _words = speech("speech")
fake_recorder(d)
d.hotkey.physically_down = lambda: True
total = len(audio) / RATE
lengths = [float(x) for x in sys.argv[1:]] or [x for x in (5.3, 7.1, 8.6, 10.4, 12.2, 13.9)
                                               if x <= total]
results = []
for secs in lengths:
    typed.clear()
    d.on_press()
    pump(0.05)
    n = int(secs * RATE)
    feed_real_time(d, audio[:n], RATE // 10)
    busy = d.live_busy
    rel = time.monotonic()
    d.on_release()
    wait_until(lambda: typed, 30)
    lat = typed[0][0] - rel if typed else float("nan")
    results.append(lat)
    say(f"{secs:5.1f} s recorded, preview running at release: {busy!s:5}  -> text after {lat:.2f} s")
    wait_until(lambda: d.reading_since is None, 30)
    pump(1.5)
r = sorted(x for x in results if x == x)
if r:
    say(f"median {r[len(r) // 2]:.2f} s, worst {r[-1]:.2f} s, best {r[0]:.2f} s")
os._exit(0)
