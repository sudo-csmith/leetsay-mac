"""Type as you speak: the first words of a new reading that only repeat the
end of what was just typed (the context read again) are not typed twice; a
short echo ("no, no") and new words are kept. Windows' cases, then a spoken
recording played in real time: no run of 3 words typed twice."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time, types

m = load_app()
D = m.Dictation


def skip(typed, words, seg=()):
    holder = types.SimpleNamespace(lt_done=typed, lt_pending="", lt_seg_words=list(seg),
                                   REPEAT_MIN=D.REPEAT_MIN, _plain=D._plain)
    return D._skip_repeat(holder, words), holder


n, _ = skip("I only said it once and just put it twice for some reason.",
            "and just put it twice for some reason, so I'm not sure.".split())
check("a whole phrase read again is skipped", n == 8, n)
n, _ = skip("Hello there for some reason.", "for some reason it fails".split())
check("the end read again is skipped", n == 3, n)
check("new words kept", skip("Hello there.", "How are you".split())[0] == 0)
check("a short echo is kept", skip("I said no", "no, it is fine".split())[0] == 0)
check("nothing typed yet: nothing skipped", skip("", "one two three".split())[0] == 0)

# Part of the piece typed already, and a reading brings back more of the
# words before it than the line-up looks at: only the new words are typed.
words = "be fine? Like, the first line seems to get messed up.".split()
_, holder = skip("Could that be fine? Like, the first line seems", words,
                 seg=["line", "seems"])
begin = max(D._after_typed(holder, D._plain(words)), D._skip_repeat(holder, words))
check("earlier words back in a started piece", " ".join(words[begin:]) == "to get messed up.",
      words[begin:])

# Spoken: the whole typed text holds no run of 3 words twice.
if MODEL_AVAILABLE:
    app = qt_app(None)
    typed = []
    m.type_text = lambda text: typed.append(text) and None
    m.focused_text_box = lambda: "yes"
    m.front_pid = lambda: 4242
    m.mic_permission = lambda: m.MIC_OK
    m.LIVE_TYPE, m.SOUNDS = True, False
    d = m.Dictation(app)
    load_model(d)
    audio, key = speech("speech")
    fake_recorder(d)
    d.hotkey.physically_down = lambda: True
    d.on_press()
    feed_real_time(d, audio, 640)
    d.on_release()
    wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
    pump(1.5)
    full = "".join(typed)
    say("TYPED:", full)
    plain = plain_words(full)
    runs = [tuple(plain[i:i + 3]) for i in range(len(plain) - 2)]
    twice = sorted({" ".join(r) for r in runs if runs.count(r) > 1})
    check("spoken: no run of 3 words typed twice", not twice, twice)
    check("spoken: the words are there", heard(full, key)[0], full)
else:
    say("no speech model: the spoken part is skipped")
finish()
