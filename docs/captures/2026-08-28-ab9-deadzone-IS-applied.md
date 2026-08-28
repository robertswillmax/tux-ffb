# 2026-08-28 — Correction: the deadzone IS applied in firmware

**This supersedes two previous notes.** Both concluded the deadzone was absent
from the HID output. Both were wrong, for different reasons, and the reasons are
worth more than the conclusion.

## Ground truth

The user swept **continuously**, pausing only at the fore and aft mechanical
stops, and states with certainty that the stick was moving throughout the centre
portion. That is direct knowledge of the input, which no amount of output
analysis can override.

## The evidence, re-read

Inside the continuous fore→aft leg (t=2.61–7.05, 4.44 s, output 153 → 65087):

```
t=4.25   output frozen at 32660 for 1.37s   then resumes at 32700
```

Slope at 0.15 s resolution:

```
approaching:  34533, 29900, 30607, 26287, 26340, 29247 c/s   -> 0
leaving:      0 -> 34700, 34020 c/s
```

Constant ~30,000 counts/s into an abrupt stop, 1.37 s of flat during continuous
motion, then an abrupt resumption. **That is a hard-clamped deadzone.**

Width, assuming uniform hand speed across the leg: the flat occupies 30.8% of the
traverse, i.e. **±30.8% of half-travel**, against a stored value of **39**. The
same order, and the gap is well within the error of the uniform-speed assumption
— the user was visibly slower at the start of the leg, which inflates the
denominator and biases the estimate low.

The clamp value is 32660, 107 counts below centre — a small centre offset.

## Why each earlier argument failed

### 1. "No gap at centre, so no deadzone"

A deadzone that **clamps and then rescales** produces a *flat region*, not a gap:
output holds at centre through the dead band, then ramps smoothly from centre
once outside it. The trace shows exactly this — flat at 32660, resuming at 32700,
just 40 counts apart. There was never going to be a gap. This is the **third**
time in this project that a chosen signature could not distinguish the hypotheses
being tested.

### 2. "The curve fold lands where a no-deadzone model predicts"

This one was subtly wrong and I leaned on it hardest.

The fold's **output** values are set by the stored curve outputs — slots 3 and 4
hold 40 and 29, giving 45874 and 42269 — **regardless of how physical position
maps onto curve input**. A deadzone changes *where along the stick's travel* the
fold occurs; it does not change *what output value* it occurs at. So matching the
predicted output values to 0.2% confirms the curve is applied and says **nothing
whatsoever** about the deadzone. I used a measurement that is invariant under the
hypothesis as though it discriminated it.

### 3. "The plateau is a hand pause"

The plateau was the one piece of evidence pointing at a deadzone, and it was
explained away with a plausible story — gradual deceleration — that turned out to
be a binning artefact. The honest move was to flag it as ambiguous and ask the
person holding the stick, who knew the answer.

## Standing conclusion

**Both the response curve and the deadzone are applied by the AB9's firmware.**
They work on Linux with no MOZA software present. Everything the earlier notes
said about the curve stands; everything they said about the deadzone is retracted.

This is the best possible outcome for the project: axis configuration is real,
firmware-side, and reachable from Linux by writing these settings.

The 39% value was also honoured despite exceeding Cockpit's stated maximum of 25,
which means the UI clamp is display-only in *effect* as well as in storage — the
firmware neither rejects nor ignores the out-of-range value.

## Physical confirmation at 95%

The user set the Y deadzone to **95** — Cockpit again clamped its display to 25 —
and swept the axis. Observed: **no output movement at all until very near the
mechanical stops**, then smooth motion over the remaining sliver of travel.

That settles it beyond any question of measurement technique:

- The deadzone is applied by firmware, and applied *proportionally* — a much
  larger stored value produces a much larger dead band.
- The firmware honours values far outside Cockpit's stated 0–25 range. 95 was
  stored **and acted upon**. Cockpit's clamp constrains neither storage nor
  behaviour; it is purely cosmetic.
- Outside the dead band the axis moves smoothly rather than jumping, confirming
  the clamp-then-rescale shape inferred from the 39% trace.

### On the exact scaling

At 39 the flat region measured ~31% of full travel under a uniform-hand-speed
assumption. Whether the residual is a real scale factor or just error in that
assumption is still unresolved, and a 95% sweep does not settle it — with only
~5% of travel left active, the measurement is dominated by hand-speed variation
through the dead band.

It is also not urgent. The stored value equals the number typed into Cockpit
(39 → 39, 95 → 95), so tux-ffb can present the same figure a user already
recognises. The precise physical mapping is a labelling refinement, not a
blocker, and a constant-speed sweep at a mid-range value will pin it down when
it matters.

## Methodological note

Three failures in one investigation, all the same shape: **a measurement that
cannot distinguish the hypotheses under test**, presented with confidence because
it produced a clean-looking result. Distinct-value sets could not see a rescaling
deadzone; 0.3 s bins could not see an abrupt edge; fold output values are
invariant under the deadzone entirely.

The check that would have caught all three: *before* running an analysis, ask
what the data would look like **if the opposite were true** — and if the answer
is "the same", the analysis is not evidence. That belongs in
[`06-protocol-acquisition.md`](../06-protocol-acquisition.md) next to the
cross-validation rules.

## Verification status

- [x] deadzone confirmed applied, hard clamp, abrupt edges at 0.15 s resolution
- [x] width consistent in magnitude with the stored value of 39
- [x] out-of-range values confirmed honoured by firmware, not merely stored (39 and 95)
- [x] curve confirmed applied (unchanged from the previous note)
- [x] deadzone confirmed proportional, and applied far outside Cockpit's range (95%)
- [ ] exact physical scaling of the stored value — deferred, not a blocker
- [ ] saturation still never verified
- [ ] no writes attempted

**Confidence**: `observed` for both settings being applied.
