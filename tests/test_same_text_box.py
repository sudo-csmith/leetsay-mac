"""Words go only into the text box the dictation started in: a box that
grows a line is still the same one; another box in the same window is not
(Windows' cases). Then dictations with the text box faked: moving to another
box shows "Go back to your text box to type there" on the card, and at the
end "You moved to another text box, so it wasn't typed" ("...so the rest
wasn't typed" with type as you speak); staying in the first box types."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import time, types

m = load_app()


def judge(start, now):
    return m.Dictation._box_moved(types.SimpleNamespace(start_rect=start), now)


start = (100, 500, 700, 540)
check("same box", not judge(start, start))
check("grew upwards: same box", not judge(start, (100, 480, 700, 540)))
check("grew downwards: same box", not judge(start, (100, 500, 700, 580)))
check("a few points off: same box", not judge(start, (104, 503, 696, 538)))
check("a box higher up: another box", judge(start, (100, 200, 700, 240)))
check("a box beside it: another box", judge(start, (800, 500, 1200, 540)))
check("didn't start in a box: not judged", not judge(None, (1, 2, 3, 4)))
check("place unknown: not judged", not judge(start, None))

need_model()
app = qt_app(None)
typed, shown = [], []
box = {"rect": start}
m.type_text = lambda text: typed.append(text) and None
m.focused_text_box = lambda: "yes"
m.start_box_rect = lambda: box["rect"]
m.front_pid = lambda: 4242
m.mic_permission = lambda: m.MIC_OK
m.SOUNDS = False
m.TEXTBOX_ONLY = True
d = m.Dictation(app)
load_model(d)
fake_recorder(d)
d.hotkey.physically_down = lambda: True
real_show = d.overlay.show_message
d.overlay.show_message = lambda text, *a, **k: (shown.append(text), real_show(text, *a, **k))
audio, key = speech("short")


def dictate(live, move_at=None, back=False):
    m.LIVE_TYPE = live
    typed.clear()
    shown.clear()
    box["rect"] = start
    d.on_press()
    card = []

    def step(at):
        if move_at is not None and at >= move_at and box["rect"] == start and not card:
            box["rect"] = (100, 200, 700, 240)           # another box higher up
        if box["rect"] != start:
            card.append(d.overlay._mic_warning())
        if back and at >= move_at + 1.5:
            box["rect"] = start
    feed_real_time(d, audio, 640, step)
    d.on_release()
    wait_until(lambda: d.reading_since is None and not d.lt_active, 60)
    pump(1.5)
    return "".join(typed), card, list(shown)


for live in (False, True):
    mode = "type as you speak" if live else "normal"
    full, card, said = dictate(live)
    check(f"{mode}: stays in the first box: typed", heard(full, key)[0], full)
    full, card, said = dictate(live, move_at=0.5)
    check(f"{mode}: card says go back", m.Overlay.MOVED_BOX in card, card[-3:])
    end = ("You moved to another text box, so the rest wasn't typed" if live
           else "You moved to another text box, so it wasn't typed")
    check(f"{mode}: moved: nothing typed and it says so",
          not full.strip() and end in said, (full, said))
    full, card, said = dictate(live, move_at=0.5, back=True)
    check(f"{mode}: came back to the first box: typed", heard(full, key)[0], (full, said))
finish()
