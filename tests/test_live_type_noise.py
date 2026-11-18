"""Type as you speak never types a word the model "hears" in noise (as
Windows 0.2.4, 9309193): every reading while speaking (settled words,
pieces at a pause) first asks the voice detector about the NEW audio, and
noise gives nothing; the rest after letting go keeps the 2 s safety net
and says why when nothing is typed. Real speech still comes through."""
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
R = 16000
rng = np.random.default_rng(7)
noise = (rng.standard_normal(R * 3) * 0.01).astype(np.float32)
speech_audio, words = speech("short")
context = speech_audio[: R * 1]                     # 1 s of earlier speech as context
words_seen, pieces, results = [], [], []
d.live_session = 99                                 # the app's own handlers ignore these
d.live_words.connect(lambda s, t, start, before: words_seen.append(t))
d.live_piece.connect(lambda s, t, end, start, before: pieces.append(t))
d.result.connect(lambda seq, t, quiet: results.append((t, quiet)))

# settled words: context + noise -> nothing
d.live_busy = True
d._live_read_run(np.concatenate([context, noise]), 0, 1, 1.0)
pump(0.1)
check("settled words: noise after speech types nothing", not words_seen, words_seen)
d.live_busy = True
d._live_read_run(np.concatenate([context, speech_audio]), 0, 1, 1.0)
pump(0.1)
check("settled words: speech comes through", words_seen and words_seen[-1].strip(), words_seen)

# a piece at a pause: noise -> done, nothing typed
d.live_busy = True
d._live_piece_run(np.concatenate([context, noise]), R * 4, 1, 0, 1.0)
pump(0.1)
check("a noise-only piece is finished with nothing typed", pieces == [""], pieces)
d.live_busy = True
d._live_piece_run(np.concatenate([context, speech_audio]), R * 4, 1, 0, 1.0)
pump(0.1)
check("a spoken piece is typed", len(pieces) == 2 and pieces[1].strip(), pieces)

# the rest after letting go: short noise -> "Didn't catch that"; silent -> "Can't hear you"
d.seq = 5
d.recorder.peak = 0.3
d._transcribe(5, np.concatenate([context, noise[: int(R * 1.2)]]), R, False, skip=1.0)
pump(0.1)
check("short noise after the last pause: nothing, not quiet", results[-1] == ("", False), results)
d.recorder.peak = 0.002
d._transcribe(5, np.concatenate([context, np.zeros(int(R * 1.2), np.float32)]), R, False, skip=1.0)
pump(0.1)
check("near-silence after the last pause: nothing, quiet", results[-1] == ("", True), results)
d.recorder.peak = 0.3
d._transcribe(5, np.concatenate([context, noise[: int(R * 2.5)]]), R, False, skip=1.0)
pump(0.1)
check("2 s or more of sound is still read (safety net)", len(results) == 3, results)
d._transcribe(5, np.concatenate([context, speech_audio]), R, False, skip=1.0)
pump(0.1)
check("speech after the last pause is typed", results[-1][0].strip(), results[-1])

# the reason shown when nothing is left to type
shown = []
d.overlay.show_message = lambda text, ms=1600, pulse=False: shown.append(text)
d.lt_active, d.lt_pending, d._typed_live = True, "", ""
d._lt_finish("", True)
check('nothing left, quiet mic: "Can\'t hear you. Check the mic"',
      shown and shown[-1] == "Can't hear you. Check the mic", shown)
d.lt_active = True
d._lt_finish("", False)
check('nothing left, noise: "Didn\'t catch that"', shown and shown[-1] == "Didn't catch that",
      shown)
finish()
