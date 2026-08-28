# 2026-08-28 — Z axis, adaptive centering, and an unrequested reset

**Setup**

User changes in one Cockpit session: a deliberately irregular **Z-axis curve**,
**Z axis inverted**, adaptive centering **effect strength = 21** and
**compensation effective range = 22**. Adaptive centering left on and hands-off
detection left disabled — both reported as *state*, not changes.

The Z axis is not physically fitted to this base. Cockpit configures it anyway.

## The Z axis is stored as floats at plain command ids

| address | before | after |
|---|---|---|
| id 83 | 20.0 | **89.0** |
| id 84 | 40.0 | **24.0** |
| id 85 | 60.0 | **76.0** |
| id 86 | 80.0 | **13.0** |
| id 87 | 100.0 | 100.0 |
| id 88, 89 | 0.0, 100.0 | unchanged (endpoints) |
| **id 90** | 0 | **1** — Z invert |

`89, 24, 76, 13` is the irregular curve, and wildly non-monotonic as intended.

**This is a second, different representation for the same concept.** X and Y
curves are integer slots on parameterised ids `149`/`150`; the Z curve is
IEEE-754 floats at plain ids `83`–`89`. The float block at 83–89 was noticed on
day one and mistaken for a duplicate of the X/Y curve — it is the *Z* curve, and
that is why it never moved when X or Y was edited.

`id 90` is confirmed as Z invert by elimination: it was the only boolean in the
whole address space to change, and the Z inversion was the only boolean the user
toggled. Note it is adjacent to the Z curve block, whereas X's invert sits far
away at `id 158`.

## Adaptive centering compensation

| control | marker | address |
|---|---|---|
| effect strength | 21 | **id 209**, bank 0, slots 0, 1, 2 |
| compensation effective range | 22 | **id 210**, bank 0, slots 0, 1, 2 |

Both have **three** slots, all of which took the same marker from a single
Cockpit control. Three slots suggests roll/pitch/Z rather than the roll/pitch
directional pairs seen on the effect block — untested. `id 196` has the same
three-slot shape and is still unidentified.

## Unrequested: every force-feedback setting reverted to its default

The 18 settings mapped in the previous session — all set to distinct markers and
read back correctly — are **back at factory values**, and the user did not reset
them:

```
169 max torque limit   25 -> 100      205/206 per-axis        29,30,26,27 -> 100
174 ffb intensity      28 ->  70      218 spring gain         32,33 -> 100
175 spring             31 ->   0      219 damper gain         35,36 -> 100
176 damper             34 ->   5      220 inertia gain        38,39 -> 100
177 inertia            37 ->   0      221 friction gain       42,43 -> 100
178 friction           41 ->   0
```

This is the third time settings have reverted across a Cockpit visit — the X
curve did it, then the Y curve, now the entire effect block. The pattern is
consistent with **Cockpit writing its own profile to the base on connect**,
overwriting whatever is there, rather than reading the base's state first.

It matters for tux-ffb in two ways:

1. **Enumeration markers are not durable.** Each marker pass must be diffed
   against a capture taken *after* the Cockpit visit that set it, which is what
   we have been doing, so no results are affected.
2. **It raises the persistence question for our own writes**, which is now the
   most important open item. Do tux-ffb's writes survive a power cycle? Do they
   survive a subsequent Cockpit connection? The second almost certainly not, on
   this evidence — but the first is what actually matters for a user who
   configures on Linux and never opens Cockpit again.

**The test:** write a distinctive value with `setval.py`, power the base off and
on, and read it back. That is a five-minute experiment and it gates whether
tux-ffb is a configurator or a session-only tool.

## Verification status

- [x] Z curve located at ids 83–87 (float), endpoints 88/89
- [x] Z invert at id 90, by elimination
- [x] adaptive centering strength/range at ids 209/210
- [x] float block 83–89 correctly identified as Z, not a duplicate X/Y curve
- [ ] whether the three slots on 209/210/196 are roll/pitch/Z
- [ ] physical effect of any setting in this note (Z is not even fitted)
- [ ] **do our writes survive a power cycle** — now the priority

**Confidence**: `observed` for the addresses. `inferred` for id 90 (elimination,
single trial).
