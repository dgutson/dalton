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
    """Which blobs kept their light when the exposure was cut?

    Planes exist only for steps that APPLIED, so they are indexed by meta['evs'] and
    never by position in meta['steps'] - a step that failed leaves no frame behind and
    shifts everything after it. Getting that wrong once compared the auto frame against
    itself and reported a clean 1.0 for every blob, which looks exactly like a working
    test returning a boring answer.
    """
    names = meta.get('planes', [])
    evs = meta.get('evs') or [s['name'] for s in meta['steps'] if s.get('applied')]
    idx = {name: i for i, name in enumerate(evs) if i < len(names)}
    stats = {s['name']: s.get('stats') for s in meta['steps']}
    if 'auto' not in idx:
        print('\nEMITTER TEST: skipped, no auto frame.')
        return

    if 'torch-on' in idx:
        other, kind = 'torch-on', 'torch'
    else:
        # No torch on this phone. Cutting the exposure is the lever that is left, and
        # it tests the same thing from the other side. Both an emitter and a reflector
        # scale linearly with exposure, so on its own a cut separates nothing - EXCEPT
        # that a clipped pixel is lying about how bright it was. An LED pinned at 255
        # may really be worth thousands; the room at 129 is worth 129. Cut the light to
        # an eighth and the room collapses while the LED is merely no longer clipped.
        # So the ratio measures hidden headroom, which is what "is it emitting" means.
        # The darkest frame that still HOLDS something, and that is actually darker
        # than auto. Two traps here, both hit for real. A frame with a median of 2
        # is black, not dark, and comparing against it measures nothing. And a step
        # that did not move the picture - ISO on this phone - is not a second
        # exposure at all; falling back to one silently reported LEDs as reflectors.
        base = stats['auto']['mean']
        dark = [(st['mean'], n) for n, st in stats.items()
                if st and n in idx and n != 'auto' and st['med'] > 8
                and st['mean'] < base * 0.8]
        if not dark:
            black = [n for n, st in stats.items()
                     if st and n != 'auto' and st['med'] <= 8]
            inert = [n for n, st in stats.items()
                     if st and n != 'auto' and st['med'] > 8
                     and st['mean'] >= base * 0.8]
            print('\nEMITTER TEST: no usable second exposure.')
            if black: print('  came back BLACK (median <= 8): ' + ', '.join(black))
            if inert: print('  did not move the picture:       ' + ', '.join(inert))
            print('  The cut has to land between those two. On this camera that means\n'
                  '  exposureCompensation in CONTINUOUS mode; manual exposureTime goes\n'
                  '  straight to black and ISO does nothing.')
            return
        other, kind = min(dark)[1], 'exposure'
    import numpy as np
    W, H = meta['w'], meta['h']

    def frame(name):
        p = os.path.join(ROOT, 'frames', names[idx[name]] + '.rgba')
        return np.fromfile(p, dtype=np.uint8).reshape(H, W, 4)[:, :, :3].astype(float)

    a_img, b_img = frame('auto'), frame(other)

    # REGISTER FIRST. The probe is handheld and each step costs about half a second,
    # so the frames drift. Measured on frames/0014: 10px across and 6px down between
    # two consecutive grabs, which is more than an LED is wide - every LED fell out
    # of its 9x9 patch and read as having gone dark, which looks exactly like a
    # reflector. Comparing unregistered frames does not measure exposure, it measures
    # the user's hands.
    dy, dx, before = register(a_img, b_img)
    if dy or dx:
        b_img = np.roll(np.roll(b_img, -dy, axis=0), -dx, axis=1)
    print('\n  registration: %+d px down, %+d px across  '
          '(correlation %.3f, was %.3f unshifted)' % (dy, dx, before[1], before[0]))
    if before[1] < 0.5:
        print('  WEAK MATCH - the two frames may not show the same thing. Treat the '
              'rest\n  of this table as unreliable.')
    scene = (stats[other]['mean'] / stats['auto']['mean']) if stats['auto']['mean'] else 1

    r = subprocess.run(['qjs', '--std', os.path.join(HERE, 'detect_test.js'),
                        os.path.join(ROOT, 'frames', names[idx['auto']] + '.rgba'),
                        str(W), str(H), tier, 'simple'],
                       capture_output=True, text=True, cwd=ROOT)
    if r.returncode:
        print('\nEMITTER TEST: detector failed: %s' % r.stderr.strip()[:300])
        return
    leds = json.loads(r.stdout)['leds']
    if not leds:
        print('\nEMITTER TEST: nothing detected in the auto frame.')
        return

    def patch(img, cy, cx, rad=4):
        return img[max(0, cy-rad):cy+rad+1, max(0, cx-rad):cx+rad+1].max(2)

    rows = []
    for b in leds:
        p0, p1 = patch(a_img, b['cy'], b['cx']), patch(b_img, b['cy'], b['cx'])
        rows.append((p1.mean() / max(p0.mean(), 1e-6), p0.mean(), p1.mean(),
                     (p0 >= 250).mean(), b))
    rows.sort(key=lambda t: -t[0])

    if kind == 'torch':
        print('\nEMITTER TEST  auto -> torch-on   (low = emitter, high = reflector)')
    else:
        print('\nEMITTER TEST  auto -> %s   the whole scene kept %.3f of its light.'
              % (other, scene))
        print('  A blob that kept much MORE than that was clipped, i.e. far brighter '
              'than it\n  could say - which is what an emitter looks like.')
    print('\n  kept   x scene  auto   dark   clip%%  where          named')
    for ratio, p0, p1, cl, b in rows:
        print('  %-6.3f %-8.2f %-6.0f %-6.0f %-6.0f (%4d,%4d)    %s'
              % (ratio, ratio / max(scene, 1e-6), p0, p1, cl * 100,
                 b['cx'], b['cy'], b['label']))
    hi = rows[0][0] / max(scene, 1e-6)
    lo = rows[-1][0] / max(scene, 1e-6)
    # What counts as a split. "x scene" estimates how many times over the clip point
    # the blob really was, so a reflector sits at 1 by construction and local contrast
    # alone spreads a scene of pure reflectors over about 2x. An LED that clips is
    # worth several times the clip point and lands far above that, with clip% at 100
    # in the auto frame. Anything under 3x is a scene with nothing emitting in it.
    print('\n  top blob is %.1fx the scene.' % hi, end=' ')
    print('That is an emitter; the test works here.' if hi > 3
          else 'Under 3x, with clip%% at 0 - nothing in this frame was emitting, '
               'so\n  the test is unproven rather than failed. Re-probe pointing at '
               'a router.')


