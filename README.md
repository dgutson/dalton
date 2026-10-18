# Dalton

Names the colour of an LED from the phone camera. Offline, no network, no accounts.

    ./serve.sh            # then open http://localhost:8080 in Chrome

Add it to your home screen from Chrome's menu for an app icon. The server has to be
running in Termux each time.

## How it reads a colour

An LED pointed at a phone camera clips: auto-exposure meters the room, the LED is far
brighter, and its core saturates to (255,255,255) — pure white, whatever colour it is.
So the centre pixel is the one pixel guaranteed to carry no information.

Instead, every pixel in the reticle is examined and three kinds are thrown away:

  * dark pixels (max channel < 28) — noise
  * **clipped pixels (any channel >= 250)** — a capped channel biases the hue. The
    dominant channel stops at 255 while the others keep climbing, which drags red
    towards amber. Measured on synthetic LEDs: a hard-clipped amber reads 34 deg if
    clipped pixels are kept, 26 deg (its true hue) if they are dropped.
  * desaturated pixels (S < 0.15) — the grey halo

What survives is the coloured fringe around the blown core. Its hue is averaged as a
*circular* mean weighted by saturation — circular because red straddles 0/360 and a
plain average of 350 and 10 gives you cyan.

If too little survives, the app says why — TOO BRIGHT, OFF / DARK, WHITE — rather than
guessing. A loud failure beats a confident wrong answer.

A second pass at S >= 0.05 runs only when the strict pass finds nothing. If it turns up
a faint but consistent tint it reports the colour marked WASHED OUT; if the tint is
below 5% saturation it is a genuine white LED.

## Simplified mode

The `FULL` / `SIMPLE` pill in the top corner switches the answer set. Simplified mode
answers only RED, YELLOW, GREEN or OTHER — the vocabulary of equipment status LEDs.
AMBER becomes YELLOW; blue, cyan, violet, magenta and white all become OTHER. The mode
is remembered between launches.

Fine-grained names like AMBER and LIME are worse than useless to a user who has no
referent for them. Precision in the output is not the goal; actionability is.

With only four answers each boundary carries more weight, so two narrow zones report
both names instead of rounding off. Measured by running the shipped code against a hue
sweep (`tools/check.sh`):

      0 - 10 deg    RED
     15 - 20 deg    RED OR YELLOW
     25 - 80 deg    YELLOW
     85 - 90 deg    YELLOW OR GREEN
     95 deg up      GREEN

Both hedges are ten degrees wide and both sit on a cut that is genuinely ambiguous to
the eye as well as to the camera. An earlier version left a twenty-six degree hole
answering YELLOW OR GREEN across the whole LIME band — a refusal to answer, in the
middle of the range where an answer is most wanted.

Two band edges are deliberately off-centre, both in the same direction:

- **Lime (68-88 deg) is YELLOW, not GREEN.** It is where the older yellow-green
  indicators land. A yellow LED called GREEN is a warning nobody looks at; a green LED
  called YELLOW costs a second glance. The second mistake is the cheap one.
- **The red/amber cut is at 18 deg, not 12.** A red fault light photographs anywhere up
  to about 15 degrees, and calling a fault a warning is the expensive direction.

Hedging stops at the edges of OTHER deliberately. Red LEDs read close to the magenta
cut at 345 deg, so hedging there would fire constantly, and "red or other" is not a
distinction worth acting on.

## Reading the display

Nothing you need is encoded in colour alone. The name is text, and the bar is
position-encoded: the band segments are fixed, the white marker is the measured hue.
How close the marker sits to a segment edge is how much to trust the name — within
6 deg the app says BORDERLINE and names both neighbours.

The stats line is the raw evidence: measured hue, mean saturation, mean value, `agree`
(how tightly the pixels concur on one hue), and the pixel census.

## Calibration

Defaults are tuned for red/amber/yellow/green separation. Your LEDs and camera will
differ. Point at an LED you can identify, read the hue in the stats line, open settings
and nudge the neighbouring boundary. Saved in localStorage on this phone.

