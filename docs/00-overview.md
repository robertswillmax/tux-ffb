# 00 — Overview, scope and roadmap

## The problem

MOZA's flight lineup (AB9, AB6 and the grips that mount on them) has no Linux
configuration path. Three routes exist today and all three are bad:

| Route | Verdict |
|---|---|
| MOZA Cockpit under Wine | **Dead end.** Verified 2026-07-29/30. Cockpit talks to the base over USB CDC-ACM via `QSerialPort`; Wine doesn't implement `IOCTL_SERIAL_GET_DTRRTS` (0x1b0078), so Qt's `pinoutSignals()` fails and every write is skipped. Patching around it hits MOZA's own worker watchdog (`stuck in onReadyRead ~3500 ms` against a 3000 ms threshold) and reconnects every ~14 s. Also: the polling rate under Wine is not good enough for the app to stay in sync. |
| Windows VM with USB passthrough | **Works, but heavy.** A whole VM to move a slider. Settings persist in the base's EEPROM, so it's one-off per change — but it's still a VM. |
| boxflat | **Not applicable.** Its device matcher is `gudsen (moza )?r[0-9]{1,2} (ultra base\|base\|racing wheel and pedals)` on both the HID and serial-by-id paths, so "MOZA AB9 FFB Base" never registers. This is by design: boxflat replaces MOZA Pit House (racing), and MOZA manages flight gear in a separate app. |

Meanwhile the *flying* part already works. The AB9 (`346e:1000`) binds to
`hid-generic` and the kernel's generic `hid-pidff` path exposes constant, spring,
damper, friction, inertia, ramp, every periodic waveform, and gain on its evdev
node. Only `FF_CUSTOM` and `FF_AUTOCENTER` are missing. DCS World and Falcon BMS
use DirectInput FFB and need no host software at all.

So the gap is narrow and specific: **there is no way to configure the base on
Linux.** That's what tux-ffb fills.

## What tux-ffb is

A GTK4/libadwaita desktop app plus a scriptable CLI that speak the MOZA serial
protocol directly over the base's CDC-ACM channel (`/dev/ttyACM*`), with no MOZA
software, no Wine, and no VM.

## Goals, in shipping order

1. **Configure an AB9 for DCS.** Axis range and centre, soft limits, response
   curves, spring/damper/friction/inertia, FFB gain. This is the whole v1.0.
2. **Cover the AB6** on the same code path, on the assumption it's the same
   protocol family with a smaller capability set. Assumption, not fact — see
   [`03-device-model.md`](03-device-model.md).
3. **Grips as first-class objects.** A grip profile system that names buttons
   correctly, models hats and shift layers, carries the right firmware decode
   mode, and covers the MOZA MH16, VIRPIL Alpha Prime and WinWing grips.

   **Scope corrected 2026-08-28:** the base decodes the grip's signalling in
   *firmware*, and we only choose among the modes MOZA implemented. So we can
   make a correctly-decoded grip much nicer to use — and prevent the
   wrong-mode-breaks-your-buttons failure — but we cannot fix a grip the base
   decodes badly. Inputs that never reach the HID report are unrecoverable
   downstream. See [`03-device-model.md`](03-device-model.md).
4. **Profiles per aircraft/sim,** exportable and shareable.
5. **Telemetry-driven FFB** for sims without DirectInput FFB. Explicitly not v1
   — see [`05-ffb-telemetry.md`](05-ffb-telemetry.md).

## Non-goals

- **Firmware flashing.** The protocol almost certainly carries firmware update
  commands. We will identify them so we can *refuse to send them*. Bricking a
  £400 base is not a supported feature.
- **Racing wheelbases.** boxflat does this well. If a user has both, they should
  run both. We will not duplicate its panels or fight it for the serial port.
- **Windows or macOS.** The whole point is that Linux is the underserved case.
- **Replacing the kernel FFB path.** The base already works for DirectInput sims.
  tux-ffb configures; it does not sit in the flight loop (until the optional
  telemetry layer, which is opt-in and separate).

## Users, in the order they'll arrive

1. **DCS/BMS players on Linux with an AB9.** They want basic configuration so
   the stick behaves. They already have working FFB. This is v1's entire
   audience, and it's small and reachable (the Linux sim community talks to
   itself in a handful of Discords and subreddits).
2. **People who bought a third-party grip** and found MOZA's software has no
   idea what it is.
3. **Everyone else with MOZA flight gear** as device coverage grows.

## Roadmap

Milestones are gated on evidence, not calendar.

### M0 — Foundations (this repo, now)
Design docs. Capture harness and protocol probe tooling. No GUI, no writes.
**Exit:** we can passively record MOZA Cockpit ↔ AB9 traffic from the VM and
decode it into frames.

### M1 — Read-only AB9
Device discovery over udev, serial transport, frame codec, command table for
everything we've decoded. CLI can dump firmware version and current settings;
live axis readout from evdev.
**Exit:** `tux-ffb-cli dump` prints the base's real configuration, and the values
match what MOZA Cockpit shows in the VM. That cross-check is the proof the
decode is right.

### M2 — Writes, and the v1.0 release
Axis calibration, curves, soft limits, FFB gain, spring/damper/friction/inertia.
Full config backup/restore before any write. GTK4 GUI with the panels in
[`04-ui.md`](04-ui.md). AUR package.
**Exit:** a DCS player can set up an AB9 end to end without touching Windows.

### M3 — Breadth
AB6. Grip profiles for MH16, Alpha Prime, F-14. Per-sim profiles with
import/export. Capability model generalised so an unknown base degrades to
"what we can read" instead of refusing to start.
**Exit:** a second person's hardware works without a code change.

### M4 — Distribution and polish
Flatpak, udev rules packaged properly, translations, docs for contributing a
device dump.

### M5 — Telemetry FFB (separate, optional)
A daemon that turns sim telemetry into PID effects for sims that don't send FFB
themselves. Ships as its own component with its own on/off switch.

## Guiding decisions

- **The CLI is not a second-class citizen.** It's the debugging tool, the
  scripting surface, and the thing that works over SSH. The GUI is a client of
  the same core library, never a superset of it.
- **Read before write, always.** Every write path has a read path that verifies
  it. Unverified commands stay behind an explicit `--unsafe` flag.
- **Unknown hardware degrades gracefully.** A base we don't recognise still gets
  discovery, firmware readout, and the generic command set. It never gets a
  silent failure or a wrong write.
- **Evidence lives in the repo.** Every command in the table cites how we know
  what it does: a capture, a boxflat cross-reference, or a hardware test.
