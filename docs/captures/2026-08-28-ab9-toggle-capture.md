# 2026-08-28 — Bools and enums, captured from Cockpit

**Method**

Rather than infer addresses by toggling in binary patterns across four VM trips,
Cockpit was captured writing them. One trip. Each write frame names its own
command id, so nothing is inferred at all. The user toggled each control there
and back, giving a matched pair per setting.

## Results

| Cockpit control | address | values |
|---|---|---|
| Disable force feedback | **id 225, idx 23** | 1 = FFB on, 0 = disabled |
| Force feedback mode | **id 133** | **0 = telemetry, 1 = DirectInput, 2 = integrated** |
| Temperature control mode | **id 192** | 1 = conservative, 2 = aggressive |
| Hands-off detection | **id 207** | 0 = off |
| Trim follow mode | **id 225, idx 14** | 0 = no follow |
| Trim follow ratio | **id 225, idx 15** | per-axis sub-slot; 100 → 200 for full follow |
| Trim following | **id 225, idx 1** | |
| Autopilot following | **id 225, idx 6** | |
| Hardware trim mode | **id 195** | |
| Trim mode | **id 203** (with **id 186**) | DirectInput / hardware |
| Adaptive centering on/off | **id 208** | |
| "Follow options" preset | **id 225**, many idx | writes a block of ~85 values |

The FFB-mode encoding is confirmed twice: the user's correction at the end of
the run (telemetry → integrated → DirectInput) produced exactly `0, 2, 1`.

## The finding that matters: ids 15 and 225 are structured sub-spaces

This is why the trim settings could not be found earlier.

`id 225` is not a single value. Writes to it carry a **sub-index and then a
payload**, and the capture shows at least eighteen distinct sub-indices — 1, 3,
6, 9, 10, 11, 14, 15, 16, 17, 18, 21, 23, 33, 35, 36, 37, 39 — several of which
take a further sub-slot:

```
7e 04 1f 12 e1 0f 00 64 14      id 225, idx 0x0f, sub 0x00, value 0x64
7e 05 1f 12 e1 11 10 02 28      id 225, idx 0x11, sub 0x10, index 2, value 0x28
```

`id 15` behaves the same way, with indices 0, 1, 4, 128, 129, 132 and multi-byte
payloads.

**Both were in `snapshot.py`'s VOLATILE set**, dismissed as noise because a plain
read returns a value that changes. They are not noise — they are nested address
spaces, and the entire trim block lives inside `225`. The earlier conclusion that
"the trim settings are not in the mapped address space" was right about the
manifest and wrong about the device: they were behind an id we had explicitly
stopped looking at.

## Correction: id 195 is hardware trim mode

`id 195` was marked **forbidden** after the self-identification incident, on the
theory that it was a calibration-validity flag and that writing it zero had wiped
the cogging calibration. The capture shows Cockpit writing it to toggle **hardware
trim mode**, plainly and reversibly.

So the incident's probable-cause story is wrong twice over: 195 is an ordinary
setting, and the calibration damage almost certainly came from the motor-state
writes to 193 or 222. That was already flagged as uncertain after the calibration
run showed 195 unchanged across a successful calibration; this settles it.

`195` moves from `forbidden` to a normal setting. `193` and `222` stay forbidden.

## Also visible

- **`id 147`/`148` are written across multiple banks** — indices 0x32–0x36 (bank
  3) and 0x52–0x56 (bank 5) — carrying `14 28 3c 50 64`, i.e. 20/40/60/80/100.
  So the six banks found by discovery really do hold curve data, and Cockpit
  writes several of them on connect.
- The connect-time push is **131 writes**, which is the mechanism behind every
  "my markers reverted" observation in this project.

## Verification status

- [x] eleven controls located, each by its own write frame
- [x] FFB mode encoding confirmed twice
- [x] ids 15 and 225 identified as nested sub-spaces
- [x] id 195 identified as hardware trim mode, not a calibration flag
- [ ] the sub-index layout of 225 — needs enumerating now that it is known to exist
- [ ] grip removal protection and extend travel range — no writes seen; either
      not toggled or not firmware-side

**Confidence**: `observed`. Every address here came from a captured write.