Boundary defaults, degrees:

    RED 345 | AMBER 12 | YELLOW 40 | LIME 68 | GREEN 88
    CYAN 160 | BLUE 200 | VIOLET 250 | MAGENTA 288

LIME exists on purpose — yellow-green is where a red-green confusion is most likely to
matter, so it gets its own name instead of being swallowed by GREEN.

## Controls

    SCAN / LIVE    capture and name every LED at once, or go back to the reticle
    tap image      freeze / unfreeze (live mode only)
    FULL / SIMPLE  switch between nine colour names and red/yellow/green/other
    speaker icon   speak the name aloud (live mode only)
    gear icon      sample size, scan sensitivity, exposure, white-balance lock,
                   boundary calibration

Scan sensitivity is **strict / normal / loose**, and it sets three numbers together:
the minimum saturation a pixel needs to count as coloured, how far below the peak the
threshold sits, and the smallest blob that counts as a light. It ships on *normal*,
which finds every LED in the corpus with no false alarms; *loose* trades that for
picking up a faint one, *strict* for being certain.

The speaker icon speaks the name in **live mode only**, once it has held steady for
three frames. Scan mode stays silent: the picture already carries every name, and
reading seven of them aloud is noise.

Exposure, white-balance lock and the flash are only offered if the camera reports
them; many Android cameras expose exposure compensation but not manual white balance.
The flash is the most useful of the three in a dark room — it lights the scene, so the
camera stops itself down and an LED that was blowing out to white stops doing so — and
live mode offers it unprompted when it would help.

## Scan mode — naming every LED in one picture

`SCAN` freezes a frame and names each light in it; `LIVE` goes back to the reticle.

The captured picture fills the screen. Every light gets a ring and its name beside it,
and that is the whole interface — one button to go back, nothing to tap, no panel
underneath. A readout that covers the picture it is describing is worse than no
readout.

The measured hue is printed after the name **only when the name is not confident**.
That is the one case where the number is worth reading, and the one to quote when
moving a boundary. Confident names stay as just a word.

Anything the scan threw away is reported in small text along the bottom edge — what
was ignored and why. A silent cap reads as "that is everything".

### How it finds them

No OpenCV. It would be about 9 MB of WebAssembly, vendored locally because this app is
offline, to get a connected-components pass that is fifty lines of JavaScript — and it
would not touch the part that is actually hard.

The hard part is that "bright" is the wrong question. A sunlit window, a chrome screw
and a white wall are all brighter than an indicator LED. The right question is **what
is emitting**, and that has a clean physical answer:

> An LED emits a narrow band of wavelengths, so when it clips it clips *coloured*.
> A highlight reflects the room's illuminant, so when it clips it clips *white*.

Measured on the first real capture — a router on a desk, thirteen regions over value
245 — the seven LEDs had a 75th-percentile saturation between 0.45 and 0.83 and the six
specular highlights sat at 0.07. There is no overlap, and nothing to tune.

So:

1. **Blur 3x3**, separable, over both value and saturation. One hot pixel is sensor
   grain, not a light.
2. **Take the peak over coloured pixels only** — those at or above the sensitivity's
   minimum saturation, and bright enough for saturation to mean anything at all (value
   60; below that the ratio is noise). A white window never enters the peak, so it
   cannot raise the bar for everything else.
3. **Threshold at the peak less a few counts**, floored at 200. An indicator LED bright
   enough to read as "on" against a room the camera has exposed for sits at the top of
   the range — every LED in every real capture so far peaks at 255. Making the
   threshold relative to that peak adapts it to the scene for free. The floor is high
   for the opposite reason: if nothing coloured in frame is near clipping then there is
   no emitter in shot, and whatever passes is wood grain. At a floor of 120 an empty
   room drew 24 rings; at 200 it says NO LIGHT FOUND.
