# 2026-08-28 — Force-sensing mode settings

**Setup**

The base was switched from FFB mode to **force-sensing mode**, and its settings
given markers: max distance 3, force saturation pitch 27 / roll 28, deadzone 9,
axis rotation 74. "Max output feedback" was left off.

## Located

| control | address | value |
|---|---|---|
| Max distance | **id 212** | 3 |
| Axis rotation | **id 225, idx 34** | 74 |
| Deadzone (force-sensing) | **id 225, idx 35, all subs** | 9 |
| Force saturation — roll | **id 225, idx 36, sub 0x00** (and 0x10) | 28 |
| Force saturation — pitch | **id 225, idx 36, sub 0x01** (and 0x11) | 27 |

**The sub-selector is `bank << 4 | slot`, the same encoding used elsewhere on
this device.** Sub `0x00` and `0x10` are slot 0 of banks 0 and 1 and both hold
the roll marker; `0x01` and `0x11` hold pitch. So slot 0 = roll, slot 1 = pitch
for this entry.

Slots 2–15 of each bank also return the pitch value. Given that two-level reads
on this id were shown to be access-dependent, the likely explanation is that
unimplemented sub-slots echo stale data rather than holding anything. **Only
slots 0 and 1 should be trusted**, and reading a slot proves nothing about
whether it exists.

"Max output feedback" was not found — it was left off, so it reads 0 and is
indistinguishable from every other zero in the space.

## Switching mode zeroed most of the FFB configuration

Thirty-odd settings went to 0 across the mode change, without being individually
touched: per-axis intensity and torque, damper/inertia/friction gains, adaptive
centering strength and range, trim follow rate, and the spring/inertia/friction
masters moved too.

That is consistent with force-sensing being a different operating mode rather
than a variation of FFB mode — the base is not producing force feedback, so the
FFB parameters are cleared.

## The mode flag, settled

`225 idx 33` **is** the base operating mode, and the firmware says so on write:

```
write 0  ->  [INFO]steer.c:779 force feedback mode
write 1  ->  [INFO]steer.c:787 force sensing mode
```

Stored at `Table 7, Param 124`. Confirmed in both directions and restored to 1.

This also resolves the `id 133` question: it did **not** move during either
write, so it is not the mode selector. It is the FFB sub-mode
(DirectInput/telemetry/integrated) exactly as the toggle capture indicated, and
its earlier 2 → 0 was a separate change rather than a side effect of switching
modes.

## Consequence

A profile captured in one mode is not valid in the other. If tux-ffb ever
supports force-sensing, mode needs to be part of a profile rather than a setting
inside it — otherwise applying an FFB profile while in force-sensing mode writes
values the base is ignoring.

## Verification status

- [x] five controls located by marker value
- [x] sub-selector confirmed as `bank << 4 | slot`
- [x] mode change shown to zero the FFB configuration
- [ ] whether id 133 is FFB mode, base mode, or both
- [ ] max output feedback
- [ ] effect of any of these — none tested on hardware

**Confidence**: `observed` for the addresses. Effects untested.
