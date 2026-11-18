"""Type as you speak: quiet words are kept. A piece, or the ending after the
last pause, is skipped as noise only when no words were heard in it at all.
Spoken: a normal sentence, then a quiet one with a little room noise (at
several levels; before this, "notes by Friday afternoon" went missing at
0.12, 0.06 and 0.03). And noise alone after speech still types nothing."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import numpy as np

need_model()
m = load_app()
app = qt_app(None)
typed = []
m.type_text = lambda text: typed.append(text) and None
m.focused_text_box = lambda: "yes"
m.front_pid = lambda: 4242
m.mic_permission = lambda: m.MIC_OK
m.LIVE_TYPE, m.SOUNDS = True, False
d = m.Dictation(app)
load_model(d)
fake_recorder(d)
d.hotkey.physically_down = lambda: True
loud, _ = speech("short")
long, _ = speech("speech")
rng = np.random.default_rng(1)


def dictate(audio):
    typed.clear()
    d.on_press()
    feed_real_time(d, audio, 640)
    d.on_release()
    wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
    pump(1.5)
    return "".join(typed)


for level in (0.12, 0.06, 0.03):
    quiet = long[-int(RATE * 3.6):] * level               # "...by Friday afternoon."
    noise = (rng.standard_normal(len(quiet)) * 0.004).astype(np.float32)
    full = dictate(np.concatenate([loud, quiet + noise, np.zeros(1600, np.float32)]))
    say(f"level {level}: {full!r}")
    check(f"quiet ending at {level} is typed", plain_words(full)[-3:] ==
          ["by", "friday", "afternoon"], full)

noise = (rng.standard_normal(RATE * 3) * 0.01).astype(np.float32)
full = dictate(np.concatenate([loud, noise]))
say(f"noise after speech: {full!r}")
check("noise alone after speech adds no words", plain_words(full)[-2:] == ["dictation", "app"],
      full)
finish()
