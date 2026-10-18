"""Synthetic LED scenes, with ground truth, for tools/check.sh.

Rebuilt against measurements from a real capture (see corpus/), because the first
version modelled LEDs that do not exist. Three things it had wrong:

  * Real indicator LEDs CLIP. A camera auto-exposing for a room puts any LED bright
    enough to read as "on" at the top of its range. The old scenes had dim LEDs
    peaking at 70-150, which sent the detector chasing local contrast and straight
    into the wood grain.
  * They are SMALL. Seven LEDs on a router eight feet away were 8-11 pixels each in
    a 720x1280 frame, not the 50-pixel discs modelled before.
  * The hard negatives are specular highlights and texture, not plain noise. A
    highlight clips too — but white, because it reflects the illuminant, where an
    LED clips coloured because it emits its own narrow band.

The detector and the naming both live in index.html and are tested by running the
real JavaScript under quickjs. Nothing here duplicates them, so nothing can drift.
"""
import numpy as np, os, json, sys, colorsys

def hue_rgb(h, s=1.0):
    return colorsys.hsv_to_rgb((h % 360) / 360.0, s, 1.0)

def spot(img, cx, cy, sigma, rgb, gain):
    """Emissive point source: gaussian, clipped by the caller at 255."""
    H, W = img.shape[:2]
    y0, y1 = max(0, cy - 5*sigma), min(H, cy + 5*sigma)
    x0, x1 = max(0, cx - 5*sigma), min(W, cx + 5*sigma)
    if y1 <= y0 or x1 <= x0: return
    y, x = np.ogrid[y0:y1, x0:x1]
    g = np.exp(-(((x-cx)**2 + (y-cy)**2) / (2.0*sigma*sigma))) * gain
    for c in range(3):
        img[y0:y1, x0:x1, c] += g * rgb[c]

def led(img, cx, cy, hue, sigma=3, gain=1400):
    """An indicator LED: small, and bright enough that its core clips."""
    spot(img, cx, cy, sigma, hue_rgb(hue), gain)

def highlight(img, cx, cy, sigma=3, gain=1200):
    """A specular highlight. Clips exactly like an LED, but white — it reflects the
       room's illuminant rather than emitting. The single most important negative."""
    spot(img, cx, cy, sigma, (1.0, 0.97, 0.93), gain)

