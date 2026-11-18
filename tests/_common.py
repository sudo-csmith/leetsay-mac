"""Shared helpers for leetsay's off-screen tests.

Every test imports this module first. It makes sure the test runs with a
throwaway HOME (the app writes its settings, log and lock file under HOME, so
a test must never see the real one), links the speech model into that HOME
when one is available, loads leetsay_mac.py from this repository, and offers
small helpers: an off-screen QApplication, pump(), wait_until(), checks that
count failures, and spoken test recordings made with macOS's own `say`.

Exit codes: 0 = passed, 1 = failed, 77 = skipped (see run_all.py).
"""
import os
import sys

sys.dont_write_bytecode = True

import importlib.util
import re
import shutil
import subprocess
import tempfile
import time
import traceback
import wave

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(TESTS_DIR)
APP_FILE = os.path.join(REPO_DIR, "leetsay_mac.py")
SKIP_CODE = 77
MODEL_NAME = "nemo-parakeet-tdt-0.6b-v2"
HELPER_NAME = "silero-vad"
_MODEL_NEEDS = {MODEL_NAME: ("config.json", "vocab.txt", "encoder-model.int8.onnx",
                             "decoder_joint-model.int8.onnx"),
                HELPER_NAME: ("config.json", "silero_vad.onnx")}


def models_source():
    """The folder holding the speech model, or '' if there is none.
    LEETSAY_MODELS wins when it is set (even when it points to an empty
    folder: then there is no model). Otherwise the model of the user's own
    leetsay, as found under the real HOME before the test replaced it."""
    if "LEETSAY_MODELS" in os.environ:
        folder = os.path.expanduser(os.environ["LEETSAY_MODELS"])
    else:
        real_home = os.environ.get("LEETSAY_REAL_HOME") or os.path.expanduser("~")
        folder = os.path.join(real_home, "Library", "Application Support", "leetsay", "models")
    return folder if has_model(folder) else ""


def has_model(folder):
    return bool(folder) and all(
        os.path.isfile(os.path.join(folder, sub, name))
        for sub, names in _MODEL_NEEDS.items() for name in names)


def _prepare_home():
    """A throwaway HOME for this test. run_all.py makes one per test and says
    so in LEETSAY_TEST_HOME; a test started on its own makes its own here."""
    home = os.environ.get("LEETSAY_TEST_HOME")
    if not home or os.path.realpath(home) != os.path.realpath(os.environ.get("HOME", "")):
        os.environ.setdefault("LEETSAY_REAL_HOME", os.path.expanduser("~"))
        if "LEETSAY_MODELS" not in os.environ:
            # Decide where the model is before HOME changes.
            os.environ["LEETSAY_MODELS"] = os.path.join(
                os.environ["LEETSAY_REAL_HOME"], "Library", "Application Support",
                "leetsay", "models")
        home = tempfile.mkdtemp(prefix="leetsay-test-home-")
        os.environ["HOME"] = os.environ["LEETSAY_TEST_HOME"] = home
        import atexit
        atexit.register(shutil.rmtree, home, True)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    support = os.path.join(home, "Library", "Application Support", "leetsay")
    os.makedirs(support, exist_ok=True)
    os.makedirs(os.path.join(home, "Library", "Logs"), exist_ok=True)
    link = os.path.join(support, "models")
    source = models_source()
    if source and not os.path.lexists(link):
        os.symlink(os.path.abspath(source), link)
    return home


HOME = _prepare_home()
MODEL_AVAILABLE = bool(models_source())


def _fail_hard(kind, value, tb):
    traceback.print_exception(kind, value, tb)
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)                         # never hang on a thread or Qt at exit


sys.excepthook = _fail_hard


def say(*parts):
    print(*parts, flush=True)