4. **Connected components on brightness alone**, 8-connected, iterative — recursion
   would blow the stack on a blob of a few thousand pixels. Saturation is deliberately
   *not* a condition for joining a blob. An LED bright enough to blow out is white in
   the middle, so a per-pixel colour gate eats its core and can leave too little above
   the minimum area: on a dark-room capture of three green LEDs, that gate found one.
5. **Drop the wrong shapes.** An LED is small (2% of the frame is already enormous),
   roughly round (aspect under 3) and solid (filling at least 45% of its box). A streak
   of glare along a window frame is none of the three.
6. **Ask whether the blob is coloured anywhere — two ways, believing whichever says
   yes.** This is where the emitter rule is actually applied, and the two kinds of LED
   need opposite evidence. An LED against a lit wall is a hard dot of colour in bright
   grey, and its rim is wall: 0.49 taken over the dot alone, 0.03 once a collar is
   included. An LED that blew out is white in the middle with its colour surviving just
   outside the part that clipped: 0.15 over the core, 0.43 to 0.47 with the collar. So
   take the 75th percentile of saturation both ways and keep the larger. A specular
   highlight fails both — white in the middle, dark outside — which is the whole point.
7. **Rank by that saturation times peak, keep the best 24, and only then sort into
   reading order.** Capping in reading order is a bug that looks like a detector
   failure: the top edge of the frame spends the whole label budget before the panel is
   reached.
8. **Pad outwards** from each blob, then read the colour from **the brightest 30% of
   what is in that box** — never from the dim fringe at its edge. See below; this is
   the step that was wrong for the longest. Clipped pixels are still skipped, the
   padding stops halfway to the nearest neighbour, and pixels labelled as a *different*
   blob are ignored, so two adjacent LEDs cannot bleed into each other.
9. **Ask how much of the neighbourhood is the same colour** — see below. A blob whose
   own hue fills more than 3% of the ring around it is part of a larger coloured thing,
   not an indicator, and is dropped.
10. **Name it** with exactly the same code the live reticle uses — one implementation of
   the bands, the simplified buckets and the hedging, so the two modes can never
   disagree. A fringe whose hue vectors cancel out — agreement below 0.50 — is not
   named at all: that is a grey fringe pointing every direction at once, and naming it
   produced a white LED confidently called VIOLET.

### Why the first two detectors failed

Both of them shipped, and both failed on the same photograph: a seven-LED router column
against wood panelling.

**A fraction of the brightest pixel** found the top LED and lost the six below it.
Every number in it is set by the single brightest thing anywhere in shot, so the power
LED set a bar the rest could not clear, an indicator at value 120 was invisible once
anything hit 255, and a floor of 100 discarded anything dimmer outright.

**Local contrast** — how far a pixel rises above a grey opening of its own surroundings
— is scale-free, and on the synthetic scenes of the day it was perfect. On the real
frame it labelled 24 fragments of wood grain and still found one LED. The reason is
measurable: the LEDs rose 141 to 204 above their surroundings and the frame's own 99th
percentile of local rise was 153. No threshold separates those. Worse, every false
positive it added was *reflective* — a yellow ethernet cable, a fern, sunlit wood —
because local contrast cannot tell a light from a thing that is lit.

The synthetic scenes had not caught it because they modelled a dim LED that does not
clip, and wood that does not exist. Real indicator LEDs always clip. The scenes were
rebuilt from measurements off the real capture, and the detector was rebuilt around the
one property a reflector cannot fake.

### Why reading the fringe was wrong

The third failure was not in finding the LEDs but in reading them, and it survived two
rounds of fixing the wrong thing.

The rule was: a clipped core carries no hue, so pad outwards and read the unclipped
fringe. In a lit room that is harmless, because the fringe is still mostly LED. In a
dark room it is fatal. The camera opens right up, and the fringe becomes mostly *room*
— the ambient, plus the LED's own glow bouncing off the plastic it is mounted on.
Across two dark captures of the same switch, six green LEDs read hue 80 to 112 at the
fringe — yellow, at 0.99 agreement, which is as confidently wrong as this app can be —
while the bright tops of the very same blobs read 108 to 151, green.

