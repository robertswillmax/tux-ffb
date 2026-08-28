# 2026-08-28 — id 92 is the grip type, and it is a selection not a detection

**Test**

The grip dropdown in Cockpit was changed to **"WW-16"** (WinWing's F-16 grip)
**without physically mounting one**. The MH16 remained fitted.

## Result

```
id 92:  0  ->  32
```

Three grip states, three distinct values:

| Cockpit dropdown | physically fitted | id 92 |
|---|---|---|
| MOZA MH16 | yes | **0** |
| VIRPIL Alpha Prime | yes | **17** |
| WinWing WW-16 | **no** | **32** |

**`id 92` is the grip type**, a single-byte plain getter. Confirmed across three
values, one of which was set with no matching hardware attached.

## It is a selection, not a detection

The base accepted a grip type for hardware that is not connected. Combined with
the earlier finding that its heartbeat reports `device connected: stick_reg`
regardless of which grip is fitted, the picture is consistent: **the AB9 does not
identify the attached grip at all.** It stores whatever the user told it.

This closes out the open question from
[`03-device-model.md`](../03-device-model.md), which listed three possible grip
architectures. The answer is the third-simplest and the most convenient for us:
the grip is neither a bus device nor auto-detected, so grip support is a matter
of a stored enum plus our own profile data — no protocol work required.

It also means **tux-ffb can be straightforwardly better than Cockpit here.** The
base is indifferent to what is actually plugged in; all the intelligence lives in
the host software. A grip profile keyed to this enum can supply correct button
names, hat modelling and shift layers for grips MOZA's own tool merely lists.

## The value spacing is not sequential

0, 17, 32 — so this is a catalogue identifier rather than a dropdown index.
Enumerating the remaining entries requires stepping through Cockpit's dropdown
and recording each value; the numbers cannot be guessed.

## Also visible in this capture: Cockpit overwrote a tux-ffb write

The Y deadzone written by tux-ffb (7) is back to 2, and the Z-axis curve,
Z invert and adaptive-centering markers all reverted to defaults. This is the
same connect-time profile push seen throughout, now observed overwriting **our**
write rather than Cockpit's own earlier values.

That is expected and harmless — writes survive power cycles, they just do not
survive Cockpit. The user-facing rule stands: configure on Linux, and opening
Cockpit afterwards will undo it.

## Verification status

- [x] id 92 confirmed as grip type across three values
- [x] confirmed to be a stored selection, accepted with no matching hardware
- [x] grip architecture question in 03-device-model.md resolved
- [ ] the rest of the grip catalogue — needs a pass through Cockpit's dropdown
- [ ] what, if anything, the base does differently per grip type

**Confidence**: `observed`.
