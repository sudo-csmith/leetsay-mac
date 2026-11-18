"""Run leetsay for Mac's off-screen tests, each in its own process with a
fresh throwaway HOME, and print one line per test.

    .venv/bin/python -I tests/run_all.py              every test
    .venv/bin/python -I tests/run_all.py flow toggle  only tests whose names hold these words
    .venv/bin/python -I tests/run_all.py --bench      the benchmarks instead (numbers only)

Options: --timeout SECONDS (per test, default 180), --verbose (every test's
full output; a failed test's output is always shown), --keep (keep the
throwaway HOME folders). Exit code 1 if any test failed. See README.md.
"""
import os
import sys

sys.dont_write_bytecode = True

import argparse
import glob
import shutil
import subprocess
import tempfile
import time

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
SKIP_CODE = 77


def main():
    parser = argparse.ArgumentParser(description="Run leetsay's off-screen tests.")
    parser.add_argument("names", nargs="*", help="only tests whose file names hold these")
    parser.add_argument("--bench", action="store_true", help="run the benchmarks instead")
    parser.add_argument("--timeout", type=float, default=180.0, help="seconds per test")
    parser.add_argument("--verbose", "-v", action="store_true", help="show every test's output")
    parser.add_argument("--keep", action="store_true", help="keep the throwaway HOME folders")
    args = parser.parse_args()

    pattern = "bench_*.py" if args.bench else "test_*.py"
    files = sorted(glob.glob(os.path.join(TESTS_DIR, pattern)))
    if args.names:
        files = [f for f in files if any(n in os.path.basename(f) for n in args.names)]
    if not files:
        print("no tests found")
        return 1

    real_home = os.path.expanduser("~")
    models = os.environ.get("LEETSAY_MODELS")
    if models is None:
        models = os.path.join(real_home, "Library", "Application Support", "leetsay", "models")
    models = os.path.abspath(os.path.expanduser(models))
    fixtures = tempfile.mkdtemp(prefix="leetsay-test-speech-")
    print(f"{len(files)} {'benchmark' if args.bench else 'test'}(s); speech model: "
          f"{'from LEETSAY_MODELS' if 'LEETSAY_MODELS' in os.environ else 'your leetsay'}"
          f"{'' if os.path.isdir(models) else ' (not found: model tests will be skipped)'}",
          flush=True)

    results = []
    try:
        for path in files:
            name = os.path.splitext(os.path.basename(path))[0]
            home = tempfile.mkdtemp(prefix="leetsay-test-home-")
            env = dict(os.environ)
            env.update(HOME=home, LEETSAY_TEST_HOME=home, LEETSAY_REAL_HOME=real_home,
                       LEETSAY_MODELS=models, LEETSAY_FIXTURE_DIR=fixtures,
                       QT_QPA_PLATFORM="offscreen", TMPDIR=os.path.join(home, "tmp"))
            os.makedirs(env["TMPDIR"])
            t0 = time.monotonic()
            try:
                run = subprocess.run([sys.executable, "-I", "-u", path], env=env, cwd=home,
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     timeout=args.timeout)
                output = run.stdout.decode("utf-8", "replace")
                code = run.returncode
            except subprocess.TimeoutExpired as e:
                output = (e.stdout or b"").decode("utf-8", "replace")
                output += f"\n(stopped after {args.timeout:.0f} s)"
                code = "timeout"
            seconds = time.monotonic() - t0
            if args.bench:
                status = "DONE" if code == 0 else ("SKIP" if code == SKIP_CODE else "ERROR")
            else:
                status = "PASS" if code == 0 else ("SKIP" if code == SKIP_CODE else "FAIL")
            lines = [ln for ln in output.strip().splitlines() if ln.strip()]
            last = lines[-1].strip() if lines else ""
            print(f"{status:5} {name:22} {seconds:6.1f}s  {last[:90]}", flush=True)
            if args.verbose or args.bench or status in ("FAIL", "ERROR"):
                print("    " + "\n    ".join(output.rstrip().splitlines()), flush=True)
            results.append(status)
            if args.keep:
                print(f"      HOME kept: {home}")
            else:
                shutil.rmtree(home, ignore_errors=True)
    finally:
        shutil.rmtree(fixtures, ignore_errors=True)

    counts = {s: results.count(s) for s in ("PASS", "FAIL", "SKIP", "DONE", "ERROR")}
    print(", ".join(f"{n} {s.lower()}" for s, n in counts.items() if n), flush=True)
    if args.bench:
        return 0                                  # benchmarks never fail
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
