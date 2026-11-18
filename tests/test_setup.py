"""The setup window (typing, microphone, try it): each step's state as
macOS's answers change (faked here, macOS is never asked), closing before
step 1 quits, closing after remembers "welcomed", and the trial words are
cleared on close. (Was setuptest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app()
state = {"mic": m.MIC_UNKNOWN}
m.mic_permission = lambda: state["mic"]
m.ask_keyboard_permission = lambda: True          # never ask macOS from a test
m.request_mic_permission = lambda *a, **k: True
m.open_settings_pane = lambda which: None
d = m.Dictation(app)
quits = []
d.quit = lambda: quits.append(1)
d.hotkey.port = None
w = m.SetupWindow(d)
w.show()
out = out_dir("setup")


def shot(name):
    w.refresh()
    app.processEvents()
    w.adjustSize()
    app.processEvents()
    w.grab().save(os.path.join(out, name + ".png"))
    say("shot", name, w.width(), "x", w.height())


shot("1_start")
check("before step 1: the button quits", w.done_button.text() == "Quit leetsay", w.done_button.text())
check("before step 1: trial box off", not w.box.isEnabled())
d.keyboard_asked = True
shot("2_waiting_for_switch")
check("waiting for the switch is said", "Waiting" in w.typing["status"].text(),
      w.typing["status"].text())
d.hotkey.port = 1
shot("3_typing_allowed")
check("typing allowed", w.typing["status"].text() == "Allowed")
check("then the button is Done", w.done_button.text() == "Done")
check("microphone button offered", w.mic_button.isVisibleTo(w) and w.mic_button.isEnabled())
state["mic"] = m.MIC_DENIED
shot("4_mic_switched_off")
check("microphone off: points to its settings",
      w.mic_button.text() == "Open Microphone settings", w.mic_button.text())
state["mic"] = m.MIC_OK
d.model = object()
shot("5_ready_to_try")
check("microphone allowed", w.mic["status"].text() == "Allowed")
check("trial box on", w.box.isEnabled())
w.box.setPlainText("Hello, this is a test.")
shot("6_it_works")
check("trial words seen", w.trial["status"].text() == "It works!", w.trial["status"].text())
w.close()

# Closing before step 1 quits; after it, it doesn't.
d.hotkey.port = None
m._config.pop("welcomed", None)
w2 = m.SetupWindow(d)
w2.show()
w2.close()
check("closed before step 1 -> quit", len(quits) >= 1, quits)
check("not remembered as set up", not m._config.get("welcomed"))
n = len(quits)
d.hotkey.port = 1
w3 = m.SetupWindow(d)
w3.show()
w3.box.setPlainText("some trial words")
w3.close()
check("closed after step 1 -> no quit", len(quits) == n)
check("remembered as set up", m._config.get("welcomed") is True)
check("trial words cleared on close", w3.box.toPlainText() == "")
finish()
