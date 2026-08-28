# 01 — Architecture

## Shape

Three layers, one direction of dependency. Nothing below imports anything above.

```
        ┌──────────────────┐   ┌──────────────────┐
        │  gui/  (GTK4 +   │   │  cli/            │
        │  libadwaita)     │   │  tux-ffb-cli     │
        └────────┬─────────┘   └────────┬─────────┘
                 └──────────┬───────────┘
                   ┌────────▼─────────┐
                   │  core/           │  no toolkit imports, ever
                   │  transport,      │
                   │  protocol, model │
                   └────────┬─────────┘
                   ┌────────▼─────────┐
                   │  data/  (YAML)   │  device + grip profiles,
                   │                  │  command tables
                   └──────────────────┘
```

The rule that keeps this honest: **`core/` must be importable with no GTK, no
display, and no user session.** If it isn't, the CLI stops working over SSH and
the future FFB daemon inherits a GUI dependency. A test enforces it.

## Modules

```
src/tux_ffb/
  core/
    transport.py    Serial port lifecycle, reader/writer threads, reconnect
    framing.py      Frame encode/decode, checksum, stream resync
    commands.py     Command table loader; name → (group, id, type, bytes)
    discovery.py    udev-based device detection and hotplug
    device.py       Device objects: capabilities, settings, read/write
    settings.py     Setting descriptors — type, range, unit, safety, provenance
    hid.py          Read-only evdev/hidraw: live axes, buttons, FFB capability
    profiles.py     User profiles: save, load, diff, apply
    backup.py       Full-config snapshot and restore
  cli/
    main.py         Argument parsing, subcommands
    probe.py        Protocol exploration (read-only sweeps)
  gui/
    main.py         Adw.Application entry point
    window.py       Main window, view switcher
    panels/         One module per page — see 04-ui.md
    widgets/        Curve editor, axis visualiser, button map grid
data/
  devices/          ab9.yaml, ab6.yaml, generic.yaml
  grips/            mh16.yaml, virpil-alpha-prime.yaml, virpil-f14.yaml
  protocol/         moza-serial.yaml (command table)
tools/
  capture/          usbmon capture + decode harness (see 06-protocol-acquisition.md)
```

## Concurrency

boxflat runs its serial handler in a forked `multiprocessing.Process` with
reader and writer threads inside it, queues across the boundary. That's more
machinery than we need: our traffic is bursty request/response at human speed,
not a continuous telemetry stream.

**Our model:** one background thread per device for reading, a queue for
writing, and an event dispatcher onto the main loop. In the GUI that means
`GLib.idle_add`; in the CLI it means a plain callback. The transport never
touches UI objects directly and never blocks the main thread.

If the telemetry FFB daemon later needs a real-time path, it gets its own
process — it does not retrofit the config transport.

## Device discovery

`pyudev` monitors for `subsystem=tty` with `ID_VENDOR_ID=346e`. On add:

1. Read the USB device's `idProduct` and `product` string.
2. Look up a device profile in `data/devices/` by PID.
3. Unknown PID → load `generic.yaml`, mark the device *unrecognised*, expose
   only reads and the shared command set, and prompt the user to contribute a
   dump.
4. Open the port, run the identity read, populate the model.

Polling is a fallback, not the primary path: the base is powered separately and
is frequently off, so the app must handle "appears an hour after launch"
gracefully. The window should show a clean "no base connected" state rather than
an error.

**Coexistence with boxflat:** we filter to flight PIDs. A `346e` tty belonging
to an R-series wheelbase is not ours; we ignore it and say so in the log. Two
apps racing for one port produces exactly the kind of intermittent bug nobody
can reproduce.

## Permissions

The base's tty and hidraw nodes need to be reachable by the desktop user. The
rule that works (already deployed on the dev machine as
`/etc/udev/rules.d/72-moza.rules`):

```
KERNEL=="hidraw*",  ATTRS{idVendor}=="346e", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="usb",   ATTRS{idVendor}=="346e", MODE="0660", TAG+="uaccess"
SUBSYSTEM=="tty",   ATTRS{idVendor}=="346e", TAG+="uaccess"
```

**The filename matters.** `uaccess` tags are processed by
`73-seat-late.rules`, so the file must sort *before* it. A `99-*.rules` file
sets the tag too late to have any effect — this is a real trap that costs an
afternoon. We ship `70-tux-ffb.rules` and the app detects the missing-permission
case explicitly, telling the user what to install rather than failing with
`PermissionError`.

Note that boxflat ships `99-boxflat.rules`, which is subject to the same
constraint. Do not assume a machine with boxflat installed already has working
permissions.

## Data files, not code

Device capabilities, command tables and grip layouts are YAML in `data/`, not
Python. Three reasons: a user can add a device without touching code; a bug
report can include a data file; and the same tables can eventually be shared
with boxflat.

## Distribution

- **Primary: AUR.** The audience is disproportionately Arch-adjacent (CachyOS,
  Nobara, SteamOS-alikes), and PyGObject/GTK4 come from the distro anyway.
- **Then Flatpak**, for everyone else. Needs `--device=all` for tty and hidraw
  access; the udev rule still has to be installed on the host, which is a known
  Flatpak wart to document rather than solve.
- **pip install** works for the CLI alone (`pyserial`, `pyudev`, `PyYAML` are all
  wheels). PyGObject is not a reasonable pip dependency, hence the `gui` extra.