def woodgrain(img, y0, y1, x0, x1, seed=1):
    """Warm, textured, locally contrasty, and NOT saturated — what 24 labels landed on."""
    r = np.random.default_rng(seed)
    h, w = y1-y0, x1-x0
    base = r.normal(0, 1, (h//8+2, w//8+2))
    base = np.repeat(np.repeat(base, 8, 0), 8, 1)[:h, :w]
    streak = np.sin(np.linspace(0, 40, w))[None, :] * 14 + base*26
    img[y0:y1, x0:x1, 0] += 108 + streak
    img[y0:y1, x0:x1, 1] += 84  + streak*0.8
    img[y0:y1, x0:x1, 2] += 62  + streak*0.6

def _f(W, H, bg=16, seed=0):
    return np.full((H, W, 3), float(bg)) + np.random.default_rng(seed).normal(0, 2.0, (H, W, 3))

# ---------------- scenes ----------------
def router(W, H):
    """The shape of the real capture: a column of LEDs on a dark body, wood behind,
       a textured warm background, and grey printed icons between the LEDs."""
    img = _f(W, H, 14, 7)
    woodgrain(img, 0, int(H*0.45), int(W*0.4), W)
    img[int(H*0.35):int(H*0.70), int(W*0.42):int(W*0.60)] = 18      # black router body
    cx = int(W*0.51); y0 = int(H*0.40); step = int(H*0.035)
    truth = []
    for i, h in enumerate([155, 155, 35, 155, 4, 155, 155]):
        y = y0 + i*step
        led(img, cx, y, h)
        img[y+step//2-3:y+step//2+3, cx-4:cx+5] += 120               # grey printed icon
        truth.append((cx, y, h))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def highlights(W, H):
    """LEDs among specular highlights that clip just as hard. Saturation is the only
       thing that tells them apart."""
    img = _f(W, H, 30, 9)
    woodgrain(img, 0, H, 0, W, seed=4)
    truth = []
    for i, h in enumerate([4, 35, 120, 155]):
        x = int(W*0.25); y = int(H*0.2) + i*int(H*0.15)
        led(img, x, y, h); truth.append((x, y, h))
    for i in range(6):
        highlight(img, int(W*0.65) + (i % 2)*60, int(H*0.15) + i*int(H*0.12))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def wall(W, H):
    """Two LEDs on a brightly lit wall — the case that once found nothing."""
    img = np.full((H, W, 3), 200.0) + np.random.default_rng(3).normal(0, 2.0, (H, W, 3))
    truth = []
    for x, h in ((int(W*0.35), 4), (int(W*0.65), 120)):
        led(img, x, H//2, h); truth.append((x, H//2, h))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def single(W, H):
    img = _f(W, H, 16, 5)
    led(img, W//2, H//2, 35, sigma=4)
    return np.clip(img, 0, 255).astype(np.uint8), [(W//2, H//2, 35)]

def closeup(W, H):
    """Phone held right against one LED, two smaller ones either side."""
    img = _f(W, H, 20, 11)
    truth = []
    for x, h, sg in ((W//2, 120, 22), (int(W*0.2), 4, 5), (int(W*0.8), 35, 5)):
        led(img, x, H//2, h, sigma=sg); truth.append((x, H//2, h))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def nothing(W, H):
    """A plain room with wood and a highlight. Anything found here is a false alarm."""
    img = _f(W, H, 40, 13)
    woodgrain(img, 0, int(H*0.6), 0, W, seed=6)
    highlight(img, int(W*0.7), int(H*0.75), sigma=5)
    return np.clip(img, 0, 255).astype(np.uint8), []

def window_scene(W, H):
    """LEDs beside a blown-out window: a hard 200-level step edge."""
    img = _f(W, H, 22, 17)
    img[int(H*0.1):int(H*0.8), int(W*0.6):] = 252.0
    truth = []
    for i, h in enumerate([155, 35, 4, 155]):
        x, y = int(W*0.3), int(H*0.2) + i*int(H*0.1)
        led(img, x, y, h); truth.append((x, y, h))
    x, y = int(W*0.55), int(H*0.5)
    led(img, x, y, 155); truth.append((x, y, 155))        # 5% from the window edge
    return np.clip(img, 0, 255).astype(np.uint8), truth

def sweep(W, H):
    """One LED per hue, 0 to 115 degrees in 5 degree steps — 24, the per-scan cap.
       Answers directly where RED becomes YELLOW and YELLOW becomes GREEN."""
    img = _f(W, H, 16, 23)
    truth = []
    hs = list(range(0, 120, 5))
    for i, h in enumerate(hs):
        x = int(W*0.1) + (i % 4) * int(W*0.26)
        y = int(H*0.08) + (i // 4) * int(H*0.15)
        led(img, x, y, h); truth.append((x, y, h))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def dim(W, H):
    """KNOWN LIMIT, not a pass/fail: an LED too dim to clip. The detector is built on
       the fact that indicator LEDs reach the top of the sensor's range; one that does
       not is indistinguishable from a reflective highlight in a single exposure."""
    img = _f(W, H, 16, 29)
    led(img, W//2, H//2, 120, sigma=4, gain=110)
    return np.clip(img, 0, 255).astype(np.uint8), [(W//2, H//2, 120)]

SCENES = {'router': router, 'highlights': highlights, 'wall': wall, 'single': single,
          'closeup': closeup, 'empty': nothing, 'window': window_scene,
          'sweep': sweep, 'dim': dim}
TITLES = {
    'router':     'router column, wood + printed icons',
    'highlights': 'LEDs among white specular highlights',
    'wall':       '2 LEDs on a brightly lit wall',
    'single':     'one LED, dark room',
    'closeup':    'close-up: 1 huge LED + 2 small',
    'empty':      'empty room, wood + a highlight',
    'window':     '5 LEDs beside a blown-out window',
    'sweep':      'hue sweep, 0-115 deg in 5 deg steps',
    'dim':        'KNOWN LIMIT: an LED too dim to clip',
}
EXPECT_FAIL = {'dim'}          # documented, not a regression

if __name__ == '__main__':
    d = sys.argv[1]; W, H = 720, 1280          # portrait, like the real captures
    os.makedirs(d, exist_ok=True)
    truth = {}
    for name, mk in SCENES.items():
        img, tr = mk(W, H)
        np.dstack([img, np.full((H, W), 255, np.uint8)]).tofile(f'{d}/{name}.rgba')
        truth[name] = tr
    json.dump({'w': W, 'h': H, 'truth': truth, 'titles': TITLES,
               'expect_fail': sorted(EXPECT_FAIL)}, open(f'{d}/truth.json', 'w'))
    print(f'{len(SCENES)} scenes -> {d}')
