# 2026-08-28 — The cogging calibration command, captured

**Method**

Attached the base to the Windows VM, let Cockpit connect and settle (so its
connect-time profile push stayed out of the data), then captured usbmon on the
AB9's device number only while the user ran the cogging calibration. Decoded with
[`tools/usbcap.py`](../../tools/usbcap.py). 175k URB lines, 4743 outbound frames.

## The trigger is one frame

```
7e 03 1f 12 c2 00 00 81      SET  device 18  cmd 194  value 0x0000
```

Sent **exactly once** in the entire capture. The twelve frames preceding it are
ordinary idle polling (184, 185, 215, 216, 12, 225) — **there is no setup, no
handshake and no mode change.** Cockpit writes `id 194 = 0` and the base starts
calibrating.

## Progress is polled on the same id

```
7e 03 1e 12 c2 00 00 80      GET  device 18  cmd 194
```

Polled 220 times, returning 0 → 100:

```
t +0.4s   194 = 0        t +25.2s  194 = 45       t +43.1s  194 = 82
t +1.2s   194 = 2        t +31.6s  194 = 56       t +47.8s  194 = 90
t +11.2s  194 = 20       t +36.4s  194 = 70       t +52.8s  194 = 100
```

**Total duration ~53 seconds**, monotonically increasing, with pauses where the
routine changes phase.

So `id 194` is a dual-purpose register: **write 0 to start, read for percent
complete.** `id 195` remains the validity flag, and both only become readable
once calibration data exists.

## tux-ffb can perform this calibration

This closes the last hard dependency on Windows for the AB9. Everything needed:

```python
write(194, 0)                      # start
while read(194) < 100:             # poll ~2 Hz
    ...                            # ~53 s
```

That turns the worst failure mode this project has produced — a wiped
calibration recoverable only through a Windows VM — into something the tool can
fix itself.

**Safety reclassification.** `id 194` was marked `forbidden` after the incident,
when its function was unknown. It is now `destructive`: it has a legitimate,
valuable use, takes ~53 seconds, moves the motor, and must not be interrupted or
run while the stick is being handled. It requires explicit confirmation, never a
silent invocation. `id 195` (validity flag), `193` and `222` (motor state) stay
`forbidden` — writing those is what caused the damage, and none has a known use.

## Two other discoveries in the same capture

### Group 14 is a raw parameter channel

```
→ 7e 03 0e 12 00 01 2c db                  group 14, cmd 0, index 0x012c (300)
← 7e 07 8e 21 00 01 2c 00 00 24 5b ed      index 300, value 0x0000245b
```

Cockpit walks this space reading 32-bit values by **16-bit index**. This is very
likely the `(Table, Param)` store that write logs have been naming all along —
a generic, flat parameter view underneath the curated command ids.

If calibration data is reachable here, **it could be backed up and restored** —
which would close the "destructible and unrecoverable" gap in
[`07-safety.md`](../07-safety.md) entirely. Worth a careful read-only survey.

Note group 14 already had a known sub-command: `cmd 5` is the ASCII log
broadcast. So group 14 is the diagnostics/parameter group, with cmd 0 = param
read and cmd 5 = log.

### The serial number is readable

```
← 7e 0c 86 31 3e 00 2c 00 12 51 34 34 35 38 35 34 59
                            └── "Q445854" in ASCII
```

Group 6, device 19, cmd 62. Matches the tail of the USB serial
(`3E002C001251343435383534`). Useful for keying per-device profiles.

## Verification status

- [x] trigger frame captured and confirmed unique in the capture
- [x] confirmed no setup or handshake precedes it
- [x] progress semantics of id 194 confirmed (0 → 100 over ~53 s)
- [x] id 194 reclassified `destructive` with a legitimate use
- [ ] **trigger not yet tested from Linux** — needs a deliberate run with the
      stick untouched
- [ ] group 14 parameter space — unsurveyed
- [ ] whether calibration data is reachable there, and therefore backable-up

**Confidence**: `observed` for the capture. The Linux-side trigger is
`inferred` until run.
