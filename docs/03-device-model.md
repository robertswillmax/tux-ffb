# 03 — Device and grip model

## Why a model at all

The naive shape for this app is "a screen of sliders for an AB9". That falls over
the first time someone plugs in an AB6, and it falls over badly the first time
someone plugs in a base we've never seen. So: a base is a *set of capabilities*
discovered at runtime, and the UI is generated from what the device actually
reports, not from a hardcoded assumption about which device it is.

## Bases

```yaml
# data/devices/ab9.yaml
id: ab9
name: MOZA AB9 FFB Base
usb: { vendor: 0x346e, product: 0x1000 }
serial_device_id: 19        # UNVERIFIED — see 02-protocol.md
axes:
  - { id: x, label: Roll,  ffb: true }
  - { id: y, label: Pitch, ffb: true }
capabilities:
  - axis-range
  - axis-centre
  - axis-curve
  - soft-limits
  - ffb-gain
  - spring
  - damper
  - friction
  - inertia
  - force-sensing        # AB9-specific, semantics not yet known
  - z-axis-module        # twist/rudder add-on registration
settings: [ ... ]        # references into the command table
```

Known-good facts about the AB9, verified on hardware:

- `346e:1000`, product string "MOZA AB9 FFB Base".
- Two force-feedback axes. MOZA markets it as an "Active Shifter" for sim
  racing; it is used here as a 2-axis FFB flight base, and the docs should never
  call it a shifter.
- Binds `hid-generic`. Generic `hid-pidff` exposes constant, spring, damper,
  friction, inertia, ramp, all periodic waveforms, and gain. `FF_CUSTOM` and
  `FF_AUTOCENTER` are absent.
- Axis calibration persists in firmware: read on Linux with no MOZA software
  present gives full 0–65535 travel, centred within ~2%.
- **Cogging torque IS a user calibration** — corrected 2026-08-28. It is
  user-initiated from Cockpit, it is **not** rebuilt by the power-on sequence,
  and losing it makes the stick flop under the grip's weight while powered.
  Validity is readable at `id 195`, completion at `id 194`. This is the most
  destructible state on the device: it is not in our readable address space, so
  it cannot be backed up, and only the vendor tool regenerates it. See
  [`captures/2026-08-28-ab9-cogging-calibration.md`](captures/2026-08-28-ab9-cogging-calibration.md).
  Cockpit's calibration also covers axis range/centre, soft limits, Z-axis module
  registration, and force-sensing mode.
- Powered separately from USB, so it is frequently absent from the bus.

### The AB6

**Assumed similar, verified as nothing.** We do not have one, we do not know its
PID, and we do not know whether it shares the AB9's command set. The plan is:
build the AB9 path properly, keep everything device-specific in `ab9.yaml`, and
add `ab6.yaml` when someone with the hardware runs `tux-ffb-cli probe --dump`.
Shipping a guessed AB6 profile would be worse than shipping none — a wrong write
to an unknown base is the one outcome we can't take back.

### Unknown bases

Any `346e` tty whose PID we don't know loads `generic.yaml`: identity read,
firmware version, live evdev axis display, and nothing writable. The UI says
plainly that the device is unrecognised and points at the contribution guide.
This is the difference between "tux-ffb doesn't support my base" and "tux-ffb
crashed".

## Grips

This is where the project can be *better* than the vendor tool rather than
merely native, which is a pleasant thing to be able to say about a
reverse-engineered clone.

MOZA's own grip handling is thin, and it has nothing at all to say about
third-party grips. Meanwhile the hardware reality is that people mount whatever
grip they like on whatever base they own, and then spend an evening in DCS
working out that "Button 14" is the pinky lever.

### Resolved: the grip is a stored selection

**Answered 2026-08-28.** Of the three possibilities below, the third-simplest
holds: the base does **not** identify the fitted grip. Its heartbeat reports
`stick_reg` whatever is attached, and `id 92` — the grip type — accepts a value
for hardware that is not plugged in. Grip support therefore needs no protocol
work: it is a stored enum (`0` = MH16, `17` = Alpha Prime, `32` = WinWing WW-16,
catalogue partial) plus our own profile data.

That is good news for the "better than MOZA" goal in
[`00-overview.md`](00-overview.md): since the base is indifferent to what is
actually attached, every bit of grip intelligence lives in host software, and
ours can simply be better. See
[`captures/2026-08-28-ab9-grip-type-confirmed.md`](captures/2026-08-28-ab9-grip-type-confirmed.md).

