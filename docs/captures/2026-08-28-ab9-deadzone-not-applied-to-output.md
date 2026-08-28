# 2026-08-28 — The stored deadzone is not applied to the HID output

> **⚠ RETRACTED.** The conclusion here is **wrong**: the deadzone *is* applied.
> See [`2026-08-28-ab9-deadzone-IS-applied.md`](2026-08-28-ab9-deadzone-IS-applied.md).

> **⚠ RIGHT CONCLUSION, WRONG METHOD.** The finding below — that the 39% deadzone
> is absent from the output — was later confirmed properly. But the reasoning
> here is invalid: it analysed the *set* of distinct output values, and neither a
> rescaling deadzone nor a remapping curve leaves a gap there. The same method
> would have concluded the response curve wasn't applied either, and **it is**.
> See [`2026-08-28-ab9-curve-is-applied-deadzone-is-not.md`](2026-08-28-ab9-curve-is-applied-deadzone-is-not.md).

**Setup**

- MOZA AB9, MH16 fitted. Y deadzone **stored as 39** (confirmed by three
  readbacks of `(152, bank 0, slot 1)` immediately before this test).
- User swept the Y axis slowly through centre, full travel both directions.
- Captured 30 s of raw `EV_ABS` events from the AB9's evdev node.

## Result: no deadzone in the output

```
ABS_Y samples: 7988        observed range: 258 .. 65329   (7559 distinct values)
samples exactly at centre (32767): 1  (0.0%)

nearest distinct value below centre: 32751   gap 16 counts
nearest distinct value above centre: 32774   gap  7 counts

largest gap anywhere in the sweep: 83 counts (0.1% of full travel)
```

A 39% deadzone would produce a flat region or discontinuity of roughly **25,000
counts** around centre. The largest gap found anywhere in the entire sweep is 83
counts, which is sensor resolution. The axis is smooth and continuous straight
through centre.

**The base stores the deadzone and does not apply it to its HID output.**

## What this does and does not mean

It does **not** mean the settings are inert. Axis calibration — range and centre —
is known to be firmware-applied on this base: it reports full 0–65535 travel
centred within ~2% on Linux with no MOZA software present. That still holds.

It means **deadzone specifically is not applied by the firmware to the axis
report**, at least not in the current device state. Three candidate explanations,
in rough order of likelihood:

1. **The firmware clamps or ignores out-of-range values at apply time.** 39
   exceeds Cockpit's stated maximum of 25. The value is stored unvalidated but
   may be rejected when used — which would make MOZA's UI limit meaningful after
   all, just enforced at a different layer than the write.
2. **Deadzone is applied by MOZA's Windows driver, not the firmware.** In that
   case it is a host-side setting that merely lives in the base's memory, and it
   would never affect a Linux game regardless of what we write.
3. **It needs a commit, a mode change, or a power cycle** that Cockpit performs
   separately and we have not replicated.

## Why this matters more than the finding itself

This is the first evidence that **a setting can be stored and read back
faithfully and still have no effect.** Read-back verification — the mechanism
[`07-safety.md`](../07-safety.md) leans on to confirm a write worked — is
therefore *necessary but not sufficient*. It proves the base accepted the value,
not that the value does anything.

Every setting tux-ffb exposes needs its effect verified against observable
behaviour — evdev output, or measurable force — not merely against a read-back.
Settings whose effect has never been observed must be marked as such, because
shipping a deadzone slider that silently does nothing is worse than not shipping
one.

## The discriminating test

Set the Y deadzone to a value **inside** Cockpit's range — 20% — and sweep again.

- A flat region appears at ±20% → explanation 1. The firmware applies in-range
  values and rejects out-of-range ones. `ui_range` becomes a real constraint to
  enforce, not merely a default.
- Still no flat region → explanation 2 or 3, and deadzone is not something a
  Linux tool can deliver by writing this setting. That would be worth knowing
  early, since it likely generalises to its neighbours (saturation, curves).

Saturation is the obvious follow-up either way: it was set to 75 earlier and its
effect was never checked. A 75% saturation should visibly compress the reported
travel, which is easy to measure with the same sweep.

## Verification status

- [x] deadzone value 39 confirmed stored, three readbacks
- [x] 30 s full-travel sweep captured, 7988 samples
- [x] no deadzone present in the evdev output — measured, not inferred
- [ ] which of the three explanations holds
- [ ] whether saturation and curves are applied to the output
- [ ] no writes attempted

**Confidence**: `observed` for the negative result.
