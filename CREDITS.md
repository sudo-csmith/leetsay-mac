# Credits

## Speech model

leetsay uses **Parakeet TDT 0.6B v2** (English) and, if you choose it,
**Parakeet TDT 0.6B v3** (25 European languages), speech recognition models
made by NVIDIA and released under the
[Creative Commons Attribution 4.0 International licence (CC-BY-4.0)](https://creativecommons.org/licenses/by/4.0/).

- Original work by NVIDIA Corporation. NVIDIA's model pages (with their model
  cards, which describe what the models can and cannot do):
  [v2](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v2) and
  [v3](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3).
- leetsay downloads them from this project's own model page,
  [leetsay-models](https://github.com/sudo-csmith/leetsay-models), where they
  are converted in the open from NVIDIA's originals. Changes made: exported to
  the ONNX format with NVIDIA's own toolkit, and weights reduced to 8 bits
  (int8). Nothing was retrained. The exact source version, the steps and the
  fingerprints are published there.
- NVIDIA has not reviewed or endorsed leetsay or these conversions.
- The models are not covered by leetsay's MIT licence. Their licence,
  CC-BY-4.0, applies to them, and they are provided by their authors without
  warranty.

Please note: the websites linked here are third-party websites that we do
not run or control.

## Speech detector

leetsay uses the **Silero VAD** voice activity model, Copyright (c)
2020-present Silero Team, under the MIT licence
([snakers4/silero-vad](https://github.com/snakers4/silero-vad)), so that
silence is not read as words. leetsay downloads it, unchanged, from
[leetsay-models](https://github.com/sudo-csmith/leetsay-models); it is the
file from Silero VAD's official release v6.2.3, with its licence.

## Libraries

- [Qt](https://www.qt.io) and [Qt for Python](https://www.qt.io/qt-for-python)
  (PySide6 and shiboken6), by The Qt Company and contributors, under the
  GNU Lesser General Public License v3 (LGPL-3.0): windows, the pop-up and
  the menu bar icon. leetsay uses only the modules QtCore, QtGui and
  QtWidgets, unchanged, version 6.12.0. Source code of that version:
  [Qt 6.12.0](https://download.qt.io/archive/qt/6.12/6.12.0/) and
  [Qt for Python v6.12.0](https://code.qt.io/cgit/pyside/pyside-setup.git/tag/?h=v6.12.0).
  The app is a folder of files, not one packed file, so the Qt libraries in
  it can be replaced with other versions (see `README.txt` in its licences
  folder). Qt itself contains code from other projects (FreeType, HarfBuzz,
  libpng, libjpeg-turbo, PCRE2, zlib and others) under their own licences;
  they are listed in `Qt-third-party.txt` in the licences folder and on the
  Qt Project's [licences page](https://doc.qt.io/qt-6/licenses-used-in-qt.html).
- [onnx-asr](https://github.com/istupakov/onnx-asr) (MIT): runs the speech models.
- [ONNX Runtime](https://github.com/microsoft/onnxruntime) (MIT, with the
  third-party notices it ships): the speech engine. It uses
  [protobuf](https://github.com/protocolbuffers/protobuf) (BSD-3-Clause),
  [flatbuffers](https://github.com/google/flatbuffers) (Apache-2.0),
  [packaging](https://github.com/pypa/packaging) (Apache-2.0 or BSD-2-Clause),
  [coloredlogs](https://github.com/xolox/python-coloredlogs) and
  [humanfriendly](https://github.com/xolox/python-humanfriendly) (MIT), and
  [SymPy](https://www.sympy.org) with [mpmath](https://mpmath.org)
  (BSD-3-Clause).
- [sounddevice](https://github.com/spatialaudio/python-sounddevice) (MIT),
  with [PortAudio](https://www.portaudio.com) (MIT) and
  [cffi](https://github.com/python-cffi/cffi) (MIT-0) /
  [pycparser](https://github.com/eliben/pycparser) (BSD-3-Clause): the
  microphone.
- [NumPy](https://numpy.org) (BSD-3-Clause, with the licences of its bundled
  parts): audio handling.
- [Python](https://www.python.org) (PSF License), inside the app, with the
  software built into it (OpenSSL under Apache-2.0, expat, libffi, zlib,
  mpdecimal, XZ, bzip2 and others).
- macOS's own system frameworks, used as they come with macOS.

Each of these is the work of its own authors and is used under its own
licence; the MIT licence of leetsay does not cover them. The app includes the
full text of every one of these licences, in
`leetsay.app/Contents/Resources/licenses`.

## Trademarks and affiliation

leetsay is an independent project. It is not affiliated with, endorsed or
sponsored by Apple, NVIDIA, GitHub, Microsoft, the Qt Company, the Silero Team
or the Python Software Foundation. Apple, Mac and macOS are trademarks of
Apple Inc. All other product names and trademarks belong to their respective
owners and are used only to describe what leetsay works with.

## leetsay itself

The icon is drawn in code: four bars with heights 1, 3, 3 and 7.
