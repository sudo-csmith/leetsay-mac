"""Builds leetsay.app for this Mac's processor type (Intel or Apple Silicon).

Run:  .venv/bin/python -I build_app.py [--dmg]

Signing (optional; without it the app gets the usual ad-hoc signature):
  LEETSAY_SIGN_IDENTITY   "Developer ID Application: ..." from the keychain
                          (or its SHA-1); every file is signed with the
                          hardened runtime and entitlements.plist.
Notarizing (needs signing; one of the two):
  LEETSAY_NOTARY_PROFILE  a notarytool keychain profile (xcrun notarytool
                          store-credentials), for builds on your own Mac
  LEETSAY_NOTARY_KEY, LEETSAY_NOTARY_KEY_ID, LEETSAY_NOTARY_ISSUER
                          an App Store Connect API key (.p8 path, key ID,
                          issuer ID), for the GitHub builds
The app is notarized and stapled, then the .dmg too, so both open without
Gatekeeper's warning even offline.
Needs PyInstaller in .venv (requirements-build-mac.txt); it is used only to
build and is not part of the app. The result is dist/leetsay.app.

An Intel build runs on Intel Macs, an Apple Silicon build on Apple Silicon
Macs (onnxruntime has no single build for both), so each is built on its own
kind of Mac.
"""
import os
import platform
import plistlib
import re
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(HERE, "leetsay_mac.py")
BUILD = os.path.join(HERE, "build")
DIST = os.path.join(HERE, "dist")
BUNDLE_ID = "io.github.sudo-csmith.leetsay"
ENTITLEMENTS = os.path.join(HERE, "entitlements.plist")
SIGN_IDENTITY = os.environ.get("LEETSAY_SIGN_IDENTITY", "").strip()

_src = open(APP_FILE, encoding="utf-8").read()
VERSION = re.search(r'^VERSION = "([^"]+)"', _src, re.M).group(1)
APP_TITLE = re.search(r'^APP_TITLE = "([^"]+)"', _src, re.M).group(1)

INFO = {
    "CFBundleName": APP_TITLE,
    "CFBundleDisplayName": APP_TITLE,
    "CFBundleShortVersionString": VERSION,
    "CFBundleVersion": VERSION,
    "LSUIElement": True,                  # menu bar app: no Dock icon
    "LSMinimumSystemVersion": "14.0",     # Qt / PySide6 6.12 needs macOS 14
    "LSApplicationCategoryType": "public.app-category.productivity",
    "NSHighResolutionCapable": True,
    "NSMicrophoneUsageDescription":
        f"{APP_TITLE} listens only while you hold the dictation key, to type what "
        f"you say. The sound is never saved or sent anywhere.",
}

SPEC = r'''
from PyInstaller.utils.hooks import collect_data_files, copy_metadata
# onnx-asr reads its own version number when it loads: keep that information.
_datas = collect_data_files("onnx_asr")
_datas.append(({licenses!r}, "licenses"))      # every third-party licence, in the app
for _pkg in ("onnx-asr", "onnxruntime", "numpy", "sounddevice"):
    _datas += copy_metadata(_pkg)
a = Analysis([{app!r}], datas=_datas,
             excludes=["tkinter", "huggingface_hub", "PySide6.QtNetwork",
                       "PySide6.QtWebEngineCore", "PySide6.QtQml", "PySide6.QtQuick"],
             noarchive=False)
# Leave out Qt's network part and the one add-on that pulls it in (touch
# input sent over the network). leetsay never goes online; nothing to carry.
_drop = ("QtNetwork", "qtuiotouchplugin")
a.binaries = [b for b in a.binaries if not any(d in b[0] for d in _drop)]
a.datas = [d for d in a.datas if not any(x in d[0] for x in _drop)]
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name={title!r},
          console=False, argv_emulation=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name={title!r}, upx=False)
app = BUNDLE(coll, name={title!r} + ".app", icon={icns!r},
             bundle_identifier={bid!r}, version={version!r}, info_plist={info!r})
'''


