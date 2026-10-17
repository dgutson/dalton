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

With only four answers each boundary carries more weight, so two zones report both
names instead of rounding off:

    7 - 17 deg    RED OR YELLOW
    63 - 93 deg   YELLOW OR GREEN

The second is the whole LIME band plus its margins. Yellow-green is genuinely ambiguous
on untested hardware — it could be a yellow LED reading green or a green LED reading
yellow — so it is reported as unsure until calibration settles it. **To settle it:** when
the app says YELLOW OR GREEN, note which LED you are pointing at and the hue in the
stats line, then move the YELLOW|LIME or LIME|GREEN boundary so that band collapses
onto the correct side.

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

    tap image      freeze / unfreeze, and speak the reading
    FULL / SIMPLE  switch between nine colour names and red/yellow/green/other
    speaker icon   speech on / off (spoken only when the name changes)
    gear icon      sample size, exposure, white-balance lock, boundary calibration

Exposure and white-balance lock are only offered if the camera reports them; many
Android cameras expose exposure compensation but not manual white balance.