The fringe is not *noisy*, it is **biased**, and that distinction decided the fix.
Three different weighting schemes were tried, down-weighting the fringe by brightness
and by its height above the local background; all three landed within ten degrees of
the yellow/green cut, because no weighting removes a bias. The fringe has to be left
out. Reading the brightest 30% of each region instead puts all thirteen LEDs across the
three real captures at least thirteen degrees clear of a band edge.

Letting *clipped* pixels in was tempting for the same reason — they are where the LED's
own light is strongest — and it was tried and rejected. A pinned channel drags the hue
towards whichever channel is second, which is towards 60° from both the red side and
the green side; it cost three LEDs on the synthetic hue sweep and bought nothing the
brightness cut had not already won.

### Chromatic uniqueness, or: what a person is actually doing

Shown a photograph of the router, a person picks out the LEDs instantly and ignores the
wood grain, the cable and the blue rubber bulb — and the obvious explanation, that they
*recognise* the objects, is wrong, or at least beside the point. Nothing about knowing
what a ukulele is helps decide whether a bright speck is lit or emitting.

What they are using is **local colour context**:

> An LED is a point of colour with nothing else like it nearby. A lit object never is.

A speck of wood grain sits in a field of more wood the same colour. A yellow cable is
one bright point on a long yellow curve. A blue rubber bulb is surrounded by more blue
rubber. An LED is surrounded by its own mounting, and by the dark.

So for each blob: take a ring around it, and count what fraction of it is within 12° of
the blob's measured hue. Over all eight real captures — 93 verified LEDs and the 24
false positives that survived every earlier rule:

| | fraction of the ring sharing the hue |
|---|---|
| 93 real LEDs | 0.00% – 1.73%, 95th percentile **0.60%** |
| 24 false positives | **4.95%** – 35.4%, median 8.9% |

Nothing lands in between, and the cut at 3% sits 1.7× above the worst LED and 1.65×
below the first thing it kills. It removed 20 of the 24, leaving seven across the whole
corpus. **No model is needed for this, and one would be the wrong tool**: it is twenty
lines of arithmetic, no weights, no training data, no network, and it runs in a few
milliseconds on the phone.

Two details decide whether it works at all:

- **The ring, not the disc.** A bright LED throws a halo of its own colour onto
  whatever it is mounted on; counting that halo is counting the LED twice. Excluding
  everything within three blob-radii took the red LED of `0006-red-in-the-dark` from
  4.7% down to 1.7% and roughly doubled the usable margin.
- **The blob's *measured* hue, not its centre pixel's.** A clipped LED's centre pixel is
  white, so it matches nothing and every blob scores zero — a bug that makes the test
  look like it is working perfectly.

### Why the captured frame is shown whole

The live preview is `object-fit: cover`, which on a portrait phone showing a landscape
sensor crops away about two thirds of the width. That is right for aiming — the reticle
is dead centre — and wrong for a still. LEDs found in the cropped-off part still got a
ring and a label, clamped to the screen edge, pointing at nothing visible. The captured
frame is letterboxed instead, so everything that was found can be seen.

### What it deliberately does not do

**It does not drop a doubtful light.** A spare false positive is cheap to ignore on
screen; a missing LED is not. So a blob whose surroundings are nearly as bright as it
is gets *flagged* ("background nearly as bright") rather than discarded, and a hue that
lands near a boundary is reported as RED OR YELLOW rather than resolved to the nearer
side.

**It does not cap silently.** The footer says what was ignored and why, the threshold it
used, and how many exposures it took. A silent cap reads as "that is everything".

### Bright backgrounds

