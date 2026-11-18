"""The download parts, offline: nothing leaves this Mac. 1. the network
guard (closed, opened for github only, look-alikes, listening, closed again);
2. the model files on this Mac match the release fingerprints; 3. fetching
and checking with file:// copies: a right file kept, a wrong one refused and
deleted, an interrupted part completed, a release fetched from this project's
URLs only into a staging folder that is then swapped in. Part 1 needs no
model; parts 2 and 3 do. (Was downloadtest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import shutil, socket

m = load_app()


def refused(fn):
    try:
        fn()
        return False
    except m.NetworkBlocked:
        return True
    except Exception as e:
        return f"other: {type(e).__name__}"


# 1. the guard
check("closed: a lookup is refused", refused(lambda: socket.getaddrinfo("github.com", 443)) is True)
check("closed: a connection is refused",
      refused(lambda: socket.create_connection(("1.1.1.1", 443), timeout=1)) is True)
import urllib.request
check("closed: urllib is refused",
      refused(lambda: urllib.request.urlopen("https://github.com", timeout=2)) is True)
check("check at start passes", m.verify_network_block() is True)
m.open_network("test")
check("open: other sites are still refused",
      refused(lambda: socket.getaddrinfo("example.com", 443)) is True)
check("open: a number never looked up is refused",
      refused(lambda: socket.create_connection(("140.82.112.3", 443), timeout=1)) is True)
s = socket.socket()
check("open: listening is refused", refused(lambda: s.bind(("127.0.0.1", 0))) is True)
s.close()
check("open: github names are allowed", all(m._host_allowed(h) for h in (
    "github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com")))
check("open: look-alikes are not", not any(m._host_allowed(h) for h in (
    "github.com.evil.example", "evilgithub.com", "githubusercontent.com")))
m.close_network()
check("closed again", refused(lambda: socket.getaddrinfo("github.com", 443)) is True)
check("total to fetch for v3 is about 670 MB",
      660e6 < m._release_bytes(m.current_release("nemo-parakeet-tdt-0.6b-v3")) < 680e6)

if not MODEL_AVAILABLE:
    if failures():
        finish()
    skip("part 1 (the network guard) passed; parts 2 and 3 need the speech model")

# 2. the files on this Mac
check("v2 files match the release", m.matching_release() is m.current_release())
check("speech detector matches", m.helper_ok())
v3 = os.path.join(models_source(), "nemo-parakeet-tdt-0.6b-v3")
if not os.path.isdir(v3):
    check("v3 is not here, and is reported missing",
          m.local_model_dir("nemo-parakeet-tdt-0.6b-v3") == "")

# 3. downloading and checking, with local files (file:// address, no network)
work = os.path.join(HOME, "dltest")
shutil.rmtree(work, ignore_errors=True)
os.makedirs(work)
src = os.path.join(m.helper_dir(), "silero_vad.onnx")
size, sha = m.HELPER_RELEASE["files"]["silero_vad.onnx"]
m.open_network("test")
dest = os.path.join(work, "silero_vad.onnx")
m._download_file("file://" + src, dest, size, sha)
check("a right file is kept", os.path.isfile(dest) and m.file_fingerprint(dest) == sha)
try:
    m._download_file("file://" + src, os.path.join(work, "wrong.onnx"), size, "0" * 64)
    check("a wrong file is refused", False)
except IOError:
    check("a wrong file is refused and deleted",
          not os.path.exists(os.path.join(work, "wrong.onnx.part"))
          and not os.path.exists(os.path.join(work, "wrong.onnx")))
half = os.path.join(work, "half.onnx")
with open(src, "rb") as f, open(half + ".part", "wb") as out:
    out.write(f.read(size // 2))
m._download_file("file://" + src, half, size, sha)
check("an interrupted part is completed", m.file_fingerprint(half) == sha)
calls = []
real = m._download_file
m._download_file = lambda url, path, sz, sh: (calls.append(url), shutil.copy(
    os.path.join(m.helper_dir(), os.path.basename(path)), path))
target = os.path.join(work, "silero-vad")
m.download_release(m.HELPER_RELEASE, target)
prefix = "https://github.com/%s/releases/download/%s/" % (m.MODELS_REPO, m.HELPER_RELEASE["tag"])
check("release: files fetched from this project's releases only",
      calls and all(u.startswith(prefix) for u in calls), calls[:1])
check("release: staging folder swapped in",
      os.path.isdir(target) and not os.path.isdir(target + ".download"))
m._download_file = real
m.close_network()
shutil.rmtree(work, ignore_errors=True)
finish()
