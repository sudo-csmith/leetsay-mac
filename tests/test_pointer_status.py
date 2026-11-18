"""The tag by the mouse pointer (as Windows 0.2.4: 5172c9a, aa3955f,
d520eb0): a microphone problem in red comes first, then "No text box" in
amber, then "Listening" in the accent colour; a new look must hold steady
for 0.9 s (red and "Typing..." change at once); after letting go it says
"Typing..." until the words are in; taps hide it at once; a microphone that
won't open is said for 3 s; it moves only when the mouse moves; the
settings are in the settings line."""
import os, sys, time
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
m.mic_permission = lambda: m.MIC_OK
check("both on by default", m.POINTER_HINT and m.POINTER_STATUS)
d = m.Dictation(app)
d.watchdog.stop()
d.hotkey.physically_down = lambda: True
d.recording, d.lt_active = True, False
O = m.Overlay

d.overlay.warning = ""
d._pointer_hint(False)
b = d.pointer_badge
check("while dictating: \"Listening\" in the accent colour", (b.text, b.colour) == ("Listening", "accent"),
      (b.text, b.colour))
d._pointer_hint(True)
check("\"No text box\" waits until it holds steady", (b.text, b.colour) == ("Listening", "accent"))
d._badge_pending = (("No text box", "warning"), time.monotonic() - 1.0)
d._pointer_hint(True)
check("... and shows after 0.9 s", (b.text, b.colour) == ("No text box", "warning"), (b.text, b.colour))
d.overlay.warning = O.NO_SOUND
d._pointer_hint(True)
check("a microphone problem comes first, in red, at once",
      (b.text, b.colour) == ("No sound from the microphone", "danger"), (b.text, b.colour))
d.overlay.warning = O.CANT_HEAR
d._pointer_hint(False)
check("\"Can't hear you\" in red", (b.text, b.colour) == ("Can't hear you", "danger"))
d.overlay.warning = ""

m.POINTER_STATUS = False
d._pointer_hint(False)
pump(0.3)
check("Listening off: no tag without a problem", not b.isVisible() or b.target == 0.0)
m.POINTER_STATUS = True

# after letting go: "Typing..." until the words are in
d.recording = False
d.reading_since = time.monotonic()
d._pointer_off(typing=True)
check("let go: \"Typing…\" at once", (b.text, b.colour) == ("Typing…", "accent"))
pump(1.0)
check("still there while the text is read", b.target == 1.0)
d.reading_since = None
d._typing_busy = True
pump(0.3)
check("still there while it types", b.target == 1.0)
d._typing_busy = False
wait_until(lambda: b.target == 0.0, 3)
check("gone once the words are in", b.target == 0.0)

d._pointer_off()
check("a tap or silence: gone at once", b.target == 0.0 and not d.typing_watch.isActive())

d._pointer_note(d.POINTER_MIC[O.NO_MIC], 300)
check("microphone won't open: said in red", (b.text, b.colour) == ("Microphone not detected", "danger"))
pump(0.5)
check("... for a moment", b.target == 0.0)

# moves only when the mouse moves
moves = []
b.appear()
real_move = b.move
b.move = lambda spot: (moves.append(spot), real_move(spot))
b._last_cursor = None
b._follow(); b._follow(); b._follow()
check("moves only when the mouse moved", len(moves) <= 1, len(moves))

good, careful, dropped, why = m.read_settings_line(m.export_settings_line())
m.set_option("POINTER_STATUS", "pointer_status", False)
good, careful, dropped, why = m.read_settings_line(m.export_settings_line())
check("pointer_status in the settings line", good.get("pointer_status") is False, good)
finish()