A lit white wall behind the LEDs used to defeat it completely: at a low threshold the
wall merged into one giant region that swallowed the LEDs inside it, and at a high one
the LEDs survived detection only to be thrown out as "not isolated". The emitter rule
makes it a non-problem. A white wall is white, so it is never a candidate, so it never
enters the peak and never forms a blob. Verified against a synthetic wall at value 200
behind LEDs clipping at 255, and against a blown-out window beside five LEDs: correct
names at every sensitivity, no extras.

### Dividing out the illuminant

A camera in a dark room opens up and also warms up. On the two real captures the grey
things in frame come back R/G 1.12 in the dark corner against 0.95 in the lit room, and
that cast on its own dragged three green LEDs to hue 75, 82 and 94 — named YELLOW, with
0.99 agreement. Confidently wrong is the worst answer this app can give.

The scene's own greys are the reference. Every pixel bright enough to trust, not
clipped, and nearly neutral is averaged, and that average is called white; hue and
saturation are then read with the two gains divided out. Clipping and darkness are
still judged on the raw reading, because those are facts about the sensor rather than
about the light. The gains are clamped to ±35%, and a frame with too little grey in it
— a close-up of a black panel — gets no correction rather than an invented one.

**Detection never sees the corrected pixels.** Scaling values before thresholding
changes which blobs exist, and on the lit capture that turned seven LEDs into
twenty-four rings of wood grain.

On the dark capture this moves the three LEDs to hue 94, 100 and 135: two named GREEN
and one hedged YELLOW OR GREEN, against none right before. On the lit capture it is
very nearly a no-op — hues 150-163 become 151-164 — which is the point. A correction
that only fires where it is needed is one you can leave switched on.

### Driving the camera, and the flash

Dividing the illuminant out fixed the colour cast, and reading the bright part of each
blob fixed the rest. Exposure was supposed to be the fix for both, and it turned out
not to be needed for either — which is worth writing down, because the obvious lever
here is a trap.

SCAN does not accept the camera's exposure. It asks for `exposureMode: "manual"` and
walks `exposureTime` down, measuring the frame after every step; a camera with no
manual mode gets `exposureCompensation` walked to its minimum instead. The darkest
*usable* frame is read first — that is where the reflections have fallen away and only
the emitters are left — and if it yields nothing, the next brightest, and so on.

**The phone honours the request. That was the problem.** On `corpus/0003-dark-router`
the ladder asked for a quarter of the exposure and got a frame sixty times darker:
medians 24, 1, 1, 1, 1, 1. Every darkened plane was solid black, the LEDs with it, and
the scan fell back to the auto-exposed frame having spent 1.7 seconds photographing
nothing. Two causes, both now fixed:

- The ladder also pinned `iso` to the sensor minimum — 50, from a maximum of 3200. In a
  dark room the camera had opened up to meet the dark, and this slammed it shut: a 64x
  cut on its own, on top of the 4x being asked for. ISO is now left alone.
- The `exposureTime` a camera reports while it is still in *continuous* mode is not the
  exposure it is using. Dividing that number by four is dividing a fiction. The ladder
  now halves rather than quarters, measures the frame it actually got after each step,
  climbs back once if it overshoots, and stops as soon as there is nothing left to see.

Before anything else is built on a camera parameter, *Settings -> Probe what this
camera can do* walks every lever the camera claims to have, one at a time, and saves
both the numbers and the frames. `python3 tools/probe.py frames/NNNN` reads it back
and gives a verdict per lever — read off the pixels, never off `getSettings()`, which
has now been wrong twice. It is cheap insurance against a third time.

**The torch is the lever that works.** It is also the one suggested to you: in live
mode, when the room is dark *and* something in the circle is clipping — the exact
conditions under which colour degrades, not merely a dark room — a banner offers to
switch the flash on. Lighting the room reaches the same place from the other side, by
making the camera's own auto exposure stop down, and it does not depend on a phone
honouring a constraint in the way the constraint meant.

