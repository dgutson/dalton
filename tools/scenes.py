"""Synthetic LED scenes, with ground truth, for tools/check.sh.

Emissive sources with a gaussian profile that clips where it goes over 255 — which is
the whole difficulty: an LED core carries no hue, only its fringe does. The detector
and the naming both live in index.html and are tested there, by running the real
JavaScript under quickjs. Nothing here duplicates them, so nothing here can drift.
"""
import numpy as np, os, json, sys

def led(img,cx,cy,r,rgb_,gain):
    """Emissive spot: gaussian core, clips where it goes over 255."""
    H,W=img.shape[:2]
    y,x=np.ogrid[max(0,cy-4*r):min(H,cy+4*r), max(0,cx-4*r):min(W,cx+4*r)]
    g=np.exp(-(((x-cx)**2+(y-cy)**2)/(2.0*r*r)))*gain
    sl=(slice(max(0,cy-4*r),min(H,cy+4*r)), slice(max(0,cx-4*r),min(W,cx+4*r)))
    for c in range(3):
        img[sl][:,:,c]+=g*rgb_[c]

def hue_led(h, s=1.0):
    """RGB for a hue, full saturation — the colour an LED's unclipped fringe shows."""
    import colorsys
    return colorsys.hsv_to_rgb((h % 360) / 360.0, s, 1.0)

def router(W=1280, H=720, bg=18, lamp=None):
    """A router panel: 7 LEDs top to bottom, red / green / yellow only, with the
    brightness spread that broke the old detector — the top one blazing, the rest
    progressively dimmer. Hues are where real indicator LEDs actually land."""
    img = np.full((H, W, 3), float(bg))
    img += np.random.default_rng(7).normal(0, 2.0, img.shape)
    img[180:620, 480:800] += 22                      # router body
    spec = [(120, 900), (120, 320), (35, 150), (120, 120),
            (4, 95), (35, 80), (120, 70)]            # (hue, gain)
    cx, y = 640, 240
    truth = []
    for h, gain in spec:
        led(img, cx, y, 7, hue_led(h), gain)
        truth.append((cx, y, h))
        y += 55
    if lamp:
        led(img, lamp[0], lamp[1], 40, (1.0, 0.92, 0.80), 1400)
    return np.clip(img, 0, 255).astype(np.uint8), truth

def sweep(W=1280, H=720):
    """One LED per planted hue, 0 to 115 degrees in 5 degree steps, all the same
    middling brightness. Answers directly: at what hue does this app stop saying RED
    and start saying YELLOW, and likewise YELLOW to GREEN."""
    img = np.full((H, W, 3), 16.0) + np.random.default_rng(23).normal(0, 2.0, (H, W, 3))
    truth = []
    hs = list(range(0, 120, 5))      # 24 LEDs: the per-scan cap, and the range that matters
    for i, h in enumerate(hs):
        cx = 90 + (i % 8) * 157
        cy = 90 + (i // 8) * 150
        led(img, cx, cy, 9, hue_led(h), 220)
        truth.append((cx, cy, h))
    return np.clip(img, 0, 255).astype(np.uint8), truth

def wall(W=1280,H=720):
    """Two LEDs on a brightly lit wall — the case that used to find nothing."""
    img=np.full((H,W,3),200.0)
    img+=np.random.default_rng(3).normal(0,2.0,img.shape)
    led(img,500,360,9,hue_led(4),260)
    led(img,780,360,9,hue_led(120),240)
    return np.clip(img,0,255).astype(np.uint8),[(500,360,4),(780,360,120)]

def single(W=1280,H=720,gain=400):
    img=np.full((H,W,3),16.0)+np.random.default_rng(5).normal(0,2.0,(H,W,3))
    led(img,640,360,10,hue_led(35),gain)
    return np.clip(img,0,255).astype(np.uint8),[(640,360,35)]

def closeup(W=1280,H=720):
    """Phone held right up to one LED: a big blob, plus two smaller neighbours."""
    img=np.full((H,W,3),20.0)+np.random.default_rng(11).normal(0,2.0,(H,W,3))
    led(img,640,360,55,hue_led(120),700)
    led(img,300,360,14,hue_led(4),180)
    led(img,980,360,14,hue_led(35),140)
    return np.clip(img,0,255).astype(np.uint8),[(640,360,120),(300,360,4),(980,360,35)]

def nothing(W=1280,H=720):
    """A plain dim room. Anything found here is a false alarm."""
    img=np.full((H,W,3),42.0)+np.random.default_rng(13).normal(0,3.0,(H,W,3))
    img[300:500,200:900]+=30
    return np.clip(img,0,255).astype(np.uint8),[]

def window_scene(W=1280,H=720):
    """Router bezel beside a blown-out window: a hard 200-level step edge."""
    img=np.full((H,W,3),22.0)+np.random.default_rng(17).normal(0,2.0,(H,W,3))
    img[80:640, 760:1240]=250.0                     # window, hard edged
    for i,(h,gain) in enumerate([(120,300),(35,110),(4,80),(120,70)]):
        led(img,420,220+i*60,8,hue_led(h),gain)
    led(img,700,400,8,hue_led(120),120)             # LED 60px from the window edge
    return np.clip(img,0,255).astype(np.uint8),[(420,220,120),(420,280,35),(420,340,4),
                                                (420,400,120),(700,400,120)]

# ---------------- candidate: union of local contrast and global peak ----------------
# They fail on opposite cases. Local contrast loses an LED so big it becomes its own
# background (phone held right against it); the global peak loses every LED dimmer than
# a fraction of the brightest thing in shot. Neither is redundant, both are cheap, and
# an extra false light is cheaper than a missed one. So: OR the two masks.
TIER={'low':(55,0.90),'med':(35,0.82),'high':(25,0.68)}


SCENES = {
    'router':     lambda W,H: router(W,H),
    'routerlamp': lambda W,H: router(W,H, lamp=(1050,150)),
    'wall':       lambda W,H: wall(W,H),
    'single':     lambda W,H: single(W,H),
    'closeup':    lambda W,H: closeup(W,H),
    'empty':      lambda W,H: nothing(W,H),
    'window':     lambda W,H: window_scene(W,H),
    'sweep':      lambda W,H: sweep(W,H),
}
TITLES = {
    'router':     'router, 7 LEDs top to bottom',
    'routerlamp': 'the same, with a lamp in shot',
    'wall':       '2 LEDs on a brightly lit wall',
    'single':     'one LED, dark room',
    'closeup':    'close-up: 1 huge LED + 2 small',
    'empty':      'empty room, no LEDs at all',
    'window':     '5 LEDs beside a blown-out window',
    'sweep':      'hue sweep, 0-115 deg in 5 deg steps',
}

if __name__ == '__main__':
    d = sys.argv[1]; W, H = 1280, 720
    os.makedirs(d, exist_ok=True)
    truth = {}
    for name, mk in SCENES.items():
        img, tr = mk(W, H)
        np.dstack([img, np.full((H, W), 255, np.uint8)]).tofile(f'{d}/{name}.rgba')
        truth[name] = tr
    json.dump({'w': W, 'h': H, 'truth': truth, 'titles': TITLES},
              open(f'{d}/truth.json', 'w'))
    print(f'{len(SCENES)} scenes -> {d}')
