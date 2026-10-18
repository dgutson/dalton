#!/data/data/com.termux/files/usr/bin/bash
# Runs index.html's own detector and namer against the real-capture corpus and a set
# of synthetic scenes.  Needs:  pkg install quickjs-ng python-numpy
set -e
cd "$(dirname "$0")/.."
D="${TMPDIR:-/tmp}/dalton-scenes"
python3 tools/scenes.py "$D" >/dev/null
python3 - "$D" "$@" <<'PY'
import json, subprocess, sys, os, tempfile
sys.path.insert(0, 'tools')
import corpus

D = sys.argv[1]
tiers = sys.argv[2:] or ['strict', 'normal', 'loose']

def run(path, w, h, tier):
    r = subprocess.run(['qjs', '--std', 'tools/detect_test.js', path, str(w), str(h),
                        tier, 'simple'], capture_output=True, text=True)
    if r.returncode: sys.exit(f'{path} {tier}: {r.stderr.strip()[:500]}')
    return json.loads(r.stdout)

# What the app may say for a planted hue. Two bands are genuinely ambiguous to the eye
# as well as the camera and accept anything reasonable; elsewhere it must be exact.
# Deliberately NOT read from the app's band table, or the test only checks itself.
def want(h):
    if h is None: return None
    h %= 360
    if h >= 345 or h < 12:  return {'RED'}
    if h < 25:              return {'RED', 'YELLOW', 'RED OR YELLOW'}
    if h < 80:              return {'YELLOW'}
    if h < 95:              return {'YELLOW', 'GREEN', 'YELLOW OR GREEN'}
    if h < 200:             return {'GREEN'}
    return {'OTHER'}

def judge(o, leds, tol=20):
    hit = named = hedge = 0
    for t in leds:
        x, y, w = t['x'], t['y'], t['expect']
        m = [b for b in o['leds'] if abs(b['cx']-x) < tol and abs(b['cy']-y) < tol]
        if not m: continue
        hit += 1
        lab = m[0]['label']
        if w is None or (lab in w and ' OR ' not in lab): named += 1
        elif lab in w: hedge += 1
    return named, hedge, hit, len(o['leds']) - hit

def cell(named, hedge, hit, extra, total, soft):
    wrong = hit - named - hedge
    bad = (total - hit) + wrong
    flag = ' ' if soft or not bad else '!'
    return '%d/%-2d %s%s+%-2d' % (named, total, flag, ('~%d' % hedge) if hedge else '  ', extra), (0 if soft else bad)

fails = 0
print('REAL CAPTURES (corpus/)      %s' % '   '.join('%-14s' % t for t in tiers))
ents = corpus.entries()
if not ents: print('  (none yet — python3 tools/corpus.py add frames/NNNN <slug>)')
for slug in ents:
    raw, t = corpus.load(slug)
    if not t.get('verified'):
        print('  %-26s SKIPPED, truth not verified by eye' % slug[:26]); continue
    with tempfile.NamedTemporaryFile(suffix='.rgba', delete=False) as f:
        f.write(raw); path = f.name
    try:
        cells = []
        for tier in tiers:
            o = run(path, t['w'], t['h'], tier)
            c, bad = cell(*judge(o, t['leds']), len(t['leds']), False)
            fails += bad; cells.append(c)
    finally: os.unlink(path)
    print('  %-26s %s' % (slug[:26], '   '.join('%-14s' % c for c in cells)))

meta = json.load(open(f'{D}/truth.json'))
W, H, titles, soft = meta['w'], meta['h'], meta['titles'], set(meta['expect_fail'])
print('\nSYNTHETIC SCENES')
for scene, tr in meta['truth'].items():
    leds = [{'x': x, 'y': y, 'expect': want(h)} for x, y, h in tr]
    cells = []
    for tier in tiers:
        o = run(f'{D}/{scene}.rgba', W, H, tier)
        c, bad = cell(*judge(o, leds), len(leds), scene in soft)
        fails += bad; cells.append(c)
    note = '  (known limit)' if scene in soft else ''
    print('  %-26s %s%s' % (titles[scene][:26], '   '.join('%-14s' % c for c in cells), note))

print('\nnamed-right / planted,  ~n = hedged on a boundary (correct),  ! = wrong, +n = extra')
print('OK' if not fails else '%d LEDs missed or misnamed' % fails)
sys.exit(1 if fails else 0)
PY
