"""Synthetic LED scenes, with ground truth, for tools/check.sh.

Rebuilt against measurements from a real capture (see corpus/), because the first
version modelled LEDs that do not exist. Four things it had wrong:

  * Real indicator LEDs CLIP. A camera auto-exposing for a room puts any LED bright
    enough to read as "on" at the top of its range. The old scenes had dim LEDs
    peaking at 70-150, which sent the detector chasing local contrast and straight
    into the wood grain.
  * They are SMALL. Seven LEDs on a router eight feet away were 3-8 pixels of clipped
    core each in a 720x1280 frame, not the 50-pixel discs modelled before. Size is
    not cosmetic: the padded box the colour is read from is derived from the blob
    radius, so an LED ten times too big samples ten times too much background.
  * They OCCLUDE. An LED is an object in the scene, not a transparency laid over the
    wall behind it. Adding its emission to a lit background instead of covering it
    is what made a red LED on a 200-level wall read at saturation 0.21.
  * The hard negatives are specular highlights and texture, not plain noise. A
    highlight clips too — but white, because it reflects the illuminant, where an
    LED clips coloured because it emits its own narrow band.

Every constant below is traceable to a number measured off corpus/0001-cbn-router:

    LEDs          peak 255, saturation 0.40-0.74 at the peak pixel and 0.70-0.88 in
                  the fringe, clipped core 3-8 px, padded box 64-81 px of which
                  44-72 are usable, 1-7 clipped, 0-4 grey
    wood          value p50 90 / p90 112 / p99 137 / max 224, nothing clipped;
                  saturation p50 0.19 / p90 0.23 / p99 0.29, and falling with
                  brightness — mean 0.20 in the darkest tenth, 0.135 in the brightest
    highlights    the six blobs that clipped white measured saturation 0.07
    printed icons peak 148-179, saturation 0.11-0.22

The detector and the naming both live in index.html and are tested by running the
real JavaScript under quickjs. Nothing here duplicates them, so nothing can drift.
"""
import numpy as np, os, json, sys, colorsys

def hue_rgb(h, s=1.0):
    return np.array(colorsys.hsv_to_rgb((h % 360) / 360.0, s, 1.0))

def spot(img, cx, cy, sigma, rgb, gain, occlude=False):
    """Gaussian point source, clipped by the caller at 255.

    occlude=False  the source adds to whatever is behind it — a specular highlight,
                   which is the illuminant bouncing off a surface that is still there.
    occlude=True   the source covers what is behind it in proportion to its profile —
                   an LED die, or a varnish glint washing the grain out to white.
    """
    H, W = img.shape[:2]
    rad = int(np.ceil(5*sigma)) + 1
    y0, y1 = max(0, cy - rad), min(H, cy + rad + 1)
    x0, x1 = max(0, cx - rad), min(W, cx + rad + 1)
    if y1 <= y0 or x1 <= x0: return
    y, x = np.ogrid[y0:y1, x0:x1]
    g = np.exp(-(((x-cx)**2 + (y-cy)**2) / (2.0*sigma*sigma)))
    if occlude: img[y0:y1, x0:x1] *= (1.0 - g)[:, :, None]
    img[y0:y1, x0:x1] += (g*gain)[:, :, None] * np.asarray(rgb, float)[None, None, :]

# Tuned so one LED on a dark body reproduces the real profile above: clipped core 9 px,
# padded box 81 px, 46 usable at mean saturation 0.71, agreement 0.999, measured hue
# within half a degree of the planted one.
LED_SIGMA, LED_GAIN, LED_BLOOM = 1.5, 500.0, 0.25

def led(img, cx, cy, hue, sigma=LED_SIGMA, gain=LED_GAIN):
    """An indicator LED: small, occluding, and bright enough that its core clips."""
    spot(img, cx, cy, sigma, hue_rgb(hue), gain, occlude=True)
    # Sensor bloom at the core. Without it the brightest pixel is as saturated as the
    # fringe; the real LEDs measured 0.40-0.74 at the peak and 0.70-0.88 two pixels
    # out, because the dominant channel caps at 255 while the others keep climbing.
    spot(img, cx, cy, sigma*0.63, (1.0, 1.0, 1.0), gain*LED_BLOOM)

def highlight(img, cx, cy, sigma=3, gain=1200):
    """A specular highlight. Clips exactly like an LED, but white — it reflects the
       room's illuminant rather than emitting. The single most important negative:
       of the thirteen blobs that clipped in the real frame, these six were told
       apart from the seven LEDs by saturation 0.07 against 0.45-0.83 and by nothing
       else at all."""
    spot(img, cx, cy, sigma, (1.0, 0.98, 0.95), gain)

