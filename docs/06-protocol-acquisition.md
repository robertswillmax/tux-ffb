# 06 — Protocol acquisition

This is the critical path. Everything else in the project is ordinary
application work; this is the part that can fail. It gets its own document and
its own tooling.

## The advantage we have

The dev machine already runs MOZA Cockpit in a Windows VM (`moza-win11`) with
the AB9 passed through over USB. That means we can watch the *authoritative*
implementation talk to the *actual* hardware, on demand, for any setting we
like. We are not guessing at a protocol from first principles; we are reading a
conversation.

Because QEMU's USB passthrough goes through usbfs on the host, `usbmon` sees
every URB. No instrumentation inside the guest is required.

## Method: differential capture

The whole technique in one line: **change exactly one thing, and diff.**

For each setting Cockpit exposes:

1. Start capture: `modprobe usbmon`, then capture the AB9's bus with
   `tshark -i usbmonN -w capture.pcapng` (or `cat /sys/kernel/debug/usb/usbmon/Nu`
   for a text dump — cheaper and easier to script).
2. Let Cockpit settle. Record ~5 s of idle traffic as the baseline; the app
   almost certainly polls.
3. Change **one** control by a **known** amount — for example, X-axis range from
   100% to 90%.
4. Stop capture. Decode to frames with `tools/capture/decode.py`.
5. Subtract the idle pattern. What remains is the write, and probably a read-back.
6. Record the finding in `docs/captures/` with the frame bytes, the control, the
   before/after values, and the resulting command-table entry.

Repeat with a second value for the same setting to confirm the payload encoding
(is it raw, percent, big-endian, scaled?). Two points beat one guess.

### First session, in order

The first hour should answer the questions that everything else depends on:

1. **Does the AB9 speak the frame format at all?** Look for `0x7E`, plausible
   length bytes, and a checksum that satisfies `(sum + 13) & 0xFF`. If yes, all
   of boxflat's structural knowledge transfers and the project is straightforward.
   If no, we're decoding a new framing and the schedule changes — find out on day
   one, not in month two.
2. **What device id does the base answer on?** Racing base is 19. See
   [`02-protocol.md`](02-protocol.md).
3. **What does Cockpit's idle poll look like?** Identifying it early makes every
   later diff readable.
4. **Is there a handshake at connect?** Capture across a Cockpit start.
5. **Does a grip change anything on the config channel?** Swap MH16 → Alpha
   Prime with Cockpit open.

## The fast probe loop

Differential probing is only useful if an iteration is cheap. The first
implementation serialised every read — drain the line, send, wait, parse — which
cost about seven minutes per snapshot and made "change one thing and diff" a
half-hour round trip.

**The protocol does not require serialisation.** Every reply echoes the command
id, and indexed replies echo the index too, so a reply is self-identifying. Fire
the whole batch, then match replies to requests by their echo:

```
send  213 request frames back-to-back
poll  until every expected echo has been matched, or 700 ms
```

That takes **~0.1 s** for a complete 213-address snapshot — roughly 4000× faster,
with no loss of coverage (213/213 on every run). [`tools/snapshot.py`](../tools/snapshot.py)
implements it:

```
tools/snapshot.py capture before.json          # ~0.1s
   ... change exactly one setting in Cockpit, return the base to the host ...
tools/snapshot.py capture after.json
tools/snapshot.py diff before.json after.json  # prints "id 152 bank 0 slot 2: 100 -> 75"
```

The address list lives in [`data/protocol/ab9-manifest.json`](../data/protocol/ab9-manifest.json).
`snapshot.py discover` rebuilds it with a slow exhaustive sweep, for when
indices appear or disappear.

### It was validated before it was trusted

The fast path was checked against the slow one across all 213 addresses. Two
mismatched — ids 114 and 225 — and both turned out to be genuinely time-varying
under serialised reads as well, not pipelining errors. They are listed in the
tool's `VOLATILE` set alongside the live telemetry ids (184, 185, 215, 216) and
reported separately in a diff rather than silently dropped.

This check was not optional. An earlier scanner produced wrong values that
reproduced across three consecutive runs because the fault was systematic in the
method; speed makes that failure mode cheaper to hit, not rarer. Any change to
the read path gets re-validated against serialised reads.

## Method: safe probing on Linux

Independently of the VM, we can sweep the device ourselves — but only for
**reads**. A read command with an unknown id either returns data or is ignored;
neither outcome writes to EEPROM.

`tux-ffb-cli probe --scan-reads` walks plausible `(group, command_id)` space,
sends each read, and records which combinations reply and what the reply looks
like. This maps the readable surface without a VM and without risk.

Hard rules for the prober:

- **Reads only.** No write groups, ever, in scan mode. Not behind a flag, not
  behind a confirmation — a scan that can write is a scan that can brick.
- Rate-limit. A firmware being hammered with malformed frames is a firmware
  doing something we can't predict.
- Log every frame sent and received, verbatim, to a file. The log *is* the
  finding.

## Ask what the data would look like if you were wrong

Before running an analysis, state what the data would look like **if the opposite
hypothesis were true**. If the answer is "the same", the analysis is not evidence,
however clean its output.

This was learned three times in one afternoon, each time with a confident wrong
answer:

- A set of distinct output values cannot reveal a rescaling deadzone — it leaves
  no gap, only a flat region that a value-set discards.
- 0.3 s averaging bins cannot reveal an abrupt clamp edge — the bin straddling the
  edge reports a gradual slope, which then reads as a hand pause.
- A response curve's fold **output** values are invariant under a deadzone: the
  deadzone moves where along the travel the fold happens, not what value it
  happens at. Matching them confirms the curve and says nothing about the deadzone.

Related: when a person operating the hardware reports what they did, that is
ground truth about the input. Analysis of the output cannot overrule it, and a
plausible story that explains it away — "they must have paused" — is the failure
mode to watch for. Ask them.

## Cross-validation

A decode is not confirmed by looking plausible. It's confirmed when:

- **Read-back matches.** We write a value on Linux, read it back, and get what we
  wrote.
- **Cockpit agrees.** We write on Linux, then open Cockpit in the VM and see our
  value in its UI. This is the strongest check available and it should be run
  for every setting before it ships.
- **The hardware agrees.** For anything with a physical effect — soft limits,
  gain, spring — confirm by feel and by evdev readout, not just by numbers.

Anything that passes fewer than two of these stays at `confidence: inferred` in
the command table and behind `--unsafe` in the CLI.

## Recording findings

Every capture session produces a note in `docs/captures/`:

```markdown
# 2026-08-28 — AB9 X-axis range

Setup:    AB9 FW <version>, Cockpit <version>, MH16 grip attached
Control:  Axis Calibration → X range, 100% → 90%
Frames:   7e 05 2a 13 0c ... (annotated)
Decode:   write group 42, id [12], u16 big-endian, 0..65535 raw
Verified: read-back ✓, Cockpit UI ✓, evdev range ✓
```

These notes are the project's actual asset. Code can be rewritten; a capture
session with hardware you no longer own cannot.

## If the frame format doesn't match

Contingency, so it isn't a crisis if it happens: fall back to pure differential
analysis. Capture enough single-setting changes and the framing falls out of the
constant prefix, the varying middle, and the trailing byte that changes with
everything. It is slower, not impossible. The tooling (`tools/capture/`) is
written to be framing-agnostic for exactly this reason: it decodes to annotated
byte runs first, and applies the MOZA frame interpretation as a *layer*.
