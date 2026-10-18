#!/data/data/com.termux/files/usr/bin/env python3
"""Turn a saved RGBA frame into a PNG, using only the standard library.

    python3 tools/rawpng.py frames/0001          -> frames/0001.png
    python3 tools/rawpng.py frames/0001 --marks  -> also ring what the app found
"""
import json, struct, sys, zlib


def chunk(tag, data):
    return (struct.pack('>I', len(data)) + tag + data
            + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))


def write_png(path, w, h, rgba):
    rows = bytearray()
    stride = w * 4
    for y in range(h):                      # filter type 0 in front of every row
        rows.append(0)
        rows += rgba[y * stride:(y + 1) * stride]
    hdr = struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0)
    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n'
                + chunk(b'IHDR', hdr)
                + chunk(b'IDAT', zlib.compress(bytes(rows), 6))
                + chunk(b'IEND', b''))


def ring(rgba, w, h, cx, cy, r, rgb):
    import math
    for i in range(int(2 * math.pi * r) + 8):
        a = i / max(1.0, r)
        for d in (-1, 0, 1):
            x, y = int(cx + (r + d) * math.cos(a)), int(cy + (r + d) * math.sin(a))
            if 0 <= x < w and 0 <= y < h:
                p = (y * w + x) * 4
                rgba[p:p + 3] = bytes(rgb)


if __name__ == '__main__':
    stem = sys.argv[1].rsplit('.', 1)[0]
    meta = json.load(open(stem + '.json'))
    w, h = meta['w'], meta['h']
    rgba = bytearray(open(stem + '.rgba', 'rb').read())
    if len(rgba) != w * h * 4:
        sys.exit('size mismatch: %d bytes, expected %d' % (len(rgba), w * h * 4))
    if '--marks' in sys.argv:
        for L in meta.get('leds', []):
            ring(rgba, w, h, L['cx'], L['cy'], max(14, L['pad'] + 10), (255, 255, 255))
    write_png(stem + '.png', w, h, rgba)
    print('%s.png  %dx%d' % (stem, w, h))
