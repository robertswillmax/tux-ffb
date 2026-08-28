# 09 — Open questions

Research deliberately deferred so building could start. None of it blocks the
CLI or the GUI; all of it makes the tool more complete.

## 1. Finish the parameter sweep

**The largest gap.** Of 238 readable addresses, 25 have confirmed semantics. The
rest are mapped but unnamed.

Method is established and fast — set many controls to distinct marker values in
one Cockpit session, capture, diff. Sixteen settings were identified in a single
pass that way. Values currently unused anywhere in the address space make the
safest markers.

Still unnamed and worth attacking first:

- **147, 148** — six banks each of curve-shaped data. The largest single unknown.
- **171, 172, 173, 180–183, 196, 197, 199, 209, 210** — parameterised, unmapped.
- Most plain ids outside the ranges already identified.

## 2. Booleans and enums — DONE by capture, not by pattern

Eleven controls were located in a single VM trip by capturing Cockpit writing
them, rather than the four binary-pattern passes proposed below. Each write frame
names its own command id, so nothing was inferred. See
[`captures/2026-08-28-ab9-toggle-capture.md`](captures/2026-08-28-ab9-toggle-capture.md).

**The binary-pattern method would not have worked**, and the reason matters: it
can only identify addresses that are already enumerable, and the trim block turned
out to live inside `id 225` as nested sub-indices — an address we had put in the
VOLATILE set and stopped reading. Capture does not care where a setting lives.

Superseded plan, kept for the reasoning:

### Binary pattern (not used)

Toggling *n* controls one at a time costs *n* round trips; a binary pattern costs
⌈log₂ n⌉. Give each control an index, then in pass *k* toggle every control whose
index has bit *k* set. An id changes in pass *k* iff its control was toggled in
pass *k*, so each id's change pattern across passes spells its control's index.

Fourteen known low-cardinality controls → **4 passes**. A fifth pass toggling
everything acts as a checksum: any id that fails to change is suspect.

Controls to cover: disable force feedback; FFB mode (DirectInput / telemetry /
integrated); temperature control mode; adaptive centering on/off; hands-off
detection; trim follow (none/full/custom); follow options (light/heavy/custom);
trim following; autopilot following; hardware trim mode; trim mode; base force
model (flight base / shifter); grip removal protection; extend travel range.

## 3. Parameter-space write path

Group 14 `cmd 0` reads the parameter store. No write sub-command is known.

**Do not search for it by trying sub-command numbers.** Probing blind write
commands against motor calibration data is what destroyed the cogging calibration
on 2026-08-28. The correct method is to capture Cockpit performing a *restore*,
exactly as its calibration trigger was captured.

Finding it would complete backup/restore. It is lower value than it looks, since
calibration can simply be re-run in 53 s and each run is as good as the last.

## 4. Grip catalogue names

34 catalogue entries; 3 known (0 = MH16, 17 = VIRPIL Alpha Prime, 32 = WinWing
WW-16). The decode-mode grouping is fully mapped, so this is pure labelling: step
through Cockpit's dropdown recording name → value.

## 5. Physical effect of the settings — DONE, except the Z axis

**22 of 25 settings now have their effect confirmed on hardware.** The remaining
three (`curve-points-z`, `curve-ends-z`, `invert-z`) cannot be tested here: the
Z-axis module is not fitted, so there is no force to feel and no axis to watch.
They stay `unverified` until someone has the hardware.

Two lessons from doing it, both worth keeping:

**Some effects are invisible to axis measurement.** Adaptive centering showed
*identical* settle statistics at strength 0, 20 and 90 (mean error ~100 counts in
all three), yet at 90 it produces an unmistakable elevated breakout force. The
reported axis position does not encode force, so an assist can work perfectly and
leave no trace in evdev. The same limitation applies to input saturation, where
the output reaches maximum before the physical limit — invisible without knowing
where the user's hand is.

**A force's signature identifies it.** Spring, damper, friction and inertia feel
genuinely different — scaling with displacement, with speed, flat across speeds,
and resisting changes in motion respectively. That they each matched their
expected signature is stronger evidence than any one of them feeling "like
something happened", because mislabelled parameters would have produced
mismatches.

## 6. The packed deadzone word — parked, not solved

Both axes write the same parameter, `Table 2 Param 60`, one byte each:
`deadzone-x` sets byte 3, `deadzone-y` sets byte 0. So the word holds four
lanes, presumably X and Y in each direction.

Two observations that do not reconcile, and are recorded rather than explained:

- `deadzone-y = 7` set **two** bytes (`0x07070202`), while `deadzone-y = 4` later
  set **one** (`0x04020203`). Same command, different reach.
- MOZA Cockpit does **not** allow unlinking + from −, so the vendor never
  exposes the lanes individually either.

Since Cockpit cannot address them separately, a four-field UI would be four boxes
that always move together. tux-ffb therefore exposes one deadzone and one
saturation per axis, which is the honest shape of what can be controlled. If the
lane layout is ever needed, the cheap experiment is to read the packed word while
varying one axis and watching which bytes move — not to probe `151 bank 0 slot 0`
blind.

## 7. Smaller loose ends

- `id 126` never answers or rejects — the only address of its kind left.
- 61 silent addresses (slots 14/15 on every parameterised id, plus scattered
  bank 0–2 slots). Regular enough to be structural, unknown, not probed.
- `id 195` — function unknown; ruled out as a validity flag. Stays `forbidden`.
- Which slot of each `roll-a`/`roll-b` pair is `+` vs `−`. Needs one unlinked
  setting to tell them apart.
- Whether the three slots on ids 196/209/210 are roll/pitch/Z.
- AB6: nothing known. No hardware.
