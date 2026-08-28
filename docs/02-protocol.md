# 02 — The MOZA serial protocol

Everything here is derived from boxflat (GPL-3.0-only, Tomasz Pakuła) plus
first-hand observation of the AB9. Racing-side details are well established;
**flight-side details are unverified** and flagged as such. See
[`06-protocol-acquisition.md`](06-protocol-acquisition.md) for how we close that
gap, and [`08-licensing.md`](08-licensing.md) for why we can use boxflat's work.

## Physical layer

The AB9 enumerates as `346e:1000`, "MOZA AB9 FFB Base", with three interfaces:

| Interface | Class | Node | Purpose |
|---|---|---|---|
| if00 / if01 | CDC-ACM | `/dev/ttyACM*` | **Configuration and firmware.** This is our channel. |
| if02 | HID | `/dev/hidraw*`, `/dev/input/event*` | Joystick axes, buttons, PID force feedback. Owned by the kernel and the game. |

Serial parameters: **115200 baud, 8N1**, opened non-exclusively
(`exclusive=False`). Non-exclusive matters — boxflat may be running for a racing
base on the same machine, and neither app should lock the other out of its own
port. We open only the port belonging to a device we recognise as ours.

The HID interface is strictly read-only for us. It belongs to the kernel's
`hid-pidff` path and, during a flight, to the game. tux-ffb reads evdev for live
axis and button display and never writes to it (until the opt-in telemetry
daemon in [`05-ffb-telemetry.md`](05-ffb-telemetry.md)).

## Frame format

Host → device:

```
 offset  field         notes
 ------  -----------   -------------------------------------------------------
 0       0x7E          start byte ("message-start", 126)
 1       length        len(command_id) + len(payload)  — NOT the whole frame
 2       group         read group or write group, depending on direction
 3       device_id     addressee, e.g. 19 = racing base
 4..     command_id    1..n bytes, from the command table
 ..      payload       length-defined, big-endian for ints and floats
 last    checksum      (sum of every preceding byte + 13) & 0xFF
```

The `+ 13` is the "magic value". It is a constant, not a per-device secret.

Device → host, same shape, with two transforms applied to the header:

- `group` has **bit 7 set**; clear it to recover the read group that the reply
  answers.
- `device_id` has its **nibbles swapped** (`0xAB` → `0xBA`).

A reply's payload begins with the command id it answers, so a reader matches on
`(group, command_id_prefix)` and takes the remainder as the value.

### Reading the stream

The framing is not self-synchronising — there is no escape mechanism, and `0x7E`
can occur inside a payload. The resync strategy is:

1. Scan for `0x7E`.
2. Read the length byte. Reject anything outside the plausible range
   (boxflat uses 2..11; we widen to 1..32 for flight commands we haven't seen
   yet, and log out-of-range lengths rather than swallowing them).
3. Read `length + 3` further bytes: group, device_id, `length` bytes of
   id+payload, and the checksum.
4. **Verify the checksum.** boxflat reads `length + 2` and discards the checksum
   byte unverified; we read and check it. On mismatch, drop the frame, log it,
   and resync from the next `0x7E`. This is the difference between "the decode
   is probably right" and "the decode is right", and it matters most exactly
   where we're weakest — on unmapped flight commands.

## Addressing

Devices on the bus have small integer ids. The racing map:

| id | device |
|---|---|
| 18 | main (devices reached through USB) / hub |
| 19 | base |
| 20 | dash |
| 21, 23 | wheel |
| 25 | pedals |
| 26 | h-pattern / sequential shifter |
| 27 | handbrake |
| 28 | e-stop |

**Open question, and the single most important one in the project:** does an AB9
answer on id 19 with the racing base command set, or does the flight line have
its own id space and command groups? Both are plausible. MOZA shipping one
firmware family across racing and flight would make 19 likely; shipping Cockpit
as a separate app hints the other way. The first capture answers this in
minutes, and every other question is downstream of it.

The equivalent question for grips: a grip is a *module* on the base, which in
racing terms is what "wheel" (23) is to "base" (19). Whether MOZA models flight
grips as separate addressable devices, or as a property of the base, determines
whether grip support is a device profile or a base setting.

## Command table

boxflat stores its command set as YAML, keyed by device name:

```yaml
commands:
  base:
    get-led-status:  { read: 31, write: -1, id: [8],  bytes: 1, type: int }
    set-led-status:  { read: -1, write: 31, id: [9],  bytes: 1, type: int }
```

- `read` / `write` — group byte for each direction; `-1` means unsupported.
- `id` — command id bytes.
- `bytes` — payload length.
- `type` — `int`, `float` (big-endian IEEE-754), `array`, or `hex`.

We adopt this schema, because compatibility with boxflat's table means their
racing work and any future flight work cross-pollinate for free. We extend each
entry with provenance and safety metadata:

```yaml
    set-axis-x-range:
      read: -1
      write: 42          # PLACEHOLDER — not yet observed
      id: [12]
      bytes: 2
      type: int
      range: [0, 65535]  # rejected client-side before transmission
      unit: raw
      source: capture/2026-08-ab9-axis-range.md   # how we know
      confidence: observed | inferred | guessed
      safety: normal | destructive | forbidden
```

### Writing

Confirmed on hardware 2026-08-28. Writes use group 31 (`Main_set`) and mirror the
read addressing, with the value appended:

```
parameterised:  7e | len | 31 | 18 | cmd_id | index | value(1 byte)  | ck
plain:          7e | len | 31 | 18 | cmd_id |       | value(2 bytes) | ck
```

**The wire width belongs to the individual setting**, and must be recorded per
entry in the command table. `id 178` requires a two-byte value and rejects one
byte with `unexpected parameter`; `id 92` requires **one** byte and, given two,
**silently writes zero with no warning at all**. Width cannot be inferred from
read width either — `id 178` reads back in one byte and writes in two.

