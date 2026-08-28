# 2026-08-28 — What the grip dropdown does, and write width is per-address

## The grip dropdown selects a firmware decode mode

Writing `id 92` produces this on the log channel:

```
[INFO]stick.c:1073 Stick compatible mode is changed to mode 0
[INFO]stick.c:515  Stick connection reset
[INFO]param_manage.c:340 Table 2, Param 22 Written: 0
[INFO]stick.c:347  Stick_reg is connected
[INFO]stick.c:1268 Stick identify id is 0
```

Writing `32` instead reports **`mode 1`**. So the grip catalogue id and the
firmware's decode mode are different numbers:

| grip | id 92 | stick compatible mode |
|---|---|---|
| MOZA MH16 | 0 | 0 |
| WinWing WW-16 | 32 | 1 |
| VIRPIL Alpha Prime | 17 | not yet observed |

**The catalogue is many-to-few.** Several grips presumably share a decode mode,
which is why MOZA can list grips it does not manufacture: what matters is the
electrical protocol the grip speaks, not the specific model.

Changing it also **resets the grip connection** (`stick.c:515`), so the base
re-initialises the link rather than merely relabelling.

## Correction: grip support is not purely host-side

The previous note concluded that "the base is indifferent to what is actually
plugged in" and that "all grip intelligence lives in host software". **That was
too strong.** The base does not *identify* the grip, but it very much *decodes*
it, and `id 92` selects which decoding it uses. Choosing the wrong entry means
buttons do not enumerate correctly — a firmware behaviour, not a labelling one.

The corrected picture:

- **Firmware owns:** the electrical decode of the grip's button matrix, selected
  by mode.
- **Host owns:** everything above that — button naming, hat modelling, shift
  layers, per-aircraft bindings.

tux-ffb still has the opportunity claimed earlier, but it now has a
responsibility too: **setting the grip type is functional, not cosmetic.** A grip
profile must carry the correct `id 92` value, and picking it wrongly breaks the
user's buttons.

`Stick identify id` echoes the configured mode rather than probing the hardware —
it reported 0 with the MH16 fitted under every setting attempted, so it is not a
detection channel.

## The HID descriptor is static

Enumerated before and after a mode change: **80 buttons** (`0x120`–`0x12f`,
`0x2c0`–`0x2ff`) and 10 axes, identical. The mode changes which physical control
maps to which code, not how many exist. So a host cannot infer the fitted grip
from the descriptor either.

## Correction: write width is per-address, and getting it wrong can be silent

Earlier this session, writing `id 178` with a one-byte value was rejected
(`unexpected parameter`) and two bytes worked, which was generalised to "plain
writes take two bytes". **Wrong.**

`id 92` takes **one** byte:

```
7e 02 1f 12 5c 20 3a   1-byte value 32  ->  reads back 32   CORRECT
7e 03 1f 12 5c 00 20 3b 2-byte value 32  ->  reads back 0    SILENTLY WRONG
```

The two-byte form produced **no warning at all** and wrote `0`. That is worse
than the `id 178` failure, which at least complained.

**Consequences:**

1. Width belongs to the individual setting, alongside its type and range, and
   must be recorded per entry in the command table — not derived from whether the
   address is plain or parameterised.
2. **A write is not verified until it has been read back.** A wrong-width write
   can look entirely successful: no warning, a plausible firmware log line, and a
   value that is simply not the one requested. `setval.py` already reads back and
   reports a mismatch; that check is now load-bearing rather than a courtesy.
3. Width cannot be inferred from read width — `id 178` reads back in one byte but
   requires two to write.

Determining width for a new setting: try the narrower form first and confirm by
read-back. A wrong narrow write is likelier to be rejected than to succeed with a
mangled value.

## Verification status

- [x] grip dropdown confirmed to select a firmware decode mode
- [x] catalogue id and mode number confirmed distinct (32 -> mode 1)
- [x] mode change resets the grip connection
- [x] HID descriptor confirmed static across mode changes
- [x] write width confirmed per-address; wrong width can write silently wrong
- [x] grip restored to 0 (MH16), matching the fitted hardware
- [ ] mode number for id 17, and the full id -> mode mapping
- [ ] whether button mapping demonstrably changes with mode — needs button presses

**Confidence**: `observed`.
