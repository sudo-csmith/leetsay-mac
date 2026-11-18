"""The update check offers the right download for the Mac it runs on, with
the fixed release names leetsay-mac-apple-silicon.dmg and
leetsay-mac-intel.dmg, whatever order they are listed in, for both kinds of
Mac (the processor is faked), and never the other kind's file or the
fingerprint list. Offline: the GitHub reply is faked."""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import io, json

m = load_app()
import urllib.request
import platform
BASE = "https://github.com/%s/releases" % m.APP_REPO


class Reply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def release(names):
    return {"tag_name": "v9.9.9", "html_url": BASE + "/tag/v9.9.9", "body": "",
            "assets": [{"name": n, "browser_download_url": BASE + "/download/v9.9.9/" + n}
                       for n in names]}


m.mac_ssl_context = lambda: None
FILES = ["leetsay-mac-apple-silicon.dmg", "leetsay-mac-intel.dmg", "SHA256SUMS.txt"]
for machine, want, other in (("arm64", "leetsay-mac-apple-silicon.dmg", "intel"),
                             ("x86_64", "leetsay-mac-intel.dmg", "apple-silicon")):
    platform.machine = lambda machine=machine: machine
    for order in (FILES, list(reversed(FILES))):
        urllib.request.urlopen = (lambda req, timeout=None, context=None, order=order:
                                  Reply(json.dumps(release(order)).encode()))
        r = m.fetch_latest_release()
        check(f"{machine}, listed {order[0]} first: offers {want}",
              r[2] == BASE + "/download/v9.9.9/" + want, r[2])
        check(f"{machine}: never the {other} file", other not in r[2].rsplit("/", 1)[-1])
# Only the fingerprint list or nothing for this kind: no download link, the
# release page is still offered.
platform.machine = lambda: "arm64"
urllib.request.urlopen = (lambda req, timeout=None, context=None:
                          Reply(json.dumps(release(["leetsay-mac-intel.dmg",
                                                    "SHA256SUMS.txt"])).encode()))
r = m.fetch_latest_release()
check("Apple silicon, only the Intel file there: no download offered", r[2] == "", r[2])
check("... but the release page is", str(r[1]).startswith(BASE), r[1])
check("network closed after", not m.network_is_open())
finish()
