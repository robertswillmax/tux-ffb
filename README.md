# tux-ffb

A Linux-native configurator for MOZA flight sim hardware, starting with the
**AB9** and **AB6** force-feedback flight bases.

MOZA ships no Linux tooling. Their Windows app, MOZA Cockpit, is the only way to
calibrate a flight base, and it does not survive Wine — the base's config link is
USB CDC-ACM, Cockpit drives it through `QSerialPort`, and Wine's serial layer is
missing `IOCTL_SERIAL_GET_DTRRTS`, so Cockpit reports "Disconnected" forever. A
Windows VM with USB passthrough works but is a heavy answer to "I want to change
my axis curve". `tux-ffb` is the light one.

The excellent [boxflat](https://github.com/Lawstorant/boxflat) already covers
MOZA's *racing* lineup. It deliberately does not handle the flight bases — its
device matcher only recognises `R*`-series wheelbases, and MOZA manages flight
gear through a separate app anyway. tux-ffb is the flight-side counterpart, and
it borrows boxflat's hard-won knowledge of the MOZA serial protocol under the
same licence.

## Status

**Pre-alpha, but it works.** The protocol is reverse-engineered and verified
against real AB9 hardware, and a working CLI reads and writes settings and runs
the base's cogging calibration — with no MOZA software involved.

```
$ tux-ffb-cli dump
  curve-points-x         [20, 40, 60, 80, 100]
  deadzone-x             2
  saturation-x           100
  invert-x               0
  grip-type              0
  ffb-intensity          70  (effect unverified)
  ...

$ tux-ffb-cli set deadzone-y 4 --expect 2
  OK: deadzone-y = 4 — read back 4 | Table 2, Param 60 Written

$ tux-ffb-cli calibrate --yes        # ~53s, repairs a lost cogging calibration
```

The GUI has four tabs: Overview (device, modes, live position, calibration),
Axes (a curve editor per axis with deadzone and saturation as its endpoints),
Forces (the effects, verified by feel on real hardware), and Profiles.

Settings whose *effect* on the hardware has not been observed are labelled as
such — storing a value and changing behaviour are separate claims, and this
project has been caught out by conflating them.

## Install

**Arch / CachyOS** — a `PKGBUILD` is in [`packaging/`](packaging/):

```
cd packaging && makepkg -si
```

**From source:**

```
uv build --wheel && pip install dist/tux_ffb-*.whl
sudo install -Dm644 packaging/70-tux-ffb.rules /usr/lib/udev/rules.d/
sudo udevadm control --reload && sudo udevadm trigger
```

The udev rule grants your desktop user access to the base. **Its filename
matters**: `uaccess` tags are processed by `73-seat-late.rules`, so the file must
sort before it — a `99-*` name sets the tag too late to have any effect.

Then run `tux-ffb` for the GUI, or `tux-ffb-cli` for the command line.

## Documentation

See [`docs/`](docs/) for the design documents,
[`docs/00-overview.md`](docs/00-overview.md) for scope and roadmap, and
[`docs/09-open-questions.md`](docs/09-open-questions.md) for what is still
unmapped.

## Scope, briefly

**What it does now**, from a GTK4 desktop app and a scriptable CLI, with no MOZA
software anywhere:

- Axis response curves, with deadzone and input saturation as the curve's own
  endpoints, plus invert
- Spring, damper, friction and inertia — globally and per axis
- Overall intensity, maximum torque, and adaptive centring
- Force-feedback mode, base mode, and the grip decode mode
- Cogging torque calibration, run from Linux
- Named profiles, saved as plain YAML

**What it cannot do.** The base decodes the grip's buttons in *firmware*, and
`grip type` only selects which of four decode modes it uses. So tux-ffb can set
the right mode — and stop you picking a wrong one, which kills your buttons
silently — but it cannot fix a grip the base decodes badly. Inputs that never
reach the HID report are not recoverable by anything downstream.

**Later:** a telemetry-driven FFB layer for sims that don't send DirectInput
force feedback.

A game that speaks DirectInput FFB — DCS World — needs none of this to *fly*.
The kernel's generic `hid-pidff` path drives the AB9 with no host software at
all. tux-ffb exists to make the base *feel right* before you launch.

## Licence

GPL-3.0-only. See [LICENSE](LICENSE) and [`docs/08-licensing.md`](docs/08-licensing.md).
