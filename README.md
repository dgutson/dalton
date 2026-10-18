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
    gear icon      sample size, scan settings, exposure, white-balance lock,
                   boundary calibration

The speaker icon speaks the name in **live mode only**, once it has held steady for
three frames. Scan mode stays silent: the picture already carries every name, and
reading seven of them aloud is noise.

Exposure and white-balance lock are only offered if the camera reports them; many
Android cameras expose exposure compensation but not manual white balance.

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
would not touch the part that is actually hard. Finding the LEDs is the easy half:

1. **Threshold twice and OR the results**, because each test is blind to what the
   other sees:
   - *local* — how far a pixel rises above its own surroundings, measured against a
     grey opening of the frame on a coarse grid. Scale-free, so a dim activity LED on
     a dark bezel passes as easily as a blazing power LED. Blind to a light so large
     it becomes its own background.
   - *global* — a fraction of the brightest pixel in the frame. Catches that large
     light, and nothing dimmer than the fraction.

   Global alone is what shipped first, and on a seven-LED router panel it found the
   top one and lost the six below it: the power LED set a bar the rest could not
   clear. See *Why one threshold was not enough* below.
2. **Connected components**, 8-connected, iterative — recursion would blow the stack on
   a blob of a few thousand pixels.
3. **Pad outwards** from each blob and read the colour *there*. This is the whole point.
   A clipped core carries no hue (see above); the unclipped fringe around it does. The
   padding stops halfway to the nearest neighbour, and pixels labelled as a *different*
   blob are skipped, so two adjacent LEDs cannot bleed into each other.
4. **Name it** with exactly the same code the live reticle uses — one implementation of
   the bands, the simplified buckets and the hedging, so the two modes can never
   disagree. A fringe whose hue vectors cancel out — agreement below 0.50 — is not
   named at all: that is a grey fringe pointing every direction at once, and naming it
   produced a white LED confidently called VIOLET.

### Why one threshold was not enough

A global threshold is `max(100, peak x fraction)`. Every number in it is set by the
single brightest pixel anywhere in shot, so:

- a router's power LED, or a lamp in the corner of the frame, raises the bar for every
  other LED;
- an indicator at value 120 is invisible at any sensitivity once something hits 255;
- and the floor of 100 discards anything dimmer than that outright.

Local contrast has none of those properties. The background estimate is a grey opening
— erode, then dilate — on a grid of blocks about a thirtieth of the frame. Eroding
deletes anything smaller than the window, which is every LED; dilating puts the level
back, so the estimate is the scene without its lights. The dilation is deliberately the
wider of the two, because a symmetric opening leaves a false ridge along any hard
bright edge (a window frame, a monitor bezel) and a ridge reads as a row of lights.

Measured on the synthetic scenes, old versus new, at loose sensitivity:

                                     global only    both
    router, 7 LEDs top to bottom        3 / 7       7 / 7
    5 LEDs beside a blown-out window    1 / 5       5 / 5
    close-up, 1 huge LED + 2 small      2 / 3       3 / 3
    empty room (false alarms)             0           0

The last row is why the value is blurred 3x3 first: without it, the loose threshold
finds sensor grain.

### Why the captured frame is shown whole

The live preview is `object-fit: cover`, which on a portrait phone showing a landscape
sensor crops away about two thirds of the width. That is right for aiming — the reticle
is dead centre — and wrong for a still. LEDs found in the cropped-off part still got a
ring and a label, clamped to the screen edge, pointing at nothing visible. The captured
frame is letterboxed instead, so everything that was found can be seen.

### What it deliberately does not do

**It does not drop a doubtful light.** A spare false positive is cheap to ignore on
screen; a missing LED is not. So a blob whose surroundings are nearly as bright as it
is gets *flagged* ("background nearly as bright") rather than discarded, and the
default sensitivity is the loose one.

**It does not cap silently.** The footer says what was ignored and why, the threshold it
used, and how many exposures it took. A silent cap reads as "that is everything".

### Bright backgrounds

A lit white wall behind the LEDs used to defeat it completely: at a low threshold the
wall merges into one giant region that swallows the LEDs inside it, and at a high one
the LEDs survived detection only to be thrown out as "not isolated". Both are fixed.
The global half still steps up (0.82 → 0.90 → 0.95 of peak) if more than a tenth of the
frame clears it, and the footer says when it did; the local half is unaffected by a
bright background by construction. Verified against a synthetic wall at value 200
behind LEDs clipping at 255: two LEDs, correct hues, at every sensitivity.

### Exposure bracketing

If the camera exposes `exposureCompensation`, SCAN also takes two darker shots and reads
each light from whichever one left the most usable fringe. Darker means less clipping
means more hue survives. It costs about a second; turn it off in settings. Without it,
or if the camera refuses, it falls back to the single frame.

### Known limits

- A window or a lamp is bright too. It gets found and usually named TOO BRIGHT. Ignore it.
- Two LEDs closer than a few pixels merge into one blob and get one name.
- A reflection of an LED on glossy plastic is, to the camera, an LED.
- None of this has been tested against a real camera yet, only against synthetic scenes
  with realistic clipping profiles. Every capture is saved (below) so that changes.

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

    pkg install quickjs-ng python-numpy
    ./tools/check.sh

`tools/scenes.py` plants synthetic LEDs — emissive, gaussian, clipping where they go
over 255 — on routers, lit walls, window edges and an empty room, and records where
each one is and what hue it was planted at. `tools/detect_test.js` then runs **the real
detector and namer, sliced straight out of `index.html` by its own section markers**,
under quickjs. `tools/label_test.js` does the same for label placement, checking that
nothing lands off-screen or on top of something else.

There is no second copy of the algorithm anywhere, so there is nothing that can drift.
An earlier Python transliteration found real bugs but had to be re-synced by hand after
every edit; running the shipped JavaScript removes that whole class of mistake.

What it will not catch: whether a real camera behaves like the synthetic model. That is
what the saved frames are for.
