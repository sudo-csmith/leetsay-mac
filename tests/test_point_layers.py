"""Beta, point at a text box: web pages and code editors answer with the line
of text under the mouse, not the box round it, so what holds it is looked at
up to 6 layers up for the text box itself (as Windows cf924f9; the Mac
looked 2 up before). Never a password box, never read-only text, never past
the page or the window, never another app. macOS is not asked: its
accessibility calls are replaced by a made-up tree of elements."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import ctypes

m = load_app()
PID = 4242
tree = {}                                # element number -> (role, subrole, parent, settable)
focused = []


def build(*layers):
    """layers from the element under the mouse upwards: (role, subrole, settable)."""
    tree.clear()
    focused.clear()
    for i, (role, sub, settable) in enumerate(layers, start=1):
        tree[i] = (role, sub, i + 1 if i < len(layers) else 0, settable)


def at_position(_system, x, y, out):
    out._obj.value = 1 if tree else None
    return 0


def get_pid(element, out):
    out._obj.value = PID
    return 0


m.AXUIElementCopyElementAtPosition = at_position
m.AXUIElementGetPid = get_pid
m.AXUIElementCreateSystemWide = lambda: 99
m.AXUIElementSetMessagingTimeout = lambda *a: 0
m._ax_system = 99
m.CFRelease = lambda value: None
m._ax_string = lambda node, name: (tree[node][0] if name == "AXRole" else tree[node][1])
m._ax_copy = lambda node, name: tree[node][2] or None
m._ax_name = lambda name: name


def settable(node, name, out):
    out._obj.value = tree[node][3]
    return 0


m.AXUIElementIsAttributeSettable = settable
m.AXUIElementSetAttributeValue = lambda node, name, value: (focused.append(node), 0)[1]


def point(*layers):
    build(*layers)
    return m.select_text_box_at(10, 10, PID), list(focused)


line = ("AXStaticText", "", False)
group = ("AXGroup", "", False)
box = ("AXTextArea", "", True)
window = ("AXWindow", "AXStandardWindow", False)

done, which = point(box, window)
check("the text box itself", done and which == [1], which)
done, which = point(line, group, group, group, group, box, window)
check("a text box 5 layers up (a code editor's line)", done and which == [6], which)
done, which = point(line, group, group, group, group, group, box, window)
check("a text box 6 layers up", done and which == [7], which)
done, which = point(line, group, group, group, group, group, group, box, window)
check("7 layers up: too far, nothing selected", not done and not which, which)
done, which = point(line, ("AXSecureTextField", "", True), window)
check("never a password box", not done and not which)
done, which = point(line, group, ("AXTextField", "AXSecureTextField", True), window)
check("never a password box (by its subrole)", not done and not which)
done, which = point(line, group, ("AXTextArea", "", False), window)
check("never read-only text", not done and not which)
done, which = point(line, group, ("AXWebArea", "", False), group, box, window)
check("never past the web page", not done and not which)
done, which = point(("AXButton", "AXSearchFieldCancelButton", False),
                    ("AXSearchField", "", True), window)
check("a search field's clear button leads to the field", done and which == [2], which)
m.AXUIElementGetPid = lambda element, out: (setattr(out._obj, "value", 1), 0)[1]
done, which = point(box, window)
check("another app's text box: never", not done and not which)
finish()