def load_app():
    """leetsay_mac.py from this repository, loaded fresh."""
    spec = importlib.util.spec_from_file_location("leetsay_mac", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_app = None


def qt_app(style="Fusion"):
    global _app
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([sys.argv[0]])
    if style:
        _app.setStyle(style)
    return _app


def pump(seconds):
    """Let Qt run for this long."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    end = time.monotonic() + seconds
    while True:
        app.processEvents()
        if time.monotonic() >= end:
            break
        time.sleep(0.005)


def wait_until(condition, timeout=30.0):
    """Let Qt run until condition() is true; True if it came in time."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    end = time.monotonic() + timeout
    while True:
        app.processEvents()
        if condition():
            return True
        if time.monotonic() >= end:
            return False
        time.sleep(0.005)


_bad = []


def check(name, condition, extra=""):
    """One check: printed as ok/BAD; a failed one fails the test at the end
    (the rest still runs, so one run shows every problem)."""
    ok = bool(condition)
    if not ok:
        _bad.append(name)
    say(("ok   " if ok else "BAD  ") + name + (f"  ({extra})" if extra else ""))
    return ok


def failures():
    return list(_bad)


def must(name, condition, extra=""):
    """A check the rest of the test depends on: stops at once if it fails."""
    if not check(name, condition, extra):
        finish()


def finish():
    if _bad:
        say(f"FAILED: {len(_bad)} check(s): " + "; ".join(_bad))
        os._exit(1)
    say("all checks passed")
    os._exit(0)


def skip(reason):
    say("SKIP: " + reason)
    os._exit(SKIP_CODE)


def need_model():
    if not MODEL_AVAILABLE:
        skip("no speech model (set LEETSAY_MODELS to a folder holding "
             f"{MODEL_NAME} and {HELPER_NAME})")


def out_dir(name):
    """Where a test may save pictures: LEETSAY_TEST_OUT/<name> when set (to
    look at them), otherwise inside the throwaway HOME (deleted)."""
    base = os.environ.get("LEETSAY_TEST_OUT") or os.path.join(HOME, "test-output")
    folder = os.path.join(base, name)
    os.makedirs(folder, exist_ok=True)
    return folder


# ---------------------------------------------------------------------------
# Spoken test recordings, made on this Mac with `say` (never private files)
# ---------------------------------------------------------------------------
SPEECH = {
    # About 15 s, four sentences with pauses between them (type as you speak
    # types at pauses; the live preview needs a longer recording).
    "speech": ["Hello team, I wanted to share a quick update on the project.",
               "The new design is almost finished and it looks great.",
               "We will test it with a few people next week.",
               "Please send me your notes by Friday afternoon."],
    # A short one, a few seconds.
    "short": ["This is a quick test of the dictation app."],
}
# Words that are spoken clearly and recognised reliably; at least `need` of
# them must be in the text.
KEY_WORDS = {
    "speech": (("hello", "team", "update", "project", "design", "finished", "week",
                "notes", "friday"), 5),
    "short": (("quick", "test", "dictation"), 2),
}
# A private recording may be used instead (LEETSAY_RECORDINGS): the names
# looked for there.
RECORDING_NAMES = {"speech": ("long.wav",), "short": ("short.wav",)}
RATE = 16000
GAP_SECONDS = 0.9


def _fixture_dir():
    folder = os.environ.get("LEETSAY_FIXTURE_DIR") or os.path.join(HOME, "fixtures")
    os.makedirs(folder, exist_ok=True)
    return folder


def _to_16k_wav(source, target):
    subprocess.run(["/usr/bin/afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1",
                    source, target], check=True, capture_output=True, timeout=60)


def _read_pcm(path):
    import numpy as np
    with wave.open(path) as w:
        if w.getframerate() != RATE or w.getnchannels() != 1 or w.getsampwidth() != 2:
            raise ValueError("not 16 kHz mono 16-bit")
        return np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(np.float32) / 32768


def speech(kind="speech"):
    """(audio as float32 at 16 kHz, key words or None). Spoken by `say` with
    the Mac's default voice, sentence by sentence, with pauses between; or a
    recording from LEETSAY_RECORDINGS (then the words are not known)."""
    import numpy as np
    own = os.environ.get("LEETSAY_RECORDINGS")
    if own:
        for name in RECORDING_NAMES[kind]:
            path = os.path.join(os.path.expanduser(own), name)
            if os.path.isfile(path):
                target = os.path.join(_fixture_dir(), "own-" + kind + ".wav")
                if not os.path.isfile(target):
                    _to_16k_wav(path, target)
                return _read_pcm(target), None
    final = os.path.join(_fixture_dir(), kind + ".wav")
    if not os.path.isfile(final):
        if not os.path.exists("/usr/bin/say"):
            skip("macOS's `say` is not available to make the test speech")
        pieces = [np.zeros(int(RATE * 0.3), np.float32)]
        for i, sentence in enumerate(SPEECH[kind]):
            aiff = os.path.join(_fixture_dir(), f"{kind}-{i}.aiff")
            wav = os.path.join(_fixture_dir(), f"{kind}-{i}.wav")
            try:
                subprocess.run(["/usr/bin/say", "-o", aiff, sentence], check=True,
                               capture_output=True, timeout=60)
                _to_16k_wav(aiff, wav)
            except Exception as e:
                skip(f"could not make the test speech with `say`: {e}")
            pieces += [_read_pcm(wav), np.zeros(int(RATE * GAP_SECONDS), np.float32)]
        audio = np.concatenate(pieces)
        peak = float(np.max(np.abs(audio))) or 1.0
        audio = (audio * min(1.0, 0.7 / peak)).astype(np.float32)
        tmp = final + ".tmp"
        with wave.open(tmp, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(RATE)
            w.writeframes((audio * 32767).astype(np.int16).tobytes())
        os.replace(tmp, final)
    return _read_pcm(final), KEY_WORDS[kind]


def plain_words(text):
    return re.sub(r"[^\w\s']", " ", (text or "").lower()).split()


def heard(text, key_words):
    """(ok, which key words were found). With no known words: any text."""
    if key_words is None:
        return bool((text or "").strip()), []
    words, need = key_words
    found = [w for w in words if w in plain_words(text)]
    return len(found) >= need, found


# ---------------------------------------------------------------------------
# A controller with the microphone faked: audio is handed in by the test
# ---------------------------------------------------------------------------
def fake_recorder(d, held_seconds=None):
    """Recorder.start without opening a microphone. held_seconds: make the
    key look held this long already (a callable or a number), else now."""
    def start():
        r = d.recorder
        r.chunks, r.level, r.peak, r.rate = [], 0.0, 0.0, RATE
        held = held_seconds() if callable(held_seconds) else held_seconds
        r.started = time.monotonic() - (held or 0.0)
        r.stream = None
    d.recorder.start = start


def feed(d, audio):
    """Hand audio to the recorder as if the microphone had sent it."""
    d.recorder._audio(audio[:, None], len(audio), None, None)


def feed_real_time(d, audio, step, on_step=None):
    """Hand audio in pieces at the speed it would be spoken, letting Qt run."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    t0 = time.monotonic()
    for i in range(0, len(audio), step):
        piece = audio[i:i + step]
        feed(d, piece)
        end = t0 + (i + step) / RATE
        while time.monotonic() < end:
            app.processEvents()
            time.sleep(0.005)
        if on_step:
            on_step(time.monotonic() - t0)
    return t0


def load_model(d):
    d._load_model()
    qt_app(None).processEvents()
    must("speech model loaded", d.model is not None, getattr(d, "model_error", ""))
    say(f"model loaded in {d.load_seconds:.1f} s")
