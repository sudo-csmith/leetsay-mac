"""The hotkey's two modes. Hold (default): down, speak, up -> typed. Press
to start and stop: a tap starts, the key being up doesn't stop it, a
shortcut (Option+E) while listening keeps it going, a second tap finishes
and types; a shortcut on the starting press cancels; a quick double tap
doesn't type the kept text again. Also the wording and the settings line
key. (Was toggletest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

need_model()
m = load_app()
app = qt_app(None)
typed = []
m.type_text = lambda t: typed.append(t)
m.focused_text_box = lambda: "yes"
m.mic_permission = lambda: m.MIC_OK
m.front_pid = lambda: 100
m.LIVE_PREVIEW = False
m.SOUNDS = False
d = m.Dictation(app)
load_model(d)
d.hotkey.port = 1
audio, words = speech("short")
fake_recorder(d)
DOWN = {"v": False}
d.hotkey.physically_down = lambda: DOWN["v"]


def down():
    DOWN["v"] = True
    d._key_down()
    pump(0.05)


def up():
    DOWN["v"] = False
    d._key_up()
    pump(0.05)


def finished():
    return typed and not d.recording and d.reading_since is None


# Hold mode (default): down, speak, up -> typed.
m.HOLD_TO_TALK = True
typed.clear()
down(); feed(d, audio); pump(0.5); up()
check("hold: typed", wait_until(finished, 30), typed)
ok, found = heard(" ".join(typed), words)
check("hold: the words were heard", ok, found)

# Press to start and stop.
d.set_hold_to_talk(False)
check("press mode set", m.HOLD_TO_TALK is False)
typed.clear()
down(); up(); pump(0.4)
check("press: recording after the first tap", d.recording)
feed(d, audio)
pump(1.0)                                       # key up: the safety check must not stop it
check("press: still recording with the key up 1 s later", d.recording)
down(); d._key_spoiled(); up(); pump(0.2)       # Option+E while listening
check("press: a shortcut while listening keeps it going", d.recording)
down(); up()
check("press: second tap finishes and types", wait_until(finished, 30), typed)

typed.clear()
down(); d._key_spoiled(); up(); pump(0.5)
check("press: a shortcut on the first press -> nothing", not d.recording and not typed)

m.KEEP_LAST = True
d.remember("old words")
typed.clear()
down(); up(); pump(0.05); down(); up(); pump(1.0)
check("press: a quick double tap types nothing", not typed, typed)
m.KEEP_LAST = False
d.forget()

say("menu status:", d.key_name(), "|", m.how_words("Right Option"))
press_words = m.how_words("Right Option")
d.set_hold_to_talk(True)
say("hold words:", m.how_words("Right Option"))
check("the wording differs between the modes", press_words != m.how_words("Right Option"))
check("hold_to_talk moves in the settings line", "hold_to_talk" in m._PORTABLE_CHECKS)
finish()
