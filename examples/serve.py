#!/usr/bin/env python3
"""Open the BugForge examples gallery in your browser.

The examples are plain files, but the 3D ones load three.js as a module, which a browser refuses
from a double-clicked file. This starts a small server on your own machine only (127.0.0.1), serves
this folder and opens the gallery. Nothing is sent anywhere. Stop it with Ctrl+C.

Usage:
    python3 examples/serve.py               serve on http://127.0.0.1:8765 and open the browser
    python3 examples/serve.py --port 9000   another port
    python3 examples/serve.py --no-open     do not open the browser

Exit codes:
    0  stopped with Ctrl+C
    2  the port is in use, or not a port
"""

import argparse
import functools
import http.server
import os
import sys
import threading
import webbrowser

HERE = os.path.dirname(os.path.abspath(__file__))


class Quiet(http.server.SimpleHTTPRequestHandler):
    """Serves the examples folder; says nothing per request; never caches, so an edit shows at once."""

    def log_message(self, *args):
        pass

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main(argv=None):
    """Serve the examples until Ctrl+C. Returns the exit code: 0 or 2 (see the top)."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8765, help="the port to serve on (default: 8765)")
    parser.add_argument("--no-open", action="store_true", help="do not open the browser")
    args = parser.parse_args(argv)
    if not 1 <= args.port <= 65535:
        print("error: %d is not a port (1 to 65535)" % args.port, file=sys.stderr)
        return 2
    handler = functools.partial(Quiet, directory=HERE)
    try:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    except OSError as error:
        print("error: cannot serve on port %d (%s). Try: --port %d" % (args.port, error.strerror or error, args.port + 1),
              file=sys.stderr)
        return 2
    address = "http://127.0.0.1:%d/" % args.port
    print("The gallery is at %s  (Ctrl+C stops it)" % address)
    if not args.no_open:
        threading.Timer(0.4, webbrowser.open, [address]).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
