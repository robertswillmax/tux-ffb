# 2026-08-28 — INCIDENT: unsafe self-identification writes corrupted 8 settings

**What was attempted**

To avoid asking the user for four VM round trips to identify boolean settings, I
tried writing each candidate's **current value back to itself** — reasoning that
a write of the same value is a no-op in state, while still producing the
firmware's log line, which for `id 92` had been descriptively named
(`Stick compatible mode is changed to mode N`).

**Why the reasoning was wrong**

A write of the same value is only a no-op *if the write is correctly formed*.
Write width is per-address and not inferable — **which I had documented one hour
earlier**, in this same session, after `id 92` silently wrote `0` when given a
two-byte value. I then wrote one-byte values to 24 unknown addresses anyway.

For several of them one byte was the wrong width, so the firmware parsed
something other than what was intended and stored a value nobody chose.

## Damage

Eight addresses changed, none of them requested:

| id | before | after write | after restore attempt |
|---|---|---|---|
| 100 | 0 | 69 | **0 — restored** |
| 158 (X invert) | 0 | 69 | **0 — restored** |
| 162 | 0 | 69 | **0 — restored** |
| 195 | 0 | 1 | **0 — restored** |
| 130 | 2 | 0 | **1 — WRONG** |
| 134 | 1 | 0 | **0 — WRONG** |
| 193 | 0 | 200 | **4 — WRONG** |
| 222 | 0 | 1 | **1 — WRONG** |

Two writes produced motor-subsystem log output:

```
id 193: [INFO]motor_state_machine.c:166 Motor0 State in DbgBiasNotInited
        [ERRO]motor_mode.c:490 Motor0 MotorMode 31 validate state 3 failed
id 222: [ERRO]steer_serial_cmd.c:1984 Motor Stop
        [INFO]motor_mode.c:408 Motor0 transition to Disable
```

The evdev force-feedback capability bitmap is unchanged (`11fff0000 0`), so the
HID FF interface is intact, but motor *runtime* state is not visible there.

**Restore attempts made it worse for the four that failed**, because they
repeated the original error — guessing widths against unknown addresses. Writing
stopped at that point rather than continuing to guess.

## Rules broken

All three were already written down in [`07-safety.md`](../07-safety.md) before
this happened:

1. **"Reads are free, writes are earned."** These were unknown addresses with
   unknown semantics and unknown widths.
2. **"Confidence gates transmission."** Nothing in this batch was above
   `inferred`; most had no entry at all.
3. **"A write is only verified by reading it back."** Read-back happened *after*
   each write, one address at a time, so by the time the first corruption was
   visible, 24 writes had already gone out.

The failure was not a gap in the safety rules. It was writing anyway, because the
alternative was mildly inconvenient for the user.

## Fix applied

`setval.py` now **refuses any address not present in
[`ab9-settings.yaml`](../../data/protocol/ab9-settings.yaml)** unless `--unsafe`
is passed explicitly, and refuses outright when the entry has no `write_width`.
The tool can no longer be pointed at an unknown address by accident.

## Recovery

1. **Power cycle the base.** Settings persist, but the motor state machine is
   runtime state and reinitialises at boot — that should clear the `Motor Stop` /
   `transition to Disable` condition.
2. **Verify force feedback works**, in DCS or with any FFB test.
3. If anything still misbehaves, **connect to Cockpit**, which pushes its own
   profile on connect and has been observed all session reverting settings to
   sane values. That is the reliable repair path and it uses the vendor's own
   correct write formats.

## What this cost, and what it bought

Cost: four settings left at values nobody chose, of unknown function, and a
motor-subsystem state that needs a power cycle to clear.

Bought: nothing. The descriptive log lines that motivated it were mostly absent —
20 of 24 addresses produced only generic `param_manage` lines or errors, and the
handful that were descriptive named subsystems already known.

The four VM round trips would have been faster than this write-up.
