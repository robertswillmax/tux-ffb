# 2026-08-28 — The volatile ids are not stick position

**Question**

Ids 184, 185, 215, 216 change between snapshots and are excluded from diffs as
"volatile". Are they simply reporting stick position or the forces on it?

**Test**

Hold the stick at a fixed deflection, then sample the kernel's own axis values
(`EVIOCGABS` on the AB9's evdev node) and the four serial ids together, 20 times
over 10 s. Then compare across two different static stick positions.

## Result: no

With the stick held still at `ABS_X=276, ABS_Y=17039`:

```
    t   ABS_X   ABS_Y |   id215   id216   id184   id185
  0.0     276   17039 |     291    3214       0       0
  4.6     276   17039 |     291    3214       0       0
  9.7     276   17039 |     291    3211       0       0

ranges: ABS_X 276-276   ABS_Y 17039-17039   id215 284-295   id216 3204-3214
```

The kernel axes are perfectly static while the serial ids jitter continuously by
a few counts. A position register does not do that.

The decisive comparison is across positions. Between two static samples:

| | ABS_X | id215 |
|---|---|---|
| first | 32767 | 305 |
| second | 276 | 291 |

`ABS_X` swung across essentially the full travel; id215 moved by 14 counts. They
are not the same quantity, and no scaling reconciles them.

## What they are instead

Small, continuously jittering analog values — plausibly motor current,
temperature, or raw encoder noise. 184/185 hover around 0 and wander either side.
They also take large step changes between sessions (215 has read both 32765 and
291), so they track some internal device state, not a user-visible setting.

They stay in `snapshot.py`'s `VOLATILE` set, reported separately in a diff rather
than dropped, and are not candidates for anything a configurator exposes.

## Corollary: read live axes from evdev, never from the serial channel

The kernel already exposes true axis position on the AB9's evdev node with full
0–65535 range. It is faster, it is what the game sees, and it costs the config
link nothing. This confirms the choice already made in [`04-ui.md`](../04-ui.md)
and removes any temptation to poll position over serial.

**Caveat noticed while testing:** `ABS_X` read exactly 32767 and then 276 a few
minutes later with no deliberate input, so the stick was still settling between
the two snapshots. Any future test that depends on physical position must confirm
the axis is actually static *before* capturing, not assume it. Note also that
with a non-linear curve loaded, evdev output is the curve's output — not raw
position.

## Verification status

- [x] position hypothesis tested against kernel ground truth and rejected
- [x] evdev confirmed as the live-axis source
- [ ] what 184/185/215/216 actually measure — unknown, and not worth chasing
      until something needs them

**Confidence**: `observed` for the negative result.