It can do more than that. An LED emits the same light whether the torch is on or off;
a reflector does not. So a torch-off/torch-on **pair** separates emitter from
reflector by construction — the one ambiguity that no single frame can resolve, and
the source of the false positives on `corpus/0004-vertical-router`. The camera
re-exposes between the two shots by some unknown factor, which rules out comparing
absolute values, but not directions: with the torch on an emitter goes *dimmer*
(`E/k`) while a lit object goes *brighter* (`(A+T)/k`), so ranking blobs by that ratio
works without knowing the factor. `tools/probe.py` runs exactly that test on any probe
that captured the pair. There is a manual toggle under
*Settings -> Camera* as well, and whether it was on is recorded with every capture.

At the darkest usable setting it takes two more shots. A quickly blinking LED is simply
absent from some frames, which is how one of three green LEDs was being lost; among
repeats at the same exposure it keeps whichever found the most.

The whole series is saved, not just the frame that was used, so a selection rule can be
tried offline instead of asking for another photograph. The capture JSON records what
the camera was asked for, what it reported back, and each frame's median brightness. It
says *"camera barely responded to the exposure request"* when the series did not get
darker, and *"every darkened frame was black"* when it got too dark to hold anything. A
phone that mishandles the request in either direction should say so rather than look
like an algorithm bug.

### Known limits

- A window or a lamp is bright, but it is white, so the emitter rule drops it before it
  becomes a blob. A *coloured* lamp is a real ambiguity and does get named.
- Two LEDs closer than a few pixels merge into one blob and get one name.
- A reflection of an LED on glossy plastic is, to the camera, an LED.
- A dim LED beside a bright one is lost: the bright one sets the threshold. That is the
  deliberate cost of a relative threshold, and it is in the test output as a
  `KNOWN LIMIT` row rather than quietly passing.
- A scene with no greys in it gets no illuminant estimate, so a strong cast over a
  wholly coloured subject stays uncorrected. Saying nothing beats guessing.
- A brightly lit *saturated* object — a yellow cable catching the sun — clips coloured
  and is, by the emitter rule alone, indistinguishable from a large yellow LED. This is
  what chromatic uniqueness was built for, and the cables on `0001-cbn-router` and
  `0008-router-on-wood` are now dropped. What survives it is the case the rule cannot
  see: a *small, isolated* coloured object, such as the single blue point on
  `corpus/0007-monitor-standby`, which is as chromatically unique as a real LED. Only
  the torch can refuse that one, by asking whether it emits.
- **Exposure control is a dead end on this phone, and that is now measured** rather
  than assumed — see above. The dark-room fix came from the illuminant and from where
  the hue is read, both proven on `corpus/0002-dark-switch` and `0003-dark-router`.
  The flash is the remaining exposure lever and the only one that behaves.

## Running it, and handing frames back

    ./serve.sh            # http://localhost:8080, loopback only

`serve.py` replaces `python3 -m http.server` for one reason: it accepts
`POST /frame`, which is how a captured frame gets off the phone's browser and onto
the filesystem. Everything still stays on the device — 127.0.0.1 is the Python
process that served the page — but without it the algorithm can only ever be tested
against synthetic images, which is how both of the last two bugs got shipped in the
first place.

**Every scan is saved automatically.** A debug channel behind a button is a debug
channel nobody presses — the first real capture that was wanted never got taken, which
is why this is no longer a button. The chip at the top of the picture says `saved 0003`
or `not saved`; settings has a re-send for the second case. The server writes two files
per capture:

    frames/0001.rgba    raw RGBA, width*height*4 bytes
    frames/0001.json    threshold, exposures, hue boundaries, and one record per
                        LED: position, area, padding, label, hue, saturation,
                        agreement, and the pixel census (used/clipped/grey/dark)

That JSON is the point. It says not just what the app answered but every number it
answered from, so a wrong name can be traced to the pixel counts that caused it.

`frames/` is git-ignored — captures are yours, they do not belong in the history.

To look at one:

    python3 tools/rawpng.py frames/0001 --marks

Standard library only: no Pillow, no numpy. `--marks` rings what the app thought it
found, so a miss or a false positive is visible at a glance.

