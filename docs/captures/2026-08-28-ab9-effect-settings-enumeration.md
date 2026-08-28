# 2026-08-28 — Force-feedback settings enumerated by marker values

**Method**

Rather than one setting per VM round trip, the user set **sixteen controls in a
single Cockpit session, each to a distinct marker value** chosen from values that
appeared nowhere in the address space. One capture and one diff then identifies
every one of them at once, because each id's new value names the control that
produced it.

This is the fastest form of differential capture available and it should be the
default from here on. Cost: one round trip for sixteen settings.

## Result: 18 settings identified

| Cockpit control | marker | address |
|---|---|---|
| maximum torque limit | 25 | **id 169** |
| overall FFB intensity | 28 | **id 174** |
| spring | 31 | **id 175** |
| damper | 34 | **id 176** |
| inertia | 37 | **id 177** |
| friction | 41 | **id 178** |
| roll max torque | 27 | **id 206 slot 0** |
| pitch max torque | 26 | **id 206 slot 2** |
| roll intensity | 30 | **id 205 slot 0** |
| pitch intensity | 29 | **id 205 slot 2** |
| spring gain roll / pitch | 33 / 32 | **id 218 slots 0,1 / 2,3** |
| damper gain roll / pitch | 36 / 35 | **id 219 slots 0,1 / 2,3** |
| inertia gain roll / pitch | 39 / 38 | **id 220 slots 0,1 / 2,3** |
| friction gain roll / pitch | 43 / 42 | **id 221 slots 0,1 / 2,3** |

Recorded in [`data/protocol/ab9-settings.yaml`](../../data/protocol/ab9-settings.yaml).

## Structure

**Masters are plain getters in a contiguous block**: 174, 175, 176, 177, 178 —
overall intensity, spring, damper, inertia, friction, in that order. Plus 169 for
the torque limit.

**Per-axis versions are parameterised, and the master→per-axis offset is a
constant 43**:

```
spring   175 -> 218      inertia  177 -> 220
damper   176 -> 219      friction 178 -> 221
```

**Slot convention within bank 0**: slots `0,1` are the roll (X) pair and `2,3`
are the pitch (Y) pair. Cockpit exposes each pair as one control with a "+/-
linked" toggle, which is why both slots of a pair took the same marker. Which
slot is `+` and which is `-` is not yet determined — it needs one unlinked
setting to tell them apart.

Ids 205 and 206 expose only slots 0 and 2, i.e. one value per axis with no
directional split, which is consistent with the same convention.

**Pitch = Y, roll = X**, confirmed: the pitch markers landed in slot 2 and the
roll markers in slot 0.

## Correction: the X/Y pairing rule is narrower than claimed

The rule recorded earlier — *consecutive command ids are (X, Y) pairs, lower id
is X* — was confirmed by prediction on the axis-shaping ids and then promoted to
the device model. **It does not generalise.**

Here, consecutive ids are consecutive *settings*, and the axes live in slots
within each id:

```
205 = per-axis FFB intensity   (both axes, slots 0 and 2)
206 = per-axis max torque      (both axes, slots 0 and 2)
218,219,220,221 = spring, damper, inertia, friction gains
```

So the device uses **two different layouts**:

| block | axis lives in |
|---|---|
| axis shaping (149/150 curves, 151/152 endpoints) | the **command id** — one id per axis |
| force-feedback effects (205, 206, 218–221) | the **slot** — one id per setting, axes inside |

The pairing rule is real but scoped to the axis-shaping block. Corrected in
[`03-device-model.md`](../03-device-model.md).

The general lesson repeats one already recorded: a rule confirmed on the cases
that suggested it is not thereby confirmed everywhere. It took a block with a
different layout to expose the limit.

## Not yet identified

Still-unmapped parameterised ids: 147, 148 (six banks of curve-shaped data),
171, 172, 173, 180, 181, 182, 183, 196, 197, 199, 209, 210. Plus most plain ids.
A second marker pass over whatever Cockpit panels remain would take a similar
bite out of that list.

## Verification status

- [x] 18 settings mapped to addresses by unique marker values
- [x] master → per-axis offset of 43 established
- [x] slot convention: 0,1 = roll, 2,3 = pitch
- [x] pairing rule scoped correctly
- [ ] which slot of each pair is `+` vs `-` — needs an unlinked setting
- [ ] **physical effect of every setting in this note** — all `unverified`
- [ ] the remaining unmapped ids

**Confidence**: `observed` for the address mapping. **Effect: unverified for all
of them** — these were identified by storage, and nothing here has yet been shown
to change how the base behaves.
