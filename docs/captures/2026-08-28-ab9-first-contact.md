# 2026-08-28 — AB9 first contact (read-only probe, no VM)

**Setup**

- MOZA AB9 `346e:1000`, bus 010 dev 019, powered on, attached to the **host**
- **MOZA MH16 grip attached** (corrected 2026-08-28 — originally and wrongly
  recorded as no grip), no MOZA software running anywhere
- `/dev/ttyACM0`, 115200 8N1, `exclusive=False`
- Probe: read-group frames only, plus a 3 s passive listen

## Result: the AB9 speaks the MOZA serial protocol

Frame format, checksum and device-id space all match the racing line. Every
device-originated frame below satisfies `(sum of bytes + 13) & 0xFF == last byte`.
boxflat's structural knowledge transfers wholesale.

## Finding 1 — the firmware emits a plaintext diagnostic stream, unprompted

Within 3 s of opening the port, with nothing sent:

```
7e 40 0e 21 05 "diag object index: 3, time usage: 3.02999%, run count/s: 10009\n" f7
   │  │  │  │  └─ payload (ASCII)
   │  │  │  └──── command id 0x05
   │  │  └─────── device id 0x21, nibble-swapped → 0x12 = 18 (main)
   │  └────────── group 0x0e = 14
   └───────────── length 0x40 = 64
```

The base free-runs a task profiler over the config channel: `group 14, dev 18,
cmd id 5, ASCII payload`. Frames cap at 64 payload bytes and **split
mid-string** — a message continues in the next frame, so a decoder must
reassemble rather than treat one frame as one message.

Consequence for `core/transport.py`: the read path must tolerate a continuous
unsolicited stream. This is not a request/response-only channel.

## Finding 2 — the firmware names its own source files when it rejects a command

Sending `main.output` (group 30, cmd id 57) from boxflat's racing table:

```
→ 7e 08 1e 12 39 00 00 00 00 00 00 00 fc
← [ERRO]serial_cmd_pull_main.c:315 Main_get, unexpect sub_cmd : 57
```

And `main.get-compat-mode` (group 31, cmd id 23):

```
→ 7e 02 1f 12 17 00 d5
← [ERRO]serial_cmd_pull_main.c:480 Main_set, unexpect sub_cmd : 23
```

(Both error strings arrived split across two frames, per Finding 1.)

This is a significant gift. It confirms:

- **Group 30 → `Main_get` handler, group 31 → `Main_set` handler**, both in
  `serial_cmd_pull_main.c`. The group dispatch is identical to the racing line.
- **`sub_cmd` is our command id**, echoed back by number.
- Our frame was parsed correctly all the way to the command dispatcher — length,
  group, device id and checksum were all accepted.
- Racing command ids **23 and 57 do not exist on AB9 firmware.** Same protocol,
  different command table, exactly as hypothesised.

It also means we can enumerate the command space by rejection: sweep sub_cmd ids
and record which ones *don't* come back as `unexpect sub_cmd`.

## Finding 3 — empty-reply signature

```
← 7e 00 a8 31 64      group 0xa8 = 40 | 0x80 (reply bit), len 0, dev 0x31 → 19
```

Returned for reads on device ids 16, 18 and 19. Reads to group 40 with ids 2
(`ffb-strength`) and 9 (`spring`) produced this. Reading as: *group understood,
no data for that id.* Distinct from silence, and distinct from `unexpect
sub_cmd` — three separate negative responses that a prober can classify.

## Finding 4 — device-id map

Swept ids 16–32 with a group-40 read (read-only):

| id | response |
|---|---|
| 16 | valid empty reply |
| 17 | **our own frame echoed back verbatim** |
| 18 | valid empty reply (this is `main`) |
| 19 | valid empty reply (this is `base`) |
| 20–32 | silence |

So the AB9 lives at the racing `main`/`base` ids. Nothing answers above 19 —
**and the MH16 was attached at the time**, so this is a real result, not an
artefact of a missing grip: the grip is *not* a separately addressed device on
the serial bus. It is a property of the base.

That is consistent with the user-visible behaviour that you must select the grip
type manually in MOZA Cockpit when you swap grips — the base does not simply
detect it. Grip type is therefore expected to be a **stored setting** on the
base, which makes it findable by differential read. Id 17's echo behaviour is
still unexplained.

## Correction to our own safety rule

The probe sent one **group 31** frame, which boxflat's table labels a *read*
group for `get-compat-mode`. The firmware calls group 31 `Main_set`. It was
rejected as an unknown sub_cmd so nothing was written, but the lesson stands:

> **boxflat's `read:` / `write:` labels are not a safety boundary on flight
> hardware.** They describe racing firmware. The AB9's own handler names are the
> authority, and until a group is confirmed against them it must be treated as
> potentially a write group.

Actioned in [`07-safety.md`](../07-safety.md).

## Verification status

- [x] checksum `(sum + 13) & 0xFF` holds on every device-originated frame
- [x] group dispatch confirmed by firmware error text
- [ ] read-back — no valid AB9 command id known yet
- [ ] Cockpit cross-check — not yet run
- [ ] physical effect — nothing written

**Confidence**: `observed` for framing, groups and device ids.
**Safety**: no writes attempted.
