# 05 — Telemetry-driven force feedback (future, M5)

**Not part of v1.** Recorded now so v1's architecture doesn't foreclose it.

## Why it's not urgent

The first users are DCS World and Falcon BMS players. Both send **DirectInput
force feedback** to the stick, and the kernel's generic `hid-pidff` path already
delivers that to the AB9 with no host software at all — constant, spring, damper,
friction, inertia, ramp and every periodic waveform. Those users need
configuration, not an FFB layer, which is exactly why configuration is v1.

MOZA's own advice to "keep Cockpit running in the background" applies only to
*telemetry-driven* FFB, which is a different feature for a different set of sims.

## What it would be for

Sims that don't send DirectInput FFB, and effects a sim can't express through
it: buffet approaching stall, gear and flap transitions, gun and cannon
vibration, ground roll and touchdown, airframe damage. On Windows this is what
FFB-Bridge and SimShaker-style tools do, and the Linux side has nothing —
FFB-Bridge itself is MSFS/X-Plane only, so it covers neither BMS nor DCS.

## Shape

A separate daemon, `tux-ffb-ffbd`, not part of the config app:

```
sim telemetry  ──►  source adapter  ──►  effect engine  ──►  evdev FF uploads
(DCS Export.lua                        (mixer, curves,      (constant/periodic
 UDP, BMS shared                        clamps, per-        effects on the
 memory, X-Plane)                       aircraft profiles)   base's event node)
```

- **Source adapters** are plugins. DCS via `Export.lua` over UDP is the obvious
  first one; the DCS-BIOS ecosystem has already solved the transport.
- **The effect engine** maps telemetry channels to force effects with per-aircraft
  profiles.
- **Output** is standard evdev force-feedback uploads. No custom driver, no
  kernel work — and note `FF_CUSTOM` is unavailable on the AB9, so effects must
  be composed from the standard set.

## Trim following belongs here, not in the configurator

Cockpit exposes a block of trim and autopilot-follow settings — follow ratios,
stick follow rates, breakout force strength and range, per-axis follow rates.
**Twelve of the thirteen are not reachable in the base's command space at all**
(see [`captures/2026-08-28-ab9-trim-settings-not-in-mapped-space.md`](captures/2026-08-28-ab9-trim-settings-not-in-mapped-space.md)),
while the one DirectInput-mode setting is.

The likely reason is that trim *following* is a telemetry-driven behaviour rather
than a firmware one. "No follow", the mode DCS uses, lets the game drive the
logical centre while the stick at that centre reports zero. The follow modes move
the physical stick with the trim so an aft-trimmed aircraft presents as a stick
held back — which requires a host application feeding trim state to the base.

Two consequences:

1. **The configurator is not missing anything its users need.** In "no follow"
   these settings are inert, and "no follow" is correct for DCS.
2. **A telemetry layer would implement this behaviour, not write these settings.**
   Trim following is a feature to provide, and the DirectInput trim rate at id
   196 is the one piece of it the firmware already owns.

## Open questions to answer before building it

1. **Coexistence.** The game already holds the evdev FF device and is uploading
   its own effects. Can a second client upload effects to the same device
   simultaneously, and does the kernel mix them sanely, or does it fight? This
   is the question the whole feature stands on — test it with a throwaway script
   long before writing a daemon.
2. **Effect slot budget.** PID devices have a finite number of effect slots. If
   DCS uses most of them, how many are left?
3. **Latency.** UDP telemetry → effect upload has to stay well inside a frame to
   feel connected rather than laggy.
4. **Under Proton.** The game runs in a Wine prefix and reaches the device
   through winebus. Whether a native Linux process can share the device with a
   Proton one is not obvious and must be tested, not assumed.
5. **Real-time headroom.** If Python can't hold the timing, this component gets
   rewritten in a compiled language. It's a daemon with a narrow interface, so
   that's a contained decision — which is the point of keeping it out of the
   config app.

## What v1 must do to keep this possible

Only one thing, and `core/` already does it: stay free of GUI dependencies and
keep the evdev layer separate from the serial layer. The daemon should be able to
import `tux_ffb.core.hid` and `tux_ffb.core.profiles` and nothing else.
