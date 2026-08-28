# 07 — Safety

We are sending undocumented commands to expensive hardware over a channel the
vendor also uses for firmware updates. This document exists so that "we were
careful" is a design property and not a hope.

## Threat model

What can actually go wrong, roughly in order of likelihood:

1. **A bad setting makes the base behave badly.** Recoverable — read it back,
   fix it, or restore a backup. Annoying, not serious.
2. **A write lands in a setting we misidentified.** Now the user's carefully
   tuned soft limits are gone and they don't know why. Recoverable *if* we took a
   backup first, which is why backups aren't optional.
3. **A malformed frame confuses the firmware** into a state a power cycle
   doesn't clear.
4. **We accidentally trigger a firmware-update or EEPROM-erase path** and brick
   the base. Unrecoverable without vendor tooling, possibly unrecoverable at all.

Risks 3 and 4 are why the rules below are absolute rather than defaults.

## Rules

### Reads are free, writes are earned
Read commands with unknown ids are safe: the device answers or ignores us. Write
commands are never sent speculatively. The protocol prober is **read-only in
code**, not by configuration — there is no flag that makes it write.

### A group is a write group until the firmware says otherwise

boxflat's command table labels each entry `read:` and `write:`. Those labels
describe **racing** firmware and are not a safety boundary on a flight base. We
learned this the mild way on 2026-08-28: a probe sent a group-31 frame because
boxflat lists group 31 as the read group for `get-compat-mode`, and the AB9's
firmware answered from a handler it calls `Main_set`. The command id didn't
exist, so nothing was written — but the frame reached a set handler.

The authority is the device. A group is treated as potentially destructive until
the firmware's own error text, or a capture, confirms it is a get handler. The
prober's group allowlist is populated from confirmed handlers only, never from
boxflat's labels.

### Every setting needs a verified read path
If we can't read a value back, we don't offer to write it. A write we can't
verify is a write we can't undo intelligently, and it's how silent corruption
starts.

### Verify effect, not just read-back

Read-back proves the base accepted a value. It does not prove the value does
anything, and the two need separate evidence: confirm each setting against
observable behaviour — evdev output, or measurable force — not merely against a
read of what we wrote.

On the AB9 as of 2026-08-28 both settings tested this way — the response curve
and the deadzone — *are* applied in firmware, so this is a precaution rather than
a known failure mode on this device. An earlier version of this rule cited the
deadzone as a setting that stored but did nothing; that was a measurement error,
now retracted. The precaution stands on its own merits.

Do not generalise effect from a neighbouring setting: adjacent entries in the
command table are unrelated code paths.

### Backup before first write
The first time tux-ffb writes to a base, it first takes a full readable-config
snapshot to `~/.local/share/tux-ffb/backups/<device>-<timestamp>.yaml`, without
asking. Cheap, and it's the difference between "restore your backup" and "open
Windows".

### Safety classes are enforced in the transport, not the UI
Every command entry has a class, and the check lives at the bottom of the stack
where nothing can route around it:

| class | behaviour |
|---|---|
| `normal` | Sent freely. |
| `destructive` | Requires explicit confirmation (GUI dialog / CLI `--yes`). Resets, calibration wipes. |
| `forbidden` | **Never sent.** Firmware update, EEPROM erase, bootloader entry, and the motor/calibration registers 193, 195 and 222. No flag enables these. |

**A fourth class exists that backups do not cover: destructible-and-unrecoverable.**
The classes above assume a bad write can be undone by restoring a snapshot. The
AB9's cogging torque calibration cannot: the data is not in our readable address
space, so there is nothing to back up, and no power cycle rebuilds it — only a
user-initiated calibration in MOZA Cockpit. It was destroyed once in this project,
on 2026-08-28, and the stick was unusable until the vendor tool regenerated it.
Anything touching motor state is `forbidden`, and "I'll take a backup first" is
not a mitigation there.

**`id 194` is the exception, and it is the cure rather than the disease.** Writing
`0` to it starts the cogging calibration — captured from Cockpit on 2026-08-28 —
and reading it returns percent complete. It is `destructive`, not `forbidden`: it
takes ~53 seconds, drives the motor, must not be interrupted or run while the
stick is being handled, and requires explicit confirmation. But it means tux-ffb
can *repair* a wiped calibration rather than sending the user to Windows.

`forbidden` commands are still *catalogued* — knowing which ids to avoid is
precisely why we identify them.

### Confidence gates transmission
Commands at `confidence: inferred` or `guessed` require `--unsafe` on the CLI
and are hidden in the GUI. Confidence is raised by evidence — a capture, a
read-back, a Cockpit cross-check — never by "it seemed to work".

### Vendor limits are not device limits

MOZA Cockpit clamps its deadzone field to a stated maximum of 25 — in the display
only. Typing 39 shows 25 and **writes 39**, which the base accepts and stores.

So a setting has two ranges, and the table records both: `ui_range` (what Cockpit
exposes, and our default clamp) and `device_range` (what the firmware has been
observed to accept). Writing beyond `ui_range` is permitted but never silent — it
leaves the vendor's tested envelope, and the user is told so.

The corollary is the cautious one: **the absence of a firmware range check is not
permission.** That a value is accepted says nothing about whether it is safe or
even applied. Values outside `ui_range` stay at `confidence: inferred` until
their effect is observed on the hardware.

### Rate limiting
Writes are rate-limited and coalesced. A dragged slider produces one write on
release, not sixty. This protects both the EEPROM write budget and the firmware's
input handling.

### Fail closed
Checksum mismatch, unexpected length, unknown group: drop the frame, log it,
resync. Never guess at a partial frame's meaning. The log is what turns a weird
one-off into a filed finding.

## Recovery

Document, and test, the recovery paths before they're needed:

- **Restore from backup:** `tux-ffb-cli restore <file>`.
- **Factory reset:** if the protocol exposes one, catalogue it as `destructive`
  and expose it deliberately — a working reset is a safety feature.
- **MOZA Cockpit in the VM** remains the ultimate fallback for anything we've
  broken, for as long as the dev machine has it. Worth keeping installed for
  exactly this reason.

## On testing against the only AB9 we have

The development hardware is also the user's flight hardware. Bricking it ends
the project. So: captures and read-only probing come first, writes are attempted
only against settings confirmed by capture, and a backup exists before the first
one. If a write path can't be confirmed by capture, it waits for a second unit
rather than being tried hopefully.
