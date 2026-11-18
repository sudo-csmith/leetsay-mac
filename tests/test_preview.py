"""The live words on the card and the moment after letting go: a last word
that only one reading has heard is held back until a second reading agrees
(a half-heard word is a guess); a new dictation starts fresh; and if the
final text isn't ready 0.7 s after letting go, the card becomes a small
"Transcribing…" pill until the text is typed."""
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
typed = []
m.type_text = lambda t: typed.append(t)
m.focused_text_box = lambda: "yes"
m.mic_permission = lambda: m.MIC_OK
m.front_pid = lambda: 100
m.SOUNDS = False
d = m.Dictation(app)

s = d._steady_words
check("first pass: its last word is held back", s(1, "Hello team I wanted to") == "Hello team I wanted")
check("next pass: a last word heard before is shown",
      s(1, "Hello team I wanted to share") == "Hello team I wanted to")
check("a guessed last word stays hidden", s(1, "Hello team I wanted to share a process") ==
      "Hello team I wanted to share a")
check("... and shows once heard again (punctuation ignored)",
      s(1, "Hello team I wanted to share a process.") == "Hello team I wanted to share a process.")
check("a single word is shown as it is", s(2, "Hello") == "Hello")
check("a new dictation starts fresh", s(3, "Okay then") == "Okay")
check("the reading window is short (8 s for two lines)",
      m.LIVE_WINDOW_SECONDS * m.LIVE_LINES <= 10, m.LIVE_WINDOW_SECONDS * m.LIVE_LINES)

# "Transcribing…" while the final read takes longer than 0.7 s (the read is
# slowed down on purpose here, so this needs no speech model).
import numpy as np


class SlowModel:
    def recognize(self, audio, sample_rate=16000):
        time.sleep(1.6)
        return "hello there"


d.model = SlowModel()
d.vad = None
d.model_event.set()
d.hotkey.port = 1
fake_recorder(d, held_seconds=5)
d.hotkey.physically_down = lambda: True
m.LIVE_PREVIEW = False
d.on_press()
feed(d, (0.3 * np.sin(np.arange(16000 * 3) / 7.0)).astype(np.float32))
d.on_release()
seen = wait_until(lambda: d.overlay.mode == "message" and d.overlay.message == d.WORKING, 3)
check("'Transcribing…' shown while the text is not ready", seen)
check("the text is typed afterwards", wait_until(lambda: bool(typed), 10), typed)
check("the pill no longer says 'Transcribing…'", wait_until(
    lambda: not (d.overlay.mode == "message" and d.overlay.message == d.WORKING), 3))
finish()
