"""Importing a settings line (as Windows 0.2.4, b12b32a): a line with only
defaults ("leetsay-settings-1:e30") says "Nothing to change: ..."; Windows
key names (ctrl+space, F-keys, "windows") are left out, counted and never
applied; usable settings from a Windows line still import."""
import os, sys, json, base64
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
from PySide6.QtWidgets import QApplication, QDialog, QPlainTextEdit, QLabel, QPushButton
from PySide6.QtCore import QTimer


def line(d):
    raw = json.dumps(d, separators=(",", ":")).encode()
    return "leetsay-settings-1:" + base64.urlsafe_b64encode(raw).decode().rstrip("=")


check("e30 reads as nothing, nothing dropped", m.read_settings_line("leetsay-settings-1:e30")
      == ({}, {}, 0, ""), m.read_settings_line("leetsay-settings-1:e30"))
for key in ("ctrl+space", "f9", "ctrl+windows", "alt+f4"):
    good, careful, dropped, why = m.read_settings_line(line({"hotkey": key}))
    check(f"Windows hotkey {key!r} left out and counted", not good and not careful and dropped == 1,
          (good, careful, dropped))
good, careful, dropped, why = m.read_settings_line(
    line({"hotkey": "ctrl+space", "accent": "#4DA3FF", "sounds": False}))
check("a Windows line keeps its usable settings", good.get("accent") == "#4DA3FF"
      and good.get("sounds") is False and "hotkey" not in good and dropped == 1, (good, dropped))

seen = {}


def press(text):
    def go():
        for w in QApplication.topLevelWidgets():
            if isinstance(w, QDialog) and w.isVisible():
                w.findChild(QPlainTextEdit).setPlainText(text)
                for b in w.findChildren(QPushButton):
                    if b.text() == "Import and restart":
                        b.click()
                pump(0.1)
                seen[text] = [l.text() for l in w.findChildren(QLabel) if l.isVisible()]
                w.reject()
    QTimer.singleShot(300, go)
    m.import_settings_window(None)


press("leetsay-settings-1:e30")
check("defaults-only line: \"Nothing to change\" message", any(
    t.startswith("Nothing to change: that line only has the default settings (leetsay exports "
                 "only settings that were changed).") for t in seen.get("leetsay-settings-1:e30", [])),
      seen.get("leetsay-settings-1:e30"))
only_windows = line({"hotkey": "ctrl+space"})
press(only_windows)
check("a line with only Windows keys keeps the usual message",
      any("holds no settings that can be used" in t for t in seen.get(only_windows, [])),
      seen.get(only_windows))
finish()
