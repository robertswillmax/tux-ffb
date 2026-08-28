# 2026-08-28 — Y curve, saturation, and the X/Y pairing rule confirmed

**Setup**

- MOZA AB9, MH16 fitted.
- **X curve reset itself** on reconnect to Cockpit (the profile was never saved),
  so X is linear again. Reported by the user, and independently confirmed below.
- **Y curve set to an absurd shape**, then **the final point dragged well to the
  left**, which in Cockpit's UI is the saturation control.
- Data: [`data/2026-08-28-ab9-ycurve-saturation.json`](data/2026-08-28-ab9-ycurve-saturation.json)

## The pairing rule is confirmed

The hypothesis from the previous session was: consecutive command ids are (X, Y)
pairs, lower id = X, and changing **Y** should move **150 and 152** while leaving
149 and 151 alone. That is exactly what happened, and nothing else moved.

| id | index | before (linear) | after | |
|---|---|---|---|---|
| **150** | bank 1, slots 2–6 | 20, 40, 60, 80, 100 | **87, 45, 29, 75, 48** | Y curve points |
| **152** | bank 0, slot 1 | 2 | **0** | Y deadzone zeroed by the curve editor (mislabelled "curve mode" when first written) |
| **152** | bank 0, slot 2 | 100 | **75** | **Y saturation** |
| 149, 151 | — | — | unchanged | X untouched, as predicted |

A prediction was made, a single variable was changed, and the predicted ids moved
while their partners did not. **Promoted from hypothesis to observed.**

The rule: **`(X, Y)` occupy consecutive command ids, X on the lower.** That makes
147/148, 149/150, 151/152, 171/172, 181/182, 205/206, 218/219 and 220/221 axis
pairs, and explains why so many settings read identically in duplicate on a
symmetric base at rest.

## Saturation located

`id 152 bank 0 slot 2: 100 → 75`, from dragging the final curve point left. So
slot 2 of the 151/152 pair is **axis saturation**, an integer percentage. X's
saturation (id 151 slot 2) still reads 100, untouched.

That gives the 151/152 pair a shape:

```
slot 1 = deadzone     (percent)
slot 2 = saturation   (percent, 100 = none)
```

> **Corrected 2026-08-28:** slot 1 was originally written up here as a curve-mode
> enum, `2 = preset / 0 = custom`. It is the **axis deadzone in percent**. The
> untouched X axis was reading 2 because its deadzone is 2%. The 2 → 0 change on
> Y was the curve editor zeroing the deadzone, not a mode flag. See
> [`2026-08-28-ab9-deadzone-and-ui-clamping.md`](2026-08-28-ab9-deadzone-and-ui-clamping.md).

## Correction: the last curve point is not pinned

The previous note said slot 6 "stays pinned at 100". That was an artefact of the
one sample available — X's last point happened to sit at 100. Y's slot 6 now
reads **48**. Slot 6 is an ordinary editable point.

## Curve points are volatile; Cockpit's UI is not authoritative

Two things reverted and one did not, and the split is informative.

**Curve points reverted.** `id 149 bank 1` read `54, 52, 70, 65, 100` when the
non-linear X curve was live; it now reads `20, 40, 60, 80, 100` again. The
non-linear values survived a trip to the host and back, then vanished on
reconnecting to Cockpit. Two candidate explanations, not yet separated:

1. Cockpit pushes its current profile down to the base on connect, and its
   profile was still linear because it was never saved.
2. The points are session state that the base itself discards.

Explanation 1 is the more likely — the values persisted fine across a
disconnect/reconnect to the *host*, and only died when Cockpit was involved.
Distinguishing them matters: it decides whether tux-ffb must implement an
explicit save/commit step, or whether writes are simply durable.

**The curve mode did not stay custom on the base.** The user reports Cockpit
still displays X's curve type as "custom", but `id 151 slot 1` reads **2**
again — the same value it held when the curve was linear. Meanwhile `id 152
slot 1` went to 0 exactly when Y was made custom, so slot 1 really is the mode.

So **Cockpit's displayed curve type disagrees with what the base has stored.**
The UI is showing local application state, not a read-back. This is a direct
argument for the principle already in [`04-ui.md`](../04-ui.md) — *the device is
the source of truth, and every value shown is read from it* — and it is a place
where tux-ffb can be straightforwardly more correct than the vendor tool.

## Note on the "no longer answering" ids

The plain scan in this session deliberately skipped the 25 known parameterised
ids, so their absence is by construction, not a finding.

The ~34 disputed ids (128–146, 154–161, 170, 179, 187–191, 200, 202, 204, 223)
did not return a clean value here either, because this tool discards any reply
accompanied by a `WARN`. That is new evidence that they behave like the
parameterised group — they answer, but with a warning, so their bare values are
junk. Still not conclusive, still excluded from conclusions.

## Verification status

- [x] X/Y pairing rule confirmed by prediction and single-variable test
- [x] Y curve points at `(150, bank 1, slots 2–6)`
- [x] Y curve mode at `(152, bank 0, slot 1)`, saturation at `(152, bank 0, slot 2)`
- [x] "last point pinned at 100" retracted
- [x] Cockpit UI shown to disagree with stored device state
- [ ] why the curve points reverted — profile push vs session state
- [ ] curve mode enum beyond `2 = preset`, `0 = custom`
- [ ] no writes attempted

**Confidence**: `observed` for the pairing rule, the Y curve location, the mode
and saturation slots. `inferred` for the profile-push explanation.
