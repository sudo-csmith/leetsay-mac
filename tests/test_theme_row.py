"""Settings › Look › Colours: one Theme row for the pop-up and the windows
together (as Windows), with "Same as macOS" (Mac): Dark / Light / Same as
macOS / Custom. Dark and Light set both; Same as macOS makes both follow
macOS's Light or Dark (the pop-up's background switches with it, a colour of
your own stays); Custom is the pop-up's own colour and is lit whenever the
pop-up and the windows differ. Saved as the Windows keys menu_theme and
popup_bg. macOS's appearance is faked here."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app()
mac = {"light": False}
m.light_menus = lambda: (mac["light"] if m.MENU_THEME == "system"
                         else m.MENU_THEME == "light") and not m.LEET_MODE
d = m.Dictation(app)
w = m.SettingsWindow(d)
DARK, LIGHT = m.BACKGROUND_CHOICES[0][1], m.BACKGROUND_CHOICES[1][1]


def lit():
    on = [b.text() for b, _v, _m in w.theme_buttons if b._chosen]
    return on + (["Custom"] if w.theme_custom._chosen else [])


labels = [b.text() for b, _v, _m in w.theme_buttons] + [w.theme_custom.text()]
check("the row: Dark, Light, Same as macOS, Custom", labels ==
      ["Dark", "Light", "Same as macOS", "Custom"], labels)
check("the old 'Settings window' row is gone", not hasattr(w, "menu_theme"))
check("default: Same as macOS", m.MENU_THEME == "system" and lit() == ["Same as macOS"], lit())

w.theme_buttons[1][0].click()
check("Light: windows and pop-up light", m.MENU_THEME == "light" and m.POPUP_BG == LIGHT
      and lit() == ["Light"], (m.MENU_THEME, m.POPUP_BG, lit()))
check("... saved with the Windows keys", m._config.get("menu_theme") == "light"
      and m._config.get("popup_bg") == LIGHT)
w.theme_buttons[0][0].click()
check("Dark: windows and pop-up dark", m.MENU_THEME == "dark" and m.POPUP_BG == DARK
      and lit() == ["Dark"], (m.MENU_THEME, m.POPUP_BG, lit()))

mac["light"] = True
w.theme_buttons[2][0].click()
check("Same as macOS while macOS is Light: the pop-up is light",
      m.MENU_THEME == "system" and m.POPUP_BG == LIGHT and lit() == ["Same as macOS"],
      (m.MENU_THEME, m.POPUP_BG, lit()))
mac["light"] = False
m.restyle_windows()                       # as when macOS switches to Dark
check("macOS switches to Dark: the pop-up follows", m.POPUP_BG == DARK
      and lit() == ["Same as macOS"], (m.POPUP_BG, lit()))

m.POPUP_BG = "#203040"                    # a colour of your own (Custom)
w._background_chosen("#203040")
mac["light"] = True
m.restyle_windows()
check("a colour of your own stays when macOS switches", m.POPUP_BG == "#203040")
check("... and Custom is lit", lit() == ["Custom"], lit())

m.MENU_THEME, m.POPUP_BG = "light", DARK  # windows light, pop-up dark: they differ
w._paint_theme()
check("pop-up and windows differ: Custom is lit", lit() == ["Custom"], lit())
finish()