### Original hardware question (kept for context)

How a non-MOZA grip presents itself to a MOZA base is **not yet known**, and it
gates the whole grip feature. The possibilities:

1. **The base reads the grip and reports its buttons as its own.** Then a grip
   profile is pure presentation — naming, hat modelling, layout — layered over
   button indices the base already reports, and we can support any grip on any
   base with zero protocol work.
2. **The base identifies the grip over the config channel** (a grip id, like
   "wheel" is a distinct device id on the racing side). Then we can detect the
   grip automatically, and possibly configure it.
3. **The grip enumerates separately over USB** (VIRPIL grips on a VIRPIL base do
   this — the MongoosT-50CM3 base is `3344:0391` with its own config channel on
   if01). Then a third-party grip on a MOZA base is really two devices, and we
   manage them independently.

Answer this early — it's cheap. Plug the MH16 in, dump the base's button
reports and its config-channel identity reads, swap to the Alpha Prime, diff.

### Presenting the grip: four modes, not thirty-four ids

Cockpit's dropdown holds **ten** entries — MH16, MA3X, FCS, V Alpha, V Alpha
Prime, V 50-2, V FLNKR, Tianhang, WW-16, Generic — while the catalogue spans ids
0–33. Dropdown position is **not** the catalogue id: Alpha Prime is fifth in the
list and id 17; WW-16 is ninth and id 32.

The names could be reconstructed from the mode map (the four VIRPIL grips fill
the four-wide mode-2 block exactly, and the two singleton modes take WW-16 and
Generic), but that is inference, and a wrong grip id is a user-visible failure —
it kills their buttons.

**So tux-ffb offers the four decode modes instead**, each labelled by a grip that
uses it, with a note that unlisted grips need trying until the buttons work:

| offered | writes catalogue id | covers |
|---|---|---|
| MH16 | 0 | ids 0–15, 20–31 |
| WW-16 | 32 | id 32 |
| VIRPIL grips | 17 | ids 16–19 |
| Generic | 33 | id 33 |

This is honest about what is known. The mode is what governs button decoding, so
four accurate choices beat thirty-four labels of which thirty-one would be
invented.

### Grip profile

Whatever the answer, the profile format is the same:

```yaml
# data/grips/mh16.yaml
id: mh16
name: MOZA MH16
vendor: MOZA
detect:
  # populated once we know how detection works; may be a base-reported grip id,
  # a USB id, or nothing at all (manual selection)
buttons:
  - { index: 1, name: Trigger stage 1, kind: trigger }
  - { index: 2, name: Trigger stage 2, kind: trigger }
  # ...
hats:
  - { id: hat1, name: Trim, mode: 4-way, buttons: [5, 6, 7, 8] }
layers:
  # shift states: a modifier button that remaps the rest of the grip
leds:
  # if the grip has addressable lighting and the base exposes it
```

Targets, in order: **MOZA MH16** (on hand), **VIRPIL Alpha Prime** (on hand),
**VIRPIL F-14** (probable). Each ships with correct button names, hat modelling,
and a suggested DCS binding reference — the last of which costs us nothing and
saves every user the same evening.

### What "better than MOZA" concretely means — revised 2026-08-28

The original claim here was that tux-ffb could support grips better than MOZA
does, because "all grip intelligence lives in host software". **That is only half
true, and the false half matters.**

The AB9's firmware decodes the grip's electrical signalling into its 80 HID
button codes and 10 axes, and `id 92` selects *which decode mode* it uses from a
set MOZA implemented. We are not writing firmware. So the line falls here:

**Reachable — genuinely better than the vendor tool:**

- Correct, human button names for third-party grips instead of bare indices.
- Hats modelled as hats, including 4-way vs 8-way and analogue vs digital.
- Shift layers, multiplying usable button count — standard in the VIRPIL/VKB
  world and absent from Cockpit.
- Profiles that are text files you can share.
- Per-aircraft binding references.
- Setting the right decode mode automatically as part of a grip profile, since
  choosing it wrongly breaks buttons entirely (verified on hardware: selecting
  WW-16 with an MH16 fitted left the buttons non-functional).

**Not reachable — a firmware limit, not a software gap:**

