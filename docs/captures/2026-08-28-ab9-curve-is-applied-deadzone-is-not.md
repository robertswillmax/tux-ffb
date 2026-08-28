# 2026-08-28 — The curve IS applied in firmware; the 39% deadzone is not

> **⚠ PARTLY RETRACTED.** The curve findings stand and are confirmed. The
> deadzone conclusion is **wrong** — it *is* applied, and the argument used here
> (that the curve fold's position rules a deadzone out) is invalid: fold output
> values are invariant under the deadzone.
> See [`2026-08-28-ab9-deadzone-IS-applied.md`](2026-08-28-ab9-deadzone-IS-applied.md).

**Setup**

- MOZA AB9, MH16 fitted, on the host. No MOZA software running.
- Stored Y state: curve `(150, bank 1, slots 2–6) = 20, 40, 29, 75, 100`,
  deadzone `(152, bank 0, slot 1) = 39`, saturation slot 2 = 100.
- User swept **centre → forward → aft → centre**, one pass, ~9.5 s.
- 3156 samples of raw `EV_ABS`. Raw data:
  [`data/2026-08-28-ab9-ycurve-sweep.jsonl`](data/2026-08-28-ab9-ycurve-sweep.jsonl)

## Method correction first

The previous test analysed the **set of distinct output values**, looking for a
gap or flat spot. That signature is wrong: a rescaling deadzone and a remapping
curve both preserve continuity and full travel, so neither leaves a gap. It also
discarded time ordering, which is where a non-monotonic curve actually shows up.

The correct signature is a **time series**: during a one-way physical sweep, any
direction reversal in the output can only come from the transfer function.

## Result 1: the response curve is applied, and the stored values predict it

The output turns around twice mid-sweep, in **both directions**, at the **same
two output values**:

| leg | direction | turnaround | turnaround |
|---|---|---|---|
| aft (t=6.0–6.4) | output rising | **45720** ↓ | **42399** ↑ |
| return (t=9.1–9.2) | output falling | **42385** ↑ | **45734** ↓ |

Hand jitter cannot reproduce the same two values travelling in opposite
directions. This is a fold in the transfer function.

**It matches the stored curve numerically.** Taking slots 2–6 as output
percentages of half-travel at evenly spaced inputs, and `output = 32767 +
(V/100) × 32767`:

| slot | stored V | predicted output | observed | error |
|---|---|---|---|---|
| 3 | 40 | 45874 | 45720 / 45734 | **~150 counts (0.2%)** |
| 4 | 29 | 42269 | 42399 / 42385 | **~130 counts (0.2%)** |

The curve says output should *fall* from 40% to 29% between the third and fourth
control points, and it does, at exactly the predicted place. Then it rises
steeply to slot 5 (75) — visible as the fastest segment of the whole sweep,
42435 → 58373 in 0.3 s.

**So the AB9 applies response curves in firmware.** They work on Linux, in DCS,
with no MOZA software anywhere. That materially raises what this project can
deliver.

One discrepancy worth noting: the observed fold is ~3330 counts deep against a
predicted 3605 — about 8% shallow. Likely spline rather than linear interpolation
between control points, which would round off local extrema. Unconfirmed.

## Result 2: the 39% deadzone is still not applied

A 39% deadzone would force output to centre across ±39% of travel, so the output
would **jump** from 32767 to roughly 45600 at the deadzone edge — a gap of some
12,800 counts. The sweep passes smoothly through 33000, 36000, 39000, 42000,
45000 with no gap at all.

The stronger argument is the curve fit above: the predicted fold positions were
computed assuming **no** deadzone, and they landed within 0.2%. A 39% deadzone
would rescale the input and move the fold well away from where it was found.

### The centre plateau is a hand pause, not a deadzone

The sweep does contain a 0.9 s plateau at 32660, near centre — tempting. It
isn't a deadzone:

- The approach **decelerates gradually**: 27710 → 4767 → 0 counts/s. A deadzone
  clamps abruptly at its edge while the hand is still moving at speed.
- It sits at 32660, 107 counts off centre, not at the centre value.
- The aft leg passes continuously through 20765 → 31789, all of which is inside
  the ±39% band that would have been dead.

## Where does the Windows deadzone come from?

The user observes a large deadzone in the Windows Game Controllers utility with
the same base and the same stored value. Since the firmware demonstrably is not
applying it, the deadzone there is being applied above the device — by MOZA's
Windows driver, or by Windows' own joystick calibration. Either way it is
host-side, and a Linux tool cannot deliver it by writing this setting.

**Unless** the value is the problem: 39 exceeds Cockpit's stated maximum of 25,
and the firmware may reject out-of-range values at apply time while still storing
them. That is untested and it is the one remaining question.

## The discriminating test

Set the Y deadzone to **20%** — inside Cockpit's range — and sweep once more.

- A gap appears around centre → firmware applies in-range deadzones and rejects
  out-of-range ones. `ui_range` becomes a constraint we enforce.
- No gap → deadzone is host-side and cannot be delivered from Linux by this
  setting. tux-ffb should either say so plainly in the UI or implement deadzone
  itself in the telemetry layer.

## Verification status

- [x] response curve confirmed applied in firmware, predicted vs observed within 0.2%
- [x] fold reproduces in both sweep directions at the same output values
- [x] 39% deadzone confirmed absent from the output, by two independent arguments
- [x] centre plateau explained as a hand pause
- [ ] whether an in-range (≤25%) deadzone is applied
- [ ] saturation never verified — it was reset to 100 before this sweep
- [ ] interpolation between control points: spline or linear
- [ ] no writes attempted

**Confidence**: `observed` for the curve being applied and for the 39% deadzone
being absent.
