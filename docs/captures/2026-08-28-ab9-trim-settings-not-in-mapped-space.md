# 2026-08-28 — The trim settings are not in the space we have mapped

**Method**

Thirteen trim and autopilot controls were set to distinct marker values in
Cockpit — trim follow ratios 0.68/0.69, stick follow rates 3/4, follow ratios
7/8, DirectInput hardware trim follow rate 9, roll/pitch breakout strength 13/14,
breakout range 15/16, follow rates 17/18 — then the device was searched for those
values.

## Result: one hit out of thirteen

| control | value | found at |
|---|---|---|
| DirectInput hardware trim follow rate | 9 | **id 196, bank 0, slots 0–2** |
| everything else | — | **not found** |

(`15` also appears at ids 95 and 97, but those read 15 before the change. False
positive.)

## Where they are not

Four places were checked and excluded:

1. **The 238-address command manifest.** Searched for each marker as a raw
   integer, and for the ratios as both floats (`0.68`) and integer percents
   (`68`). Nothing.
2. **The raw parameter store.** All 60 real parameters read; the 29 that changed
   are the cogging calibration data from the run performed earlier, not trim.
3. **Device 19.** Never previously enumerated, so worth checking — but a
   group-30 sweep there returns the same values as device 18, including the
   boot-calibration constants at 163–168. The firmware is not treating it as a
   separate settings space.
4. **Newly-appearing ids.** Ids 194/195 only became readable once calibration
   data existed, so enabling trim might have exposed new ones. A full re-sweep of
   plain ids 0–255 found **no new ids** — the set is unchanged apart from the
   known volatile ones.

## What this means

**The device has configuration we cannot reach.** The mapped space — group 30,
device 18, plus the flat parameter store — is not all of it. That is a real
limit on what tux-ffb can currently offer, and it is better recorded than
discovered later by a user whose trim settings silently do not save into a
profile.

Candidates for where they live, none investigated:

- The **61 silent addresses** — slots 14 and 15 on every one of the 24
  parameterised ids, plus scattered bank 0–2 slots. They accept a read and
  return nothing. Their regularity across every command suggests structure.
- **Groups other than 30.** Group 6 to device 19 returns a frame, and is where
  the serial number lives. Group 67 appeared in the calibration capture.
- Parameter **tables not exposed** through the flat 16-bit index space.

## A likely explanation, and why it lowers the stakes

The user's reading, which fits the evidence better than anything above:

**Trim *follow* is a telemetry-side feature, not a firmware one.** "No follow" —
the mode used for DCS — lets the game drive the logical centre while the stick at
that logical centre reports zero. The follow modes instead move the physical
stick with the trim, so an aft-trimmed aircraft presents as a stick held back.
That is behaviour a host application drives from telemetry, not something the
base does alone.

The split in what we found supports it precisely:

| control | reachable? |
|---|---|
| **DirectInput** hardware trim follow rate | **yes** — id 196 |
| the twelve *follow-mode* parameters | no |

The DirectInput trim path is firmware-side and appears in the command space. The
follow-mode parameters do not, which is what you would expect if they are
consumed by MOZA's Windows driver rather than the base.

**This lowers the stakes considerably.** With trim follow set to "no follow",
these settings do nothing — and "no follow" is the correct mode for DCS, which is
tux-ffb's entire v1 audience. So the unreachable block is precisely the part that
does not apply to the users we are building for.

It also means these belong with [`05-ffb-telemetry.md`](../05-ffb-telemetry.md)
rather than with the configurator: if tux-ffb ever implements a telemetry layer,
trim following is a behaviour it would provide itself rather than a setting it
would write.

## The reliable way to find them

Not by probing. **Capture Cockpit writing one of these settings**, exactly as the
cogging calibration command was captured: attach the base to the VM, let Cockpit
settle, start a filtered usbmon capture, change one trim value, and decode. The
write frame names its own group, device and command id, and one capture would
locate the whole block.

That method has worked every time it has been used here, and it does not risk
anything.

## Verification status

- [x] one control located: DI hardware trim follow rate at id 196
- [x] command manifest, parameter store, device 19 and new-id appearance all
      excluded
- [ ] where the remaining twelve live — needs a Cockpit write capture

**Confidence**: `observed` for the negative result.
