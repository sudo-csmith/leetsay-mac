"""Idle cost once set up: which timers run, and the processor time used over
10 s of doing nothing must stay small (measured well under 1 % on the test
Mac; the limit here is generous for busy CI machines). (Was idletest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time, cProfile, pstats

LIMIT = float(os.environ.get("LEETSAY_IDLE_CPU_LIMIT", "1.5"))   # seconds of CPU in 10 s
m = load_app()
from PySide6.QtCore import QTimer
app = qt_app(None)
m.mic_permission = lambda: m.MIC_OK
d = m.Dictation(app)
d.hotkey.port = 1                               # as if set up
d.overlay.show_idle()
pump(3)
active = sorted((tm.interval(), tm.parent().__class__.__name__ if tm.parent() else None)
                for tm in set(app.findChildren(QTimer) + d.findChildren(QTimer)
                              + d.overlay.findChildren(QTimer)) if tm.isActive())
say("active timers:", active)
check("no timer faster than 80 ms while idle", all(ms >= 80 for ms, _ in active), active)
pr = cProfile.Profile()
pr.enable()
c0 = time.process_time()
pump(10)
used = time.process_time() - c0
pr.disable()
say("cpu over 10 s idle: %.2f s" % used)
pstats.Stats(pr).sort_stats("cumulative").print_stats(8)
check(f"idle processor time under {LIMIT} s in 10 s", used < LIMIT, f"{used:.2f} s")
finish()
