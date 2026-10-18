#!/data/data/com.termux/files/usr/bin/env python3
"""Read a camera-probe capture and say which exposure levers this phone really has.

    python3 tools/probe.py frames/0012

A lever counts as working only if the pixels moved. Two levers on this phone have
already passed every check that asked the camera what it did, and failed the only
check that mattered - exposureTime reported exactly what was requested and returned
solid black, and the ISO floor was applied silently as a side effect. So nothing here
trusts getSettings(); every verdict is read off the frames.

If the probe caught a torch-on/torch-off pair, it also runs the emitter test, which
is the whole reason the pair is worth taking:

    an LED emits the same with the torch on or off;  a lit object does not.

The camera re-exposes between the two shots by some unknown factor k, so absolute
values cannot be compared. Directions can: with the torch on, an emitter goes DIMMER
(E/k) while a reflector goes BRIGHTER ((A+T)/k). Ranking blobs by that ratio
separates them without ever needing to know k.
"""
import json, subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load(stem):
    meta = json.load(open(stem + '.json'))
    if meta.get('kind') != 'camera-probe':
        sys.exit('%s is not a camera probe (kind=%r)' % (stem, meta.get('kind')))
    return meta


def planes(meta, stem):
    out = []
    for i, name in enumerate(meta.get('planes', [])):
        p = os.path.join(ROOT, 'frames', name + '.rgba')
        out.append(p if os.path.exists(p) else None)
    return out


def caps_table(meta):
    c = meta.get('caps') or {}
    print('WHAT THE CAMERA CLAIMS')
    for k in ('torch', 'exposureMode', 'exposureTime', 'iso',
              'exposureCompensation', 'whiteBalanceMode', 'focusMode'):
        if k in c:
            print('  %-22s %s' % (k, json.dumps(c[k])))
    missing = [k for k in ('torch', 'iso', 'exposureTime') if k not in c]
    if missing:
        print('  NOT OFFERED AT ALL: ' + ', '.join(missing))
    return c


def steps_table(meta):
    base = None
    print('\nWHAT THE SENSOR DID         applied  median   mean  clip%%   vs auto')
    for s in meta['steps']:
        st = s.get('stats')
        if st is None:
            print('  %-24s  no       —        —      —      (%s)'
                  % (s['name'], s.get('err') or 'skipped'))
            continue
        if base is None:
            base = st['mean']
        rel = (st['mean'] / base) if base else 0
        verdict = ''
        if s['name'] != 'auto':
            verdict = ('BLACK' if st['med'] <= 2 else
                       'no change' if 0.9 < rel < 1.1 else
                       '%.2fx' % rel)
        print('  %-24s  %-7s %-7d %-6.1f %-6.2f %s'
              % (s['name'], 'yes' if s['applied'] else 'NO',
                 st['med'], st['mean'], st['clip'] * 100, verdict))
        if not s['applied']:
            print('        error: %s' % s.get('err'))
    return base


def emitter_test(meta, stem, tier='normal'):
    """Compare every blob between the torch-off and torch-on frames."""
    names = meta.get('planes', [])
    idx = {s['name']: i for i, s in enumerate(meta['steps'])}
    if 'torch-on' not in idx or idx['torch-on'] >= len(names):
        print('\nEMITTER TEST: skipped, no torch-on frame in this probe.')
        return
    import numpy as np
    W, H = meta['w'], meta['h']

    def frame(i):
        p = os.path.join(ROOT, 'frames', names[i] + '.rgba')
        return np.fromfile(p, dtype=np.uint8).reshape(H, W, 4)[:, :, :3].astype(float)

    off = frame(idx.get('auto', 0))
    on = frame(idx['torch-on'])

    # Blobs come from the REAL detector, on the torch-off frame.
    r = subprocess.run(['qjs', '--std', os.path.join(HERE, 'detect_test.js'),
                        os.path.join(ROOT, 'frames', names[idx.get('auto', 0)] + '.rgba'),
                        str(W), str(H), tier, 'simple'],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        print('\nEMITTER TEST: detector failed: %s' % r.stderr.strip()[:300])
        return
    leds = json.loads(r.stdout)['leds']
    if not leds:
        print('\nEMITTER TEST: nothing detected in the torch-off frame.')
        return

    def patch(img, cy, cx, r=4):
        return img[max(0, cy - r):cy + r + 1, max(0, cx - r):cx + r + 1].max(2)

    rows = []
    for b in leds:
        a = patch(off, b['cy'], b['cx']).mean()
        c = patch(on, b['cy'], b['cx']).mean()
        rows.append((c / max(a, 1e-6), a, c, b))
    rows.sort(key=lambda t: t[0])

    print('\nEMITTER TEST  (torch off -> on; low ratio = emitter, high = reflector)')
    print('  ratio   off    on     where            named')
    for ratio, a, c, b in rows:
        print('  %-7.2f %-6.0f %-6.0f (%4d,%4d)      %s'
              % (ratio, a, c, b['cy'], b['cx'], b['label']))
    lo, hi = rows[0][0], rows[-1][0]
    print('\n  spread %.2f to %.2f (%.1fx).' % (lo, hi, hi / max(lo, 1e-6)), end=' ')
    print('A clean split means the emitter test works here.' if hi / max(lo, 1e-6) > 2
          else 'No clean split - the torch may be too weak, or everything in frame '
               'is the same kind of thing.')


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    stem = sys.argv[1].rstrip('/')
    if stem.endswith('.json'):
        stem = stem[:-5]
    meta = load(stem)
    caps_table(meta)
    steps_table(meta)
    try:
        emitter_test(meta, stem)
    except ImportError:
        print('\nEMITTER TEST: needs numpy (pkg install python-numpy)')


if __name__ == '__main__':
    main()
