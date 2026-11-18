"""Start at login in the setup window: ticked at first (as Windows' "Start
with Windows"), applied only when setup is finished (quitting during setup
adds nothing), the choice survives the restart during setup, and a later
visit shows and changes the real state at once. macOS is never asked: the
login item calls are replaced."""
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
check("first setup: ticked", w.login.isChecked())
check("nothing applied before setup is finished", not calls)
w.login.setChecked(False)
w.login.setChecked(True)
check("ticking and unticking during setup applies nothing", not calls)
w.done(0)
check("Done applies the tick once", calls == [True], calls)
check("setup marked finished", m._config.get("welcomed") is True)

w2 = m.SetupWindow(d)
w2.typing_ok = lambda: True
check("a later visit shows the real state", w2.login.isChecked() and not w2.first_setup)
w2.login.setChecked(False)
check("unticking later applies at once", calls == [True, False], calls)

m._config.pop("welcomed", None)
m.save_setting("setup_login", False)
w3 = m.SetupWindow(d)
check("unticked during setup, then restarted: stays unticked", not w3.login.isChecked())

calls.clear()
w4 = m.SetupWindow(d)
w4.typing_ok = lambda: False
d.quit = lambda: None
w4.done(0)
check("quitting during setup adds nothing to Login Items", not calls, calls)
finish()
