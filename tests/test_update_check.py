"""Update check, offline: a fake GitHub reply. The network guard is closed
before, open only during the check, closed after; links that are not this
project's are dropped; the minimum safe version is read; versions compare.
No real request is made. (Was updatetest.)"""
import os, sys
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *
import io, json

m = load_app()
import urllib.request
seen = {}


class Reply(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *a): pass


def fake_urlopen(req, timeout=None, context=None):
    seen["open_during"] = m.network_is_open()
    seen["url"] = req.full_url
    base = "https://github.com/%s/releases" % m.APP_REPO
    return Reply(json.dumps({
        "tag_name": "v99.0.0",
        "html_url": base + "/tag/v99.0.0",
        "body": "Minimum safe version: 0.0.30",
        "assets": [
            {"name": "leetsay-mac-intel.dmg",
             "browser_download_url": base + "/download/v99.0.0/leetsay-mac-intel.dmg"},
            {"name": "leetsay-mac-apple-silicon.dmg",
             "browser_download_url": "https://evil.example/x.dmg"}]}).encode())


urllib.request.urlopen = fake_urlopen
m.mac_ssl_context = lambda: None
check("guard closed before", not m.network_is_open())
r = m.fetch_latest_release()
say("result:", r)
check("the check asked GitHub's API for this project",
      seen.get("url", "").startswith("https://api.github.com/repos/%s/" % m.APP_REPO), seen.get("url"))
check("open during the check", seen.get("open_during") is True)
check("closed after", not m.network_is_open())
check("newest tag read", r[0] in ("v99.0.0", "99.0.0"), r[0])
check("release page is this project's", str(r[1]).startswith("https://github.com/%s/" % m.APP_REPO), r[1])
import platform
if platform.machine() == "arm64":
    check("this Mac's .dmg link (another site) dropped", r[2] == "", r[2])
else:
    check("this Mac's .dmg chosen", r[2].endswith("/leetsay-mac-intel.dmg"), r[2])
check("no link to another site", "evil.example" not in json.dumps(r, default=str))
check("minimum safe version read", m._app_update_work.get("minimum") in ("0.0.30", (0, 0, 30)),
      m._app_update_work.get("minimum"))
check("versions compare", m.version_tuple("v99.0.0") > m.version_tuple(m.VERSION))
say("odd version text ->", m.version_tuple("x"))
check("api.github.com allowed", m._host_allowed("api.github.com"))
check("a look-alike is not", not m._host_allowed("api.github.com.evil.example"))
finish()
