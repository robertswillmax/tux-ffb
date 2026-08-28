# 2026-08-28 — Deadzone located, and Cockpit's UI clamp is display-only

**Setup**

- MOZA AB9, MH16 fitted. Y-axis deadzone changed in MOZA Cockpit.
- The user **typed `39`** into the deadzone field. **Cockpit clamped the display
  to `25`**, its stated maximum, and reported 25 in the UI.

## Deadzone is `(151 | 152, bank 0, slot 1)`, plain percent

| | id | value | |
|---|---|---|---|
| X deadzone | 151 bank 0 slot 1 | **2** | untouched, and X's deadzone is 2% |
| Y deadzone | 152 bank 0 slot 1 | **39** | the typed value, not the displayed one |

Encoding is integer percent, 1:1. Confirmed stable across three readbacks.

This follows the X/Y pairing rule, with the deadzone sharing the 151/152 pair
alongside saturation at slot 2.

### Correction

The previous note labelled slot 1 "curve mode (2 = preset, 0 = custom)". **That
was wrong.** Slot 1 is the deadzone. The 2 → 0 transition seen when the Y curve
was made custom was the curve editor zeroing the axis deadzone, not a mode flag.
Corrected in
[`2026-08-28-ab9-y-curve-saturation-pairing.md`](2026-08-28-ab9-y-curve-saturation-pairing.md).

The lesson: the value `2` was read as an enum because it was small and the
neighbouring setting was a curve. It was a percentage all along, and the axis
that wasn't touched was holding the answer the whole time.

## Cockpit's range limit is a display clamp, not a write clamp

The UI clamped the field to its documented maximum of 25 **and sent 39 anyway**.
The base accepted and stored it.

This is a vendor bug, and it has three consequences for us:

1. **The device's accepted range is wider than the vendor UI's range.** MOZA's
   own limits are advisory, not enforced by firmware — at least for this setting.
2. **A configurator can legitimately offer more than Cockpit does**, which is one
   of this project's stated aims. Here is a concrete instance rather than an
   aspiration.
3. **It is untested territory.** MOZA presumably validates behaviour within 0–25.
   A 39% deadzone may be fine; it may also be a range nobody has ever exercised.

So the command table needs **two** ranges per setting, not one:

```yaml
    deadzone:
      ui_range:     [0, 25]     # what MOZA Cockpit exposes
      device_range: [0, 39]     # what the firmware has been observed to accept
      unit: percent
```

`ui_range` is the default clamp. Going beyond it is allowed but explicit — the
user is opting out of the vendor's tested envelope and should know it. Neither
range is assumed: `device_range` records only what we have actually observed
accepted, and widens as we learn more.

## Not yet confirmed

**Whether the base honours 39% in its axis output.** Storing a value and acting
on it are different things. The check is to park the stick near centre and sweep
it slowly: with a 39% deadzone, evdev `ABS_Y` should stay pinned at 32767 across
roughly ±12,800 counts of physical travel before it starts moving. It could not
be run here — the stick was resting at `ABS_Y=5188`, far outside any plausible
deadzone, so the reading says nothing either way.

## Verification status

- [x] deadzone located on both axes, encoding confirmed as integer percent
- [x] readback stable across three passes
- [x] UI clamp shown to be display-only
- [ ] whether a >25% deadzone is actually applied to axis output
- [ ] no writes attempted

**Confidence**: `observed` for the deadzone location, encoding, and the UI clamp
behaviour.
