"""copy_privately(): the text goes on a pasteboard marked Concealed and
Transient (clipboard managers that follow nspasteboard.org skip it). Uses a
private pasteboard, never the user's clipboard. (Was pbtest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
from ctypes import c_void_p, c_char_p

m = load_app()
pb = m.objc(m.objc_class("NSPasteboard"), "pasteboardWithUniqueName")
must("a private pasteboard", bool(pb))
try:
    m.copy_privately("hello from the test", pb)
    types = m.objc(pb, "types")
    n = m.objc(types, "count", restype=m.c_ulong)
    names = [m._nsstring(m.objc(types, "objectAtIndex:", i, argtypes=(m.c_ulong,)))
             for i in range(n)]
    ns = lambda v: m.objc(m.objc_class("NSString"), "stringWithUTF8String:", v.encode(),
                          argtypes=(c_char_p,))
    text = m._nsstring(m.objc(pb, "stringForType:", ns("public.utf8-plain-text"),
                              argtypes=(c_void_p,)))
    say("types:", names)
    check("the text is there", text == "hello from the test", repr(text))
    check("marked concealed", "org.nspasteboard.ConcealedType" in names)
    check("marked transient", "org.nspasteboard.TransientType" in names)
finally:
    m.objc(pb, "releaseGlobally", restype=None)
finish()
