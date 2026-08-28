# 2026-08-28 — The raw parameter space is 60 values, and they are backable-up

**Method**

Group 14 / cmd 0 reads a flat parameter store by 16-bit index, returning a 32-bit
value — discovered by watching Cockpit use it during a cogging calibration.
Surveyed indices 0–8191 read-only with [`tools/paramspace.py`](../../tools/paramspace.py),
then probed far indices to establish the bounds.

```
→ 7e 03 0e 12 00 <idx_hi> <idx_lo> <ck>
← 7e 07 8e 21 00 <idx_hi> <idx_lo> <b3 b2 b1 b0> <ck>
```

## `0x00008000` means "no such parameter"

8035 of 8095 responses were `00 00 80 00` (32768), and indices 8192, 10000,
16384, 32768, 50000 and 65535 all return the same. It is the not-implemented
default, not data. **Reading a nonexistent parameter is silent and
plausible-looking** — another case where the device answers rather than
complains, which the decoder must treat as absence.

## The real space is 60 parameters in 6 blocks

| block | count | values |
|---|---|---|
| **1–20** | 20 | 11–78, small and irregular |
| **300–320** | 21 | 0–9311 |
| **400–402** | 3 | 3813–9469 |
| **1000–1001** | 2 | 867, 2900 |
| **1900–1905** | 6 | 0/1 — booleans |
| **2000–2007** | 8 | 5–3586 |

Backed up verbatim in
[`data/2026-08-28-ab9-paramspace-backup.json`](data/2026-08-28-ab9-paramspace-backup.json).

**These are exactly the indices Cockpit read during the calibration capture** —
300–313, 400, 1000, 1900–1905, 2000–2008. The user reports Cockpit displays
"backing up" while calibrating, and this is what it is reading.

**Block 1–20 is the strongest candidate for the cogging table itself**: twenty
small irregular values is the shape of a per-angle motor correction table.
Unconfirmed until a calibration is observed changing them.

## What this means for the unrecoverable-state problem

[`07-safety.md`](../07-safety.md) records a class of state that backups cannot
protect, because the data was not reachable. **It is reachable.** Sixty values,
readable in about a second.

That is half the solution. The other half is a *write* path into this space —
group 14 sub-commands other than `cmd 0`. We have not seen one, and it will not
be found by guessing: probing write sub-commands blind against motor calibration
data is precisely the mistake that destroyed the calibration in the first place.
The correct way to find it is to capture Cockpit performing a *restore*, the same
way the calibration trigger was captured.

Until then tux-ffb can **back up** calibration state and **detect** its loss, but
must still send the user to Cockpit to restore it.

## Verification status

- [x] parameter channel confirmed, addressing and reply format
- [x] `0x00008000` confirmed as the not-implemented default
- [x] real space bounded at 60 parameters across 6 blocks
- [x] full backup captured
- [ ] which block holds the cogging table — test by diffing across a calibration
- [ ] a write path into this space — needs a Cockpit restore capture, not guesswork

**Confidence**: `observed`.
