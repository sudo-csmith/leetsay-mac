"""Fetch the speech model and the speech detector for the tests into a
folder, with leetsay's OWN download code (download_release): only from this
project's releases on github.com, every file checked against its SHA-256
before it is kept. Files already there that match are not fetched again.

    .venv/bin/python -I tests/get_model.py FOLDER       fetch / check
    .venv/bin/python -I tests/get_model.py --cache-key  print a cache key

Then: LEETSAY_MODELS=FOLDER .venv/bin/python -I tests/run_all.py
This goes online (github.com), so it is never run by the tests themselves.
"""
import os
import sys

sys.dont_write_bytecode = True

import importlib.util
import shutil
import tempfile

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
APP_FILE = os.path.join(os.path.dirname(TESTS_DIR), "leetsay_mac.py")


def load_app():
    # A throwaway HOME: importing the app must never touch the real settings.
    home = tempfile.mkdtemp(prefix="leetsay-get-model-")
    os.environ["HOME"] = home
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    spec = importlib.util.spec_from_file_location("leetsay_mac", APP_FILE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, home


def matches(m, folder, release):
    for name, (size, sha) in release["files"].items():
        path = os.path.join(folder, name)
        if not os.path.isfile(path) or os.path.getsize(path) != size \
                or m.file_fingerprint(path) != sha:
            return False
    return True


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    m, home = load_app()
    model_release = m.current_release(m.MODEL)
    wanted = [(m.MODEL, model_release), (m.HELPER, m.HELPER_RELEASE)]
    try:
        if sys.argv[1] == "--cache-key":
            print("leetsay-models-" + "-".join(r["tag"] for _name, r in wanted))
            return 0
        root = os.path.abspath(os.path.expanduser(sys.argv[1]))
        os.makedirs(root, exist_ok=True)
        for name, release in wanted:
            folder = os.path.join(root, name)
            if os.path.isdir(folder) and matches(m, folder, release):
                print(f"{release['tag']}: already here, every file matches")
                continue
            print(f"{release['tag']}: fetching {m.size_words(m._release_bytes(release))} "
                  "from this project's releases on github.com", flush=True)
            m.open_network("test model download")
            try:
                m.download_release(release, folder)
            finally:
                m.close_network()
            if not matches(m, folder, release):          # download_release checks too
                print(f"{release['tag']}: files do not match after the download")
                return 1
            print(f"{release['tag']}: fetched, every file matches", flush=True)
        return 0
    finally:
        shutil.rmtree(home, ignore_errors=True)


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    os._exit(code)
