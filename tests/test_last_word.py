"""Last-word catch (as Windows 0.2.4, df17f0a/c6f96e5): after the key is let
go the microphone keeps listening for last_word_ms (default 400, 250-1000)
so a word still being finished isn't cut off; a second release meanwhile
changes nothing; taps are judged as on Windows; Settings > Audio has the
slider ("0.40 s") and the note; the setting is in the settings line."""
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app("Fusion")
import numpy as np
m.mic_permission = lambda: m.MIC_OK
m.SOUNDS = False
check("default 400 ms", m.LAST_WORD_MS == 400)
d = m.Dictation(app)
d.model = object()
d.model_event.set()
d.hotkey.port = 1
fake_recorder(d)
d.hotkey.physically_down = lambda: True
d.watchdog.stop()
got = []
d._transcribe = lambda seq, audio, rate, quiet, skip=None: got.append(len(audio) / float(rate))
R = 16000

d.on_press()
feed(d, np.full(R, 0.2, np.float32))             # 1 s before letting go
d.on_release()
check("still listening right after letting go", d.recording)
feed(d, np.full(int(R * 0.3), 0.2, np.float32))  # the end of a word, during the catch
d.on_release()                                   # a second release changes nothing
pump(0.2)
check("still listening 0.2 s later", d.recording)
done = wait_until(lambda: got, 3)
check("finished after the catch", done and not d.recording)
check("the sound during the catch is kept", got and abs(got[-1] - 1.3) < 0.01, got)

# taps, judged as on Windows (less than ~0.1 s of sound before letting go)
said = []
d.overlay.dismiss = lambda force=False: said.append("dismissed")
for before, want_tap in ((0.05, True), (0.2, False)):
    got.clear(); said.clear()
    d.reading_since = None                       # (the stand-in reading never reports back)
    d.on_press()
    must("recording started", d.recording)
    feed(d, np.full(int(R * (before + m.LAST_WORD_MS / 1000.0)), 0.2, np.float32))
    d.on_release()
    wait_until(lambda: not d.recording, 3)
    pump(0.1)
    check(f"{before:.2f} s before letting go: {'a tap' if want_tap else 'a dictation'}",
          (not got) == want_tap, (got, said))

# Settings > Audio: the slider
m.SettingsWindow  # noqa
w = m.SettingsWindow(d)
check("slider 0.25-1 s in twentieths", (w.catch.minimum(), w.catch.maximum()) == (5, 20))
check("shown as \"0.40 s\"", w.catch_value.text() == "0.40 s", w.catch_value.text())
w.catch.setValue(12)
check("moving it saves milliseconds", m._config.get("last_word_ms") == 600 and
      w.catch_value.text() == "0.60 s", (m._config.get("last_word_ms"), w.catch_value.text()))
from PySide6.QtWidgets import QLabel
check("the note is there", any(l.text().startswith("Keeps listening a moment after you let go")
                               for l in w.findChildren(QLabel)))
good, careful, dropped, why = m.read_settings_line(m.export_settings_line())
check("in the settings line", good.get("last_word_ms") == 600, good)
import json, base64
bad = "leetsay-settings-1:" + base64.urlsafe_b64encode(json.dumps({"last_word_ms": 5000})
                                                       .encode()).decode().rstrip("=")
check("out of range is left out", "last_word_ms" not in m.read_settings_line(bad)[0])
finish()
