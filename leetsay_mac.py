#!/usr/bin/env python3
"""leetsay for Mac: hold a key, speak, let go, and the words are typed where
the cursor is. Speech is recognised on this Mac; nothing goes online."""

import os
import sys

# Never import stray .py files that happen to sit next to this script. (In the
# packaged leetsay.app this folder is the app's own sealed contents: keep it.)
FROZEN = bool(getattr(sys, "frozen", False))
_HERE = os.path.dirname(os.path.abspath(__file__))
if not FROZEN:
    sys.path[:] = [p for p in sys.path if os.path.abspath(p or os.getcwd()) != _HERE]

VERSION = "0.2.3"
APP_TITLE = "leetsay"


# ---------------------------------------------------------------------------
# Network block: installed before anything else is imported. This test
# version never goes online at all (the model is already on the Mac).
# ---------------------------------------------------------------------------
import socket as _socket

# The network guard (as on Windows). Installed before anything else and never
# removed: Python reports every network action to it first, from whatever
# library it comes, and it refuses. Only after the user agreed, in a window
# that says "This application will go online", is it opened for this run, and
# then only towards github.com and GitHub's own file servers. It closes again
# as soon as the download is done.
_NET_MESSAGE = APP_TITLE + ": network access is blocked (offline)"
_NET_ALLOWED_HOSTS = frozenset(("github.com", "release-assets.githubusercontent.com",
                                "objects.githubusercontent.com",
                                "api.github.com"))   # the update check (only if asked)
_NET_EVENTS = frozenset(("socket.connect", "socket.getaddrinfo", "socket.gethostbyname",
                         "socket.gethostbyname_ex", "socket.gethostbyaddr",
                         "socket.getnameinfo", "socket.sendto", "socket.sendmsg",
                         "socket.bind"))
_NET_OTHER = frozenset(("ftplib.connect", "smtplib.connect", "poplib.connect",
                        "imaplib.open", "nntplib.connect", "telnetlib.Telnet.open"))
_NET_LIBS = ("cfnetwork", "libcurl", "network.framework", "nsurl")
_net = {"open": False, "why": "", "verified": None, "hosts": set(), "ips": set()}


class NetworkBlocked(ConnectionRefusedError):
    """Raised for any network action while the guard is closed."""


def _proxy_hosts():
    """Proxy servers set up on this Mac (an agreed download may go through them)."""
    from urllib.parse import urlsplit
    hosts, values = set(), []
    try:
        import urllib.request
        values = list(urllib.request.getproxies().values())
    except Exception:
        pass
    for name in ("HTTPS_PROXY", "HTTP_PROXY", "ALL_PROXY"):
        values += [os.environ.get(name), os.environ.get(name.lower())]
    for value in values:
        if value:
            try:
                host = urlsplit(value if "://" in value else "http://" + value).hostname
                if host:
                    hosts.add(host.lower())
            except Exception:
                pass
    return hosts


def _host_allowed(host):
    if isinstance(host, bytes):
        host = host.decode("ascii", "replace")
    host = str(host or "").lower().rstrip(".")
    return host in _NET_ALLOWED_HOSTS or host in _proxy_hosts()


def _address_of(sockaddr):
    try:
        return str(sockaddr[0]).split("%")[0].lower()
    except Exception:
        return ""


def _is_local_pipe(args):
    try:
        return args[0].family == _socket.AF_UNIX         # never leaves this Mac
    except Exception:
        return False


def _net_guard(event, args):
    if event in _NET_EVENTS:
        if event in ("socket.connect", "socket.bind", "socket.sendto", "socket.sendmsg") \
                and _is_local_pipe(args):
            return
        if not _net["open"]:
            raise NetworkBlocked(_NET_MESSAGE)
        if event == "socket.bind":
            raise NetworkBlocked(_NET_MESSAGE)        # never listens, even when open
        if event in ("socket.connect", "socket.sendto", "socket.sendmsg"):
            # Even while open: only to an address that a lookup of an allowed
            # name returned, so nothing can connect to a number directly.
            target = args[1] if len(args) > 1 else None
            if event == "socket.sendmsg":
                target = args[-1] if args else None
            if _address_of(target) not in _net["ips"]:
                raise NetworkBlocked(_NET_MESSAGE)
            return
        if event in ("socket.getaddrinfo", "socket.gethostbyname", "socket.gethostbyname_ex"):
            host = args[0] if args else None
            if not _host_allowed(host):
                raise NetworkBlocked(_NET_MESSAGE)
            _net["hosts"].add(str(host))
            return
        raise NetworkBlocked(_NET_MESSAGE)            # reverse lookups: never needed
    elif event in _NET_OTHER:
        raise NetworkBlocked(_NET_MESSAGE)            # mail, ftp...: never
    elif event == "http.client.connect":
        if not _net["open"] or not _host_allowed(args[1] if len(args) > 1 else ""):
            raise NetworkBlocked(_NET_MESSAGE)
    elif event == "urllib.Request" and not _net["open"]:
        raise NetworkBlocked(_NET_MESSAGE)
    elif event == "ctypes.dlopen" and not _net["open"] and args and args[0]:
        name = str(args[0]).lower()
        if any(n in name for n in _NET_LIBS):
            raise NetworkBlocked(_NET_MESSAGE)


sys.addaudithook(_net_guard)


def _remember_addresses():
    """Note the addresses that lookups of allowed names return (lookups of any
    other name are refused), so connections can be held to exactly those."""
    real_getaddrinfo = _socket.getaddrinfo

    def getaddrinfo(*args, **kwargs):
        found = real_getaddrinfo(*args, **kwargs)
        for entry in found:
            _net["ips"].add(_address_of(entry[4]))
        return found
    _socket.getaddrinfo = getaddrinfo


_remember_addresses()


def open_network(why):
    """Allow network access towards github.com for this run. Only ever called
    right after the user agreed to go online (or for a start a "go online"
    window in Settings covered)."""
    _net["why"] = why
    _net["open"] = True


def close_network():
    _net["open"] = False
    _net["ips"].clear()


def network_is_open():
    return _net["open"]


def verify_network_block():
    """Check, with nothing leaving this Mac, that the guard really refuses: a
    connection to this Mac itself and a name lookup must both be stopped by
    the guard (a refusal from macOS itself would not count)."""
    results = []
    for attempt in ("connect", "lookup"):
        try:
            if attempt == "connect":
                probe = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
                try:
                    probe.settimeout(0.2)
                    probe.connect(("127.0.0.1", 9))
                finally:
                    probe.close()
            else:
                _socket.getaddrinfo("localhost", 9)
            results.append(False)
        except NetworkBlocked:
            results.append(True)
        except Exception:
            results.append(False)
    _net["verified"] = all(results)
    return _net["verified"]

# No Hugging Face code may ever run: models come only from this project's own
# releases. onnx-asr would reach for this library only without a model folder;
# marking it as missing makes any such attempt fail at once.
sys.modules["huggingface_hub"] = None

import ctypes
import fcntl
import math
from collections import deque
import hashlib
import json
import logging
import re
import subprocess
import threading
import time
from ctypes import (CFUNCTYPE, POINTER, byref, c_bool, c_char_p, c_double,
                    c_int32, c_int64, c_long, c_ubyte, c_uint16, c_uint32,
                    c_uint64, c_ulong, c_void_p)

import numpy as np
import sounddevice as sd
from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtCore import (QEasingCurve, QObject, QPointF, QPropertyAnimation, QRectF,
                            Qt, QTimer, QUrl, Signal)
from PySide6.QtGui import (QAction, QActionGroup, QColor, QCursor,
                           QDesktopServices, QFont, QFontMetrics, QGuiApplication,
                           QIcon, QPainter, QPainterPath, QPen, QPixmap)
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon, QWidget

# ---------------------------------------------------------------------------
# Places and settings
# ---------------------------------------------------------------------------
HOME = os.path.expanduser("~")
SUPPORT_DIR = os.path.join(HOME, "Library", "Application Support", APP_TITLE)
LOG_DIR = os.path.join(HOME, "Library", "Logs", APP_TITLE)
SETTINGS_FILE = os.path.join(SUPPORT_DIR, "settings.json")
LOCK_FILE = os.path.join(SUPPORT_DIR, f"{APP_TITLE}.lock")

# Speech models that can be picked in Settings: (name, label, quantization, size).
MODELS = [
    ("nemo-parakeet-tdt-0.6b-v2", "English (Parakeet v2)", "int8", "about 660 MB"),
    ("nemo-parakeet-tdt-0.6b-v3", "25 European languages (Parakeet v3)", "int8", "about 670 MB"),
]
MODEL = "nemo-parakeet-tdt-0.6b-v2"          # the one in use (setting "model")
APP_REPO = "sudo-csmith/leetsay-mac"        # the Mac version's own repository
# Where the speech models come from: this project's own releases on github.com,
# converted in the open from NVIDIA's originals. Every file of every model,
# with its exact size and SHA-256: a file is used only if it matches, wherever
# it came from. The same values as the Windows version's (0.2.0).
MODELS_REPO = "sudo-csmith/leetsay-models"
MODELS_PAGE = "https://github.com/%s/releases" % MODELS_REPO
MODEL_RELEASES = {
    "nemo-parakeet-tdt-0.6b-v2": [{
        "tag": "parakeet-tdt-0.6b-v2-int8-r1",
        "files": {
            "config.json": (98, "21565538716b1cb134a096e3df9fa3f27f0470bc09c596d9faa578dc27d945d5"),
            "vocab.txt": (9384, "ec182b70dd42113aff6c5372c75cac58c952443eb22322f57bbd7f53977d497d"),
            "encoder-model.int8.onnx":
                (652282027, "e6698cc5b6ad84289b568b47e43b8e8d056d47dfdbb7de6f71d98eb073b1bcf1"),
            "decoder_joint-model.int8.onnx":
                (8998286, "a449f49acd68979d418651dd2dcb737cc0f1bf0225e009e29ee326354edbf7d3"),
        }}],
    "nemo-parakeet-tdt-0.6b-v3": [{
        "tag": "parakeet-tdt-0.6b-v3-int8-r1",
        "files": {
            "config.json": (98, "21565538716b1cb134a096e3df9fa3f27f0470bc09c596d9faa578dc27d945d5"),
            "vocab.txt": (93939, "d58544679ea4bc6ac563d1f545eb7d474bd6cfa467f0a6e2c1dc1c7d37e3c35d"),
            "encoder-model.int8.onnx":
                (652282012, "89e59ef6598d7edce584759b8648b5daaf518dc221e948c1d4db2270554cafcb"),
            "decoder_joint-model.int8.onnx":
                (18202004, "eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70"),
        }}],
}
# The small speech detector (Silero VAD, MIT), the makers' own unchanged file:
# stops the model "hearing" words in silence.
HELPER = "silero-vad"
HELPER_RELEASE = {
    "tag": "silero-vad-v6.2.3",
    "files": {
        "config.json": (31, "5d8aaa4970ba7f3b089d11ee1e7e8033363c52a16ce7afb2595f0c941a280996"),
        "silero_vad.onnx": (2327524, "1a153a22f4509e292a94e67d6f9b85e8deb25b4988682b7e174c65279d8788e3"),
    }}
MODEL_FILES = ["config.json", "vocab.txt",
               "encoder-model.int8.onnx", "decoder_joint-model.int8.onnx"]

SAMPLE_RATE = 16000
MIN_HOLD = 0.3          # shorter presses are treated as accidental
ACCENT = "#3DDC97"               # Mint, the same as the Windows version
POPUP_BG = "#16171B"

# Hold-to-talk keys: (macOS key code, device flag bit, name shown)
HOTKEYS = {
    "right_option": (61, 0x40, "Right Option (⌥)"),
    "right_command": (54, 0x10, "Right Command (⌘)"),
    "right_control": (62, 0x2000, "Right Control (⌃)"),
    "right_shift": (60, 0x04, "Right Shift (⇧)"),
}
_ALL_MOD_BITS = 0x01 | 0x02 | 0x04 | 0x08 | 0x10 | 0x20 | 0x40 | 0x2000

# ---------------------------------------------------------------------------
# Settings. The same names (keys) as the Windows version, so a settings line
# exported there can be imported here. Changes are saved straight away.
# ---------------------------------------------------------------------------
HOTKEY = "right_option"
ADD_SPACE = True                     # a space after each dictation
REMOVE_FILLERS = True                # leave out "um", "uh" and the like
TEXTBOX_ONLY = True                  # type only into a text box (asks macOS)
MAX_RECORD_SECONDS = 300             # a recording always stops after this long
MIC_DEVICE = ""                      # microphone by name; "" = the Mac's default
SCREEN_GLOW = True                   # also glow round the edge of the whole screen
SCREEN_GLOW_STRENGTH = 60            # how bright that glow is, 5-100
SCREEN_GLOW_SIZE = 56                # how far it reaches in from the edge, 20-200 pixels
SCREEN_GLOW_FLOW = True              # a light moves along it, and it ripples with your voice
SCREEN_GLOW_EDGES = "bottom"         # one side ("bottom", "top", "left", "right") or "all"
SCREEN_GLOW_FOCUS = "middle"         # one side's glow: "middle", "corners" or "even"
SCREEN_GLOW_SCREENS = "popup"        # on which screens: "popup" (the pop-up's), "all", "main"
TRAY_LIVE = False                    # the menu bar icon's bars move with your voice
POINTER_HINT = True                  # say "No text box" by the mouse pointer too
CHECK_APP_UPDATES = False            # ask github.com for a newer version at startup
                                     # (off unless switched on, after a warning)
SOUNDS = True                        # soft tone on start and on finish (as on Windows)
SOUND_SET = "soft"                   # soft, bright, click, low, or custom
SOUND_START_FILE = ""                # your own .wav files, used when the set is
SOUND_FINISH_FILE = ""               # "custom"
SOUND_VOLUME = 0.25                  # 0.0 - 1.0
SOUND_DEVICE = ""                    # where the sounds play; "" = the Mac's default output
# Word replacements: what the speech model writes -> what you want instead.
REPLACEMENTS = [["leet say", "leetsay"], ["leaked say", "leetsay"],
                ["lit say", "leetsay"], ["leet-say", "leetsay"]]
REPLACE_MAX, REPLACE_LEN = 50, 60
TECH_TERMS = [["kilobytes", "KB"], ["kilobyte", "KB"], ["megabytes", "MB"],
              ["megabyte", "MB"], ["gigabytes", "GB"], ["gigabyte", "GB"],
              ["terabytes", "TB"], ["terabyte", "TB"], ["kilohertz", "kHz"],
              ["megahertz", "MHz"], ["gigahertz", "GHz"],
              ["java script", "JavaScript"], ["type script", "TypeScript"],
              ["git hub", "GitHub"], ["c plus plus", "C++"], ["c sharp", "C#"],
              ["node js", "Node.js"], ["vs code", "VS Code"]]
TIME_LIMITS = [60, 120, 300, 600, 1800]

# The pop-up (the same names and defaults as the Windows version)
HOLD_TO_TALK = True                  # True: hold the key while speaking; False: a tap
                                     # starts, the next tap finishes (as on Windows)
SHOW_POPUP = True                    # show the pop-up while dictating
ALWAYS_SHOW = True                   # the small status pill between dictations
PILL_OVER_FULLSCREEN = False         # keep the pill over full-screen apps (games,
                                     # videos) too; off: it steps aside while one
                                     # covers its screen
SHOW_HOTKEY_HINT = True              # the hotkey on that pill
PILL_MARK = "logo"                   # "logo" (four bars), "dot" or "none"
PILL_MARKS = ("logo", "dot", "none")
SHOW_APP_ICON = True                 # the icon of the app you dictate into
SHOW_APP_NAME = False
SHOW_WAVEFORM = True
SHOW_TIMER = True
LIVE_PREVIEW = True                  # your words in the pop-up as you speak
LIVE_TYPE = False                    # type the words into the app at each pause, as you
                                     # speak (Windows: "Type as you speak")
RETURN_FOCUS = True                  # type into the app you started in, even if
                                     # another one took over while you spoke
AFTER_KEY = ""                       # a key pressed for you once the text is in
AFTER_DELAY = 0                      # seconds to wait before that key is pressed
ACTION_HOTKEY = ""                   # a second hotkey: dictate, then press ACTION_KEY
ACTION_KEY = "enter"
# The same setting values as Windows; Mac: "ctrl+enter" (Windows) is ⌘ Return here.
AFTER_CHOICES = [("", "do nothing"), ("enter", "press Return"),
                 ("cmd+enter", "press \u2318 Return"), ("tab", "press Tab")]
AFTER_DELAYS = [(0, "right away"), (1, "after 1 second"), (2, "after 2 seconds"),
                (3, "after 3 seconds"), (5, "after 5 seconds")]
AFTER_KEY_NAMES = {"enter": "Return", "cmd+enter": "\u2318 Return", "tab": "Tab"}
TYPE_TEXT = True                     # True: type the text, never touch the clipboard
CLIPBOARD_RESTORE_MS = 1000          # how long the paste gets before the restore
KEEP_LAST = False                    # "Missed text safety": a quick tap of the hotkey
KEEP_LAST_SECONDS = 300              # types the last dictation again; it is held in
                                     # memory this long. Off unless switched on.
PASTE_HOTKEY = ""                    # optional extra key for "missed text safety"
LIVE_LINES = 2
LIVE_ALIGN = "left"
WIDE_CARD = False
CARD_WIDTH = 0                       # dragged to your own width (0 = usual)
TEXT_SIZE = 12
TEXT_SIZES = [(11, "Small"), (12, "Medium"), (14, "Large"), (16, "Extra large")]
CARD_STYLE = "glow"
CARD_STYLES = [("glow", "Glow"), ("clean", "Clean"), ("accent", "Clean with a colour edge")]
GLOW = "medium"
GLOW_LEVELS = [("off", "Off", 0.0), ("subtle", "Subtle", 0.45), ("medium", "Medium", 0.75),
               ("strong", "Strong", 1.1)]
GLOW_FROM_APP = True                 # glow in the colour of the app's icon
GLOW_COLOUR = ""                     # your own glow colour ("" = the accent)
ACCENT_OUTLINE = True                # a ring in the accent colour round the pop-up
OUTLINE_LIGHT = True                 # a band of light travelling round that ring
ACCENT_CHOICES = [("Mint", "#3DDC97"), ("Sky", "#4DA3FF"), ("Violet", "#9B8CFF"),
                  ("Amber", "#FFB547"), ("Rose", "#FF6B8B"), ("White", "#F2F2F5")]
BACKGROUND_CHOICES = [("Dark", "#16171B"), ("Light", "#F8F8FA")]
LEET_MODE = False                    # 1337 mode (see apply_leet); set from the file below
MENU_THEME = "system"                # Settings and the other windows: "system" (as macOS),
                                     # "dark" or "light"
ICON_BARS = (1, 3, 3, 7)             # the icon's bar heights: 1337
N_DOTS = 46                          # how much level history the wave keeps
MIC_SILENT_PEAK = 0.0008             # below this the microphone is giving no signal
MIC_QUIET_PEAK = 0.01                # below this it can barely hear anything
BOTTOM_MARGIN = 36                   # gap between the pill and the Dock
EDGE_GAP = 8                         # the pop-up never comes closer to a screen edge
LIVE_EVERY_MS = 250                  # the live words refresh this often at most
LIVE_REST = 1.0 if (os.cpu_count() or 4) <= 8 else 0.25
LIVE_WINDOW_SECONDS = 4              # recent audio re-read for the live words, per line
                                     # (was 10: each pass took ~1.5 s, so the card
                                     # updated only every 2-3.5 s and fell behind)

_config = {}
_config_lock = threading.RLock()
_config_frozen = [False]             # set when restarting: the old copy saves nothing


def _load_config():
    try:
        with open(SETTINGS_FILE, encoding="utf-8-sig") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        raise ValueError("not a set of settings")
    except FileNotFoundError:
        return {}
    except Exception:
        # Damaged: keep it aside instead of quietly overwriting it.
        try:
            os.replace(SETTINGS_FILE, SETTINGS_FILE + ".damaged")
        except Exception:
            pass
        return {}


def write_config():
    """Saved to a temporary file first, then swapped in whole: a crash
    mid-save leaves the previous settings intact, never half a file."""
    if _config_frozen[0]:
        return
    temporary = SETTINGS_FILE + ".saving"
    with _config_lock:
        try:
            os.makedirs(SUPPORT_DIR, exist_ok=True)
            snapshot = json.loads(json.dumps(_config))
            with open(temporary, "w", encoding="utf-8") as fh:
                json.dump(snapshot, fh, indent=2)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temporary, SETTINGS_FILE)
        except Exception as exc:
            log.warning("could not save the settings: %s", exc)


def save_setting(key, value):
    with _config_lock:
        if value is None:
            _config.pop(key, None)
        else:
            _config[key] = value
        write_config()


def set_option(name, key, value):
    """Change one of the settings above and remember it."""
    globals()[name] = value
    save_setting(key, value)


def plain_text(part):
    """Ordinary text only: no control or invisible formatting characters
    (typed into an app, some of them act as keys)."""
    import unicodedata
    return all(unicodedata.category(c)[0] != "C" for c in part)


def valid_replacements(value):
    """A list of [heard, write] pairs of short, non-empty, one-line, plain texts."""
    return (isinstance(value, list) and len(value) <= REPLACE_MAX and all(
        isinstance(pair, list) and len(pair) == 2 and all(
            isinstance(part, str) and part.strip() and len(part) <= REPLACE_LEN
            and plain_text(part) for part in pair)
        for pair in value))


_COLOUR_RE = re.compile(r"#[0-9A-Fa-f]{6}")


def _is_colour(value, empty_ok=False):
    return isinstance(value, str) and (_COLOUR_RE.fullmatch(value) is not None
                                       or (empty_ok and value == ""))


def apply_config():
    """Read the saved choices into the settings above, each value checked."""
    global HOTKEY, MAX_RECORD_SECONDS, REPLACEMENTS
    _config.clear()
    _config.update(_load_config())
    if _config.get("hotkey") in HOTKEYS:
        HOTKEY = _config["hotkey"]
    globals()["HOLD_TO_TALK"] = (_config["hold_to_talk"]
                                 if isinstance(_config.get("hold_to_talk"), bool) else True)
    for name, key in (("AFTER_KEY", "after_key"), ("ACTION_KEY", "action_key")):
        value = _config.get(key)
        value = "cmd+enter" if value == "ctrl+enter" else value   # a Windows line
        if value in [k for k, _label in AFTER_CHOICES] and (value or name == "AFTER_KEY"):
            globals()[name] = value
    if _config.get("after_delay") in [seconds for seconds, _label in AFTER_DELAYS]:
        globals()["AFTER_DELAY"] = _config["after_delay"]
    value = _config.get("action_hotkey")
    globals()["ACTION_HOTKEY"] = value if (value in HOTKEYS and value != HOTKEY) else ""
    value = _config.get("paste_hotkey")
    globals()["PASTE_HOTKEY"] = (value if (value in HOTKEYS and value != HOTKEY
                                           and value != ACTION_HOTKEY) else "")
    for name, key in (("ADD_SPACE", "add_space"), ("REMOVE_FILLERS", "remove_fillers"),
                      ("TEXTBOX_ONLY", "textbox_only"), ("RETURN_FOCUS", "return_focus"),
                      ("TYPE_TEXT", "type_text"), ("KEEP_LAST", "keep_last")):
        if isinstance(_config.get(key), bool):
            globals()[name] = _config[key]
    value = _config.get("max_seconds")
    if isinstance(value, int) and not isinstance(value, bool):
        MAX_RECORD_SECONDS = max(30, min(3600, value))
    if isinstance(_config.get("mic"), str):
        globals()["MIC_DEVICE"] = _config["mic"]
    for name, key in (("SCREEN_GLOW", "screen_glow"), ("SCREEN_GLOW_FLOW", "screen_glow_flow"),
                      ("TRAY_LIVE", "tray_live"), ("POINTER_HINT", "pointer_hint")):
        if isinstance(_config.get(key), bool):
            globals()[name] = _config[key]
    for name, key, low, high in (("SCREEN_GLOW_STRENGTH", "screen_glow_strength", 5, 100),
                                 ("SCREEN_GLOW_SIZE", "screen_glow_size", 20, 200)):
        value = _config.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            globals()[name] = max(low, min(high, value))
    if _config.get("screen_glow_focus") in ("middle", "corners", "even"):
        globals()["SCREEN_GLOW_FOCUS"] = _config["screen_glow_focus"]
    if _config.get("screen_glow_screens") in ("popup", "all", "main"):
        globals()["SCREEN_GLOW_SCREENS"] = _config["screen_glow_screens"]
    if _config.get("screen_glow_edges") in ("bottom", "top", "left", "right", "all"):
        globals()["SCREEN_GLOW_EDGES"] = _config["screen_glow_edges"]
    if _config.get("menu_theme") in ("system", "dark", "light"):
        globals()["MENU_THEME"] = _config["menu_theme"]
    if isinstance(_config.get("check_app_updates"), bool):
        globals()["CHECK_APP_UPDATES"] = _config["check_app_updates"]
    if isinstance(_config.get("sounds"), bool):
        globals()["SOUNDS"] = _config["sounds"]
    if _config.get("sound_set") in ("soft", "bright", "click", "low", "custom"):
        globals()["SOUND_SET"] = _config["sound_set"]
    for name, key in (("SOUND_START_FILE", "sound_start"), ("SOUND_FINISH_FILE", "sound_finish"),
                      ("SOUND_DEVICE", "sound_device")):
        if isinstance(_config.get(key), str):
            globals()[name] = _config[key]
    value = _config.get("volume")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        globals()["SOUND_VOLUME"] = max(0.0, min(1.0, float(value)))
    if valid_replacements(_config.get("replacements")):
        REPLACEMENTS = _config["replacements"]
    if _config.get("model") in [entry[0] for entry in MODELS]:
        globals()["MODEL"] = _config["model"]
    for name, key in (("SHOW_POPUP", "show_popup"), ("ALWAYS_SHOW", "always_show"),
                      ("PILL_OVER_FULLSCREEN", "pill_over_fullscreen"),
                      ("SHOW_HOTKEY_HINT", "hotkey_hint"), ("SHOW_APP_ICON", "show_app_icon"),
                      ("SHOW_APP_NAME", "show_app_name"), ("SHOW_WAVEFORM", "show_waveform"),
                      ("SHOW_TIMER", "show_timer"), ("LIVE_PREVIEW", "live_preview"),
                      ("LIVE_TYPE", "live_type"),
                      ("WIDE_CARD", "wide_card"), ("GLOW_FROM_APP", "glow_from_app"),
                      ("ACCENT_OUTLINE", "accent_outline"), ("OUTLINE_LIGHT", "outline_light")):
        if isinstance(_config.get(key), bool):
            globals()[name] = _config[key]
    for name, key in (("ACCENT", "accent"), ("POPUP_BG", "popup_bg"),
                      ("GLOW_COLOUR", "glow_colour")):
        if _is_colour(_config.get(key), empty_ok=(key == "glow_colour")):
            globals()[name] = _config[key]
    if _config.get("pill_mark") in PILL_MARKS:
        globals()["PILL_MARK"] = _config["pill_mark"]
    if _config.get("card_style") in [k for k, _l in CARD_STYLES]:
        globals()["CARD_STYLE"] = _config["card_style"]
    if _config.get("glow") in [k for k, _l, _a in GLOW_LEVELS]:
        globals()["GLOW"] = _config["glow"]
    if _config.get("text_size") in [k for k, _l in TEXT_SIZES]:
        globals()["TEXT_SIZE"] = _config["text_size"]
    value = _config.get("live_lines")
    if isinstance(value, int) and not isinstance(value, bool):
        globals()["LIVE_LINES"] = max(1, min(6, value))
    value = _config.get("card_width")
    if isinstance(value, int) and not isinstance(value, bool):
        globals()["CARD_WIDTH"] = max(0, value)


apply_config()

# ---------------------------------------------------------------------------
# Cleaning up the model's text (the same rules as the Windows version)
# ---------------------------------------------------------------------------
FILLERS = {"um", "umm", "ummm", "uh", "uhh", "uhm", "erm"}
_SENTENCE_END = (".", "!", "?", "…")


def drop_fillers(words):
    """Leave out "um", "uh" and the like, tidying up around them:
    "Um, it seems" -> "It seems", "so, um, this" -> "so, this",
    "right now um." -> "right now.". Words such as "like" stay."""
    if not REMOVE_FILLERS:
        return list(words)
    out, capital = [], False
    for word in words:
        core = word.strip(".,!?;:…").lower()
        if core in FILLERS:
            marks = word[len(word.rstrip(".,!?;:…")):]
            starts = not out or out[-1].endswith(_SENTENCE_END)
            if starts and word[:1].isupper():
                capital = True                   # the next word starts the sentence
            if out and marks and marks[0] in "!?.…" \
                    and not out[-1].endswith(_SENTENCE_END):
                out[-1] = out[-1].rstrip(",;:") + marks[0]    # "now um." -> "now."
                capital = False
            continue
        if capital and word[:1].islower():
            word = word[0].upper() + word[1:]
        capital = False
        out.append(word)
    return out


def replace_words(words):
    """Your word replacements: a phrase the speech model wrote ("leaked say")
    becomes what you want ("leetsay"). Whole words, ignoring capitals and
    punctuation; the punctuation after the last matched word is kept."""
    rules = []
    for heard, write in REPLACEMENTS:
        key = [w for w in ("".join(c for c in part.lower() if c.isalnum() or c == "'")
                           for part in heard.split()) if w]
        if key:
            rules.append((key, write.split()))
    if not rules:
        return list(words)
    rules.sort(key=lambda rule: -len(rule[0]))  # longer phrases first
    plain = ["".join(c for c in w.lower() if c.isalnum() or c == "'") for w in words]
    out, i = [], 0
    while i < len(words):
        for key, write in rules:
            if plain[i:i + len(key)] == key and write:
                last = words[i + len(key) - 1]
                end = last[len(last.rstrip(".,!?;:…")):]
                write = list(write)
                first = words[i]
                if first[:1].isupper() and write[0][:1].islower():
                    write[0] = write[0][0].upper() + write[0][1:]   # a sentence's capital
                out.extend(write[:-1] + [write[-1] + end])
                i += len(key)
                break
        else:
            out.append(words[i])
            i += 1
    return out


_TIME_DOT = re.compile(r"^(\d{1,2})\.([0-5]\d)((?:[ap]\.?m\.?)?)([.,!?;:]*)$", re.IGNORECASE)
_AM_PM = re.compile(r"^[ap]\.?m\.?[.,!?;:]*$", re.IGNORECASE)


def fix_times(words):
    """"3.47 PM" -> "3:47 PM". Without AM or PM right after it, a number is
    left alone (it may be a price: "3.47 dollars")."""
    out = list(words)
    for i, word in enumerate(out):
        match = _TIME_DOT.match(word)
        if not match or not 1 <= int(match.group(1)) <= 12:
            continue
        if match.group(3) or (i + 1 < len(out) and _AM_PM.match(out[i + 1])):
            out[i] = "%s:%s%s%s" % match.groups()
    return out


def clean_words(words):
    """Filler words out, then times, then your word replacements."""
    return replace_words(fix_times(drop_fillers(words)))


def clean_text(text):
    return " ".join(clean_words(text.split()))


class _PrivateLog(logging.Filter):
    """Show the home folder as ~ so a shared log never shows the user name:
    in the message, its arguments (an error can carry a path) and any
    traceback, which is written out here so it can be cleaned too."""
    def filter(self, record):
        try:
            text = record.getMessage()
        except Exception:
            text = str(record.msg)
        if record.exc_info:
            import traceback
            text += "\n" + "".join(traceback.format_exception(*record.exc_info)).rstrip()
            record.exc_info = None
            record.exc_text = None
        record.msg = text.replace(HOME, "~")
        record.args = None
        return True


log = logging.getLogger(APP_TITLE)


def setup_log():
    os.makedirs(LOG_DIR, exist_ok=True)
    # Started afresh each time (as on Windows): only this session's lines are kept.
    h = logging.FileHandler(os.path.join(LOG_DIR, f"{APP_TITLE}.log"), mode="w",
                            encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    h.addFilter(_PrivateLog())
    log.addHandler(h)
    log.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# The speech model on this Mac: folders, checks, download (as on Windows)
# ---------------------------------------------------------------------------
def models_root():
    return os.path.join(SUPPORT_DIR, "models")


def model_dir(name=None):
    """~/Library/Application Support/leetsay/models/<model>."""
    return os.path.join(models_root(), name or MODEL)


def helper_dir():
    return os.path.join(models_root(), HELPER)


def local_model_dir(name=None):
    """The model's folder if all its files are there ('' if not). Whether they
    are the right files is checked separately, before anything is loaded."""
    folder = model_dir(name)
    if all(os.path.isfile(os.path.join(folder, item)) for item in MODEL_FILES):
        return folder
    return ""


def helper_on_disk():
    return all(os.path.isfile(os.path.join(helper_dir(), item))
               for item in HELPER_RELEASE["files"])


def current_release(name=None):
    releases = MODEL_RELEASES.get(name or MODEL) or [None]
    return releases[0]


def model_label(name=None):
    name = MODEL if name is None else name
    return dict((entry[0], entry[1]) for entry in MODELS).get(name, name)


def model_size_words(name=None):
    return dict((entry[0], entry[3]) for entry in MODELS).get(name or MODEL,
                                                            "several hundred MB")


def file_fingerprint(path):
    digest = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def check_files(folder, files, key):
    """The names in `folder` that are missing or don't match {name: (size,
    SHA-256)}. A file whose size and time are as recorded the last time it
    matched is not read again, so an ordinary start costs nothing; any change
    means it is read in full."""
    saved = _config.get("model_files")
    known = saved.get(key, {}) if isinstance(saved, dict) else {}
    bad, record = [], {}
    for name, (size, sha) in sorted(files.items()):
        path = os.path.join(folder, name)
        try:
            info = os.stat(path)
            if info.st_size != size:
                bad.append(name)
                continue
            old = known.get(name)
            same = (isinstance(old, list) and len(old) == 3 and old[0] == size
                    and abs(float(old[1]) - info.st_mtime) < 2.0 and old[2] == sha)
            if not same and file_fingerprint(path) != sha:
                bad.append(name)
                continue
            record[name] = [size, info.st_mtime, sha]
        except OSError:
            bad.append(name)
    if record != known:
        saved = dict(saved) if isinstance(saved, dict) else {}
        saved[key] = record
        save_setting("model_files", saved)
    return bad


def matching_release(name=None):
    """The trusted release that the model's files on this Mac exactly are, or None."""
    name = name or MODEL
    if not local_model_dir(name):
        return None
    for release in MODEL_RELEASES.get(name) or []:
        if not check_files(model_dir(name), release["files"], "%s|%s" % (name, release["tag"])):
            return release
    return None


def model_mismatches(name=None):
    name = name or MODEL
    release = current_release(name)
    if release is None:
        return list(MODEL_FILES)
    return check_files(model_dir(name), release["files"], "%s|%s" % (name, release["tag"]))


def helper_ok():
    return helper_on_disk() and not check_files(
        helper_dir(), HELPER_RELEASE["files"], "%s|%s" % (HELPER, HELPER_RELEASE["tag"]))


_ssl_context = None


def mac_ssl_context():
    """Checking github.com's certificate needs a list of trusted authorities.
    The Python inside the app has none of its own, so macOS's own list is
    used (read from the system keychain, nothing is changed)."""
    global _ssl_context
    if _ssl_context is None:
        import ssl
        pem = subprocess.run(
            ["/usr/bin/security", "find-certificate", "-a", "-p",
             "/System/Library/Keychains/SystemRootCertificates.keychain"],
            capture_output=True, timeout=30, check=True).stdout.decode("ascii", "replace")
        _ssl_context = ssl.create_default_context(cadata=pem)
    return _ssl_context


def _download_file(url, path, size, sha):
    """Fetch one file, carrying on from a part an earlier, interrupted try left
    behind. Kept only if it is exactly the right size and fingerprint;
    otherwise it is deleted and the attempt fails."""
    import urllib.request
    part = path + ".part"
    have = os.path.getsize(part) if os.path.isfile(part) else 0
    if have > size:
        os.remove(part)
        have = 0
    if have < size:
        request = urllib.request.Request(url, headers={"User-Agent": APP_TITLE})
        if have:
            request.add_header("Range", "bytes=%d-" % have)
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=mac_ssl_context()))
        with opener.open(request, timeout=30) as reply:
            if have and getattr(reply, "status", 200) != 206:
                have = 0                         # sent from the start again
            with open(part, "ab" if have else "wb") as out:
                while True:
                    block = reply.read(1024 * 1024)
                    if not block:
                        break
                    out.write(block)
    got = os.path.getsize(part)
    if got < size:
        raise ConnectionError("%s stopped at %d of %d bytes" % (os.path.basename(path), got, size))
    if got != size or file_fingerprint(part) != sha:
        os.remove(part)
        raise IOError("%s did not match its fingerprint, so it was deleted"
                      % os.path.basename(path))
    os.replace(part, path)


def download_release(release, folder):
    """Fetch every file of a release into a folder beside `folder`, check each
    one, and only then put the new folder in place of the old one. If it
    fails, what is in `folder` is untouched, and complete files are kept so
    the next try carries on from there."""
    import shutil
    staging = folder + ".download"
    os.makedirs(staging, exist_ok=True)
    for name, (size, sha) in sorted(release["files"].items(), key=lambda item: item[1][0]):
        target = os.path.join(staging, name)
        if os.path.isfile(target) and os.path.getsize(target) == size \
                and file_fingerprint(target) == sha:
            continue                             # arrived complete in an earlier try
        _download_file("https://github.com/%s/releases/download/%s/%s"
                       % (MODELS_REPO, release["tag"], name), target, size, sha)
    old = folder + ".old"
    shutil.rmtree(old, ignore_errors=True)
    if os.path.isdir(folder):
        os.replace(folder, old)
    os.replace(staging, folder)
    shutil.rmtree(old, ignore_errors=True)
    log.info("downloaded and checked %s (%d files)", release["tag"], len(release["files"]))


def _release_bytes(release):
    return sum(size for size, _sha in release["files"].values())


def model_total_bytes():
    """How much this download fetches: the model, plus the helper if missing."""
    release = current_release()
    total = _release_bytes(release) if release else 0
    if not helper_on_disk():
        total += _release_bytes(HELPER_RELEASE)
    return total


def folder_bytes(folder):
    total = 0
    for where, _dirs, files in os.walk(folder):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(where, name))
            except OSError:
                pass
    return total


def model_bytes_on_disk():
    """How much of this download has arrived so far (partly arrived files too)."""
    got = 0
    for folder, release in ((model_dir(), current_release()), (helper_dir(), HELPER_RELEASE)):
        if release is None:
            continue
        if os.path.isdir(folder + ".download"):
            got += folder_bytes(folder + ".download")
        elif folder == helper_dir() and helper_on_disk():
            got += _release_bytes(release)
        elif folder == model_dir() and local_model_dir():
            got += _release_bytes(release)
    return got


def size_words(count):
    """A byte count the way people say it: 104 KB, 12.4 MB, 660 MB."""
    if count < 1024 * 1024:
        return "%d KB" % (count // 1024)
    if count < 100 * 1024 * 1024:
        return "%.1f MB" % (count / (1024.0 * 1024.0))
    return "%d MB" % (count // (1024 * 1024))


def model_folders(name=None):
    base = model_dir(name)
    return [folder for folder in (base, base + ".download", base + ".old")
            if os.path.isdir(folder)]


def forget_model():
    """Delete this model from this Mac (only folders inside leetsay's own
    models folder), so the next start offers to download it afresh, after
    asking. The helper goes too unless another model still uses it."""
    import shutil
    freed = 0
    folders = model_folders()
    others = [entry[0] for entry in MODELS if entry[0] != MODEL and local_model_dir(entry[0])]
    if not others:
        folders += [f for f in (helper_dir(), helper_dir() + ".download") if os.path.isdir(f)]
    root = os.path.realpath(models_root()) + os.sep
    for folder in folders:
        if not os.path.realpath(folder).startswith(root):
            continue                             # never anything outside it
        freed += folder_bytes(folder)
        shutil.rmtree(folder, ignore_errors=True)
    saved = _config.get("model_files")
    if isinstance(saved, dict):
        save_setting("model_files", {k: v for k, v in saved.items()
                                     if not k.startswith(MODEL + "|")})
    log.info("model removed (%d MB)", freed // (1024 * 1024))
    return freed


# ---------------------------------------------------------------------------
# macOS system calls (through ctypes, so no extra packages are needed)
# ---------------------------------------------------------------------------
_objc = ctypes.CDLL("/usr/lib/libobjc.A.dylib")
_objc.objc_getClass.restype = c_void_p
_objc.objc_getClass.argtypes = [c_char_p]
_objc.sel_registerName.restype = c_void_p
_objc.sel_registerName.argtypes = [c_char_p]
_MSGSEND = ctypes.cast(_objc.objc_msgSend, c_void_p).value

_cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
_as = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
_carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
_avf = ctypes.CDLL("/System/Library/Frameworks/AVFoundation.framework/AVFoundation")


def _fn(lib, name, restype, *argtypes):
    f = getattr(lib, name)
    f.restype = restype
    f.argtypes = list(argtypes)
    return f


def objc(obj, selector, *args, restype=c_void_p, argtypes=()):
    proto = CFUNCTYPE(restype, c_void_p, c_void_p, *argtypes)
    return proto(_MSGSEND)(obj, _objc.sel_registerName(selector.encode()), *args)


def objc_class(name):
    return _objc.objc_getClass(name.encode())


TAP_CALLBACK = CFUNCTYPE(c_void_p, c_void_p, c_uint32, c_void_p, c_void_p)

CGEventTapCreate = _fn(_as, "CGEventTapCreate", c_void_p, c_uint32, c_uint32, c_uint32, c_uint64, TAP_CALLBACK, c_void_p)
CGEventTapEnable = _fn(_as, "CGEventTapEnable", None, c_void_p, c_bool)
CGEventGetIntegerValueField = _fn(_as, "CGEventGetIntegerValueField", c_int64, c_void_p, c_uint32)
CGEventSetIntegerValueField = _fn(_as, "CGEventSetIntegerValueField", None, c_void_p, c_uint32, c_int64)
CGEventGetFlags = _fn(_as, "CGEventGetFlags", c_uint64, c_void_p)
CGEventSetFlags = _fn(_as, "CGEventSetFlags", None, c_void_p, c_uint64)
CGEventSourceCreate = _fn(_as, "CGEventSourceCreate", c_void_p, c_int32)
CGEventSourceFlagsState = _fn(_as, "CGEventSourceFlagsState", c_uint64, c_int32)
CGEventCreateKeyboardEvent = _fn(_as, "CGEventCreateKeyboardEvent", c_void_p, c_void_p, c_uint16, c_bool)
CGEventKeyboardSetUnicodeString = _fn(_as, "CGEventKeyboardSetUnicodeString", None, c_void_p, c_ulong, POINTER(c_uint16))
CGEventPost = _fn(_as, "CGEventPost", None, c_uint32, c_void_p)
AXIsProcessTrusted = _fn(_as, "AXIsProcessTrusted", c_ubyte)
AXIsProcessTrustedWithOptions = _fn(_as, "AXIsProcessTrustedWithOptions", c_ubyte, c_void_p)
CFMachPortCreateRunLoopSource = _fn(_cf, "CFMachPortCreateRunLoopSource", c_void_p, c_void_p, c_void_p, c_long)
CFRunLoopGetMain = _fn(_cf, "CFRunLoopGetMain", c_void_p)
CFRunLoopAddSource = _fn(_cf, "CFRunLoopAddSource", None, c_void_p, c_void_p, c_void_p)
CFDictionaryCreate = _fn(_cf, "CFDictionaryCreate", c_void_p, c_void_p, POINTER(c_void_p), POINTER(c_void_p), c_long, c_void_p, c_void_p)
CFRelease = _fn(_cf, "CFRelease", None, c_void_p)
IsSecureEventInputEnabled = _fn(_carbon, "IsSecureEventInputEnabled", c_ubyte)

kCFRunLoopCommonModes = c_void_p.in_dll(_cf, "kCFRunLoopCommonModes")
kCFBooleanTrue = c_void_p.in_dll(_cf, "kCFBooleanTrue")
kAXTrustedCheckOptionPrompt = c_void_p.in_dll(_as, "kAXTrustedCheckOptionPrompt")
AVMediaTypeAudio = c_void_p.in_dll(_avf, "AVMediaTypeAudio")

EV_KEYDOWN, EV_KEYUP, EV_FLAGS = 10, 11, 12
EV_TAP_OFF_TIMEOUT, EV_TAP_OFF_USER = 0xFFFFFFFE, 0xFFFFFFFF
FIELD_KEYCODE, FIELD_USERDATA = 9, 42
OUR_MARK = 0x1337C0DE          # stamped on keys we type, so we ignore them

SETTINGS_PANES = {
    "accessibility": "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility",
    "microphone": "x-apple.systempreferences:com.apple.preference.security?Privacy_Microphone",
    "input": "x-apple.systempreferences:com.apple.preference.security?Privacy_ListenEvent",
}


def can_control_keyboard():
    return bool(AXIsProcessTrusted())


def ask_keyboard_permission():
    """Shows macOS's own Accessibility question (adds us to the list)."""
    keys = (c_void_p * 1)(kAXTrustedCheckOptionPrompt.value)
    vals = (c_void_p * 1)(kCFBooleanTrue.value)
    kcb = ctypes.addressof(ctypes.c_byte.in_dll(_cf, "kCFTypeDictionaryKeyCallBacks"))
    vcb = ctypes.addressof(ctypes.c_byte.in_dll(_cf, "kCFTypeDictionaryValueCallBacks"))
    d = CFDictionaryCreate(None, keys, vals, 1, kcb, vcb)
    try:
        return bool(AXIsProcessTrustedWithOptions(d))
    finally:
        CFRelease(d)


MIC_UNKNOWN, MIC_RESTRICTED, MIC_DENIED, MIC_OK = 0, 1, 2, 3


def mic_permission():
    return objc(objc_class("AVCaptureDevice"), "authorizationStatusForMediaType:",
                AVMediaTypeAudio.value, restype=c_long, argtypes=(c_void_p,))


# macOS's own "may this app use the microphone?" request takes a "block" (a
# small Objective-C callback). A global block built by hand: it captures
# nothing, so it needs no copying. The answer itself is read afterwards
# with mic_permission(); the callback only notes that macOS replied.
class _BlockDescriptor(ctypes.Structure):
    _fields_ = [("reserved", c_ulong), ("size", c_ulong)]


class _Block(ctypes.Structure):
    _fields_ = [("isa", c_void_p), ("flags", c_int32), ("reserved", c_int32),
                ("invoke", c_void_p), ("descriptor", POINTER(_BlockDescriptor))]


_MIC_REPLY = CFUNCTYPE(None, c_void_p, c_bool)
_mic_reply = {"answered": False}


def _on_mic_reply(_block, granted):
    _mic_reply["answered"] = True


_mic_reply_fn = _MIC_REPLY(_on_mic_reply)          # kept alive for as long as the app runs
_mic_block_desc = _BlockDescriptor(0, ctypes.sizeof(_Block))
_mic_block = None


def request_mic_permission():
    """Ask macOS to show its microphone question (only while undecided).
    Returns False if it could not be asked this way."""
    global _mic_block
    try:
        if _mic_block is None:
            libsystem = ctypes.CDLL("/usr/lib/libSystem.B.dylib")
            isa = ctypes.addressof(c_void_p.in_dll(libsystem, "_NSConcreteGlobalBlock"))
            _mic_block = _Block(isa, 1 << 28, 0,                 # 1 << 28: a global block
                                ctypes.cast(_mic_reply_fn, c_void_p).value,
                                ctypes.pointer(_mic_block_desc))
        objc(objc_class("AVCaptureDevice"), "requestAccessForMediaType:completionHandler:",
             AVMediaTypeAudio.value, ctypes.byref(_mic_block), restype=None,
             argtypes=(c_void_p, c_void_p))
        return True
    except Exception:
        log.exception("microphone request")
        return False


def open_settings_pane(which):
    QDesktopServices.openUrl(QUrl(SETTINGS_PANES[which]))


def hide_from_dock():
    app = objc(objc_class("NSApplication"), "sharedApplication")
    objc(app, "setActivationPolicy:", 1, restype=c_bool, argtypes=(c_long,))


def show_in_dock(on):
    """In the Dock (and in ⌘Tab) only while Settings or setup is open, so
    the window can be found again; otherwise just the menu bar."""
    if not _real_mac_window():
        return
    try:
        app = objc(objc_class("NSApplication"), "sharedApplication")
        objc(app, "setActivationPolicy:", 0 if on else 1, restype=c_bool,
             argtypes=(c_long,))
        if on:
            bring_to_front()
    except Exception:
        log.exception("dock icon")


def bring_to_front():
    app = objc(objc_class("NSApplication"), "sharedApplication")
    objc(app, "activateIgnoringOtherApps:", True, restype=None, argtypes=(c_bool,))


def _real_mac_window():
    """Only a real Mac window can be told these things (not an invisible test one)."""
    return QGuiApplication.platformName() == "cocoa"


def float_everywhere(widget):
    """Keep a window above other apps, on every Space and over full-screen apps."""
    if not _real_mac_window():
        return
    try:
        view = int(widget.winId())
        win = objc(view, "window")
        if not win:
            return
        objc(win, "setLevel:", 25, restype=None, argtypes=(c_long,))          # status level
        objc(win, "setCollectionBehavior:", 1 | 16 | 256, restype=None, argtypes=(c_ulong,))
        objc(win, "setHidesOnDeactivate:", False, restype=None, argtypes=(c_bool,))
    except Exception:
        log.exception("float_everywhere")


def set_click_through(widget, on):
    """Clicks go through the window to what is under it (or not)."""
    if not _real_mac_window():
        return
    try:
        win = objc(int(widget.winId()), "window")
        if win:
            objc(win, "setIgnoresMouseEvents:", bool(on), restype=None, argtypes=(c_bool,))
    except Exception:
        log.exception("set_click_through")


def started_by():
    """While testing from a terminal, macOS gives permissions to the terminal."""
    if ".app/Contents/MacOS/" in os.path.realpath(sys.argv[0]):
        return None
    bundle = os.environ.get("__CFBundleIdentifier", "")
    return {"com.apple.Terminal": "Terminal", "com.googlecode.iterm2": "iTerm"}.get(
        bundle, "Terminal")


# ---------------------------------------------------------------------------
# Hotkey: watches one modifier key held on its own
# ---------------------------------------------------------------------------
class HotkeyWatch:
    def __init__(self, on_press, on_release, on_cancel):
        self.on_press, self.on_release, self.on_cancel = on_press, on_release, on_cancel
        self.code, self.mask, _ = HOTKEYS[HOTKEY]
        self.action_code = self.action_mask = None   # the second hotkey (dictate + a key)
        self.via_action = False                      # this hold is the second hotkey
        self.paste_code = self.paste_mask = None     # "missed text safety" key
        self.on_paste = None
        self.paste_down = False
        self.held = False
        self.spoiled = False
        self.port = None
        self.listen_only = None
        self._cb = TAP_CALLBACK(self._callback)   # must stay alive

    def set_paste(self, key):
        self.paste_code, self.paste_mask = (HOTKEYS[key][:2] if key in HOTKEYS
                                            else (None, None))

    def set_action(self, key):
        self.action_code, self.action_mask = (HOTKEYS[key][:2] if key in HOTKEYS
                                              else (None, None))

    def set_key(self, key):
        self.code, self.mask, _ = HOTKEYS[key]
        if self.held:
            self.held = False
            QTimer.singleShot(0, self.on_cancel)

    def install(self):
        if self.port:
            return True
        mask = (1 << EV_KEYDOWN) | (1 << EV_FLAGS)
        # Listen-only first: it can never slow down the user's typing.
        for listen_only in (1, 0):
            port = CGEventTapCreate(1, 0, listen_only, mask, self._cb, None)
            if port:
                src = CFMachPortCreateRunLoopSource(None, port, 0)
                CFRunLoopAddSource(CFRunLoopGetMain(), src, kCFRunLoopCommonModes)
                CGEventTapEnable(port, True)
                self.port, self.listen_only = port, bool(listen_only)
                log.info("hotkey watch on (%s)", "listen-only" if listen_only else "active")
                return True
        return False

    def physically_down(self):
        mask = self.action_mask if (self.via_action and self.action_mask) else self.mask
        return bool(CGEventSourceFlagsState(0) & mask)

    def _callback(self, proxy, etype, event, user):
        try:
            if etype in (EV_TAP_OFF_TIMEOUT, EV_TAP_OFF_USER):
                if self.port:
                    CGEventTapEnable(self.port, True)
                return event
            if CGEventGetIntegerValueField(event, FIELD_USERDATA) == OUR_MARK:
                return event
            if etype == EV_FLAGS:
                flags = CGEventGetFlags(event)
                code = CGEventGetIntegerValueField(event, FIELD_KEYCODE)
                if self.paste_code is not None and KEEP_LAST and code == self.paste_code:
                    if flags & self.paste_mask:      # down, on its own
                        self.paste_down = not (flags & _ALL_MOD_BITS & ~self.paste_mask)
                    elif self.paste_down:            # let go: a tap of it
                        self.paste_down = False
                        if self.on_paste is not None:
                            QTimer.singleShot(0, self.on_paste)
                    return event
                if self.paste_down:
                    self.paste_down = False          # another modifier: a shortcut
                ours = code == self.code or (self.action_code is not None
                                             and code == self.action_code)
                if ours and (not self.held or (code == self.action_code) == self.via_action):
                    mask = self.mask if code == self.code else self.action_mask
                    down = bool(flags & mask)
                    if down and not self.held:
                        self.held = True
                        self.via_action = code != self.code
                        # Held together with another modifier: a shortcut, not us.
                        self.spoiled = bool(flags & _ALL_MOD_BITS & ~mask)
                        if not self.spoiled:
                            QTimer.singleShot(0, self.on_press)
                    elif not down and self.held:
                        self.held = False
                        if not self.spoiled:
                            QTimer.singleShot(0, self.on_release)
                elif self.held and not self.spoiled:
                    self._spoil()
            elif etype == EV_KEYDOWN and self.paste_down:
                self.paste_down = False              # with a letter: a shortcut
            elif etype == EV_KEYDOWN and self.held and not self.spoiled:
                # Another key pressed while holding: the user meant a shortcut
                # or a special character, so this is not a dictation.
                self._spoil()
        except Exception:
            log.exception("hotkey callback")
        return event

    def _spoil(self):
        self.spoiled = True
        QTimer.singleShot(0, self.on_cancel)


# ---------------------------------------------------------------------------
# Typing into the focused app (no clipboard)
# ---------------------------------------------------------------------------
def type_text(text):
    """Types text as key presses. Returns None if done, or a reason if not."""
    if not can_control_keyboard():
        return "no_permission"
    if IsSecureEventInputEnabled():
        return "secure"
    src = CGEventSourceCreate(-1)          # private state: ignores held keys
    units = text.encode("utf-16-le")
    codes = [int.from_bytes(units[i:i + 2], "little") for i in range(0, len(units), 2)]
    i = 0
    try:
        while i < len(codes):
            n = min(20, len(codes) - i)
            if 0xD800 <= codes[i + n - 1] <= 0xDBFF and n > 1:   # keep pairs together
                n -= 1
            chunk = (c_uint16 * n)(*codes[i:i + n])
            for down in (True, False):
                ev = CGEventCreateKeyboardEvent(src, 0, down)
                CGEventSetFlags(ev, 0)
                CGEventKeyboardSetUnicodeString(ev, n, chunk)
                CGEventSetIntegerValueField(ev, FIELD_USERDATA, OUR_MARK)
                CGEventPost(0, ev)
                CFRelease(ev)
            i += n
            time.sleep(0.004)
    finally:
        if src:
            CFRelease(src)
    return None


KEY_CODES = {"enter": 36, "tab": 48, "v": 9}
FLAG_COMMAND = 0x100000


def press_key(name):
    """Press Return, ⌘ Return or Tab for you (marked as ours, so the hotkey
    watch ignores it). Returns None if done, or a reason if not."""
    if not can_control_keyboard():
        return "no_permission"
    if IsSecureEventInputEnabled():
        return "secure"
    flags = FLAG_COMMAND if name.startswith("cmd+") else 0
    code = KEY_CODES[name.split("+")[-1]]
    src = CGEventSourceCreate(-1)
    try:
        for down in (True, False):
            ev = CGEventCreateKeyboardEvent(src, code, down)
            CGEventSetFlags(ev, flags)
            CGEventSetIntegerValueField(ev, FIELD_USERDATA, OUR_MARK)
            CGEventPost(0, ev)
            CFRelease(ev)
            time.sleep(0.01)
    finally:
        if src:
            CFRelease(src)
    return None


def copy_privately(text, pb=None):
    """Put text on the clipboard, marked "concealed" and "transient" (the
    nspasteboard.org markers), so clipboard managers that follow them don't
    keep it in their history."""
    pb = pb or objc(objc_class("NSPasteboard"), "generalPasteboard")
    objc(pb, "clearContents", restype=c_long)

    def ns(value):
        return objc(objc_class("NSString"), "stringWithUTF8String:", value.encode(),
                    argtypes=(c_char_p,))
    objc(pb, "setString:forType:", ns(text), ns("public.utf8-plain-text"),
         restype=c_bool, argtypes=(c_void_p, c_void_p))
    for marker in ("org.nspasteboard.ConcealedType", "org.nspasteboard.TransientType"):
        objc(pb, "setString:forType:", ns(""), ns(marker), restype=c_bool,
             argtypes=(c_void_p, c_void_p))


_CLIPBOARD_FAILED = object()          # the clipboard could not be read
_pending_restore = {}                 # a paste waiting to give the clipboard back


def snapshot_clipboard():
    """A copy of whatever is on the clipboard right now (None if empty,
    _CLIPBOARD_FAILED if it could not be read)."""
    try:
        source = QtGui.QGuiApplication.clipboard().mimeData()
        formats = list(source.formats()) if source is not None else []
        if not formats:
            return None
        copy = QtCore.QMimeData()
        for fmt in formats:
            copy.setData(fmt, source.data(fmt))
        if source.hasImage():
            copy.setImageData(source.imageData())
        if source.hasUrls():
            copy.setUrls(source.urls())
        if source.hasHtml():
            copy.setHtml(source.html())
        if source.hasText():
            copy.setText(source.text())
        return copy
    except Exception:
        return _CLIPBOARD_FAILED


def restore_clipboard(before, text):
    """Take the dictated text back off the clipboard."""
    _pending_restore.clear()
    try:
        clipboard = QtGui.QGuiApplication.clipboard()
        if clipboard.text() != text:
            return                         # you copied something else meanwhile
        if before is None:
            clipboard.clear()
        else:
            clipboard.setMimeData(before)
    except Exception:
        pass


def activate_app(pid):
    """Bring the app with this process number to the front ("Stay in the app
    I started in"). True if macOS took the request."""
    try:
        app = objc(objc_class("NSRunningApplication"),
                   "runningApplicationWithProcessIdentifier:", pid, argtypes=(ctypes.c_int,))
        if not app:
            return False
        return bool(objc(app, "activateWithOptions:", 2, restype=c_bool,
                         argtypes=(c_ulong,)))         # 2: ignoring other apps
    except Exception:
        log.exception("activate app")
        return False


# ---------------------------------------------------------------------------
# Is the cursor in a text box? Asks macOS's accessibility service (the one
# screen readers use) only what KIND of control has the focus: never its
# text, the page, or the app. Nothing is kept or written down.
# ---------------------------------------------------------------------------
AXUIElementCreateSystemWide = _fn(_as, "AXUIElementCreateSystemWide", c_void_p)
AXUIElementCopyAttributeValue = _fn(_as, "AXUIElementCopyAttributeValue", c_int32,
                                    c_void_p, c_void_p, POINTER(c_void_p))
AXUIElementSetMessagingTimeout = _fn(_as, "AXUIElementSetMessagingTimeout", c_int32,
                                     c_void_p, ctypes.c_float)
CFStringCreateWithCString = _fn(_cf, "CFStringCreateWithCString", c_void_p, c_void_p, c_char_p, c_uint32)
CFStringGetCString = _fn(_cf, "CFStringGetCString", c_bool, c_void_p, c_char_p, c_long, c_uint32)
CFGetTypeID = _fn(_cf, "CFGetTypeID", c_ulong, c_void_p)
CFStringGetTypeID = _fn(_cf, "CFStringGetTypeID", c_ulong)
_UTF8 = 0x08000100
_ax_names = {}
_ax_system = None

TEXT_ROLES = {"AXTextField", "AXTextArea", "AXComboBox", "AXSearchField"}
# Controls where typed letters would act as shortcuts, not text.
NOT_TEXT_ROLES = {"AXButton", "AXCheckBox", "AXRadioButton", "AXPopUpButton",
                  "AXMenuButton", "AXSlider", "AXImage", "AXLink", "AXList", "AXTable",
                  "AXOutline", "AXRow", "AXCell", "AXTabGroup", "AXDisclosureTriangle",
                  "AXIncrementor", "AXColorWell", "AXMenuItem", "AXWebArea", "AXBrowser",
                  "AXToolbar", "AXScrollBar", "AXValueIndicator", "AXSplitter"}


def _ax_name(text):
    if text not in _ax_names:
        _ax_names[text] = CFStringCreateWithCString(None, text.encode(), _UTF8)
    return _ax_names[text]


def _ax_copy(element, attribute):
    out = c_void_p()
    err = AXUIElementCopyAttributeValue(element, _ax_name(attribute), byref(out))
    return out.value if err == 0 else None


def _ax_string(element, attribute):
    value = _ax_copy(element, attribute)
    if not value:
        return ""
    try:
        if CFGetTypeID(value) != CFStringGetTypeID():
            return ""
        buf = ctypes.create_string_buffer(128)
        return buf.value.decode() if CFStringGetCString(value, buf, 128, _UTF8) else ""
    finally:
        CFRelease(value)


def focused_text_box():
    """"yes", "no", "password", or "unknown" (the app does not say: then
    typing goes ahead, so apps without accessibility support still work)."""
    global _ax_system
    try:
        if _ax_system is None:
            _ax_system = AXUIElementCreateSystemWide()
            AXUIElementSetMessagingTimeout(_ax_system, 0.25)   # never hang on a busy app
        focused = _ax_copy(_ax_system, "AXFocusedUIElement")
        if not focused:
            return "unknown"
        try:
            role = _ax_string(focused, "AXRole")
            subrole = _ax_string(focused, "AXSubrole")
            if "AXSecureTextField" in (role, subrole):
                return "password"
            if role in TEXT_ROLES:
                return "yes"
            if role in NOT_TEXT_ROLES:
                return "no"
            # Something else (a custom editor): a text cursor means text.
            caret = _ax_copy(focused, "AXSelectedTextRange")
            if caret:
                CFRelease(caret)
                return "yes"
            return "unknown"
        finally:
            CFRelease(focused)
    except Exception:
        log.exception("text box check")
        return "unknown"


# ---------------------------------------------------------------------------
# Start at login (only from the user's own choice; only in the real app)
# ---------------------------------------------------------------------------
try:
    ctypes.CDLL("/System/Library/Frameworks/ServiceManagement.framework/ServiceManagement")
except OSError:
    pass


def _login_service():
    if not FROZEN:
        return None
    cls = objc_class("SMAppService")
    return objc(cls, "mainAppService") if cls else None


def starts_at_login():
    svc = _login_service()
    if not svc:
        return False
    return objc(svc, "status", restype=c_long) in (1, 2)   # enabled, or awaiting approval


def set_start_at_login(on):
    svc = _login_service()
    if not svc:
        return False
    selector = "registerAndReturnError:" if on else "unregisterAndReturnError:"
    ok = objc(svc, selector, None, restype=c_bool, argtypes=(c_void_p,))
    log.info("start at login %s: %s", "on" if on else "off", "ok" if ok else "failed")
    return bool(ok)


# ---------------------------------------------------------------------------
# Microphone
# ---------------------------------------------------------------------------
def leveled(audio):
    """Quiet recordings are turned up before the model hears them, so a
    microphone set low still reads well. Loud ones, and silence, are left alone."""
    if len(audio) == 0:
        return audio
    peak = float(np.max(np.abs(audio)))
    if peak < MIC_SILENT_PEAK or peak >= 0.25:
        return audio
    return (audio * min(0.5 / peak, 25.0)).astype(np.float32)


def input_devices():
    """Names of the microphones macOS offers right now."""
    try:
        return [d["name"] for d in sd.query_devices() if d["max_input_channels"] > 0]
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Sounds (made here as tones, no audio files needed; copied from Windows)
# ---------------------------------------------------------------------------
SOUND_RATE = 44100
SOUND_SETS = [("soft", "Soft"), ("bright", "Bright"), ("click", "Click"),
              ("low", "Low"), ("custom", "My own files")]


def _tone(freq, seconds):
    """A pure tone that starts and ends at exactly zero (no click, no hiss)."""
    t = np.arange(int(SOUND_RATE * seconds)) / SOUND_RATE
    attack = 0.5 - 0.5 * np.cos(np.pi * np.clip(t / 0.012, 0.0, 1.0))
    release = 0.5 - 0.5 * np.cos(np.pi * np.clip((seconds - t) / 0.045, 0.0, 1.0))
    decay = np.exp(-t / (seconds * 0.42))
    return np.sin(2 * np.pi * freq * t) * attack * release * decay


def _mix(parts, seconds):
    lead, tail = 0.03, 0.10
    out = np.zeros(int(SOUND_RATE * (lead + seconds + tail)))
    for offset, tone in parts:
        i = int(SOUND_RATE * (lead + offset))
        out[i:i + len(tone)] += tone
    return out.astype(np.float32)


def _make_sounds(which):
    if which == "bright":       # higher, glassier pair
        start = _mix([(0.0, _tone(880.0, 0.10)), (0.07, _tone(1174.7, 0.16))], 0.23)
        finish = _mix([(0.0, _tone(1174.7, 0.10)), (0.07, _tone(880.0, 0.18))], 0.25)
    elif which == "click":      # short ticks: one to start, two to finish
        start = _mix([(0.0, _tone(1400.0, 0.05))], 0.05)
        finish = _mix([(0.0, _tone(1400.0, 0.05)), (0.09, _tone(1050.0, 0.05))], 0.14)
    elif which == "low":        # one deep note each
        start = _mix([(0.0, _tone(220.0, 0.22))], 0.22)
        finish = _mix([(0.0, _tone(164.8, 0.26))], 0.26)
    else:                       # soft: two rising notes, then one lower note
        start = _mix([(0.0, _tone(523.25, 0.12)), (0.08, _tone(659.25, 0.16))], 0.24)
        finish = _mix([(0.0, _tone(392.0, 0.24))], 0.24)
    return {"start": start, "finish": finish}


_SOUND_CACHE = {}
_WAV_CACHE = {}


def _read_wav(path):
    """A WAV file as (samples, rate); read once and reused until it changes."""
    import wave
    key = (path, os.path.getmtime(path))
    if key not in _WAV_CACHE:
        with wave.open(path, "rb") as fh:
            width, channels, rate = fh.getsampwidth(), fh.getnchannels(), fh.getframerate()
            raw = fh.readframes(fh.getnframes())
        if width == 2:
            data = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768.0
        elif width == 1:
            data = (np.frombuffer(raw, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        elif width == 4:
            data = np.frombuffer(raw, dtype="<i4").astype(np.float32) / 2147483648.0
        else:
            raise ValueError("unsupported WAV format")
        if len(_WAV_CACHE) > 6:
            _WAV_CACHE.clear()
        _WAV_CACHE[key] = (data.reshape(-1, channels), rate)
    return _WAV_CACHE[key]


def output_devices():
    """Names of the speakers and headphones the Mac offers (one entry each)."""
    names = []
    try:
        for device in sd.query_devices():
            if device.get("max_output_channels", 0) > 0 and device["name"] not in names:
                names.append(device["name"])
    except Exception:
        pass
    return names


def chosen_output():
    if not SOUND_DEVICE:
        return None
    try:
        for index, device in enumerate(sd.query_devices()):
            if device.get("name") == SOUND_DEVICE and device.get("max_output_channels", 0) > 0:
                return index
    except Exception:
        pass
    return None                                  # unplugged: the default


def play_sound(name, force=False):
    """'start' or 'finish': your own file if the set is "My own files", else
    the built-in tones. Never gets in the way of dictating."""
    if not SOUNDS and not force:
        return
    try:
        own = SOUND_START_FILE if name == "start" else SOUND_FINISH_FILE
        if SOUND_SET == "custom" and own and os.path.isfile(own):
            data, rate = _read_wav(own)
        else:
            which = SOUND_SET if SOUND_SET in ("soft", "bright", "click", "low") else "soft"
            if which not in _SOUND_CACHE:
                _SOUND_CACHE.clear()
                _SOUND_CACHE[which] = _make_sounds(which)
            data, rate = _SOUND_CACHE[which][name] * SOUND_VOLUME, SOUND_RATE
        sd.play(data, rate, device=chosen_output())
    except Exception:
        log.exception("sound")


def chosen_input():
    """The chosen microphone's number, or None for the Mac's default."""
    if not MIC_DEVICE:
        return None
    try:
        for i, d in enumerate(sd.query_devices()):
            if d["name"] == MIC_DEVICE and d["max_input_channels"] > 0:
                return i
    except Exception:
        pass
    return None                     # unplugged: the default one is used
def find_pause(audio, rate):
    """(Copied from Windows.) Where a piece of a dictation can be cut off and
    typed (typing as you speak): in the middle of the last short pause after
    some speech, as a sample index into audio, or None if there is no such
    pause yet. Talking on and on without a pause: after about 8 seconds it is
    cut at the quietest moment of the last few seconds instead."""
    frame = rate // 50                           # 20 ms
    count = len(audio) // frame
    if count < 30:
        return None
    loud = np.sqrt(np.mean(np.square(
        audio[:count * frame].astype(np.float32).reshape(count, frame)), axis=1))
    floor, top = float(np.percentile(loud, 3)), float(np.percentile(loud, 95))
    if top < 0.0002 or top < floor * 3.0:
        return None                              # nothing that stands out as speech
    quiet = loud < floor + 0.15 * (top - floor)
    gap = 22                                     # a pause of about 0.45 s
    speech, run, cut = 0, 0, None
    for i, still in enumerate(quiet):
        if still:
            run += 1
            if run == gap and speech >= 15:     # 0.3 s of speech before it
                cut = (i - gap + 1 + gap // 2) * frame
        else:
            run = 0
            speech += 1
    if cut is None and count > 8 * 50:           # no pause at all: cut anyway
        lo = count - 200
        smooth = np.convolve(loud, np.ones(10) / 10.0, mode="same")
        cut = (lo + int(np.argmin(smooth[lo:count - 10]))) * frame
    return cut


def holds_speech(audio, whole, rate):
    """(Copied from Windows.) Does this leftover bit of a recording hold any
    speech? Measured against the whole recording's speaking level, so that
    background noise left after the last pause is not read as an "uh"."""
    frame = rate // 50

    def loudness(a):
        n = len(a) // frame
        if n < 1:
            return np.zeros(1, dtype=np.float32)
        return np.sqrt(np.mean(np.square(a[:n * frame].astype(np.float32).reshape(n, frame)),
                               axis=1))
    every = loudness(whole)
    floor, top = float(np.percentile(every, 3)), float(np.percentile(every, 95))
    part = loudness(audio)
    return int(np.sum(part > floor + 0.25 * (top - floor))) >= 8     # 0.16 s of it


class Recorder:
    def __init__(self):
        self.stream = None
        self.chunks = []
        self.level = 0.0
        self.rate = SAMPLE_RATE
        self.started = 0.0
        self.peak = 0.0

    @property
    def is_open(self):
        return self.stream is not None

    def start(self):
        self.close()
        self.chunks = []
        self.level = 0.0
        self.peak = 0.0       # loudest sample in this recording (0 = dead silent)
        last_error = None
        device = chosen_input()
        for rate in (SAMPLE_RATE, None):
            try:
                if rate is None:
                    info = sd.query_devices(device if device is not None else sd.default.device[0])
                    rate = int(info["default_samplerate"])
                stream = sd.InputStream(samplerate=rate, channels=1, dtype="float32",
                                        device=device, blocksize=int(rate * 0.04),
                                        callback=self._audio)
            except Exception as e:
                last_error = e
                continue
            try:
                stream.start()
            except Exception as e:
                last_error = e
                try:
                    stream.close()
                except Exception:
                    pass
                continue
            self.stream, self.rate, self.started = stream, rate, time.monotonic()
            return
        raise RuntimeError(f"microphone did not start: {last_error}")

    def _audio(self, indata, frames, t, status):
        mono = indata[:, 0].copy()
        self.chunks.append(mono)
        rms = float(np.sqrt(np.mean(mono * mono))) if len(mono) else 0.0
        if len(mono):
            self.peak = max(self.peak, float(np.max(np.abs(mono))))
        loud = min(1.0, (rms * 10.0) ** 0.7)
        self.level = max(loud, self.level * 0.6)   # quick rise, soft fall (as on Windows)

    def recent(self, seconds):
        """The last few seconds recorded so far, without stopping."""
        chunks = list(self.chunks)
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks)[-int(seconds * self.rate):]

    def stop(self):
        self.close()
        audio = np.concatenate(self.chunks) if self.chunks else np.zeros(0, np.float32)
        self.chunks = []
        return audio, self.rate

    def close(self):
        s, self.stream = self.stream, None
        if s is not None:
            try:
                s.stop()
            except Exception:
                pass
            try:
                s.close()
            except Exception:
                pass
        self.level = 0.0


# ---------------------------------------------------------------------------
# Icon: four bars, heights 1, 3, 3, 7
# ---------------------------------------------------------------------------
def draw_bars(p, x, y, w, h, colour, levels=(1, 3, 3, 7)):
    n = len(levels)
    gap = w / (n * 3 - 1)
    bar = gap * 2
    p.setPen(Qt.NoPen)
    p.setBrush(colour)
    for i, lv in enumerate(levels):
        bh = max(bar, h * lv / 7)
        r = QRectF(x + i * (bar + gap), y + h - bh, bar, bh)
        p.drawRoundedRect(r, bar / 2, bar / 2)


def menu_bar_icon(dim=False, levels=None):
    # 18 x 18 points, bars filling nearly all of it (macOS adds its own spacing).
    # With `levels` (recent loudness, newest first) the bars grow and shrink
    # with your voice, keeping their 1337 shape (as the Windows tray icon).
    pm = QPixmap(36, 36)
    pm.fill(Qt.transparent)
    pm.setDevicePixelRatio(2)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    c = QColor(0, 0, 0, 120 if dim else 255)
    if levels:
        loud = max(0.0, min(1.0, max((list(levels) + [0.0])[:2])))
        h = 16 * (0.45 + 0.55 * loud)
        draw_bars(p, 1.5, 1 + 16 - h, 15, h, c)
    else:
        draw_bars(p, 1.5, 1, 15, 16, c)
    p.end()
    icon = QIcon(pm)
    icon.setIsMask(True)          # macOS colours it to match the menu bar
    return icon


def icon_pixmap(size, mac_grid=False):
    """The app icon: a dark tile with the four bars. `mac_grid` uses the
    margins macOS app icons use (a 824 tile on a 1024 canvas), for the Dock
    and Finder; without it the tile fills the picture (for dialogs)."""
    pm = QPixmap(size, size)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    p.setPen(Qt.NoPen)
    tile = size * (824 / 1024 if mac_grid else 0.88)
    m = (size - tile) / 2
    if mac_grid:                       # a soft shadow under the tile
        for i in range(6):
            p.setBrush(QColor(0, 0, 0, 10))
            grow = size * 0.004 * (i + 1)
            p.drawRoundedRect(QRectF(m - grow, m - grow + size * 0.012, tile + 2 * grow, tile + 2 * grow),
                              tile * 0.225 + grow, tile * 0.225 + grow)
    p.setBrush(QColor("#16171B"))
    p.drawRoundedRect(QRectF(m, m, tile, tile), tile * 0.225, tile * 0.225)
    s = tile * 0.56
    draw_bars(p, (size - s) / 2, (size - s) / 2, s, s, QColor(ACCENT))
    p.end()
    return pm


def app_icon():
    icon = QIcon()
    for size in (64, 128, 256):
        icon.addPixmap(icon_pixmap(size))
    return icon


# ---------------------------------------------------------------------------
# Mac versions of the small things the pop-up uses
# ---------------------------------------------------------------------------
# Spelled out on the pill: the key symbols alone were hard to read.
HOTKEY_SHORT = {"right_option": "Right Option", "right_command": "Right Command",
                "right_control": "Right Control", "right_shift": "Right Shift"}
HOTKEY_CHOICES = list(HOTKEYS)


def pretty(hotkey):
    """The hotkey as the pill shows it: "Right ⌥"."""
    return HOTKEY_SHORT.get(hotkey, hotkey)


def pill_text():
    """What the pill says between dictations: the hotkey ("Right Option").
    During setup it says "Setup" instead (see show_setup_notice)."""
    return pretty(HOTKEY)


def ui_font():
    """The pop-up's font: the Mac's own, or a typewriter font in 1337 mode."""
    if LEET_MODE:
        return QtGui.QFont("Menlo")
    return QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.GeneralFont)


# 1337 mode: a hidden look (click the title in About seven times). Green on
# black, a typewriter font, the logo on the pill. Looks only: the typed text is
# never changed. Your own colours are kept: the mode only covers them while on.
_LEET_LOOK = {"ACCENT": "#39FF6A", "POPUP_BG": "#050A06", "GLOW_COLOUR": "",
              "GLOW_FROM_APP": False, "CARD_STYLE": "glow"}
_LEET_SAVED = {}


def apply_leet(on):
    """Put the 1337 look on (or take it off again), in memory only."""
    global LEET_MODE
    LEET_MODE = bool(on)
    if on:
        for name, value in _LEET_LOOK.items():
            _LEET_SAVED.setdefault(name, globals()[name])
            globals()[name] = value
    else:
        keys = {"ACCENT": "accent", "POPUP_BG": "popup_bg", "GLOW_COLOUR": "glow_colour",
                "GLOW_FROM_APP": "glow_from_app", "CARD_STYLE": "card_style"}
        for name, value in _LEET_SAVED.items():
            # Changed in Settings while the mode was on? Then that, as saved.
            globals()[name] = _config.get(keys.get(name, ""), value)
        _LEET_SAVED.clear()


if _config.get("leet_mode") is True:
    apply_leet(True)


def light_menus():
    """Settings and the other windows in the light look (never in 1337 mode).
    "system" follows macOS's own Light or Dark appearance."""
    if LEET_MODE:
        return False
    if MENU_THEME == "system":
        try:
            hints = QtGui.QGuiApplication.styleHints()
            return hints.colorScheme() == Qt.ColorScheme.Light
        except Exception:
            return False
    return MENU_THEME == "light"


def glow_base():
    """The glow's colour when it isn't taken from the app's icon: your own
    choice if you made one, else the accent colour."""
    colour = QtGui.QColor(GLOW_COLOUR) if GLOW_COLOUR else QtGui.QColor(ACCENT)
    return colour if colour.isValid() else QtGui.QColor(ACCENT)


def glow_amount():
    return dict((key, amount) for key, _label, amount in GLOW_LEVELS).get(GLOW, 0.75)


_animations = {"checked": 0.0, "on": True}


def animations_on():
    """macOS's "Reduce motion" (System Settings › Accessibility › Display).
    On: the pop-up changes shape at once instead of animating."""
    now = time.monotonic()
    if now - _animations["checked"] > 5.0:
        _animations["checked"] = now
        try:
            ws = objc(objc_class("NSWorkspace"), "sharedWorkspace")
            _animations["on"] = not objc(ws, "accessibilityDisplayShouldReduceMotion",
                                         restype=c_bool)
        except Exception:
            _animations["on"] = True
    return _animations["on"]


def own_bundle_path():
    """This app's own folder (leetsay.app), or "" while testing."""
    if not FROZEN:
        return ""
    exe = os.path.realpath(sys.executable)
    return exe[:exe.index(".app/") + 4] if ".app/" in exe else ""


def _nsstring(value):
    if not value:
        return ""
    raw = objc(value, "UTF8String", restype=c_char_p)
    return raw.decode("utf-8", "replace") if raw else ""


class _NSRect(ctypes.Structure):
    _fields_ = [("x", c_double), ("y", c_double), ("w", c_double), ("h", c_double)]


_app_icons = {}


def mac_app_icon(path, side=128):
    """An app's own icon (as Finder shows it), from macOS. Kept for the
    session per app folder, so it is fetched once."""
    if path in _app_icons:
        return _app_icons[path]
    icon = QIcon()
    try:
        ws = objc(objc_class("NSWorkspace"), "sharedWorkspace")
        real = os.path.realpath(path)    # (a shortcut's icon would carry an arrow badge)
        cpath = objc(objc_class("NSString"), "stringWithUTF8String:", real.encode(),
                     argtypes=(c_char_p,))
        image = objc(ws, "iconForFile:", cpath, argtypes=(c_void_p,))
        rect = _NSRect(0, 0, side, side)
        cg = objc(image, "CGImageForProposedRect:context:hints:", byref(rect), None, None,
                  argtypes=(c_void_p, c_void_p, c_void_p)) if image else None
        if cg:
            rep = objc(objc(objc_class("NSBitmapImageRep"), "alloc"), "initWithCGImage:",
                       cg, argtypes=(c_void_p,))
            try:
                empty = objc(objc_class("NSDictionary"), "dictionary")
                data = objc(rep, "representationUsingType:properties:", 4, empty,
                            argtypes=(c_ulong, c_void_p))            # 4 = PNG
                if data:
                    size = objc(data, "length", restype=c_ulong)
                    raw = ctypes.string_at(objc(data, "bytes"), size)
                    pixmap = QPixmap()
                    if pixmap.loadFromData(raw, "PNG"):
                        icon = QIcon(pixmap)
            finally:
                objc(rep, "release", restype=None)
    except Exception:
        log.exception("app icon")
    _app_icons[path] = icon
    return icon


def front_app():
    """(name, folder) of the app in front, to show its icon on the card. Read
    only for that; never written down."""
    try:
        ws = objc(objc_class("NSWorkspace"), "sharedWorkspace")
        app = objc(ws, "frontmostApplication")
        if not app:
            return "", ""
        name = _nsstring(objc(app, "localizedName"))
        url = objc(app, "bundleURL")
        path = _nsstring(objc(url, "path")) if url else ""
        return name, path
    except Exception:
        return "", ""


def front_pid():
    """The process number of the app in front (0 if unknown): typing as you
    speak only types into the app the dictation started in. Never written down."""
    try:
        ws = objc(objc_class("NSWorkspace"), "sharedWorkspace")
        app = objc(ws, "frontmostApplication")
        return int(objc(app, "processIdentifier", restype=ctypes.c_int)) if app else 0
    except Exception:
        return 0


# The live preview's reading can be stopped part-way: each of the model's
# onnxruntime sessions is given, on the preview thread only, a RunOptions whose
# terminate flag is set when the key is let go. Other reads are untouched.
_PREVIEW = threading.local()


def _preview_stop_switch():
    import onnxruntime as ort
    _PREVIEW.stop = ort.RunOptions()
    return _PREVIEW.stop


def make_preview_stoppable(model, depth=0, seen=None):
    """Wraps every onnxruntime session inside the loaded model (found by
    walking its attributes), so a preview pass can be stopped."""
    import onnxruntime as ort
    seen = set() if seen is None else seen
    if model is None or id(model) in seen or depth > 5:
        return 0
    seen.add(id(model))
    if isinstance(model, ort.InferenceSession):
        if getattr(model, "_leetsay_wrapped", False):
            return 0
        original = model.run

        def run(output_names, input_feed, run_options=None, _original=original):
            stop = getattr(_PREVIEW, "stop", None)
            return _original(output_names, input_feed, stop if stop is not None else run_options)

        model.run = run
        model._leetsay_wrapped = True
        return 1
    found = 0
    values = (list(vars(model).values()) if hasattr(model, "__dict__")
              else list(model) if isinstance(model, (list, tuple)) else
              list(model.values()) if isinstance(model, dict) else [])
    for value in values:
        if isinstance(value, (str, bytes, int, float, np.ndarray)):
            continue
        found += make_preview_stoppable(value, depth + 1, seen)
    return found


SHORT_CHECK_SECONDS = 2.0    # under this, sound without speech is a click or a cough


def speech_decision(found, peak, seconds):
    """What to do with a finished recording (as Windows 0.2.4), from the voice
    detector's answer (found), the microphone's loudest moment (peak) and the
    length: "read" (transcribe it), "quiet" (the microphone barely heard
    anything: nothing typed, and the pop-up says so) or "noise" (a short sound
    without speech, a key click or a cough: nothing typed, and the pop-up says
    so). Sound without detected speech that lasts 2 s or more is read anyway:
    on a very quiet microphone the detector can miss real speech."""
    if found:
        return "read"
    if peak < MIC_QUIET_PEAK:
        return "quiet"
    if seconds < SHORT_CHECK_SECONDS:
        return "noise"
    return "read"


def how_words(key):
    """How to dictate, for the hotkey mode in use."""
    if HOLD_TO_TALK:
        return f"hold {key}, speak, let go"
    return f"press {key}, speak, press it again"


def mic_on_words(key):
    if HOLD_TO_TALK:
        return f"only while you hold {key}"
    return f"only between two presses of {key}"


class _CGRect(ctypes.Structure):
    _fields_ = [("x", ctypes.c_double), ("y", ctypes.c_double),
                ("w", ctypes.c_double), ("h", ctypes.c_double)]


CGWindowListCopyWindowInfo = _fn(_as, "CGWindowListCopyWindowInfo", c_void_p, c_uint32, c_uint32)
CGRectMakeWithDictionaryRepresentation = _fn(_as, "CGRectMakeWithDictionaryRepresentation",
                                             c_bool, c_void_p, POINTER(_CGRect))
CFArrayGetCount = _fn(_cf, "CFArrayGetCount", c_long, c_void_p)
CFArrayGetValueAtIndex = _fn(_cf, "CFArrayGetValueAtIndex", c_void_p, c_void_p, c_long)
CFDictionaryGetValue = _fn(_cf, "CFDictionaryGetValue", c_void_p, c_void_p, c_void_p)
CFNumberGetValue = _fn(_cf, "CFNumberGetValue", c_bool, c_void_p, c_long, c_void_p)


def _cf_int(d, key):
    value = CFDictionaryGetValue(d, _ax_name(key))
    out = ctypes.c_int64(-1)
    if value:
        CFNumberGetValue(value, 4, byref(out))           # kCFNumberSInt64Type
    return out.value


def fullscreen_app_in_front(widget):
    """Is the app in front a full-screen one (a game, a full-screen video or
    slide show, an app in its own full-screen Space) covering the whole screen
    this widget is on? Reads only the place and size of that app's windows,
    never their titles, contents or the app's name. Mac: an ordinary zoomed
    window leaves the menu bar showing, so it doesn't count."""
    try:
        pid = front_pid()
        if not pid or pid == os.getpid():
            return False                          # unknown, or one of our own windows
        screen = widget.screen() or QtGui.QGuiApplication.primaryScreen()
        g = screen.geometry()
        info = CGWindowListCopyWindowInfo(1 | 16, 0)   # on screen, no desktop pieces
        if not info:
            return False
        try:
            for i in range(CFArrayGetCount(info)):
                d = CFArrayGetValueAtIndex(info, i)
                if _cf_int(d, "kCGWindowOwnerPID") != pid or _cf_int(d, "kCGWindowLayer") != 0:
                    continue
                r = _CGRect()
                bounds = CFDictionaryGetValue(d, _ax_name("kCGWindowBounds"))
                if (bounds and CGRectMakeWithDictionaryRepresentation(bounds, byref(r))
                        and r.x <= g.x() and r.y <= g.y()
                        and r.x + r.w >= g.x() + g.width()
                        and r.y + r.h >= g.y() + g.height()):
                    return True
        finally:
            CFRelease(info)
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# The pop-up: carried over from the Windows version (leetsay.pyw 0.2.0) as it
# is, by a script, with only the Mac edits marked "Mac:". Keep it in step
# with the Windows pop-up rather than changing it here.
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# The glow round the edge of the screen and the "No text box" tag by the
# pointer: copied from Windows (leetsay.pyw) by a script, Mac edits marked.
# Mac: there is no see-through taskbar; the bottom glow sits just above the
# usable screen (above the Dock), so nothing is covered.
# ---------------------------------------------------------------------------
def taskbar_see_through():
    return False                                 # Mac: no taskbar to shine through


def tuck_behind_taskbar(_strip):
    pass                                         # Mac: never used (see above)


def mac_overlay_window(widget):
    """Mac: a glow or tag window floats above every app (full-screen ones
    too) and never catches a click."""
    if _real_mac_window():
        try:
            float_everywhere(widget)
            set_click_through(widget, True)
        except Exception:
            log.exception("overlay window")


class PointerBadge(QtWidgets.QWidget):
    """A small "No text box" tag that follows the mouse pointer while typing
    as you speak waits for a text box (your eyes are often where the pointer
    is, not on the pop-up). Clicks pass straight through it, it never takes
    the keyboard, and the real pointer is left alone."""

    OFFSET = QtCore.QPoint(16, 4)                # right beside the pointer's tip

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.text = "No text box"
        font = ui_font()
        font.setPixelSize(12)
        font.setWeight(QtGui.QFont.DemiBold)
        self.font_ = font
        width = QtGui.QFontMetricsF(font).horizontalAdvance(self.text)
        self.resize(int(width + 41), 24)          # room for the leetsay logo
        self.timer = QtCore.QTimer(self)
        # Follows the pointer about 100 times a second while it shows (30 a
        # second looked jerky beside the pointer itself).
        self.timer.setInterval(10)
        self.timer.timeout.connect(self._follow)

    def showEvent(self, event):              # Mac: above everything, clicks pass through
        super().showEvent(event)
        mac_overlay_window(self)

    def appear(self):
        self.target = 1.0
        if not self.isVisible():
            self._follow()
            self.setWindowOpacity(0.0)
            self.show()
        self.timer.start()

    def vanish(self):
        self.target = 0.0                        # fades out, then hides itself
        if self.isVisible():
            self.timer.start()

    def _follow(self):
        # Fade towards showing or gone (about a tenth of a second), not a pop.
        shown = self.windowOpacity()
        target = getattr(self, "target", 1.0)
        if abs(shown - target) > 0.01:
            step = 0.1 if animations_on() else 1.0     # still about a tenth of a second
            shown = min(target, shown + step) if target > shown else max(target, shown - step)
            self.setWindowOpacity(shown)
        if target == 0.0 and shown <= 0.01:
            self.timer.stop()
            self.hide()
            return
        spot = QtGui.QCursor.pos() + self.OFFSET
        screen = QtGui.QGuiApplication.screenAt(QtGui.QCursor.pos())
        if screen is not None:                   # never off the screen's edge
            room = screen.availableGeometry()
            spot.setX(min(spot.x(), room.right() - self.width()))
            spot.setY(min(spot.y(), room.bottom() - self.height()))
        if spot != self.pos():
            self.move(spot)

    def paintEvent(self, _event):
        theme = popup_theme()
        p = QtGui.QPainter(self)
        try:
            p.setRenderHint(QtGui.QPainter.Antialiasing)
            box = QtCore.QRectF(0.5, 0.5, self.width() - 1.0, self.height() - 1.0)
            fill = QtGui.QColor(theme["bg"])
            fill.setAlpha(240)
            p.setPen(QtGui.QPen(QtGui.QColor(theme["warning"]), 1.0))
            p.setBrush(fill)
            p.drawRoundedRect(box, box.height() / 2.0, box.height() / 2.0)
            # leetsay's logo (its four 1337 bars) in amber, so it is clear
            # where the note comes from.
            p.setPen(Qt.NoPen)
            p.setBrush(QtGui.QColor(theme["warning"]))
            bar, gap, tallest = 2.4, 1.6, 11.0
            unit = tallest / float(max(ICON_BARS))
            cy = box.center().y()
            for i, units in enumerate(ICON_BARS):
                h = max(2.4, unit * units)
                p.drawRoundedRect(QtCore.QRectF(10.0 + i * (bar + gap), cy - h / 2.0, bar, h),
                                  bar / 2.0, bar / 2.0)
            p.setFont(self.font_)
            p.setPen(theme["text"])
            p.drawText(QtCore.QRectF(29, 0, self.width() - 33, self.height()),
                       Qt.AlignLeft | Qt.AlignVCenter, self.text)
        finally:
            p.end()


class EdgeStrip(QtWidgets.QWidget):
    """One edge of the screen glow: a thin see-through window along a screen
    edge. Clicks pass straight through it, and it can never take the
    keyboard.

    The light is built like real light: a thin bright core at the very
    edge, a tight glow behind it and a wide soft haze, rounding off smoothly
    in the corners. Its brightness is a picture made once per size; the
    colour is laid over it, and with "flowing colours" it drifts slowly round
    the screen (the strip is then redrawn while you dictate, about 30 times a
    second; otherwise it is painted once and only its opacity changes)."""

    def __init__(self, side):
        super().__init__(None)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                            | Qt.WindowDoesNotAcceptFocus | Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.side = side
        self.colour = QtGui.QColor(ACCENT)
        self.phase = 0.0                     # where the moving light is on its way round
        self.voice = []                      # recent voice levels (the bottom edge's ripples)
        self.alone = False                   # the only strip: the bottom edge on its own
        self.behind = False                  # sits behind the taskbar, showing through it
        self.span = (0.0, 1.0)               # this strip's share of the way round
        self._mask = None                    # (key, picture of the brightness)

    def showEvent(self, event):              # Mac: above everything, clicks pass through
        super().showEvent(event)
        mac_overlay_window(self)

    @staticmethod
    def light(distance, depth):
        """How bright the glow is at `distance` pixels in from the edge
        (numbers, or a numpy array), for a glow `depth` pixels deep: a thin
        hot core, a tight glow and a wide haze, each fading smoothly."""
        x = np.maximum(distance, 0.0)
        core = np.exp(-x / 1.6)
        glow = 0.55 * np.exp(-(x / np.maximum(2.0, 0.14 * depth)) ** 2)
        haze = 0.34 * np.exp(-(x / np.maximum(4.0, 0.42 * depth)) ** 1.6)
        fade = np.clip(1.0 - x / depth, 0.0, 1.0) ** 0.6     # gone by the far side
        return np.minimum(1.0, (core + glow + haze) * fade)

    def _brightness(self, w, h, ratio):
        """The strip's brightness as a picture (white, see-through), made at
        the screen's real pixels, with a whisper of noise so the soft fade
        shows no bands."""
        key = (w, h, self.side, round(ratio, 2), self.alone, SCREEN_GLOW_FOCUS, self.behind)
        if self._mask is not None and self._mask[0] == key:
            return self._mask[1]
        pw, ph = max(1, int(round(w * ratio))), max(1, int(round(h * ratio)))
        depth = (h if self.side in ("top", "bottom") else w) * ratio
        xs = np.arange(pw, dtype=np.float32) + 0.5
        ys = np.arange(ph, dtype=np.float32) + 0.5
        gx, gy = np.meshgrid(xs, ys)
        if self.alone:
            # One side on its own (no corners to share): distance from its edge,
            # and how far along it a point is (0 at one end, 1 at the other).
            dist = {"left": gx, "right": pw - gx, "top": gy, "bottom": ph - gy}[self.side]
            along = gy / ph if self.side in ("left", "right") else gx / pw
        elif self.side in ("left", "right"):
            dist = gx if self.side == "left" else pw - gx
        else:
            dist = gy if self.side == "top" else ph - gy
            # The corners (the top and bottom strips own them): the distance
            # to the nearest edge, softened, so the light bends round in a
            # smooth curve instead of meeting the other edge in a crease.
            # (Further along, it is just the distance to this edge.)
            soft = max(1.0, 0.12 * depth)
            dist = -soft * np.log(np.exp(-dist / soft) + np.exp(-gx / soft)
                                  + np.exp(-(pw - gx) / soft))
            dist = np.maximum(dist, 0.0)
        if self.alone:
            # On its own it carries more light, gathered in its two corners:
            # there it reaches the full depth, in the middle (where people
            # read, and the pop-up sits) only a slim band, faint.
            side = np.abs(2.0 * along - 1.0)             # 0 in the middle, 1 at the ends
            # "corners": fullest at the two ends; "middle": rising highest in
            # the centre, like the system itself listening.
            gather = side if SCREEN_GLOW_FOCUS == "corners" else 1.0 - side
            if SCREEN_GLOW_FOCUS == "even":
                gather = np.ones_like(side)              # one even line, end to end
            reach = depth * (0.38 + 0.62 * gather ** 1.4)
            rise = 0.85 * np.exp(-(np.maximum(dist, 0.0) / (0.45 * reach)) ** 1.3)
            alpha = np.minimum(1.0, self.light(dist, reach) * 2.0 + rise)
            if self.behind:
                # Behind the taskbar its frosted layer dims the light: give it
                # more, filling more of the taskbar's height.
                alpha = np.minimum(1.0, alpha * 1.7 + 0.3 * np.exp(-dist / (0.8 * reach)))
            alpha = alpha * (0.15 + 0.85 * gather ** 1.3)
        else:
            alpha = self.light(dist, depth)
        alpha = alpha + (np.random.default_rng(7).random(alpha.shape, dtype=np.float32)
                         - 0.5) / 255.0
        a = np.clip(alpha * 255.0, 0, 255).astype(np.uint8)
        pixels = np.empty((ph, pw, 4), dtype=np.uint8)
        pixels[..., 0] = a
        pixels[..., 1] = a
        pixels[..., 2] = a
        pixels[..., 3] = a                   # premultiplied white
        image = QtGui.QImage(np.ascontiguousarray(pixels).tobytes(), pw, ph, 4 * pw,
                             QtGui.QImage.Format_ARGB32_Premultiplied).copy()
        image.setDevicePixelRatio(ratio)
        self._mask = (key, image)
        return image

    def _tint(self, position, along):
        """The colour (and strength) at a point on the way round the screen
        (0..1); `along` is how far along this strip (0..1). With "moving
        light": a brighter band in a neighbouring shade travels round the
        edge, and the bottom edge ripples out from its middle with your voice."""
        base = QtGui.QColor(self.colour)
        if not SCREEN_GLOW_FLOW:
            return base
        hue, sat, val, _a = base.getHsvF()
        hue = max(0.0, hue)
        gap = abs(position - self.phase) % 1.0
        gap = min(gap, 1.0 - gap)                # round the screen, either way
        light = math.exp(-(gap / 0.07) ** 2)     # the travelling band
        shifted = partner_colour(base)            # a shade that goes with it
        colour = QtGui.QColor(int(base.red() + (shifted.red() - base.red()) * light),
                              int(base.green() + (shifted.green() - base.green()) * light),
                              int(base.blue() + (shifted.blue() - base.blue()) * light))
        strength = (0.8 + 0.2 * light) if self.alone else (0.55 + 0.45 * light)
        if self.alone and self.voice:
            # Your voice, rippling out from the middle (or in from the
            # corners): the newest sound there, older sounds further along.
            out = abs(along - 0.5) * 2.0
            if SCREEN_GLOW_FOCUS == "corners":
                out = 1.0 - out
            spot = min(len(self.voice) - 1, int(out * len(self.voice)))
            strength += 0.6 * self.voice[-1 - spot]
        colour.setAlphaF(min(1.0, strength))
        return colour

    def paintEvent(self, _event):
        w, h = self.width(), self.height()
        ratio = self.devicePixelRatioF() or 1.0
        mask = self._brightness(w, h, ratio)
        layer = QtGui.QImage(mask)
        q = QtGui.QPainter(layer)
        q.setCompositionMode(QtGui.QPainter.CompositionMode_SourceIn)
        along = (QtCore.QPointF(0, 0), QtCore.QPointF(w, 0)) \
            if self.side in ("top", "bottom") else (QtCore.QPointF(0, 0), QtCore.QPointF(0, h))
        tint = QtGui.QLinearGradient(*along)
        first, last = self.span
        for i in range(41):
            colour = self._tint(first + (last - first) * i / 40.0, i / 40.0)
            if self.behind:
                # Behind the taskbar's frosted layer: a lighter, brighter shade
                # of the same colour gets through it far better than a deep one.
                lift = 0.45
                colour = QtGui.QColor(int(colour.red() + (255 - colour.red()) * lift),
                                      int(colour.green() + (255 - colour.green()) * lift),
                                      int(colour.blue() + (255 - colour.blue()) * lift),
                                      colour.alpha())
            tint.setColorAt(i / 40.0, colour)
        q.fillRect(QtCore.QRectF(0, 0, w, h), QtGui.QBrush(tint))
        # The hot core is lighter, nearly white, right at the edge: that is
        # what makes it read as light rather than paint.
        q.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
        if self.side == "top":
            start, stop = QtCore.QPointF(0, 0), QtCore.QPointF(0, 4)
        elif self.side == "bottom":
            start, stop = QtCore.QPointF(0, h), QtCore.QPointF(0, h - 4)
        elif self.side == "left":
            start, stop = QtCore.QPointF(0, 0), QtCore.QPointF(4, 0)
        else:
            start, stop = QtCore.QPointF(w, 0), QtCore.QPointF(w - 4, 0)
        hot = QtGui.QLinearGradient(start, stop)
        hot.setColorAt(0.0, QtGui.QColor(255, 255, 255, 105))
        hot.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
        q.fillRect(QtCore.QRectF(0, 0, w, h), QtGui.QBrush(hot))
        if self.side in ("top", "bottom") and not self.alone:
            # The corners belong to this strip: the side edges' hot line runs
            # on into them, right up to the corner.
            for x0, x1 in ((0.0, 4.0), (float(w), w - 4.0)):
                hot = QtGui.QLinearGradient(QtCore.QPointF(x0, 0), QtCore.QPointF(x1, 0))
                hot.setColorAt(0.0, QtGui.QColor(255, 255, 255, 105))
                hot.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
                q.fillRect(QtCore.QRectF(min(x0, x1), 0, 4.0, h), QtGui.QBrush(hot))
        q.end()
        p = QtGui.QPainter(self)
        p.setCompositionMode(QtGui.QPainter.CompositionMode_Source)
        p.drawImage(QtCore.QPointF(0, 0), layer)
        p.end()


class ScreenGlow:
    """A glow round the edge of the whole screen while you dictate (optional,
    off by default). It breathes in when dictation starts, swells with your
    voice and fades out at the end."""

    def __init__(self):
        self.sets = {}                           # a screen's rectangle -> its four strips
        self.strips = []                         # every strip in use now
        self.fade = 0.0
        self.showing = False

    def start(self, colour, areas):
        """Show round `areas` (one screen's rectangle, or a list of them: the
        glow can be on several screens at once) in `colour`."""
        if isinstance(areas, QtCore.QRect):
            areas = [areas]
        keys = []
        for area in areas:
            key = (area.x(), area.y(), area.width(), area.height())
            if key in keys:
                continue
            keys.append(key)
            if key not in self.sets:             # made the first time a screen is used
                self.sets[key] = [EdgeStrip(side) for side in
                                  ("top", "bottom", "left", "right", "bottom")]
            self._place(self.sets[key], colour, area)
        for key, strips in self.sets.items():    # screens not chosen this time
            if key not in keys:
                for strip in strips:
                    strip.hide()
        self.strips = [strip for key in keys for strip in self.sets[key]]
        if not self.showing:                     # already up (Settings demo): no restart
            self.fade = 0.0
        self.showing = True

    @staticmethod
    def _move(strip, rect):
        """Move or resize a strip without a jump: hidden for that moment and
        redrawn at its new size before it shows again. (Windows would show
        the old picture stretched to the new size for an instant, so a
        change of size made the glow leap up and settle back.)"""
        if strip.geometry() == rect:
            return
        if strip.isVisible():
            strip.setWindowOpacity(0.0)
            strip.setGeometry(rect)
            strip.repaint()                      # the new picture, before it shows
        else:
            strip.setGeometry(rect)

    def _shown(self, strip):
        """How strongly a strip shows: the glow along the bottom on its own
        shows stronger, so the low glow still reads clearly."""
        return min(1.0, self.fade * (2.6 if strip.behind else 1.8 if strip.alone else 1.0))

    def _place(self, strips, colour, area):
        """Put one screen's four strips in place for the chosen style."""
        x, y, w, h = area.x(), area.y(), area.width(), area.height()
        d = int(SCREEN_GLOW_SIZE)
        if SCREEN_GLOW_EDGES in ("bottom", "top", "left", "right"):
            # One side on its own, fullest in its two corners (it reaches
            # about 1.8 x the edge size there, a slim band in the middle);
            # "Edge size" in Settings makes it bigger. It starts from the edge
            # of the usable screen, so a taskbar on that side doesn't hide it.
            # Slim and soft on every side, like the glow under the taskbar's
            # icons (about 18 px; "Edge size" in More glow options makes it bigger).
            depth = max(12, int(SCREEN_GLOW_SIZE * 0.32))
            room = QtCore.QRect(area)
            screen = QtGui.QGuiApplication.screenAt(area.center())
            if screen is not None and area.contains(screen.availableGeometry()):
                room = screen.availableGeometry()
            rx, ry, rw, rh = room.x(), room.y(), room.width(), room.height()
            # The bottom glow lives in the taskbar. With a see-through taskbar
            # (Windows' default) on the main screen it sits behind it, filling
            # its height, and shines through behind the icons: nothing is
            # covered.
            taskbar = (y + h) - (ry + rh)
            main = QtGui.QGuiApplication.primaryScreen()
            on_main = main is not None and main.geometry() == area
            behind = taskbar > 0 and on_main and taskbar_see_through()
            if behind:
                bottom_rect = QtCore.QRect(rx, y + h - taskbar, rw, taskbar)
            else:
                # Another screen's taskbar, or a solid one: a slim glow just
                # above it, so its icons and their marks are never covered.
                bottom_rect = QtCore.QRect(rx, ry + rh - depth, rw, depth)
            place = {"top": QtCore.QRect(rx, ry, rw, depth),
                     "bottom": bottom_rect,
                     "left": QtCore.QRect(rx, ry, depth, rh),
                     "right": QtCore.QRect(rx + rw - depth, ry, depth, rh)}[SCREEN_GLOW_EDGES]
            one = strips[("top", "bottom", "left", "right").index(SCREEN_GLOW_EDGES)]
            for strip in strips[:4]:
                strip.alone = strip is one
                strip.behind = strip is one and SCREEN_GLOW_EDGES == "bottom" and behind
                if strip is not one:
                    strip.hide()
            one.span = (0.0, 1.0)
            one.colour = QtGui.QColor(colour)
            self._move(one, place)
            one.setWindowOpacity(self._shown(one) if self.showing else 0.0)
            one.show()
            strips[4].hide()                     # (a line in front: tried, looked worse)
            if one.behind:
                tuck_behind_taskbar(one)
            one.update()
            return
        d = max(12, int(SCREEN_GLOW_SIZE * 0.32))   # the full border: slim as well
        strips[4].hide()                         # the taskbar's line: not for the border
        for strip in strips[:4]:
            strip.alone = False
            strip.behind = False
            strip.setWindowOpacity(self.fade if self.showing else 0.0)
        places = ((x, y, w, d), (x, y + h - d, w, d),
                  (x, y + d, d, h - 2 * d), (x + w - d, y + d, d, h - 2 * d))
        # Each strip's share of the way round the screen, clockwise from the
        # top left, so the colours flow on from one edge into the next.
        round_trip = 2.0 * (w + h)
        spans = ((0.0, w / round_trip), ((2.0 * w + h) / round_trip, (w + h) / round_trip),
                 (1.0 - d / round_trip, (2.0 * w + h + d) / round_trip),
                 ((w + d) / round_trip, (w + h - d) / round_trip))
        for strip, place, span in zip(strips, places, spans):
            strip.span = span
            strip.colour = QtGui.QColor(colour)
            self._move(strip, QtCore.QRect(*place))
            strip.setWindowOpacity(self._shown(strip) if self.showing else 0.0)
            strip.show()
            strip.update()

    def step(self, level, active, still=False):
        """Advance one frame. Returns False once it has faded away. still:
        hold steady (no moving light, no ripples, no swelling with your
        voice), e.g. while nothing can be typed ("No text box selected")."""
        if not self.showing:
            return False
        if still:
            level = 0.0
        target = ((0.68 + 0.32 * max(0.0, min(1.0, level)))
                  * SCREEN_GLOW_STRENGTH / 100.0) if active else 0.0
        self.fade += (target - self.fade) * (0.16 if target > self.fade else 0.10)
        if not active and self.fade < 0.02:
            self.stop()
            return False
        moving = SCREEN_GLOW_FLOW and animations_on() and not still
        if moving:
            # The light travels round clockwise, once in about 6.5 s, quicker
            # while you speak. Your voice is kept for a moment, for the bottom
            # edge's ripples (none while you are quiet).
            voice = max(0.0, min(1.0, level)) if active else 0.0
            self.phase = (getattr(self, "phase", 0.0) + 0.005 * (1.0 + 1.5 * voice)) % 1.0
            self.voice = (getattr(self, "voice", []) + [voice])[-20:]
        for strip in self.strips:
            if not strip.isVisible():
                continue
            if strip.behind:
                tuck_behind_taskbar(strip)       # the taskbar stays in front of it
            strip.setWindowOpacity(self._shown(strip))
            if moving:
                strip.phase = self.phase
                strip.voice = self.voice if strip.alone else []
                strip.update()
            elif still and strip.voice:
                strip.voice = []                 # held still: no ripple left frozen
                strip.update()
        if still:
            self.voice = []
        return True

    def stop(self):
        self.showing = False
        self.fade = 0.0
        for strips in self.sets.values():
            for strip in strips:
                strip.hide()


_GLOW_CACHE = {}
_GLOW_BROKEN = False


def glow_pixmap(width, height, radius, colour, margin, blur, dpr):
    """A soft glow in the shape of the card, made by really blurring that shape
    (smooth at any size, no visible steps). Made once per size and colour, then
    reused; returns None if this PC can't make it."""
    global _GLOW_BROKEN
    if _GLOW_BROKEN:
        return None
    key = (int(round(width)), int(round(height)), int(round(radius)), colour.name(),
           int(margin), int(blur), round(dpr, 2))
    if key in _GLOW_CACHE:
        return _GLOW_CACHE[key]
    try:
        w = int(round((width + 2 * margin) * dpr))
        h = int(round((height + 2 * margin) * dpr))
        shape = QtGui.QPixmap(w, h)
        shape.fill(Qt.transparent)
        painter = QtGui.QPainter(shape)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.scale(dpr, dpr)
        painter.setPen(Qt.NoPen)
        painter.setBrush(colour)
        spill = 4.0                              # a little larger than the card itself
        painter.drawRoundedRect(QtCore.QRectF(margin - spill, margin - spill,
                                              width + 2 * spill, height + 2 * spill),
                                radius + spill, radius + spill)
        painter.end()

        scene = QtWidgets.QGraphicsScene()
        item = QtWidgets.QGraphicsPixmapItem(shape)
        effect = QtWidgets.QGraphicsBlurEffect()
        effect.setBlurRadius(blur * dpr)
        effect.setBlurHints(QtWidgets.QGraphicsBlurEffect.QualityHint)
        item.setGraphicsEffect(effect)
        scene.addItem(item)
        image = QtGui.QImage(w, h, QtGui.QImage.Format_ARGB32_Premultiplied)
        image.fill(Qt.transparent)
        painter = QtGui.QPainter(image)
        scene.render(painter, QtCore.QRectF(0, 0, w, h), QtCore.QRectF(0, 0, w, h))
        painter.end()
        result = QtGui.QPixmap.fromImage(image)
        while len(_GLOW_CACHE) > 16:             # forget the oldest, keep the rest
            _GLOW_CACHE.pop(next(iter(_GLOW_CACHE)))
        _GLOW_CACHE[key] = result
        return result
    except Exception as exc:
        print("Smooth glow unavailable, using the simple one:", exc, file=sys.stderr)
        _GLOW_BROKEN = True
        return None


def icon_colour(pixmap):
    """The main colour of an app's icon, brightened into something that glows
    well. None if the icon is basically grey, black or white."""
    try:
        image = pixmap.toImage().scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        buckets = {}
        for y in range(image.height()):
            for x in range(image.width()):
                c = image.pixelColor(x, y)
                if c.alpha() < 140:
                    continue
                saturation, value = c.hsvSaturationF(), c.valueF()
                if saturation * saturation * value < 0.08:
                    continue                     # greys, whites, blacks don't count
                # The brightest, purest parts of the icon count most, so a shaded
                # logo is judged by its lit side, not its shadows.
                weight = saturation * value ** 3
                bucket = int(c.hsvHueF() * 12) % 12
                total = buckets.setdefault(bucket, [0.0, 0.0, 0.0, 0.0])
                total[0] += weight
                total[1] += c.red() * weight
                total[2] += c.green() * weight
                total[3] += c.blue() * weight
        if not buckets:
            return None
        weight, red, green, blue = max(buckets.values(), key=lambda t: t[0])
        if weight < 4.0:
            return None                          # too little colour to go on
        colour = QtGui.QColor(int(red / weight), int(green / weight), int(blue / weight))
        # A glow is see-through light over a dark screen, which dulls it (orange
        # turns brownish). So it is made at full brightness, a little less heavy,
        # and lifted slightly towards white: it then reads as the icon's colour.
        # Mac: richer than Windows (an orange icon came out pale, almost
        # white): more colour, hardly lifted towards white.
        full = QtGui.QColor.fromHsvF(max(0.0, colour.hsvHueF()),
                                     min(0.95, max(0.80, colour.hsvSaturationF())), 1.0)
        lift = 0.04
        return QtGui.QColor(int(full.red() + (255 - full.red()) * lift),
                            int(full.green() + (255 - full.green()) * lift),
                            int(full.blue() + (255 - full.blue()) * lift))
    except Exception:
        return None


def partner_colour(colour):
    """A second shade that goes with a colour: its neighbour on the colour
    wheel, a little lighter (warm with warm, cool with cool, never a clash).
    Your voice brings it in, over the app's own colour."""
    base = QtGui.QColor(colour)
    hue, sat, _val, _a = base.getHsvF()
    # Mac: a closer neighbour, nearly as rich (the old one turned orange
    # into pale yellow, which washed the glow out).
    near = QtGui.QColor.fromHsvF((max(0.0, hue) + 0.05) % 1.0, min(1.0, sat * 0.95), 1.0)
    lift = 0.05
    return QtGui.QColor(int(near.red() + (255 - near.red()) * lift),
                        int(near.green() + (255 - near.green()) * lift),
                        int(near.blue() + (255 - near.blue()) * lift))


def accent_on_light(accent):
    """A deeper, richer version of the accent colour for pale backgrounds
    (the same hue, so it still reads as the colour that was picked)."""
    hue, saturation, lightness, _alpha = accent.getHslF()
    if saturation > 0.25:                        # leave greys and white neutral
        saturation = min(1.0, saturation * 1.1 + 0.08)
    return QtGui.QColor.fromHslF(max(0.0, hue), saturation, min(lightness, 0.37))


def is_light(colour):
    """True if a colour is light enough to need dark text on it."""
    c = QtGui.QColor(colour)

    def linear(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4

    luminance = (0.2126 * linear(c.red()) + 0.7152 * linear(c.green())
                 + 0.0722 * linear(c.blue()))
    return luminance > 0.179             # the point where dark text reads better


def popup_theme():
    """Every colour the pop-up uses, worked out from its background colour."""
    if LEET_MODE:                                # green on black, all of it
        return {"bg": QtGui.QColor(5, 10, 6, 250), "border": QtGui.QColor(57, 255, 106, 60),
                "shadow": QtGui.QColor(0, 0, 0, 10),
                "text": QtGui.QColor(110, 255, 150), "text2": QtGui.QColor(70, 230, 110),
                "muted": QtGui.QColor(40, 170, 80), "faint": QtGui.QColor(30, 120, 60),
                "quiet": QtGui.QColor(57, 255, 106, 60),
                "warning": QtGui.QColor(255, 200, 70), "danger": QtGui.QColor(255, 90, 90),
                "chip": QtGui.QColor(57, 255, 106, 18),
                "chip_hot": QtGui.QColor(57, 255, 106, 40),
                "chip_border": QtGui.QColor(57, 255, 106, 70),
                "sheen": QtGui.QColor(57, 255, 106, 16)}
    bg = QtGui.QColor(POPUP_BG)
    if not bg.isValid():
        bg = QtGui.QColor("#16171B")
    if is_light(bg):
        # Solid (a see-through pale card picks up whatever is behind it and
        # looks grubby), a hairline edge, a fuller shadow, and soft blacks.
        bg.setAlpha(255)
        return {"bg": bg, "border": QtGui.QColor(0, 0, 0, 24),
                "shadow": QtGui.QColor(0, 0, 0, 17),
                "text": QtGui.QColor(29, 29, 31), "text2": QtGui.QColor(60, 60, 67),
                "muted": QtGui.QColor(110, 110, 118), "faint": QtGui.QColor(142, 142, 150),
                "quiet": QtGui.QColor(0, 0, 0, 34), "warning": QtGui.QColor(181, 95, 0),
                "danger": QtGui.QColor(200, 40, 40),
                "chip": QtGui.QColor(0, 0, 0, 10), "chip_hot": QtGui.QColor(0, 0, 0, 24),
                "chip_border": QtGui.QColor(0, 0, 0, 40),
                "sheen": QtGui.QColor(255, 255, 255, 150)}
    bg.setAlpha(247)
    return {"bg": bg, "border": QtGui.QColor(255, 255, 255, 28),
            "shadow": QtGui.QColor(0, 0, 0, 10),
            "text": QtGui.QColor(240, 240, 244), "text2": QtGui.QColor(214, 216, 224),
            "muted": QtGui.QColor(170, 172, 182), "faint": QtGui.QColor(120, 122, 132),
            "quiet": QtGui.QColor(255, 255, 255, 60), "warning": QtGui.QColor(255, 181, 71),
            "danger": QtGui.QColor(255, 107, 107),
            "chip": QtGui.QColor(255, 255, 255, 14), "chip_hot": QtGui.QColor(255, 255, 255, 32),
            "chip_border": QtGui.QColor(255, 255, 255, 46),
            "sheen": QtGui.QColor(255, 255, 255, 16)}


def _plain(word):
    return "".join(ch for ch in word.lower() if ch.isalnum())


def overlap_start(shown, target):
    """Where in `shown` (words on the card) the model's new reading `target`
    begins. Usually 0. Once a long dictation outgrows what the preview re-reads,
    the reading starts later, and this finds where by lining the words up
    (ignoring capitals and punctuation, which the model keeps changing)."""
    if not shown or not target:
        return 0
    a, b = [_plain(w) for w in shown], [_plain(w) for w in target]
    best, best_hits = None, 0
    for start in range(len(a)):
        length = min(len(a) - start, len(b))
        hits = sum(1 for i in range(length) if a[start + i] == b[i])
        # On a tie the later start wins: a repeated phrase ("I said yes, I said
        # yes") lines up with its last repeat, not its first, so the words
        # already on the card are not cut off.
        if (hits > best_hits or (hits == best_hits and hits > 0)) and hits * 2 >= length:
            best, best_hits = start, hits
    if best is None:                             # nothing lines up: swap from the end
        return max(0, len(a) - len(b))
    return best


def wrap_words(text, measure, room):
    """Break text into lines no wider than `room` (measure gives a width)."""
    lines, current = [], ""
    for word in text.split():
        trial = word if not current else current + " " + word
        if current and measure(trial) > room:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]


class Overlay(QtWidgets.QWidget):
    cancel_clicked = QtCore.Signal()
    pill_clicked = QtCore.Signal()        # the small always-on pill was clicked
    settings_wanted = QtCore.Signal()     # ... or right-clicked
    retry_wanted = QtCore.Signal()        # the download card was right-clicked
    finish_clicked = QtCore.Signal()      # a recording started that way was clicked
    welcome_clicked = QtCore.Signal()
    notice_clicked = QtCore.Signal()
    hotkey_picked = QtCore.Signal(str)

    CARD_W, CARD_H = 164, 76       # compact by default; drag an edge to widen it
    WIDE_W = 300                   # card width when several lines of words are shown
    WELCOME_W, WELCOME_H = 256, 100
    WIN_W = 560                    # window width (and the widest the card can be
                                   # dragged); narrower cards are centred in it

    @property
    def LINE_H(self):
        """Height of one line of live words: follows the chosen text size."""
        return TEXT_SIZE + 5
    NOTE_W, NOTE_H = 120, 30       # every small pill: idle, notices, one-row dictation
    # The small pills (idle, notices): a dot or the leetsay logo in the accent
    # colour, then the hotkey or a short notice, flat and crisp: no shadow,
    # glow or shading. Sizes are at 100% scale; Qt multiplies them by the
    # screen's scaling factor.
    DOT_R = 4.5                    # the dot's radius
    LOGO_H, LOGO_MIN = 16.0, 3.0   # the logo's height; its shortest bar at least
    PILL_PAD_V, PILL_PAD_L, PILL_PAD_R = 6.0, 11.0, 13.0
    MARK_GAP, WORD_GAP = 8.0, 5.0  # mark to words; between a key and its "+"

    @staticmethod
    def _pill_font(weight):
        font = ui_font()
        font.setPixelSize(13)
        font.setWeight(weight)
        # Letters snapped to the pixel grid: the pill is see-through, where
        # Windows smooths text less, so this keeps them sharp.
        font.setHintingPreference(QtGui.QFont.PreferFullHinting)
        return font

    @classmethod
    def _key_font(cls):
        return cls._pill_font(QtGui.QFont.DemiBold)     # 600

    @classmethod
    def _plus_font(cls):
        return cls._pill_font(QtGui.QFont.Medium)       # 500

    @staticmethod
    def _pill_colours():
        """Fill, outline, key names, "+": the dark look, or the same contrast
        on the light theme."""
        if LEET_MODE:
            return (QtGui.QColor("#050A06"), QtGui.QColor("#1E7A3C"),
                    QtGui.QColor("#6EFF96"), QtGui.QColor("#2FB85C"))
        if is_light(POPUP_BG):
            # A faint see-through edge (a solid grey line showed its steps
            # round the curves); a soft shadow does the rest (see _draw_pill).
            return (QtGui.QColor("#FBFBFC"), QtGui.QColor(0, 0, 0, 34),
                    QtGui.QColor("#1B1D22"), QtGui.QColor("#737885"))
        return (QtGui.QColor("#1B1D22"), QtGui.QColor("#3A3E47"),
                QtGui.QColor("#EEF0F3"), QtGui.QColor("#8D929D"))

    @staticmethod
    def _hotkey_keys(note):
        """The keys to show when the pill is showing the hotkey, e.g.
        ["Ctrl", "Space"]; None for any other text."""
        if not note or note != pill_text():
            return None
        return [part for part in note.split("+") if part]

    @classmethod
    def _logo_metrics(cls):
        """Bar width, gap and height per unit of the logo: bars 8 units wide
        with 3-unit gaps, heights 1 : 3 : 3 : 7, the tallest filling LOGO_H."""
        unit = cls.LOGO_H / float(max(ICON_BARS))
        s = unit / 5.4                           # the app icon's own unit scale
        return 8.0 * s, 3.0 * s, unit

    def _mark(self):
        """The mark the pill shows now: "logo", "dot" or None. With the mark
        hidden, a dot still appears while something needs you (the status
        light: amber while loading, red for a problem)."""
        if LEET_MODE:
            return "logo"                        # 1337 mode: the four bars, in green
        if PILL_MARK == "none":
            return "dot" if self.status != "ok" else None
        return PILL_MARK

    def _mark_width(self):
        mark = self._mark()
        if mark == "logo":
            width, gap, _unit = self._logo_metrics()
            return len(ICON_BARS) * width + (len(ICON_BARS) - 1) * gap
        return 2.0 * self.DOT_R if mark == "dot" else 0.0

    def _draw_mark(self, p, left, cy, colour):
        """The dot, or the logo's four 1337 bars, centred on cy."""
        mark = self._mark()
        if mark is None:
            return
        p.setPen(Qt.NoPen)
        p.setBrush(colour)
        if mark == "dot":
            p.drawEllipse(QtCore.QPointF(left + self.DOT_R, cy), self.DOT_R, self.DOT_R)
            return
        width, gap, unit = self._logo_metrics()
        for i, units in enumerate(ICON_BARS):
            h = max(self.LOGO_MIN, unit * units)
            p.drawRoundedRect(QtCore.QRectF(left + i * (width + gap), cy - h / 2.0, width, h),
                              width / 2.0, width / 2.0)

    def _hotkey_words(self, keys):
        """[(word, is_plus, width)] for "Ctrl", "+", "Space"..., and the total width."""
        key_metrics = QtGui.QFontMetricsF(self._key_font())
        plus_metrics = QtGui.QFontMetricsF(self._plus_font())
        sized = []
        for i, key in enumerate(keys):
            if i:
                sized.append(("+", True, plus_metrics.horizontalAdvance("+")))
            sized.append((key, False, key_metrics.horizontalAdvance(key)))
        total = sum(w for _word, _plus, w in sized) + self.WORD_GAP * (len(sized) - 1)
        return sized, total

    def _pill_height(self):
        return float(self.NOTE_H)

    def _pill_width(self, keys, text=""):
        """Width of a small pill: the mark, then the hotkey or a notice."""
        if not keys and not text:
            # The mark alone: a round button for the dot, a pill that hugs the logo.
            if self._mark() != "logo":
                return self._pill_height()
            return float(round(self.PILL_PAD_L + self._mark_width() + self.PILL_PAD_L))
        if self._mark() is None:                 # no mark: the words, evenly padded
            width = 2 * self.PILL_PAD_R
        else:
            width = self.PILL_PAD_L + self._mark_width() + self.MARK_GAP + self.PILL_PAD_R
        if keys:
            width += self._hotkey_words(keys)[1]
        elif self._closable():
            width += QtGui.QFontMetricsF(self._key_font()).horizontalAdvance(text) + 2.0 \
                + self.CLOSE_ROOM
        else:
            # (+2: room for the outline and pixel rounding, so it is never cut short)
            width += QtGui.QFontMetricsF(self._key_font()).horizontalAdvance(text) + 2.0
        return float(round(min(380.0, width)))

    def _draw_pill(self, p, keys, card, accent, text=""):
        """A whole small pill, flat: its fill and a 1 px outline lined up with
        the screen's real pixels, the mark, then the hotkey's words or a short
        notice."""
        ratio = self.devicePixelRatioF() or 1.0
        snap = lambda value: round(value * ratio) / ratio
        # The outline is one or two whole screen pixels (1 px at 150% falls
        # between pixels and looks fuzzy), drawn as a filled ring so its curves
        # come out smooth.
        line = max(1, int(round(ratio))) / ratio
        outer_box = QtCore.QRectF(snap(card.left()), snap(card.top()),
                                  snap(card.width()), snap(card.height()))
        box = outer_box.adjusted(line / 2.0, line / 2.0, -line / 2.0, -line / 2.0)
        fill, outline, key_colour, plus_colour = self._pill_colours()
        outer = QtGui.QPainterPath()
        outer.addRoundedRect(outer_box, outer_box.height() / 2.0, outer_box.height() / 2.0)
        inner_box = outer_box.adjusted(line, line, -line, -line)
        inner = QtGui.QPainterPath()
        inner.addRoundedRect(inner_box, inner_box.height() / 2.0, inner_box.height() / 2.0)
        p.setPen(Qt.NoPen)
        if is_light(POPUP_BG):
            # On the light theme a soft shadow lifts the pill off the screen,
            # as light pop-ups do, instead of a strong outline.
            shade = glow_pixmap(outer_box.width(), outer_box.height(),
                                outer_box.height() / 2.0, QtGui.QColor(0, 0, 0), 10.0, 5.0,
                                ratio)
            if shade is not None:
                p.save()
                p.setOpacity(p.opacity() * 0.11)
                p.drawPixmap(outer_box.adjusted(-10, -7, 10, 13), shade,
                             QtCore.QRectF(shade.rect()))
                p.restore()
        # The whole shape filled first, the outline laid over it: drawn as two
        # pieces that only touch, a faint seam of the background showed
        # between them (worst on a light pill).
        p.fillPath(outer, QtGui.QBrush(fill))
        # Edge correction: a light shape on a dark screen (or the other way)
        # loses some strength in its softened edge pixels, so the curve looks
        # thin and stepped. A hair-thin line of the fill colour, half strength,
        # along the edge gives those pixels back their proper weight.
        firm = QtGui.QColor(fill)
        firm.setAlphaF(0.5)
        p.setPen(QtGui.QPen(firm, 0.6))
        p.setBrush(Qt.NoBrush)
        p.drawRoundedRect(outer_box.adjusted(0.3, 0.3, -0.3, -0.3),
                          outer_box.height() / 2.0 - 0.3, outer_box.height() / 2.0 - 0.3)
        p.setPen(Qt.NoPen)
        p.fillPath(outer.subtracted(inner), QtGui.QBrush(outline))
        cy = box.center().y()
        still = self.mode == "idle" or self.previewing
        pulse = 1.0 if still else 0.5 + 0.5 * math.sin(self.phase * 0.16)
        colour = QtGui.QColor(accent)
        colour.setAlphaF(colour.alphaF() * (0.55 + 0.45 * pulse))   # breathes when busy
        if not keys and not text:                # the mark alone, in the middle
            if self._mark() is None:             # nothing else to show: a quiet dot
                p.setPen(Qt.NoPen)
                p.setBrush(colour)
                p.drawEllipse(QtCore.QPointF(box.center().x(), cy), self.DOT_R, self.DOT_R)
                return
            self._draw_mark(p, snap(box.center().x() - self._mark_width() / 2.0), cy, colour)
            return
        if self._mark() is None:
            x = snap(card.left() + self.PILL_PAD_R)
        else:
            left = snap(card.left() + self.PILL_PAD_L)
            self._draw_mark(p, left, cy, colour)
            x = left + self._mark_width() + self.MARK_GAP
        # Centred on the capital letters, not on the whole line (which also
        # holds room for letters that hang below it, and so sat the words low):
        # the gap above "Ctrl" equals the gap below it. The line it sits on is
        # put on a whole pixel, so the letters stay sharp.
        baseline = snap(cy + QtGui.QFontMetricsF(self._key_font()).capHeight() / 2.0)
        if not keys:                             # a short notice
            metrics = QtGui.QFontMetricsF(self._key_font())
            room = box.right() - self.PILL_PAD_R - x
            p.setFont(self._key_font())
            # A missing microphone is said in red: nothing can work without it.
            p.setPen(popup_theme()["danger"] if text == self.NO_MIC else key_colour)
            if self._closable():
                room -= self.CLOSE_ROOM
                self._draw_close(p, box)
            p.drawText(QtCore.QPointF(snap(x), baseline),
                       metrics.elidedText(text, Qt.ElideRight, room))
            return
        words, _total = self._hotkey_words(keys)
        for word, plus, width in words:
            p.setFont(self._plus_font() if plus else self._key_font())
            p.setPen(plus_colour if plus else key_colour)
            p.drawText(QtCore.QPointF(snap(x), baseline), word)
            x += width + self.WORD_GAP
    GLOW = 36          # transparent room around the card for its glow and shadow
    CLOSE_ROOM = 24.0  # Mac: room for the × on a notice that stays

    def _closable(self):
        return self.mode == "message" and self.closable and self.message_stays

    def _draw_close(self, p, box):
        """Mac: the × at the right end of a notice that stays."""
        c = QtCore.QRectF(box.right() - self.PILL_PAD_R - 15.0, box.center().y() - 8.0,
                          16.0, 16.0)
        self._close_rect = c
        p.save()
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 30) if not is_light(POPUP_BG)
                   else QtGui.QColor(0, 0, 0, 22))
        p.drawEllipse(c)
        pen = QtGui.QPen(self._pill_colours()[3], 1.5)
        pen.setCapStyle(Qt.RoundCap)
        p.setPen(pen)
        k = 3.6
        m = c.center()
        p.drawLine(QtCore.QPointF(m.x() - k, m.y() - k), QtCore.QPointF(m.x() + k, m.y() + k))
        p.drawLine(QtCore.QPointF(m.x() + k, m.y() - k), QtCore.QPointF(m.x() - k, m.y() + k))
        p.restore()

    def __init__(self, recorder):
        super().__init__(None,
                         Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
                         | Qt.WindowDoesNotAcceptFocus)   # clickable, never takes focus
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.preview_words = None  # third-row text while previewing
        self.warning = ""          # microphone problem shown where the words go
        self.box_missing = False   # typing as you speak: no text box has the focus
        self.stepped_aside = False # the idle pill is hidden for a full-screen app
        self.status = "ok"         # the pill's light: "ok" (accent), "busy" (amber),
                                   # "problem" (red: no microphone, no model...)
        self._line_key = None      # what the card's words line shows, and since when
        self._line_t0 = 0.0
        self.picking = False       # welcome card is showing the hotkey choices
        self._hits = {}            # welcome card: name -> (x, y, w, h) click targets
        self._mouse = None         # last mouse position over the window
        self._card = None          # (x, y, w, h) of the card as last drawn
        self.ring = 0.0            # how far the outline is swollen by the voice
        self.app_colour = None     # main colour of the focused app's icon
        self.pulse_started = None  # when the one-off "hello" pulse began
        self.progress = None       # 0..1 while a download's progress shows on the pill
        self._own_icon = None      # this app's icon, for the download card
        self.message_stays = False # the notice showing has no time limit
        self.closable = False      # Mac: that notice has a × to close it
        self._close_rect = None
        self.rows = 1.0            # rows of words the card currently has room for
        self.half_step = False     # flips every tick: step-based things run on True
        self.click_started = False # this recording was started by clicking the pill
        self._resizing = None      # 'left' / 'right' while an edge is being dragged
        self._edge_hover = None    # the edge the mouse is resting on, if any
        self.hover_armed = True    # False until the mouse has left the card once
        self.spin = 0.0            # where the band of light is on the outline, degrees
        self.apply_size()
        self.welcome_ready = False # first-run card: model finished loading?
        self.live_text = ""        # words shown so far in this recording
        self.live_target = ""      # words heard so far (shown ones catch up to this)
        self.reveal_credit = 0.0
        self._clear_words()

        self.recorder = recorder
        self.mode = "message"            # "recording" | "transcribing" | "message"
        self.message = ""
        self.levels = deque([0.0] * N_DOTS, maxlen=N_DOTS)
        self.phase = 0.0
        self._message_id = 0
        self.fade = 0.0            # current opacity of the whole pop-up, 0..1
        self.fade_target = 0.0
        self.started = time.monotonic()
        self.previewing = False    # showing a demo, not a real recording
        self.app_name = ""         # focused app, shown while recording
        self.app_icon = None
        self.hover = False         # mouse is over the pop-up
        self._press = None         # where a mouse press started
        self._offset = None
        self._dragging = False
        self._pos = self._load_position()    # where the user dragged it, if anywhere
        self.setMouseTracking(True)

        self._morph = None             # a shape change under way (pill <-> card)
        self._shape_kind = None        # "small", "card" or "welcome": what was drawn
        self._last_frame = None        # the last picture, at full strength
        self._last_origin = QtCore.QPointF(0, 0)
        self._last_shape = None        # ... and its card's rectangle and corner radius
        self._last_fade = 0.0
        self._card_radius = 0.0
        self._clamp_shift = QtCore.QPointF(0, 0)   # how far the card was moved to fit
        self._card_screen = None       # the screen the card is on
        self._glow_margin = None       # the glow's size, kept steady while dragging
        self._slide = None             # the pill moving in from an edge for its pulse
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(16)               # about 60 frames a second
        self.timer.timeout.connect(self._tick)

    # -- public --------------------------------------------------------------
    def show_recording(self, app_name="", exe_path=""):
        self.mode = "recording"
        self.started = time.monotonic()
        self.app_name = app_name if SHOW_APP_NAME else ""
        self.app_icon = None
        self.app_colour = None
        if (SHOW_APP_ICON or GLOW_FROM_APP) and exe_path:
            try:
                if exe_path == own_bundle_path():
                    # Typing into our own window (the setup's try box): our
                    # icon, not Python's when it runs as a script.
                    icon = app_icon()
                else:
                    icon = mac_app_icon(exe_path)    # Mac: the app's real icon
                if not icon.isNull():
                    # Take the largest picture the app offers and shrink it once,
                    # with proper smoothing, to exactly the pixels it will cover.
                    # (Shrinking a big icon on every frame skips pixels and leaves
                    # rough edges, which show most against a dark card.)
                    picture = icon.pixmap(256, 256)
                    if SHOW_APP_ICON:
                        ratio = self.devicePixelRatioF()
                        side = max(1, int(round(20 * ratio)))
                        small = picture.scaled(side, side, Qt.KeepAspectRatio,
                                               Qt.SmoothTransformation)
                        small.setDevicePixelRatio(ratio)
                        self.app_icon = small
                    if GLOW_FROM_APP:
                        self.app_colour = icon_colour(picture)
            except Exception:
                self.app_icon = None
        self.levels = deque([0.0] * N_DOTS, maxlen=N_DOTS)
        self.live_text = ""
        self.live_target = ""
        self.reveal_credit = 0.0
        self._clear_words()
        self.warning = ""
        self.box_missing = False
        self.rows = 1.0
        self._present()

    NO_SOUND = "No sound from the microphone"
    CARD_EDGE_GAP = 24             # a dictation card's room from the screen's edges
    TASKBAR_GAP = 18               # ... and from the taskbar
    NO_BOX = "No text box selected"
    NO_MIC = "Microphone not detected  \u00b7  click for help"

    def _mic_warning(self):
        """Say so if the microphone is giving nothing a couple of seconds in."""
        elapsed = time.monotonic() - self.started
        peak = getattr(self.recorder, "peak", 1.0)
        if elapsed > 1.5 and peak < MIC_SILENT_PEAK:
            return self.NO_SOUND
        if elapsed > 5.0 and peak < MIC_QUIET_PEAK and not self.live_text:
            return "Can't hear you. Check the mic"
        if self.box_missing:
            # (Mac: a string is said as it is, e.g. a password field.)
            return self.box_missing if isinstance(self.box_missing, str) else self.NO_BOX
        return ""

    # -- size ------------------------------------------------------------------
    @property
    def live_h(self):
        """Height set aside for the live words (grows with the line count)."""
        return 8 + self.LINE_H * LIVE_LINES

    def _below(self):
        """Room below the pill's bottom line. A card opens centred on the pill,
        but a pill dragged to the top of the screen has its card open
        downwards instead, so there is room for the whole card below it."""
        return int(self.CARD_H + self.live_h - self.NOTE_H) + 4

    def apply_size(self):
        """Size the window for the current settings, keeping its base in place."""
        anchor = self._anchor() if self.isVisible() else None
        # Twice the widest card: a pill pushed against a screen edge opens its
        # card beside it, shifted inwards, and that card must still fit in the
        # (see-through) window.
        self.resize(2 * (self.WIN_W + self.GLOW),
                    max(self.CARD_H + self.live_h, self.WELCOME_H) + 2 * self.GLOW
                    + self._below())
        if anchor is not None:
            self.move(self._top_left(anchor))
        self.update()

    def _anchor(self):
        """The pill's bottom-centre point: stays put when the size changes."""
        return QtCore.QPoint(self.pos().x() + self.width() // 2,
                             self.pos().y() + self.height() - self.GLOW - self._below())

    def _top_left(self, anchor):
        return QtCore.QPoint(anchor.x() - self.width() // 2,
                             anchor.y() - self.height() + self.GLOW + self._below())

    def show_idle(self):
        """The small always-there pill between dictations."""
        self.mode = "idle"
        self.previewing = False
        self._present()

    def _note_text(self):
        """Text of the small pill, or None when the full card is showing."""
        if self.mode == "message":
            return self.message.replace("\n", " ")
        if self.mode == "idle":
            # Without the hotkey text the pill is just its dot: a small round
            # button, as quiet as it can be.
            return pill_text() if SHOW_HOTKEY_HINT else ""
        return None

    def show_welcome(self, ready):
        """First launch: stays on screen until it is clicked."""
        self.mode = "welcome"
        self.welcome_ready = bool(ready)
        self.previewing = False
        self._present()

    def _target_at(self, point):
        """Which welcome-card target (button, hotkey, a choice) is at this spot."""
        if self.mode != "welcome" or point is None:
            return None
        px, py = point
        for name, (x, y, w, h) in self._hits.items():
            if x <= px <= x + w and y <= py <= y + h:
                return name
        return None

    def _clear_words(self):
        self.live_lines = []       # rows of words, as laid out on the card
        self.line_w = []           # each row's drawn width (glides to its real width)
        self.pending = []          # words heard but not on the card yet
        self.row_slide = 0.0          # rows sliding up after a new row started
        self.word_fade = 1.0       # the newest word fades in
        self.second_look = {}      # word number -> a change the model suggested once

    def _measure(self):
        font = ui_font()
        font.setPixelSize(TEXT_SIZE)
        return QtGui.QFontMetricsF(font).horizontalAdvance

    def _fit_width(self, base):
        """The card's width once the app's name is on it: wide enough to show
        the name in full with a decent length of wave beside it."""
        if not self.app_name:
            return base
        font = ui_font()
        font.setPixelSize(12)
        font.setWeight(QtGui.QFont.DemiBold)
        name_w = QtGui.QFontMetricsF(font).horizontalAdvance(self.app_name)
        icon_w = 20.0 if self.app_icon is not None else 10.0
        need = (28.0 + icon_w + 8.0 + name_w + (40.0 if SHOW_TIMER else 0.0)
                + (76.0 if SHOW_WAVEFORM else 0.0))
        return max(float(base), min(float(self.WIN_W), need))

    def _words_room(self):
        if CARD_WIDTH:
            base = max(self.CARD_W, min(self.WIN_W, CARD_WIDTH))
        else:
            base = self.WIDE_W if WIDE_CARD else self.CARD_W
        return self._fit_width(base) - 32

    def _rewrap(self):
        """Lay the words out again from the start (the card changed width)."""
        words = [word for line in self.live_lines for word in line]
        measure, room = self._measure(), self._words_room()
        self.live_lines, self.line_w = [], []
        for word in words:
            last = self.live_lines[-1] if self.live_lines else None
            if last is not None and measure(" ".join(last + [word])) <= room:
                last.append(word)
            else:
                self.live_lines.append([word])
                self.line_w.append(None)
        self.row_slide = 0.0
        self.second_look = {}

    def _edge_at(self, spot):
        """'left' or 'right' when this point is on that edge of the full card
        (where a drag resizes it), else None."""
        if self.mode != "recording" or self._card is None:
            return None
        left, top, width, height = self._card
        if height <= self.NOTE_H or not (top <= spot.y() <= top + height):
            return None                          # the one-row pill has a set width
        if abs(spot.x() - left) <= 9:
            return "left"
        if abs(spot.x() - (left + width)) <= 9:
            return "right"
        return None

    def set_live_text(self, text):
        """Take the model's newest reading of the recent audio.

        Words already on the card keep their place: a reworded or re-punctuated
        word is swapped where it stands, rows that are full are never re-broken,
        and older words the model no longer re-reads stay as they were. Only
        words that are actually new are fed in, at the end."""
        self.live_target = text
        target = text.split()
        shown = [word for line in self.live_lines for word in line]
        start = overlap_start(shown, target)
        have = len(shown) - start                # words on the card this reading covers
        self.pending = target[have:]
        # The model often flips a word back and forth between readings
        # ("All right" / "Alright"). A word on the card is only swapped once
        # two readings in a row agree on the change, so it doesn't flicker.
        words, votes = list(shown[:start]), {}
        for i, new in enumerate(target[:have]):
            at = start + i
            if new == shown[at] or self.second_look.get(at) == new:
                words.append(new)
            else:
                votes[at] = new
                words.append(shown[at])
        self.second_look = votes
        if words != shown:
            self._refill(words)
        self.update()

    def _refill(self, words):
        """Put `words` back into the rows as they are, word for word."""
        measure, room = self._measure(), self._words_room()
        at, lines = 0, []
        for line in self.live_lines:
            if at >= len(words):
                break
            lines.append(words[at:at + len(line)])
            at += len(line)
        for i, line in enumerate(lines):         # a swap made a row far too long
            while len(line) > 1 and measure(" ".join(line)) > room + 14:
                if i + 1 == len(lines):
                    lines.append([])
                lines[i + 1].insert(0, line.pop())
        self.live_lines = lines
        self.line_w = (self.line_w + [None] * len(lines))[:len(lines)]
        self.live_text = " ".join(words)

    def _add_word(self, word):
        measure, room = self._measure(), self._words_room()
        last = self.live_lines[-1] if self.live_lines else None
        if last is None or measure(" ".join(last + [word])) > room:
            if len(self.live_lines) >= max(1, LIVE_LINES):
                self.row_slide = min(self.row_slide + self.LINE_H, float(self.LINE_H))
            self.live_lines.append([word])
            self.line_w.append(None)
            if len(self.live_lines) > 60:        # plenty of history to line up against
                del self.live_lines[0], self.line_w[0]
        else:
            last.append(word)
        self.word_fade = 0.0
        self.live_text = " ".join(w for line in self.live_lines for w in line)

    def _reveal_words(self):
        """Feed waiting words in at a steady pace (faster when many wait)."""
        if not self.pending:
            return
        self.reveal_credit += max(0.25, len(self.pending) / 10.0)
        step = int(self.reveal_credit)
        self.reveal_credit -= step
        for _ in range(min(step, len(self.pending))):
            self._add_word(self.pending.pop(0))

    def show_transcribing(self):
        self.mode = "transcribing"
        self.phase = 0.0
        self._present()

    PULSE_SECONDS = 0.9

    def show_message(self, text, ms=1600, pulse=False):
        """Short notice. ms=None keeps it up until something replaces it.
        pulse=True sends one wave of the accent colour out from it."""
        self.mode = "message"
        self.message = text
        self.message_stays = not ms              # no time limit: only replaced, never timed out
        self.closable = False                    # (set after this call, when wanted)
        self.progress = None                     # set again by whoever shows progress
        self.pulse_started = time.monotonic() if pulse else None
        self._message_id += 1
        this_id = self._message_id
        self._present()
        if ms:
            QtCore.QTimer.singleShot(ms, lambda: self._hide_message(this_id))

    def invite_drag(self):
        self.show_message("Drag me to where you want me", ms=7000)

    def reset_position(self):
        self._pos = None
        save_setting("anchor", None)
        save_setting("anchor2", None)
        if self.isVisible():
            self.move(self._top_left(self._home()))

    def preview(self, ms=2600, label="Your app", words=None, shape=True):
        """Show the full pop-up as a still picture: at startup, and after a
        setting change. Nothing is recorded and nothing moves, so it can't be
        mistaken for the microphone being on. shape=False leaves the bars flat."""
        self.previewing = True
        self.preview_ms = ms                     # None: stays until replaced
        self.preview_words = words
        self.show_recording(label)
        if SHOW_APP_ICON:                        # a stand-in for the app's own icon
            try:
                ratio = self.devicePixelRatioF()
                side = max(1, int(round(20 * ratio)))
                picture = app_icon().pixmap(128, 128).scaled(
                    side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                picture.setDevicePixelRatio(ratio)
                self.app_icon = picture
            except Exception:
                self.app_icon = None
        if shape:                                # a fixed, made-up outline
            still = [0.12, 0.3, 0.2, 0.55, 0.35, 0.8, 0.5, 1.0][::-1]
            for i in range(N_DOTS):
                self.levels[-1 - i] = still[i] * 0.8 if i < len(still) else 0.0
        self._message_id += 1
        this_id = self._message_id
        if ms:                                   # ms=None: stays until replaced
            QtCore.QTimer.singleShot(ms, lambda: self._end_preview(this_id))

    def _end_preview(self, preview_id):
        # The card stays a still picture while it fades out: "previewing" is
        # only cleared when a real recording (or another card) takes over.
        if self.previewing and preview_id == self._message_id:
            self.dismiss()

    def dismiss(self, force=False):
        """Fade out (the window hides once fully transparent). With the
        always-on setting, settle back to the small pill instead."""
        if ALWAYS_SHOW and not force:
            if PILL_OVER_FULLSCREEN or not fullscreen_app_in_front(self):
                self.show_idle()
                return
            self.stepped_aside = True            # a game is in front: fade out instead;
                                                 # the step-aside check brings it back
        self.fade_target = 0.0
        if not self.isVisible():
            self.timer.stop()
        else:
            self.timer.start()                   # the idle pill's clock is stopped: wake
                                                 # it, or the fade-out never happens
    # -- internals -----------------------------------------------------------
    def _hide_message(self, message_id):
        if self.mode == "message" and message_id == self._message_id:
            self.dismiss()

    def _present(self):
        if not self._dragging:
            self.move(self._top_left(self._home()))
        if not self.isVisible():
            self.fade = 0.0
        self.fade_target = 1.0
        self.show()
        self._set_hover(False)                   # worked out afresh on the next frame
        self.timer.start()
        self.update()

    def _home(self):
        """Bottom-centre point for the pop-up: the dragged spot, else just above
        the taskbar in the middle of the screen."""
        if self._pos is not None:
            # The pill must be fully on a screen, a little away from its edges
            # (older versions let it be dragged half off). A spot on a monitor
            # that has since been unplugged or moved falls back to the usual
            # place; a spot partly off a screen is pulled back onto it.
            card = QtCore.QRect(self._pos.x() - 30, self._pos.y() - 26, 60, 20)
            for screen in QtGui.QGuiApplication.screens():
                if screen.availableGeometry().intersects(card):
                    # Half the idle pill's own width (never a card's: a card
                    # as wide would push the pill away from where you put it).
                    keys = self._hotkey_keys(pill_text()) if SHOW_HOTKEY_HINT else None
                    half = self._pill_width(keys) / 2.0
                    spot = self._inside(screen.availableGeometry(), QtCore.QRectF(
                        self._pos.x() - half, self._pos.y() - self.NOTE_H,
                        2 * half, self.NOTE_H))
                    return QtCore.QPoint(self._pos.x() + int(round(spot.x())),
                                         self._pos.y() + int(round(spot.y())))
        screen = QtGui.QGuiApplication.primaryScreen()    # the main monitor
        area = screen.availableGeometry()     # excludes the taskbar
        return QtCore.QPoint(area.x() + area.width() // 2,
                             area.y() + area.height() - BOTTOM_MARGIN)

    @staticmethod
    def _inside(area, rect, gaps=None):
        """How far rect (in screen coordinates) must move to sit inside area,
        EDGE_GAP away from its edges (or gaps: left, top, right, bottom).
        Too big to fit: its top-left wins."""
        gl, gt, gr, gb = gaps or (EDGE_GAP,) * 4
        left, top = area.left() + gl, area.top() + gt
        right, bottom = area.right() + 1 - gr, area.bottom() + 1 - gb
        dx = dy = 0.0
        if rect.right() > right:
            dx = right - rect.right()
        if rect.left() + dx < left:
            dx = left - rect.left()
        if rect.bottom() > bottom:
            dy = bottom - rect.bottom()
        if rect.top() + dy < top:
            dy = top - rect.top()
        return QtCore.QPointF(dx, dy)

    @staticmethod
    def _load_position():
        try:
            if "anchor2" in _config:
                x, y = _config["anchor2"]
            else:                                # older versions saved the window's base,
                x, y = _config["anchor"]         # 18 px below the card's
                y = int(y) - 18
            return QtCore.QPoint(int(x), int(y))
        except Exception:
            return None

    def _save_position(self):
        save_setting("anchor2", [self._pos.x(), self._pos.y()])

    # -- mouse: hover shows "Cancel recording", click cancels, drag moves ----
    def _set_hover(self, value):
        value = bool(value)
        if not value:
            self.hover_armed = True
        if value != self.hover:
            self.hover = value
            self.update()
        clickable = value and ((self.mode == "recording" and not self.previewing)
                               or self._target_at(self._mouse) is not None)
        if value and (self._edge_hover or self._resizing):
            self.setCursor(Qt.SizeHorCursor)     # on an edge: drag to resize
            return
        self.setCursor(Qt.PointingHandCursor if clickable else Qt.ArrowCursor)

    def _cursor_on_card(self):
        """Is the mouse over the card that is actually drawn? (The window is
        bigger than the card: it has see-through space around it.)"""
        if self._card is None:
            return False
        spot = QtGui.QCursor.pos()
        x, y = spot.x() - self.pos().x(), spot.y() - self.pos().y()
        left, top, width, height = self._card
        return left <= x <= left + width and top <= y <= top + height

    def enterEvent(self, event):
        self._set_hover(self._cursor_on_card())

    def leaveEvent(self, event):
        self._mouse = None
        self._edge_hover = None
        self._set_hover(False)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._press = event.globalPosition().toPoint()
            self._offset = self._press - self.pos()
            self._dragging = False
            self._message_id += 1          # keep a notice up while it is held
            self._resizing = self._edge_at(event.position())

    def mouseMoveEvent(self, event):
        spot = event.position()
        self._mouse = (spot.x(), spot.y())
        if self._resizing and self._card is not None and (event.buttons() & Qt.LeftButton):
            # Dragging an edge: the card stays centred and both sides follow.
            centre = self._card[0] + self._card[2] / 2.0
            wanted = int(round(abs(spot.x() - centre) * 2.0))
            wanted = max(self.CARD_W, min(self.WIN_W, wanted))
            if wanted != CARD_WIDTH:
                globals()["CARD_WIDTH"] = wanted         # saved when you let go
                self._rewrap()
                self.update()
            return
        if self._press is None:
            edge = self._edge_at(spot)
            if edge != self._edge_hover:
                self._edge_hover = edge
                self._set_hover(self._cursor_on_card())
        if self.mode == "idle" and not self._dragging:
            self.setCursor(Qt.PointingHandCursor)      # the pill can be clicked
        if self.mode == "welcome" and not self._dragging:
            self._set_hover(self._cursor_on_card())    # refreshes the cursor shape
            self.update()                         # and the hover highlight
        if self._press is None or not (event.buttons() & Qt.LeftButton):
            return
        here = event.globalPosition().toPoint()
        if not self._dragging and (here - self._press).manhattanLength() > 6:
            self._dragging = True
        if self._dragging:
            spot = here - self._offset
            if self._card is not None:
                # Stop at the edges of the screen under the mouse (the taskbar
                # included), a few pixels short, so it can't be lost off-screen.
                screen = QtGui.QGuiApplication.screenAt(here) or self.screen()
                if screen is not None:
                    left, top, width, height = self._card
                    nudge = self._inside(screen.availableGeometry(), QtCore.QRectF(
                        spot.x() + left, spot.y() + top, width, height))
                    spot += QtCore.QPoint(int(round(nudge.x())), int(round(nudge.y())))
            self.move(spot)
            self.update()

    def mouseReleaseEvent(self, event):
        if (event.button() == Qt.RightButton and self.mode in ("idle", "message")
                and self.fade_target > 0.0 and self._cursor_on_card()):
            if self.mode == "message" and self.progress is not None:
                self.retry_wanted.emit()         # right-click the download card: retry
            else:
                self.settings_wanted.emit()      # right-click the pill: Settings
            return
        if event.button() != Qt.LeftButton or self._press is None:
            return
        if self._resizing:                       # finished resizing: keep the width
            self._resizing = None
            self._press = None
            self._dragging = False
            save_setting("card_width", int(CARD_WIDTH))
            if self.previewing:
                this_id = self._message_id
                QtCore.QTimer.singleShot(2500, lambda: self._end_preview(this_id))
            self.update()
            return
        was_drag = self._dragging
        self._press = None
        self._dragging = False
        if self.previewing and self.mode == "recording":
            # A still preview card that was moved or clicked: the press cancelled
            # its timer, so set it again, or the card would stay (and keep
            # redrawing) until the next dictation.
            if was_drag:
                self._pos = self._anchor()
                self._save_position()
            if getattr(self, "preview_ms", None):
                this_id = self._message_id
                QtCore.QTimer.singleShot(2500, lambda: self._end_preview(this_id))
            self.update()
            return
        if was_drag:
            self._pos = self._anchor()
            self._save_position()
        elif self.mode == "welcome" and self.fade_target > 0.0:
            spot = event.position()
            target = self._target_at((spot.x(), spot.y()))
            if target == "start":
                self.welcome_clicked.emit()
            elif target == "hotkey":
                self.picking = not self.picking
            elif target is not None and target.startswith("pick:"):
                self.picking = False
                self.hotkey_picked.emit(target[5:])
            elif self.picking and target is None:
                self.picking = False              # clicked away from the choices
        elif (self.mode == "recording" and self.fade_target > 0.0
              and self._cursor_on_card()):
            if self.click_started:
                self.finish_clicked.emit()
            else:
                self.cancel_clicked.emit()
        elif self.mode == "idle" and self.fade_target > 0.0 and self._cursor_on_card():
            self.pill_clicked.emit()
        elif self.mode == "message" and self._cursor_on_card():
            if self._closable() and self._close_rect is not None and \
                    self._close_rect.adjusted(-6, -6, 6, 6).contains(event.position()):
                self.closable = False            # the ×: just put it away
                self.dismiss()
            else:
                self.notice_clicked.emit()
        if self.mode == "message" and not self.message_stays:
            # A timed notice that was held or clicked goes away shortly after.
            # One with no time limit (a download in progress, say) stays put.
            this_id = self._message_id
            QtCore.QTimer.singleShot(1500, lambda: self._hide_message(this_id))
        self.update()

    def _tick(self):
        if self._press is not None and \
                not (QtGui.QGuiApplication.mouseButtons() & Qt.LeftButton):
            # The button was let go where this window never heard of it (the
            # screen locked mid-click, say): forget the press, or the pop-up
            # could never hide.
            self._press = None
            self._dragging = False
            self._resizing = None
        # Fade in quickly (about 120 ms), fade out a little slower.
        speed = 0.30 if self.fade_target > self.fade else 0.16
        self.fade += (self.fade_target - self.fade) * speed
        if self.fade_target == 0.0 and self.fade < 0.03 and self._press is None:
            self.fade = 0.0
            self.hover = False
            self.timer.stop()
            self.hide()
            return
        if self.mode == "idle" and abs(self.fade - self.fade_target) < 0.02 \
                and self._morph is None and self._slide is None:
            self.fade = self.fade_target        # nothing moves while idle:
            self.timer.stop()                   # stop redrawing, use no CPU
            self.update()
            return

        # A card that sits still (a notice, the download card, a still preview)
        # needs far fewer redraws than a live dictation: save the CPU.
        settled = abs(self.fade - self.fade_target) < 0.02 and self.word_fade >= 1.0
        if settled and self.previewing and self.mode == "recording":
            wanted = 100                          # a still picture
        elif settled and self.mode == "message":
            wanted = 50                           # progress and small movements only
        else:
            wanted = 16
        if self._morph is not None or self._slide is not None:
            wanted = 16                           # a shape change or a slide: every frame
        if self.timer.interval() != wanted:
            self.timer.setInterval(wanted)

        # Motion (fades, the card growing, the glow) is redrawn on every tick.
        # Things that move in steps (the waveform, the words, timers) advance
        # on every second tick, so they keep the pace they were tuned for.
        self.half_step = not self.half_step
        if self.word_fade < 1.0:
            self.word_fade = min(1.0, self.word_fade + 0.14)
        if self.half_step:
            self.phase += 1.0
            if self._press is None:              # keep "is the mouse on it?" honest
                self._set_hover(self._cursor_on_card())
            if self.mode == "recording" and self.fade_target > 0.0:
                if not self.previewing:
                    self.levels.append(self.recorder.level)
                    self.warning = self._mic_warning()
                    self._reveal_words()
            elif self.mode == "transcribing":
                for i in range(N_DOTS):                  # bars settle down
                    self.levels[i] *= 0.72
        self.update()

    def paintEvent(self, event):
        """Draw the pop-up, faded as one piece. Each frame is drawn fresh, at
        full strength, at the screen's real scale, then shown at the right
        transparency. (Fading each layer separately lets the shadow and glow
        show through the card, which turns it a muddy grey.) While the pill
        turns into the card or back, the two are blended as one changing
        shape (see _morph_frame)."""
        fade = max(0.0, min(1.0, self.fade))
        ratio = self.devicePixelRatioF()
        area = self._paint_area()
        frame = QtGui.QPixmap(max(1, int(round(area.width() * ratio))),
                              max(1, int(round(area.height() * ratio))))
        frame.setDevicePixelRatio(ratio)
        frame.fill(Qt.transparent)
        p = QtGui.QPainter(frame)
        try:
            p.translate(-area.x(), -area.y())
            self._draw(p)
        finally:
            p.end()
        shown = self._morph_frame(frame, fade, area)
        p = QtGui.QPainter(self)
        try:
            if fade < 0.995:
                p.setOpacity(fade)
            p.drawPixmap(area.topLeft(), shown)
        finally:
            p.end()

    SLIDE_IN, SLIDE_OUT = 0.18, 0.25     # seconds: the pill moving in for its pulse, and back

    def _ready_slide(self, card, note, width, height):
        """The "Ready" pulse needs room round the pill. With the pill close to
        a screen edge it would be cut off, so the pill first slides in just
        far enough, sends out its pulse, then glides back to its place.
        Returns how far the pill is moved in right now."""
        if note is None or self.mode != "message" or self._dragging:
            self._slide = None                   # only for the small pill's pulse
            return QtCore.QPointF(0, 0)
        now = time.monotonic()
        if self._slide is None and self.pulse_started is not None \
                and now - self.pulse_started < 0.5 and animations_on():
            screen = self._card_screen or self.screen()
            if screen is not None:
                whole = QtCore.QRectF(screen.geometry()).translated(-self.x(), -self.y())
                # How far the pulse reaches (its outer part is too faint to count).
                reach_x = (width + 2.0 * self.GLOW) * 1.42 / 2.0 * 0.82
                reach_y = (height + 2.0 * self.GLOW) * 1.62 / 2.0 * 0.82
                cx, cy = card.center().x(), card.center().y()
                dx = max(0.0, whole.left() - (cx - reach_x)) - max(0.0, (cx + reach_x) - whole.right())
                dy = max(0.0, whole.top() - (cy - reach_y)) - max(0.0, (cy + reach_y) - whole.bottom())
                if abs(dx) > 1.0 or abs(dy) > 1.0:
                    self._slide = {"t0": self.pulse_started, "shift": QtCore.QPointF(dx, dy)}
        if self._slide is None:
            return QtCore.QPointF(0, 0)
        t = now - self._slide["t0"]
        hold = self.SLIDE_IN + self.PULSE_SECONDS
        if t < self.SLIDE_IN:                    # in: quick at first, gentle at the end
            amount = 1.0 - (1.0 - t / self.SLIDE_IN) ** 3
        elif t < hold:
            amount = 1.0
        elif t < hold + self.SLIDE_OUT:          # back: gentle at both ends
            u = (t - hold) / self.SLIDE_OUT
            amount = 1.0 - u * u * (3.0 - 2.0 * u)
        else:
            self._slide = None
            return QtCore.QPointF(0, 0)
        return self._slide["shift"] * amount

    def _paint_area(self):
        """The part of the window drawn this frame: the card with room for its
        glow and shadow. The window is far wider than the card (so a card can
        shift at a screen edge), and drawing all of it every frame cost three
        times as much. The whole window is drawn when the shape is changing
        (pill to card), for the welcome card and the "Ready" pulse."""
        whole = QtCore.QRect(0, 0, self.width(), self.height())
        note = self._note_text()
        kind = "small" if note is not None else ("welcome" if self.mode == "welcome" else "card")
        if (self._card is None or self._morph is not None or kind != self._shape_kind
                or kind == "welcome" or self.pulse_started is not None or self._dragging
                or self._slide is not None):
            return whole
        left, top, width, height = self._card
        room = self.GLOW + 28
        return QtCore.QRectF(left - room, top - room, width + 2 * room,
                             height + 2 * room).toAlignedRect().intersected(whole)

    def _morph_frame(self, frame, fade, area):
        """Pill to card (or back) as one shape: its position, size, corners and
        fill move smoothly from one to the other (about 200 ms growing, 160 ms
        shrinking, fast at first, gentle at the end). What the pill showed
        fades out in the first third, what the card shows fades in over the
        last half, and the card's glow comes last. The contents are never
        stretched: each is a picture drawn at its real size, only revealed
        inside the changing shape. Windows' "Animation effects" off: no
        animation, the new shape is simply there."""
        note = self._note_text()
        kind = "small" if note is not None else ("welcome" if self.mode == "welcome" else "card")
        target = QtCore.QRectF(*self._card) if self._card else None
        radius = float(self._card_radius)
        now = time.monotonic()
        if (kind != self._shape_kind and self._last_frame is not None
                and self._last_shape is not None and target is not None
                and fade > 0.9 and self._last_fade > 0.9 and "welcome" not in
                (kind, self._shape_kind) and animations_on()):
            start, start_radius = self._last_shape
            grow = target.width() * target.height() >= start.width() * start.height()
            self._morph = {"t0": now, "length": 0.20 if grow else 0.16, "rect": start,
                           "radius": start_radius, "old": self._last_frame,
                           "origin": QtCore.QPointF(self._last_origin),
                           "from": self._shape_fill(self._shape_kind),
                           "to": self._shape_fill(kind)}
            self.timer.start()
        elif kind != self._shape_kind:
            self._morph = None
        self._shape_kind = kind
        self._last_fade = fade
        shown = frame
        morph = self._morph
        if morph is not None and target is not None:
            t = min(1.0, (now - morph["t0"]) / morph["length"])
            eased = 1.0 - (1.0 - t) ** 3

            def mix(a, b):
                return a + (b - a) * eased
            was = morph["rect"]
            shape = QtCore.QRectF(mix(was.left(), target.left()), mix(was.top(), target.top()),
                                  mix(was.width(), target.width()),
                                  mix(was.height(), target.height()))
            corner = min(mix(morph["radius"], radius), shape.height() / 2.0)
            a, b = morph["from"], morph["to"]
            body = QtGui.QColor(int(mix(a.red(), b.red())), int(mix(a.green(), b.green())),
                                int(mix(a.blue(), b.blue())), int(mix(a.alpha(), b.alpha())))
            shown = QtGui.QPixmap(frame.size())
            shown.setDevicePixelRatio(frame.devicePixelRatio())
            shown.fill(Qt.transparent)
            p = QtGui.QPainter(shown)
            try:
                p.setRenderHint(QtGui.QPainter.Antialiasing)
                p.setPen(QtGui.QPen(self._pill_colours()[1], 1.0))
                p.setBrush(body)
                p.drawRoundedRect(shape, corner, corner)
                outline = QtGui.QPainterPath()
                outline.addRoundedRect(shape, corner, corner)
                p.save()
                p.setClipPath(outline)
                leaving = max(0.0, 1.0 - t / 0.33)        # the pill's contents
                if leaving > 0.0:
                    p.setOpacity(leaving)
                    p.drawPixmap(morph["origin"], morph["old"])
                arriving = max(0.0, (t - 0.5) / 0.5)      # the card's contents
                if arriving > 0.0:
                    p.setOpacity(arriving)
                    p.drawPixmap(0, 0, frame)
                p.restore()
                outside = max(0.0, (t - 0.75) / 0.25)     # its glow, last of all
                if outside > 0.0:
                    # Only round the shape: inside it the card is drawn already.
                    around = QtGui.QPainterPath()
                    around.addRect(QtCore.QRectF(0, 0, frame.width(), frame.height()))
                    p.save()
                    p.setClipPath(around.subtracted(outline))
                    p.setOpacity(outside)
                    p.drawPixmap(0, 0, frame)
                    p.restore()
            finally:
                p.end()
            if t >= 1.0:
                self._morph = None
        self._last_frame = frame
        self._last_origin = QtCore.QPointF(area.topLeft())   # where that picture sits
        self._last_shape = (QtCore.QRectF(target), radius) if target is not None else None
        return shown

    def _shape_fill(self, kind):
        """The fill colour of a small pill, or of a card."""
        if kind == "small":
            return QtGui.QColor(self._pill_colours()[0])
        return QtGui.QColor(popup_theme()["bg"])

    def _download_lines(self, note):
        """The download card's two lines of text, and whether it is stalled."""
        title, _dot, detail = note.partition("  \u00b7  ")
        stuck = "not moving" in note or "seems blocked" in note
        if title.startswith("Downloading"):
            title = "Downloading"                # the icon and the amount say the rest
        percent = "%d%%" % int(max(0.0, min(1.0, self.progress or 0.0)) * 100)
        if stuck:
            # Short, so it is no wider than the title above it (same wording
            # style as the pill's "Click: dictate" hints).
            words = "Click: help  \u00b7  Right-click: retry"
        elif detail:
            words = "%s  \u00b7  %s" % (detail, percent)
        else:
            words = "Starting\u2026"
        return title, words, stuck

    def _draw_download(self, p, card, font, accent, theme, note):
        """The download card: the app's icon, what is happening, how much has
        arrived, and a bar with a light that travels along it. If the download
        stops moving the bar turns amber and the light stops."""
        title, words, stuck = self._download_lines(note)
        left, right, top = card.left() + 18.0, card.right() - 18.0, card.top()
        if self._own_icon is None:
            try:
                ratio = self.devicePixelRatioF()
                side = max(1, int(round(30 * ratio)))
                picture = app_icon().pixmap(128, 128).scaled(
                    side, side, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                picture.setDevicePixelRatio(ratio)
                self._own_icon = picture
            except Exception:
                self._own_icon = False
        # The icon and the two lines of text form one group, placed in the
        # middle of the card so neither side is left emptier than the other.
        font.setPixelSize(12)
        font.setWeight(QtGui.QFont.DemiBold)
        title_w = QtGui.QFontMetricsF(font).horizontalAdvance(title)
        font.setWeight(QtGui.QFont.Normal)
        # A stalled download's hint is what to do next: a size larger, in the
        # ordinary text colour (amber small print was hard to read; the amber
        # bar already says something is wrong).
        hint_size = 12 if stuck else 11
        font.setPixelSize(hint_size)
        words_w = QtGui.QFontMetricsF(font).horizontalAdvance(words)
        lead = 40.0 if self._own_icon else 0.0
        group = lead + max(title_w, words_w)
        x = card.center().x() - group / 2.0
        if self._own_icon:
            p.drawPixmap(QtCore.QRectF(x, top + 14, 30, 30), self._own_icon,
                         QtCore.QRectF(self._own_icon.rect()))
        text_left = x + lead
        font.setPixelSize(12)
        font.setWeight(QtGui.QFont.DemiBold)
        p.setFont(font)
        p.setPen(theme["text"])
        p.drawText(QtCore.QRectF(text_left, top + 11, title_w + 4, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, title)
        font.setWeight(QtGui.QFont.Normal)
        font.setPixelSize(hint_size)
        p.setFont(font)
        p.setPen(theme["text"] if stuck else theme["muted"])
        p.drawText(QtCore.QRectF(text_left, top + 29, words_w + 4, 18),
                   Qt.AlignLeft | Qt.AlignVCenter, words)
        font.setPixelSize(12)
        p.setFont(font)

        bar = QtCore.QRectF(left, top + 57.0, right - left, 6.0)
        p.setPen(Qt.NoPen)
        p.setBrush(theme["quiet"])
        p.drawRoundedRect(bar, 3, 3)
        done = max(6.0, max(0.0, min(1.0, self.progress)) * bar.width())
        fill = QtCore.QRectF(bar.left(), bar.top(), done, 6.0)
        colour = QtGui.QColor(theme["warning"]) if stuck else QtGui.QColor(accent)
        p.setBrush(colour)
        p.drawRoundedRect(fill, 3, 3)
        if not stuck:
            # A soft light sweeping along the filled part: it is alive, and moving.
            bright = QtGui.QColor(int(colour.red() + (255 - colour.red()) * 0.55),
                                  int(colour.green() + (255 - colour.green()) * 0.55),
                                  int(colour.blue() + (255 - colour.blue()) * 0.55))
            sweep = (time.monotonic() * 90.0) % (bar.width() + 60.0) - 60.0
            p.save()
            p.setClipRect(fill)
            glint = QtGui.QLinearGradient(QtCore.QPointF(bar.left() + sweep, 0),
                                          QtCore.QPointF(bar.left() + sweep + 60.0, 0))
            clear = QtGui.QColor(bright)
            clear.setAlpha(0)
            glint.setColorAt(0.0, clear)
            glint.setColorAt(0.5, bright)
            glint.setColorAt(1.0, clear)
            p.setBrush(QtGui.QBrush(glint))
            p.drawRoundedRect(fill, 3, 3)
            p.restore()

    def _draw_wave(self, p, x1, x2, y, accent, quiet):
        """The sound wave: one flowing line. Your voice sets how tall it is,
        loudest and newest in the middle, and it settles to a faint ripple
        when you are quiet. It always fits its row: the ends meet the centre
        line and the peaks stop short of the row's edges."""
        span = x2 - x1
        if span < 20.0:
            return
        drift = 0.0 if self.previewing else time.monotonic() * 5.0
        steps = max(8, int(span / 2.0))
        reach = (N_DOTS - 1) * 0.5               # how far back in time the ends show
        # Loudness jumps about from moment to moment; averaged over its
        # neighbours it makes a smooth swell instead of a jagged line.
        raw = [self.levels[-1 - j] for j in range(N_DOTS)]
        soft = []
        for j in range(N_DOTS):
            near = raw[max(0, j - 3):j + 4]
            soft.append(sum(near) / len(near))
        path = QtGui.QPainterPath()
        for i in range(steps + 1):
            u = i / float(steps)
            back = abs(u - 0.5) * 2.0 * reach
            k = int(back)
            a = soft[min(k, N_DOTS - 1)]
            b = soft[min(k + 1, N_DOTS - 1)]
            level = max(0.0, min(1.0, a + (b - a) * (back - k)))
            taper = math.sin(math.pi * u) ** 0.6             # nothing at either end
            height = (0.8 + 8.2 * min(1.0, level * 1.25)) * taper   # at most 9 px each way
            point = QtCore.QPointF(x1 + u * span,
                                   y + math.sin(u * span * 0.16 - drift) * height)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        speaking = max(self.levels[-1 - j] for j in range(6)) > 0.05
        pen = QtGui.QPen(accent if speaking else quiet, 1.8)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)

    def _draw(self, p):
        """Everything in the pop-up, at full strength, onto the given painter."""
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)    # no jagged icons
        fade = 1.0
        p.setOpacity(fade)
        g = self.GLOW
        base = self.height() - g - self._below()  # the pill sits on this line
        note = self._note_text()
        warning = "" if self.previewing else self.warning
        third = LIVE_PREVIEW or bool(self.previewing and self.preview_words) or bool(warning)
        drop = 28                             # one top row: icon, wave and timer side
                                              # by side (there is no middle row)
        lines = LIVE_LINES if (LIVE_PREVIEW and not self.previewing) else 1
        if third and lines > 1 and not warning:
            # How many rows the words need right now: the card starts with one
            # and grows a row at a time, up to the number chosen in Settings.
            needed = float(max(1, min(lines, len(self.live_lines))))
        else:
            needed = 1.0
        self.rows += (needed - self.rows) * 0.16             # eased growth
        if abs(needed - self.rows) < 0.02:
            self.rows = needed

        if note is not None:            # small pill that grows to fit its text
            note_font = ui_font()
            note_font.setPixelSize(12)
            wanted = QtGui.QFontMetricsF(note_font).horizontalAdvance(note) + 58.0
            width = max(80.0, min(380.0, wanted))                # hugs short text
            height, radius = float(self.NOTE_H), self.NOTE_H / 2.0
            # Every small pill (idle, "Ready", notices) is one height and one
            # look, so moving from one to the next never jumps in size.
            keys = self._hotkey_keys(note)
            width = self._pill_width(keys, "" if keys else note)
            height = self._pill_height()
            radius = height / 2.0
            if self.progress is not None and self.mode == "message":
                # The download card: just wide enough for its text, with the
                # same margin on every side.
                bold = ui_font()
                bold.setPixelSize(12)
                bold.setWeight(QtGui.QFont.DemiBold)
                small = ui_font()
                small.setPixelSize(11)
                title, words, _stuck = self._download_lines(note)
                widest = max(QtGui.QFontMetricsF(bold).horizontalAdvance(title),
                             QtGui.QFontMetricsF(small).horizontalAdvance(words))
                width, height, radius = 18.0 + 40.0 + widest + 18.0, 80.0, 18.0
        elif self.mode == "welcome":
            width, height, radius = float(self.WELCOME_W), float(self.WELCOME_H), 18.0
        else:
            width = float(self.WIDE_W if (third and lines > 1 and WIDE_CARD)
                          else self.CARD_W)
            if CARD_WIDTH:                       # dragged to your own width
                width = float(max(self.CARD_W, min(self.WIN_W, CARD_WIDTH)))
            width = self._fit_width(width)       # room for the app's name in full
            if warning:                          # a microphone warning, never cut short
                said = ui_font()
                said.setPixelSize(TEXT_SIZE)
                width = max(width, min(float(self.WIN_W),
                                       QtGui.QFontMetricsF(said).horizontalAdvance(warning)
                                       + 34.0))
            # What sits on the top row, left to right: the app's icon (or a
            # dot), its name if wanted, the wave, the timer.
            one_row = not third                  # no words under it: a pill
            hug = one_row and not SHOW_WAVEFORM  # nothing stretchy: fit the contents
            top_font = ui_font()
            top_font.setPixelSize(12)
            top_font.setWeight(QtGui.QFont.DemiBold)
            top_metrics = QtGui.QFontMetricsF(top_font)
            icon_w = 20.0 if self.app_icon is not None else 10.0
            label = self.app_name
            if not label and self.app_icon is None and not SHOW_WAVEFORM:
                label = "Dictating"              # otherwise the row would be just a dot
            name_room = (width - 28.0 - icon_w - 8.0
                         - (40.0 if SHOW_TIMER else 0.0)
                         - (44.0 if SHOW_WAVEFORM else 0.0))
            label = top_metrics.elidedText(label, Qt.ElideRight, max(20.0, name_room)) \
                if label else ""
            name_w = top_metrics.horizontalAdvance(label) if label else 0.0
            parts_w = (icon_w + ((8.0 + name_w) if label else 0.0)
                       + (40.0 if SHOW_TIMER else 0.0))
            if hug:
                width = min(width, max(64.0, parts_w + 28.0))
            height = float(self.CARD_H - drop
                           + ((8 + self.LINE_H * self.rows) if third else 0))
            radius = 18.0
            if one_row:
                # One row only: a proper pill, the same shape and height as the
                # resting pill, not a short card with card-sized corners.
                height = float(self.NOTE_H)
                radius = height / 2.0
        top = base - height                      # small pills, welcome, download card
        if note is None and self.mode != "welcome":
            # A dictation card opens centred on the pill: it grows out evenly
            # from the pill's middle. Never into the taskbar or off the screen,
            # though: then it sits just high enough to stay clear.
            top = base - self.NOTE_H / 2.0 - height / 2.0
        card = QtCore.QRectF((self.width() - width) / 2.0, top, width, height)
        if self._dragging:
            card.translate(self._clamp_shift)    # as it was when the drag began
        else:
            # Never into the taskbar or off the screen: a card opened from a
            # pill near an edge or a corner moves just far enough to fit.
            # (While dragging it keeps that shift: the drag itself stops at
            # the edges, and dropping it changes nothing for one frame.)
            centre = self.mapToGlobal(QtCore.QPoint(self.width() // 2, int(base)))
            screen = (QtGui.QGuiApplication.screenAt(centre) or self.screen()
                      or QtGui.QGuiApplication.primaryScreen())
            if screen is not None:
                room, whole = screen.availableGeometry(), screen.geometry()
                gaps = None
                if note is None and self.mode != "welcome":
                    # A dictation card keeps a little more room from the
                    # screen's real edges, so its glow has space to fade out
                    # instead of meeting the edge, and from the taskbar, so
                    # its glow doesn't touch the icons there.
                    gaps = tuple(self.CARD_EDGE_GAP if at_edge else self.TASKBAR_GAP
                                 for at_edge in (
                        room.left() == whole.left(), room.top() == whole.top(),
                        room.right() == whole.right(), room.bottom() == whole.bottom()))
                shift = self._inside(room, card.translated(self.x(), self.y()), gaps)
                card.translate(shift)
                self._clamp_shift = shift
                self._card_screen = screen
        card.translate(self._ready_slide(card, note, width, height))
        # On whole screen pixels: a card at half a pixel smears every letter
        # in it over two rows of pixels, and the text looks slightly blurred.
        ratio = max(1.0, float(self.devicePixelRatioF()))
        card.moveTo(round(card.left() * ratio) / ratio, round(card.top() * ratio) / ratio)
        self._card = (card.left(), card.top(), width, height)
        self._card_radius = radius
        cy = card.center().y()
        cx = card.center().x()
        accent = QtGui.QColor(ACCENT)
        theme = popup_theme()
        if is_light(POPUP_BG):
            accent = accent_on_light(accent)     # keeps the bars vivid on a pale card
        flat = note is not None and self.progress is None

        # Soft drop shadow under the card: lighter and tighter under the small
        # pill, where a full shadow reads as a heavy dark ring.
        shadow = QtGui.QColor(theme["shadow"])
        spread = 9
        if note is not None:
            shadow.setAlpha(int(shadow.alpha() * 0.45))
            spread = 5
        p.setPen(Qt.NoPen)
        p.setBrush(shadow)
        # (The card no longer gets this stepped shadow: a soft blurred shadow
        # or the glow does that job, and the steps showed as faint rings.)

        # A single pulse of the accent colour, used once when the app says
        # "Ready": it swells out from the pill and fades as it goes.
        if self.pulse_started is not None and self.mode == "message":
            delay = self.SLIDE_IN if self._slide is not None else 0.0
            t = (time.monotonic() - self.pulse_started - delay) / self.PULSE_SECONDS
            if t >= 1.0:
                self.pulse_started = None
            elif t >= 0.0:
                wave = glow_pixmap(width, height, radius, QtGui.QColor(ACCENT),
                                   float(self.GLOW), 15.0, self.devicePixelRatioF())
                if wave is not None:
                    eased = 1.0 - (1.0 - t) ** 3             # fast at first, then slowing
                    scale = 1.0 + 0.42 * eased
                    gw = (width + 2.0 * self.GLOW) * scale
                    gh = (height + 2.0 * self.GLOW) * (1.0 + 0.62 * eased)
                    p.setOpacity(fade * (1.0 - t) ** 1.6)
                    p.drawPixmap(QtCore.QRectF(card.center().x() - gw / 2.0,
                                               card.center().y() - gh / 2.0, gw, gh),
                                 wave, QtCore.QRectF(wave.rect()))
                    p.setOpacity(fade)

        if flat:
            # A small pill (idle, "Ready", a notice): flat and crisp, with no
            # shadow, glow or shading. ("Ready" still sends out its one pulse.)
            keys = self._hotkey_keys(note)
            # The mark is a status light: the accent colour when all is well,
            # amber while the model loads, red when something needs you.
            light = accent
            if self.status == "problem":
                light = QtGui.QColor(theme["danger"])
            elif self.status == "busy":
                light = QtGui.QColor(theme["warning"])
            self._draw_pill(p, keys, card, light, "" if keys else note)
            return

        if note is not None and self.progress is not None and self.mode == "message":
            halo = glow_pixmap(width, height, radius,
                               QtGui.QColor(theme["warning"]) if "not moving" in note
                               else QtGui.QColor(ACCENT), float(self.GLOW), 15.0,
                               self.devicePixelRatioF())
            if halo is not None:
                breath = 0.5 + 0.5 * math.sin(time.monotonic() * 1.6)
                p.setOpacity(fade * (0.30 + 0.16 * breath))
                p.drawPixmap(QtCore.QRectF(card.left() - self.GLOW, card.top() - self.GLOW,
                                           width + 2 * self.GLOW, height + 2 * self.GLOW),
                             halo, QtCore.QRectF(halo.rect()))
                p.setOpacity(fade)

        # Around the card: a soft glow and a ring, both in the accent colour and
        # both optional. They sit outside the card, on whatever is behind it, so
        # they use the accent as chosen (the deepened version made for pale cards
        # would vanish against a dark screen).
        live = self.mode == "recording" and not self.previewing
        if live:
            voice = max(0.0, min(1.0, self.levels[-1]))
            self.ring += (voice - self.ring) * 0.19          # eased, so it doesn't flicker
            self.spin = (self.spin + 1.5 + 3.5 * self.ring) % 360.0
        else:
            self.ring = 0.0                      # still cards stay plain
        vivid = glow_base()
        if GLOW_FROM_APP and self.app_colour is not None and self.mode == "recording":
            vivid = QtGui.QColor(self.app_colour)    # glow in the app icon's own colour
        amount = glow_amount() if CARD_STYLE == "glow" else 0.0
        if CARD_STYLE != "glow":
            # A soft, neutral shadow under the card, the way the system's own
            # pop-ups float: dark and wide, a little lower than the card, never
            # tinted (a coloured halo looks muddy over some apps).
            shade = glow_pixmap(width, height, radius, QtGui.QColor(0, 0, 0),
                                float(self.GLOW), 16.0, self.devicePixelRatioF())
            if shade is not None:
                p.setOpacity(fade * (0.22 if is_light(POPUP_BG) else 0.42))
                p.drawPixmap(QtCore.QRectF(card.left() - self.GLOW,
                                           card.top() - self.GLOW + 5.0,
                                           width + 2 * self.GLOW, height + 2 * self.GLOW),
                             shade, QtCore.QRectF(shade.rect()))
                p.setOpacity(fade)

        # The glow belongs to dictating: it is there while you are talking to
        # the app (and in previews from Settings), never on the idle pill, the
        # notices or the welcome card.
        if amount > 0.0 and (live or self.previewing):
            breath = 0.5 + 0.5 * math.sin(self.phase * 0.07) if live else 0.5
            strength = ((0.55 + 0.10 * breath + 0.35 * self.ring) if live else 0.6) * amount
            spread = 1.0 + (0.012 * breath + 0.05 * self.ring if live else 0.0)
            # Near a screen edge the whole glow draws in, evenly on every
            # side, to the room there is: smooth all round, never cut off by
            # the edge or squeezed on one side.
            margin = float(self.GLOW)
            screen = (self._card_screen or self.screen()
                      or QtGui.QGuiApplication.primaryScreen())
            if self._dragging and self._glow_margin is not None:
                margin = self._glow_margin       # steady while dragging (no rebuilds)
            elif screen is not None:
                whole = QtCore.QRectF(screen.geometry()).translated(-self.x(), -self.y())
                space = min(card.left() - whole.left(), card.top() - whole.top(),
                            whole.right() - card.right(), whole.bottom() - card.bottom())
                # In steps of 4 px, so the picture is made a few times, not
                # once for every pixel the card moves.
                margin = float(max(8, min(self.GLOW, (int(space) - 2) // 4 * 4)))
            self._glow_margin = margin
            glow = glow_pixmap(width, height, radius, vivid, margin, 15.0 * margin / self.GLOW,
                               self.devicePixelRatioF())
            if glow is not None:
                # One smooth picture of the glow, faded in and out and nudged
                # outward: in silence it breathes slowly, your voice pushes it.
                # The swell is a set number of pixels, the same as on the
                # standard card, however wide the card has been dragged. (As a
                # share of the card's size it ballooned on a wide one.)
                gw = width + 2 * margin + (self.CARD_W + 2 * margin) * (spread - 1.0)
                gh = height + 2 * margin + (100.0 + 2 * margin) * (spread - 1.0)
                p.setOpacity(fade * min(1.0, strength * 1.15))
                outer = QtCore.QRectF(cx - gw / 2.0, cy - gh / 2.0, gw, gh)
                p.drawPixmap(outer, glow, QtCore.QRectF(glow.rect()))
                if live and self.ring > 0.06 and animations_on():
                    # Your voice brings in the partner shade over the app's colour.
                    partner = glow_pixmap(width, height, radius, partner_colour(vivid),
                                          margin, 15.0 * margin / self.GLOW,
                                          self.devicePixelRatioF())
                    if partner is not None:
                        p.setOpacity(fade * min(1.0, strength * 1.15) * min(0.45, self.ring * 0.7))
                        p.drawPixmap(outer, partner, QtCore.QRectF(partner.rect()))
                p.setOpacity(fade)
            else:
                # Fallback: the same glow built from many faint outlines.
                reach = 24.0 + 3.0 * breath + 7.0 * self.ring
                p.setBrush(Qt.NoBrush)
                layer = int(reach)
                while layer > 0:
                    halo = QtGui.QColor(vivid)
                    halo.setAlpha(min(255, int(
                        58 * strength * (1.0 - layer / (reach + 1.0)) ** 2.6)))
                    p.setPen(QtGui.QPen(halo, layer * 2.0))
                    p.drawRoundedRect(card, radius, radius)
                    layer -= 1

        if ACCENT_OUTLINE:
            # The ring sits just outside the card and follows its shape exactly.
            # It swells with your voice; optionally a brighter band of light
            # travels round it.
            thickness = 1.4 + 1.6 * self.ring
            if OUTLINE_LIGHT:
                sweep = QtGui.QConicalGradient(QtCore.QPointF(cx, cy), -self.spin)
                # The travelling light is the same colour, a shade lighter. (Much
                # lighter and it turns white, which reads as a glint on a dark card.)
                bright = QtGui.QColor(int(vivid.red() + (255 - vivid.red()) * 0.22),
                                      int(vivid.green() + (255 - vivid.green()) * 0.22),
                                      int(vivid.blue() + (255 - vivid.blue()) * 0.22))
                for position, colour in ((0.00, bright), (0.14, vivid), (0.86, vivid),
                                         (1.00, bright)):
                    sweep.setColorAt(position, colour)
                pen = QtGui.QPen(QtGui.QBrush(sweep), thickness)
            else:
                pen = QtGui.QPen(vivid, thickness)
            grow = thickness / 2.0
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawRoundedRect(card.adjusted(-grow, -grow, grow, grow),
                              radius + grow, radius + grow)
            p.setPen(Qt.NoPen)

        # The card itself: a touch lighter at the top than the bottom, with a
        # faint highlight along its upper edge, so it reads as a raised surface
        # and not a flat block.
        top_colour = QtGui.QColor(theme["bg"]).lighter(124 if not is_light(POPUP_BG) else 101)
        top_colour.setAlpha(theme["bg"].alpha())
        surface = QtGui.QLinearGradient(QtCore.QPointF(0, card.top()),
                                        QtCore.QPointF(0, card.bottom()))
        surface.setColorAt(0.0, top_colour)
        surface.setColorAt(1.0, theme["bg"])
        p.setPen(Qt.NoPen)
        p.setBrush(QtGui.QBrush(surface))
        p.drawRoundedRect(card, radius, radius)          # the surface, drawn once
        p.setBrush(Qt.NoBrush)

        # Its edge, drawn last so nothing covers part of it (a half-hidden edge
        # is what makes rounded corners look jagged). While the glow is showing,
        # the edge is a fine line in the glow's colour; otherwise a quiet neutral.
        if not ACCENT_OUTLINE:
            if amount > 0.0 and (live or self.previewing):
                edge = QtGui.QColor(vivid)
                edge.setAlpha(125)
            else:
                # A bezel: the one edge line catches light at the top and falls
                # away toward the bottom, like the rim of a raised button. (It is
                # the same single line, not an extra one inside it.)
                dark = not is_light(POPUP_BG)
                tone = (255, 255, 255) if dark else (0, 0, 0)
                rim = QtGui.QLinearGradient(QtCore.QPointF(0, card.top()),
                                            QtCore.QPointF(0, card.bottom()))
                for position, alpha in (((0.0, 78), (0.45, 30), (1.0, 14)) if dark
                                        else ((0.0, 14), (0.55, 24), (1.0, 40))):
                    rim.setColorAt(position, QtGui.QColor(*tone, alpha))
                edge = QtGui.QBrush(rim)
                if CARD_STYLE == "accent" and (live or self.previewing):
                    edge = QtGui.QColor(glow_base())   # your accent, never the app's
                    edge.setAlpha(170)
            if True:
                # One whole screen pixel or two, lined up with the pixels, so
                # the edge is crisp rather than a soft grey smear.
                ratio = self.devicePixelRatioF() or 1.0
                line = max(1, int(round(ratio))) / ratio
                snap = lambda value: round(value * ratio) / ratio
                # Drawn as a filled ring (the card's shape less the same shape
                # one line smaller): its curves come out smoother than a thin
                # drawn line, which shows steps at the corners at 100%.
                outer_box = QtCore.QRectF(snap(card.left()), snap(card.top()),
                                          snap(card.width()), snap(card.height()))
                outer = QtGui.QPainterPath()
                outer.addRoundedRect(outer_box, radius, radius)
                inner = QtGui.QPainterPath()
                inner.addRoundedRect(outer_box.adjusted(line, line, -line, -line),
                                     radius - line, radius - line)
                p.setPen(Qt.NoPen)
                p.fillPath(outer.subtracted(inner), QtGui.QBrush(edge))
        p.setPen(Qt.NoPen)

        font = ui_font()
        font.setPixelSize(12)
        p.setFont(font)

        still = self.mode == "idle" or self.previewing
        pulse = 1.0 if still else 0.5 + 0.5 * math.sin(self.phase * 0.16)

        def breathing_dot(centre, size):
            halo = QtGui.QColor(accent)
            halo.setAlpha(int(70 * (1.0 - pulse)))
            p.setPen(Qt.NoPen)
            p.setBrush(halo)
            p.drawEllipse(centre, size + 1.0 + size * pulse, size + 1.0 + size * pulse)
            p.setBrush(accent)
            p.drawEllipse(centre, size, size)

        if note is not None and self.progress is not None and self.mode == "message":
            self._draw_download(p, card, font, accent, theme, note)
            return

        if note is not None:
            metrics = QtGui.QFontMetricsF(font)
            text = metrics.elidedText(note, Qt.ElideRight, width - 52)
            text_w = metrics.horizontalAdvance(text)
            start = cx - (text_w + 16) / 2.0
            breathing_dot(QtCore.QPointF(start + 4, cy), 4.0)
            p.setPen(theme["text"])
            p.drawText(QtCore.QRectF(start + 16, card.top(), text_w + 4, height),
                       Qt.AlignLeft | Qt.AlignVCenter, text)
            return

        if self.mode == "welcome":
            self._paint_welcome(p, card, font, accent, breathing_dot)
            return

        cancel_view = (self.mode == "recording" and self.hover and not self.previewing
                       and not self._dragging and self.fade_target > 0.0
                       and self.hover_armed and not self._resizing
                       and not self._edge_hover)
        if cancel_view:
            p.setOpacity(fade * 0.2)

        # The top row, left to right: the app being dictated into (its icon,
        # with a breathing dot on the corner; with no icon the dot stands
        # alone), its name if wanted, the wave, and the timer on the right.
        row1 = cy if one_row else card.top() + 24
        font.setWeight(QtGui.QFont.DemiBold)
        p.setFont(font)
        x = (cx - parts_w / 2.0) if hug else card.left() + 14.0
        if hug and not label and self.app_icon is not None and not SHOW_TIMER:
            x -= 1.5                             # the corner dot hangs off the right:
                                                 # centre the pair, not the icon alone
        end = (cx + parts_w / 2.0) if hug else card.right() - 14.0
        if self.app_icon is not None:
            p.drawPixmap(QtCore.QRectF(x, row1 - 10, 20, 20), self.app_icon,
                         QtCore.QRectF(self.app_icon.rect()))     # already the right size
            breathing_dot(QtCore.QPointF(x + 19, row1 + 8), 3.0)
        else:
            breathing_dot(QtCore.QPointF(x + 5, row1), 4.0)
        x += icon_w
        if label:
            p.setPen(theme["text"])
            p.drawText(QtCore.QRectF(x + 8, row1 - 11, name_w + 4, 22),
                       Qt.AlignLeft | Qt.AlignVCenter, label)
            x += 8.0 + name_w
        font.setWeight(QtGui.QFont.Normal)
        p.setFont(font)
        seconds = 0 if self.previewing else int(max(0.0, time.monotonic() - self.started))
        if SHOW_TIMER:
            p.setPen(theme["muted"])
            p.drawText(QtCore.QRectF(end - 36, row1 - 11, 36, 22),
                       Qt.AlignRight | Qt.AlignVCenter, "%d:%02d" % divmod(seconds, 60))
            end -= 40.0
        if SHOW_WAVEFORM:
            # The wave fills the space between the icon and the timer: short
            # on the compact card, longer as the card is dragged wider.
            self._draw_wave(p, x + 12.0, end - 2.0, row1, accent, theme["quiet"])

        # Below: the words heard so far.        # Below: the words heard so far. One line shows the latest words; with
        # more lines the text wraps and the most recent lines are kept.
        if third:
            font.setPixelSize(TEXT_SIZE)
            p.setFont(font)
            metrics = QtGui.QFontMetricsF(font)
            room = width - 32
            if warning:
                words, lines = warning, 1
                colour = theme["danger" if warning == self.NO_SOUND else "warning"]
            elif self.previewing:
                words = self.preview_words or "Your words appear here"
                colour = theme["muted"]
            elif self.live_text:
                words, colour = self.live_text, theme["text2"]
            else:
                words, colour = "Listening\u2026", theme["faint"]
            p.setPen(colour)
            # When the line changes between your words and a notice ("No text
            # box selected"), the new one fades in over a fifth of a second
            # instead of snapping in.
            key = warning or "words"
            now = time.monotonic()
            if key != self._line_key:
                self._line_key, self._line_t0 = key, now
            appear = min(1.0, (now - self._line_t0) / 0.2) if animations_on() else 1.0
            p.save()
            p.setOpacity(p.opacity() * (1.0 - (1.0 - appear) ** 2))
            if lines == 1:
                side = Qt.ElideRight if warning else Qt.ElideLeft
                p.drawText(QtCore.QRectF(card.left() + 16, card.top() + 70 - drop, room,
                                         self.LINE_H + 4),
                           Qt.AlignCenter, metrics.elidedText(words, side, room))
            elif not self.live_lines:
                p.drawText(QtCore.QRectF(card.left() + 16, card.top() + 70 - drop, room,
                                         self.LINE_H + 4), Qt.AlignCenter, words)
            else:
                rows = max(1, min(lines, int(self.rows + 0.999)))
                line_h = self.LINE_H
                self.row_slide *= 0.80              # rows glide up to make room
                if self.row_slide < 0.3:
                    self.row_slide = 0.0
                count = len(self.live_lines)
                extra = 1 if (self.row_slide > 0.0 and count > rows) else 0
                first = max(0, count - rows - extra)
                top = card.top() + 70 - drop + self.row_slide - extra * line_h
                p.save()                         # rows sliding in or out stay in their area
                p.setClipRect(QtCore.QRectF(card.left(), card.top() + 68 - drop,
                                            card.width(),
                                            max(0.0, card.bottom() - card.top() - 68 + drop)))
                for i in range(first, count):
                    line = self.live_lines[i]
                    text = " ".join(line)
                    real = metrics.horizontalAdvance(text)
                    drawn = self.line_w[i]
                    if drawn is None or abs(real - drawn) < 0.4:
                        drawn = real
                    else:                        # centred, but it glides rather than hops
                        drawn += (real - drawn) * 0.22
                    self.line_w[i] = drawn
                    x = card.left() + 16 if LIVE_ALIGN == "left" else cx - drawn / 2.0
                    y = top + (i - first) * line_h
                    box = QtCore.QRectF(x, y, real + 8, line_h + 4)
                    side = Qt.AlignLeft | Qt.AlignVCenter
                    if extra and i == first:     # the row leaving: fades as it slides
                        leaving = QtGui.QColor(colour)
                        leaving.setAlpha(int(leaving.alpha()
                                             * max(0.0, self.row_slide / line_h) ** 2))
                        p.setPen(leaving)
                        p.drawText(box, side, text)
                    elif i == count - 1 and self.word_fade < 1.0:
                        head = " ".join(line[:-1])
                        if head:
                            p.setPen(colour)
                            p.drawText(box, side, head)
                        soft = QtGui.QColor(colour)
                        soft.setAlpha(int(soft.alpha() * self.word_fade))
                        p.setPen(soft)
                        shift = metrics.horizontalAdvance(head + " ") if head else 0.0
                        p.drawText(QtCore.QRectF(x + shift, y, real + 8, line_h + 4),
                                   side, line[-1])
                    else:
                        p.setPen(colour)
                        p.drawText(box, side, text)
                p.restore()
            font.setPixelSize(12)
            p.setFont(font)

            p.restore()
        if cancel_view:
            p.setOpacity(fade)
            font.setWeight(QtGui.QFont.DemiBold)
            p.setFont(font)
            p.setPen(theme["text"])
            hint = "Click to finish" if self.click_started else "Click to cancel"
            if card.width() < 110:
                hint = "Finish" if self.click_started else "Cancel"
            p.drawText(card, Qt.AlignCenter, hint)


def _paint_welcome(self, p, card, font, accent, breathing_dot):
    """First-run card: shows the hotkey (click it to pick another) and a
    Get started button. Only the drawn controls respond to clicks."""
    cx = card.center().x()
    theme = popup_theme()
    white = theme["text"]
    grey = theme["muted"]
    over = None if self._dragging else self._target_at(self._mouse)
    hits = {}

    def chip(rect, text, name, selected=False):
        x, y, w, h = rect
        hits[name] = rect
        hot = over == name
        p.setPen(QtGui.QPen(accent if (selected or hot) else theme["chip_border"], 1.0))
        p.setBrush(theme["chip_hot"] if hot else theme["chip"])
        p.drawRoundedRect(QtCore.QRectF(x, y, w, h), h / 2.0, h / 2.0)
        p.setPen(white)
        p.drawText(QtCore.QRectF(x, y, w, h), Qt.AlignCenter, text)

    font.setPixelSize(13)
    font.setWeight(QtGui.QFont.DemiBold)
    p.setFont(font)
    p.setPen(white)
    if self.picking:
        title = "Choose a hotkey"
    else:
        title = "Dictation is ready" if self.welcome_ready else "Setting up dictation"
    p.drawText(QtCore.QRectF(card.left(), card.top() + 8, card.width(), 20),
               Qt.AlignCenter, title)
    font.setPixelSize(12)
    font.setWeight(QtGui.QFont.Normal)
    p.setFont(font)
    metrics = QtGui.QFontMetricsF(font)

    if self.picking:                            # two columns of choices
        choices = list(HOTKEY_CHOICES)
        if HOTKEY not in choices:
            choices.insert(0, HOTKEY)
        choices = choices[:6]
        chip_w, chip_h, gap = 116.0, 19.0, 4.0
        left = cx - chip_w - gap / 2.0
        for i, choice in enumerate(choices):
            chip((left + (i % 2) * (chip_w + gap),
                  card.top() + 32 + (i // 2) * (chip_h + gap), chip_w, chip_h),
                 pretty(choice), "pick:" + choice, selected=(choice == HOTKEY))
        self._hits = hits
        return

    # "Hold [Ctrl+Space] and speak": the hotkey is a chip you can click.
    before = "Hold" if HOLD_TO_TALK else "Press"
    after = "and speak"
    key = pretty(HOTKEY)
    chip_w = metrics.horizontalAdvance(key) + 22.0
    widths = [metrics.horizontalAdvance(before), chip_w, metrics.horizontalAdvance(after)]
    x = cx - (sum(widths) + 16.0) / 2.0
    row = card.top() + 45
    p.setPen(grey)
    p.drawText(QtCore.QRectF(x, row - 11, widths[0] + 2, 22),
               Qt.AlignLeft | Qt.AlignVCenter, before)
    x += widths[0] + 8.0
    chip((x, row - 11, chip_w, 22.0), key, "hotkey", selected=True)
    x += chip_w + 8.0
    p.setPen(grey)
    p.drawText(QtCore.QRectF(x, row - 11, widths[2] + 2, 22),
               Qt.AlignLeft | Qt.AlignVCenter, after)

    row = card.top() + 78
    if self.welcome_ready:                      # the button, and only the button
        rect = (cx - 52.0, row - 12.0, 104.0, 24.0)
        hits["start"] = rect
        fill = QtGui.QColor(accent)
        if over != "start":
            fill.setAlpha(210)
        p.setPen(Qt.NoPen)
        p.setBrush(fill)
        p.drawRoundedRect(QtCore.QRectF(*rect), 12, 12)
        font.setWeight(QtGui.QFont.DemiBold)
        p.setFont(font)
        p.setPen(QtGui.QColor(16, 17, 20))
        p.drawText(QtCore.QRectF(*rect), Qt.AlignCenter, "Get started")
    else:                                       # still loading / downloading
        font.setPixelSize(11)
        p.setFont(font)
        note = "Getting the speech model ready\u2026"
        width = QtGui.QFontMetricsF(font).horizontalAdvance(note)
        breathing_dot(QtCore.QPointF(cx - width / 2.0 - 10, row), 3.0)
        p.setPen(grey)
        p.drawText(QtCore.QRectF(cx - width / 2.0, row - 10, width + 4, 20),
                   Qt.AlignLeft | Qt.AlignVCenter, note)
    self._hits = hits


Overlay._paint_welcome = _paint_welcome


def swatch_picture(colour, chosen, ratio):
    """A colour circle for Settings, drawn with smooth edges at the screen's
    real resolution. The chosen one gets a thin ring with a gap around it."""
    size = 24
    picture = QtGui.QPixmap(int(round(size * ratio)), int(round(size * ratio)))
    picture.fill(Qt.transparent)
    p = QtGui.QPainter(picture)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    p.scale(ratio, ratio)
    middle = QtCore.QPointF(size / 2.0, size / 2.0)
    light = light_menus()
    # On the light look a very light colour gets a faint edge, or it is lost.
    faint = light and QtGui.QColor(colour).lightnessF() > 0.85
    p.setPen(QtGui.QPen(QtGui.QColor("#B5B9C2"), 1.0) if faint else Qt.NoPen)
    p.setBrush(QtGui.QColor(colour))
    dot = 7.0 if chosen else 9.0
    p.drawEllipse(middle, dot, dot)
    if chosen:
        p.setBrush(Qt.NoBrush)
        p.setPen(QtGui.QPen(QtGui.QColor("#1B1D22" if light else "#FFFFFF"), 1.6))
        p.drawEllipse(middle, 10.4, 10.4)
    p.end()
    picture.setDevicePixelRatio(ratio)
    return picture


class ChoiceButton(QtWidgets.QPushButton):
    """A choice button (such as Dark / Light) drawn by hand, so its rounded
    border is smooth: style-sheet borders are not anti-aliased and their
    corners look jagged, most of all in the bright colour of a chosen one."""

    def __init__(self, text, radius=6.0, height=28):
        super().__init__(text)
        self._chosen = False
        self._radius = float(radius)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)
        self.setFixedHeight(height)
        self.setMinimumWidth(self.fontMetrics().horizontalAdvance(text) + 32)

    def setChosen(self, chosen):
        self._chosen = bool(chosen)
        self.update()

    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        hover = self.underMouse()
        light = light_menus()
        if light:
            fill = QtGui.QColor("#F0F1F4" if hover else "#FFFFFF")
            if self.isDown():
                fill = QtGui.QColor("#E6E8EC")
            edge = QtGui.QColor(accent_on_light(QtGui.QColor(ACCENT))) if self._chosen \
                else QtGui.QColor("#B5B9C2" if hover else "#CDD0D7")
        else:
            fill = QtGui.QColor("#2D3037" if hover else "#24262C")
            if self.isDown():
                fill = QtGui.QColor("#1E2025")
            edge = QtGui.QColor(ACCENT) if self._chosen else QtGui.QColor(
                "#454852" if hover else "#34363E")
        p.setPen(QtGui.QPen(edge, 1.0))
        p.setBrush(fill)
        p.drawRoundedRect(QtCore.QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5),
                          self._radius, self._radius)
        p.setPen(QtGui.QColor("#1B1D22" if light else "#E6E7EC"))
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


# ---------------------------------------------------------------------------
# The controller
# ---------------------------------------------------------------------------
class Dictation(QObject):
    model_ready = Signal(bool, str)
    result = Signal(int, str, bool)
    typed = Signal(str)
    after_ready = Signal(str)            # the text is in: the key after it, if any
    live_text = Signal(int, str)
    live_words = Signal(int, str, int, str)        # typing as you speak: a reading
    live_piece = Signal(int, str, int, int, str)   # ... and a finished piece
    model_suspect = Signal(str)

    def __init__(self, app):
        super().__init__()
        self.app = app
        self.model = None
        self.load_seconds = None
        self.vad = None
        self.model_event = threading.Event()
        self.model_error = ""
        self.recorder = Recorder()
        self.recording = False
        self.seq = 0
        self.overlay = Overlay(self.recorder)
        self.downloading = False
        self.download_failures = 0
        self.download_blocked = False
        self.download_stuck = False
        self.download_got = 0
        self.download_moved = time.monotonic()
        self.load_failed_at = None
        self.load_thread = None
        self.download_timer = QTimer(self)
        self.download_timer.setInterval(500)
        self.download_timer.timeout.connect(self._download_tick)
        self.model_suspect.connect(self.on_model_suspect)
        self.overlay.setAttribute(Qt.WA_MacAlwaysShowToolWindow)
        self.overlay.cancel_clicked.connect(self.on_cancel)
        self.overlay.finish_clicked.connect(self.on_release)
        self.overlay.pill_clicked.connect(self.on_pill_clicked)
        self.overlay.settings_wanted.connect(self.open_settings)
        self.overlay.notice_clicked.connect(self._notice_clicked)
        self.notice_action = None
        self.click_mode = False          # this dictation was started by clicking the pill
        self.model_lock = threading.Lock()
        self.live_busy = False
        self.live_seen = 0
        self._live_rest_until = 0.0
        self.live_text.connect(self._on_live_text)
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(LIVE_EVERY_MS)
        self.live_timer.timeout.connect(self._live_tick)
        # Typing as you speak (as on Windows): what part of the recording is
        # done (typed, or waiting for its app), as a sample index.
        self.model_timed = None
        self.lt_active = False
        self.target_pid = 0
        self._lt_reset()
        self.live_words.connect(self.on_live_words)
        self.live_piece.connect(self.on_live_piece)
        self.screen_glow = ScreenGlow()      # the glow round the screen's edge
        self.pointer_badge = None            # "No text box" by the pointer
        self.fx_demo_until = 0.0
        self.fx_count = 0
        self.tray_levels = deque([0.0] * 4, maxlen=4)
        self.fx_timer = QTimer(self)
        self.fx_timer.setInterval(33)
        self.fx_timer.timeout.connect(self._fx_tick)
        self.lt_pacer = QTimer(self)         # types the waiting words a little at a time
        self.lt_pacer.setInterval(30)
        self.lt_pacer.timeout.connect(self._pace_tick)
        self._through = None             # is the pop-up letting clicks through?
        self.click_timer = QTimer(self)  # Mac: clicks pass the pop-up's see-through part
        self.click_timer.setInterval(80)
        self.click_timer.timeout.connect(self._update_click_through)
        self.click_timer.start()
        self.hotkey = HotkeyWatch(self._key_down, self._key_up, self._key_spoiled)
        self._tap_first = self._tap_stop = False   # press-to-start-and-stop mode
        self.hotkey.set_key(HOTKEY)
        self.hotkey.set_action(ACTION_HOTKEY)
        self.hotkey.set_paste(PASTE_HOTKEY)
        self.hotkey.on_paste = self.on_paste_again
        self.last_text, self.last_time = "", 0.0
        self.do_action = False           # this dictation ends with the second hotkey's key
        self.after_ticket = 0
        self.mic_asked = False
        self.keyboard_asked = False
        self.perm_checks = 0
        self.settings_window = None
        self.box_state = "unknown"     # the latest text box answer
        self.box_no_count = 0
        self.model_ready.connect(self._on_model_ready)
        self.result.connect(self._on_result)
        self.typed.connect(self._on_typed)
        self.after_ready.connect(self._press_after)
        self._build_tray()
        self.watchdog = QTimer(self)
        self.watchdog.setInterval(250)
        self.watchdog.timeout.connect(self._watch)
        self.watchdog.start()
        self.box_timer = QTimer(self)
        self.box_timer.setInterval(400)
        self.box_timer.timeout.connect(self._check_box)
        self.trust_timer = QTimer(self)      # waiting for the permission
        self.trust_timer.setInterval(2000)
        self.trust_timer.timeout.connect(self._ask_fresh)
        self.perm_timer = QTimer(self)
        self.perm_timer.setInterval(1500)
        self.perm_timer.timeout.connect(self._check_permissions)
        self.step_timer = QTimer(self)       # the idle pill and full-screen apps
        self.step_timer.setInterval(3000)
        self.step_timer.timeout.connect(self._step_aside_check)
        self.step_timer.start()

    # menu bar ------------------------------------------------------------
    def _build_tray(self):
        self.tray = QSystemTrayIcon(menu_bar_icon(dim=True))
        self.tray.setToolTip(APP_TITLE)
        m = QMenu()
        self.status_action = m.addAction("Loading the speech model…")
        self.status_action.setEnabled(False)
        m.addSeparator()
        m.addAction("Settings…", self.open_settings)
        m.addAction("Setup and permissions…", self.open_setup)
        m.addSeparator()
        m.addAction(f"About {APP_TITLE}", self.show_about)
        m.addAction(f"Restart {APP_TITLE}", restart_app)
        m.addAction(f"Quit {APP_TITLE}", self.quit)
        self.menu = m
        self.tray.setContextMenu(m)
        self.tray.show()

    def open_settings(self, tab=None):
        """One Settings window at a time; brought to the front if open."""
        show_in_dock(True)
        bring_to_front()
        if self.settings_window is None:
            self.settings_window = SettingsWindow(self)
            self.settings_window.finished.connect(self._settings_closed)
        if tab:
            self.settings_window.show_tab(tab)
        self.settings_window.show()
        self.settings_window.raise_()
        self.settings_window.activateWindow()

    def _settings_closed(self, _result=0):
        self.settings_window = None
        self._dock_check()

    def _dock_check(self):
        """Out of the Dock again once no window of ours is open."""
        if self.settings_window is None and getattr(self, "setup_window", None) is None:
            show_in_dock(False)

    def key_name(self):
        return HOTKEYS[HOTKEY][2]

    def update_status(self):
        if self.model_error:
            text = "Speech model not found"
        elif self.model is None:
            text = "Loading the speech model…"
        elif not self.hotkey.port:
            text = "Needs permission to watch the key and type"
        else:
            text = ("Ready: " + how_words(self.key_name())).replace(", let go", "")
        self.status_action.setText(text)
        self.tray.setIcon(menu_bar_icon(dim=self.model is None or not self.hotkey.port))
        # The pill's light: amber while the model loads; red with no usable
        # model or no microphone at all; otherwise the accent colour.
        if self.model_error or not input_devices():
            status = "problem"
        elif self.model is None or not self.hotkey.port:
            status = "busy"          # loading, or setup not finished (permission)
        else:
            status = "ok"
        if status != self.overlay.status:
            self.overlay.status = status
            self.overlay.update()

    def set_hold_to_talk(self, on):
        """Hold the key while speaking, or tap to start and tap to stop."""
        set_option("HOLD_TO_TALK", "hold_to_talk", bool(on))
        self._tap_first = self._tap_stop = False
        self.refresh_popup()

    def set_hotkey(self, key):
        set_option("HOTKEY", "hotkey", key)
        self.hotkey.set_key(key)
        if ACTION_HOTKEY == key:                 # the same key can't do both
            set_option("ACTION_HOTKEY", "action_hotkey", "")
            self.hotkey.set_action("")
        if PASTE_HOTKEY == key:
            set_option("PASTE_HOTKEY", "paste_hotkey", "")
            self.hotkey.set_paste("")
        self.update_status()
        self.refresh_popup()

    # start-up ------------------------------------------------------------
    def start(self):
        self.update_status()
        trusted = can_control_keyboard()
        if not trusted:
            # Not set up yet: the pill says so (never shows the hotkey as if it
            # worked), and clicking it opens the explanation again.
            self.show_setup_notice()
            self.trust_timer.start()
        elif ALWAYS_SHOW:
            self.overlay.show_idle()
        log.info("Accessibility %s, microphone status %d", "on" if trusted else "off",
                 mic_permission())
        if trusted and self.hotkey.install():
            self.update_status()
        elif trusted:
            log.warning("Accessibility on, but the key watch could not start")
        if not self.hotkey.port or mic_permission() != MIC_OK or not _config.get("welcomed"):
            self.open_setup()                    # first, before the busy model loading
        # The model loads in the background; started a moment later, so the
        # windows above are drawn first (loading keeps Python busy for a while).
        if network_is_open():                    # a download agreed to at start
            self.downloading = True
            self.overlay.show_message(self.DOWNLOADING, ms=None)
            self.overlay.progress = 0.0
            self.notice_action = self.download_clicked
            self.download_timer.start()
        QTimer.singleShot(250, self.begin_load)
        if CHECK_APP_UPDATES:
            # Switched on (after its "This application will go online" window):
            # a little after start-up, so it never slows the start. Says
            # something only if there is a new version.
            QTimer.singleShot(10000, lambda: run_app_update_check(
                None, manual=False, tray=self.tray))

    def _load_model(self):
        t0 = time.perf_counter()
        try:
            release = current_release()
            if release is None:
                raise RuntimeError("no download is known for this model")
            if network_is_open():
                # A download the user agreed to. The files go into a separate
                # folder and are checked; only then do they replace anything.
                try:
                    if matching_release() is not release:
                        download_release(release, model_dir())
                    if not helper_ok():
                        try:
                            download_release(HELPER_RELEASE, helper_dir())
                        except Exception:
                            log.exception("speech detector download")   # works without
                except Exception:
                    if matching_release() is None:
                        raise                    # nothing usable here: this try failed
                    log.exception("download did not finish; using the model on this Mac")
                close_network()                  # done: the door shuts again at once
                log.info("network closed again (download done)")
            using = matching_release()
            if using is None:
                if local_model_dir():
                    # Files are here but are not the official ones: refused.
                    self.model_suspect.emit(", ".join(model_mismatches()))
                    return
                raise FileNotFoundError("the speech model's files are not on this Mac")
            import onnxruntime as ort
            import onnx_asr
            opts = ort.SessionOptions()
            opts.enable_cpu_mem_arena = False       # gives memory back after use
            opts.intra_op_num_threads = min(4, os.cpu_count() or 4)
            opts.inter_op_num_threads = 1
            model = onnx_asr.load_model(MODEL, model_dir(), quantization="int8",
                                        sess_options=opts, providers=["CPUExecutionProvider"])
            model.recognize(np.zeros(SAMPLE_RATE, np.float32))      # warm up
            if helper_ok():
                self.vad = onnx_asr.load_vad("silero", helper_dir(), sess_options=opts,
                                             providers=["CPUExecutionProvider"])
            else:
                log.warning("speech detector missing; silence is not filtered")
            try:
                wrapped = make_preview_stoppable(model)
            except Exception:
                wrapped = 0
            log.info("preview reading can be stopped: %d parts", wrapped)
            self.model = model
            self.model_error = ""
            self.load_seconds = time.perf_counter() - t0
            log.info("model %s loaded in %.1fs", using["tag"], self.load_seconds)
            self.model_ready.emit(True, "")
        except Exception as e:
            log.warning("model not loaded: %s", str(e).replace(HOME, "~"))
            self.model_ready.emit(False, str(e))
        finally:
            self.model_event.set()

    def begin_load(self):
        """Start loading the model (downloading it first if that was agreed)."""
        self.load_failed_at = None
        self.model_event.clear()
        self.load_thread = threading.Thread(target=self._load_model, daemon=True)
        self.load_thread.start()

    DOWNLOADING = "Downloading the speech model"
    STUCK = "The download is not moving  \u00b7  click for help"
    BLOCKED = "The download seems blocked  \u00b7  click to try again"
    NO_MODEL = "No speech model  \u00b7  click to download"
    GIVE_UP_AFTER = 3                            # failed attempts before stopping
    STUCK_AFTER = 20.0                           # seconds with nothing new arriving
    RETRY_AFTER = 15.0                           # seconds between attempts

    def download_words(self):
        if self.download_blocked:
            return self.BLOCKED
        if self.download_stuck:
            return self.STUCK
        total = model_total_bytes()
        if self.download_got <= 0:
            return self.DOWNLOADING
        return "%s  \u00b7  %s of %s" % (self.DOWNLOADING, size_words(self.download_got),
                                         size_words(max(total, self.download_got)))

    def _download_tick(self):
        """Twice a second while downloading: how much has arrived (the size of
        the files on disk), shown on the pill's download card."""
        if not self.downloading or self.model is not None:
            self.download_timer.stop()
            self.downloading = False
            self.overlay.progress = None
            return
        try:
            got = model_bytes_on_disk()
        except Exception:
            return
        if got != self.download_got:
            self.download_got, self.download_moved = got, time.monotonic()
            self.download_stuck = False
        elif time.monotonic() - self.download_moved > self.STUCK_AFTER:
            self.download_stuck = True
        if (self.load_failed_at is not None and not self.download_blocked
                and time.monotonic() - self.load_failed_at > self.RETRY_AFTER
                and (self.load_thread is None or not self.load_thread.is_alive())):
            log.info("trying the download again")
            self.begin_load()                    # it really does keep trying
        if self.recording:
            return
        total = model_total_bytes()
        mine = (self.overlay.mode == "message" and (
            self.overlay.message.startswith(self.DOWNLOADING)
            or self.overlay.message in (self.STUCK, self.BLOCKED)))
        if not mine:
            self.overlay.show_message(self.download_words(), ms=None)
            self.notice_action = self.download_clicked
        self.overlay.message = self.download_words()
        self.overlay.progress = min(0.99, self.download_got / float(total)) if total else None
        self.overlay.update()

    def download_clicked(self):
        """The download card was clicked: help, or another try."""
        self.notice_action = self.download_clicked     # stays clickable
        if self.download_blocked or self.download_stuck:
            self.retry_download()

    def retry_download(self):
        if not self.downloading:
            return
        if self.load_thread is not None and self.load_thread.is_alive() \
                and not self.download_stuck:
            return                               # data is arriving: nothing to retry
        self.download_moved = time.monotonic()
        self.download_stuck = False
        if self.download_blocked:
            # Another go asked for after it stopped trying: the download was
            # agreed to at the start of this run, so it may open again.
            self.download_blocked = False
            self.download_failures = 0
            open_network("another try at the agreed download")
        if self.load_thread is None or not self.load_thread.is_alive():
            self.begin_load()
        else:
            save_setting("download_yes_once", MODEL)   # already agreed: not asked again
            restart_app()                        # a stuck connection: start fresh

    def _on_model_ready(self, ok, err):
        if not ok and self.downloading:
            # A download attempt gave up. Another follows shortly, a few
            # times; then it stops (and the network shuts) until asked again.
            self.load_failed_at = time.monotonic()
            self.download_failures += 1
            if self.download_failures >= self.GIVE_UP_AFTER:
                self.download_blocked = True
                close_network()
                log.info("download failed %d times: stopped, network closed",
                         self.download_failures)
            self.update_status()
            return
        if not ok:
            close_network()
            self.model_error = err or "not loaded"
            self.update_status()
            if not local_model_dir():
                self.notice(self.NO_MODEL, stays=True, action=self.offer_download)
            else:
                self.notice("The speech model could not be loaded (see the log)", ms=8000)
            return
        self.downloading = False
        self.overlay.progress = None
        self.update_status()
        if self.hotkey.port and not self.recording and self.setup_complete():
            self.overlay.show_message(pill_text() if SHOW_HOTKEY_HINT else "Ready",
                                      ms=1500, pulse=True)
            self.maybe_pill_tip()
        elif not self.setup_complete() and not self.recording:
            self.show_setup_notice()

    def offer_download(self):
        """No model here (none was downloaded): download it, after asking."""
        if dialog(f"{APP_TITLE}: download the speech model",
                  download_question_words(), buttons=("Download and restart", "Cancel"),
                  headline="This application will go online") == "Download and restart":
            save_setting("download_yes_once", MODEL)
            restart_app()
        elif not local_model_dir():
            self.notice(self.NO_MODEL, stays=True, action=self.offer_download)

    def on_model_suspect(self, names):
        """The model's files are not the official ones: never loaded. Download
        them again, or quit."""
        self.on_cancel()
        again = dialog(
            f"{APP_TITLE}: speech model does not match",
            f"These files are not exactly the official ones that {APP_TITLE} checks them "
            f"against:\n\n{names}\n\nThey may be damaged, only partly downloaded, or "
            f"replaced by something else, so {APP_TITLE} will not use them.\n\n"
            f"Download again deletes them and restarts. This application will go online "
            f"once, to github.com (a third-party website that we do not run or control), "
            f"to download fresh copies from this project's model page, and checks every "
            f"file before using it.",
            buttons=("Download again", f"Quit {APP_TITLE}"), icon="warning",
            headline="The speech model's files do not match")
        if again == "Download again":
            forget_model()
            save_setting("download_yes_once", MODEL)
            restart_app()
        else:
            self.quit()

    def unload_model(self):
        """Let go of the speech model (it is about to be removed). Returns False
        while it is still loading or downloading."""
        if self.model is None and (self.load_thread is not None and self.load_thread.is_alive()):
            return False
        self.on_cancel()
        with self.model_lock:
            self.model = None
            self.vad = None
        self.model_error = "removed"
        import gc
        gc.collect()
        self.update_status()
        return True

    # permissions ---------------------------------------------------------
    def open_setup(self):
        """The setup window (one at a time), brought to the front."""
        show_in_dock(True)
        bring_to_front()
        if getattr(self, "setup_window", None) is None:
            self.setup_window = SetupWindow(self)
            self.setup_window.finished.connect(self._setup_closed)
        self.setup_window.refresh()
        self.setup_window.show()
        self.setup_window.raise_()
        self.setup_window.activateWindow()

    def _setup_closed(self, _result=0):
        self.setup_window = None
        self._dock_check()
        if self.setup_complete() and not self.recording and ALWAYS_SHOW:
            self.overlay.show_idle()

    def explain_keyboard_permission(self):
        if can_control_keyboard():
            self._check_permissions()
            return
        who = started_by()
        extra = (f"\n\nWhile testing, the list shows “{who}” instead of {APP_TITLE}, because "
                 f"{APP_TITLE} was started from {who}. Switch on “{who}”.") if who else ""
        go = dialog(
            "Allow typing and the hotkey",
            f"{APP_TITLE} types your words into other apps, and notices when you hold "
            f"{self.key_name()}. macOS calls this permission “Accessibility”.\n\n"
            f"Next, macOS will show its own message. Click “Open System Settings” and switch "
            f"on {APP_TITLE} in the list.{extra}\n\n"
            f"{APP_TITLE} only uses this to notice the key and type what you said. "
            f"It does not record or save your typing.",
            buttons=("Continue", f"Quit {APP_TITLE}"))
        if go != "Continue":
            # Without this permission leetsay can't work at all: "Quit" (or
            # closing the window) quits it. It asks again next time.
            log.info("typing permission declined: quit")
            self.quit()
            return
        self.keyboard_asked = True
        if not ask_keyboard_permission():
            open_settings_pane("accessibility")
        self.perm_checks = 0
        self.perm_timer.start()

    def _check_permissions(self):
        if self.perm_timer.isActive():
            self.perm_checks += 1
            # macOS often gives the permission only to a fresh start: after
            # 15 s, say to restart. Never start the key watch before the
            # permission reads on: a watch started too early is given no keys
            # by macOS, even once the permission arrives (seen in 0.0.6).
            if self.perm_checks == 10 and not can_control_keyboard():
                log.info("Accessibility still off after 15 s of waiting")
                self.notice(f"Switched it on? Click here to finish",
                            stays=True, action=self.permission_help)
                self.status_action.setText(f"Switched on Accessibility? Restart {APP_TITLE}")
                return
        if can_control_keyboard():
            if self.hotkey.install():
                self.perm_timer.stop()
                self.update_status()
                self.overlay.show_message(pill_text() if SHOW_HOTKEY_HINT else "Ready",
                                          ms=1800, pulse=True)
            elif not self.hotkey.port and self.perm_timer.isActive():
                # Allowed, but macOS sometimes wants the app started again.
                self.perm_timer.stop()
                self.update_status()
                self.notice(f"Allowed. Click here to restart {APP_TITLE}",
                            stays=True, action=restart_app)
        self.update_status()

    def permission_help(self):
        """After the switch was (maybe) turned on: restart, or the one fix
        for a switch that is on but doesn't count (an older copy's entry)."""
        if can_control_keyboard():
            restart_app()
            return
        who = started_by() or APP_TITLE
        answer = dialog(
            "Finish setting up",
            f"Switched {who} on in the list? Then {APP_TITLE} only needs a restart.\n\n"
            f"If {who} was already switched on, macOS is remembering an older copy of "
            f"{APP_TITLE}, and that switch doesn't count for this one. To fix it:\n"
            f"1.  Click “Open Accessibility settings”.\n"
            f"2.  Click {who} in the list once, then the – (minus) button below the list.\n"
            f"3.  Click the + (plus) button, choose Applications › {APP_TITLE}, and click "
            f"Open. Make sure its switch is on.\n"
            f"4.  Click “Restart {APP_TITLE}” here.",
            buttons=(f"Restart {APP_TITLE}", "Open Accessibility settings"),
            headline="Not allowed yet")
        if answer == f"Restart {APP_TITLE}":
            restart_app()
        elif answer == "Open Accessibility settings":
            open_settings_pane("accessibility")
            self.notice(f"Switched it on? Click here to finish", stays=True,
                        action=self.permission_help)
        else:
            self.notice(f"Switched it on? Click here to finish", stays=True,
                        action=self.permission_help)

    def show_permissions(self):
        ok = "✓ allowed"
        no = "✗ not allowed"
        mic = mic_permission()
        mic_text = {MIC_OK: ok, MIC_UNKNOWN: "not asked yet (asked the first time you dictate)"}.get(mic, no)
        kb = can_control_keyboard()
        who = started_by()
        extra = f"\n\nWhile testing, these permissions belong to “{who}”." if who else ""
        choice = dialog(
            "Permissions",
            f"Typing and the hotkey (Accessibility): {ok if kb else no}\n"
            f"Microphone: {mic_text}{extra}",
            buttons=("Open Accessibility settings", "Open Microphone settings", "Close"))
        if choice == "Open Accessibility settings":
            if not kb:
                ask_keyboard_permission()
                self.perm_checks = 0
                self.perm_timer.start()
            open_settings_pane("accessibility")
        elif choice == "Open Microphone settings":
            open_settings_pane("microphone")

    def explain_mic_permission(self):
        go = dialog(
            "Allow the microphone",
            f"To hear you, {APP_TITLE} needs the microphone. It is switched on "
            f"{mic_on_words(self.key_name())}, and the sound is never saved or sent anywhere.\n\n"
            f"Next, macOS will ask about the microphone. Click “Allow”.",
            buttons=("Continue", "Not now"))
        if go != "Continue":
            return
        # Opening the microphone for a moment is what makes macOS ask.
        try:
            self.recorder.start()
        except Exception:
            log.exception("mic prompt")
        QTimer.singleShot(400, self.recorder.close)
        self.mic_asked = True

    def mic_blocked(self):
        choice = dialog(
            "Microphone is switched off",
            f"macOS is not letting {APP_TITLE} use the microphone.\n\n"
            f"Open System Settings › Privacy & Security › Microphone and switch it on"
            + (f" for “{started_by()}”." if started_by() else f" for {APP_TITLE}."),
            buttons=("Open Microphone settings", "Close"), icon="warning")
        if choice == "Open Microphone settings":
            open_settings_pane("microphone")

    # dictation -----------------------------------------------------------
    def on_press_mic_check_only(self):
        """Microphone not allowed yet: the setup window (step 2) instead of a
        pop-up. Returns True if the microphone may be used now."""
        mic = mic_permission()
        if (mic == MIC_UNKNOWN and not self.mic_asked) or mic in (MIC_DENIED, MIC_RESTRICTED):
            self.open_setup()
            return False
        return True

    PILL_TIP = "Right-click me for Settings"
    # Short: people click the pill anyway; it opens the setup window.
    # One word for the whole setup; a click brings the setup window
    # to the front, and that window says what is left to do.
    SETUP_NEEDED = "Setup"
    SETUP_MIC = "Setup"

    def setup_complete(self):
        """Typing allowed and the microphone allowed: only then can it dictate."""
        return bool(self.hotkey.port) and mic_permission() == MIC_OK

    def show_setup_notice(self, pulse=False):
        """Stays until setup is done: no × (it is the one thing to do)."""
        text = (self.SETUP_NEEDED if not self.hotkey.port
                else self.SETUP_MIC)
        self.overlay.show_message(text, ms=None, pulse=pulse)
        self.overlay.closable = False
        self.notice_action = self.open_setup

    def _ask_fresh(self):
        """Every 2 s while waiting: is typing allowed now? If so, restart by
        itself (a new user can't know macOS wants that). Asked quietly in
        this process: AXIsProcessTrusted never shows macOS's question.
        (0.0.13-0.0.23 started a helper copy of leetsay for this every 2 s;
        after a Deny, each new copy made macOS ask again, over and over.)"""
        if self.hotkey.port:
            self.trust_timer.stop()
            return
        if can_control_keyboard():
            self._fresh_answer(True)

    def _fresh_answer(self, allowed):
        if allowed and not self.hotkey.port and self.trust_timer.isActive():
            self.trust_timer.stop()
            log.info("Accessibility now on: restarting")
            self.overlay.show_message("Allowed. Starting again\u2026", ms=None, pulse=True)
            QTimer.singleShot(1500, restart_app)

    def maybe_pill_tip(self):
        """Once ever: the pill itself says where Settings are."""
        if _config.get("pill_tip_seen") or not ALWAYS_SHOW:
            return

        def show():
            if self.recording or _config.get("pill_tip_seen"):
                return                           # busy: another time
            save_setting("pill_tip_seen", True)
            self.overlay.show_message(self.PILL_TIP, ms=4500, pulse=True)
        QTimer.singleShot(2600, show)            # after the hotkey's own flash

    def _idle(self):
        return not self.recording and self.overlay.mode != "welcome"

    def preview_popup(self):
        if self._idle():
            self.overlay.preview()

    def preview_pill(self):
        """After a change to the small pill: show the pill itself."""
        if not self._idle():
            return
        if ALWAYS_SHOW and self.overlay.isVisible() and self.overlay.mode == "idle":
            self.overlay.update()
            return
        self.overlay.show_message(pill_text() if SHOW_HOTKEY_HINT else "", ms=2500)

    def refresh_popup(self):
        """After a settings change: resize, and show or hide the idle pill."""
        self.overlay.apply_size()
        if self.recording:
            return
        mode, visible = self.overlay.mode, self.overlay.isVisible()
        if ALWAYS_SHOW and (not visible or mode == "idle"):
            self.overlay.show_idle()
        elif not ALWAYS_SHOW and visible and mode == "idle":
            self.overlay.dismiss(force=True)

    def move_popup(self):
        if self._idle():
            self.overlay.invite_drag()

    def resize_popup(self):
        if self._idle():
            self.overlay.preview(ms=12000, words="Drag either edge")

    def notice(self, text, ms=1800, stays=False, action=None):
        """A short notice on the pill. stays=True: it stays until it is dealt
        with, with a × to close it; clicking the notice itself does `action`."""
        self.overlay.show_message(text, ms=None if stays else ms)
        self.overlay.closable = bool(stays)
        self.notice_action = action
        self.overlay.update()

    def _notice_clicked(self):
        action, self.notice_action = self.notice_action, None
        if action is not None:
            action()

    def on_pill_clicked(self):
        """A click on the pill starts a dictation; a click on the card ends it."""
        if self.recording or self.model_error:
            return
        if not self.setup_complete():        # setup not finished: the setup window
            self.open_setup()
            return
        self.click_mode = True
        self.on_press()

    # -- the hotkey: held, or tapped to start and tapped again to stop --------------
    def _key_down(self):
        if HOLD_TO_TALK or not self.recording:
            self._tap_first = not HOLD_TO_TALK
            self.on_press()
        else:
            self._tap_stop = True        # the next tap: finishes when it is let go

    def _key_up(self):
        if HOLD_TO_TALK:
            self.on_release()
        elif self._tap_stop:
            self._tap_stop = False
            if self.recording:
                self.on_release()
        elif self._tap_first:
            self._tap_first = False      # the starting tap let go: keep listening

    def _key_spoiled(self):
        """Another key with the hotkey (⌥E): a shortcut, not a dictation."""
        if not HOLD_TO_TALK and self.recording and not self._tap_first:
            self._tap_stop = False       # a shortcut while listening: keep listening
            return
        self._tap_first = self._tap_stop = False
        self.on_cancel()

    def on_press(self):
        if self.recording:
            return
        busy = getattr(self, "reading_since", None)
        if busy is not None and time.monotonic() - busy < 20:
            # The last dictation is still being read: one at a time, or its
            # text (and typing as you speak) would mix with the new one.
            self.overlay.show_message("Still typing the last one\u2026", ms=1200)
            return
        click = self.click_mode
        self.click_mode = False
        if mic_permission() != MIC_OK:
            # No microphone yet: nothing is recorded; the setup window instead
            # (a dictation of silence was confusing).
            self.hotkey.held = False
            self.open_setup()
            return
        if self.model is None:
            # Not ready to read speech yet: nothing is recorded. (0.0.18 held
            # dictations made during the download and typed them out half a
            # minute later, into whatever was in front then.)
            self.hotkey.held = False
            if self.downloading:
                self.overlay.pulse_started = time.monotonic()   # the card says why
                self.overlay.timer.start()
                self.overlay.update()
            elif self.model_error:
                self.notice(self.NO_MODEL, stays=True, action=self.offer_download)
            else:
                self.overlay.show_message("Still loading the speech model…", ms=2000)
            return
        try:
            self.recorder.start()
        except Exception:
            log.exception("microphone start")
            self.notice(Overlay.NO_MIC, ms=4000,
                        action=lambda: open_settings_pane("microphone"))
            return
        self.recording = True
        self.clicked_start = click
        play_sound("start")
        self.do_action = bool(self.hotkey.via_action and not click and ACTION_HOTKEY)
        self.box_no_count = 0
        self.live_seen = 0
        self.live_session = getattr(self, "live_session", 0) + 1
        if SHOW_POPUP:
            name, path = front_app() if (SHOW_APP_ICON or SHOW_APP_NAME or GLOW_FROM_APP) \
                else ("", "")
            self.overlay.show_recording(name, path)
            self.overlay.click_started = click
            self.overlay.box_missing = False
        # Typing as you speak needs the model's own 16 kHz (a microphone that
        # only gives 48 kHz is read the usual way, all at once).
        self.lt_active = LIVE_TYPE and self.recorder.rate == SAMPLE_RATE
        self.target_pid = front_pid()
        self.after_ticket += 1                   # a key still waiting is called off
        self._lt_reset()
        self._start_effects()
        if TEXTBOX_ONLY or self.lt_active:
            self.box_timer.setInterval(250 if self.lt_active else 400)
            self._check_box()
            self.box_timer.start()
        self.live_timer.setInterval(120 if self.lt_active else LIVE_EVERY_MS)
        if (LIVE_PREVIEW and SHOW_POPUP) or self.lt_active:
            self.live_timer.start()

    def _check_box(self):
        """While dictating: say in time if the words would have nowhere to go.
        A "no" must be seen twice in a row (a click can briefly move the focus)."""
        if not self.recording:
            self.box_timer.stop()
            return
        state = focused_text_box()
        self.lt_box = (state, time.monotonic())
        if not TEXTBOX_ONLY:                     # only asked for typing as you speak
            self.overlay.box_missing = ("Password field: nothing will be typed"
                                        if state == "password" else False)
            return
        was = self.overlay.box_missing
        self.box_no_count = self.box_no_count + 1 if state == "no" else 0
        if state == "password":
            self.overlay.box_missing = "Password field: nothing will be typed"
        else:
            self.overlay.box_missing = self.box_no_count >= 2
        if was and not self.overlay.box_missing and self.lt_active:
            self._show_typed(self.live_session, [])   # the card: as it is in your app
        self._pointer_hint(bool(self.overlay.box_missing) and self.recording)

    def _pointer_hint(self, show):
        """The "No text box" tag by the mouse pointer (on by default)."""
        if show and POINTER_HINT:
            if self.pointer_badge is None:
                self.pointer_badge = PointerBadge()
            self.pointer_badge.appear()
        elif self.pointer_badge is not None:
            self.pointer_badge.vanish()

    def demo_screen_glow(self):
        """From Settings: show the screen glow for a moment (nothing records)."""
        if not self.recording:
            self.fx_demo_until = time.monotonic() + 3.0
            self._start_effects(demo=True)

    def _start_effects(self, demo=False):
        """The extras: a glow round the screen, a moving menu bar icon. They
        may never get in the way of dictating, so errors are only logged."""
        try:
            if not demo:
                self.fx_demo_until = 0.0
            if SCREEN_GLOW:
                colour = glow_base()
                tint = getattr(self.overlay, "app_colour", None)
                if GLOW_FROM_APP and tint is not None and not demo:
                    colour = QtGui.QColor(tint)
                spot = self.overlay.frameGeometry().center()
                screen = (QtGui.QGuiApplication.screenAt(spot)
                          or QtGui.QGuiApplication.primaryScreen())
                if SCREEN_GLOW_SCREENS == "all":
                    areas = [sc.geometry() for sc in QtGui.QGuiApplication.screens()]
                elif SCREEN_GLOW_SCREENS == "main":
                    areas = [QtGui.QGuiApplication.primaryScreen().geometry()]
                else:
                    areas = [screen.geometry()]
                self.screen_glow.start(colour, areas)
            if SCREEN_GLOW or TRAY_LIVE:
                self.fx_timer.start()
        except Exception:
            log.exception("effects")

    def _fx_tick(self):
        try:
            active = self.recording
            level = float(getattr(self.recorder, "level", 0.0)) if active else 0.0
            if not active and time.monotonic() < self.fx_demo_until:
                alive = self.screen_glow.step(0.55, True)        # the Settings demo
            else:
                # Nothing can be typed right now: the glow holds still.
                still = bool(active and self.overlay.box_missing)
                alive = self.screen_glow.step(level, active, still)
            if active and TRAY_LIVE:
                alive = True
                self.fx_count += 1
                if self.fx_count % 3 == 0:               # about ten times a second
                    self.tray_levels.appendleft(level)
                    self.tray.setIcon(menu_bar_icon(levels=list(self.tray_levels)))
            elif TRAY_LIVE and self.fx_count:
                self.fx_count = 0
                self.update_status()                     # the still icon again
            if not alive:
                self.fx_timer.stop()
        except Exception:
            log.exception("effects")
            self.fx_timer.stop()

    def on_release(self):
        if not self.recording:
            return
        self._pointer_hint(False)
        self.recording = False
        self.live_timer.stop()
        if not self.lt_active:
            self._stop_preview()         # (type as you speak keeps its own reading)
        held = time.monotonic() - self.recorder.started
        audio, rate = self.recorder.stop()
        self.box_timer.stop()
        self.lt_pacer.stop()
        if held >= MIN_HOLD:
            play_sound("finish")
        if held < MIN_HOLD:
            self._lt_end()
            # (A quick tap types the last dictation again only when the key is
            # held to dictate: in press-to-start mode a tap starts one.)
            again = self.last_dictation() if HOLD_TO_TALK and not self.clicked_start else ""
            if again:                    # "missed text safety": type it once more
                self.overlay.show_message("Typed again", ms=1300)
                self.target_pid = front_pid()
                QTimer.singleShot(60, lambda: self._deliver(again, "", remember=False))
            else:
                self.overlay.dismiss()
            return
        if audio.size == 0 or float(np.max(np.abs(audio))) < MIC_SILENT_PEAK:
            self._lt_end()
            self.notice(Overlay.NO_SOUND, ms=2600,
                        action=lambda: open_settings_pane("microphone"))
            return
        skip = None
        if self.lt_active and self.lt_commit:
            # Typing as you speak: only the piece since the last pause is left
            # to read, with a little of what came before.
            whole, rest = audio, audio[self.lt_commit:]
            if len(rest) < rate * 0.3 or not holds_speech(rest, whole, rate):
                self.overlay.dismiss()
                QTimer.singleShot(0, lambda: self._lt_finish(""))
                return
            first = max(0, self.lt_commit - int(self.LT_CONTEXT * rate))
            audio = whole[first:]
            skip = (self.lt_commit - first) / float(rate)
        self.seq += 1
        if self.model is None:
            self.overlay.show_message("Loading the speech model\u2026", ms=None)
        elif SHOW_POPUP:
            self.overlay.show_transcribing()
        quiet = float(np.max(np.abs(audio))) < MIC_QUIET_PEAK
        self.reading_since = time.monotonic()    # until its text is in (see on_press)
        threading.Thread(target=self._transcribe, args=(self.seq, audio, rate, quiet, skip),
                         daemon=True).start()
        if not self.lt_active:
            seq = self.seq
            QTimer.singleShot(700, lambda: self._still_working(seq))

    WORKING = "Transcribing\u2026"

    def _still_working(self, seq):
        """A longer dictation takes a moment to turn into text: after 0.7 s the
        card becomes a small "Transcribing…" pill until the text is typed, so
        it doesn't look frozen (as Windows)."""
        if (seq == self.seq and self.reading_since is not None and SHOW_POPUP
                and self.overlay.mode == "transcribing"):
            self.overlay.show_message(self.WORKING, ms=None)

    def on_cancel(self):
        self._pointer_hint(False)
        if self.recording:
            self.recording = False
            self.live_timer.stop()
            self.box_timer.stop()
            self._lt_end()                       # what was typed already stays
            self.recorder.close()
            self.overlay.dismiss()

    # -- your words in the pop-up while you speak (as on Windows) -----------------
    def _live_tick(self):
        if not self.recording or not (LIVE_PREVIEW or self.lt_active) or self.model is None:
            if not self.recording:
                self.live_timer.stop()
            return
        if self.recorder.peak < MIC_SILENT_PEAK:
            return                       # nothing heard yet: nothing to read
        if self.lt_active:
            self._flush_live()           # back in the right app: catch up
        if self.live_busy or time.monotonic() < self._live_rest_until:
            return                       # the last reading is running, or resting
        if self.lt_active:
            self._live_type_tick()
            return
        total = sum(len(chunk) for chunk in list(self.recorder.chunks))
        if total < self.recorder.rate * 0.6 or total == self.live_seen:
            return
        self.live_seen = total
        audio = self.recorder.recent(LIVE_WINDOW_SECONDS * LIVE_LINES)
        self.live_busy = True
        threading.Thread(target=self._live_run,
                         args=(audio, self.recorder.rate, self.live_session),
                         daemon=True).start()

    def _live_run(self, audio, rate, session):
        stop = None
        try:
            audio = leveled(audio)
            with self.model_lock:
                if not self.recording:
                    return                       # let go meanwhile: the final read is next
                stop = _preview_stop_switch()
                self._live_stop = stop           # flipped when the key is let go
                began = time.monotonic()
                text = str(self.model.recognize(audio, sample_rate=rate))
                done = time.monotonic()
                # Rest as long as it worked: on a small computer this keeps
                # the reading along to about half of the processor's time.
                self._live_rest_until = done + (done - began) * LIVE_REST
            # The same clean-up as the final text (fillers, times, your word
            # replacements), so the card shows what will be typed.
            self.live_text.emit(session, " ".join(clean_words(text.split())))
        except Exception:
            pass                                 # also: stopped because the key was let go
        finally:
            _PREVIEW.stop = None
            if stop is not None and getattr(self, "_live_stop", None) is stop:
                self._live_stop = None
            self.live_busy = False

    def _stop_preview(self):
        """Letting go: a preview pass still running is stopped where it is,
        so the final read doesn't wait for it (it took up to 1.7 s more)."""
        stop = getattr(self, "_live_stop", None)
        if stop is not None:
            try:
                stop.terminate = True
            except Exception:
                pass

    def _on_live_text(self, session, text):
        if session == getattr(self, "live_session", 0) and self.recording and text \
                and LIVE_PREVIEW and self.overlay.mode == "recording":
            text = self._steady_words(session, text)
            if text:
                self.overlay.set_live_text(text)

    @staticmethod
    def _plain_word(word):
        return word.strip(".,!?;:\"'“”‘’").lower()

    def _steady_words(self, session, text):
        """The live words without a last word that is only a guess: each pass
        reads up to the moment it starts, often in the middle of a word, and
        the model then guesses ("process" for "project"). The last word is
        shown once a second pass has heard it too."""
        words = text.split()
        prev = self._live_prev if getattr(self, "_live_prev_session", None) == session else []
        self._live_prev, self._live_prev_session = words, session
        if len(words) > 1 and self._plain_word(words[-1]) not in {
                self._plain_word(w) for w in prev[-3:]}:
            words = words[:-1]
        return " ".join(words)

    # -- typing as you speak (ported from Windows) ---------------------------------
    LT_CONTEXT = 2.0     # seconds of what came before, read along with each piece

    def _lt_reset(self):
        self.lt_commit = 0
        self.lt_index = (0, 0)               # a chunk of the recording and where it starts
        self.lt_done = ""                    # typed so far, this dictation
        self.lt_pending = ""                 # read but not typed yet
        self.lt_counts = [0, 0, 0]           # parts typed, waits, refused
        self.lt_prev = []                    # the last reading of the piece, its words
        self.lt_seg_words = []               # words of this piece typed so far
        self.lt_all = []                     # every word typed, this dictation
        self.lt_held = None                  # punctuation held back at a piece's end
        self.lt_box = ("unknown", 0.0)       # the latest text box answer, and when
        self.lt_credit = 0.0
        self._final_before = ""

    def _lt_forget(self):
        """The words are kept no longer than needed."""
        self.lt_done = self.lt_pending = ""
        self.lt_all, self.lt_prev, self.lt_seg_words = [], [], []
        self.lt_held = None
        self._final_before = ""

    def _lt_end(self):
        if getattr(self, "lt_pacer", None) is not None:
            self.lt_pacer.stop()
        self.lt_active = False
        self._lt_forget()

    def _audio_since(self, start):
        chunks = list(self.recorder.chunks)
        i, pos = self.lt_index
        if pos > start or i > len(chunks):
            i, pos = 0, 0
        while i < len(chunks) and pos + len(chunks[i]) <= start:
            pos += len(chunks[i])
            i += 1
        self.lt_index = (i, pos)
        if i >= len(chunks):
            return np.zeros(0, dtype=np.float32)
        return np.concatenate(chunks[i:])[start - pos:]

    def _live_type_tick(self):
        """The piece being spoken (since the last pause) is read again and
        again, with the last couple of seconds before it. A word is typed once
        two readings in a row agree on it (never the newest word). At a pause
        the piece is read once more to finish it."""
        start = max(0, self.lt_commit - int(self.LT_CONTEXT * SAMPLE_RATE))
        audio = self._audio_since(start)
        lead = self.lt_commit - start            # the part before the piece
        cut = find_pause(audio[lead:], SAMPLE_RATE)
        session = self.live_session
        if cut:
            self.live_busy = True
            threading.Thread(target=self._live_piece_run,
                             args=(audio[:lead + cut], self.lt_commit + cut, session,
                                   self.lt_commit, lead / float(SAMPLE_RATE)),
                             daemon=True).start()
            return
        total = start + len(audio)
        if len(audio) - lead < SAMPLE_RATE * 0.4 or total == self.live_seen:
            return
        self.live_seen = total
        self.live_busy = True
        threading.Thread(target=self._live_read_run,
                         args=(audio, self.lt_commit, session, lead / float(SAMPLE_RATE)),
                         daemon=True).start()

    def _timed_read(self, audio, skip):
        """Read audio, leaving out the words spoken in its first `skip`
        seconds. Returns (the piece's words, the last word of the context).
        Call with model_lock held."""
        if self.model_timed is None:
            self.model_timed = self.model.with_timestamps()
        result = self.model_timed.recognize(audio, sample_rate=SAMPLE_RATE)
        words = []                                   # [text, when it began]
        for token, at in zip(result.tokens, result.timestamps):
            if token.startswith(" ") or not words:
                words.append([token.strip(), float(at)])
            else:
                words[-1][0] += token
        words = [w for w in words if w[0]]
        before = [w for w, at in words if at < skip - 0.04]
        piece = [w for w, at in words if at >= skip - 0.04]
        return " ".join(piece), (before[-1] if before else "")

    def _live_read_run(self, audio, start, session, skip):
        try:
            audio = leveled(audio)
            with self.model_lock:
                began = time.monotonic()
                text, before = self._timed_read(audio, skip)
                done = time.monotonic()
                self._live_rest_until = done + (done - began) * LIVE_REST
            self.live_busy = False
            self.live_words.emit(session, text, start, before)
        except Exception:
            log.exception("type as you speak: reading")
        finally:
            self.live_busy = False

    def _live_piece_run(self, audio, end, session, start, skip):
        try:
            audio = leveled(audio)
            with self.model_lock:
                began = time.monotonic()
                text, before = self._timed_read(audio, skip)
                done = time.monotonic()
                self._live_rest_until = done + (done - began) * LIVE_REST
            self.live_piece.emit(session, text, end, start, before)
        except Exception:
            log.exception("type as you speak: piece")   # the final pass reads it
        finally:
            self.live_busy = False

    @staticmethod
    def _plain(words):
        return ["".join(c for c in w.lower() if c.isalnum() or c == "'") for w in words]

    @staticmethod
    def _end_marks(word):
        i = len(word)
        while i > 0 and word[i - 1] in ".,!?;:\u2026":
            i -= 1
        return word[i:] if i > 0 else ""

    def _after_typed(self, plain):
        """Where, in a new reading, the words not typed yet begin (the start of
        a reading repeats words typed already, sometimes a little differently)."""
        typed = self.lt_seg_words
        if not typed:
            return 0
        import difflib
        near = plain[:len(typed) + 3]
        blocks = [b for b in difflib.SequenceMatcher(None, typed, near, autojunk=False)
                  .get_matching_blocks() if b.size]
        if not blocks:
            return min(len(typed), len(plain))
        last = blocks[-1]
        return min(len(plain), last.b + last.size + (len(typed) - (last.a + last.size)))

    def _compose(self, words, before=None, piece_end=False):
        """The text to type for these new words. The last word's full stop (or
        comma) is held back until the next words show the sentence ended."""
        text = ""
        if self.lt_held is not None:
            text = self.lt_held if before is None else self._end_marks(before)
            first = words[0] if words else ""
            if (not text and first[:1].isupper()
                    and self._plain([first])[0] not in ("i", "i'm", "i've", "i'll", "i'd")):
                text = self.lt_held                # a capital: a new sentence after all
            if not words and before is None:
                self.lt_held = None
                return text
            self.lt_held = None
        if not words:
            return text
        words = list(words)
        if piece_end:
            marks = self._end_marks(words[-1])
            if marks and len(marks) < len(words[-1]):
                words[-1] = words[-1][:-len(marks)]
            else:
                marks = ""
            self.lt_held = marks
        if self.lt_done or self.lt_pending or text:
            text += " "
        self.lt_all += self._plain(words)
        return text + " ".join(words)

    def _queue_words(self, words, before=None, piece_end=False):
        text = self._compose(words, before, piece_end)
        if text:
            self.lt_pending += text
            self._flush_live()

    def on_live_words(self, session, text, start, before=""):
        if session != self.live_session or not self.recording or not self.lt_active:
            return
        if start != self.lt_commit:
            return                               # a reading of a piece already done
        words = clean_words(text.split())
        plain = self._plain(words)
        begin = self._after_typed(plain)
        self._show_typed(session, words[begin:])
        fresh = plain[begin:]
        agreed = 0
        for a, b in zip(fresh, self.lt_prev):
            if a != b:
                break
            agreed += 1
        self.lt_prev = fresh
        upto = begin + min(agreed, len(fresh) - 1)       # never the newest word
        wait = max(0.0, self._live_rest_until - time.monotonic())
        QTimer.singleShot(int(wait * 1000) + 1, self._live_tick)
        if upto > begin:
            self._queue_words(words[begin:upto], words[begin - 1] if begin else (before or None),
                              piece_end=True)
            self.lt_seg_words += plain[begin:upto]

    def on_live_piece(self, session, text, end, start, before=""):
        if session != self.live_session or not self.recording or not self.lt_active:
            return
        if start != self.lt_commit:
            return
        words = clean_words(text.split())
        begin = self._after_typed(self._plain(words))
        self._queue_words(words[begin:], words[begin - 1] if begin else (before or None),
                          piece_end=True)
        self.lt_commit = max(self.lt_commit, end)
        self.lt_prev = []
        self.lt_seg_words = []                   # the next piece starts afresh
        self._show_typed(session, [])

    def _show_typed(self, session, coming):
        """The card shows the text as it is in your app, then the newest words."""
        words = (self.lt_done + self.lt_pending).split() + list(coming)
        if words:
            self._on_live_text(session, " ".join(words[-60:]))

    def _flush_live(self):
        if self.lt_pending and not self.lt_pacer.isActive():
            self.lt_credit = 0.0
            self.lt_pacer.start()

    def _pace_tick(self):
        """The waiting words go in a few letters at a time at an even pace, a
        little faster when more are waiting. Only into the app the dictation
        started in, and only into a text box: otherwise it waits (and is typed
        when you come back, or with the rest when you let go)."""
        if not self.recording or not self.lt_active or not self.lt_pending:
            self.lt_pacer.stop()
            return
        if not self.target_pid or front_pid() != self.target_pid:
            self.lt_counts[1] += 1
            self.lt_pacer.stop()                 # the live tick tries again
            return
        state, at = self.lt_box
        if time.monotonic() - at > 0.6:
            return                               # wait for a fresh answer
        if state == "password" or (TEXTBOX_ONLY and state == "no"):
            self.lt_counts[1] += 1
            self.lt_pacer.stop()
            return
        self.lt_credit += max(len(self.lt_pending) / 6.0, 2.0)
        count = min(len(self.lt_pending), int(self.lt_credit))
        if count < 1:
            return
        self.lt_credit -= count
        part = self.lt_pending[:count]
        self._last_batch = time.monotonic()
        problem = type_text(part)
        self._last_batch = time.monotonic()
        if problem is None:
            self.lt_done += part
            self.lt_pending = self.lt_pending[count:]
            self.lt_counts[0] += 1
        else:
            self.lt_counts[2] += 1
            self.lt_pacer.stop()
            if problem == "secure":
                self.overlay.box_missing = "Password field: nothing will be typed"

    def _lt_finish(self, text):
        """You let go: type what is left, after what was typed already."""
        self.lt_active = False
        self.lt_pacer.stop()
        # Counts only: the log never holds your words or app names.
        log.info("type as you speak: %d bits typed while speaking, %d waits for the "
                 "app or a text box, %d refused", *self.lt_counts)
        typed = self.lt_done
        words = text.split()
        begin = self._after_typed(self._plain(words)) if words else 0
        rest = self._compose(words[begin:], words[begin - 1] if begin
                             else (self._final_before or None))
        rest = self.lt_pending + rest
        self._lt_forget()
        if not rest.strip() and not typed:
            self.overlay.show_message("Didn't catch that", ms=1400)
            return
        after_key = ACTION_KEY if (self.do_action and ACTION_KEY) else AFTER_KEY
        if rest.strip():
            if self.target_pid and front_pid() != self.target_pid:
                # Typing as you speak only ever types into the app you started in.
                if not activate_app(self.target_pid):
                    self.remember((typed + rest).strip())
                    self.overlay.show_message("Back in the other app? The rest wasn't typed",
                                              ms=3000)
                    return
                self.overlay.dismiss()
                QTimer.singleShot(200, lambda: self._deliver(
                    rest + (" " if ADD_SPACE and not after_key else ""), after_key,
                    kept=typed))
                return
            state = focused_text_box() if TEXTBOX_ONLY else "unknown"
            if state == "password":
                self.forget()
                self.overlay.show_message("Not typed: a password field is selected", ms=3500)
                return
            if state == "no":
                self.remember((typed + rest).strip())
                self.overlay.show_message("No text box, so the rest wasn't typed", ms=2500)
                return
        out = rest + (" " if ADD_SPACE and not after_key else "")
        if not out and not after_key:
            self.overlay.dismiss()
            return
        self._deliver(out, after_key, kept=typed)

    def _transcribe(self, seq, audio, rate, quiet, skip=None):
        self.model_event.wait()
        if self.model is None:
            self.result.emit(seq, "", quiet)
            return
        if skip is not None:
            # The rest of a typed-as-you-speak dictation, read with its
            # context: only the words after the context are new.
            try:
                with self.model_lock:
                    text, self._final_before = self._timed_read(leveled(audio), skip)
                text = " ".join(clean_words(text.split()))
            except Exception:
                log.exception("recognition failed")
                text = ""
            self.result.emit(seq, text, False)
            return
        t0 = time.perf_counter()
        found = self.has_speech(audio, rate)
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        decision = speech_decision(found, peak, len(audio) / rate)
        if decision != "read":
            log.info("no speech found in %.1fs of audio (%s; checked in %.0f ms)",
                     len(audio) / rate, decision, (time.perf_counter() - t0) * 1000)
            self.result.emit(seq, "", decision == "quiet")
            return
        if not found:
            log.info("no speech detected in %.1fs of sound: read anyway", len(audio) / rate)
        try:
            # Quiet recordings turned up; a little silence at the end so the
            # last word is not cut short.
            audio = np.concatenate([leveled(audio), np.zeros(int(rate * 0.25), np.float32)])
            with self.model_lock:
                text = clean_text(self.model.recognize(audio, sample_rate=rate).strip())
        except Exception:
            log.exception("recognition failed")
            text = ""
        log.info("read %.1fs of audio in %.2fs (%d characters)",
                 len(audio) / rate, time.perf_counter() - t0, len(text))
        self.result.emit(seq, text, quiet)

    def has_speech(self, audio, rate):
        """True if the speech detector finds any speech (or is not available)."""
        if self.vad is None:
            return True
        try:
            if rate != SAMPLE_RATE:       # the detector works at 16 kHz
                n = int(len(audio) * SAMPLE_RATE / rate)
                audio = np.interp(np.arange(n) * rate / SAMPLE_RATE,
                                  np.arange(len(audio)), audio).astype(np.float32)
            segments = next(self.vad.segment_batch(
                audio[None, :], np.array([len(audio)], np.int64), SAMPLE_RATE))
            return any(True for _ in segments)
        except Exception:
            log.exception("speech detector")
            return True

    def _on_result(self, seq, text, quiet):
        if seq != self.seq:
            return                       # an older dictation's (never mixed in)
        self.reading_since = None
        if self.model is None:
            self.notice("Speech model not found", ms=3000)
            return
        if self.lt_active:
            self._lt_finish(text)
            return
        if not text:
            # Whenever nothing is typed, the pop-up says why.
            if quiet:
                self.overlay.show_message("Can't hear you. Check the mic", ms=3000)
            else:
                self.overlay.show_message("Didn't catch that", ms=1400)
            return
        if TEXTBOX_ONLY:
            state = focused_text_box()       # where the cursor is now
            if state == "password":
                self.overlay.show_message("Not typed: a password field is selected", ms=3500)
                return
            if state == "no":
                self.remember(text)      # kept only with "missed text safety"
                self.overlay.show_message(Overlay.NO_BOX + ": nothing typed" + (
                    "  \u00b7  tap the key to type it" if KEEP_LAST else ""), ms=3500)
                log.info("not typed: no text box selected")
                return
        after_key = ACTION_KEY if (self.do_action and ACTION_KEY) else AFTER_KEY
        if ADD_SPACE and not after_key:
            text += " "                  # so the next dictation doesn't run on
        self._deliver(text, after_key)

    def _step_aside_check(self):
        """While a full-screen app (a game, a video) covers the pill's screen,
        the idle pill fades out, and comes back once it is gone, unless "Show
        it over full-screen apps too" is on. Only the idle pill: a dictation
        card or a notice still shows."""
        o = self.overlay
        if not o.stepped_aside and not (ALWAYS_SHOW and not PILL_OVER_FULLSCREEN
                                        and o.isVisible() and o.mode == "idle"
                                        and o.fade_target > 0):
            return                               # nothing to hide or bring back
        if self.recording or getattr(self, "reading_since", None):
            return
        covered = (ALWAYS_SHOW and not PILL_OVER_FULLSCREEN
                   and fullscreen_app_in_front(o))
        if covered and not o.stepped_aside:
            o.stepped_aside = True
            o.dismiss(force=True)
        elif not covered and o.stepped_aside:
            o.stepped_aside = False
            if ALWAYS_SHOW and (not o.isVisible() or o.fade_target == 0):
                o.show_idle()

    def _back_to_target(self, attempt=1):
        """"Stay in the app I started in": asks macOS to bring the app you
        started in back to the front. False if it can't (the app has quit)."""
        if not self.target_pid or front_pid() == self.target_pid or not RETURN_FOCUS:
            return True
        asked = activate_app(self.target_pid)
        # The log never names the apps you use.
        log.info("another app took the focus during dictation; asked the starting app "
                 "back (try %d)%s", attempt, "" if asked else ": refused")
        return asked

    # -- the last dictation, kept briefly so a missed one isn't lost -------------
    def remember(self, text):
        if not KEEP_LAST:
            self.forget()
            return
        self.last_text = text
        self.last_time = stamp = time.monotonic()
        QTimer.singleShot(int(KEEP_LAST_SECONDS * 1000) + 500,
                          lambda: self.forget(only_if=stamp))

    def forget(self, only_if=None):
        if only_if is None or only_if == self.last_time:
            self.last_text = ""
            self.last_time = 0.0

    def last_dictation(self):
        """The last text if it is still being kept, else ''."""
        if not KEEP_LAST or not self.last_text:
            return ""
        if time.monotonic() - self.last_time > KEEP_LAST_SECONDS:
            self.forget()
            return ""
        return self.last_text

    def on_paste_again(self):
        """The paste key: put the last dictation in once more."""
        if self.recording:
            return
        again = self.last_dictation()
        if again:
            self.overlay.show_message("Typed again", ms=1300)
            self.target_pid = front_pid()
            QTimer.singleShot(60, lambda: self._deliver(again, "", remember=False))
        else:
            self.overlay.show_message("Nothing to type again", ms=1300)

    RETURN_TRIES = 4             # requests to bring back the app you started in,
    RETURN_GAP_MS = 250          # this far apart (about a second in all)
    RETURN_POLL_MS = 50          # how often to look whether it is back

    def _deliver(self, text, after_key="", tries=0, remember=True, kept="", target=None):
        """Type the text (in a thread, so the pop-up keeps moving), then press
        the key after it if one is set. If another app took the front during
        the dictation (often one starting in the background), the app you
        started in is asked back up to 4 times over about a second; the words
        never go into the app that took over."""
        if target is None:
            target = self.target_pid
        elif self.recording or self.target_pid != target:
            return                               # a new dictation has started
        if target and RETURN_FOCUS and front_pid() != target:
            per_try = self.RETURN_GAP_MS // self.RETURN_POLL_MS
            attempt = tries // per_try
            if attempt < self.RETURN_TRIES:
                if tries % per_try == 0 and not self._back_to_target(attempt + 1):
                    attempt = self.RETURN_TRIES  # the app is gone: no use waiting
                else:
                    QTimer.singleShot(self.RETURN_POLL_MS, lambda: self._deliver(
                        text, after_key, tries + 1, remember, kept, target))
                    return
            log.info("could not return to the starting app after %d tries",
                     min(attempt, self.RETURN_TRIES))
            if remember:
                self.remember((kept + text).strip())   # kept only with Missed text safety
            self.overlay.show_message("Couldn't get back to your app, so it wasn't typed",
                                      ms=4500)
            return
        box = focused_text_box()
        if box == "password":
            # Never into a password field (secure input also stops it; this
            # asks the field itself too).
            self.overlay.show_message("Not typed: a password field is selected", ms=3500)
            return
        if after_key and TEXTBOX_ONLY and box == "no":
            after_key = ""               # never Return into a page or a list
        if remember:
            self.remember((kept + text).strip())
        if text and not TYPE_TEXT:
            self._paste(text, after_key)
            return
        def work():
            problem = type_text(text) if text else None
            self.typed.emit(problem or "")
            if not problem and after_key:
                self.after_ready.emit(after_key)
        threading.Thread(target=work, daemon=True).start()

    def _paste(self, text, after_key):
        """Paste mode (off by default): borrow the clipboard for a moment, then
        put back what was there."""
        if IsSecureEventInputEnabled() or focused_text_box() == "password":
            self.overlay.show_message("Not typed: a password field is active", ms=3500)
            return
        if not can_control_keyboard():
            self._on_typed("no_permission")
            return
        before = snapshot_clipboard()
        if before is _CLIPBOARD_FAILED:
            # What you had copied could not be kept safe: type instead.
            log.info("clipboard could not be read; typed instead of pasting")
            threading.Thread(target=lambda: self.typed.emit(type_text(text) or ""),
                             daemon=True).start()
            return
        try:
            copy_privately(text)
        except Exception:
            # Never an unmarked copy on the clipboard: type instead.
            log.exception("clipboard")
            threading.Thread(target=lambda: self.typed.emit(type_text(text) or ""),
                             daemon=True).start()
            return
        _pending_restore.update(before=before, text=text)     # put back even on quit
        QTimer.singleShot(40, lambda: press_key("cmd+v"))
        if after_key:
            QTimer.singleShot(120, lambda: self._press_after(after_key))
        QTimer.singleShot(40 + CLIPBOARD_RESTORE_MS, lambda: restore_clipboard(before, text))
        self.overlay.dismiss()

    def _press_after(self, key):
        """Press the "after dictating" key once the chosen wait is over. During
        a wait a notice says what is coming; clicking it calls it off."""
        self.after_ticket += 1
        ticket = self.after_ticket
        target = front_pid()                     # the app the text went into
        wait_ms = 180 + int(AFTER_DELAY * 1000)
        if AFTER_DELAY > 0:
            self.notice(f"{AFTER_KEY_NAMES.get(key, key)} in {AFTER_DELAY} s  \u00b7  "
                        f"click to cancel", ms=wait_ms, action=self._cancel_after)

        def press():
            if ticket != self.after_ticket or self.recording:
                return                   # cancelled, or you started talking again
            if front_pid() != target:
                # Another app is in front now: Return must not land there.
                log.info("the app changed before the key after the dictation; not pressed")
                return
            if self.hotkey.physically_down():
                QTimer.singleShot(50, press)     # the hotkey would combine with it
                return
            press_key(key)
        QTimer.singleShot(wait_ms, press)

    def _cancel_after(self):
        self.after_ticket += 1
        self.overlay.dismiss()

    def _on_typed(self, problem):
        if problem == "secure":
            self.overlay.show_message("Not typed: a password field is active", ms=3500)
        elif problem == "no_permission":
            self.notice("Not typed: typing permission is off  \u00b7  click to fix",
                        stays=True, action=lambda: open_settings_pane("accessibility"))
        else:
            self.overlay.dismiss()

    def _update_click_through(self):
        """Mac: the pop-up's window is much bigger than what is drawn, and the
        see-through part must not catch clicks meant for the app under it. So
        it takes clicks only while the mouse is over the pill or card."""
        ov = self.overlay
        if ov.isVisible() and not getattr(self, "_floated", False):
            float_everywhere(ov)                 # above other apps, on every Space
            self._floated = True
        wanted = not (ov.isVisible() and ov.fade_target > 0.0
                      and (ov._cursor_on_card() or ov._press is not None))
        if wanted != self._through or not ov.isVisible():
            if ov.isVisible():
                set_click_through(ov, wanted)
                self._through = wanted
            else:
                self._through = None

    def _watch(self):
        if self.downloading:
            pass                                 # the download card has the pill
        elif not self.recording and not self.setup_complete():
            # Setup not finished: the pill keeps saying so, and pressing the
            # key (which leetsay can't hear properly yet) makes it pulse.
            showing = self.overlay.message if self.overlay.mode == "message" else ""
            if self.overlay.mode == "idle" or not self.overlay.isVisible() or (
                    showing == self.SETUP_NEEDED and showing != (
                        self.SETUP_NEEDED if not self.hotkey.port else
                        self.SETUP_MIC)):
                self.show_setup_notice()
        elif (not self.recording and self.overlay.mode == "message"
              and self.overlay.message == self.SETUP_NEEDED):
            # Everything allowed now: the usual pill, with its "ready" pulse.
            self.overlay.show_message(pill_text() if SHOW_HOTKEY_HINT else "Ready",
                                      ms=1800, pulse=True)
        if not self.hotkey.port and not self.recording:
            down = self.hotkey.physically_down()
            if down and not getattr(self, "_setup_key_down", False):
                self.show_setup_notice(pulse=True)
                self.open_setup()                # the one place to finish it
            self._setup_key_down = down
        # A missed key release, or a very long hold: finish the dictation.
        if self.recording:
            started_by_click = getattr(self, "clicked_start", False) or not HOLD_TO_TALK
            typing_now = time.monotonic() - getattr(self, "_last_batch", 0.0) < 0.3
            if not started_by_click and not typing_now \
                    and not self.hotkey.physically_down() \
                    and time.monotonic() - self.recorder.started > 0.3:
                self.hotkey.held = False
                self.on_release()
            elif time.monotonic() - self.recorder.started > MAX_RECORD_SECONDS:
                self.on_release()
        elif self.recorder.is_open and not self.mic_asked:
            self.recorder.close()          # never leave the microphone on

    # other ---------------------------------------------------------------
    def show_about(self):
        folder = local_model_dir()
        release = matching_release() if folder else None
        lines = [
            f"Local dictation for Mac. Speech is recognised on this Mac by NVIDIA's "
            f"Parakeet model; {APP_TITLE} is designed not to save your audio or send it "
            f"anywhere.",
            "",
            f"Model:  {model_label()} (int8), release "
            f"{(release or current_release() or {}).get('tag', 'unknown')}",
            "Stored in:  " + (folder.replace(HOME, "~") if folder else "not on this Mac"),
            f"Loaded in:  {self.load_seconds:.1f} seconds" if self.load_seconds else "Still loading…",
            "Network:  " + network_words(),
            "",
            f"Hotkey:  {self.key_name()}  ("
            f"{'hold while speaking' if HOLD_TO_TALK else 'press to start and stop'})",
            "Settings file:  " + SETTINGS_FILE.replace(HOME, "~"),
            "Log file:  " + os.path.join(LOG_DIR, f"{APP_TITLE}.log").replace(HOME, "~"),
            "",
            f"Speech model: Parakeet TDT 0.6B {'v3' if MODEL.endswith('v3') else 'v2'} "
            f"by NVIDIA Corporation, under the "
            f"CC-BY-4.0 licence, converted to ONNX and reduced to 8 bits by this project "
            f"(github.com/{MODELS_REPO}). Not reviewed or endorsed by NVIDIA. Speech "
            f"detector: Silero VAD by the Silero Team, MIT licence. Windows and menus: "
            f"Qt 6 and PySide6 by The Qt Company and contributors, LGPL-3.0. Other libraries "
            f"(ONNX Runtime, onnx-asr, NumPy, sounddevice and PortAudio, Python) and "
            f"their licences: CREDITS.md, and leetsay.app › Contents › Resources › "
            f"licenses.",
            "",
            "Open-source software under the MIT licence, provided as is, without any warranty. "
            "Speech recognition makes mistakes, and can add words that were never said: "
            "check the text before you send it, and do not rely on it where a wrong word "
            "could cause harm. You are responsible for where the text it types goes.",
        ]
        dialog(f"About {APP_TITLE}", "\n".join(lines), headline=f"{APP_TITLE} {VERSION}",
               on_headline_clicks=lambda: toggle_leet(self))

    def quit(self):
        log.info("quit")
        if _pending_restore:                     # a paste still had the clipboard
            restore_clipboard(_pending_restore.get("before"), _pending_restore.get("text"))
        self.recorder.close()
        leave_now(0)


def restyle_windows():
    """Settings, the setup window and dialogs take a new look at once."""
    for widget in QApplication.topLevelWidgets():
        try:
            if isinstance(widget, SettingsWindow):
                widget.setStyleSheet(settings_style())
                if isinstance(widget, SettingsWindow):
                    widget.leet_bar.setVisible(LEET_MODE)
                    QTimer.singleShot(0, widget._fit_height)
        except Exception:
            log.exception("restyle")


def toggle_leet(dictation):
    """Turn 1337 mode on or off (About's title clicked seven times, or "Exit
    1337 mode" at the top of Settings, shown only while it's on)."""
    apply_leet(not LEET_MODE)
    save_setting("leet_mode", LEET_MODE)
    dictation.overlay.apply_size()
    dictation.overlay.update()
    restyle_windows()
    dictation.overlay.show_message("1337 mode on" if LEET_MODE else "1337 mode off",
                                   ms=2200, pulse=True)


# ---------------------------------------------------------------------------
# Restarting (to apply imported or reset settings)
# ---------------------------------------------------------------------------
def restart_app():
    """Start a fresh copy a moment after this one has gone (only one copy can
    run at a time), then leave. The old copy saves nothing more."""
    _config_frozen[0] = True
    if _pending_restore:                         # a paste still had the clipboard
        restore_clipboard(_pending_restore.get("before"), _pending_restore.get("text"))
    if FROZEN:
        exe = os.path.realpath(sys.executable)
        bundle = exe[:exe.index(".app/") + 4] if ".app/" in exe else exe
        cmd = ["/bin/sh", "-c", 'sleep 1; exec /usr/bin/open -n "$0"', bundle]
    else:
        cmd = ["/bin/sh", "-c", 'sleep 1; exec "$0" -I "$1"', sys.executable,
               os.path.abspath(__file__)]
    log.info("restarting")
    subprocess.Popen(cmd, start_new_session=True, stdin=subprocess.DEVNULL,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    leave_now(0)


def reset_all_settings():
    """Wipe the saved choices and start again with the defaults."""
    keep = {k: _config[k] for k in ("welcomed",) if k in _config}
    _config.clear()
    _config.update(keep)
    write_config()
    if starts_at_login():
        set_start_at_login(False)      # "Start at login" is off at first
    restart_app()


# ---------------------------------------------------------------------------
# The look of Settings and the other windows (the same as on Windows)
# ---------------------------------------------------------------------------
SETTINGS_STYLE = """
QDialog { background: #16171B; }
QLabel, QCheckBox { color: #E6E7EC; font-size: 13px; }
QLabel#field { color: #A9ABB5; }
QLabel#heading { color: #FFFFFF; font-size: 13px; font-weight: 600; }
QFrame#rule { background: #2A2C33; max-height: 1px; border: none; }
QProgressBar { background: #24262C; border: none; border-radius: 3px; max-height: 6px; }
QLabel#info { color: #8E909A; font-size: 11px; }
QComboBox, QPushButton { background: #24262C; color: #E6E7EC; font-size: 13px;
    border: 1px solid #34363E; border-radius: 6px; padding: 4px 11px; min-height: 18px; }
QPushButton:hover, QComboBox:hover { background: #2D3037; border-color: #454852; }
QPushButton:pressed { background: #1E2025; }
QPushButton:disabled { color: #8E909A; }
QComboBox:disabled { color: #6E707A; background: #1F2025; border-color: #2C2E35; }
QPushButton#danger { background: #B8352F; color: #FFFFFF; border-color: #C9443D; }
QPushButton#danger:hover { background: #CC423B; border-color: #E0574F; }
QPushButton#danger:pressed { background: #9E2D28; }
QComboBox::drop-down { border: none; width: 20px; }
QComboBox QAbstractItemView { background: #24262C; color: #E6E7EC; border: 1px solid #34363E;
    selection-background-color: #3A3D46; outline: none; }
QCheckBox { spacing: 9px; }
QCheckBox:disabled, QLabel:disabled { color: #6B6D77; }
QTabWidget::pane { border: 1px solid #2A2C33; border-radius: 10px; background: #1B1C21;
    top: -1px; }
QScrollArea#tabscroll, QWidget#tabpage { background: transparent; border: none; }
QScrollBar:vertical { background: transparent; width: 10px; margin: 6px 2px 6px 0; }
QScrollBar::handle:vertical { background: #3A3D46; border-radius: 4px; min-height: 30px; }
QScrollBar::handle:vertical:hover { background: #4A4E59; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: none; }
QTabBar { qproperty-drawBase: 0; }
QFrame#panel { border: 1px solid #2A2C33; border-radius: 10px; background: #1B1C21; }
QListWidget#sidebar { background: transparent; border: none; outline: none; padding: 4px 0; }
QListWidget#sidebar::item { color: #A9ABB5; font-size: 13px; padding: 0 12px;
    border-radius: 7px; margin: 1px 0; }
QListWidget#sidebar::item:hover { color: #E6E7EC; background: #202228; }
QTabBar::tab { background: transparent; color: #9A9CA6; font-size: 13px;
    padding: 7px 9px; border: none; border-bottom: 2px solid transparent; }
QTabBar::tab:hover { color: #E6E7EC; }
QToolTip { background: #24262C; color: #E6E7EC; border: 1px solid #3A3D46; padding: 6px; }
QLabel#headline { color: #FFFFFF; font-size: 15px; font-weight: 600; }
QLabel#warnline { color: #F2B45A; font-size: 15px; font-weight: 600; }
QLabel#body { color: #C4C6CF; font-size: 13px; }
QLabel#problem { color: #F2B45A; font-size: 13px; }
QPlainTextEdit { background: #121317; color: #E6E7EC; border: 1px solid #2A2C33;
    border-radius: 6px; padding: 6px; font-family: Menlo, monospace; font-size: 12px; }
QTableWidget { background: #121317; color: #E6E7EC; border: 1px solid #2A2C33;
    gridline-color: #2A2C33; font-size: 13px; }
QHeaderView::section { background: #1B1C21; color: #A9ABB5; border: none;
    border-bottom: 1px solid #2A2C33; padding: 4px; }
QTableWidget QLineEdit { background: #24262C; color: #FFFFFF; border: none; }
"""


def tick_image():
    """Path of a small tick picture for ticked check boxes ('' if it can't be made)."""
    path = os.path.join(SUPPORT_DIR, "tick.png")
    try:
        os.makedirs(SUPPORT_DIR, exist_ok=True)
        if not os.path.exists(path):
            pix = QPixmap(32, 32)
            pix.fill(Qt.transparent)
            p = QPainter(pix)
            p.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(16, 17, 20), 4.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([QPointF(7, 17), QPointF(13.5, 23), QPointF(25, 9.5)])
            p.end()
            pix.save(path, "PNG")
        return path
    except Exception:
        return ""


# The light look (Settings › Look) and 1337 mode's look, copied from Windows
# (Mac: Menlo instead of Consolas, plus the sidebar and dialogs).
LIGHT_STYLE = """
QDialog { background: #F4F5F7; }
QDialog QLabel, QDialog QCheckBox { color: #1B1D22; }
QDialog QLabel#field { color: #5A5E69; }
QDialog QLabel#heading { color: #111216; }
QDialog QLabel#headline { color: #111216; }
QDialog QLabel#body { color: #4A4E59; }
QDialog QLabel#note { color: #3A3E47; }
QDialog QLabel#info { color: #6B6F7A; }
QDialog QFrame#rule { background: #DDE0E6; }
QDialog QFrame#panel { background: #FFFFFF; border: 1px solid #E0E2E7; }
QDialog QComboBox, QDialog QPushButton { background: #FFFFFF; color: #1B1D22;
    border: 1px solid #CDD0D7; }
QDialog QPushButton:hover, QDialog QComboBox:hover { background: #F0F1F4; border-color: #B5B9C2; }
QDialog QPushButton:pressed { background: #E6E8EC; }
QDialog QPushButton:disabled { color: #9A9EA8; }
QDialog QComboBox:disabled { color: #9A9EA8; background: #F4F5F7; border-color: #E0E2E7; }
QDialog QComboBox QAbstractItemView { background: #FFFFFF; color: #1B1D22;
    border: 1px solid #CDD0D7; selection-background-color: #E6E8EC; }
QDialog QCheckBox:disabled, QDialog QLabel:disabled { color: #A3A7B0; }
QDialog QCheckBox::indicator { border: 1px solid #B5B9C2; background: #FFFFFF; }
QDialog QCheckBox::indicator:hover { border-color: #7A7E89; }
QDialog QTabWidget::pane { border: 1px solid #E0E2E7; background: #FFFFFF; }
QDialog QTabBar::tab { color: #5A5E69; }
QDialog QTabBar::tab:hover { color: #1B1D22; }
QDialog QTabBar::tab:selected { color: #111216; }
QDialog QScrollBar::handle:vertical { background: #CDD0D7; }
QDialog QScrollBar::handle:vertical:hover { background: #B5B9C2; }
QDialog QSlider::groove:horizontal, QDialog QSlider::add-page:horizontal { background: #DDE0E6; }
QDialog QSlider::handle:horizontal { background: #FFFFFF; border: 1px solid #B5B9C2; }
QDialog QProgressBar { background: #E6E8EC; }
QDialog QPlainTextEdit, QDialog QLineEdit { background: #FFFFFF; color: #1B1D22;
    border: 1px solid #CDD0D7; }
QToolTip { background: #FFFFFF; color: #1B1D22; border: 1px solid #CDD0D7; }
QDialog QFrame#panel { background: #FFFFFF; border: 1px solid #E0E2E7; }
QDialog QListWidget#sidebar::item { color: #4A4E59; }
QDialog QListWidget#sidebar::item:hover { color: #1B1D22; background: #E9EBEF; }
QDialog QListWidget#sidebar::item:selected { color: #111216; background: #E3E6EB; }
QDialog QLabel#warnline { color: #B26A00; }
QDialog QLabel#problem { color: #B26A00; }
QDialog QTableWidget { background: #FFFFFF; color: #1B1D22; border: 1px solid #E0E2E7;
    gridline-color: #E0E2E7; }
QDialog QHeaderView::section { background: #F4F5F7; color: #5A5E69;
    border-bottom: 1px solid #E0E2E7; }
QDialog QTableWidget QLineEdit { background: #FFFFFF; color: #111216; }
QDialog QPushButton#danger { background: #B8352F; color: #FFFFFF; border-color: #C9443D; }
"""



LEET_STYLE = """
QDialog, QWidget#tabpage { font-family: Menlo; }
QDialog { background: #050A06; }
QLabel, QCheckBox { color: #8CFFAE; font-family: Menlo; font-size: 12px; }
QLabel#field { color: #3FBF6A; font-size: 11px; }
QLabel#heading { color: #B6FFC9; }
QLabel#info { color: #2F9E57; }
QFrame#rule { background: #123A1E; }
QComboBox, QPushButton { background: #0B160E; color: #8CFFAE; border-color: #1E5A30;
    font-family: Menlo; font-size: 12px; }
QPushButton:hover, QComboBox:hover { background: #102516; border-color: #2FB85C; }
QPushButton:pressed { background: #071009; }
QComboBox QAbstractItemView { background: #0B160E; color: #8CFFAE; border-color: #1E5A30;
    selection-background-color: #174D27; }
QCheckBox::indicator { border-color: #1E5A30; background: #071009; }
QTabWidget::pane { border-color: #123A1E; background: #071009; }
QTabBar::tab { color: #3FBF6A; font-family: Menlo; font-size: 12px; }
QTabBar::tab:hover { color: #8CFFAE; }
QTabBar::tab:selected { color: #B6FFC9; }
QSlider::groove:horizontal, QSlider::add-page:horizontal { background: #123A1E; }
QSlider::handle:horizontal { background: #8CFFAE; }
QScrollBar::handle:vertical { background: #174D27; }
QProgressBar { background: #0B160E; }
QToolTip { background: #0B160E; color: #8CFFAE; border-color: #1E5A30; }
QPushButton#danger { background: #B8352F; color: #FFFFFF; border-color: #C9443D; }
QFrame#panel { background: #071009; border-color: #123A1E; }
QListWidget#sidebar::item { color: #3FBF6A; font-family: Menlo; }
QListWidget#sidebar::item:hover { color: #8CFFAE; background: #0B160E; }
QListWidget#sidebar::item:selected { color: #B6FFC9; background: #102516; }
QLabel#headline, QLabel#body { color: #8CFFAE; font-family: Menlo; }
QPlainTextEdit, QTableWidget { background: #050A06; color: #8CFFAE; border-color: #1E5A30; }
"""


def settings_style():
    tick = tick_image()
    accent = QColor(ACCENT).name()
    return SETTINGS_STYLE + """
QCheckBox::indicator { width: 16px; height: 16px; border-radius: 4px;
    border: 1px solid #555862; background: #1E2025; }
QCheckBox::indicator:hover { border-color: #8A8D98; }
QCheckBox::indicator:checked { background: %(accent)s; border-color: %(accent)s; %(tick)s }
QTabBar::tab:selected { color: #FFFFFF; border-bottom: 2px solid %(accent)s; }
QListWidget#sidebar::item:selected { color: #FFFFFF; background: #26282F;
    border-left: 3px solid %(accent)s; }
QProgressBar::chunk { background: %(accent)s; border-radius: 3px; }
QPushButton#primary { background: %(accent)s; color: #101114; border: 1px solid %(accent)s;
    font-weight: 600; }
QPushButton#primary:hover { background: %(accent)s; border-color: #FFFFFF; }
""" % {"accent": accent, "tick": ('image: url("%s");' % tick) if tick else ""} + (
        LEET_STYLE if LEET_MODE else LIGHT_STYLE if light_menus() else "")


def dialog(title, text, buttons=("OK",), icon=None, parent=None, headline=None,
           width=400, on_headline_clicks=None):
    """The app's own dialog: a headline, a paragraph at a comfortable width,
    and buttons on the right, the main one (the first named) in the accent
    colour. Enter picks the last-named, safe one. Returns the button's name,
    or None if the window was closed."""
    bring_to_front()
    box = QtWidgets.QDialog(parent)
    box.setWindowTitle(title)
    box.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
                       | Qt.WindowStaysOnTopHint)
    box.setStyleSheet(settings_style())
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(24, 20, 24, 18)
    layout.setSpacing(10)
    top = QtWidgets.QLabel(headline or title)
    top.setObjectName("warnline" if icon == "warning" else "headline")
    top.setWordWrap(True)
    top.setFixedWidth(width)
    if on_headline_clicks is not None:
        # About: the title clicked seven times in a row (quickly) does this.
        clicks = {"n": 0, "at": 0.0}

        def clicked(_event):
            now = time.monotonic()
            clicks["n"] = clicks["n"] + 1 if now - clicks["at"] < 1.0 else 1
            clicks["at"] = now
            if clicks["n"] >= 7:
                clicks["n"] = 0
                on_headline_clicks()
                box.setStyleSheet(settings_style())
        top.mousePressEvent = clicked
    layout.addWidget(top)
    body = QtWidgets.QLabel(text)
    body.setObjectName("body")
    body.setWordWrap(True)
    body.setFixedWidth(width)
    body.setTextInteractionFlags(Qt.TextSelectableByMouse)
    layout.addWidget(body)
    layout.addSpacing(8)
    row = QtWidgets.QHBoxLayout()
    row.addStretch(1)
    picked = {"name": None}
    made = []
    for i, name in reversed(list(enumerate(buttons))):
        b = QtWidgets.QPushButton(name)
        b.setAutoDefault(False)
        if i == 0 and len(buttons) > 1:
            b.setObjectName("primary")
        b.clicked.connect(lambda _c=False, n=name: (picked.update(name=n), box.accept()))
        row.addWidget(b)
        made.append(b)
    made[0].setDefault(True)               # the safe, last-named choice
    layout.addLayout(row)
    box.exec()
    return picked["name"]


class _Relay(QObject):
    """Carries a result from a helper thread back to the windows."""
    done = Signal(object)


# ---------------------------------------------------------------------------
# Move settings to another computer: one line of text
# ---------------------------------------------------------------------------
# Only choices about how the app behaves travel: never file paths, devices,
# model files, or anything that would delete, download or go online. A pasted
# line is untrusted: every value is checked, unknown keys are left out, and
# switching a safety check off needs a yes.
_PORTABLE_PREFIX = APP_TITLE.lower() + "-settings-1:"
_PORTABLE_MAX = 8000


def _is_int_in(low, high):
    return lambda v: isinstance(v, int) and not isinstance(v, bool) and low <= v <= high


_AFTER_KEYS = [c[0] for c in AFTER_CHOICES] + ["ctrl+enter"]   # Windows' = ⌘ Return here
_PORTABLE_CHECKS = {
    # Windows hotkeys are left out here (and Mac ones there).
    "hotkey": lambda v: v in HOTKEYS,
    "action_hotkey": lambda v: v == "" or v in HOTKEYS,
    "paste_hotkey": lambda v: v == "" or v in HOTKEYS,
    "action_key": lambda v: v in _AFTER_KEYS and v != "",
    "after_key": lambda v: v in _AFTER_KEYS,
    "after_delay": lambda v: v in [d[0] for d in AFTER_DELAYS],
    "accent": lambda v: _is_colour(v),
    "popup_bg": lambda v: _is_colour(v),
    "glow_colour": lambda v: _is_colour(v, empty_ok=True),
    "glow": lambda v: v in [g[0] for g in GLOW_LEVELS],
    "sound_set": lambda v: v in [k for k, _label in SOUND_SETS if k != "custom"],
    "volume": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    and 0.0 <= v <= 1.0,
    "text_size": lambda v: v in [t[0] for t in TEXT_SIZES],
    "live_lines": _is_int_in(1, 6),
    "card_width": _is_int_in(0, 2000),
    "max_seconds": _is_int_in(30, 3600),
    "screen_glow_strength": _is_int_in(5, 100),
    "screen_glow_size": _is_int_in(20, 200),
    "card_style": lambda v: v in [k for k, _label in CARD_STYLES],
    "screen_glow_edges": lambda v: v in ("bottom", "top", "left", "right", "all"),
    "screen_glow_screens": lambda v: v in ("popup", "all", "main"),
    "screen_glow_focus": lambda v: v in ("middle", "corners", "even"),
    "pill_mark": lambda v: v in PILL_MARKS,
    "menu_theme": lambda v: v in ("system", "dark", "light"),
}
for _key in ("add_space", "always_show", "pill_over_fullscreen", "accent_outline", "outline_light", "glow_from_app",
             "hotkey_hint", "return_focus", "screen_glow", "show_app_icon", "show_app_name",
             "show_popup", "show_timer", "show_waveform", "sounds", "tray_live", "wide_card",
             "live_preview", "type_text", "keep_last", "check_app_updates", "live_type",
             "remove_fillers", "textbox_only", "screen_glow_flow", "pointer_hint",
             "hold_to_talk"):
    _PORTABLE_CHECKS[_key] = lambda v: isinstance(v, bool)

# Turning these on touches the clipboard, keeps text, or goes online. For
# "type_text" it is turning it OFF that switches to pasting via the clipboard.
_PORTABLE_CAREFUL = {
    "type_text": (False, "Paste using the clipboard instead of typing"),
    "keep_last": (True, "Missed text safety (keeps your last dictation in memory "
                        "for %d minutes)" % (KEEP_LAST_SECONDS // 60)),
    "check_app_updates": (True, "Check for updates at startup (this application will go "
                                "online, to github.com, a third-party website that we do "
                                "not run or control)"),
    # Safety checks: switching these OFF needs a yes too.
    "textbox_only": (False, "Text box detection OFF (words are typed wherever the "
                            "cursor is, even outside a text box)"),
    "return_focus": (False, "Stay in the app I started in OFF (words go to whatever app "
                            "is in front when they are typed)"),
    # Any key at all (not one value): see _careful_value.
    "after_key": ("any", "Pressing a key for you after dictating (Return can send a "
                         "message straight away)"),
    "action_hotkey": ("any", "A second hotkey that presses a key for you after dictating "
                             "(Return can send a message straight away)"),
}


def export_settings_line():
    import base64
    picked = {key: _config[key] for key in sorted(_PORTABLE_CHECKS)
              if key in _config and _PORTABLE_CHECKS[key](_config[key])}
    raw = json.dumps(picked, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return _PORTABLE_PREFIX + base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


_CAREFUL_NAMES = {"after_key": "AFTER_KEY", "action_hotkey": "ACTION_HOTKEY",
                  "type_text": "TYPE_TEXT", "keep_last": "KEEP_LAST",
                  "check_app_updates": "CHECK_APP_UPDATES", "textbox_only": "TEXTBOX_ONLY",
                  "return_focus": "RETURN_FOCUS"}


def read_settings_line(line):
    """Returns (good, careful, dropped, problem)."""
    import base64
    line = "".join(str(line or "").split())
    if not line:
        return {}, {}, 0, "Nothing was pasted."
    if len(line) > _PORTABLE_MAX:
        return {}, {}, 0, "That is far too long to be a settings line."
    if not line.startswith(_PORTABLE_PREFIX):
        return {}, {}, 0, (f"That is not a settings line from {APP_TITLE}. It should "
                           f"start with \"{_PORTABLE_PREFIX}\".")
    body = line[len(_PORTABLE_PREFIX):]
    try:
        data = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
                          .decode("utf-8"))
    except Exception:
        return {}, {}, 0, "The line is damaged (part of it may be missing)."
    if not isinstance(data, dict):
        return {}, {}, 0, "The line is damaged."
    good, careful, dropped = {}, {}, 0
    for key, value in data.items():
        check = _PORTABLE_CHECKS.get(key) if isinstance(key, str) else None
        if check is None or not check(value):
            dropped += 1
            continue
        risky = _PORTABLE_CAREFUL.get(key)
        current = _config.get(key, globals().get(_CAREFUL_NAMES.get(key, ""), None))
        if risky and risky[0] == "any":
            risky_now = bool(value) and current != value
        else:
            risky_now = bool(risky) and value == risky[0] and current != value
        if risky_now:
            careful[key] = value
        else:
            good[key] = value
    return good, careful, dropped, ""


def export_settings_window(parent):
    """Shows the line to copy. The app does not put it on the clipboard itself."""
    box = QtWidgets.QDialog(parent)
    box.setWindowTitle("Export settings")
    box.setStyleSheet(settings_style())
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(24, 20, 24, 18)
    layout.setSpacing(10)
    for words, name in (("Your settings as one line", "headline"),
                        (f"Select the line below and copy it (⌘C), then paste it into "
                         f"Import settings on another computer. {APP_TITLE} does not put it "
                         f"on the clipboard for you.\n\nIt holds only your choices. No text "
                         f"you dictated, no file paths, no devices, nothing about the "
                         f"speech model.", "body")):
        label = QtWidgets.QLabel(words)
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setFixedWidth(420)
        layout.addWidget(label)
    field = QtWidgets.QPlainTextEdit(export_settings_line())
    field.setReadOnly(True)
    field.setFixedSize(420, 110)
    field.selectAll()
    layout.addWidget(field)
    buttons = QtWidgets.QHBoxLayout()
    buttons.addStretch(1)
    close = QtWidgets.QPushButton("Close")
    close.clicked.connect(lambda _c=False: box.accept())
    buttons.addWidget(close)
    layout.addLayout(buttons)
    field.setFocus()
    box.exec()


def import_settings_window(parent):
    """Paste a line, check it, and apply what is safe; ask about the rest."""
    box = QtWidgets.QDialog(parent)
    box.setWindowTitle("Import settings")
    box.setStyleSheet(settings_style())
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(24, 20, 24, 18)
    layout.setSpacing(10)
    for words, name in (("Paste a settings line", "headline"),
                        ("Paste a line made with Export settings (⌘V). Every value is "
                         "checked first; settings this Mac version doesn't have yet are "
                         "left out. Switching a safety check off needs your yes. The "
                         "application restarts to apply the settings.", "body")):
        label = QtWidgets.QLabel(words)
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setFixedWidth(420)
        layout.addWidget(label)
    field = QtWidgets.QPlainTextEdit()
    field.setFixedSize(420, 110)
    field.setPlaceholderText(_PORTABLE_PREFIX + "…")
    layout.addWidget(field)
    problem = QtWidgets.QLabel("")
    problem.setObjectName("problem")
    problem.setWordWrap(True)
    problem.setFixedWidth(420)
    problem.setVisible(False)
    layout.addWidget(problem)
    buttons = QtWidgets.QHBoxLayout()
    buttons.addStretch(1)
    cancel = QtWidgets.QPushButton("Cancel")
    cancel.clicked.connect(lambda _c=False: box.reject())
    buttons.addWidget(cancel)
    go_button = QtWidgets.QPushButton("Import and restart")
    go_button.setObjectName("primary")
    buttons.addWidget(go_button)
    layout.addLayout(buttons)

    def go(_checked=False):
        good, careful, dropped, why = read_settings_line(field.toPlainText())
        if why or not (good or careful):
            problem.setText(why or "The line holds no settings that can be used on "
                                   "this Mac yet.")
            problem.setVisible(True)
            box.adjustSize()
            return
        if careful:
            names = "\n".join("•  " + _PORTABLE_CAREFUL[key][1] for key in careful)
            answer = dialog("Change these too?",
                            f"The line would also change:\n\n{names}\n\nOn this Mac this is "
                            f"set the careful way. Leave it as it is unless you want this "
                            f"on this Mac too.",
                            buttons=("Change them", "Leave them as they are"), parent=box,
                            headline="These are set the careful way on this Mac")
            if answer == "Change them":
                good.update(careful)
        _config.update(good)
        write_config()
        log.info("imported %d settings (%d left out)", len(good), dropped)
        box.accept()
        note = f"{len(good)} settings imported." + (
            f" {dropped} entries were left out (not on this Mac yet, or not valid)."
            if dropped else "")
        dialog("Settings imported", note + "\n\nIt restarts now to use them.",
               buttons=("Restart",), parent=parent,
               headline="The application will restart")
        restart_app()

    go_button.clicked.connect(go)
    box.exec()


def replacements_window(parent):
    """Edit the word replacements. Empty rows are ignored; saved on closing."""
    box = QtWidgets.QDialog(parent)
    box.setWindowTitle("Word replacements")
    box.setStyleSheet(settings_style())
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(20, 18, 20, 16)
    note = QtWidgets.QLabel(
        "The speech model can't learn new words, so names it doesn't know come out as "
        "something close (\"leet\" as \"leaked\"). Add what it writes on the left and "
        "what you want on the right. Whole words only; capitals don't matter. Kept in "
        "your settings on this Mac.")
    note.setObjectName("info")
    note.setWordWrap(True)
    note.setFixedWidth(440)
    layout.addWidget(note)
    table = QtWidgets.QTableWidget(max(12, len(REPLACEMENTS) + 4), 2)
    table.setHorizontalHeaderLabels(["It writes", "You want"])
    table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
    table.verticalHeader().setVisible(False)
    table.setFixedWidth(440)
    table.setMinimumHeight(300)
    for r, (heard, write) in enumerate(REPLACEMENTS):
        table.setItem(r, 0, QtWidgets.QTableWidgetItem(heard))
        table.setItem(r, 1, QtWidgets.QTableWidgetItem(write))
    layout.addWidget(table)
    buttons = QtWidgets.QHBoxLayout()

    def add_tech_terms():
        have = {" ".join((table.item(r, 0).text() if table.item(r, 0) else "").lower().split())
                for r in range(table.rowCount())}
        missing = [pair for pair in TECH_TERMS if pair[0] not in have]
        rows_now = sum(1 for r in range(table.rowCount())
                       if table.item(r, 0) and table.item(r, 0).text().strip())
        missing = missing[:max(0, REPLACE_MAX - rows_now)]
        empty = [r for r in range(table.rowCount())
                 if not (table.item(r, 0) and table.item(r, 0).text().strip())]
        if len(empty) < len(missing):
            table.setRowCount(table.rowCount() + len(missing) - len(empty))
            empty = [r for r in range(table.rowCount())
                     if not (table.item(r, 0) and table.item(r, 0).text().strip())]
        for (heard, write), r in zip(missing, empty):
            table.setItem(r, 0, QtWidgets.QTableWidgetItem(heard))
            table.setItem(r, 1, QtWidgets.QTableWidgetItem(write))

    tech = QtWidgets.QPushButton("Add tech terms")
    tech.setToolTip("Adds common tech terms written the short way: megabytes as MB, "
                    "gigahertz as GHz, java script as JavaScript and more. Remove any "
                    "you don't want.")
    tech.clicked.connect(lambda _c=False: add_tech_terms())
    buttons.addWidget(tech)
    buttons.addStretch(1)
    done = QtWidgets.QPushButton("Save")
    done.setObjectName("primary")
    done.clicked.connect(lambda _c=False: box.accept())
    buttons.addWidget(done)
    layout.addLayout(buttons)
    box.exec()                                   # Save, the close button or Esc: kept
    pairs = []
    for r in range(table.rowCount()):
        cells = [table.item(r, col) for col in (0, 1)]
        heard, write = [(" ".join(c.text().split()) if c else "")[:REPLACE_LEN] for c in cells]
        heard = "".join(c for c in heard if plain_text(c))
        write = "".join(c for c in write if plain_text(c))
        if heard and write and len(pairs) < REPLACE_MAX:
            pairs.append([heard, write])
    globals()["REPLACEMENTS"] = pairs
    save_setting("replacements", pairs)


def network_words():
    """How the network stands, in words for Settings and About."""
    if _net["open"]:
        return "open for this download or update check only (GitHub)"
    if _net["verified"]:
        return f"blocked for {APP_TITLE} (offline, checked at start)"
    if _net["verified"] is False:
        return "blocked, but the check at start did not pass (see the log)"
    return f"blocked for {APP_TITLE} (offline)"


def check_model_files():
    """Read every file of the model in use and of the helper in full and
    compare it with its known SHA-256. Returns the problems (empty if all is
    well)."""
    problems = []
    for name, folder, release in ((model_label(), model_dir(), current_release()),
                                  ("speech detector", helper_dir(), HELPER_RELEASE)):
        if not os.path.isdir(folder):
            problems.append(f"{name}: not on this Mac")
            continue
        for file, (size, sha) in release["files"].items():
            path = os.path.join(folder, file)
            if not os.path.isfile(path):
                problems.append(f"{file}: missing")
            elif os.path.getsize(path) != size or file_fingerprint(path) != sha:
                problems.append(f"{file}: does not match")
    return problems


def download_question_words(name=None):
    """The words of the one-time download question."""
    return (f"This application will go online once to download the speech model "
            f"({model_label(name)}, {model_size_words(name)}) and a small helper (about "
            f"2 MB) from this project's page on github.com, a third-party website that we "
            f"do not run or control. Every file is checked; after that, {APP_TITLE} works "
            f"offline.")


def manual_download_steps():
    """For people who would rather the app never went online: the files to
    fetch by hand, and where to put them. The page is opened only on request."""
    release = current_release()
    folder = model_dir()
    files = "\n".join("•  " + name for name in sorted(release["files"]))
    helper = "\n".join("•  " + name for name in sorted(HELPER_RELEASE["files"]))
    while True:
        choice = dialog(
            "Manual download",
            f"1.  On the project's model page, open the release “{release['tag']}” and "
            f"download these files:\n{files}\n\n"
            f"2.  Put them in this folder (create it if it isn't there):\n"
            f"{folder.replace(HOME, '~')}\n\n"
            f"3.  For the speech detector, release “{HELPER_RELEASE['tag']}”:\n{helper}\n"
            f"into {helper_dir().replace(HOME, '~')}\n\n"
            f"{APP_TITLE} checks every file before using it; a file that doesn't match "
            f"is never used. The page is on github.com, a third-party website that we do "
            f"not run or control.",
            buttons=("Open the folder", "Open the page", "Close"),
            headline="Download the speech model yourself", width=460)
        if choice == "Open the folder":
            os.makedirs(folder, exist_ok=True)
            os.makedirs(helper_dir(), exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(models_root()))
        elif choice == "Open the page":
            QDesktopServices.openUrl(QUrl(MODELS_PAGE))
        else:
            return


def open_feedback_page(parent, kind):
    """The GitHub form for a bug report or an idea, in the web browser, after
    the third-party notice. The application itself does not go online."""
    form = "bug_report.yml" if kind == "bug" else "feature_request.yml"
    what = "report a problem" if kind == "bug" else "suggest an idea"
    if dialog("Open github.com?",
              f"To {what}, {APP_TITLE} opens a form on github.com in your web browser. "
              f"That is a third-party website that we do not run or control; you need a "
              f"free GitHub account to send the form, and what you write there is "
              f"public.\n\nPlease do not include anything private. {APP_TITLE} itself "
              f"does not go online for this.",
              buttons=("Open the page", "Cancel"), parent=parent,
              headline="This opens a page in your web browser") == "Open the page":
        QDesktopServices.openUrl(QUrl(
            f"https://github.com/{APP_REPO}/issues/new?template={form}"))


# ---------------------------------------------------------------------------
# Settings window
# ---------------------------------------------------------------------------
class _TabScroll(QtWidgets.QScrollArea):
    """A tab that scrolls up and down if it must, always exactly as wide as
    the window shows."""

    def resizeEvent(self, event):
        super().resizeEvent(event)
        page = self.widget()
        if page is not None:
            page.setFixedWidth(self.viewport().width())
            page.setMinimumHeight(page.sizeHint().height())


class SettingsWindow(QtWidgets.QDialog):
    """Every option in one place. Changes apply straight away and are saved."""

    TABS = ("General", "Typing", "Pop-up", "Pill", "Look", "Audio", "Model", "Privacy")
    _last_tab = 0                   # remembered while the app runs (not saved)

    def __init__(self, dictation):
        super().__init__()
        self.dictation = dictation
        self.setWindowTitle(f"{APP_TITLE} settings  ·  v{VERSION}")
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
                            | Qt.WindowMinimizeButtonHint)
        self.setStyleSheet(settings_style())
        # A sidebar on the left, as Mac apps have it: wider and much less tall
        # than tabs along the top (the window was too long on a Mac).
        self.setFixedWidth(700)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 14)
        outer.setSpacing(12)
        # Only while 1337 mode is on: a bar at the top with the way back out.
        self.leet_bar = QtWidgets.QWidget()
        bar = QtWidgets.QHBoxLayout(self.leet_bar)
        bar.setContentsMargins(0, 0, 0, 0)
        bar_text = QtWidgets.QLabel("1337 mode is on")
        bar_text.setObjectName("info")
        bar.addWidget(bar_text)
        bar.addStretch(1)
        leave_leet = QtWidgets.QPushButton("Exit 1337 mode")
        leave_leet.setAutoDefault(False)
        leave_leet.clicked.connect(lambda: toggle_leet(self.dictation))
        bar.addWidget(leave_leet)
        self.leet_bar.setVisible(LEET_MODE)
        outer.addWidget(self.leet_bar)
        body = QtWidgets.QHBoxLayout()
        body.setSpacing(12)
        sidebar = QtWidgets.QListWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(150)
        sidebar.setFocusPolicy(Qt.NoFocus)
        sidebar.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sidebar.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        panel = QtWidgets.QFrame()
        panel.setObjectName("panel")
        panel_layout = QtWidgets.QVBoxLayout(panel)
        panel_layout.setContentsMargins(1, 1, 1, 1)
        tabs = QtWidgets.QStackedWidget()
        panel_layout.addWidget(tabs)
        body.addWidget(sidebar, 0, Qt.AlignTop)
        body.addWidget(panel, 1)
        outer.addLayout(body, 1)
        sidebar.currentRowChanged.connect(tabs.setCurrentIndex)
        tabs.currentChanged.connect(lambda i: sidebar.setCurrentRow(i))
        self._tabs = tabs
        self._sidebar = sidebar
        page = {"layout": None}
        self._relay = _Relay()
        self._relay.done.connect(self._helper_done)

        def tab(title):
            holder = QtWidgets.QWidget()
            holder.setObjectName("tabpage")
            layout = QtWidgets.QVBoxLayout(holder)
            layout.setContentsMargins(16, 14, 16, 14)
            layout.setSpacing(10)
            layout.setSizeConstraint(QtWidgets.QLayout.SetNoConstraint)
            area = _TabScroll()
            area.setObjectName("tabscroll")
            area.setWidgetResizable(True)
            area.setFrameShape(QtWidgets.QFrame.NoFrame)
            area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            area.setWidget(holder)
            area.viewport().setAutoFillBackground(False)
            tabs.addWidget(area)
            item = QtWidgets.QListWidgetItem(title)
            item.setSizeHint(QtCore.QSize(140, 32))
            sidebar.addItem(item)
            sidebar.setFixedHeight(32 * sidebar.count() + 8)
            page["layout"] = layout

        def end_tab():
            page["layout"].addStretch(1)

        def row(*widgets):
            line = QtWidgets.QHBoxLayout()
            line.setSpacing(8)
            for widget in widgets:
                if widget is None:
                    line.addStretch(1)
                else:
                    line.addWidget(widget)
            page["layout"].addLayout(line)
            return line

        def button_grid(*buttons):
            grid = QtWidgets.QGridLayout()
            grid.setHorizontalSpacing(8)
            grid.setVerticalSpacing(8)
            for i, made in enumerate(buttons):
                made.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
                if i == len(buttons) - 1 and i % 2 == 0 and i > 0:
                    grid.addWidget(made, i // 2, 0, 1, 2)
                else:
                    grid.addWidget(made, i // 2, i % 2)
            grid.setColumnStretch(0, 1)
            grid.setColumnStretch(1, 1)
            page["layout"].addLayout(grid)

        def field(text):
            label = QtWidgets.QLabel(text)
            label.setObjectName("field")
            label.setFixedWidth(104)             # one column on every tab
            return label

        def heading(text, first=False):
            if not first:
                rule = QtWidgets.QFrame()
                rule.setObjectName("rule")
                rule.setFixedHeight(1)
                page["layout"].addSpacing(2)
                page["layout"].addWidget(rule)
                page["layout"].addSpacing(2)
            label = QtWidgets.QLabel(text)
            label.setObjectName("heading")
            page["layout"].addWidget(label)

        def button(text, handler, width=None):
            made = QtWidgets.QPushButton(text)
            made.setAutoDefault(False)
            made.clicked.connect(lambda _c=False: handler())
            if width:
                made.setFixedWidth(width)
            return made

        def note(text):
            label = QtWidgets.QLabel(text)
            label.setObjectName("info")
            label.setWordWrap(True)
            page["layout"].addWidget(label)
            return label

        def check(text, value, handler, tip=None, hint=None):
            box = QtWidgets.QCheckBox(text)
            box.setChecked(bool(value))
            box.toggled.connect(handler)
            if tip:
                box.setToolTip("<p style='white-space: pre-wrap; width: 300px;'>%s</p>" % tip)
            page["layout"].addWidget(box)
            if hint:                             # indented under the box's text
                label = QtWidgets.QLabel(hint)
                label.setObjectName("info")
                label.setWordWrap(True)
                label.setContentsMargins(25, 0, 0, 2)
                page["layout"].addWidget(label)
            return box

        def option(name, key, refresh=False, preview=False):
            def handler(value):
                set_option(name, key, bool(value))
                if refresh:
                    dictation.refresh_popup()
                if preview:
                    dictation.preview_popup()
            return handler
        self.swatches = []

        # ================= General =================
        tab("General")
        heading("Dictation hotkey", first=True)
        self.hotkey = QtWidgets.QComboBox()
        for key, (_code, _mask, name) in HOTKEYS.items():
            self.hotkey.addItem(name, key)
        self.hotkey.setCurrentIndex(max(0, self.hotkey.findData(HOTKEY)))
        self.hotkey.currentIndexChanged.connect(
            lambda i: (dictation.set_hotkey(self.hotkey.itemData(i)),
                       getattr(self, "_show_action", lambda: None)()))
        row(field("Key"), self.hotkey, None)
        self.hold_mode = QtWidgets.QComboBox()
        self.hold_mode.addItem("Hold while speaking", True)
        self.hold_mode.addItem("Press to start and stop", False)
        self.hold_mode.setCurrentIndex(0 if HOLD_TO_TALK else 1)
        self.hold_mode.currentIndexChanged.connect(
            lambda i: dictation.set_hold_to_talk(bool(self.hold_mode.itemData(i))))
        row(field("How"), self.hold_mode, None)
        note("Hold: hold the key on its own while you speak, and let go to type. "
             "Press: tap it once to start and once more to finish. Pressed together "
             "with another key it works as usual (for example ⌥E for é), and nothing "
             "is recorded.")

        heading("Pressing a key for you")
        self.after = QtWidgets.QComboBox()
        for key, label in AFTER_CHOICES:
            self.after.addItem(label, key)
        self.after.setCurrentIndex(max(0, self.after.findData(AFTER_KEY)))
        self.after_delay = QtWidgets.QComboBox()
        for seconds, label in AFTER_DELAYS:
            self.after_delay.addItem(label, seconds)
        self.after_delay.setCurrentIndex(max(0, self.after_delay.findData(AFTER_DELAY)))

        def after_key_chosen(index):
            key = self.after.itemData(index)
            if key and not AFTER_KEY and not auto_key_warning(
                    self, AFTER_KEY_NAMES.get(key, key)):
                self.after.blockSignals(True)    # not confirmed: back to "do nothing"
                self.after.setCurrentIndex(max(0, self.after.findData("")))
                self.after.blockSignals(False)
                key = ""
            set_option("AFTER_KEY", "after_key", key)
            self.after_delay.setEnabled(bool(key))
        self.after.currentIndexChanged.connect(after_key_chosen)
        self.after_delay.currentIndexChanged.connect(
            lambda index: set_option("AFTER_DELAY", "after_delay",
                                     int(self.after_delay.itemData(index))))
        self.after_delay.setEnabled(bool(AFTER_KEY))
        row(field("After dictating"), self.after, self.after_delay, None)
        note("A key pressed for you once the text is typed: Return sends a chat "
             "message, Tab moves to the next box. With a wait, a notice counts it "
             "down; click the notice to cancel.")

        # A second hotkey: dictate as usual, then press a key (say, to send a
        # chat message straight away only when you want to).
        self.action = QtWidgets.QComboBox()
        self.action.addItem("not set", "")
        for key, (_code, _mask, name) in HOTKEYS.items():
            self.action.addItem(name, key)
        self.action_key = QtWidgets.QComboBox()
        for key, label in AFTER_CHOICES:
            if key:
                self.action_key.addItem(label, key)
        self.action_key.setCurrentIndex(max(0, self.action_key.findData(ACTION_KEY)))
        self.action_key.currentIndexChanged.connect(
            lambda index: set_option("ACTION_KEY", "action_key",
                                     self.action_key.itemData(index)))

        def show_action():
            self.action.blockSignals(True)
            self.action.setCurrentIndex(max(0, self.action.findData(ACTION_HOTKEY)))
            for i in range(self.action.count()):         # not the dictation key itself
                item = self.action.model().item(i)
                if item is not None:
                    item.setEnabled(self.action.itemData(i) != HOTKEY)
            self.action.blockSignals(False)
            self.action_key.setEnabled(bool(ACTION_HOTKEY))
        self._show_action = show_action

        def action_chosen(index):
            key = self.action.itemData(index) or ""
            if key and not ACTION_HOTKEY and not auto_key_warning(
                    self, AFTER_KEY_NAMES.get(ACTION_KEY, ACTION_KEY)):
                key = ""                         # not confirmed
            if key == HOTKEY:
                key = ""
            if key and key == PASTE_HOTKEY:     # one job per key
                set_option("PASTE_HOTKEY", "paste_hotkey", "")
                dictation.hotkey.set_paste("")
            set_option("ACTION_HOTKEY", "action_hotkey", key)
            dictation.hotkey.set_action(key)
            show_action()
        self.action.currentIndexChanged.connect(action_chosen)
        show_action()
        row(field("Second hotkey"), self.action, self.action_key, None)
        note("Hold it to dictate as usual; when you let go, the text is typed and the "
             "key on the right is pressed too. For when you only sometimes want that.")

        heading("Startup")
        self.login = check("Start at login", starts_at_login(), self._login_changed,
                           hint=("Starts quietly in the menu bar when you log in." if FROZEN
                                 else "Only in the installed app (not while testing)."))
        self.login.setEnabled(FROZEN)

        heading("Permissions")
        self.perm_typing = QtWidgets.QLabel("")
        self.perm_mic = QtWidgets.QLabel("")
        row(field("Typing"), self.perm_typing, None,
            button("Open settings", lambda: open_settings_pane("accessibility"), width=130))
        row(field("Microphone"), self.perm_mic, None,
            button("Open settings", lambda: open_settings_pane("microphone"), width=130))
        note("Typing covers the hotkey too (macOS calls it Accessibility). Something not "
             "working? Choose Setup and permissions\u2026 in the menu bar menu.")
        self._show_permissions()
        self._perm_timer = QTimer(self)          # kept up to date while this is open
        self._perm_timer.setInterval(1500)
        self._perm_timer.timeout.connect(self._show_permissions)
        self._perm_timer.start()
        end_tab()

        # ================= Typing =================
        tab("Typing")
        heading("Text", first=True)
        check("Type as you speak", LIVE_TYPE, option("LIVE_TYPE", "live_type"),
              tip="Off by default. Your words are typed into your app while you "
                  "speak, about half a second behind you, instead of all at once "
                  "when you finish. The key can stay held: it doesn't get in the "
                  "way of the typing.\n\n"
                  "Words only go into the app you started in, and only into a "
                  "text box (see below). Otherwise typing waits; if you click into "
                  "a text box, it catches up.\n\n"
                  "Less accurate: each part is read on its own, before the rest of "
                  "the sentence is heard, and words already typed are never changed "
                  "afterwards. Small words like \"and\" or \"on\" are the most "
                  "often wrong.",
              hint="Words appear as you say them. Less accurate than all at once "
                   "(off is recommended).")
        self.textbox = check(
            "Text box detection", TEXTBOX_ONLY, self._textbox_changed,
            tip="On by default. While you dictate, the pop-up says \"No text box "
                "selected\" when the cursor isn't in one, so you notice in time, and "
                "nothing is typed then: on a web page or in a list, typed letters would "
                "work as shortcuts.\n\nTo tell, the app asks macOS's accessibility "
                "service (the one screen readers use) what kind of control has the "
                "focus: a text box, a button, a page. Only that: never the text in it, "
                "the page or the app. Nothing is kept or written down.\n\nApps that "
                "don't say are typed into as usual.\n\nOff: macOS isn't asked, and "
                "words are typed wherever the focus is.",
            hint="Says when the cursor isn't in a text box, and types nothing then. Asks "
                 "macOS only what kind of control has the focus.")
        check("Show it at the mouse pointer", POINTER_HINT,
              option("POINTER_HINT", "pointer_hint"),
              hint="\"No text box\" also appears right beside the pointer, where your "
                   "eyes often are.")
        check("Remove filler words", REMOVE_FILLERS, option("REMOVE_FILLERS", "remove_fillers"),
              hint="Leaves out um, uh and erm.")
        check("Add a space after each dictation", ADD_SPACE, option("ADD_SPACE", "add_space"),
              hint="So two dictations in a row don't run together.")
        check("Stay in the app I started in", RETURN_FOCUS,
              option("RETURN_FOCUS", "return_focus"),
              hint="If another app pops up and takes over while you are speaking, your "
                   "words still go to the app you were in when you pressed the key.")
        replace_button = button("Word replacements…", lambda: replacements_window(self),
                                width=180)
        replace_button.setToolTip("Fix words the speech model gets wrong, such as names it "
                                  "doesn't know: what it writes, and what you want instead.")
        row(field("Words"), replace_button, None)
        note("Times are always written with a colon: \"3.47 PM\" becomes \"3:47 PM\".")
        end_tab()

        # ================= Pop-up (as on Windows) =================
        tab("Pop-up")

        def popup_changed(on):
            set_option("SHOW_POPUP", "show_popup", bool(on))
            if on:
                dictation.preview_popup()

        heading("While dictating", first=True)
        check("Show the pop-up while dictating", SHOW_POPUP, popup_changed,
              hint="Unticked, nothing appears on screen while you dictate. Notices, such "
                   "as a microphone problem, still show.")
        check("Show the icon of the app you're dictating into", SHOW_APP_ICON,
              option("SHOW_APP_ICON", "show_app_icon", preview=True))
        check("Show the name of the app you're dictating into", SHOW_APP_NAME,
              option("SHOW_APP_NAME", "show_app_name", preview=True))
        check("Show the sound wave", SHOW_WAVEFORM,
              option("SHOW_WAVEFORM", "show_waveform", preview=True))
        check("Show the timer", SHOW_TIMER, option("SHOW_TIMER", "show_timer", preview=True))
        heading("Your words")
        check("Show words as you speak", LIVE_PREVIEW, self._live_changed)
        self.lines = QtWidgets.QComboBox()
        for count in range(1, 7):
            self.lines.addItem("%d line%s" % (count, "" if count == 1 else "s"), count)
        self.lines.setCurrentIndex(LIVE_LINES - 1)
        self.lines.currentIndexChanged.connect(self._lines_changed)
        self.wide = QtWidgets.QComboBox()
        self.wide.addItem("Narrow", False)
        self.wide.addItem("Wide", True)
        self.wide.setCurrentIndex(1 if WIDE_CARD else 0)
        self.wide.currentIndexChanged.connect(self._wide_changed)
        self.wide.setToolTip("How wide the pop-up is when it shows more than one line of "
                             "words. Narrow keeps it the usual size.")
        row(field("Words shown"), self.lines, self.wide, None)
        self.text_size = QtWidgets.QComboBox()
        for size, label in TEXT_SIZES:
            self.text_size.addItem(label, size)
        self.text_size.setCurrentIndex(max(0, self.text_size.findData(TEXT_SIZE)))
        self.text_size.currentIndexChanged.connect(self._text_size_changed)
        row(field("Text size"), self.text_size, None)
        note("Reading along while you speak uses the processor: on an older Mac, "
             "turning it off makes the final text arrive a little sooner.")
        end_tab()

        # ================= Pill (split from Pop-up: the page was too long) ======
        tab("Pill")
        heading("Between dictations", first=True)
        check("Always show a small status pill on screen", ALWAYS_SHOW,
              option("ALWAYS_SHOW", "always_show", refresh=True),
              tip="Shows a small pill between dictations so you can see the app is "
                  "running. The microphone stays off until you use the hotkey. Click the "
                  "pill to dictate; right-click it for Settings.")
        check("Show it over full-screen apps too", PILL_OVER_FULLSCREEN,
              option("PILL_OVER_FULLSCREEN", "pill_over_fullscreen", refresh=True),
              tip="Off: the pill steps aside while a game, a full-screen video or "
                  "another full-screen app covers its screen, and comes back after. "
                  "The hotkey works either way.")
        check("Show the hotkey text", SHOW_HOTKEY_HINT,
              lambda value: (option("SHOW_HOTKEY_HINT", "hotkey_hint", refresh=True)(value),
                             dictation.preview_pill()))
        self.pill_mark = QtWidgets.QComboBox()
        self.pill_mark.addItem(f"{APP_TITLE} logo", "logo")
        self.pill_mark.addItem("Dot", "dot")
        self.pill_mark.addItem("None", "none")
        self.pill_mark.setCurrentIndex(max(0, self.pill_mark.findData(PILL_MARK)))
        self.pill_mark.setToolTip(f"What the small pill shows next to the hotkey: the "
                                  f"{APP_TITLE} logo (four bars), a dot, or nothing. It is "
                                  f"also a status light: with None, a dot still appears "
                                  f"while something needs you.")
        self.pill_mark.currentIndexChanged.connect(
            lambda i: (set_option("PILL_MARK", "pill_mark", self.pill_mark.itemData(i)),
                       dictation.refresh_popup(), dictation.preview_pill()))
        row(field("Pill mark"), self.pill_mark, None)
        heading("Position")

        def reset_popup():
            dictation.overlay.reset_position()
            set_option("CARD_WIDTH", "card_width", 0)
            dictation.refresh_popup()
            dictation.preview_popup()

        row(field("Pop-up"), button("Move", dictation.move_popup),
            button("Resize", dictation.resize_popup), button("Reset", reset_popup), None)
        note("You can also drag the pop-up's left or right edge while you dictate to make "
             "it wider, so more of your words fit on each line.")
        heading("Menu bar icon")
        check("Moves with your voice", TRAY_LIVE, option("TRAY_LIVE", "tray_live"),
              hint="While you dictate, the bars of the icon at the top of the screen grow "
                   "and shrink as you speak.")
        end_tab()

        # ================= Look (as on Windows) =================
        tab("Look")
        heading("Settings window", first=True)
        self.menu_theme = QtWidgets.QComboBox()
        for label, key in (("Same as macOS", "system"), ("Dark", "dark"), ("Light", "light")):
            self.menu_theme.addItem(label, key)
        self.menu_theme.setCurrentIndex(max(0, self.menu_theme.findData(MENU_THEME)))

        def menu_theme_chosen(index):
            set_option("MENU_THEME", "menu_theme", self.menu_theme.itemData(index))
            restyle_windows()
        self.menu_theme.currentIndexChanged.connect(menu_theme_chosen)
        row(field("Look"), self.menu_theme, None)
        heading("Colours")
        colour_row = [field("Colour")]
        for label, value in ACCENT_CHOICES:
            swatch = QtWidgets.QPushButton()
            swatch.setFixedSize(24, 24)
            swatch.setCursor(Qt.PointingHandCursor)
            swatch.setToolTip(label)
            swatch.setAutoDefault(False)
            swatch.clicked.connect(lambda _c=False, v=value: self._accent_chosen(v))
            self.swatches.append((swatch, value))
            colour_row.append(swatch)
        row(*(colour_row + [button("Custom", self._accent_custom), None]))
        self._paint_swatches()
        self.backgrounds = []
        background_row = [field("Background")]
        for label, value in BACKGROUND_CHOICES:
            choice = ChoiceButton(label)
            choice.setAutoDefault(False)
            choice.clicked.connect(lambda _c=False, v=value: self._background_chosen(v))
            self.backgrounds.append((choice, value))
            background_row.append(choice)
        row(*(background_row + [button("Custom", self._background_custom), None]))
        self._paint_backgrounds()
        heading("Card")
        self.card_style = QtWidgets.QComboBox()
        for key, label in CARD_STYLES:
            self.card_style.addItem(label, key)
        self.card_style.setCurrentIndex(max(0, self.card_style.findData(CARD_STYLE)))
        self.card_style.setToolTip(
            "How the pop-up stands out while you dictate. Clean: a soft shadow and a crisp "
            "edge. With a colour edge: the same, with a fine line in your accent colour. "
            "Glow: a coloured glow round it (set below).")

        def card_style_chosen(index):
            set_option("CARD_STYLE", "card_style", self.card_style.itemData(index))
            self.glow.setEnabled(CARD_STYLE == "glow")
            dictation.preview_popup()

        self.card_style.currentIndexChanged.connect(card_style_chosen)
        row(field("Style"), self.card_style, None)
        heading("Glow")
        self.glow = QtWidgets.QComboBox()
        for key, label, _amount in GLOW_LEVELS:
            self.glow.addItem(label, key)
        self.glow.setCurrentIndex(max(0, self.glow.findData(GLOW)))
        self.glow.currentIndexChanged.connect(self._glow_changed)
        self.glow.setEnabled(CARD_STYLE == "glow")
        row(field("Pop-up glow"), self.glow, None)
        self.glow_colour = QtWidgets.QComboBox()
        self.glow_colour.addItem("The app's icon colour", "app")
        self.glow_colour.addItem("My accent colour", "accent")
        self.glow_colour.addItem("Custom\u2026", "custom")
        self._show_glow_source()
        self.glow_colour.currentIndexChanged.connect(self._glow_colour_changed)
        self.glow_colour.setToolTip("The app's icon colour changes with whichever app you "
                                    "are dictating into.")
        row(field("Glow colour"), self.glow_colour, None)

        heading("Screen glow")
        # Where the screen glow goes, or none: one choice (as on Windows).
        self.glow_where = QtWidgets.QComboBox()
        for label, key in (("Off", "off"), ("Bottom (above the Dock)", "bottom"),
                           ("Top", "top"), ("Left side", "left"), ("Right side", "right"),
                           ("Full-screen border", "all")):
            self.glow_where.addItem(label, key)
        self.glow_where.setCurrentIndex(max(0, self.glow_where.findData(
            SCREEN_GLOW_EDGES if SCREEN_GLOW else "off")))
        self.glow_where.setToolTip("A soft glow at the edge of the screen while you "
                                   "dictate, which reacts to your voice.")

        def glow_where_chosen(index):
            key = self.glow_where.itemData(index)
            set_option("SCREEN_GLOW", "screen_glow", key != "off")
            if key != "off":
                set_option("SCREEN_GLOW_EDGES", "screen_glow_edges", key)
            for widget in self._glow_extras:
                widget.setEnabled(SCREEN_GLOW)
            self.glow_focus.setEnabled(SCREEN_GLOW and SCREEN_GLOW_EDGES != "all")
            if key == "off":                     # gone at once, no preview to wait out
                dictation.fx_demo_until = 0.0
                dictation.screen_glow.stop()
            else:
                dictation.demo_screen_glow()
        self.glow_where.currentIndexChanged.connect(glow_where_chosen)
        row(field("Where"), self.glow_where, None)
        self.glow_focus = QtWidgets.QComboBox()
        self.glow_focus.addItem("In the middle", "middle")
        self.glow_focus.addItem("In the corners", "corners")
        self.glow_focus.addItem("The whole edge", "even")
        self.glow_focus.setCurrentIndex(max(0, self.glow_focus.findData(SCREEN_GLOW_FOCUS)))
        self.glow_focus.setToolTip("Where a glow along one side is strongest. Greyed out "
                                   "with the full-screen border, which is even all round.")
        self.glow_focus.currentIndexChanged.connect(
            lambda index: (set_option("SCREEN_GLOW_FOCUS", "screen_glow_focus",
                                      self.glow_focus.itemData(index)),
                           dictation.demo_screen_glow()))
        row(field("Light from"), self.glow_focus, None)

        def glow_slider(label, name, key, low, high, value):
            slider = QtWidgets.QSlider(Qt.Horizontal)
            slider.setRange(low, high)
            slider.setValue(int(value))
            slider.setFixedWidth(200)

            def moved(_value=None):              # shows the result as you drag
                globals()[name] = int(slider.value())
                if not slider.isSliderDown():
                    save_setting(key, int(slider.value()))
                dictation.demo_screen_glow()
            slider.valueChanged.connect(moved)
            slider.sliderReleased.connect(lambda: set_option(name, key, int(slider.value())))
            row(field(label), slider, None)
            return slider
        strength = glow_slider("Strength", "SCREEN_GLOW_STRENGTH", "screen_glow_strength",
                               5, 100, SCREEN_GLOW_STRENGTH)

        def more_glow_options():
            """The fine-tuning in a small window of its own (as on Windows),
            built with the same helpers, pointed at this window for the moment."""
            box = QtWidgets.QDialog(self)
            box.setWindowTitle("More glow options")
            box.setStyleSheet(settings_style())
            inside = QtWidgets.QVBoxLayout(box)
            inside.setContentsMargins(20, 16, 20, 16)
            inside.setSpacing(8)
            outer, page["layout"] = page["layout"], inside
            try:
                glow_slider("Edge size", "SCREEN_GLOW_SIZE", "screen_glow_size",
                            20, 200, SCREEN_GLOW_SIZE)
                screens = QtWidgets.QComboBox()
                screens.addItem("The pop-up's screen", "popup")
                screens.addItem("All screens", "all")
                screens.addItem("Main screen", "main")
                screens.setCurrentIndex(max(0, screens.findData(SCREEN_GLOW_SCREENS)))
                screens.currentIndexChanged.connect(
                    lambda index: (set_option("SCREEN_GLOW_SCREENS", "screen_glow_screens",
                                              screens.itemData(index)),
                                   dictation.demo_screen_glow()))
                row(field("Glow on"), screens, None)

                def flow_changed(value):
                    set_option("SCREEN_GLOW_FLOW", "screen_glow_flow", bool(value))
                    dictation.demo_screen_glow()
                check("Moving light", SCREEN_GLOW_FLOW, flow_changed,
                      hint="A light travels along the glow while you dictate, and it "
                           "ripples with your voice. Off: one still colour.")
                closing = QtWidgets.QHBoxLayout()
                closing.addStretch(1)
                done = QtWidgets.QPushButton("Close")
                done.setAutoDefault(False)
                done.clicked.connect(lambda _checked=False: box.accept())
                closing.addWidget(done)
                inside.addLayout(closing)
            finally:
                page["layout"] = outer
            box.setFixedWidth(460)
            box.exec()
        more = button("More glow options\u2026", more_glow_options, width=200)
        row(field(""), more, None)
        self._glow_extras = [strength, more]
        for widget in self._glow_extras:
            widget.setEnabled(SCREEN_GLOW)
        self.glow_focus.setEnabled(SCREEN_GLOW and SCREEN_GLOW_EDGES != "all")
        heading("Outline")
        check("Outline in the accent colour", ACCENT_OUTLINE,
              option("ACCENT_OUTLINE", "accent_outline", refresh=True, preview=True))
        check("Moving light on the outline", OUTLINE_LIGHT,
              option("OUTLINE_LIGHT", "outline_light", refresh=True, preview=True))
        end_tab()

        # ================= Audio =================
        tab("Audio")
        heading("Microphone", first=True)
        self.mic = QtWidgets.QComboBox()
        self.mic.setSizeAdjustPolicy(QtWidgets.QComboBox.AdjustToMinimumContentsLengthWithIcon)
        self.mic.setMinimumContentsLength(12)
        self.mic.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self._fill_microphones()
        self.mic.currentIndexChanged.connect(self._mic_changed)
        line = row(field("Input"), self.mic, button("Refresh", self._fill_microphones))
        line.setStretch(1, 1)
        self.mic_test = button("Test", self._test_mic, width=84)
        self.mic_bar = QtWidgets.QProgressBar()
        self.mic_bar.setRange(0, 100)
        self.mic_bar.setTextVisible(False)
        self.mic_bar.setMinimumWidth(60)
        self.mic_note = QtWidgets.QLabel("")
        self.mic_note.setObjectName("info")
        line = row(field("Level"), self.mic_test, self.mic_bar, self.mic_note)
        line.setStretch(2, 1)
        self.mic_heard = QtWidgets.QLabel("")   # the words heard during a test
        self.mic_heard.setWordWrap(True)
        self.mic_heard.setContentsMargins(112, 0, 0, 0)
        self.mic_heard.setVisible(False)
        page["layout"].addWidget(self.mic_heard)
        note("Test listens for about 6 seconds, then shows the words it heard. Nothing "
             "is typed anywhere and nothing is kept.")
        self._test_rec = None
        self._test_timer = QTimer(self)
        self._test_timer.setInterval(50)
        self._test_timer.timeout.connect(self._test_tick)
        self.limit = QtWidgets.QComboBox()
        limits = sorted(set(TIME_LIMITS) | {MAX_RECORD_SECONDS})
        for seconds in limits:
            self.limit.addItem("%d minute%s" % (seconds // 60, "" if seconds == 60 else "s")
                               if seconds % 60 == 0 else "%d seconds" % seconds, seconds)
        self.limit.setCurrentIndex(max(0, self.limit.findData(MAX_RECORD_SECONDS)))
        self.limit.currentIndexChanged.connect(
            lambda i: set_option("MAX_RECORD_SECONDS", "max_seconds",
                                 int(self.limit.itemData(i))))
        row(field("Time limit"), self.limit, None)
        note("A dictation ends by itself after this long: a safety net if the key gets "
             "stuck.")

        heading("Sounds")
        check("Play a sound when dictation starts and finishes", SOUNDS,
              lambda on: set_option("SOUNDS", "sounds", bool(on)))
        self.speaker = QtWidgets.QComboBox()
        self.speaker.setFixedWidth(250)
        self.speaker.addItem("Mac default", "")
        outputs = output_devices()
        if SOUND_DEVICE and SOUND_DEVICE not in outputs:
            outputs.insert(0, SOUND_DEVICE)      # chosen earlier, unplugged right now
        for name in outputs:
            self.speaker.addItem(name, name)
        self.speaker.setCurrentIndex(max(0, self.speaker.findData(SOUND_DEVICE)))

        def speaker_changed(index):
            set_option("SOUND_DEVICE", "sound_device", self.speaker.itemData(index) or "")
            play_sound("start", force=True)      # hear where it now plays
        self.speaker.currentIndexChanged.connect(speaker_changed)
        row(field("Output"), self.speaker, None)
        self.sound_set = QtWidgets.QComboBox()
        for key, label in SOUND_SETS:
            self.sound_set.addItem(label, key)
        self.sound_set.setCurrentIndex(max(0, self.sound_set.findData(SOUND_SET)))
        self.sound_set.currentIndexChanged.connect(self._sound_set_changed)
        row(field("Sound set"), self.sound_set, button("Play", self._play_both, width=84), None)
        self.own_rows = []
        for which, label in (("start", "Start sound"), ("finish", "Finish sound")):
            name = QtWidgets.QLabel("")
            name.setObjectName("info")
            browse = button("Choose\u2026", lambda _c=False, w=which: self._browse_sound(w),
                            width=100)
            title = field(label)
            row(title, browse, name, None)
            self.own_rows.append((which, title, browse, name))
        self.volume = QtWidgets.QSlider(Qt.Horizontal)
        self.volume.setRange(0, 100)
        self.volume.setValue(int(round(SOUND_VOLUME * 100)))
        self.volume.setFixedWidth(200)
        self.volume.sliderReleased.connect(self._volume_changed)
        self.volume.valueChanged.connect(
            lambda _v: None if self.volume.isSliderDown() else self._volume_changed())
        self.volume_label = field("Volume")
        row(self.volume_label, self.volume, None)
        self._refresh_own_rows()
        end_tab()

        # ================= Model =================
        tab("Model")
        heading("Speech model", first=True)
        self.model = QtWidgets.QComboBox()
        for name, label, _quant, _size in MODELS:
            self.model.addItem(label, name)
        self.model.setCurrentIndex(max(0, self.model.findData(MODEL)))
        self.model.currentIndexChanged.connect(self._model_changed)
        row(field("Model"), self.model, None)
        self.model_where = QtWidgets.QLabel("")
        self.model_where.setObjectName("info")
        self.model_where.setTextInteractionFlags(Qt.TextSelectableByMouse)
        row(field("Stored in"), self.model_where, None)
        note("Runs on this Mac. Choosing a model that is not on this Mac yet asks first, "
             "then restarts to download it from this project's own model releases.")
        heading("Files")
        self.check_button = button("Check files", self._check_files)
        self.model_button = button("Remove model", self._remove_or_download)
        row(self.check_button, button("Open folder", self._open_model_folder),
            self.model_button, None)
        self.check_note = note("Check files compares the model's files with their known "
                               "fingerprints (SHA-256). Removing frees about 660 MB; it can "
                               "be downloaded again later.")
        self._show_model()
        end_tab()

        # ================= Privacy =================
        tab("Privacy")
        heading("Updates", first=True)
        self.app_updates = check(
            "Check for %s updates at startup" % APP_TITLE, CHECK_APP_UPDATES,
            self._app_updates_changed,
            tip="Off by default. With this ticked, every start asks github.com whether a "
                "newer version has been published, and tells you once if there is. "
                "Nothing is downloaded or installed.")
        self.app_update_button = button("Check now", self._check_app_now, width=110)
        page["layout"].removeWidget(self.app_updates)
        row(self.app_updates, None, self.app_update_button)
        note("You have version %s. Off: %s never goes online for this." % (VERSION, APP_TITLE))
        heading("Clipboard and kept text")
        self.paste_mode = check(
            "Paste using the clipboard instead of typing", not TYPE_TEXT,
            self._paste_mode_changed,
            tip="Off by default. The words are normally typed as keystrokes, so the "
                "clipboard is not used.\n\nWith this on, the text is pasted instead: "
                "it borrows the clipboard for a second, then puts back what you had "
                "copied. Pasting is quicker for long text, but other apps that watch "
                "the clipboard could see the text during that second.")
        minutes = round(KEEP_LAST_SECONDS / 60.0)
        self.keep_last = check(
            "Missed text safety", KEEP_LAST, self._keep_last_changed,
            tip="Why this exists: if no text box is selected when you finish speaking, "
                "the words have nowhere to go and are lost.\n\nWith this on, the app "
                "keeps your last dictation for %d minutes so a quick tap of the hotkey "
                "types it again once you have clicked the right box.\n\nOff by "
                "default, because it means holding on to your words after you have "
                "finished. They stay in this app's memory only: not written to disk or "
                "left on the clipboard." % minutes,
            hint="Keeps your last dictation for %d minutes so you can type it again "
                 "if needed." % minutes)
        self.paste_key = QtWidgets.QComboBox()
        self.paste_key.addItem("only the tap", "")
        for key, (_code, _mask, name) in HOTKEYS.items():
            self.paste_key.addItem("also " + name, key)

        def show_paste():
            self.paste_key.blockSignals(True)
            self.paste_key.setCurrentIndex(max(0, self.paste_key.findData(PASTE_HOTKEY)))
            for i in range(self.paste_key.count()):
                item = self.paste_key.model().item(i)
                if item is not None:
                    item.setEnabled(self.paste_key.itemData(i) not in (HOTKEY, ACTION_HOTKEY)
                                    or not self.paste_key.itemData(i))
            self.paste_key.blockSignals(False)
            self.paste_key.setEnabled(KEEP_LAST)
        self._show_paste = show_paste

        def paste_chosen(index):
            key = self.paste_key.itemData(index) or ""
            if key in (HOTKEY, ACTION_HOTKEY):
                key = ""
            set_option("PASTE_HOTKEY", "paste_hotkey", key)
            dictation.hotkey.set_paste(key)
            show_paste()
        self.paste_key.currentIndexChanged.connect(paste_chosen)
        show_paste()
        row(field("Type again"), self.paste_key, None)
        note("A quick tap of the dictation key types the kept text again; you can "
             "also give it a key of its own (tapped on its own).")
        heading("Move settings to another computer")
        note("Your choices as one line of text, to copy and paste on another computer "
             "(Mac or PC). Nothing private is included.")
        button_grid(button("Export settings", lambda: export_settings_window(self)),
                    button("Import settings", lambda: import_settings_window(self)))
        heading("Help and information")
        network = QtWidgets.QLabel(network_words()[0].upper() + network_words()[1:])
        network.setObjectName("info")
        network.setToolTip(f"{APP_TITLE} blocks its own internet access while it runs.")
        row(field("Internet"), network, None)
        button_grid(button(f"About {APP_TITLE}", dictation.show_about),
                    button("Open data folder", lambda: QDesktopServices.openUrl(
                        QUrl.fromLocalFile(SUPPORT_DIR))),
                    button("Report a problem", lambda: open_feedback_page(self, "bug")),
                    button("Suggest an idea", lambda: open_feedback_page(self, "idea")))
        end_tab()

        tabs.setCurrentIndex(min(SettingsWindow._last_tab, tabs.count() - 1))
        sidebar.setCurrentRow(tabs.currentIndex())
        tabs.currentChanged.connect(self._tab_changed)

        bottom = QtWidgets.QHBoxLayout()
        bottom.addWidget(button("Reset all settings", self._reset_all))
        bottom.addStretch(1)
        quit_button = button(f"Quit {APP_TITLE}", dictation.quit)
        quit_button.setObjectName("danger")      # red: it closes the application
        bottom.addWidget(quit_button)
        bottom.addWidget(button("Close", self.close, width=84))
        outer.addLayout(bottom)

    # -- size: fits the tab showing, never more than the screen ---------------
    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._fit_height)

    def _fit_height(self):
        """One size for every page: as tall as the tallest one (the window
        changing height on each page didn't look smooth on a Mac).
        Never taller than the screen: then a page scrolls instead."""
        try:
            area = self._tabs.currentWidget()
            content = max(self._tabs.widget(i).widget().sizeHint().height()
                          for i in range(self._tabs.count()))
            around = self.height() - area.viewport().height()
            screen = self.screen() or QGuiApplication.primaryScreen()
            room = screen.availableGeometry()
            title_bar = max(0, self.frameGeometry().height() - self.height())
            limit = room.height() - title_bar - 16
            height = max(320, min(around + content, limit))
            if height != self.height():
                self.resize(self.width(), height)
            frame = self.frameGeometry()
            if frame.bottom() > room.bottom() or frame.top() < room.top():
                self.move(self.x(), max(room.top(), room.bottom() - frame.height()))
        except Exception:
            log.exception("settings height")

    def _tab_changed(self, index):
        SettingsWindow._last_tab = int(index)     # (the window keeps its size)

    def show_tab(self, title):
        if title in self.TABS:
            self._tabs.setCurrentIndex(self.TABS.index(title))

    def done(self, result):
        # Every way out (Close, the red button, Esc) comes through here: the
        # microphone test must never be left running.
        self._stop_test()
        self.mic_heard.clear()
        super().done(result)

    def closeEvent(self, event):
        self._stop_test()
        super().closeEvent(event)

    # -- General ----------------------------------------------------------------
    def _login_changed(self, on):
        if not set_start_at_login(bool(on)):
            self.login.blockSignals(True)
            self.login.setChecked(starts_at_login())
            self.login.blockSignals(False)
            dialog("Start at login", "macOS did not accept the change. You can also "
                   "manage it in System Settings › General › Login Items.", parent=self)

    def _show_permissions(self):
        def show(label, ok, words):
            colour = ACCENT if ok else "#F2B45A"
            label.setText(f"<span style='color:{colour}'>\u25cf</span>&nbsp; {words}")
        mic = mic_permission()
        typing = bool(self.dictation.hotkey.port) or can_control_keyboard()
        show(self.perm_typing, typing, "Allowed" if typing else "Not allowed")
        show(self.perm_mic, mic == MIC_OK,
             {MIC_OK: "Allowed", MIC_UNKNOWN: "Not asked yet"}.get(mic, "Not allowed"))

    # -- Sounds (as on Windows) ---------------------------------------------------
    def _refresh_own_rows(self):
        own = SOUND_SET == "custom"
        for which, _title, _browse, name in self.own_rows:
            path = SOUND_START_FILE if which == "start" else SOUND_FINISH_FILE
            if path and os.path.isfile(path):
                text = os.path.basename(path) + ("" if own else "  (not in use)")
            elif path:
                text = "file not found"
            else:
                text = "none chosen"
            name.setText(text)
        self.volume.setEnabled(not own)          # your own files play at their own level
        self.volume_label.setEnabled(not own)

    def _sound_set_changed(self, index):
        set_option("SOUND_SET", "sound_set", self.sound_set.itemData(index))
        self._refresh_own_rows()
        if SOUND_SET != "custom":
            play_sound("start", force=True)

    def _browse_sound(self, which):
        path, _filter = QtWidgets.QFileDialog.getOpenFileName(
            self, "Choose the %s sound" % which, os.path.expanduser("~"),
            "WAV sounds (*.wav)")
        if not path:
            return
        set_option("SOUND_START_FILE" if which == "start" else "SOUND_FINISH_FILE",
                   "sound_start" if which == "start" else "sound_finish", path)
        if SOUND_SET != "custom":                # choosing a file means you want it used
            self.sound_set.setCurrentIndex(max(0, self.sound_set.findData("custom")))
        self._refresh_own_rows()
        play_sound(which, force=True)

    def _play_both(self):
        play_sound("start", force=True)
        QTimer.singleShot(700, lambda: play_sound("finish", force=True))

    def _volume_changed(self):
        set_option("SOUND_VOLUME", "volume", self.volume.value() / 100.0)
        play_sound("start", force=True)

    # -- Updates ------------------------------------------------------------------
    def _app_updates_changed(self, on):
        if on and not ask_app_update_check(self, at_startup=True):
            self.app_updates.blockSignals(True)  # untick it again, quietly
            self.app_updates.setChecked(False)
            self.app_updates.blockSignals(False)
            on = False
        set_option("CHECK_APP_UPDATES", "check_app_updates", bool(on))

    def _check_app_now(self):
        if not ask_app_update_check(self):
            return
        self.app_update_button.setEnabled(False)
        self.app_update_button.setText("Checking\u2026")

        def done():
            try:
                self.app_update_button.setEnabled(True)
                self.app_update_button.setText("Check now")
            except RuntimeError:
                pass                             # the window was closed meanwhile
        run_app_update_check(self, manual=True, done=done)

    # -- Clipboard and kept text --------------------------------------------------
    def _paste_mode_changed(self, on):
        if not on:
            set_option("TYPE_TEXT", "type_text", True)   # typing: clipboard untouched
            return
        if dialog("Paste using the clipboard?",
                  "Instead of typing your words, the app will put them on the clipboard "
                  "for about a second, paste them, and then put back what you had "
                  "copied.\n\nThey are marked so that clipboard managers which follow "
                  "the usual convention leave them out of their history, but other apps "
                  "that watch the clipboard could see them during that second.",
                  buttons=("Turn on", "Keep typing"), parent=self,
                  headline="Your words will pass through the clipboard") == "Turn on":
            set_option("TYPE_TEXT", "type_text", False)
        else:
            self.paste_mode.blockSignals(True)
            self.paste_mode.setChecked(False)
            self.paste_mode.blockSignals(False)
            set_option("TYPE_TEXT", "type_text", True)

    def _keep_last_changed(self, on):
        if not on:
            set_option("KEEP_LAST", "keep_last", False)
            self.dictation.forget()              # drop anything being held, now
            self._show_paste()
            return
        minutes = round(KEEP_LAST_SECONDS / 60.0)
        if dialog("Turn on missed text safety?",
                  "This is so a quick tap of the hotkey can type it again if it missed "
                  "the text box.\n\nThe words are held in this app's memory only. "
                  "%s does not write them to disk or leave them on the clipboard, and "
                  "they are dropped after %d minutes (or replaced by your next dictation), or when "
                  "the app closes." % (APP_TITLE, minutes),
                  buttons=("Turn on", "Keep off"), parent=self,
                  headline="Your last dictation will be kept for %d minutes" % minutes
                  ) == "Turn on":
            set_option("KEEP_LAST", "keep_last", True)
        else:
            self.keep_last.blockSignals(True)
            self.keep_last.setChecked(False)
            self.keep_last.blockSignals(False)
            set_option("KEEP_LAST", "keep_last", False)
        self._show_paste()

    # -- Typing -----------------------------------------------------------------
    def _textbox_changed(self, on):
        if not on and dialog(
                "Text box detection", "With it off, your words are typed wherever the "
                "focus is when you let go of the key: on a web page or in a list, letters "
                "can work as shortcuts, and Space can scroll or press a button.",
                buttons=("Switch it off", "Keep it on"), parent=self,
                headline="Switch text box detection off?") != "Switch it off":
            self.textbox.blockSignals(True)
            self.textbox.setChecked(True)
            self.textbox.blockSignals(False)
            return
        set_option("TEXTBOX_ONLY", "textbox_only", bool(on))

    # -- Pop-up and Look (as on Windows) ------------------------------------------
    def _live_changed(self, on):
        set_option("LIVE_PREVIEW", "live_preview", bool(on))
        self.dictation.refresh_popup()
        self.dictation.preview_popup()

    def _lines_changed(self, index):
        set_option("LIVE_LINES", "live_lines", int(self.lines.itemData(index)))
        self.dictation.refresh_popup()

    def _wide_changed(self, index):
        set_option("WIDE_CARD", "wide_card", bool(self.wide.itemData(index)))
        set_option("CARD_WIDTH", "card_width", 0)
        self.dictation.refresh_popup()

    def _text_size_changed(self, index):
        set_option("TEXT_SIZE", "text_size", int(self.text_size.itemData(index)))
        self.dictation.refresh_popup()
        self.dictation.preview_popup()

    def _glow_changed(self, index):
        set_option("GLOW", "glow", self.glow.itemData(index))
        self.dictation.refresh_popup()
        self.dictation.preview_popup()

    def _paint_swatches(self):
        ratio = max(1.0, float(self.devicePixelRatioF())) * 2.0
        for swatch, value in self.swatches:
            swatch.setStyleSheet("background: transparent; border: none; padding: 0; "
                                 "min-height: 0;")
            swatch.setIcon(QIcon(swatch_picture(value, value.lower() == ACCENT.lower(), ratio)))
            swatch.setIconSize(QtCore.QSize(24, 24))

    def _paint_backgrounds(self):
        for choice, value in self.backgrounds:
            choice.setChosen(value.lower() == POPUP_BG.lower())

    def _accent_chosen(self, colour):
        set_option("ACCENT", "accent", colour)
        self._paint_swatches()
        self._paint_backgrounds()
        self.setStyleSheet(settings_style())     # ticks and tabs follow the colour
        self.dictation.overlay.update()
        self.dictation.preview_popup()

    def _background_chosen(self, colour):
        set_option("POPUP_BG", "popup_bg", colour)
        self._paint_backgrounds()
        self.dictation.overlay.update()
        self.dictation.preview_popup()

    def _pick_colour(self, title, start, try_out):
        """A colour picker that shows each colour on the pop-up as you move
        through them. Returns the chosen colour, or None if cancelled (then
        try_out is called with the starting colour again)."""
        picker = QtWidgets.QColorDialog(QColor(start), self)
        picker.setWindowTitle(title)
        picker.setOption(QtWidgets.QColorDialog.DontUseNativeDialog, True)   # live updates
        overlay = self.dictation.overlay
        if self.dictation._idle():
            overlay.preview(ms=None)             # stays up while you choose

        def tried(colour):
            try_out(colour.name())
            overlay.update()
        picker.currentColorChanged.connect(tried)
        chosen = picker.exec() == QtWidgets.QDialog.Accepted
        if not chosen:
            try_out(start)
        overlay.update()
        if overlay.previewing:
            overlay.dismiss()
        return picker.selectedColor().name() if chosen else None

    def _accent_custom(self):
        chosen = self._pick_colour("Accent colour", ACCENT,
                                   lambda c: globals().__setitem__("ACCENT", c))
        if chosen:
            self._accent_chosen(chosen)

    def _background_custom(self):
        chosen = self._pick_colour("Pop-up background", POPUP_BG,
                                   lambda c: globals().__setitem__("POPUP_BG", c))
        if chosen:
            self._background_chosen(chosen)

    def _show_glow_source(self):
        source = "app" if GLOW_FROM_APP else ("custom" if GLOW_COLOUR else "accent")
        self.glow_colour.blockSignals(True)
        self.glow_colour.setCurrentIndex(max(0, self.glow_colour.findData(source)))
        self.glow_colour.blockSignals(False)

    def _glow_colour_changed(self, index):
        choice = self.glow_colour.itemData(index)
        if choice == "custom":
            before, was_app = GLOW_COLOUR, GLOW_FROM_APP
            globals()["GLOW_FROM_APP"] = False   # so the picker's preview shows it
            picked = self._pick_colour("Glow colour", GLOW_COLOUR or ACCENT,
                                       lambda c: globals().__setitem__("GLOW_COLOUR", c))
            if picked:
                set_option("GLOW_FROM_APP", "glow_from_app", False)
                set_option("GLOW_COLOUR", "glow_colour", picked)
            else:
                globals()["GLOW_COLOUR"], globals()["GLOW_FROM_APP"] = before, was_app
                self._show_glow_source()
            return
        set_option("GLOW_FROM_APP", "glow_from_app", choice == "app")
        if choice == "accent":
            set_option("GLOW_COLOUR", "glow_colour", "")
        self.dictation.preview_popup()

    # -- Audio -------------------------------------------------------------------
    def _fill_microphones(self):
        self.mic.blockSignals(True)
        self.mic.clear()
        self.mic.addItem("The Mac's default", "")
        names = input_devices()
        if MIC_DEVICE and MIC_DEVICE not in names:
            names.insert(0, MIC_DEVICE)          # chosen earlier, unplugged right now
        for name in names:
            self.mic.addItem(name, name)
        self.mic.setCurrentIndex(max(0, self.mic.findData(MIC_DEVICE)))
        self.mic.blockSignals(False)

    def _mic_changed(self, index):
        set_option("MIC_DEVICE", "mic", self.mic.itemData(index) or "")

    def _test_mic(self):
        if self._test_rec:
            self._finish_test()
            return
        if mic_permission() != MIC_OK:
            self.dictation.on_press_mic_check_only()
            self._show_permissions()
            return
        self._test_rec = Recorder()
        try:
            self._test_rec.start()
        except Exception:
            log.exception("mic test")
            self._test_rec = None
            self.mic_note.setText("Microphone not detected")
            return
        self.mic_test.setText("Stop")
        self.mic_note.setText("Listening…")
        self.mic_heard.setVisible(False)
        self._test_timer.start()

    def _test_tick(self):
        rec = self._test_rec
        if not rec:
            self._test_timer.stop()
            return
        self.mic_bar.setValue(int(min(100, rec.level * 900)))
        if time.monotonic() - rec.started > 6:
            self._finish_test()

    def _finish_test(self):
        rec, self._test_rec = self._test_rec, None
        self._test_timer.stop()
        self.mic_bar.setValue(0)
        self.mic_test.setText("Test")
        if not rec:
            return
        audio, rate = rec.stop()
        peak = float(np.max(np.abs(audio))) if audio.size else 0.0
        if peak < 1e-4:
            self.mic_note.setText("No sound from the microphone")
            return
        if self.dictation.model is None:
            self.mic_note.setText("Heard sound (the model is still loading)")
            return
        self.mic_note.setText("Reading…")
        self.mic_test.setEnabled(False)
        d = self.dictation

        def read():
            try:
                text = clean_text(d.model.recognize(audio, sample_rate=rate).strip()) \
                    if d.has_speech(audio, rate) else ""
            except Exception:
                text = ""
            self._relay.done.emit(("test", text, peak))
        threading.Thread(target=read, daemon=True).start()

    def _stop_test(self):
        if self._test_rec:
            self._test_rec.close()
            self._test_rec = None
        self._test_timer.stop()

    # -- Model --------------------------------------------------------------------
    def _show_model(self):
        folder = local_model_dir()
        self.model_where.setText(models_root().replace(HOME, "~") if folder
                                 else "Not on this Mac")
        self.model_where.setToolTip(folder.replace(HOME, "~") if folder else "")
        self.model_button.setText("Remove model" if folder else "Download model")

    def _model_changed(self, index):
        name = self.model.itemData(index)
        if name == MODEL:
            return
        have = bool(local_model_dir(name))
        if have:
            answer = dialog("Switch speech model?",
                            f"This model is already on this Mac. {APP_TITLE} restarts to "
                            f"load it, and stays offline.",
                            buttons=("Switch and restart", "Cancel"), parent=self,
                            headline=f"Switch to {model_label(name)}")
        else:
            answer = dialog("Download speech model?",
                            download_question_words(name) + f"\n\n{APP_TITLE} restarts "
                            f"to download it.", buttons=("Download and restart", "Cancel"),
                            parent=self, headline="This application will go online")
        if answer in ("Switch and restart", "Download and restart"):
            save_setting("model", name)
            if not have:
                # The yes just given covers this one restart only.
                save_setting("download_yes_once", name)
            restart_app()
        else:
            self.model.blockSignals(True)
            self.model.setCurrentIndex(max(0, self.model.findData(MODEL)))
            self.model.blockSignals(False)

    def _remove_or_download(self):
        d = self.dictation
        if not local_model_dir():
            d.offer_download()
            return
        if dialog("Remove the speech model?",
                  f"This deletes the model's files from this Mac (about "
                  f"{folder_bytes(model_dir()) // (1024 * 1024)} MB). {APP_TITLE} stays open "
                  f"so you can still change settings, but dictation won't work until the "
                  f"model is downloaded again. Your settings are kept.",
                  buttons=("Remove", "Cancel"), parent=self,
                  headline="Delete the speech model from this Mac") != "Remove":
            return
        if not d.unload_model():
            dialog("Still loading", "Please wait until it has loaded, then try again.",
                   parent=self, headline="The speech model is still loading")
            return
        freed = forget_model()
        self._show_model()
        d.notice(d.NO_MODEL, stays=True, action=d.offer_download)
        dialog("Speech model removed",
               f"Deleted from this Mac: about {freed // (1024 * 1024)} MB.\n\nDictation is "
               f"off until the model is downloaded again: click “Download model” here, or "
               f"the pill.", parent=self, headline="The speech model has been removed")

    def _open_model_folder(self):
        folder = local_model_dir()
        if folder:
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            dialog("Speech model", "There is no model folder to open yet.", parent=self,
                   headline="The model is not on this Mac")

    def _check_files(self):
        self.check_button.setEnabled(False)
        self.check_note.setText("Checking… (this takes a few seconds)")

        def work():
            try:
                problems = check_model_files()
            except Exception as exc:
                problems = [f"could not be read ({exc})"]
            self._relay.done.emit(("check", problems))
        threading.Thread(target=work, daemon=True).start()

    # -- results from helper threads --------------------------------------------
    def _helper_done(self, result):
        if result[0] == "check":
            problems = result[1]
            self.check_button.setEnabled(True)
            if problems:
                self.check_note.setText("Problems found:\n" + "\n".join(problems))
                log.warning("model check: %d problems", len(problems))
            else:
                self.check_note.setText("All files match their known fingerprints.")
        elif result[0] == "test":
            _kind, text, peak = result
            self.mic_test.setEnabled(True)
            self.mic_note.setText("Quiet: speak up or move closer" if peak < 0.02 else "")
            self.mic_heard.setText(f"Heard: {text}" if text else "Heard no words.")
            self.mic_heard.setVisible(True)
            self._fit_height()

    def _reset_all(self):
        if dialog("Reset all settings",
                  "All your choices go back to how they were at first (word replacements "
                  "too), and Start at login is switched off. The speech model is kept. "
                  f"{APP_TITLE} restarts.",
                  buttons=("Reset and restart", "Cancel"), parent=self,
                  headline="Reset all settings?") == "Reset and restart":
            reset_all_settings()


# ---------------------------------------------------------------------------
# "Before you start": carried over from the Windows version as it is (hold
# for 3 seconds to confirm), so what it says gets read. Mac edits marked.
# ---------------------------------------------------------------------------
class HoldButton(QtWidgets.QPushButton):
    """A button that has to be held down for a few seconds: it fills up while
    held and counts down; letting go early drains it back and starts over.
    Holding Space or Enter works the same, for the keyboard. Used where a
    quick click should not be enough, so that the words above it get read."""

    completed = QtCore.Signal()
    FILL_STYLE = "lighter"                       # how it fills while held (see paintEvent)
    FRAME_MS = 8                                 # redraw often, on a precise timer
    DRAIN = 0.25                                 # seconds to empty after letting go

    def __init__(self, text, seconds=3.0):
        super().__init__(text)
        self._label = text
        self._seconds = float(seconds)
        self._held_since = None                  # when the current hold began
        self._held_from = 0.0                    # the fill when it began
        self._drain_since = None                 # when a let-go began draining
        self._drain_from = 0.0
        self._fill = 0.0                         # 0..1, what is drawn
        self._done = False
        self._shown_number = None
        self._held_key = None                    # Space/Enter, if held by keyboard
        self._timer = QtCore.QTimer(self)
        # Windows' ordinary timers tick unevenly (about every 15 ms, sometimes
        # 31): a precise one keeps the fill moving smoothly.
        self._timer.setTimerType(Qt.PreciseTimer)
        self._timer.setInterval(self.FRAME_MS)
        self._timer.timeout.connect(self._tick)
        self.setObjectName("primary")
        self.setProperty("hold", True)           # its own hover look (settings_style)
        # A fixed width, so the countdown text never makes the button resize.
        metrics = self.fontMetrics()
        widest = max(metrics.horizontalAdvance(text),
                     metrics.horizontalAdvance("Keep holding… 3"))
        self.setMinimumWidth(widest + 48)

    def reset(self):
        """Ready to be held again (coming back to its page)."""
        self._timer.stop()
        self._done = False
        self._held_since = self._drain_since = None
        self._fill = 0.0
        self._shown_number = None
        self.setText(self._label)
        self.update()

    def _begin(self):
        if self._done or self._held_since is not None:
            return
        self._held_since = time.monotonic()
        self._held_from = self._fill             # carries on from where a drain got to
        self._drain_since = None
        self._timer.start()
        self._tick()

    def _cancel(self):
        if self._done or self._held_since is None:
            return
        self._held_since = None
        self._drain_since = time.monotonic()     # empty smoothly, not in one jump
        self._drain_from = self._fill
        self._shown_number = None
        self.setText(self._label)
        self._timer.start()

    def _tick(self):
        now = time.monotonic()
        if self._held_since is not None:
            self._fill = min(1.0, self._held_from + (now - self._held_since) / self._seconds)
            left = self._seconds * (1.0 - self._fill)
            if self._fill >= 1.0:
                self._done = True
                self._timer.stop()
                self.setText(self._label)
                self.update()
                # A held key (Space/Enter) stays down after this: until it is
                # really let go, its repeats are swallowed, or they would press
                # whatever button comes next (Quit, or even Download).
                # (Mac: no key swallowing needed; the window closes at once.)
                # A moment on the full button, then on: it feels finished.
                QtCore.QTimer.singleShot(120, self.completed.emit)
                return
            number = max(1, int(math.ceil(left - 1e-6)))
            if number != self._shown_number:     # only when it changes: no re-measuring
                self._shown_number = number
                self.setText("Keep holding… %d" % number)
        elif self._drain_since is not None:
            gone = (now - self._drain_since) / self.DRAIN
            self._fill = max(0.0, self._drain_from * (1.0 - gone))
            if self._fill <= 0.0:
                self._drain_since = None
                self._timer.stop()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._held_key = None                # held with the mouse, not a key
            self.setFocus()
            self._begin()
        event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._cancel()
        event.accept()

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if not event.isAutoRepeat():
                self._held_key = event.key()
                self._begin()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() in (Qt.Key_Space, Qt.Key_Return, Qt.Key_Enter):
            if not event.isAutoRepeat():
                self._cancel()
            event.accept()
            return
        super().keyReleaseEvent(event)

    def focusOutEvent(self, event):
        self._cancel()                           # clicked or tabbed away: start over
        super().focusOutEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        if self._fill <= 0.0:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        inner = QtCore.QRectF(self.rect()).adjusted(1, 1, -1, -1)
        edge = inner.left() + inner.width() * self._fill
        path = QtGui.QPainterPath()
        path.addRoundedRect(inner, 6, 6)
        p.setClipPath(path)
        soft = 14.0
        style = self.FILL_STYLE
        if style in ("deeper", "lighter"):
            # The button fills with a lighter (or deeper) shade of its own
            # colour (lighter: a white sweep looked washed out, a
            # darker one too heavy).
            deep = QtGui.QColor(ACCENT).lighter(122) if style == "lighter"                 else QtGui.QColor(ACCENT).darker(122)
            clear = QtGui.QColor(deep)
            clear.setAlpha(0)
            sweep = QtGui.QLinearGradient(QtCore.QPointF(edge - soft, 0), QtCore.QPointF(edge, 0))
            sweep.setColorAt(0.0, deep)
            sweep.setColorAt(1.0, clear)
            p.setBrush(QtGui.QBrush(sweep))
            p.drawRect(QtCore.QRectF(inner.left(), inner.top(), edge - inner.left(),
                                     inner.height()))
        elif style == "bar":
            # A slim bar along the bottom of the button fills up.
            p.setBrush(QtGui.QColor(16, 17, 20, 150))
            p.drawRect(QtCore.QRectF(inner.left(), inner.bottom() - 3.0, edge - inner.left(), 3.0))
        else:
            # The first look: a light sweep.
            sweep = QtGui.QLinearGradient(QtCore.QPointF(edge - soft, 0), QtCore.QPointF(edge, 0))
            sweep.setColorAt(0.0, QtGui.QColor(255, 255, 255, 85))
            sweep.setColorAt(1.0, QtGui.QColor(255, 255, 255, 0))
            p.setBrush(QtGui.QBrush(sweep))
            p.drawRect(QtCore.QRectF(inner.left(), inner.top(), edge - inner.left(),
                                     inner.height()))
        p.setClipping(False)
        p.setPen(QtGui.QColor("#101114"))        # the words stay sharp on top
        p.setFont(self.font())
        p.drawText(self.rect(), Qt.AlignCenter, self.text())
        p.end()


def hold_confirm_window(parent, title, headline, paragraphs, hold_text, cancel_text):
    """A window whose yes has to be held down for three seconds (see
    HoldButton), so that what it says gets read. Returns True if confirmed;
    the other button, or closing the window, gives False."""
    box = QtWidgets.QDialog(parent)
    box.setWindowTitle(title)
    box.setWindowIcon(app_icon())
    box.setWindowFlags(Qt.Dialog | Qt.WindowTitleHint | Qt.WindowCloseButtonHint
                       | Qt.WindowStaysOnTopHint)
    box.setStyleSheet(settings_style() + """
QLabel#headline { color: #FFFFFF; font-size: 17px; font-weight: 600; }
QLabel#body { color: #C4C6CF; font-size: 13px; }
QPushButton { padding: 7px 16px; }
QPushButton#primary { background: %(accent)s; color: #101114; border: 1px solid %(accent)s;
    font-weight: 600; }
QPushButton#primary:hover { background: %(accent)s; border-color: #FFFFFF; }
""" % {"accent": ACCENT})
    layout = QtWidgets.QVBoxLayout(box)
    layout.setContentsMargins(26, 22, 26, 20)
    layout.setSpacing(12)
    for words, name in [(headline, "headline")] + [(text, "body") for text in paragraphs]:
        label = QtWidgets.QLabel(words)
        label.setObjectName(name)
        label.setWordWrap(True)
        label.setFixedWidth(420)
        layout.addWidget(label)
    layout.addSpacing(6)
    buttons = QtWidgets.QHBoxLayout()
    cancel = QtWidgets.QPushButton(cancel_text)
    cancel.clicked.connect(lambda _checked=False: box.reject())
    hold = HoldButton(hold_text)
    hold.completed.connect(box.accept)
    buttons.addWidget(cancel)
    buttons.addStretch(1)
    buttons.addWidget(hold)
    layout.addLayout(buttons)
    hint = QtWidgets.QLabel("Press and hold the button for 3 seconds (or hold Space).")
    hint.setObjectName("info")
    hint.setAlignment(Qt.AlignRight)
    layout.addWidget(hint)
    hold.setFocus()
    bring_to_front()                              # Mac: in front of other apps
    return box.exec() == QtWidgets.QDialog.Accepted


# ---------------------------------------------------------------------------
# Is there a newer version? (as on Windows; off unless switched on, and each
# time only after "This application will go online")
# ---------------------------------------------------------------------------
APP_RELEASES_PAGE = "https://github.com/%s/releases/latest" % APP_REPO
APP_UPDATE_WARNING = (
    "%(app)s will connect to api.github.com (GitHub) to read the version number of "
    "its latest published release. That is a third-party website that we do not run "
    "or control.\n\nOnly GitHub's servers are let through, and only for this; the "
    "network block is closed again straight after. Nothing about you or your use of %(app)s "
    "is sent, apart from what any visit to a website involves (such as your IP "
    "address). Nothing is downloaded or installed: if there is a newer version, you "
    "are told and can open its download page yourself.")


def version_tuple(text):
    """"v0.58.4" -> (0, 58, 4); anything unreadable -> ()."""
    parts = str(text or "").strip().lstrip("vV").split(".")
    try:
        return tuple(int(x) for x in parts) if parts and parts[0] else ()
    except ValueError:
        return ()


_app_update_work = {"busy": False}


def fetch_latest_release():
    """Ask github.com for the latest published version. Returns (tag, page,
    download, None), "" for what is not there, or (None, None, None, why).
    Links are only accepted if they point at this repository."""
    import urllib.error
    import urllib.request
    import platform
    was_open = network_is_open()
    open_network("update check")
    try:
        return _fetch_latest(was_open)
    except Exception as exc:                     # an odd reply: say so, never hang
        return None, None, None, str(exc)


def _fetch_latest(was_open):
    import urllib.error
    import urllib.request
    import platform
    try:
        request = urllib.request.Request(
            "https://api.github.com/repos/%s/releases/latest" % APP_REPO,
            headers={"User-Agent": "app-update-check",
                     "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(request, timeout=20,
                                        context=mac_ssl_context()) as reply:
                data = json.load(reply)
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                raise
            return "", "", "", None                  # nothing published yet
    except Exception as exc:
        return None, None, None, str(exc)
    finally:
        # Shut again at once (unless a download opened it meanwhile: then the
        # download closes it when it is done).
        if not was_open and _net.get("why") == "update check":
            close_network()
    if not isinstance(data, dict):
        raise ValueError("unexpected reply")
    kind = "apple-silicon" if platform.machine() == "arm64" else "intel"
    download = ""
    for asset in data.get("assets") or []:
        name = str(asset.get("name") or "").lower()
        if name.startswith("leetsay-") and name.endswith("-%s.dmg" % kind):
            download = str(asset.get("browser_download_url") or "")

    def safe_link(link, start):
        """Only a plain link under this repository: no "..", encoded
        characters, user names, ports or odd characters."""
        from urllib.parse import urlsplit
        if not link.startswith(start) or any(c in link for c in "\\%@?#<>\"' "):
            return False
        parts = urlsplit(link)
        return (parts.scheme == "https" and parts.netloc == "github.com"
                and ".." not in parts.path.split("/"))
    page = str(data.get("html_url") or "")
    if not safe_link(page, "https://github.com/%s/" % APP_REPO):
        page = APP_RELEASES_PAGE
    if not safe_link(download, "https://github.com/%s/releases/download/" % APP_REPO):
        download = ""
    found = re.search(r"minimum safe version:\s*v?([0-9]+(?:\.[0-9]+)*)",
                      str(data.get("body") or ""), re.IGNORECASE)
    _app_update_work["minimum"] = found.group(1) if found else ""
    return str(data.get("tag_name") or ""), page, download, None


def ask_app_update_check(parent, at_startup=False):
    if at_startup:
        return dialog("Check for updates at startup?",
                      "With this switched on, every time it starts, "
                      + APP_UPDATE_WARNING % {"app": APP_TITLE},
                      buttons=("Turn on", "Keep off"), parent=parent,
                      headline="This application will go online") == "Turn on"
    return dialog("Check for updates?", "Once, now, " + APP_UPDATE_WARNING % {"app": APP_TITLE},
                  buttons=("Check now", "Cancel"), parent=parent,
                  headline="This application will go online") == "Check now"


def run_app_update_check(parent=None, manual=True, done=None, tray=None):
    """Check in the background, then say what was found. manual=False (at
    startup) says something only if there is a newer version, once per version."""
    if _app_update_work["busy"]:
        return
    _app_update_work.update(busy=True, result=None)

    def work():
        try:
            _app_update_work["result"] = fetch_latest_release()
        except Exception as exc:                 # never leave the check hanging
            _app_update_work["result"] = (None, None, None, str(exc))
    threading.Thread(target=work, daemon=True).start()
    poll = QTimer(QApplication.instance())
    poll.setInterval(250)

    def check():
        if _app_update_work.get("result") is None:
            return
        poll.stop()
        poll.deleteLater()
        _app_update_work["busy"] = False
        tag, page, download, why = _app_update_work["result"]
        if done is not None:
            done()
        show_app_update_result(parent, tag, page, why, manual, download, tray)
    poll.timeout.connect(check)
    poll.start()


def show_app_update_result(parent, tag, page, why, manual, download="", tray=None):
    if why is not None:
        log.info("update check: github.com could not be reached")
        if manual:
            dialog("Check for updates", "github.com could not be reached, so nothing was "
                   "checked.", parent=parent, headline="Could not check for updates")
        return
    if not tag or not version_tuple(tag):
        log.info("update check: no published version found")
        if manual:
            dialog("Check for updates", "No version of %s for Mac has been published on "
                   "github.com yet." % APP_TITLE, parent=parent,
                   headline="No published version found")
        return
    latest = tag.lstrip("vV")
    minimum = _app_update_work.get("minimum") or ""
    if minimum and version_tuple(VERSION) < version_tuple(minimum) \
            and version_tuple(latest) > version_tuple(VERSION):
        offer_update(parent, latest, page, download, unsafe=True)
        return
    if version_tuple(latest) <= version_tuple(VERSION):
        log.info("update check: up to date")
        if manual:
            dialog("Check for updates", "%s %s is the newest published version."
                   % (APP_TITLE, VERSION), parent=parent,
                   headline="You have the latest version")
        return
    log.info("update check: version %s is available", latest)
    if manual or tray is None:
        offer_update(parent, latest, page, download)
        return
    if _config.get("app_update_seen") != latest:     # a notice once per new version
        _update_offer["args"] = (latest, page, download)
        if not _update_offer["connected"]:
            tray.messageClicked.connect(
                lambda: offer_update(None, *_update_offer["args"]))
            _update_offer["connected"] = True
        tray.showMessage("%s update available" % APP_TITLE,
                         "Version %s is available. Click here for details." % latest)
    save_setting("app_update_seen", latest)


_update_offer = {"connected": False, "args": None}


def offer_update(parent, latest, page, download, unsafe=False):
    if download:
        how = ("Download now opens the new .dmg in your web browser, which downloads it "
               "from github.com. Open it and drag leetsay into Applications again: your "
               "settings and speech model are kept.")
    else:
        how = ("What's new opens the release page, where you can download the new .dmg. "
               "Your settings and speech model are kept.")
    if unsafe:
        headline = "Please update %s" % APP_TITLE
        why = ("A problem was found in earlier versions, including yours (%s), and they "
               "should no longer be used. Version %s fixes it." % (VERSION, latest))
    else:
        headline = "%s %s is available" % (APP_TITLE, latest)
        why = "You have version %s." % VERSION
    buttons = ("Download now", "What's new", "Not now") if download else ("What's new",
                                                                           "Not now")
    choice = dialog("%s update" % APP_TITLE, "%s\n\n%s\n\ngithub.com is a third-party "
                    "website that we do not run or control. Nothing has been downloaded "
                    "yet." % (why, how), buttons=buttons, parent=parent, headline=headline,
                    width=440)
    if choice == "Download now":
        QDesktopServices.openUrl(QUrl(download))
    elif choice == "What's new":
        QDesktopServices.openUrl(QUrl(page))


def auto_key_warning(parent, key):
    """(As on Windows.) Before a key is pressed automatically after dictating:
    what that can do. Returns True if confirmed."""
    app = {"app": APP_TITLE, "key": key}
    return hold_confirm_window(
        parent, "%s: pressing a key for you" % APP_TITLE, "Pressing a key for you",
        ["With this on, %(app)s presses %(key)s for you right after typing your "
         "words. In many apps that sends a message, submits a form or confirms an "
         "action straight away, with no chance to read or correct the text first, "
         "and it can skip confirmation steps those apps would normally give you." % app,
         "You are responsible for where it is used and what it sends."],
        "Hold to confirm: turn it on", "Cancel")


def responsibility_notice():
    """Shown once before first use (and after Reset all settings): what the
    application does and does not do, and that where the text goes is up to
    the user. Quit, or closing the window, quits. Returns True if understood.
    (On a first start it is a page of the setup window instead.)"""
    return hold_confirm_window(
        None, "%s: before you start" % APP_TITLE, "Before you start",
        responsibility_paragraphs(), "Hold to confirm: I understand", "Quit")


def responsibility_paragraphs():
    """The words of "Before you start"."""
    app = {"app": APP_TITLE}
    # Short lines, one point each (long ones left a word or two hanging on a
    # line of their own). The bullets are one paragraph, one line per point.
    return ["%(app)s types your words into whichever window has your keyboard "
            "input, usually the text box you last clicked. It does not decide or "
            "control where the text goes; that is up to you." % app,
            "•  Check where your cursor is before you speak.\n"
            "•  Speech recognition makes mistakes: read before you send.\n"
            # A general rule, not a list (a list could read as "anything else
            # is fine"); the README gives examples.
            "•  Don't rely on it where a wrong word could cause harm.\n"
            "•  Don't dictate passwords or anything private.",
            "You are responsible for what %(app)s types and where it goes. It is "
            "open-source software, provided as is, without any warranty. Full terms: the "
            "Disclaimer in the README and the LICENSE." % app]


# ---------------------------------------------------------------------------
# Setup: one window that takes a new user through everything, in order
# (pop-ups that came up on each key press were not smooth)
# ---------------------------------------------------------------------------
class SetupWindow(QtWidgets.QDialog):
    """Step 1: typing (Accessibility). Step 2: the microphone. Step 3: try it.
    Each step ticks itself off as soon as macOS says yes; nothing pops up
    on a key press while this is open."""

    TEXT_W = 430

    def __init__(self, dictation):
        super().__init__()
        self.dictation = dictation
        key = pretty(HOTKEY)
        self.setWindowTitle(f"Set up {APP_TITLE}")
        self.setWindowFlags(Qt.Window | Qt.WindowTitleHint | Qt.WindowCloseButtonHint)
        self.setStyleSheet(settings_style() + """
QFrame#step { border: 1px solid #2A2C33; border-radius: 10px; background: #1B1C21; }
QFrame#step[done="true"] { border-color: #2F5A47; }
QLabel#steptitle { color: #FFFFFF; font-size: 14px; font-weight: 600; }
QLabel#stepbody { color: #C4C6CF; font-size: 13px; }
QLabel#ok { color: %s; font-size: 12px; font-weight: 600; }
QLabel#wait { color: #F2B45A; font-size: 12px; }
""" % ACCENT)
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 18)
        outer.setSpacing(12)
        # Always exactly as big as what it shows (the usual sizing caps a
        # window at two thirds of the screen and squashed the steps).
        outer.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        top = QtWidgets.QHBoxLayout()
        logo = QtWidgets.QLabel()
        logo.setPixmap(app_icon().pixmap(48, 48))
        top.addWidget(logo)
        words = QtWidgets.QVBoxLayout()
        title = QtWidgets.QLabel(f"Set up {APP_TITLE}")
        title.setObjectName("headline")
        words.addWidget(title)
        sub = QtWidgets.QLabel(f"Three short steps (and one optional). {how_words(key).capitalize()}: your words are "
                               f"typed where the cursor is. It all happens on this Mac.")
        sub.setObjectName("body")
        sub.setWordWrap(True)
        sub.setFixedWidth(440)
        words.addWidget(sub)
        top.addLayout(words, 1)
        top.setSpacing(14)
        outer.addLayout(top)

        self.steps = []
        b1 = self._button("Open Accessibility settings", self._ask_typing)
        self.typing = self._step(
            1, f"Let {APP_TITLE} type for you",
            f"So {APP_TITLE} can notice {key} and type your words into other apps. macOS "
            f"calls this “Accessibility”. Click the button, then switch {APP_TITLE} on in "
            f"the list.",
            [b1],
            f"Not in the list? Click + under it and choose Applications › {APP_TITLE}. "
            f"Already on, but this step doesn't tick? Select {APP_TITLE}, click –, then add "
            f"it again with +. {APP_TITLE} restarts by itself once it is allowed.")
        self.mic_button = self._button("Allow the microphone", self._ask_mic)
        self.mic = self._step(
            2, f"Let {APP_TITLE} hear you",
            f"The microphone is on {mic_on_words(key)}. Nothing is recorded or "
            f"saved, and nothing is sent anywhere.",
            [self.mic_button],
            f"No question from macOS? Open System Settings › Privacy & Security › "
            f"Microphone: if {APP_TITLE} is listed, switch it off and on again. Otherwise "
            f"quit {APP_TITLE}, open it again and click “Ask again”.")
        self.box = QtWidgets.QPlainTextEdit()
        self.box.setPlaceholderText(f"Click here, then {how_words(key)}.")
        self.box.setFixedSize(self.TEXT_W - 80, 64)
        self.box.setStyleSheet("QPlainTextEdit { font-family: 'Helvetica Neue'; "
                               "font-size: 13px; }")
        self.box.textChanged.connect(self.refresh)
        self.trial = self._step(
            3, "Try it", f"Click in the box below, then {how_words(key)}.",
            [self.box], None)

        # 4: optional, as in the Windows introduction: a colour, and start at login.
        self.colour_buttons = []
        widgets = []
        for label, value in ACCENT_CHOICES:
            swatch = QtWidgets.QPushButton()
            swatch.setToolTip(label)
            swatch.setFixedSize(30, 30)
            swatch.setFlat(True)
            swatch.setStyleSheet("background: transparent; border: none; padding: 0; "
                                 "min-height: 0;")
            swatch.clicked.connect(lambda _c=False, v=value: self._colour_chosen(v))
            self.colour_buttons.append((swatch, value))
            widgets.append(swatch)
        self.login = QtWidgets.QCheckBox("Start at login")
        # First setup: ticked to begin with (as Windows' "Start with Windows"),
        # and only applied when setup is finished, so quitting here adds
        # nothing to Login Items. Later visits show and change the real state.
        self.first_setup = not _config.get("welcomed")
        self.login.setChecked(bool(_config.get("setup_login", True)) if self.first_setup
                              else starts_at_login())
        self.login.setEnabled(FROZEN)
        self.login.toggled.connect(self._login_toggled)
        widgets.append(self.login)
        self.extras = self._step(
            4, "Make it yours (optional)",
            "Pick a colour for the pop-up, and choose whether leetsay starts quietly in "
            "the menu bar when you log in. Both can be changed later in Settings.",
            widgets, None)
        self._paint_colours()

        bottom = QtWidgets.QHBoxLayout()
        self.footnote = QtWidgets.QLabel("")
        self.footnote.setObjectName("info")
        self.footnote.setWordWrap(True)
        bottom.addWidget(self.footnote, 1)
        self.done_button = QtWidgets.QPushButton("Done")
        self.done_button.setAutoDefault(False)
        self.done_button.clicked.connect(self._done_clicked)
        bottom.addWidget(self.done_button)
        outer.addLayout(bottom)

        self.timer = QTimer(self)
        self.timer.setInterval(700)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def _paint_colours(self):
        ratio = self.devicePixelRatioF() or 2.0
        for swatch, value in self.colour_buttons:
            swatch.setIcon(QIcon(swatch_picture(value, value.lower() == ACCENT.lower(),
                                                ratio)))
            swatch.setIconSize(QtCore.QSize(24, 24))

    def _colour_chosen(self, colour):
        set_option("ACCENT", "accent", colour)
        self._paint_colours()
        self.dictation.overlay.update()          # the pill shows it at once

    def _login_toggled(self, on):
        if self.first_setup:
            save_setting("setup_login", bool(on))   # applied when setup is done
            return
        if not set_start_at_login(bool(on)):
            self.login.blockSignals(True)
            self.login.setChecked(starts_at_login())
            self.login.blockSignals(False)

    # -- building -----------------------------------------------------------
    def _button(self, text, handler):
        b = QtWidgets.QPushButton(text)
        b.setAutoDefault(False)
        b.clicked.connect(lambda _c=False: handler())
        return b

    def _step(self, number, title, text, widgets, small):
        frame = QtWidgets.QFrame()
        frame.setObjectName("step")
        grid = QtWidgets.QHBoxLayout(frame)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setSpacing(12)
        badge = QtWidgets.QLabel()
        badge.setFixedSize(26, 26)
        grid.addWidget(badge, 0, Qt.AlignTop)
        col = QtWidgets.QVBoxLayout()
        col.setSpacing(6)
        head = QtWidgets.QLabel(title)
        head.setObjectName("steptitle")
        col.addWidget(head)
        body = QtWidgets.QLabel(text)
        body.setObjectName("stepbody")
        body.setWordWrap(True)
        body.setFixedWidth(self.TEXT_W)          # (a fixed width: wrapped text then
        col.addWidget(body)                      # gets its full height)
        line = QtWidgets.QHBoxLayout()
        for w in widgets:
            line.addWidget(w)
        status = QtWidgets.QLabel("")
        line.addWidget(status)
        line.addStretch(1)
        col.addLayout(line)
        note = None
        if small:
            note = QtWidgets.QLabel(small)
            note.setObjectName("info")
            note.setWordWrap(True)
            note.setFixedWidth(self.TEXT_W)
            col.addWidget(note)
        grid.addLayout(col, 1)
        self.layout().addWidget(frame)
        step = {"frame": frame, "badge": badge, "status": status, "number": number,
                "widgets": widgets, "note": note}
        self.steps.append(step)
        return step

    def _badge(self, step, state):
        """A number in a ring, or a tick in the accent colour when done."""
        ratio = max(1.0, float(self.devicePixelRatioF()))
        pm = QPixmap(int(26 * ratio), int(26 * ratio))
        pm.fill(Qt.transparent)
        pm.setDevicePixelRatio(ratio)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        accent = QColor(ACCENT)
        if state == "done":
            p.setPen(Qt.NoPen)
            p.setBrush(accent)
            p.drawEllipse(QRectF(1, 1, 24, 24))
            pen = QPen(QColor(16, 17, 20), 2.4)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            p.setPen(pen)
            p.drawPolyline([QPointF(7.5, 13.5), QPointF(11.5, 17.5), QPointF(18.5, 9)])
        else:
            ring = accent if state == "now" else QColor("#4A4D57")
            p.setPen(QPen(ring, 1.6))
            p.setBrush(Qt.NoBrush)
            p.drawEllipse(QRectF(1.5, 1.5, 23, 23))
            p.setPen(QColor("#FFFFFF") if state == "now" else QColor("#7A7D88"))
            font = QFont()
            font.setPixelSize(12)
            font.setWeight(QFont.DemiBold)
            p.setFont(font)
            p.drawText(QRectF(0, 0, 26, 26), Qt.AlignCenter, str(step["number"]))
        p.end()
        step["badge"].setPixmap(pm)
        step["frame"].setProperty("done", state == "done")
        step["frame"].style().unpolish(step["frame"])
        step["frame"].style().polish(step["frame"])

    # -- state ----------------------------------------------------------------
    def typing_ok(self):
        return bool(self.dictation.hotkey.port)

    def mic_ok(self):
        return mic_permission() == MIC_OK

    def refresh(self):
        d = self.dictation
        typing, mic = self.typing_ok(), self.mic_ok()
        if mic and getattr(self, "_mic_was_ok", None) is False:
            # Just allowed: macOS gives the focus back to the app used before
            # its question (System Settings, from step 1), which then covers
            # this window. Come back to the front for step 3.
            QTimer.singleShot(300, self._to_front)
        self._mic_was_ok = mic
        tried = bool(self.box.toPlainText().strip())
        self._badge(self.typing, "done" if typing else "now")
        self.typing["status"].setObjectName("ok" if typing else "wait")
        self.typing["status"].setText(
            "Allowed" if typing else
            ("Waiting for you to switch it on…" if d.keyboard_asked else ""))
        for w in self.typing["widgets"]:
            w.setVisible(not typing)
        self.typing["note"].setVisible(not typing)   # the help is only needed until then
        mic_state = mic_permission()
        self._badge(self.mic, "done" if mic else ("now" if typing else "later"))
        self.mic_button.setVisible(not mic)
        self.mic_button.setEnabled(typing)
        if mic_state in (MIC_DENIED, MIC_RESTRICTED):
            self.mic_button.setText("Open Microphone settings")
            self.mic["status"].setObjectName("wait")
            self.mic["status"].setText(f"Switched off: switch {APP_TITLE} on there")
        else:
            self.mic_button.setText("Allow the microphone")
            self.mic["status"].setObjectName("ok" if mic else "wait")
            self.mic["status"].setText("Allowed" if mic else
                                       ("Answer macOS's question…" if d.mic_asked else ""))
        # No question within a few seconds: macOS may be remembering an older
        # copy of leetsay (it then neither asks nor allows). Say what helps.
        stuck = (not mic and mic_state == MIC_UNKNOWN and d.mic_asked
                 and time.monotonic() - getattr(self, "mic_asked_at", 1e12) > 4)
        self.mic["note"].setVisible(stuck)
        if stuck:
            self.mic_button.setText("Ask again")
            self.mic["status"].setText("")
        ready = typing and mic and d.model is not None
        self._badge(self.trial, "done" if tried else ("now" if ready else "later"))
        self._badge(self.extras, "now" if tried else "later")
        self.box.setEnabled(typing and mic)
        self.trial["status"].setObjectName("ok" if tried else "wait")
        self.trial["status"].setText("It works!" if tried else
                                     ("" if ready or not (typing and mic)
                                      else "The speech model is still loading…"))
        for step in self.steps:
            st = step["status"]
            st.style().unpolish(st)
            st.style().polish(st)
        if typing:
            self.done_button.setText("Done")
            self.done_button.setObjectName("primary" if (mic and tried) else "")
            self.footnote.setText("" if mic else "You can allow the microphone later: "
                                  "it is asked the first time you dictate.")
        else:
            self.done_button.setText(f"Quit {APP_TITLE}")
            self.done_button.setObjectName("")
            self.footnote.setText(f"{APP_TITLE} can't work without step 1.")
        self.done_button.style().unpolish(self.done_button)
        self.done_button.style().polish(self.done_button)

    # -- actions --------------------------------------------------------------
    def _ask_typing(self):
        d = self.dictation
        d.keyboard_asked = True
        if not ask_keyboard_permission():        # macOS's own question, and the list
            open_settings_pane("accessibility")
        d.trust_timer.start()
        self.refresh()

    def _ask_mic(self):
        d = self.dictation
        if mic_permission() in (MIC_DENIED, MIC_RESTRICTED):
            open_settings_pane("microphone")
            return
        # macOS's own request; if that can't be made, opening the microphone
        # for a moment makes macOS ask too.
        if not request_mic_permission():
            try:
                d.recorder.start()
            except Exception:
                log.exception("mic prompt")
            QTimer.singleShot(400, d.recorder.close)
        d.mic_asked = True
        self.mic_asked_at = time.monotonic()
        log.info("microphone question requested")
        self.refresh()

    def _to_front(self):
        bring_to_front()
        self.raise_()
        self.activateWindow()
        if self.box.isEnabled():
            self.box.setFocus()                   # ready for "Try it"

    def _done_clicked(self):
        self.close()

    def done(self, result):
        self.timer.stop()
        self.box.clear()                          # the trial words are not kept
        if not self.typing_ok():
            # Without step 1 leetsay can't work: closing this quits.
            log.info("setup closed before typing was allowed: quit")
            self.dictation.quit()
            return
        if self.first_setup and FROZEN and self.login.isChecked() != starts_at_login():
            set_start_at_login(self.login.isChecked())
        save_setting("welcomed", True)
        super().done(result)


def leave_now(code=0):
    logging.shutdown()
    os._exit(code)


_lock_handle = None


def only_one_copy():
    global _lock_handle
    _lock_handle = open(LOCK_FILE, "w")
    try:
        fcntl.flock(_lock_handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    _lock_handle.write(f"{os.getpid()} {VERSION}\n")
    _lock_handle.flush()
    return True


def main():
    os.makedirs(SUPPORT_DIR, exist_ok=True)
    app = QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    app.setStyle("Fusion")          # the app's own look for its windows (the menu stays native)
    if not only_one_copy():
        # (Before the log is started afresh: the running copy's log is kept.)
        dialog(APP_TITLE, f"{APP_TITLE} is already running. Look for its icon in the menu bar "
                          f"at the top of the screen.")
        leave_now(0)
    setup_log()
    log.info("start %s %s, macOS %s, %s", APP_TITLE, VERSION,
             os.uname().release, os.uname().machine)
    hide_from_dock()
    if not network_is_open():
        log.info("network block check: %s", "passed" if verify_network_block() else "FAILED")
    if _config.get("responsibility_ok") is not True:
        # Once, before first use: what leetsay does with your words, and that
        # where they go is up to you. Not confirmed (Quit, or closed): quits.
        if not responsibility_notice():
            log.info("'Before you start' was not confirmed: quit")
            leave_now(0)
        save_setting("responsibility_ok", True)
    # A yes given in Settings (switching models, downloading again) covers the
    # one restart that follows it, and no more: used up here, as it is read.
    agreed_once = _config.get("download_yes_once") == MODEL
    if _config.get("download_yes_once"):
        save_setting("download_yes_once", "")
    if agreed_once:
        open_network("a download agreed to in Settings")
    elif not local_model_dir():
        # Nothing is downloaded without saying so first: explain the one-time
        # download and wait for a yes. Closing this window quits.
        answer = dialog(f"{APP_TITLE}: one-time download", download_question_words(),
                        buttons=("Download", "Manual download", f"Quit {APP_TITLE}"),
                        headline="This application will go online")
        if answer == "Manual download":
            manual_download_steps()
            if not local_model_dir() and dialog(
                    f"{APP_TITLE}: no speech model yet",
                    f"You can look around and change settings, but dictation won't work "
                    f"until the model's files are in place. {APP_TITLE} looks for them each "
                    f"time it starts; you can also download the model later from Settings.",
                    buttons=("Continue without it", f"Quit {APP_TITLE}"),
                    headline="Continue without the speech model?") != "Continue without it":
                leave_now(0)
        elif answer == "Download":
            open_network("first download, agreed just now")
        else:
            log.info("the download question was declined: quit")
            leave_now(0)
    d = Dictation(app)
    d.start()
    app.exec()
    leave_now(0)


if __name__ == "__main__":
    main()
