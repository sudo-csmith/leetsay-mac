"""Type as you speak: the last reading after letting go is lined up with the
end of the typed text (a run of 2+ words reaching the last typed word), and
everything after it is typed; the word times decide only when it can't be
lined up. Windows' cases, then spoken recordings played in real time: the
last words of each are typed, nothing twice."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
line_up = m.Dictation._after_tail

whole = "it cuts off a, but when the like".split()
check("words the times put in the context are kept",
      " ".join(whole[line_up("Here at the end it cuts off a", whole, 8):]) == "but when the like")
whole = "be fine? Like, the first line seems to get messed up.".split()
check("a context word read as new is not typed twice",
      " ".join(whole[line_up("Could that be fine? Like, the first line seems", whole, 0):])
      == "to get messed up.")
whole = "we went to the shop and then home".split()
check("one last word heard differently still lines up",
      " ".join(whole[line_up("so we went to the shops", whole, 5):]) == "and then home")
check("nothing to line up with: the times decide",
      line_up("Hello there", "something else entirely".split(), 1) is None)
check("nothing typed yet: the times decide", line_up("", "one two".split(), 0) is None)

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
    fake_recorder(d)
    d.hotkey.physically_down = lambda: True
    for kind, last in (("speech", "afternoon"), ("short", "app")):
        audio, key = speech(kind)
        typed.clear()
        d.on_press()
        feed_real_time(d, audio, 640)
        d.on_release()
        wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
        pump(1.5)
        full = "".join(typed)
        say(f"TYPED ({kind}):", full)
        plain = plain_words(full)
        check(f"spoken {kind}: the last word is typed", plain[-1:] == [last], plain[-3:])
        runs = [tuple(plain[i:i + 3]) for i in range(len(plain) - 2)]
        check(f"spoken {kind}: nothing typed twice",
              not [r for r in runs if runs.count(r) > 1])
        pump(0.5)
else:
    say("no speech model: the spoken part is skipped")
finish()
