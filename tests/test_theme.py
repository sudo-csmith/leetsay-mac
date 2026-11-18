"""The light Settings theme (General and Look pages) and 1337 mode on and
off: the look changes, is saved, and comes back as before. (Was themetest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app()
out = out_dir("themes")
d = m.Dictation(app)
accent_before, bg_before = m.ACCENT, m.POPUP_BG
m.MENU_THEME = "light"
check("light theme style", m.settings_style() != "" and m.LIGHT_STYLE.strip()[:20] in m.settings_style())
w = m.SettingsWindow(d)
w.show()
for name in ("General", "Look"):
    w.show_tab(name)
    app.processEvents()
    w._fit_height()
    app.processEvents()
    w.grab().save(os.path.join(out, f"light_{name}.png"))
m.toggle_leet(d)
app.processEvents()
w.show_tab("Typing")
app.processEvents()
w.grab().save(os.path.join(out, "leet_Typing.png"))
say("leet:", m.LEET_MODE, m.ACCENT)
check("1337 mode on", m.LEET_MODE is True)
check("1337 accent", m.ACCENT == m._LEET_LOOK["ACCENT"], m.ACCENT)
check("1337 saved", m._config.get("leet_mode") is True)
check("1337 style used", m.LEET_STYLE.strip()[:20] in m.settings_style())
m.toggle_leet(d)
check("1337 mode off", m.LEET_MODE is False)
check("accent back", m.ACCENT == accent_before, m.ACCENT)
check("pop-up background back", m.POPUP_BG == bg_before, m.POPUP_BG)
check("off saved", m._config.get("leet_mode") is False)
finish()
