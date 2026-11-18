"""Measurement only (never fails): does numpy reserve memory per processor
thread here, and does limiting its threads change memory or speed? Each
setting runs in a fresh process: numpy alone, then the speech model loaded
and reading the test speech three times (if the model is available)."""
import os, sys, subprocess, json
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

CHILD = r'''
import os, sys, time, json, resource, subprocess
sys.dont_write_bytecode = True
def rss():
    return int(subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())],
                              capture_output=True, text=True).stdout) / 1024
before = rss()
import numpy as np
out = {"before": before, "numpy": rss()}
cfg = np.show_config(mode="dicts")["Build Dependencies"]["blas"]
out["blas"] = "%s %s" % (cfg.get("name"), cfg.get("version"))
models = sys.argv[1]
if models:
    import onnx_asr, onnxruntime as ort
    o = ort.SessionOptions(); o.enable_cpu_mem_arena = False
    o.intra_op_num_threads = min(4, os.cpu_count() or 4); o.inter_op_num_threads = 1
    m = onnx_asr.load_model("nemo-parakeet-tdt-0.6b-v2",
                            os.path.join(models, "nemo-parakeet-tdt-0.6b-v2"),
                            quantization="int8", sess_options=o,
                            providers=["CPUExecutionProvider"])
    out["loaded"] = rss()
    audio = np.load(sys.argv[2]) if sys.argv[2] else np.zeros(16000 * 15, np.float32)
    m.recognize(audio[:16000])
    times = []
    for _ in range(3):
        t = time.perf_counter(); m.recognize(audio); times.append(time.perf_counter() - t)
    out["read"] = min(times); out["seconds"] = len(audio) / 16000
out["peak"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1048576
print(json.dumps(out))
'''

from _common import MODEL_AVAILABLE, models_source, speech, HOME
import numpy as np
models = models_source() if MODEL_AVAILABLE else ""
audio_file = ""
if models:
    try:
        audio, _words = speech("speech")
        audio_file = os.path.join(HOME, "bench-speech.npy")
        np.save(audio_file, audio.astype(np.float32))
    except Exception:
        audio_file = ""
print(f"processor: {os.uname().machine}, {os.cpu_count()} threads; model: "
      f"{'yes' if models else 'no (numpy only)'}", flush=True)
for label, extra in (("default", {}), ("OPENBLAS_NUM_THREADS=1", {"OPENBLAS_NUM_THREADS": "1"}),
                     ("VECLIB_MAXIMUM_THREADS=1", {"VECLIB_MAXIMUM_THREADS": "1"}),
                     ("OMP_NUM_THREADS=1", {"OMP_NUM_THREADS": "1"})):
    env = dict(os.environ, **extra)
    for run in (1, 2):
        r = subprocess.run([sys.executable, "-I", "-c", CHILD, models or "", audio_file],
                           env=env, capture_output=True, text=True)
        try:
            d = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            print(f"{label:26s} run {run}: failed: {r.stderr.strip()[-200:]}", flush=True)
            continue
        line = (f"{label:26s} run {run}: blas {d['blas']}; numpy import +{d['numpy'] - d['before']:.0f} MB")
        if "loaded" in d:
            line += (f"; model loaded {d['loaded']:.0f} MB; peak {d['peak']:.0f} MB; "
                     f"read {d['seconds']:.0f} s in {d['read']:.2f} s")
        print(line, flush=True)
