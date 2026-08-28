# 2026-08-28 — Deadzone and saturation are the curve's endpoints; invert located

**Setup**

- MOZA AB9, MH16 fitted. Two changes made in Cockpit:
  1. **X axis inverted.**
  2. **Both Y curve endpoints dragged inward as far as they go** — the user
     reports the plot's x-position for each landed 25 points from its edge.

## Deadzone and saturation are the curve's input-axis endpoints

The diff:

| id | | before → after |
|---|---|---|
| 152 bank 0 slot 1 | Y "deadzone" | 2 → **25** |
| 152 bank 0 slot 2 | Y "saturation" | 100 → **75** |

The user moved the first point to 25 from the left edge and the last point to 25
from the right edge. Deadzone became **25**; saturation became **75**, i.e.
`100 − 25`. Both match the reported plot positions exactly.

**So these are not two independent effects — they are the x-coordinates of the
response curve's first and last control points.** The curve maps the input span
`[deadzone, saturation]` onto the full output range. Everything below the first
point is dead; everything above the last is saturated.

This retro-explains earlier observations that had been recorded as separate
findings:

- Dragging only the final point left set saturation to 75 — it was moving that
  point's x-coordinate.
- The deadzone "clamps then rescales" — inevitable, because the curve simply
  starts at that input position.
- The curve editor zeroing the deadzone when a custom curve was first applied was
  the editor placing the first control point at x=0.

The practical consequence for tux-ffb: **axis shaping is one object, not three.**
A curve, its two endpoints, and its interior points are a single editable entity,
and the UI should present it that way rather than as a curve plus two unrelated
sliders. `03-device-model.md`'s settings taxonomy should model it accordingly.

## The curve is still non-monotonic, and moving the endpoints cannot fix it

```
id 150 (Y) bank 1:  slot2=20  slot3=40  slot4=29  slot5=80  slot6=100
                                            ^ drops 11 from slot 3
```

Slot 4 holds **29** where monotonic shape needs roughly 60. The endpoints are the
*x*-positions; slots 2–6 are the *output values*. Dragging the endpoints inward
rescales the input span but leaves the interior output values untouched — so the
fold survives, exactly as the user observes on the aft stroke.

This is consistent with the earlier axis trace, where the fold was measured at
output 45720 → 42399, matching stored slots 3 and 4 (40 and 29) to within 0.2%.

## Axis invert: id 158

`id 158` went **0 → 1** when X was inverted. No other unexplained id moved.

Its axis partner is not adjacent: ids 154–157 and 159–161 are invalid on this
firmware, and the next readable neighbour is **id 162**, currently 0. If the
X/Y pairing holds in spirit, `158 = X invert` and `162 = Y invert` — but the
usual "consecutive ids" form of the rule does not apply here, so this is a
hypothesis with an obvious test: invert Y and see whether 162 flips.

## Unexplained

`id 151 slot 1` (X deadzone) went **2 → 0** across the invert, then back to 2
afterwards. Since 2 is the default node position, the most likely reading is that
Cockpit rewrote the axis on connect and briefly placed the node at 0. Not
distinguished from "inverting an axis resets its first node", and low stakes
either way.

## Confirmed by prediction

The user then set the leftmost node to x=2 on X and x=6 on Y, and reported those
positions **without stating the expected register values**. Read back:

```
id 151 (X) bank 0 slot 1 = 2   expected 2   MATCH
id 152 (Y) bank 0 slot 1 = 6   expected 6   MATCH
```

They also confirm the link is bidirectional in Cockpit — editing the deadzone
field moves the node, and moving the node changes the field — and that the
default node position is x=2, which is why every untouched axis has read 2
throughout this investigation.

`id 158` also went **1 → 0** when the X invert was switched back off, confirming
it in both directions.

## Verification status

- [x] deadzone/saturation identified as the curve's endpoint x-coordinates
- [x] non-monotonic interior confirmed as the cause of the persisting fold
- [x] axis invert located at id 158 (X)
- [x] endpoint mapping confirmed by blind prediction (x=2 / x=6)
- [x] id 158 confirmed as X invert in both directions (0→1→0)
- [ ] id 162 as the Y invert — needs a Y invert to confirm
- [ ] why X's deadzone went to 0

**Confidence**: `observed` for the endpoint interpretation and the invert flag.
`hypothesis` for id 162.
