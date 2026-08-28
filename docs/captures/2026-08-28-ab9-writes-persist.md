# 2026-08-28 — Writes survive a power cycle

**Test**

Two values written by tux-ffb, base switched off and on, full address space
re-read and diffed.

| address | value | age at power-off | result |
|---|---|---|---|
| Y deadzone `(152, bank 0, slot 1)` | 7 | minutes | **survived** |
| Y curve `(150, bank 1, slot 4)` | 60 | hours, and several Cockpit visits | **survived** |
| X deadzone `(151, bank 0, slot 1)` | 2 | untouched control | survived |
| friction `(id 178)` | 0 | written then restored | survived |

**Writes commit to non-volatile storage immediately.** There is no separate save
or commit step to find. A value written over the serial channel is still there
after the base has been powered down.

## What this settles

tux-ffb is a **configurator**, not a session tool. A user can set the base up on
Linux, power it off, and fly the next day with those settings intact — with no
MOZA software ever involved. That was the assumption the whole project rested on
and it is now measured rather than hoped for.

It also puts Cockpit's behaviour in its proper place. Cockpit overwrites the base
with its own profile **on connect**, which is why marker values kept vanishing
across VM visits. That is a Cockpit behaviour, not a base behaviour, and the
practical consequence for users is simply: configure on Linux, and don't open
Cockpit afterwards unless you want its profile.

## Correction: ids 163–168 are boot-time calibration, not grip state

Six values changed across the power cycle, and only those six:

```
163  5823 -> 5842      166  6287 -> 6312
164  3746 -> 3740      167  4214 -> 4211
165  1669 -> 1638      168  2141 -> 2110
```

These are the same ids previously recorded as shifting between the MH16 and the
Alpha Prime, and offered as evidence of grip-dependent calibration. **That was
wrong.** They shift by a comparable amount here with the *same grip fitted*,
across nothing but a power cycle. They are re-measured at boot — sensor or
motor calibration constants that land slightly differently each run.

The earlier grip comparison necessarily involved a power cycle, so the two causes
were confounded and the wrong one was named.

**This strengthens a different finding.** With 163–168 eliminated as noise, **id
92 stands alone** as the only value that genuinely tracked the grip — 0 with the
MH16, 17 with the Alpha Prime. The grip-type hypothesis is now cleaner than when
it was first proposed, because its competition has been ruled out.

Consequence for tooling: 163–168 belong in `snapshot.py`'s `VOLATILE` set. They
are not settings and they will otherwise pollute every diff that spans a power
cycle.

## Verification status

- [x] writes confirmed durable across a power cycle, two independent values
- [x] no separate commit or save step required
- [x] ids 163–168 identified as boot-time calibration, not grip-dependent
- [x] id 92 isolated as the sole grip-tracking value
- [ ] whether id 92 is genuinely the grip *type* — still one data point per grip

**Confidence**: `observed`.
