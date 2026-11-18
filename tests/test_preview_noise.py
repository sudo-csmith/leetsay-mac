"""The live words never show a word the model "hears" in room noise (an
"Okay" before anything was said, as Windows fixed): a preview pass runs the
voice detector first and shows nothing when it hears no speech. Real
speech still shows."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

need_model()
m = load_app()
app = qt_app(None)
import numpy as np
m.mic_permission = lambda: m.MIC_OK
m.SOUNDS = False
d = m.Dictation(app)
load_model(d)
shown = []
d.live_text.connect(lambda session, text: shown.append(text))
rng = np.random.default_rng(5)
R = 16000
d.hotkey.physically_down = lambda: True    # the key is "held" for the whole test
d.watchdog.stop()
d.recording = True
for name, audio in (("room hiss", (rng.standard_normal(R * 3) * 0.01).astype(np.float32)),
                    ("fan rumble", (np.convolve(rng.standard_normal(R * 3), np.ones(60) / 60,
                                                mode="same") * 0.3).astype(np.float32)),
                    ("breath-like noise", (rng.standard_normal(R * 2) * 0.02
                                           * np.hanning(R * 2)).astype(np.float32))):
    shown.clear()
    d.live_busy = True
    d._live_run(audio, R, 1)
    pump(0.1)
    check(f"{name}: nothing shown on the card", not shown, shown)
audio, words = speech("short")
shown.clear()
d.live_busy = True
d._live_run(audio, R, 1)
pump(0.1)
ok, found = heard(shown[-1] if shown else "", words)
check("real speech still shows", bool(shown) and ok, shown)
d.recording = False
finish()