- Fixing a grip whose buttons or axes decode *incorrectly* in every available
  mode. Information that never reaches the HID report cannot be recovered by
  anything downstream. A userspace remapper can relabel and rearrange what
  arrives; it cannot invent what didn't.
- Improving axis resolution, scaling or sampling of the grip's own inputs.

This is a real reduction in scope from the project's original ambition, and it is
recorded rather than quietly dropped. The honest summary: tux-ffb can make a
correctly-decoded grip much nicer to use, and can stop users from selecting the
wrong mode — but it cannot rescue a grip the base decodes badly.

**That avenue was tested and is closed.** Sweeping every value into `id 92` found
a catalogue of exactly 34 entries (`0`–`33`, higher values rejected) mapping onto
**four** decode modes — all of them reachable from Cockpit's dropdown. There is
no hidden mode to expose.

What the map does buy, modestly: a grip that MOZA does not list can be aimed at
the right compatibility group (an unlisted VIRPIL grip belongs in mode 2, ids
16–19), and a wrong selection becomes a diagnosable failure rather than a mystery
— Cockpit never explains why the buttons died. See
[`captures/2026-08-28-ab9-grip-mode-catalogue.md`](captures/2026-08-28-ab9-grip-mode-catalogue.md).

## The axis model, confirmed on AB9 hardware

This is the first part of the device model backed by measurement rather than
assumption. Every element below has been read, written, or observed to change in
response to a known cause.

**An axis is one object: a response curve with movable endpoints.** It is *not* a
curve plus a separate deadzone plus a separate saturation, which is how the
vendor UI presents it and how this project first modelled it.

```
        output
        100 ┤                                   ●  slot 6
            │                            ●         slot 5
            │                     ●                slot 4   <- these are
            │              ●                       slot 3      OUTPUT values
         20 ┤       ●                              slot 2
          0 ┼───────●──────────────────────────┬─────────  input
                 slot 1                   saturation
              = deadzone                (right node x)
              (pinned at output 0)
```

| element | address | encoding |
|---|---|---|
| curve output points | `(149 \| 150, bank 1, slots 2–6)` | integer percent |
| left node x — "deadzone" | `(151 \| 152, bank 0, slot 1)` | integer percent of input travel, default 2 |
| right node x — "saturation" | `(151 \| 152, bank 0, slot 2)` | integer percent, 100 = at the edge |
| invert | `id 158` (X) | 0/1 — Y partner unconfirmed, `162` suspected |

Lower id is X, higher is Y. Bank 0 of the curve ids holds an untouched linear
reference copy; bank 1 is the live curve.

**The curve has six nodes, not five.** Slot 1 is pinned at output 0 and sits at
the deadzone position. Drawing only slots 2–6 produces a cliff from 0 to 20 at
the deadzone edge instead of a flat run followed by a ramp — a bug this project
shipped in its first GUI build.

**The curve is defined *after* the deadzone.** Setting the deadzone to 90 leaves
the stored curve unchanged at `20, 40, 60, 80, 100`: the values are output levels
across whatever travel remains between the endpoints, not across the full
physical range. So shrinking the span makes the ramp steeper — the remaining
travel still has to reach 100%. Corroborated independently: at deadzone 39 the
axis output is *continuous* through centre, largest discontinuity 83 counts,
where a curve spanning the full range with a separate clamp would show a
~12,800-count cliff.

**The one-id-per-axis layout is specific to axis shaping.** The force-feedback
effect block puts both axes inside one id as slots (`0,1` = roll, `2,3` = pitch),
confirmed by force. Do not assume consecutive ids are an axis pair outside
147–152.

**Consequences for the UI.** Present an axis as a single curve editor with
draggable endpoints, not three controls. Editing the deadzone field and dragging
the left node are the same operation — Cockpit itself links them bidirectionally.
Interior points are output values, so moving the endpoints rescales the input
span and cannot change the curve's shape; a non-monotonic curve stays
non-monotonic however the ends are dragged. The editor should be able to say so.

**Nothing here is inferred from boxflat.** It came from differential capture
against the user's own hardware, and the endpoint mapping was confirmed by
predicting two register values from reported node positions before reading them.

## Settings taxonomy

Every setting carries: id, label, type, range, unit, default, capability tag,
command-table reference, safety class, and provenance. The UI renders from this,
so a new setting is a data change, not a UI change. A setting with no verified
read path is not shown by default — if we can't confirm what we wrote, we don't
offer to write it.
