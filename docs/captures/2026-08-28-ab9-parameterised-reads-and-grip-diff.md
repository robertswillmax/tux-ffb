# 2026-08-28 — Parameterised reads, and the MH16 ↔ Alpha Prime diff

**Setup**

- MOZA AB9 on the host. Two clean scans with the corrected scanner: **MH16
  fitted and selected**, and **VIRPIL Alpha Prime fitted and selected** (each
  set in MOZA Cockpit, base then returned to the host).
- Data: [`data/2026-08-28-ab9-g30-mh16-robust.json`](data/2026-08-28-ab9-g30-mh16-robust.json),
  [`data/2026-08-28-ab9-g30-alphaprime-robust.json`](data/2026-08-28-ab9-g30-alphaprime-robust.json),
  [`data/2026-08-28-ab9-g30-classified.json`](data/2026-08-28-ab9-g30-classified.json)
- Tools: [`tools/cmdscan.py`](../../tools/cmdscan.py), [`tools/classify.py`](../../tools/classify.py)

## Finding 1 — read commands come in two kinds

Not every get takes an empty request. **25 of them require an index parameter.**
Sent without one, the firmware reads a stale byte as the parameter and answers
with junk, while saying so:

```
→ 7e 01 1e 12 cd 3b                          (id 205, no parameter)
← 7e 03 9e 21 cd 5e 00 78                    (junk value 0x5e00)
← [WARN]steer_serial_cmd.c:58 unexpected parameter at line:779
← [WARN]steer_serial_cmd_index1.c:1888 unexpect cmd_num: 94
```

`94` is `0x5e` — the stale byte, echoed back as the parameter it was mistaken
for. That single byte is the source of every phantom value in the previous two
sessions.

### Supplying the parameter works

```
→ 7e 02 1e 12 cd 00 3c        (id 205, index 0)   ← 7e .. cd 00 64   value 100
→ 7e 02 1e 12 cd 01 3d        (id 205, index 1)   ← 7e .. cd 01 00   + WARN
→ 7e 02 1e 12 cd 02 3e        (id 205, index 2)   ← 7e .. cd 02 64   value 100
→ 7e 02 1e 12 cd 03 3f        (id 205, index 3)   ← 7e .. cd 03 00   + WARN
```

**Response payload for a parameterised read is `<cmd_id> <index> <value>`** — the
index is echoed alongside the command id. Indices 0 and 2 answer cleanly with
100; 1 and 3 warn and return 0. Two valid slots, which is suggestive on a
two-axis base, but the indexing is not yet understood and should not be assumed
to be "axis 0 / axis 1".

This is the unlock for the settings that matter. Per-axis range, curve and limit
values almost certainly live behind these indexed getters, which is why the
plain sweep found so much that reads 0 or 100 and so little that looks like real
per-axis configuration.

### The partition

| class | count | meaning |
|---|---|---|
| rejected (`unexpect cmd_index`) | 163 | id does not exist |
| **plain getters** | **64** | value trustworthy from an empty request |
| **parameterised getters** | **25** | require an index; ids 147–152, 171–173, 180–183, 196, 197, 199, 205, 206, 209, 210, 218–221, 225 |
| no reply, not rejected | 4 | ids 15, 126, 194, 195 |

**Open discrepancy:** the polling scanner reports ~123 ids returning data, while
this fixed-window classifier reports 89 (64 + 25). The ~34 ids in the gap
(128–146, 154–161, 170, 179, 187–191, 200, 202, 204, 223) appear to return
*both* a data frame and a rejection message, and the two tools disagree on which
to believe because they check in a different order. Unresolved; those ids are
excluded from every conclusion below.

## Finding 2 — what changes when you change grips

Diffed over **plain getters only** (parameterised ids excluded as junk, live
telemetry ids 184/185/215/216 excluded):

**53 of 60 comparable settings are identical.** Seven differ:

| id | MH16 | Alpha Prime | reading |
|---|---|---|---|
| **92** | 0 | **17** (`0x11`) | **Strongest grip-type candidate.** A single byte, zero for the MOZA grip, 17 for the VIRPIL one. Stable across three passes and 15 minutes in both sessions. |
| 163 | 5823 | 5845 | \\ |
| 164 | 3746 | 3739 | > Five of six shift slightly. Calibration constants — plausibly re-measured |
| 165 | 1669 | 1633 | > against a different grip mass and balance. |
| 166 | 6287 | 6330 | / |
| 168 | 2141 | 2099 | / |
| 167 | 4214 | 4214 | **unchanged** — the odd one out of the 163–168 block |
| 114 | `5e 00` | `00 00` | **Suspect.** Holds the same `0x5e` byte as the stale-parameter artifact. Verified *not* a last-command register (it does not move when other commands are sent), and stable across many reads with the MH16 — but it read `00 00` under the corrected method with the Alpha Prime and `5e 00` under the broken one. Needs re-confirming on the next Alpha fit before it counts. |

### Control

Re-reading all seven ids three times, 15 minutes after the MH16 scan with the
grip untouched: **every one identical to the scan.** So these are stored state
that differs by grip, not drift. That control is what makes the table above
worth anything.

## Finding 3 — the heartbeat does not identify the grip

With the Alpha Prime fitted *and* selected, the base still broadcasts `device
connected: stick_reg`, unchanged from the MH16. `stick_reg` means "a stick is
registered", not which one. Grip detection has to come from a setting — id 92
being the candidate.

## What this means for tux-ffb

- **`core/` must model parameterised reads as first-class.** A setting is
  `(command_id, index)`, not `command_id`. The command table schema in
  [`02-protocol.md`](../02-protocol.md) needs an `index` dimension.
- **Never send a read without its parameter.** It doesn't fail — it returns a
  plausible-looking wrong number. That is the worst possible failure mode for a
  config tool, and it is exactly what burned two sessions here.
- The grip-type setting looks like a small enum, which supports the
  [`03-device-model.md`](../03-device-model.md) plan of shipping grip profiles
  keyed to it.

## Verification status

- [x] parameterised read format confirmed, request and response
- [x] command space partitioned
- [x] grip diff over trustworthy ids, with a same-grip control
- [ ] id 92 = grip type — strong candidate, **not confirmed**; needs a third grip
      or a Cockpit cross-check to prove the mapping
- [ ] id 114 — needs re-confirming on the next Alpha Prime fit
- [ ] the ~34 disputed ids
- [ ] no writes attempted

**Confidence**: `observed` for the read format and the partition. Grip mapping:
`inferred`.