def woodgrain(img, y0, y1, x0, x1, seed=1):
    """Warm varnished wood, matched to the real capture.

    The old version ADDED a flat warm offset (108/84/62) on top of the frame's
    background, which put wood at value 138 and saturation 0.34 — brighter than real
    wood, more saturated than a real LED's own fringe, and clipping at 255 wherever
    the grain peaked. Every empty-room false alarm and every misnamed LED in the
    specular-highlight scene came from that one line: the detector's whole premise is
    "clips AND clips coloured", and this painted a wall of pixels that did both.

    Two things make the real thing harmless. Its value distribution tops out around
    225, nowhere near an LED. And its saturation FALLS as it brightens — a bright wood
    pixel is the neutral illuminant glancing off the varnish, not more wood colour.
    Measured by decile on the real frame: mean saturation 0.20 in the darkest tenth,
    0.135 in the brightest, with only 2% of that brightest tenth reaching 0.20.
    """
    r = np.random.default_rng(seed)
    h, w = y1-y0, x1-x0
    def grid(cell, scale):                 # blocky low-frequency field, like grain
        n = r.normal(0, 1, (h//cell+2, w//cell+2))
        return np.repeat(np.repeat(n, cell, 0), cell, 1)[:h, :w] * scale
    v = (90 + np.sin(np.linspace(0, 40, w))[None, :]*8
            + grid(8, 16) + r.normal(0, 2.0, (h, w)))
    v = np.clip(v, 20, None)
    s = np.clip(0.19 + grid(16, 0.020) - 0.0019*(v - 90), 0.03, 0.42)
    img[y0:y1, x0:x1, 0] = v
    img[y0:y1, x0:x1, 1] = v*(1 - 0.55*s)
    img[y0:y1, x0:x1, 2] = v*(1 - s)
    # Varnish glints: the only part of real wood that gets near the top of the range,
    # and specular, so they wash towards the illuminant rather than towards more wood.
    for _ in range(8):
        spot(img, int(r.integers(x0+8, x1-8)), int(r.integers(y0+8, y1-8)),
             float(r.uniform(1.5, 3.0)), (1.0, 0.99, 0.97), 225.0, occlude=True)

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
        # Grey printed icon. Measured peak 148-179 at saturation 0.11-0.22 — bright
        # enough to label, nowhere near saturated enough to be an emitter.
        img[y+step//2-3:y+step//2+3, cx-4:cx+5] = (165, 155, 140)
        truth.append((cx, y, h))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def highlights(W, H):
    """LEDs among specular highlights that clip just as hard. Saturation is the only
       thing that tells them apart.

       The LEDs are on an equipment front, not stuck on the plank. That is not a
       convenience: measured radially on the seven real LEDs, the glow is already
       down to value 80 at three pixels out and 39 at four, while the wood around it
       sits at 90. Plant a bare LED on bare wood and more than half of the padded box
       the hue is read from is wood at hue 27 — the earlier version of this scene did
       exactly that, and the app answered RED OR YELLOW for a 4-degree red and
       YELLOW OR GREEN for a 120-degree green. Both answers are honest about their
       own uncertainty, and both describe a mounting that does not exist."""
    img = _f(W, H, 30, 9)
    woodgrain(img, 0, H, 0, W, seed=4)
    img[int(H*0.12):int(H*0.78), int(W*0.17):int(W*0.33)] = 22       # dark device front
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
    """A plain room with wood and a highlight. Anything found here is a false alarm.

       Clean at strict and normal. At loose it still labels about two dozen single
       grain pixels, and that is not this scene lying: with no emitter in frame the
       saturated peak is only 136, so the threshold drops to its floor of 120 and the
       loose tier's minimum area of 1 turns every stray pixel into a blob. Real wood
       does the same — the capture in corpus/ has roughly 48 pixels per frame over
       value 120 at saturation 0.20 or more, this scene has 25. The app's answer to
       that is the footer, which says what it found and at what threshold."""
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
    """KNOWN LIMIT, not a pass/fail: an LED too dim to clip, sharing a frame with a
       normal one. The detector is built on indicator LEDs reaching the top of the
       sensor's range, and its threshold is a fixed distance below the brightest
       SATURATED pixel in the frame — so a dim LED survives only while nothing
       brighter and coloured is in the picture with it.

       Measured, dim LED at gain 110 against a normal one at 500:
           alone in a dark room             found at every tier (it sets the bar)
           on wood                          found - wood is not saturated enough
           on wood beside a highlight       found - a highlight clips white
           with one normal LED in frame     LOST at every tier  <- this scene
       The last line is the one that matters: equipment panels carry more than one
       light, and the normal one puts the threshold at 235-247. An earlier version of
       this scene had the dim LED alone, so it passed, and documented nothing."""
    img = _f(W, H, 16, 29)
    truth = [(W//2, H//2, 120), (int(W*0.8), int(H*0.25), 155)]
    led(img, W//2, H//2, 120, sigma=4, gain=110)        # too dim to clip — lost
    led(img, int(W*0.8), int(H*0.25), 155)              # normal — sets the threshold
    return np.clip(img, 0, 255).astype(np.uint8), truth

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
    'dim':        'KNOWN LIMIT: a dim LED beside a normal one',
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
