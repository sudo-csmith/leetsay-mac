"""Start at login: switched on when setup is finished (as Windows' "Start
with Windows", ticked in its introduction), never before (quitting during
setup adds nothing to Login Items), and not again on later visits to the
setup window (a choice made in Settings stays). The setup window has no
colour or Start at login step. macOS is never asked: the login item calls
are replaced."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
calls = []
m.FROZEN = True
m.set_start_at_login = lambda on: (calls.append(on), True)[1]
m.starts_at_login = lambda: bool(calls and calls[-1])
m.mic_permission = lambda: m.MIC_OK
d = m.Dictation(app)
d.hotkey.port = 1

w = m.SetupWindow(d)
w.typing_ok = lambda: True
check("no colour / Start at login step any more", not hasattr(w, "login") and not hasattr(w, "extras"))
check("nothing applied while setup is open", not calls)
w.done(0)
check("finishing setup switches Start at login on", calls == [True], calls)
check("setup marked finished", m._config.get("welcomed") is True)

calls.append(False)                       # switched off later in Settings
w2 = m.SetupWindow(d)
w2.typing_ok = lambda: True
w2.done(0)
check("a later visit to setup leaves the Settings choice alone", calls == [True, False], calls)

m._config.pop("welcomed", None)
calls.clear()
w4 = m.SetupWindow(d)
w4.typing_ok = lambda: False
d.quit = lambda: None
w4.done(0)
check("quitting during setup adds nothing to Login Items", not calls, calls)
finish()
