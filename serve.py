#!/data/data/com.termux/files/usr/bin/env python3
"""Dalton's server. Loopback only.

Serves the app, and accepts POST /frame so the page can hand a captured frame
back to the machine for offline analysis. That is the whole reason this exists
instead of `python3 -m http.server`: without it there is no way to test the
algorithm against anything but synthetic images.

Body format: one line of JSON metadata, '\\n', then raw RGBA bytes.
Writes frames/NNNN.json and frames/NNNN.rgba next to this file.
"""
import json, os, sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
FRAMES = os.path.join(HERE, 'frames')
MAX_BODY = 48 * 1024 * 1024          # a 1280x720 RGBA frame is 3.7 MB


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=HERE, **kw)

    def do_POST(self):
        if self.path.split('?')[0] != '/frame':
            self.send_error(404); return
        try:
            n = int(self.headers.get('Content-Length', 0))
        except ValueError:
            self.send_error(400, 'bad length'); return
        if n <= 0 or n > MAX_BODY:
            self.send_error(413, 'body %d bytes' % n); return

        body = b''
        while len(body) < n:                      # read() can come up short
            chunk = self.rfile.read(n - len(body))
            if not chunk: break
            body += chunk

        cut = body.find(b'\n')                    # JSON never contains a raw newline
        if cut < 0:
            self.send_error(400, 'no metadata line'); return
        try:
            meta = json.loads(body[:cut].decode('utf-8'))
        except Exception as e:
            self.send_error(400, 'bad metadata: %s' % e); return
        raw = body[cut + 1:]

        os.makedirs(FRAMES, exist_ok=True)
        seq = 1 + max([int(f[:4]) for f in os.listdir(FRAMES)
                       if f[:4].isdigit()] or [0])
        stem = os.path.join(FRAMES, '%04d' % seq)
        meta['bytes'] = len(raw)
        meta['stem'] = '%04d' % seq
        with open(stem + '.rgba', 'wb') as f:
            f.write(raw)
        with open(stem + '.json', 'w') as f:
            json.dump(meta, f, indent=1)

        w, h = meta.get('w', 0), meta.get('h', 0)
        ok = (w * h * 4 == len(raw))
        print('saved %s.rgba  %dx%d  %.1f MB  %d led(s)%s'
              % (stem, w, h, len(raw) / 1e6, len(meta.get('leds', [])),
                 '' if ok else '  <-- SIZE MISMATCH'), flush=True)

        out = json.dumps({'ok': ok, 'saved': meta['stem']}).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store')   # always serve the newest edit
        super().end_headers()

    def log_message(self, fmt, *args):
        if self.command != 'GET':
            sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    srv = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print('Dalton on http://localhost:%d  (loopback only)' % port, flush=True)
    print('frames -> %s' % FRAMES, flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
