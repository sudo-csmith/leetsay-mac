"""The speech check before reading (same rules as Windows 0.2.4): voices at
four loudness levels (x1, x0.1, x0.02, x0.005) and four noises (silence,
hiss, clicks, hum), long and short, through the real voice detector.
Speech at x1 and x0.1 must always be transcribed; whatever isn't must have a
pop-up reason; the check must stay fast."""
import os, sys, subprocess, tempfile, time, wave
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

need_model()
m = load_app()
import numpy as np
import onnx_asr

R = 16000
started = time.perf_counter()
vad = onnx_asr.load_vad("silero", m.helper_dir())
say(f"detector loaded in {(time.perf_counter() - started) * 1000:.0f} ms")


class Holder:
    pass


holder = Holder()
holder.vad = vad
tmp = tempfile.mkdtemp()


def spoken(voice, text):
    a, w = os.path.join(tmp, "a.aiff"), os.path.join(tmp, "a.wav")
    cmd = ["say", "-o", a] + (["-v", voice] if voice else []) + [text]
    if subprocess.run(cmd, capture_output=True).returncode != 0:
        return None
    subprocess.run(["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", a, w], check=True)
    with wave.open(w) as h:
        x = np.frombuffer(h.readframes(h.getnframes()), np.int16).astype(np.float32) / 32768
    return x / max(1e-6, float(np.max(np.abs(x)))) * 0.6


slowest = 0.0


def decide(audio):
    global slowest
    t = time.perf_counter()
    found = m.Dictation.has_speech(holder, audio, R)
    slowest = max(slowest, (time.perf_counter() - t) * 1000)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    return m.speech_decision(found, peak, len(audio) / R)


voices = [v for v in ("Samantha", "Daniel", "Karen", "Moira", "Rishi", "Tessa", None)
          if spoken(v, "test") is not None]
if not voices:
    skip("the say command is not available")
say("voices:", ", ".join(v or "default" for v in voices))
for voice in voices:
    for kind, text in (("long", "Please send the report to the team before the "
                                 "meeting on Friday afternoon."), ("short", "Okay.")):
        x = spoken(voice, text)
        for level in (1, 0.1, 0.02, 0.005):
            d = decide(x * level)
            if level in (1, 0.1):
                check(f"{voice or 'default'} {kind} x{level}: transcribed", d == "read", d)
            else:
                say(f"     {voice or 'default'} {kind} x{level}: {d}")
rng = np.random.default_rng(1)
for secs, kind in ((4.0, "long"), (0.8, "short")):
    n = int(secs * R)
    clicks = np.zeros(n, np.float32)
    clicks[::R // 3] = 0.5
    noises = {"silence": np.zeros(n, np.float32),
              "hiss": (rng.standard_normal(n) * 0.02).astype(np.float32),
              "clicks": clicks,
              "hum": (0.05 * np.sin(2 * np.pi * 60 * np.arange(n) / R)).astype(np.float32)}
    for name, audio in noises.items():
        d = decide(audio)
        if name == "silence":
            check(f"silence {kind}: 'Can't hear you'", d == "quiet", d)
        elif kind == "short":
            check(f"{name} short: 'Didn't catch that'", d == "noise", d)
        else:
            check(f"{name} long: transcribed anyway (2 s or more)", d == "read", d)
check("each check under 300 ms", slowest < 300, f"slowest {slowest:.0f} ms")
finish()
