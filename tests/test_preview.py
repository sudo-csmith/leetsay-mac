"""The live words on the card and the moment after letting go: the preview
re-reads a short stretch of recent audio (so it keeps up), and from the
moment the hotkey is let go the card is a small "Transcribing…" pill (no
sound wave) until the words are ready, also with type as you speak."""
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

check("the reading window is short (8 s for two lines)",
      m.LIVE_WINDOW_SECONDS * m.LIVE_LINES <= 10, m.LIVE_WINDOW_SECONDS * m.LIVE_LINES)

# "Transcribing…" from letting go until the words are ready (the read is
# slowed down on purpose here, so this needs no speech model).
import numpy as np


class SlowModel:
    def recognize(self, audio, sample_rate=16000):
        time.sleep(1.6)
        return "hello there"

    def with_timestamps(self):
        class Timed:
            def recognize(self, audio, sample_rate=16000):
                time.sleep(1.6)
                from types import SimpleNamespace
                return SimpleNamespace(tokens=[" hello", " there"], timestamps=[2.1, 2.4])
        return Timed()


d.model = SlowModel()
d.vad = None
d.model_event.set()
d.hotkey.port = 1
fake_recorder(d, held_seconds=5)
d.hotkey.physically_down = lambda: True
m.LIVE_PREVIEW = False
d.on_press()
feed(d, (0.3 * np.sin(np.arange(16000 * 3) / 7.0)).astype(np.float32))
let_go = time.monotonic()
d.on_release()
seen = wait_until(lambda: d.overlay.mode == "message" and d.overlay.message == d.WORKING, 3)
after = time.monotonic() - let_go
check("'Transcribing…' shown while the text is not ready", seen)
check("... from the moment the catch ends (no 0.7 s wait)",
      after < m.LAST_WORD_MS / 1000 + 0.15, f"{after:.2f} s")
check("... as the small pill, without the sound wave", d.overlay.mode == "message")
check("the text is typed afterwards", wait_until(lambda: bool(typed), 10), typed)
check("the pill no longer says 'Transcribing…'", wait_until(
    lambda: not (d.overlay.mode == "message" and d.overlay.message == d.WORKING), 3))

# The same with type as you speak (it read the rest without the pill before).
typed.clear()
m.LIVE_TYPE = True
d.recorder.rate = 16000
d.on_press()
check("type as you speak is on", d.lt_active)
feed(d, (0.3 * np.sin(np.arange(16000 * 3) / 7.0)).astype(np.float32))
d.lt_commit = 16000                       # a piece typed already: the rest is read
d.on_release()
seen = wait_until(lambda: (d.overlay.mode == "message" and d.overlay.message == d.WORKING)
                  or not d.lt_active, 3)
check("type as you speak: 'Transcribing…' after letting go", seen and d.lt_active,
      (d.overlay.mode, getattr(d.overlay, "message", "")))
wait_until(lambda: d.reading_since is None, 10)
check("type as you speak: the pill goes when the words are ready", wait_until(
    lambda: not (d.overlay.mode == "message" and d.overlay.message == d.WORKING), 3))
finish()
