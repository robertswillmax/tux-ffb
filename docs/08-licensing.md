# 08 — Licensing and provenance

## tux-ffb is GPL-3.0-only

Chosen deliberately, not by default.

## Why: boxflat

[boxflat](https://github.com/Lawstorant/boxflat) (Tomasz Pakuła) is GPL-3.0-only
and contains years of accumulated knowledge about MOZA's serial protocol — the
frame format, the checksum, the device id map, and a 2000-line command table.
Reimplementing that from scratch, for a protocol we'd then have to re-derive
capture by capture, would be a large amount of work spent on ground someone else
already covered and published freely.

Licensing tux-ffb GPL-3.0-only means we can **read, adapt and reuse boxflat's
code directly**, with attribution, and stay unambiguously within the licence.
The alternative — a permissive licence — would require clean-room derivation of
material we can simply be allowed to use. That trade isn't worth it for a tool
whose users are all going to install it from a package manager anyway.

## Obligations we take on

- Any file adapted from boxflat carries a header naming it, its author, and its
  licence. Not a courtesy — a requirement.
- The command table in `data/protocol/` is derived from boxflat's `serial.yml`
  and is marked as such at the top of the file.
- Contributions are GPL-3.0-only. No CLA.

## Provenance in the command table

Separate from licensing, every command entry records **how we know what it
does**:

| `source` | meaning |
|---|---|
| `boxflat:<command-name>` | Taken from boxflat's table. Racing-verified; **not** verified on flight hardware. |
| `capture/<file>` | Observed in a MOZA Cockpit ↔ base capture. See [`06-protocol-acquisition.md`](06-protocol-acquisition.md). |
| `probe/<file>` | Found by our own read-only scan. |
| `inferred` | Reasoned from neighbouring commands. Not sent without `--unsafe`. |

This keeps two different questions apart — *may we use this?* and *do we believe
this?* — which is worth doing explicitly, because the second one is where the
bricked hardware lives.

## What we will not do

- Ship anything extracted from MOZA's own binaries or firmware.
- Redistribute MOZA firmware images.
- Implement firmware update commands. See [`07-safety.md`](07-safety.md).

Reverse-engineering a hardware protocol for interoperability is well-established
practice, and it's the only thing that makes this hardware usable on Linux at
all. But there's a clear line between *understanding the conversation* and
*redistributing the vendor's work*, and we stay on the right side of it.
