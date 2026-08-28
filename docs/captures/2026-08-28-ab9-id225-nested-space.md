# 2026-08-28 — id 225 is a nested address space

**What it is**

Not a setting. `id 225` takes an index and, for most indices, a further
sub-selector, giving a three-level address:

```
7e 03 1e 12 e1 0f 01            read  (225, 0x0f, 0x01)
7e 04 1f 12 e1 0f 00 64         write (225, 0x0f, 0x00) = 0x64
7e 05 1f 12 e1 11 10 02 28      write (225, 0x11, 0x10) index 2 = 0x28  (four levels)
```

Read-only enumeration over indices 0–63 and sub-selectors 0–47 finds roughly
**640 valid three-level addresses**. `id 15` behaves the same way.

The trim and follow block lives here. That is why a flat scan of the command
space never found it, and why the earlier note concluding "the trim settings are
not in the mapped address space" was right about the manifest and wrong about the
device.

## Structure so far

| index | sub-selectors | value |
|---|---|---|
| 2, 8 | 48 | `0a` |
| 3, 9 | 40 | `64` |
| 4, 12 | 48 | `7f ff` |
| 10, 11 | 40–48 | `32` |
| 15 | 48 | `64` — trim follow ratio; set to `c8` by "full follow" |
| 16, 17 | 40–48 | `5b 00` |
| 35, 37 | 40–48 | `00` |
| 36 | 48 | `64` |

Plain two-level entries with a single value: 0, 1 (trim following), 6 (autopilot
following), 7, 14 (trim follow mode), 18, 19, 23 (FFB enable), 33, 34, 39.

## A caution: two-level reads of indexed entries are not stable

Reading `(225, 2)` — without a sub-selector — returned `22 00` on one pass and
`2f 00` on two later ones. `0x2f` is 47, the highest sub-selector probed in the
run immediately before. **The value depends on what was accessed previously**, so
it behaves like a cursor or last-access register rather than a setting.

Anything read that way is meaningless. Indexed entries must be read with their
sub-selector.

This also cost a false result: the first enumeration mixed two- and three-level
addresses in the same pipelined batch, and a reply to `(225, idx, sub)` has a
payload beginning `225, idx, sub`, which matches the two-level address by prefix.
The levels are now probed in separate passes — but separating them did not make
the two-level values trustworthy, only differently wrong.

## What the space probably is

The user's reading, and it fits: **640 addresses is far too many for switches,
and the shape suits telemetry FFB effect tables.** MOZA's integrated and
telemetry FFB modes would each need per-effect curves — several tables of 40–48
entries is exactly what that looks like, and it explains why the values are
uniform defaults (`0x0a`, `0x64`, `0x7fff`) rather than scattered.

Partly borne out already: the force-sensing settings turned out to live here too
(idx 34, 35, 36), so `225` looks like the home for whole operating modes rather
than for individual switches.

## What remains

Naming these ~640 addresses needs a marker pass: set the trim and follow controls
to distinct values in Cockpit, then diff this space. The structure is now known,
which is what was missing — the earlier marker attempt failed because it searched
a space that did not contain them.

## Verification status

- [x] three-level addressing confirmed by read and by captured writes
- [x] ~640 valid addresses enumerated under id 225
- [x] two-level reads of indexed entries shown to be access-dependent
- [ ] semantics of any of them beyond the eleven located by capture
- [ ] the four-level form seen in writes (`e1 11 10 02 28`)

**Confidence**: `observed` for the structure. Nothing is claimed about meaning.