Widths established across 20 settings show a strong tendency with real
exceptions:

| kind | width | exceptions |
|---|---|---|
| parameterised (has an index) | 1 | none seen in 10 settings |
| plain (no index) | 2 | **`id 90` (invert-z) and `id 92` (grip-type) are 1** |

The decisive case: **`invert-x` (id 158) is two bytes and `invert-z` (id 90) is
one** — identical semantics, different widths. So the tendency is a starting
guess for probing, never a substitute for establishing the width per address and
confirming by read-back.

Floats are written as 4-byte big-endian IEEE-754, verified against the Z-axis
curve at ids 83–89.

**So a write is only verified by reading it back.** A wrong-width write can
produce no warning, a plausible-looking firmware log line, and a value that is
not the one requested. See
[`captures/2026-08-28-ab9-grip-mode-and-write-width.md`](captures/2026-08-28-ab9-grip-mode-and-write-width.md).

There is no reply frame. Confirmation arrives on the ASCII log channel:

```
[INFO]param_manage.c:340 Table 7, Param 54 Written: 1022739087 0.02999
```

which names the internal `(Table, Param)` location and prints the stored word
**both as an integer and as a float**. That is how to tell a parameter's storage
type: writing integer `3` to the friction master stored `0.02999`, so that
parameter holds a float fraction, while the deadzone write stored a packed
integer whose float reading is meaningless. Harvest this line on every write.

### Indexed settings

Confirmed on AB9 hardware: **25 read commands take an index parameter**, and the
index is itself two fields — `bank = index >> 4`, `slot = index & 0x0F`. The
request carries the index as its payload, and the reply echoes it:

```
→ 7e 02 1e 12 <cmd_id> <index> <ck>
← 7e ?? 9e 21 <cmd_id> <index> <value...> <ck>
```

Sent **without** the parameter, the firmware reads a stale byte in its place and
returns a plausible wrong value — see
[`captures/2026-08-28-ab9-parameterised-reads-and-grip-diff.md`](captures/2026-08-28-ab9-parameterised-reads-and-grip-diff.md).
It warns on the ASCII channel, but the reply frame itself looks perfectly valid.
**A read without its required parameter is silently wrong, not failed.**

Consequences for the table: a setting is addressed by `(command_id, bank, slot)`;
bank counts differ per command (5, 2 and 3 observed on different ids); index
ranges are sparse, so validity must be enumerated rather than assumed to be a
range; and payload width varies *per index*, so `bytes`/`type` belong on the leaf
rather than the command.

`confidence` and `safety` are not decoration. The CLI refuses to send anything
below `observed` without `--unsafe`, and refuses `forbidden` (firmware update,
EEPROM erase) unconditionally. See [`07-safety.md`](07-safety.md).

## Confirmed on AB9 hardware

Probed 2026-08-28 against a live AB9 on `/dev/ttyACM0`, read-only, no VM. Full
detail in [`captures/2026-08-28-ab9-first-contact.md`](captures/2026-08-28-ab9-first-contact.md).

- **The framing above is correct on flight hardware.** Checksum `(sum + 13) & 0xFF`
  validates on every device-originated frame.
- **Group dispatch matches the racing line.** The firmware's own error text names
  group 30 → `Main_get` and group 31 → `Main_set`, in `serial_cmd_pull_main.c`.
- **Device ids 16, 17, 18 and 19 respond; 20–32 are silent** (with no grip
  attached). Id 17 echoes frames back verbatim.
- **The command id space is different.** Racing ids 23 and 57 are rejected by
  name and number.
- **The channel is not request/response-only.** The base free-runs an ASCII task
  profiler at group 14 / dev 18 / cmd id 5, in 64-byte frames that split
  mid-string. A decoder must reassemble across frames.

### Three distinct negative responses

Classify them separately — the difference is what makes enumeration possible:

| response | meaning |
|---|---|
| `7e 00 <group\|0x80> <dev> <ck>` | Group understood, no data for that id. |
| `[ERRO]…unexpect sub_cmd : N` | Group understood, command id N does not exist. |
| silence | Device id not present, or frame not accepted at all. |
| no reply, but not rejected either | The dispatcher accepts the id and produces nothing. Seen on ids 126, 194, 195. Possibly write-only or long-running — treat as unknown. |

A fifth case is not a device response at all: a reply that simply **arrived after
you stopped listening**. Scanning the AB9 with a fixed 0.12 s window missed 34 of
124 ids and corrupted others by letting replies bleed into the next request's
buffer. Poll until the echo matches; never sleep a fixed interval and parse
whatever showed up.

### Enumeration by rejection

Because the firmware reports unknown command ids **by number**, the readable
command space can be enumerated without the VM: sweep sub_cmd ids against a
confirmed *get* group and record which ones don't come back as `unexpect
sub_cmd`. Read-only, self-documenting, and it does not need MOZA Cockpit at all.

Sweep only groups confirmed to be **get** handlers. See the correction in
[`07-safety.md`](07-safety.md) — boxflat's `read:`/`write:` labels describe
racing firmware and are not a safety boundary here.

## What we still do not know

1. Which command ids the AB9 actually implements — the enumeration above is the
   next job.
2. Payload semantics for those ids: units, scaling, ranges.
3. How a grip presents itself. Ids 20+ were silent **with no grip attached**;
   re-run the sweep with the MH16 fitted before drawing any conclusion.
4. What id 16 is, and why id 17 echoes.
5. Whether Cockpit performs a handshake we haven't seen.
6. Which settings are EEPROM-backed vs session state. Axis calibration is known
   to persist; nothing else is.
7. Anything at all about the AB6.