## Tests

    pkg install quickjs-ng python-numpy git-lfs
    ./tools/check.sh      # real captures first, then synthetic scenes (~30s)
    ./tools/lint.sh       # static checks on index.html; run after every edit to it
    qjs --std tools/label_test.js    # label placement: off-screen and overlaps

The captures in `corpus/` are stored with **git LFS**, so a clone without it gets
130-byte pointer files and `check.sh` fails in a thoroughly confusing way. If that
happens: `pkg install git-lfs && git lfs install && git lfs pull`.

`check.sh` runs two suites, and the order they print in is the point.

**`corpus/`** holds real captures with ground truth checked by eye — where each LED is
and what colour it actually is. These are the authority, and every scan taken with the
app is added to it, including the ones that pass: a capture that works today is what
stops tomorrow's fix from breaking it.

- `0001-cbn-router` — the seven-LED router that broke the first two detectors. 7/7 at
  every sensitivity, no exceptions.
- `0002-dark-switch` — three green LEDs in a dark corner, the capture that broke the
  colour reading. Still carries a `known_limit` for *strict*, which finds two of three.
- `0003-dark-router` — that switch re-shot, and the capture that proved the exposure
  ladder was blacking the frame out. 3/3 at every sensitivity.
- `0004-vertical-router` — seven green LEDs in a column, in a lit room. Here for its
  negatives: a yellow cable and a blue rubber bulb, both lit, saturated, and clipping
  coloured exactly as an emitter does.
- `0005-water-dispenser` — **the first non-green entry.** A red indicator and an amber
  one, both with cores blown to near white, in a dark kitchen; proof that a blown red
  core still comes back red. A third indicator is off and correctly not found.
- `0006-red-in-the-dark` — one red LED in near-total darkness, against a coil of orange
  cable that is strongly coloured but never clips, so none of it is detected.
- `0007-monitor-standby` — a monitor in standby, and the entry that settled an argument:
  reported as red, measured amber at hue 42, while two red LEDs shot the same night in
  the same darkness came back at 1.2 and 1.3. Its negatives are genuine errors — two
  reflections off a teal disc at hue 197 and 199, three degrees inside the green band
  and therefore named GREEN.

To add one:

    python3 tools/corpus.py add frames/0004 0004-my-switch
    # then fill in corpus/0004-my-switch/truth.json — LED positions and colours —
    # and set "verified": true once they have been checked against the picture.

Unverified entries are skipped rather than trusted.

**`tools/scenes.py`** plants synthetic LEDs on routers, lit walls, window edges, a
close-up and an empty room, and records where each one is and what hue it was planted
at. Synthetic scenes are a guess about physics, and this guess has been wrong before:
the first set modelled LEDs that do not clip, and passing it is exactly what let a
1-of-7 detector ship. They are built from measurements off the real capture now — wood
running value 90 to 150 with saturation *falling* from 0.20 in its darkest decile to
0.135 in its brightest — and they earn their keep by being quicker to vary than a
photograph, not by being believed.

`tools/detect_test.js` runs **the real detector and namer, sliced straight out of
`index.html` by its own section markers**, under quickjs. `tools/label_test.js` does
the same for label placement, checking that nothing lands off-screen or on top of
something else. Because both of those only execute the sliced region, `lint.sh` also
compiles the whole script block without running it — otherwise everything that touches
the DOM would never meet a parser, which is how a mangled `async function scan(){`
once got as far as the phone.

There is no second copy of the algorithm anywhere, so there is nothing that can drift.
An earlier Python transliteration found real bugs but had to be re-synced by hand after
every edit; running the shipped JavaScript removes that whole class of mistake.

What none of it can catch: whether this phone's camera behaves the way the model says.
Twice now it has not — an auto white balance that warms up in the dark, and an exposure
request honoured so literally it returned black frames — and both times the only thing
that revealed it was a real capture with its metadata saved beside it.
That is what the saved frames are for.
