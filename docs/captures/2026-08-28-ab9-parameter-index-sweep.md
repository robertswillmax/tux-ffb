# 2026-08-28 — Parameter index sweep of the 25 parameterised getters

**Setup**

- MOZA AB9 on the host, MH16 fitted and selected, base at rest
- Read-only, group 30 (`Main_get`) throughout
- Tool: [`tools/paramsweep.py`](../../tools/paramsweep.py). Data:
  [`data/2026-08-28-ab9-param-sweep.json`](data/2026-08-28-ab9-param-sweep.json),
  [`data/2026-08-28-ab9-param-sweep-extended.json`](data/2026-08-28-ab9-param-sweep-extended.json)

## Method

For each of the 25 parameterised ids, request every index 0–31 and keep only
replies that both echo `<cmd_id> <index>` **and** arrive without a `WARN`. A
warning means the index is out of range for that command; the accompanying value
is not real. The structured ids were then re-swept to index 79.

## The index is two fields: `bank * 16 + slot`

Id 147 swept to 79 resolves into five identical banks:

```
id 147   bank 0 (idx  0-15):  1=0, 2=20, 3=40, 4=60, 5=80, 6=100
         bank 1 (idx 16-31):  1=0, 2=20, 3=40, 4=60, 5=80, 6=100
         bank 2 (idx 32-47):  1=0, 2=20, 3=40, 4=60, 5=80, 6=100
         bank 3 (idx 48-63):  1=0, 2=20, 3=40, 4=60, 5=80, 6=100
         bank 4 (idx 64-79):  1=0, 2=20, 3=40, 4=60, 5=80, 6=100
```

The index byte's **high nibble selects a bank and the low nibble selects a slot
within it.** Bank count is per-command, not global: id 147 has five, id 181 has
two, id 225 has three. So it is not simply "one bank per axis" — do not assume
that.

## Six-point curve tables

Ids **147, 148, 149, 150, 181, 182** all carry the same shape: slots 1–6 holding
`0, 20, 40, 60, 80, 100`. That is a six-point response curve, currently linear.
It matches the float curve already seen on the plain getters at ids 83–89
(20, 40, 60, 80, 100, plus 0 and 100 endpoints) — the same curve expressed twice,
once as floats and once as indexed bytes.

These are the tables a curve editor will write to.

> **Corrected 2026-08-28:** the claim that these match the float curve at ids
> 83–89, "the same curve expressed twice", is **wrong**. Changing the X-axis
> curve moved id 149 and left 83–89 untouched. The float table is something else.
> See [`2026-08-28-ab9-x-axis-curve-identified.md`](2026-08-28-ab9-x-axis-curve-identified.md).

## Full result (MH16, at rest)

| id | valid indices | values |
|---|---|---|
| 147, 148 | banks 0–4 (147), slots 1–6 | 0, 20, 40, 60, 80, 100 — linear curve |
| 149, 150 | slots 1–6 in bank 0; bank 1 missing slot 1 | 0, 20, 40, 60, 80, 100 |
| 181, 182 | banks 0–1, slots 1–6 | 0, 20, 40, 60, 80, 100 |
| 151, 152 | 1, 2 | 2, 100 |
| 171, 172 | 1, 2 | 100, 100 |
| 173, 199 | 0, 1 | 100, 100 |
| 180, 183 | 0, 1 | 1, 1 |
| 196, 209 | 0, 1, 2 | 20, 20, 20 |
| 210 | 0, 1, 2 | 10, 10, 10 |
| 197 | 0–5 | all 0 |
| 205, 206 | **0 and 2 only** | 100, 100 |
| 218, 219, 220, 221 | 0–3 | 100 ×4 |
| 225 | banks 0–2, scattered slots | heterogeneous, mixed widths |

### Two details that matter for the decoder

- **Payload width varies by index, not just by command.** Id 225 returns 1, 2
  and 4-byte values at different indices. A command-table entry therefore cannot
  carry a single `bytes:` field — width belongs to `(command_id, index)`.
- **Index ranges are sparse, not contiguous.** Ids 205 and 206 answer at index 0
  and 2 but reject index 1. Re-tested five times each: index 0 valid 5/5, index 1
  invalid 5/5. The gaps are real, not read flakes.

Every "flaky" reading from the first pass was re-tested five times and resolved
deterministically — 149/150 index 17 genuinely absent, 147 index 17 genuinely
present, 218 index 4 and 196 index 3 genuinely invalid. The sweep is accurate.

## What is still unknown

- **What a bank is.** Five banks on a two-axis base rules out the obvious
  reading. Could be curve profiles, effect channels, or sub-device slots.
- **What any of these settings mean.** Everything here is shape, not semantics.
  A table of sixes and hundreds is not a configurator.
- Whether writes use the same `(command_id, index)` addressing on group 31.
  Almost certainly, but unverified, and it will stay unverified until a capture
  or a read-back confirms it.

## Consequence for the command table

The schema in [`02-protocol.md`](../02-protocol.md) needs an index dimension: a
setting is `(command_id, bank, slot)`, and `bytes`/`type` hang off the leaf, not
the command. Updated there.

## Verification status

- [x] index structure confirmed as bank/slot by sweeping to 79
- [x] curve tables located on six command ids
- [x] sparse index ranges confirmed by repeat testing
- [ ] bank semantics unknown
- [ ] setting semantics unknown
- [ ] no writes attempted

**Confidence**: `observed` for structure and values. Everything about meaning:
unknown, and deliberately not guessed.
