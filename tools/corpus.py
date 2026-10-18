#!/usr/bin/env python3
"""The regression corpus: real captures, with hand-verified ground truth.

Synthetic scenes are a guess about what a camera does. Every real bug in this project
so far has been something the guess got wrong — LEDs that always clip, specular
highlights that clip white, a green indicator that photographs at 160 degrees. Once a
real capture is in here it is a permanent test, and that class of mistake cannot come
back silently.

    python3 tools/corpus.py add frames/0003 some-router   # stage a new capture
    python3 tools/corpus.py list                          # what is in the corpus

`add` seeds truth.json from whatever the app detected at capture time and marks it
"verified": false. That seed is a convenience, NOT ground truth — open the rendered
PNG, check every LED by eye, fix the list, then set verified to true. An unverified
entry is skipped by the tests rather than trusted.

An entry may also carry

    "known_limit": {"strict": "why this tier cannot pass on this capture"}

which stops that one tier failing the run while still printing its real score and the
reason underneath it. It is the same promise as EXPECT_FAIL in tools/scenes.py: a
documented limitation, never a way to quiet a regression.
"""
import gzip, json, os, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(ROOT, 'corpus')

def add(stem, slug):
    raw, meta = stem + '.rgba', stem + '.json'
    for f in (raw, meta):
        if not os.path.exists(f): sys.exit('missing ' + f)
    cap = json.load(open(meta))
    d = os.path.join(CORPUS, slug)
    os.makedirs(d, exist_ok=True)
    with open(raw, 'rb') as fi, gzip.open(os.path.join(d, 'frame.rgba.gz'), 'wb', 6) as fo:
        shutil.copyfileobj(fi, fo)
    shutil.copy(meta, os.path.join(d, 'capture.json'))
    tp = os.path.join(d, 'truth.json')
    if os.path.exists(tp):
        print('kept existing', tp)
    else:
        json.dump({'w': cap['w'], 'h': cap['h'], 'note': '', 'verified': False,
                   'leds': [{'y': b['cy'], 'x': b['cx'], 'expect': b['label']}
                            for b in cap['leds']]}, open(tp, 'w'), indent=2)
        print('seeded', tp, '- VERIFY IT BY EYE, then set verified: true')
    print('added', d)

def load(slug):
    """-> (rgba bytes, truth dict). Decompressed in memory, nothing written."""
    d = os.path.join(CORPUS, slug)
    truth = json.load(open(os.path.join(d, 'truth.json')))
    with gzip.open(os.path.join(d, 'frame.rgba.gz'), 'rb') as f:
        return f.read(), truth

def entries():
    if not os.path.isdir(CORPUS): return []
    return sorted(e for e in os.listdir(CORPUS)
                  if os.path.exists(os.path.join(CORPUS, e, 'truth.json')))

if __name__ == '__main__':
    if len(sys.argv) >= 2 and sys.argv[1] == 'add' and len(sys.argv) == 4:
        add(sys.argv[2], sys.argv[3])
    elif len(sys.argv) >= 2 and sys.argv[1] == 'list':
        for e in entries():
            t = json.load(open(os.path.join(CORPUS, e, 'truth.json')))
            print('%-28s %dx%d  %2d LEDs  %s  %s' % (
                e, t['w'], t['h'], len(t['leds']),
                'verified' if t.get('verified') else 'UNVERIFIED', t.get('note', '')))
    else:
        sys.exit(__doc__)
