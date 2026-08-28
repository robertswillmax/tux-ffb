# 2026-08-28 — Cogging torque IS a user calibration, and it can be destroyed

**How this came to light**

Writes made during the [self-identification incident](2026-08-28-INCIDENT-unsafe-self-identification.md)
wiped the base's **cogging torque calibration**. The symptom: with the base
powered on, the stick flopped forward under the grip's own weight instead of
behaving as a balanced, bias-free stick.

Critically, **the power-on sequence does not restore it.** The base runs its
usual startup sweep and still behaves wrongly. Recovery required the user to
run the cogging calibration explicitly from Cockpit — a button-press process,
not something that happens on boot.

## Correction to the device model

`03-device-model.md` asserted, inherited from earlier notes:

> Cogging torque is not a user calibration on this base.

**That is wrong.** It is a user calibration, it is user-initiated, and it is the
single most destructible piece of state on the device — because nothing in the
normal power cycle rebuilds it.

## Calibration status is readable at ids 194 and 195

Diffing a snapshot taken while broken against one taken after recalibration
isolates it exactly:

| id | wiped | after calibration |
|---|---|---|
| **194** | 0 | **100** |
| **195** | 0 | **1** |

Both were among the three addresses that originally *neither answered nor
rejected* a read (126, 194, 195). They answer once valid calibration data
exists. `194` reads as a completion percentage, `195` as a validity flag.

Ids 163–168 also shifted. They were previously classified as boot-time
re-measurement, which still holds, but they move with a cogging calibration too —
so they are measured values that both the boot sequence and this calibration
refresh.

## Probable cause, stated as probable

During incident recovery I wrote `id 195 = 0`, believing I was restoring it to a
pre-incident value. If `195` is the calibration-valid flag, that write is what
told the base its cogging data was invalid.

This is not proven — the same batch also disturbed `193` (`DbgBiasNotInited`) and
`222` (`Motor Stop`) — and proving it would mean deliberately wiping the
calibration again, which is not worth doing to a user's hardware.

## Consequences for tux-ffb

**1. A new safety class: destructible-and-unrecoverable.**

The existing classes in [`07-safety.md`](../07-safety.md) assume a bad write is
recoverable by restoring a backup. Cogging calibration is not: the data is not in
our readable address space, so we cannot back it up, and only the vendor tool can
regenerate it. Ids 193, 194, 195 and 222 are now `forbidden` — never written,
under any flag.

**2. A genuinely useful feature falls out of this.**

tux-ffb can **read** calibration validity (`195`) and completeness (`194`) and
tell the user plainly: *"this base has no valid cogging calibration — run it in
MOZA Cockpit."* Nothing on Linux reports that today, and the failure mode is
otherwise baffling: a stick that flops despite the base being powered and the
axes working.

That is worth surfacing on the Overview page, and it is a case where tux-ffb
diagnoses something the user would otherwise chase for hours.

**3. Calibration cannot be performed from Linux — for now.**

Whatever command triggers the calibration was not observed. It could be found by
capturing the Cockpit↔base traffic during a calibration run, which is exactly
what [`06-protocol-acquisition.md`](../06-protocol-acquisition.md) describes and
what the usbmon setup already supports. Until then, tux-ffb should detect and
report, not attempt.

## Verification status

- [x] cogging calibration confirmed as a user-initiated process, not a boot step
- [x] confirmed not restored by a power cycle
- [x] calibration status readable at ids 194 (completion) and 195 (validity)
- [x] ids 193, 194, 195, 222 marked forbidden for writes
- [ ] which write destroyed it — probable but deliberately not re-tested
- [ ] the command that triggers calibration — needs a Cockpit capture

**Confidence**: `observed` for the status addresses and the recovery path.
`inferred` for the cause.
