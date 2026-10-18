#!/data/data/com.termux/files/usr/bin/bash
# Runs index.html's own detector and namer against synthetic LED scenes.
# Needs:  pkg install quickjs-ng python-numpy
set -e
cd "$(dirname "$0")/.."
D="${TMPDIR:-/tmp}/dalton-scenes"
python3 tools/scenes.py "$D" >/dev/null
python3 - "$D" "$@" <<'PY'
import json, subprocess, sys
D = sys.argv[1]
tiers = sys.argv[2:] or ['strict', 'normal', 'loose']
meta = json.load(open(f'{D}/truth.json'))
W, H, truth, titles = meta['w'], meta['h'], meta['truth'], meta['titles']

def run(scene, tier, simple):
    cmd = ['qjs', '--std', 'tools/detect_test.js', f'{D}/{scene}.rgba', str(W), str(H), tier]
    if simple: cmd.append('simple')
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode: sys.exit(f'{scene}/{tier}: {r.stderr.strip()}')
    return json.loads(r.stdout)

# What the app may say for a planted hue, in the user's own vocabulary. Two bands are
# genuinely ambiguous to the eye as well as to the camera, and anything reasonable is
# accepted there; everywhere else the answer must be exact. Deliberately NOT read from
# the app's own band table, or the test would only be checking itself.
def want(h):
    if h is None: return None
    h %= 360
    if h >= 345 or h < 12:  return {'RED'}
    if h < 25:              return {'RED', 'YELLOW', 'RED OR YELLOW'}
    if h < 80:              return {'YELLOW'}
    if h < 95:              return {'YELLOW', 'GREEN', 'YELLOW OR GREEN'}
    if h < 160:             return {'GREEN'}
    return {'OTHER'}

bad = 0
print('%-34s %s' % ('', '   '.join('%-14s' % t for t in tiers)))
for scene in truth:
    tr = truth[scene]
    cells = []
    for tier in tiers:
        o = run(scene, tier, True)
        hit = named = hedge = 0
        for t in tr:
            tx, ty = t[0], t[1]
            w = want(t[2] if len(t) > 2 else None)
            m = [b for b in o['leds'] if abs(b['cx']-tx) < 24 and abs(b['cy']-ty) < 24]
            if not m: continue
            hit += 1
            lab = m[0]['label']
            if w is None or (lab in w and ' OR ' not in lab): named += 1
            # A hedge inside an ambiguous band is the intended answer, not a miss.
            # Counted apart so it stays visible if it starts spreading.
            elif lab in w: hedge += 1
        extra = len(o['leds']) - hit
        miss = len(tr) - hit
        wrong = hit - named - hedge
        bad += miss + wrong
        cells.append('%d/%-2d %s%s+%-2d' % (named, len(tr), '!' if wrong else ' ',
                     ('~%d' % hedge) if hedge else '  ', extra))
    print('%-34s %s' % (titles[scene][:33], '   '.join('%-14s' % c for c in cells)))
print('\nnamed-right / planted,  ~n = hedged on a boundary (correct),  ! = misnamed,  +n = extra')
print('OK' if bad == 0 else '%d LEDs missed or misnamed' % bad)

# where the names actually change
o = run('sweep', 'normal', True)
rows = []
for t in sorted(truth['sweep'], key=lambda t: t[2]):
    m = [b for b in o['leds'] if abs(b['cx']-t[0]) < 24 and abs(b['cy']-t[1]) < 24]
    rows.append((t[2], m[0]['label'] if m else 'NOT FOUND',
                 m[0]['hue'] if m and m['hue'] is not None else None) if False else
                (t[2], m[0]['label'] if m else 'NOT FOUND', m[0]['hue'] if m else None))
print('\nhue sweep, simplified mode (planted -> measured -> name)')
prev = None
for h, lab, mh in rows:
    mark = '  <-- changes here' if prev is not None and lab != prev else ''
    print('  %3d deg  ->  %-6s  ->  %-16s%s' % (h, ('%.0f' % mh) if mh is not None else '--', lab, mark))
    prev = lab
PY
