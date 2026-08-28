# 2026-08-28 — The full grip catalogue and decode-mode map

**Method**

Wrote every value 0–255 to `id 92` and recorded the `Stick compatible mode is
changed to mode N` line the firmware emits for each. Restored to 0 afterwards.

## Result: 34 catalogue entries, 4 decode modes

| mode | catalogue ids | count |
|---|---|---|
| **0** | 0–15, 20–31 | 28 |
| **1** | 32 | 1 |
| **2** | 16–19 | 4 |
| **3** | 33 | 1 |

Values **34 and above are rejected** — no mode reported. So the grip catalogue is
exactly 34 entries, `0`–`33`.

Placing the three known grips:

| grip | id | mode |
|---|---|---|
| MOZA MH16 | 0 | 0 |
| VIRPIL Alpha Prime | 17 | **2** |
| WinWing WW-16 | 32 | **1** |

The blocks are coherent: `0–15` and `20–31` share MOZA's own decode, `16–19` is a
four-entry group containing the VIRPIL grip, and `32` / `33` are singletons
holding WinWing's.

## The hidden-capability avenue is closed

The open question was whether the firmware implements decode modes that Cockpit's
dropdown does not expose. **It does not.** Every valid catalogue id is in the
0–33 range the dropdown covers, and all four modes are reachable from it.

So the user's assessment stands, and is now measured rather than assumed:
**tux-ffb cannot do better than Cockpit at the decode level.** There is no hidden
mode to unlock, and we are not writing firmware.

## What is still worth having

Modest, but real, and it comes free with the map above:

- **A grip not on MOZA's list can be aimed at the right compatibility group.**
  Someone with an unlisted VIRPIL grip is far likelier to work in mode 2
  (ids 16–19) than anywhere else. Cockpit offers only named models, so it cannot
  give that advice; we can, because we know the grouping.
- **A wrong selection is a diagnosable failure.** "Your buttons stopped working
  because the decode mode does not match your grip" is a message Cockpit never
  shows — verified on hardware, where selecting WW-16 with an MH16 fitted left
  the buttons dead until the mode was set back.
- Only 3 of 34 catalogue names are known. The rest need a pass through the
  dropdown, which is now purely a labelling exercise — the mode structure behind
  it is fully mapped.

## Verification status

- [x] catalogue bounded at ids 0–33; 34+ rejected
- [x] four decode modes enumerated with their full id groupings
- [x] no modes hidden from Cockpit's dropdown — avenue closed
- [x] grip restored to 0 (MH16)
- [ ] catalogue names for ids other than 0, 17, 32

**Confidence**: `observed`.