def make_icns():
    """Draws the icon in code (same drawing as the app) into an .icns file."""
    iconset = os.path.join(BUILD, f"{APP_TITLE}.iconset")
    icns = os.path.join(BUILD, f"{APP_TITLE}.icns")
    shutil.rmtree(iconset, ignore_errors=True)
    os.makedirs(iconset)
    code = (
        "import sys, importlib.util; sys.dont_write_bytecode = True\n"
        f"spec = importlib.util.spec_from_file_location('app', {APP_FILE!r})\n"
        "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)\n"
        "from PySide6.QtGui import QGuiApplication\n"
        "q = QGuiApplication(['icon'])\n"
        "for pt in (16, 32, 128, 256, 512):\n"
        "    for scale, tag in ((1, ''), (2, '@2x')):\n"
        f"        m.icon_pixmap(pt * scale, mac_grid=True).save({iconset!r} + "
        "f'/icon_{pt}x{pt}{tag}.png')\n"
        "import os; os._exit(0)\n")
    subprocess.run([sys.executable, "-I", "-c", code], check=True,
                   env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    subprocess.run(["iconutil", "-c", "icns", iconset, "-o", icns], check=True)
    return icns


# Third-party parts inside the app, with where their licence texts come from.
# (name, distribution, licence, what it does)
PACKAGES = [
    ("PySide6 (Qt for Python)", "PySide6-Essentials", "LGPL-3.0", "windows, pop-up, menu bar icon"),
    ("shiboken6", "shiboken6", "LGPL-3.0", "part of Qt for Python"),
    ("ONNX Runtime", "onnxruntime", "MIT (with its third-party notices)", "the speech engine"),
    ("onnx-asr", "onnx-asr", "MIT", "runs the speech models"),
    ("NumPy", "numpy", "BSD-3-Clause (with its bundled parts)", "audio handling"),
    ("sounddevice", "sounddevice", "MIT", "the microphone (with PortAudio, MIT)"),
    ("cffi", "cffi", "MIT-0", "used by sounddevice"),
    ("pycparser", "pycparser", "BSD-3-Clause", "used by cffi"),
    ("protobuf", "protobuf", "BSD-3-Clause", "used by ONNX Runtime"),
    ("flatbuffers", "flatbuffers", "Apache-2.0", "used by ONNX Runtime"),
    ("packaging", "packaging", "Apache-2.0 or BSD-2-Clause", "used by ONNX Runtime"),
    ("coloredlogs", "coloredlogs", "MIT", "used by ONNX Runtime"),
    ("humanfriendly", "humanfriendly", "MIT", "used by coloredlogs"),
    ("sympy", "sympy", "BSD-3-Clause", "used by ONNX Runtime"),
    ("mpmath", "mpmath", "BSD-3-Clause", "used by sympy"),
]
_LICENCE_FILE = re.compile(r"(LICEN[CS]E|COPYING|NOTICE|ThirdPartyNotices)", re.I)


def _python_incorporated_text():
    """Python's own list of the software built into it (OpenSSL, expat,
    libffi, zlib, mpdecimal, XZ, bzip2...), with their licence texts, from
    the documentation that comes with Python, as plain text."""
    import html
    page = os.path.join(sys.base_prefix, "Resources", "English.lproj", "Documentation",
                        "license.html")
    text = open(page, encoding="utf-8").read()
    start = text.find('id="licenses-and-acknowledgements-for-incorporated-software"')
    text = text[start if start > 0 else 0:]
    text = text[text.find(">") + 1:]                 # past the tag it started in
    end = text.find('<footer')
    text = text[:end if end > 0 else None]
    text = re.sub(r"<(br|/p|/pre|/h[1-6]|/li|/div|/section)[^>]*>", "\n", text)
    text = html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\u00b6", "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return ("Licences and acknowledgements for software incorporated in Python\n"
            "(from Python's own documentation, %s)\n\n" % platform.python_version() + text + "\n")


def collect_licenses():
    """Put every licence text the app needs into build/licenses (it goes into
    leetsay.app/Contents/Resources/licenses): leetsay's own, Python's and the
    parts built into it, each package's own files, and the texts kept in the
    repository's licenses/ folder (Qt's LGPL and notes, PortAudio, Apache,
    Silero VAD). README.txt says what each file is for."""
    import importlib.metadata as md
    out = os.path.join(BUILD, "licenses")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(out)
    for name in sorted(os.listdir(os.path.join(HERE, "licenses"))):
        shutil.copy(os.path.join(HERE, "licenses", name), out)
    shutil.copy(os.path.join(HERE, "LICENSE"), os.path.join(out, "leetsay-LICENSE.txt"))
    shutil.copy(os.path.join(sys.base_prefix, "lib", "python%d.%d" % sys.version_info[:2],
                             "LICENSE.txt"), os.path.join(out, "Python-LICENSE.txt"))
    with open(os.path.join(out, "Python-incorporated-software.txt"), "w", encoding="utf-8") as f:
        f.write(_python_incorporated_text())
    versions = {}
    for _label, dist, _lic, _what in PACKAGES:
        d = md.distribution(dist)
        versions[dist] = d.version
        for item in d.files or []:
            path = str(item)
            if _LICENCE_FILE.search(os.path.basename(path)) and not path.endswith((".py", ".pyc")):
                flat = re.sub(r"[^A-Za-z0-9._-]+", "_", path.split(".dist-info/")[-1])
                target = os.path.join(out, "%s-%s" % (dist, flat))
                if not target.endswith((".txt", ".md")):
                    target += ".txt"
                shutil.copy(item.locate(), target)
    qt = versions["PySide6-Essentials"]
    rows = "\n".join("  %-26s %-10s %s: %s" % (label, versions[dist], lic, what)
                      for label, dist, lic, what in PACKAGES)
    readme = f"""Licences of leetsay {VERSION} for Mac
=================================

leetsay itself: MIT licence (leetsay-LICENSE.txt). It does not cover the parts
below: each is the work of its own authors and is used under its own licence,
whose full text is in this folder.

Python {platform.python_version()} (PSF License): Python-LICENSE.txt. Software built into Python
and included with it here (OpenSSL under Apache-2.0, expat, libffi, zlib,
mpdecimal, XZ, bzip2 and others): Python-incorporated-software.txt.

Packages included in this app:
{rows}

Their licence files are the files named after them in this folder. Texts they
refer to: Apache-2.0.txt, LGPL-3.0.txt and GPL-3.0.txt (the LGPL builds on the
GPL). PortAudio (in sounddevice): PortAudio-LICENSE.txt.

Qt and Qt for Python (LGPL-3.0)
-------------------------------
leetsay uses Qt {qt} and PySide6 {qt} (the modules QtCore, QtGui and QtWidgets),
unchanged, under the GNU Lesser General Public License v3. Their source code:
  https://download.qt.io/archive/qt/{qt.rsplit('.', 1)[0]}/{qt}/
  https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v{qt}
(third-party websites that we do not run or control). The Qt libraries are
separate files inside the app (leetsay.app/Contents/Frameworks/PySide6/Qt/lib),
so they can be replaced with other compatible versions; after changing files,
the app needs signing again before macOS will open it, for example:
  codesign --force --deep --sign - leetsay.app
Qt contains code from other projects under their own licences:
Qt-third-party.txt (summary) and Qt-third-party-full.txt (full texts).

Speech models (not part of this app)
------------------------------------
The speech models leetsay downloads are NVIDIA's Parakeet TDT 0.6B v2 and v3,
under CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/), converted to
ONNX and reduced to 8 bits by this project
(https://github.com/sudo-csmith/leetsay-models). NVIDIA has not reviewed or
endorsed leetsay or these conversions. The speech detector is Silero VAD,
Copyright (c) 2020-present Silero Team, MIT (Silero-VAD-LICENSE.txt).

Trademarks: leetsay is an independent project, not affiliated with, endorsed
or sponsored by Apple, NVIDIA, GitHub, Microsoft, the Qt Company, the Silero
Team or the Python Software Foundation. Apple, Mac and macOS are trademarks of Apple
Inc.; the other names belong to their owners and are used only to describe
what leetsay works with.
"""
    with open(os.path.join(out, "README.txt"), "w", encoding="utf-8") as f:
        f.write(readme)
    print("licences collected: %d files" % len(os.listdir(out)))
    return out


def main():
    print(f"Building {APP_TITLE} {VERSION} for {platform.machine()}")
    shutil.rmtree(BUILD, ignore_errors=True)
    shutil.rmtree(os.path.join(DIST, APP_TITLE), ignore_errors=True)
    shutil.rmtree(os.path.join(DIST, APP_TITLE + ".app"), ignore_errors=True)
    os.makedirs(BUILD)
    icns = make_icns()
    spec = os.path.join(BUILD, f"{APP_TITLE}.spec")
    with open(spec, "w", encoding="utf-8") as f:
        f.write(SPEC.format(app=APP_FILE, title=APP_TITLE, icns=icns, bid=BUNDLE_ID,
                            version=VERSION, info=INFO, licenses=collect_licenses()))
    subprocess.run([sys.executable, "-I", "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--log-level", "WARN", "--distpath", DIST,
                    "--workpath", os.path.join(BUILD, "work"), spec], check=True)
    shutil.rmtree(os.path.join(DIST, APP_TITLE), ignore_errors=True)  # loose copy
    app = os.path.join(DIST, APP_TITLE + ".app")
    with open(os.path.join(app, "Contents", "Info.plist"), "rb") as f:
        plist = plistlib.load(f)
    missing = [k for k, v in INFO.items() if plist.get(k) != v]
    if missing:
        sys.exit(f"Info.plist is missing: {missing}")
    if SIGN_IDENTITY:
        sign_app(app)
    subprocess.run(["codesign", "--verify", "--deep", "--strict", app], check=True)
    if SIGN_IDENTITY and notary_args():
        notarize(app)
    print(f"Done: {app}")
    if "--dmg" in sys.argv:
        make_dmg(app)


_MACHO = (b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe")


def _codesign(path, entitlements=False):
    cmd = ["codesign", "--force", "--options", "runtime", "--sign", SIGN_IDENTITY]
    if SIGN_IDENTITY != "-":            # "-" = a local test without a certificate
        cmd.append("--timestamp")
    if entitlements:
        cmd += ["--entitlements", _test_entitlements() if SIGN_IDENTITY == "-"
                else ENTITLEMENTS]
    subprocess.run(cmd + [path], check=True, stdout=subprocess.DEVNULL)


def _test_entitlements():
    """A local test without a certificate ("-") has no team ID, so macOS would
    refuse to load the app's own libraries; only for that test, allow it."""
    with open(ENTITLEMENTS, "rb") as fh:
        ent = plistlib.load(fh)
    ent["com.apple.security.cs.disable-library-validation"] = True
    out = os.path.join(BUILD, "entitlements-local-test.plist")
    with open(out, "wb") as fh:
        plistlib.dump(ent, fh)
    return out


def sign_app(app):
    """Signs every program file inside out (libraries, then the framework
    bundles, then the app with its entitlements), all with the hardened
    runtime, as Apple's notary service asks."""
    files, frameworks = [], []
    for root, dirs, names in os.walk(app):
        for d in dirs:
            p = os.path.join(root, d)
            if d.endswith(".framework") and not os.path.islink(p):
                frameworks.append(p)
        for n in names:
            p = os.path.join(root, n)
            if os.path.islink(p) or not os.path.isfile(p):
                continue
            with open(p, "rb") as fh:
                if fh.read(4) in _MACHO:
                    files.append(p)
    main_exe = os.path.join(app, "Contents", "MacOS", APP_TITLE)
    depth = lambda p: p.count(os.sep)
    for p in sorted(files, key=depth, reverse=True):
        if p != main_exe:
            _codesign(p)
    for p in sorted(frameworks, key=depth, reverse=True):
        _codesign(p)
    _codesign(app, entitlements=True)
    print(f"signed: {len(files)} program files, {len(frameworks)} frameworks, the app")


def notary_args():
    """notarytool's sign-in arguments from the environment, or None."""
    profile = os.environ.get("LEETSAY_NOTARY_PROFILE")
    if profile:
        return ["--keychain-profile", profile]
    key = os.environ.get("LEETSAY_NOTARY_KEY")
    key_id = os.environ.get("LEETSAY_NOTARY_KEY_ID")
    issuer = os.environ.get("LEETSAY_NOTARY_ISSUER")
    if key and key_id and issuer:
        return ["--key", key, "--key-id", key_id, "--issuer", issuer]
    return None


def notarize(path):
    """Sends the app (zipped) or the .dmg to Apple's notary service, waits
    for the answer and staples the ticket on, so it opens offline too."""
    upload = path
    if path.endswith(".app"):
        upload = os.path.join(BUILD, APP_TITLE + "-notarize.zip")
        subprocess.run(["ditto", "-c", "-k", "--keepParent", path, upload], check=True)
    print(f"notarizing {os.path.basename(path)} (usually a few minutes)...")
    # A limit, so a slow answer fails cleanly instead of keeping the build
    # Mac (and its paid minutes) waiting; Apple still finishes the check.
    r = subprocess.run(["xcrun", "notarytool", "submit", upload, "--wait",
                        "--timeout", os.environ.get("LEETSAY_NOTARY_TIMEOUT", "30m"),
                        "--output-format", "json"] + notary_args(),
                       capture_output=True, text=True)
    import json
    try:
        answer = json.loads(r.stdout)
    except ValueError:
        answer = {}
    print(f"notary answer: {answer.get('status')} ({answer.get('id')})")
    if answer.get("status") == "In Progress" or "Timeout" in str(answer.get("message", "")):
        sys.exit("Apple's check took longer than the time limit. It carries on at "
                 "Apple; try the build again later.")
    if answer.get("status") != "Accepted":
        if answer.get("id"):
            subprocess.run(["xcrun", "notarytool", "log", answer["id"]] + notary_args())
        sys.exit("Notarization failed: " + (r.stderr.strip() or r.stdout.strip()))
    subprocess.run(["xcrun", "stapler", "staple", path], check=True)
    subprocess.run(["xcrun", "stapler", "validate", path], check=True)


def arch_label():
    """The kind of Mac this build is for, as people say it."""
    return "apple-silicon" if platform.machine() == "arm64" else "intel"


def draw_dmg_background(one, two):
    """Draw the install window's background (normal and double size), in
    leetsay's own look: its dark background, a soft Mint glow, round plates
    for the two icons, a Mint arrow between them, the title with leetsay's
    bars, and a quiet note about the first-open "Open Anyway" step. Runs in
    its own process (Qt), started by make_dmg_background."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("leetsay_app", APP_FILE)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    from PySide6.QtCore import QPointF, QRectF, Qt
    from PySide6.QtGui import (QColor, QFont, QFontMetricsF, QGuiApplication, QImage,
                               QLinearGradient, QPainter, QPainterPath, QPen,
                               QRadialGradient)
    QGuiApplication(["background"])
    W, H, Y = DMG_W, DMG_H, DMG_ICON_Y
    left_x, right_x = DMG_ICON_X, DMG_W - DMG_ICON_X
    mint = QColor(m.ACCENT)
    for scale, path in ((1, one), (2, two)):
        img = QImage(W * scale, H * scale, QImage.Format_ARGB32)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(scale, scale)
        p.fillRect(QRectF(0, 0, W, H), QColor(m.POPUP_BG))          # #16171B
        glow = QRadialGradient(QPointF(W / 2, Y), 300)                # soft Mint light
        for at, alpha in ((0.0, 34), (0.55, 10), (1.0, 0)):
            c = QColor(mint)
            c.setAlpha(alpha)
            glow.setColorAt(at, c)
        p.fillRect(QRectF(0, 0, W, H), glow)
        for x in (left_x, right_x):          # a light card for each icon and its name
            # Light: Finder writes the names under the icons in black over a
            # background picture, whatever the mode (seen on a Mac in dark
            # mode), so they need a light card to be read.
            card = QRectF(x - 80, Y - 76, 160, 180)
            shade = QColor(0, 0, 0, 70)
            p.setPen(Qt.NoPen)
            for grow in (6, 3):
                shade.setAlpha(22 if grow == 6 else 34)
                p.setBrush(shade)
                p.drawRoundedRect(card.adjusted(-grow, -grow + 4, grow, grow + 4),
                                  22 + grow, 22 + grow)
            fill = QLinearGradient(QPointF(0, card.top()), QPointF(0, card.bottom()))
            fill.setColorAt(0.0, QColor("#F6F7F9"))
            fill.setColorAt(1.0, QColor("#E6E8EC"))
            p.setBrush(fill)
            p.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
            p.drawRoundedRect(card, 22, 22)
        # The arrow: Mint, fading in from the left.
        line = QLinearGradient(QPointF(left_x + 88, 0), QPointF(right_x - 88, 0))
        faint = QColor(mint)
        faint.setAlpha(60)
        line.setColorAt(0.0, faint)
        line.setColorAt(1.0, mint)
        pen = QPen(line, 4.0)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.setBrush(Qt.NoBrush)
        tip = right_x - 92
        p.drawLine(QPointF(left_x + 92, Y), QPointF(tip, Y))
        head = QPainterPath()
        head.moveTo(tip - 14, Y - 13)
        head.lineTo(tip, Y)
        head.lineTo(tip - 14, Y + 13)
        p.setPen(QPen(mint, 4.0, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.drawPath(head)
        # Title: leetsay's bars, then the words, centred as one group.
        font = QFont()
        font.setPixelSize(22)
        font.setWeight(QFont.DemiBold)
        title = "Drag leetsay into Applications"
        width = QFontMetricsF(font).horizontalAdvance(title)
        x0 = (W - (width + 34)) / 2
        m.draw_bars(p, x0, 40, 22, 22, mint)
        p.setFont(font)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(x0 + 34, 36, width + 4, 30), Qt.AlignLeft | Qt.AlignVCenter, title)
        font.setPixelSize(13)
        font.setWeight(QFont.Normal)
        p.setFont(font)
        p.setPen(QColor("#A9ABB5"))
        p.drawText(QRectF(0, 70, W, 20), Qt.AlignCenter,
                   "Then open it from your Applications folder.")
        # The first-open note, on a quiet panel at the bottom.
        panel = QRectF(48, H - 74, W - 96, 50)
        p.setPen(QPen(QColor("#2A2C33"), 1.0))
        p.setBrush(QColor("#1B1C21"))
        p.drawRoundedRect(panel, 10, 10)
        font.setPixelSize(12)
        p.setFont(font)
        p.setPen(QColor("#8E909A"))
        if os.environ.get("LEETSAY_SIGN_IDENTITY", "-") != "-":
            note = ("Signed by its developer and checked by Apple. The first time,\n"
                    "macOS asks whether to open an app from the internet: click Open.")
        else:
            note = ("The first time you open it, if macOS says it can't verify leetsay:\n"
                    "System Settings \u203a Privacy & Security \u203a Open Anyway.")
        p.drawText(panel, Qt.AlignCenter, note)
        p.end()
        img.setDotsPerMeterX(2835 * scale)
        img.setDotsPerMeterY(2835 * scale)
        img.save(path)


def make_dmg_background():
    """The background picture for the install window, as one TIFF holding the
    normal and the double-size picture (sharp on every screen)."""
    out = os.path.join(BUILD, "dmg-background.tiff")
    one, two = (os.path.join(BUILD, n) for n in ("dmg-bg.png", "dmg-bg@2x.png"))
    subprocess.run([sys.executable, "-I", os.path.abspath(__file__),
                    "--draw-dmg-background", one, two], check=True,
                   env=dict(os.environ, QT_QPA_PLATFORM="offscreen"))
    subprocess.run(["tiffutil", "-cathidpicheck", one, two, "-out", out], check=True,
                   capture_output=True)
    return out


def set_dmg_label_colour(dmg):
    """The window's plain background colour (shown before the picture loads,
    or if it can't) set to leetsay's dark one; dmgbuild leaves it white.
    (Tried as a way to get white names: it doesn't do that. Finder writes the
    names in black over a picture whatever this colour or the mode, hence the
    light cards in the picture.)"""
    from ds_store import DSStore
    work = os.path.join(BUILD, "dmg-rw.dmg")
    if os.path.exists(work):
        os.remove(work)
    subprocess.run(["hdiutil", "convert", dmg, "-format", "UDRW", "-o", work],
                   check=True, capture_output=True)
    mount = os.path.join(BUILD, "dmg-mount")
    os.makedirs(mount, exist_ok=True)
    subprocess.run(["hdiutil", "attach", work, "-nobrowse", "-noautoopen",
                    "-mountpoint", mount], check=True, capture_output=True)
    try:
        with DSStore.open(os.path.join(mount, ".DS_Store"), "r+") as store:
            view = store["."]["icvp"]
            red, green, blue = (int(DMG_BG[i:i + 2], 16) / 255.0 for i in (1, 3, 5))
            view["backgroundColorRed"] = red
            view["backgroundColorGreen"] = green
            view["backgroundColorBlue"] = blue
            store["."]["icvp"] = view
    finally:
        subprocess.run(["hdiutil", "detach", mount], check=True, capture_output=True)
    os.remove(dmg)
    subprocess.run(["hdiutil", "convert", work, "-format", "UDZO", "-imagekey",
                    "zlib-level=9", "-o", dmg], check=True, capture_output=True)
    os.remove(work)


DMG_BG = "#16171B"               # leetsay's own dark background
DMG_ICON_X = 168                 # the app's icon centre (Applications mirrors it)
DMG_W, DMG_H = 640, 400          # the install window, in points
DMG_ICON_Y = 190                 # where the two icons sit (their centres)


def make_dmg(app):
    """The usual Mac download: a disk image that opens as an install window,
    leetsay on the left and Applications on the right, with the background
    above. Its SHA-256 fingerprint goes beside it."""
    import hashlib
    import dmgbuild
    # The same name for every version (as Windows' leetsay-setup.exe), so a
    # link to releases/latest/download/<name> always works.
    name = f"{APP_TITLE}-mac-{arch_label()}.dmg"
    out = os.path.join(DIST, name)
    if os.path.exists(out):
        os.remove(out)
    settings = {
        "format": "UDZO",
        "compression_level": 9,
        "files": [app],
        "symlinks": {"Applications": "/Applications"},
        "icon": os.path.join(BUILD, f"{APP_TITLE}.icns"),
        "background": make_dmg_background(),
        "window_rect": ((200, 160), (DMG_W, DMG_H)),
        "default_view": "icon-view",
        "show_status_bar": False, "show_tab_view": False, "show_toolbar": False,
        "show_pathbar": False, "show_sidebar": False,
        "icon_size": 112,
        "text_size": 13,
        "icon_locations": {f"{APP_TITLE}.app": (DMG_ICON_X, DMG_ICON_Y),
                           "Applications": (DMG_W - DMG_ICON_X, DMG_ICON_Y)},
    }
    dmgbuild.build_dmg(out, APP_TITLE, settings=settings)
    set_dmg_label_colour(out)
    if SIGN_IDENTITY:
        subprocess.run(["codesign", "--force", "--timestamp", "--sign", SIGN_IDENTITY,
                        out], check=True)
        if notary_args():
            notarize(out)
    digest = hashlib.sha256(open(out, "rb").read()).hexdigest()
    with open(out + ".sha256", "w") as fh:
        fh.write(f"{digest}  {name}\n")
    print(f"Disk image: {out} ({os.path.getsize(out) // (1024 * 1024)} MB)\nSHA-256: {digest}")

if __name__ == "__main__":
    if "--draw-dmg-background" in sys.argv:
        draw_dmg_background(*sys.argv[sys.argv.index("--draw-dmg-background") + 1:][:2])
        os._exit(0)
    main()
