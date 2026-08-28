# 2026-08-28 — AB9 command-id enumeration (read-only, no VM)

> **⚠ SUPERSEDED IN PART.** The scanner used here had a fixed-window timing bug:
> it missed 34 command ids and produced some misaligned values. The id count
> here (91) should read **124**, and ids 184/185/215/216 are *live telemetry*,
> not stored settings. See
> [`2026-08-28-ab9-grip-swap-and-scanner-correction.md`](2026-08-28-ab9-grip-swap-and-scanner-correction.md)
> for the corrected method and results. The dispatch-structure and
> attribution-rule findings below are unaffected and still stand.

**Setup**

- MOZA AB9 `346e:1000` on the host, `/dev/ttyACM0`, 115200 8N1
- **MOZA MH16 grip attached**, and selected as the grip type in MOZA Cockpit
  during earlier Windows-side configuration
- No MOZA software running; VM shut off
- Tool: [`tools/cmdscan.py`](../../tools/cmdscan.py). Baseline data:
  [`data/2026-08-28-ab9-g30-baseline.json`](data/2026-08-28-ab9-g30-baseline.json)

## Method

Enumeration by rejection, per [`02-protocol.md`](../02-protocol.md): send a read
frame for every command id 0–255 with a zero-length payload, and classify the
response. An id that comes back as `unexpect cmd_index: N` does not exist; an id
that returns a data frame does.

## Result: 91 readable settings on group 30 / device 18

| outcome | count |
|---|---|
| data frame returned | **91** |
| rejected (`unexpect cmd_index`) | 161 |
| silent | 2 |
| async log landed in window (see attribution note) | 2 |

Replies come back as `grp=0x9e` (= 30 \| 0x80, the reply bit) and `dev=0x21`
(nibble-swapped 18), with the requested command id echoed as the first payload
byte followed by the value. Payload widths seen: 1, 2, 3, 4 and 5 bytes.

## Two dispatch layers, and their handler names

The firmware's own warnings distinguish them:

```
group 30, id 251  → [WARN]steer_serial_cmd.c:2826 unexpect cmd_index: 251
group 31, id 251  → [WARN]steer_serial_cmd.c:2844 unexpect cmd_index: 251
group 60          → [WARN]serial_cmd_pull_main.c:746 Unexpected main_cmd: 60
group 100         → [WARN]serial_cmd_pull_main.c:746 Unexpected main_cmd: 100
```

So the **group byte is a `main_cmd`**, dispatched in `serial_cmd_pull_main.c`,
which forwards to `steer_serial_cmd.c` where the **command id is a `cmd_index`**.
Groups 30 and 31 are the get/set pair for the flight base's setting space, and
they land 18 lines apart in the same source file — almost certainly adjacent
`case` arms in one switch.

Groups 60, 100 and 14 are not valid `main_cmd`s on this firmware.

**Group 40 / device 19 returned silence for all 256 ids** at payload length 0,
having returned empty replies earlier at boxflat's payload lengths. Group 40
appears to be length-sensitive, and in any case is not where the AB9 keeps its
settings. Group 30 / device 18 is the real surface.

## Notable values

Read with the base idle, MH16 attached, at rest.

| ids | value | reading |
|---|---|---|
| 83, 84, 85, 86, 87 | floats **20.0, 40.0, 60.0, 80.0, 100.0** | An evenly-spaced 5-point curve — a response curve or equaliser, currently linear |
| 88, 89 | floats **0.0, 100.0** | Curve endpoints |
| 10, 12 | 32767 (`0x7fff`) | Axis full-scale, half of 65535 |
| 215, 216 | 32765 (`0x7ffd`) | ~~Two axes' centre~~ **CORRECTED: live axis position**, jitters every read |
| 153, 169, 173, 199, 205, 206, 213, 214, 218–221 | 100 | Twelve percentage settings at max — gain, spring, damper, friction, inertia and friends |
| 163–168 | 5831, 3744, 1657, 6306, 4219, 2132 | Non-round, unique — calibration constants or stored ADC extents |
| 174 | 70 | A percentage that isn't 100 |
| 176 | 5, 196/209 | 20, 210 | 10 | Small integers — counts, indices or enums |
| 184 | 65301 (`0xff15`, or −235 signed) | Signed offset |

None of these have confirmed meanings yet. They are the search space, not the
answer.

## The grip lead: an asynchronous heartbeat

Roughly every 50 s the base broadcasts, unprompted:

```
[INFO]main_diag.c:131 Base heart beat log
sys run_time: 782s
device connected: stick_reg
```

**`device connected: stick_reg`** is the base naming what is attached to it.
That is a direct, zero-write handle on grip detection — if this string changes
when the grip type is changed in Cockpit, we can identify the fitted grip by
listening rather than by asking.

Confirmed periodic and unprompted by a 100 s passive listen with nothing sent:
2050 bytes, two heartbeats, no requests.

## Attribution warning — this cost us a wrong conclusion

The heartbeat first appeared inside the probe window for command id 17, and was
briefly recorded as *the response to id 17*. It isn't: probing 17 directly
returns `unexpect sub_cmd : 17`. The log stream is asynchronous and lands in
whatever window happens to be open.

**Rule for `core/transport.py` and the prober:** a response is only attributable
to a request if it is a data frame whose **first payload byte echoes the command
id sent**. Text arriving in the window proves nothing. The ASCII channel is a
broadcast, not a reply channel — the only exception being `unexpect
sub_cmd/cmd_index: N`, which is self-identifying because it names N.

## Writes attempted

None. Two frames were sent to group 31 (`Main_set`) with deliberately
non-existent command ids (23, then 251) purely to make the firmware name its
handler; both were rejected at the dispatcher. No group-31 frame was ever sent
with a valid command id. See [`07-safety.md`](../07-safety.md).

## Verification status

- [x] 91 readable command ids identified and their current values recorded
- [x] get/set group pair and handler names confirmed from firmware text
- [x] heartbeat confirmed periodic and unprompted
- [ ] no command id has a confirmed *meaning* yet — that's the next job
- [ ] no write attempted, so no read-back verification

**Confidence**: `observed` for the id set and current values; nothing inferred
about semantics.
