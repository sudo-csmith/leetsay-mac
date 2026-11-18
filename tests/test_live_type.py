"""Type as you speak with a spoken recording (pauses between sentences)
played in real time as the microphone: words are typed at the pauses while
speaking, the rest after letting go, and the whole holds the spoken words
with nothing typed twice. Typing goes into a list; the front app and text
box are faked. (Was livetypetest.)"""
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
m.LIVE_TYPE = True
m.SOUNDS = False
d = m.Dictation(app)
load_model(d)
audio, words = speech("speech")
fake_recorder(d)
d.hotkey.physically_down = lambda: True
d.on_press()
check("type as you speak active", d.lt_active)
t0 = feed_real_time(d, audio, 640)
during = "".join(typed)
if typed:
    say(f"typed WHILE speaking ({len(typed)} bits, first after {stamps[0] - t0:.1f}s):")
else:
    say("nothing typed while speaking")
say("  " + during)
check("words typed while speaking", typed)
let_go = time.monotonic()
n = len(typed)
d.on_release()
came = wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
check("the rest was read after letting go", came)
# Typing runs in a thread: wait until nothing new has come for 1 s.
wait_until(lambda: stamps and time.monotonic() - max(stamps[-1], let_go) > 1.0, 30)
if len(typed) > n:
    say(f"after letting go ({stamps[-1] - let_go:.2f}s): {''.join(typed[n:])!r}")
full = "".join(typed)
say("FULL:", full)
ok, found = heard(full, words)
check("the whole holds the spoken words", ok, found)
plain = plain_words(full)
check("no sentence typed twice", plain.count("hello") <= 1 and plain.count("friday") <= 1, plain)
finish()
