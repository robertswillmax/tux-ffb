# 2026-08-28 — Cogging calibration performed from Linux

**The last hard dependency on Windows for this base is gone.**

## The run

```
write 194 = 0        7e 03 1f 12 c2 00 00 81
poll  194            0 → 100 over 53.2 seconds, monotonic
```

Cockpit's own run took ~52.8 s; ours took 53.2 s. Same routine, same timing, no
setup, no handshake — exactly as the capture predicted.

## Which parameters the calibration writes

Bracketing the run with parameter-space snapshots identifies the calibration data
precisely. **26 of 60 parameters changed:**

| block | changed | note |
|---|---|---|
| **300–319** | 18 of 21 | the bulk of it; 303, 304, 320 stayed 0 |
| **400–402** | 3 of 3 | |
| **1001** | 1 of 2 | 1000 unchanged |
| **2000–2003** | 4 of 8 | 2004–2007 unchanged |
| 1–20 | **0 of 20** | unchanged |
| 1900–1905 | 0 of 6 | unchanged |

**Block 1–20 is not the cogging table.** The previous note guessed it was, on the
grounds that twenty small irregular values look like a per-angle motor table. It
is not — the calibration does not touch it. A plausible shape is not evidence.

The cogging data is **300–319, 400–402, 1001, 2000–2003** — 26 values. That is
what a backup needs to preserve, and it is comfortably small.

## Correction: id 195 is not a validity flag

Recorded earlier as the calibration-validity flag, on the strength of a single
diff where it went 0 → 1 across a recalibration. **This run contradicts that:**

```
before calibration:  194 = 100,  195 = 0
after  calibration:  194 = 100,  195 = 0
```

`195` read 0 both before and after a successful calibration, and had drifted from
1 back to 0 with nothing but read-only work in between. It is not a stable
validity indicator. `194` = completion percentage still holds — confirmed twice
now, once per calibration.

This also weakens the incident's probable-cause story, which supposed that
writing `195 = 0` invalidated the calibration. If 195 does not indicate validity,
that write may not have been the culprit; the damage more likely came from the
motor-state writes to 193 or 222. Recorded as less certain rather than quietly
kept.

`195` stays `forbidden` regardless — unknown function, near motor state.

## Parameters drift between calibrations

The values are measurements, not settings: index 300 read 9311 in the backup
taken after the user's Cockpit calibration, 9228 before this run, and 9268 after.
Each calibration produces a slightly different result, which is expected for a
physical measurement and matches the behaviour of the boot-time constants at ids
163–168.

Consequence: a restored backup would be a *previous* calibration, not a
bit-identical state, and comparing two calibrations for equality is meaningless.

## What tux-ffb can now do

- **Detect** a missing or in-progress calibration (`194`).
- **Run** the calibration, with progress, in ~53 s.
- **Back up** the 26 values it produces.
- Still **cannot restore** them — that needs a write path into the parameter
  space, to be found by capturing Cockpit doing a restore, not by guesswork.

The recovery story is now: *if calibration is lost, tux-ffb regenerates it on the
spot*, which is better than restoring a stale one anyway.

## Verification status

- [x] calibration triggered and completed from Linux, 53.2 s, 0 → 100
- [x] calibration data located: 26 parameters in 4 blocks
- [x] block 1–20 ruled out as the cogging table
- [x] id 195 ruled out as a validity flag
- [x] physical confirmation: stick behaves as an unbiased stick again, verified by the user
- [ ] a parameter-space write path

**Confidence**: `observed`.
