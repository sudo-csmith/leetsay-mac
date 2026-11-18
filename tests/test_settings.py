"""Text cleaning (fillers, times, word replacements), the "move settings"
line (export, import, a Windows line, junk), the text box check, and every
Settings page drawn without errors. (Was settingstest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import base64, json

m = load_app()
check("settings file is in the throwaway HOME", m.SETTINGS_FILE.startswith(HOME))

def eq(name, got, want):
    return check(name, got == want, "" if got == want else f"got {got!r}, want {want!r}")
eq("fillers", m.clean_text("Um, it seems so, um, this works right now um."),
   "It seems so, this works right now.")
eq("time", m.clean_text("I said 3.47 p.m. today"), "I said 3:47 p.m. today")
eq("time pm glued", m.clean_text("at 9.05pm"), "at 9:05pm")
eq("decimal kept", m.clean_text("It is 3.47 metres long."), "It is 3.47 metres long.")
eq("replacement", m.clean_text("I use leaked say every day."), "I use leetsay every day.")
eq("replacement capital", m.clean_text("Leet say is great"), "Leetsay is great")
eq("plain text", m.clean_text("Hello team, I wanted to share a quick update."),
   "Hello team, I wanted to share a quick update.")
m.REMOVE_FILLERS = False
eq("fillers kept when off", m.clean_text("Um, yes"), "Um, yes")
m.REMOVE_FILLERS = True

# The settings line: a Mac export imported again; a Windows-style line.
m._config.update({"hotkey": "right_command", "add_space": False, "mic": "Secret Mic",
                  "replacements": [["a", "b"]]})
line = m.export_settings_line()
data = json.loads(base64.urlsafe_b64decode(line.split(":", 1)[1] + "==="))
eq("export holds only portable keys (no microphone name, no replacements)",
   sorted(data), ["add_space", "hotkey"])
eq("import own line", m.read_settings_line(line),
   ({"add_space": False, "hotkey": "right_command"}, {}, 0, ""))
win = {"hotkey": "ctrl+space", "accent": "#3DDC97", "remove_fillers": False,
       "textbox_only": False, "max_seconds": 600}
wline = m._PORTABLE_PREFIX + base64.urlsafe_b64encode(json.dumps(win).encode()).decode().rstrip("=")
good, careful, dropped, why = m.read_settings_line(wline)
eq("Windows line: good", good, {"accent": "#3DDC97", "remove_fillers": False, "max_seconds": 600})
eq("Windows line: text box detection off needs a yes", careful, {"textbox_only": False})
eq("Windows line: Windows hotkey left out", dropped, 1)
eq("junk line refused", m.read_settings_line("hello")[3][:22], "That is not a settings")
m._config.clear()

box = m.focused_text_box()
check("text box check answers", box in ("yes", "no", "password", "unknown"), box)
say("start at login available here:", m._login_service() is not None)
say("microphones:", len(m.input_devices()))

app = qt_app()
d = m.Dictation(app)
w = m.SettingsWindow(d)
w.show()
out = out_dir("settings")
for i, name in enumerate(m.SettingsWindow.TABS):
    w.show_tab(name)
    app.processEvents()
    w._fit_height()
    app.processEvents()
    pic = w.grab()
    check(f"page {name} drawn", not pic.isNull() and w._tabs.currentIndex() == i,
          f"{w.width()} x {w.height()}")
    pic.save(os.path.join(out, f"tab_{i}_{name}.png"))
finish()
