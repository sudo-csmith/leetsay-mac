"""One-time tip for typing as you speak (as Windows 0.2.4, 27af2dc): after
the 3rd dictation of a session, with Type as you speak off, the pill says
"Want words typed as you speak? Click me" for 6 s with a pulse; a click
opens Settings > Typing. Shown once ever (live_tip_seen); not when Type as
you speak is on, nor while busy; never in the settings line."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
m.mic_permission = lambda: m.MIC_OK
m.LIVE_TYPE = False
TIP = "Want words typed as you speak? Click me"


def setup_done(x):
    x.hotkey.port = 1                            # set up: no "Setup" pill over the tip
    x.watchdog.stop()
    return x


d = setup_done(m.Dictation(app))
shown, opened = [], []
d.overlay.show_message = lambda text, ms=1600, pulse=False: (
    shown.append((text, ms, pulse)) if text == TIP else None, setattr(d.overlay, "message", text))
d.open_settings = lambda tab=None: opened.append(tab)
d.overlay.dismiss = lambda force=False: None

for i in range(2):
    d.maybe_live_tip()
pump(2.8)
check("not after 2 dictations", not shown, shown)
d.maybe_live_tip()
pump(2.8)
check("after the 3rd: the tip, 6 s, with a pulse",
      shown == [("Want words typed as you speak? Click me", 6000, True)], shown)
check("saved as seen", m._config.get("live_tip_seen") is True)
d._notice_clicked()
check("a click opens Settings > Typing", opened == ["Typing"], opened)
for i in range(5):
    d.maybe_live_tip()
pump(2.8)
check("never again", len(shown) == 1, shown)

m._config.pop("live_tip_seen", None)
d2 = setup_done(m.Dictation(app))
d2.overlay.show_message = lambda text, ms=1600, pulse=False: shown.append(text) if text == TIP else None
m.LIVE_TYPE = True
for i in range(3):
    d2.maybe_live_tip()
pump(2.8)
check("not when Type as you speak is on", len(shown) == 1, shown)
m.LIVE_TYPE = False
d3 = setup_done(m.Dictation(app))
d3.overlay.show_message = lambda text, ms=1600, pulse=False: shown.append(text) if text == TIP else None
for i in range(3):
    d3.maybe_live_tip()
d3.recording = True                              # busy when it would show: never
pump(2.8)
check("not while dictating (and not saved as seen)", len(shown) == 1 and
      not m._config.get("live_tip_seen"), shown)
d3.recording = False
check("not in the settings line", "live_tip_seen" not in m._PORTABLE_CHECKS)
finish()
