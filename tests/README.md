# leetsay for Mac: tests

Off-screen tests of `leetsay_mac.py`. Nothing is shown on screen, the
microphone is never opened, nothing is really typed, macOS is never asked
for a permission, and nothing goes online.

## Running them

```sh
.venv/bin/python -I tests/run_all.py               # every test
.venv/bin/python -I tests/run_all.py flow toggle   # only these
.venv/bin/python -I tests/run_all.py --verbose     # with each test's output
.venv/bin/python -I tests/run_all.py --bench       # the benchmarks instead
```

Each test runs in its own process with a fresh, throwaway HOME (the app
keeps its settings, log and lock file under HOME, so your own leetsay, even
a running one, is never touched) and `QT_QPA_PLATFORM=offscreen`. One line
per test: PASS, FAIL or SKIP, the time, and the test's last line. A failed
test's full output is shown. The exit code is 1 if any test failed. Each test
has a time limit (`--timeout`, 180 s by default).

A single test can also be run on its own (it makes its own throwaway HOME):
`QT_QPA_PLATFORM=offscreen .venv/bin/python -I -u tests/test_flow.py`.

## The speech model

Tests that read speech (after_key, kept_text, flow, live_type, toggle, and
parts 2-3 of download) need the speech model. By default they use your own
leetsay's, from `~/Library/Application Support/leetsay/models` (linked into
the throwaway HOME, never changed). Without it they are SKIPPED, not failed.

- `LEETSAY_MODELS=/some/folder`: use the model in that folder instead
  (it must hold `nemo-parakeet-tdt-0.6b-v2` and `silero-vad`). Set it to an
  empty folder to run without a model.
- `tests/get_model.py FOLDER` fetches the model into FOLDER with leetsay's
  own download code (this project's releases on github.com only; every
  file's SHA-256 checked). It goes online; the tests themselves never do.

## Test speech

Recordings are made at test time with macOS's own `say` (the default voice),
sentence by sentence with pauses between, and converted to 16 kHz with
`afconvert`, in a temporary folder. Checks look for a few clearly spoken
words, not the exact text. `LEETSAY_RECORDINGS=/some/folder` uses your own
recordings instead (`speech.wav`, a longer one with pauses, and `leetsay.wav`
or `short.wav`, a few seconds); then any recognised text counts.
Never add recordings to the repository.

## Pictures

Several tests draw windows and the pop-up. Set `LEETSAY_TEST_OUT=/some/folder`
to keep those pictures (one folder per test); otherwise they are thrown away.

## Benchmarks

`--bench` runs `bench_*.py` instead of the tests: they print numbers (for
example the time from letting go to the text being typed) and never fail.
They are not run by default or on GitHub.

## On GitHub

`.github/workflows/tests.yml` runs `run_all.py` on every push and pull
request on a `macos-15` runner, with the model kept in GitHub's cache.
