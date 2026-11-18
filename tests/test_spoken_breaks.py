"""Spoken line breaks (as Windows 0.2.4, c6f96e5): "new line" / "new
paragraph" said on their own become a line break, typed as Shift+Return
(never Return); ordinary sentences stay words; off leaves words; terminals
(and Messages, where Shift+Return can send) get a space. The Windows test
cases are run as they are."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
text_of = lambda s: m.join_words(m.clean_words(s.split()))

m.SPOKEN_BREAKS = True
for said, want in (("Hi Tom. New line. Can we meet at three?", "Hi Tom.\nCan we meet at three?"),
                   ("Dear team, new line, thanks for today.", "Dear team,\nThanks for today."),
                   ("First point. New paragraph. Second point.", "First point.\n\nSecond point."),
                   ("New line. Hi.", "\nHi.")):
    check(f"{said!r} -> line break", text_of(said) == want, repr(text_of(said)))
for sentence in ("I bought a new line of credit.", "Is this new? Line two.", "I need a new line.",
                 "The new paragraph is fine.", "Hello new line"):
    check(f"{sentence!r} stays words", text_of(sentence) == sentence, repr(text_of(sentence)))
m.SPOKEN_BREAKS = False
check("switched off: words stay", text_of("Hi. New line. Bye.") == "Hi. New line. Bye.")
m.SPOKEN_BREAKS = True

check("terminal: a space", m.no_breaks_in_terminal("ls\nrm", "com.apple.Terminal") == "ls rm")
check("iTerm: a space", m.no_breaks_in_terminal("a\n\nb", "com.googlecode.iterm2") == "a b")
check("Messages: a space", m.no_breaks_in_terminal("a\nb", "com.apple.MobileSMS") == "a b")
check("other apps keep the break", m.no_breaks_in_terminal("a\nb", "com.apple.Notes") == "a\nb")

check("typed as text, Shift+Return, text", m.typing_steps("Hi Tom.\nCan we") ==
      [("text", "Hi Tom."), ("break",), ("text", "Can we")], m.typing_steps("Hi Tom.\nCan we"))
check("a paragraph is two breaks", m.typing_steps("A.\n\nB.") ==
      [("text", "A."), ("break",), ("break",), ("text", "B.")])
check("never a plain Return: Shift is set", m.FLAG_SHIFT == 0x20000)
check("line breaks survive the trip back into words",
      m.words_of("Hi Tom.\nCan we") == ["Hi Tom.".split()[0], "Tom.", "\n", "Can", "we"])

app = qt_app(None)
m.mic_permission = lambda: m.MIC_OK
d = m.Dictation(app)
d._lt_reset()
check("type as you speak: no space after a line break",
      d._compose(["Hi", "Tom.", "\n", "Can", "we"]) == "Hi Tom.\nCan we",
      repr(d._compose(["Hi", "Tom.", "\n", "Can", "we"])))
# "new" waits for the next reading ("new line" may be coming)
queued = []
d._queue_words = lambda words, before=None, piece_end=False: queued.append(list(words))
d.live_session, d.recording, d.lt_active, d.lt_commit = 1, True, True, 0
d.lt_prev = d._plain(["Hi", "Tom.", "new", "line"])
d.on_live_words(1, "Hi Tom. new line", 0)
check("type as you speak holds back a trailing \"new\"",
      queued and "new" not in [w.lower() for w in queued[-1]], queued)
d.recording = False
finish()
