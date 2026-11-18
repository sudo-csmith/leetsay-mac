"""Download certificates are checked by macOS's own certificate check
(truststore), never switched off: a server with a certificate this Mac
doesn't trust is refused with "certificate verify failed". When that is why
the download failed, the download card says a security check blocked it,
and a click shows help that points to Manual download. Offline: a local
stand-in server over a socket pair; nothing goes online."""
import os, sys, socket, ssl, subprocess, tempfile, threading
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import *

m = load_app()
app = qt_app(None)
ctx = m.mac_ssl_context()
check("macOS's own certificate check is used", type(ctx).__module__.startswith("truststore"),
      type(ctx))
check("certificates are checked", ctx.verify_mode == ssl.CERT_REQUIRED and ctx.check_hostname)

tmp = tempfile.mkdtemp()
key, crt = os.path.join(tmp, "k.pem"), os.path.join(tmp, "c.pem")
made = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-days", "1",
                       "-subj", "/CN=github.com", "-keyout", key, "-out", crt],
                      capture_output=True).returncode == 0
must("a stand-in certificate was made", made)
server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
server_ctx.load_cert_chain(crt, key)
a, b = socket.socketpair()


def serve():
    try:
        server_ctx.wrap_socket(a, server_side=True).recv(1)
    except Exception:
        pass


threading.Thread(target=serve, daemon=True).start()
error = ""
try:
    ctx.wrap_socket(b, server_hostname="github.com")
except Exception as e:
    error = str(e)
check("an untrusted certificate is refused", "certificate verify failed" in error.lower()
      or "not trusted" in error.lower(), error[:120])

# The card and the help for this case.
m.mic_permission = lambda: m.MIC_OK
shown = []
m.dialog = lambda title, text, buttons=("OK",), **kw: (shown.append((kw.get("headline"), text)),
                                                       None)[1]
d = m.Dictation(app)
d.downloading = True
d._on_model_ready(False, "<urlopen error [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify "
                         "failed: unable to get local issuer certificate>")
check("the certificate problem is noticed", d.download_cert)
d.download_blocked = True
check("the card says a security check blocked it", d.download_words() == d.BLOCKED_CERT,
      d.download_words())
d.download_clicked()
check("a click shows the security-check help",
      shown and shown[-1][0] == "A security check blocked the download", shown and shown[-1][0])
check("... pointing to Manual download", shown and "Manual download" in shown[-1][1])
d3 = m.Dictation(app)
d3.downloading = True
d3._on_model_ready(False, "<urlopen error " + error + ">")      # macOS's own wording
check("macOS's wording is noticed too", d3.download_cert, error[:60])
d2 = m.Dictation(app)
d2.downloading = True
d2._on_model_ready(False, "timed out")
d2.download_blocked = True
check("other failures keep the usual words", d2.download_words() == d2.BLOCKED)
finish()
