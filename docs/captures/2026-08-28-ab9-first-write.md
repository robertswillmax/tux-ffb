# 2026-08-28 — First write to the AB9

**The write path works.** Same addressing as reads, no surprises, no side effects.

## What was written

| | |
|---|---|
| target | `(152, bank 0, slot 1)` — Y-axis deadzone |
| before | 95 (set via Cockpit, verified by read) |
| after | **2** |
| frame | `7e 03 1f 12 98 01 02 5a` |

Chosen as the first write because the address, encoding and physical effect were
all already established, the value is one the X axis already holds, it is
trivially restorable through Cockpit if anything went wrong, and it undoes the
95% deadzone that had made the axis unusable. Backup taken first:
[`data/2026-08-28-ab9-pre-first-write-backup.json`](data/2026-08-28-ab9-pre-first-write-backup.json).

The script asserted the pre-write value was 95 and would have aborted otherwise —
a guard against writing to a misidentified address.

## Write frame format

Identical in shape to the read, with the value appended and the set group:

```
→ 7e | len | 31 | 18 | cmd_id | index | value | checksum
       03    ^Main_set    98      01      02      5a
```

`len` counts `cmd_id + index + value`. Reads use group 30 and omit the value.
So a setting is addressed the same way for reading and writing, which is what
[`02-protocol.md`](../02-protocol.md) assumed but had not verified.

## The firmware narrates its own writes

The write produced no reply frame, but this appeared on the ASCII channel:

```
[INFO]param_manage.c:340 Table 2, Param 60 Written: 33686018 0.00000
```

Three things worth having:

1. **Writes are confirmed on the log channel**, naming the internal location and
   the resulting value. That is an independent verification path — we can see
   that a write landed without relying on a read-back of the same address.
2. **Internal storage is `(Table, Param)`.** Our `(cmd_id 152, index 1)` maps to
   Table 2, Param 60. The serial command space is a façade over a parameter
   store, and the mapping is discoverable from these log lines.
3. **The stored word is `33686018` = `0x02020202`** — the single byte written,
   replicated four times. The param is 32 bits and a one-byte write fills all
   four lanes.

That replication is very likely why deadzone is described as applying to "both
directions": one written byte populates several sub-fields. It did **not** bleed
into other settings — X's deadzone and both saturations were unchanged — so the
four lanes belong to this parameter alone. Unconfirmed beyond that.

## Side effects: none, once two status registers are accounted for

A full 238-address diff across the write showed three changes:

| id | before → after | verdict |
|---|---|---|
| 152 bank 0 slot 1 | 95 → 2 | **the intended write** |
| 198 | 768 → 256 | status register — reverted to 768 by itself later |
| 15 | 214272 → 66088 | status register — later 197120, changes on its own |

Three consecutive snapshots with no writes confirmed both are stable across a
short window but differ across longer ones: transient state, not settings. Id 198
flipping to 256 exactly at the write and back afterwards reads as a
write-in-progress or EEPROM-busy flag.

Both added to `snapshot.py`'s `VOLATILE` set, which now holds
`{15, 114, 184, 185, 198, 215, 216, 225}`.

Crucially, **X's deadzone and both axes' saturation were untouched.** The write
was surgical.

## Physical effect confirmed

The user verified in the Windows Game Controllers utility that the dead band has
collapsed from the near-full-travel 95% back to a barely-perceptible one,
consistent with the written value of 2.

**The round trip is closed, on four independent signals:**

1. the write frame was accepted,
2. the firmware logged `Table 2, Param 60 Written`,
3. the read-back returns 2,
4. the hardware behaves accordingly.

That is the standard [`07-safety.md`](../07-safety.md) asks for — effect
observed, not merely stored — and it is the first setting on this device to meet
it end to end from Linux.

## Verification status

- [x] write path confirmed: group 31, `cmd_id + index + value`
- [x] read-back matches the written value
- [x] firmware log independently confirms the write and names the internal location
- [x] full-address diff shows no side effects on any setting
- [x] backup captured before writing
- [x] physical effect of the new value, confirmed on the hardware
- [ ] `(cmd_id, index)` → `(Table, Param)` mapping, harvestable from write logs
- [ ] what the four replicated lanes of a 32-bit param mean

**Confidence**: `observed` for the write path, the frame format, and the absence
of side effects.
