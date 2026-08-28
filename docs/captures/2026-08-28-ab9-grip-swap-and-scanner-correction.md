# 2026-08-28 — Grip swap (MH16 → Alpha Prime), and a scanner correction

**Setup**

- MOZA AB9 on the host, `/dev/ttyACM0`
- **VIRPIL Alpha Prime** fitted, selected and detected in MOZA Cockpit, base
  returned to the host
- Tool: [`tools/cmdscan.py`](../../tools/cmdscan.py) (rewritten, see below).
  Data: [`data/2026-08-28-ab9-g30-alphaprime-robust.json`](data/2026-08-28-ab9-g30-alphaprime-robust.json)

## Correction: the earlier scanner was wrong, and so were its results

The first scanner sent a request, slept a fixed 0.12 s, and parsed whatever had
arrived. That is wrong in two ways:

1. **Slow responses were missed entirely.** The window closed before the reply
   landed, so the id looked non-existent.
2. **Responses bled between requests.** Clearing the buffer at the start of the
   next request discarded the tail of the previous reply, leaving the parser to
   resynchronise mid-frame and occasionally produce a checksum-valid frame from
   misaligned bytes.

### What this invalidates

| Earlier claim | Corrected |
|---|---|
| **91 readable command ids** | **124** — the short window missed 34 ids (128–146, 154–161, 170, 179, 187–191, 200, 202, 204, 223) |
| ids 215/216 = "axis centre, stored" | **Live axis position.** They move every read: `7f fb`, `7f ff`, `80 02`. Not settings. |
| id 184/185 = "signed offset" | **Live telemetry**, also changing every read |
| "22 settings changed between MH16 and Alpha Prime" | **Retracted.** Nearly all were artifacts — ids 173, 199, 205, 206, 209, 210, 218–221 read exactly their baseline values under the corrected method. |

### The trap worth remembering

The bogus values **reproduced identically across three consecutive scans**, which
is why they were initially believed. The error was systematic in the method, not
random, so repetition confirmed nothing. Reproducibility is only evidence of
correctness when the repeats vary something.

What actually caught it was a **control at a different timing**: re-reading the
same ids with a 0.25 s wait returned the baseline values. Vary the method, not
just the run.

### The corrected method

```
for each id:
    drain until the line has been quiet for 60 ms, then clear
    send the read frame
    poll until a data frame arrives whose first payload byte echoes the id,
      or the firmware rejects the id by number, or 500 ms elapses
```

Early-exit on match keeps it fast; the drain removes cross-request bleed; the
echo match is the attribution rule from the enumeration note, enforced.

## Result: 124 readable ids

- **120 stable** across two runs — settings.
- **4 live** — ids 184, 185, 215, 216. 215/216 sit at ~32767 (axis centre) and
  jitter by a few counts: these are the two axis positions. 184/185 are small
  signed values that also move; candidate torque, current or velocity.
- **3 neither answer nor reject** — ids 126, 194, 195. A fourth response class:
  the dispatcher accepts the id but produces no reply. Possibly write-only, or
  long-running. Treat as unknown, do not poke.

## The grip question

**The heartbeat does not carry grip identity.** With the Alpha Prime fitted and
selected, the base still broadcasts `device connected: stick_reg`, unchanged from
the MH16. So `stick_reg` means "a stick is registered", not *which* stick. The
zero-write grip-detection idea from the previous session is dead.

**Surviving candidates for grip-dependent state**, comparing against the old
MH16 scan where its values look trustworthy:

| id | MH16 | Alpha Prime | note |
|---|---|---|---|
| **92** | 0 | **17** (`0x11`) | Best candidate for a grip-type enum — a single byte that was zero and now isn't |
| 163–168 | 5831, 3744, 1657, 6306, 4219, 2132 | 5845, 3739, 1633, 6330, 4214, 2099 | All six shifted slightly. Calibration constants re-measured with a different grip mass |
| 225 | `00 00 49` | `00 00 00` | Low byte 73 → 0 |
| 195 | `c2 00 00` | no reply | Changed response class |

**These are candidates, not findings.** The MH16 baseline was taken with the
broken scanner, so it cannot be trusted as the other half of a diff. The
comparison is only suggestive because the corrected Alpha Prime values agree with
the old baseline nearly everywhere, which implies the baseline was mostly right —
but "mostly right" is not a baseline.

## Next step

Refit the MH16 and re-scan with the corrected tool. That gives two trustworthy
halves and turns the table above into an answer. Until then, nothing here is
confirmed and nothing should be written to the base.

## Verification status

- [x] scanner corrected and validated against an independent slower-timing control
- [x] 124 ids, 120 stable, confirmed across two runs
- [x] heartbeat ruled out as a grip identifier
- [ ] grip-dependent ids — need a clean MH16 scan
- [ ] no writes attempted

**Confidence**: `observed` for the id set and current values. Grip candidates:
`inferred`, pending the MH16 re-scan.