def register(a, b, span=300):
    """Integer shift of b that best lines it up with a, by CORRELATION.

    Absolute difference is the obvious metric and it is useless here: the two frames
    differ by a factor of eight in brightness, so the difference is dominated by the
    exposure and barely moves with alignment. On frames/0013 it picked a 20px shift
    that improved the residual by half a percent and was simply wrong. Normalised
    correlation subtracts the mean and divides by the spread of each crop, so it
    asks only whether the same EDGES are in the same places.
    """
    import numpy as np
    H, W = a.shape[:2]
    y0, x0 = H // 2 - span // 2, W // 2 - span // 2
    A = a[y0:y0 + span, x0:x0 + span].max(2).astype(float)
    A = A - A.mean()
    na = float(np.sqrt((A * A).sum()))
    B = b.max(2).astype(float)

    def ncc(dy, dx):
        C = B[y0 + dy:y0 + dy + span, x0 + dx:x0 + dx + span]
        if C.shape != A.shape: return -1.0
        C = C - C.mean()
        d = na * float(np.sqrt((C * C).sum()))
        return float((A * C).sum()) / d if d > 0 else -1.0

    zero = ncc(0, 0)
    best = (zero, 0, 0)
    for stride, rng in ((4, 32), (1, 5)):
        cy, cx = best[1], best[2]
        for dy in range(cy - rng, cy + rng + 1, stride):
            for dx in range(cx - rng, cx + rng + 1, stride):
                c = ncc(dy, dx)
                if c > best[0]: best = (c, dy, dx)
    return best[1], best[2], (zero, best[0])


def drift_note(meta):
    """How far did the hands move over the whole probe? The error bar on everything."""
    names, evs = meta.get('planes', []), meta.get('evs') or []
    idx = {n: i for i, n in enumerate(evs) if i < len(names)}
    if 'auto' not in idx or 'auto-again' not in idx: return
    try:
        import numpy as np
    except ImportError:
        return
    W, H = meta['w'], meta['h']
    def f(n):
        p = os.path.join(ROOT, 'frames', names[idx[n]] + '.rgba')
        return np.fromfile(p, dtype=np.uint8).reshape(H, W, 4)[:, :, :3].astype(float)
    dy, dx, (z, c) = register(f('auto'), f('auto-again'))
    d = (dy * dy + dx * dx) ** 0.5
    print('\nHANDHELD DRIFT over the whole probe: %+d px down, %+d px across (%.0f px).'
          % (dy, dx, d), end=' ')
    print('An LED is a few px wide, so every pair above is registered before it is\n'
          'compared.' if d >= 3 else 'Steady enough that registration barely matters.')


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
        drift_note(meta)
    except Exception as e:
        print('\n(drift not measured: %s)' % e)
    try:
        emitter_test(meta, stem)
    except ImportError:
        print('\nEMITTER TEST: needs numpy (pkg install python-numpy)')


if __name__ == '__main__':
    main()
