"""After dictating: Return pressed after the text (no trailing space then),
a Tab countdown that a click cancels, "Stay in the app I started in" when
another app takes the front (and not when it's off), and the second hotkey
through the real key-watch callback with real CGEvents: it dictates and then
presses its own key (cmd+Return), the main key does not. Typing and keys go
into a list; the front app is faked. (Was afterkeytest.)

Waits are for the expected events (up to 30 s), never fixed times, and the
simulated app switch happens after a set number of looks at the front app,
not after a timer, so a busy machine can't change the result."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import ctypes

need_model()
m = load_app()
app = qt_app(None)
log = []
m.type_text = lambda t: (log.append(("type", t)), None)[1]
m.press_key = lambda k: (log.append(("key", k)), None)[1]
m.focused_text_box = lambda: "yes"
FRONT = {"pid": 100, "to": None, "looks": 0}


def front_pid():
    if FRONT["to"] is not None:
        FRONT["looks"] -= 1
        if FRONT["looks"] <= 0:
            FRONT["pid"], FRONT["to"] = FRONT["to"], None
    return FRONT["pid"]


def activate(pid):
    """The app comes back on the second look after asking (as if macOS took
    a moment), however slow the machine is."""
    log.append(("activate", pid))
    FRONT["to"], FRONT["looks"] = pid, 2
    return True


m.front_pid = front_pid
m.activate_app = activate
m.mic_permission = lambda: m.MIC_OK
m.LIVE_PREVIEW = False
m.SOUNDS = False
d = m.Dictation(app)
load_model(d)
audio, words = speech("short")
fake_recorder(d, held_seconds=5)
d.hotkey.physically_down = lambda: False


def kinds():
    return [a for a, _ in log]


def dictate(name, until, during=None, timeout=30):
    log.clear()
    d.on_press()
    feed(d, audio)
    if during:
        during()
    d.on_release()
    came = wait_until(lambda: until(log), timeout)
    say(f"{name}: " + " | ".join(f"{a}:{b!r}"[:70] for a, b in log))
    check(f"{name}: arrived in time", came)
    return list(log)


has_key = lambda k: (lambda l: ("key", k) in l)
has_type = lambda l: "type" in [a for a, _ in l]

m.AFTER_KEY = "enter"
r = dictate("Return after", has_key("enter"))
check("Return after: typed first, then Return", r and r[0][0] == "type" and r[-1] == ("key", "enter"))
check("Return after: no space added before Return", r and not r[0][1].endswith(" "), r[:1])
ok, found = heard(r[0][1] if r and r[0][0] == "type" else "", words)
check("Return after: the words were heard", ok, found)

m.AFTER_KEY = "tab"
m.AFTER_DELAY = 2
log.clear()
d.on_press(); feed(d, audio); d.on_release()
came = wait_until(lambda: has_type(log) and "Tab in" in str(d.overlay.message or ""), 30)
check("Tab countdown notice shown after typing", came, repr(d.overlay.message))
d._cancel_after()
pump(2.0 + 0.18 + 1.5)                         # past the moment it would have pressed
check("Tab after 2 s, cancelled: not pressed", ("key", "tab") not in log, log)
m.AFTER_KEY = ""
m.AFTER_DELAY = 0

r = dictate("other app took over", has_type, during=lambda: FRONT.update(pid=200))
check("other app took over: starting app asked back", ("activate", 100) in r)
check("other app took over: typed after it came back",
      r and r[-1][0] == "type" and FRONT["pid"] == 100)
m.RETURN_FOCUS = False
r = dictate("stay-in-app off", has_type, during=lambda: FRONT.update(pid=300))
check("stay-in-app off: not asked back", "activate" not in kinds())
m.RETURN_FOCUS = True
FRONT.update(pid=100, to=None)

# The second hotkey through the real tap callback, with real CGEvents.
m.ACTION_HOTKEY = "right_command"
m.ACTION_KEY = "cmd+enter"
d.hotkey.set_action("right_command")
CGEventSetType = m._fn(ctypes.CDLL(
    "/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices"),
    "CGEventSetType", None, ctypes.c_void_p, ctypes.c_uint32)


def flags_event(code, flags):
    ev = m.CGEventCreateKeyboardEvent(None, code, True)
    CGEventSetType(ev, m.EV_FLAGS)
    m.CGEventSetFlags(ev, flags)
    return ev


calls = []
d.hotkey.on_press = lambda: calls.append("press")
d.hotkey.on_release = lambda: calls.append("release")
d.hotkey._callback(None, m.EV_FLAGS, flags_event(54, 0x10 | 0x100000), None)  # right cmd down
app.processEvents()
check("second hotkey: pressed, seen as the second hotkey", d.hotkey.via_action, calls)
d.hotkey._callback(None, m.EV_FLAGS, flags_event(54, 0), None)
app.processEvents()
check("second hotkey: press then release", calls == ["press", "release"], calls)
d.hotkey._callback(None, m.EV_FLAGS, flags_event(61, 0x40 | 0x80000), None)  # right option
app.processEvents()
d.hotkey._callback(None, m.EV_FLAGS, flags_event(61, 0), None)
app.processEvents()
check("main key: not the second hotkey", not d.hotkey.via_action, calls)
d.hotkey.on_press, d.hotkey.on_release = d.on_press, d.on_release

d.hotkey.via_action = True
r = dictate("second hotkey dictation", has_key("cmd+enter"))
check("second hotkey dictation ends with cmd+Return", r and r[-1] == ("key", "cmd+enter"))
d.hotkey.via_action = False
r = dictate("main key dictation", has_type)
pump(0.6)                                       # (a key would follow within 0.2 s)
check("main key dictation: typed, no key pressed", kinds() == ["type"], log)
finish()
