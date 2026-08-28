# 2026-08-28 — X-axis response curve identified

**Setup**

- MOZA AB9, MH16 fitted. Baseline: all curve tables linear.
- **Single change, made in MOZA Cockpit: X-axis response curve set to a
  strongly non-linear shape.** Nothing else touched.
- Base returned to the host, re-swept with the same tool and method as the
  baseline. Data: [`data/2026-08-28-ab9-xcurve-nonlinear.json`](data/2026-08-28-ab9-xcurve-nonlinear.json)

This is the first differential result in the project where a known change was
made and a specific setting moved. Everything before it was structure.

## Result: three things changed, and only three

| id | index | before | after |
|---|---|---|---|
| **149** | bank 1, slots 2–5 | 20, 40, 60, 80 | **54, 52, 70, 65** |
| **151** | bank 0, slot 1 | 2 | **0** |
| 225 | bank 2, slots 1, 2, 7 | 0, 0, 0 | no longer valid |

**No plain getter changed at all** — including the float curve at ids 83–89,
which still reads 20/40/60/80/100. So that float table is *not* the axis response
curve. It is something else that happens to hold curve-shaped numbers, and the
earlier note calling it "the same curve expressed twice" was wrong.

## id 149 bank 1 is the X-axis response curve

Confirmed over two passes, identical both times:

```
id 149 bank 0:  slot 1=0, 2=20,  3=40,  4=60,  5=80,  6=100     (linear)
id 149 bank 1:          2=54,  3=52,  4=70,  5=65,  6=100     ← X axis, non-linear
```

Slot 1 is absent in bank 1. (An earlier claim that slot 6 "stays pinned at 100"
was **wrong** — it happened to be 100 here; the Y axis later showed slot 6 at 48.
See [`2026-08-28-ab9-y-curve-saturation-pairing.md`](2026-08-28-ab9-y-curve-saturation-pairing.md).) The new sequence is non-monotonic (54, 52, 70, 65), which
is what a hand-dragged "comically non-linear" curve should look like — it is not
a smooth preset.

Values are plain integers, 0–100, one byte.

## id 151 is the companion mode/preset selector

Slot 1 went from **2 to 0** at the same time. The obvious reading is a curve-mode
enum flipping from a preset (2) to custom (0) when the points were hand-edited.
Its partner id 152 still reads 2.

## The pairing rule

The five curve-shaped tables that did **not** change all still read
`0, 20, 40, 60, 80, 100`. But 149 has a structural twin:

```
id 149 bank 1:  [absent, 54, 52, 70, 65, 100]   ← changed
id 150 bank 1:  [absent, 20, 40, 60, 80, 100]   ← unchanged, identical shape
```

Ids 149 and 150 share a shape no other table has — bank 1 missing slot 1 — and
only 149 moved. Same story one id along: 151 changed, 152 did not.

**Hypothesis: consecutive command ids are (X, Y) pairs, lower id = X.** That
would make 147/148, 149/150, 151/152, 171/172, 181/182, 205/206, 218/219 and
220/221 all axis pairs, and would explain why so many settings appear twice with
identical values on a symmetric, at-rest base.

This was one data point when written. **It has since been confirmed**: changing
the Y curve moved ids 150 and 152 and left 149 and 151 untouched, exactly as
predicted. See
[`2026-08-28-ab9-y-curve-saturation-pairing.md`](2026-08-28-ab9-y-curve-saturation-pairing.md).

## Unexplained

Id 225 bank 2 slots 1, 2 and 7 stopped answering — they returned 0 before and are
now rejected. A settings change should not alter which indices *exist*. Id 225
has been odd throughout (mixed payload widths, scattered slots) and is probably a
status or descriptor block rather than a setting. Flagged, not explained.

## Verification status

- [x] single-variable change, baseline and re-read with identical method
- [x] X curve located at `(149, bank 1, slots 2–5)`, confirmed over two passes
- [x] float table at 83–89 ruled out as the axis curve
- [ ] the X/Y pairing rule — needs the Y-curve change to confirm
- [ ] id 151's enum values beyond "2 became 0"
- [ ] id 225's index set changing
- [ ] no writes attempted

**Confidence**: `observed` for id 149 bank 1 being the X curve — a known cause
produced exactly this effect. `inferred` for id 151's meaning. The pairing rule:
`hypothesis`.
