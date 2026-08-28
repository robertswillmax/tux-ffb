# tux-ffb design documents

Read in order on first pass; after that they stand alone.

| Doc | What's in it |
|---|---|
| [00 — Overview](00-overview.md) | The problem, scope, non-goals, users, roadmap |
| [01 — Architecture](01-architecture.md) | Layers, modules, discovery, permissions, packaging |
| [02 — Protocol](02-protocol.md) | MOZA serial framing, addressing, command table, known unknowns |
| [03 — Device model](03-device-model.md) | Bases, capabilities, grips, settings taxonomy |
| [04 — UI](04-ui.md) | GTK4/libadwaita layout, pages, live data, CLI parity |
| [05 — Telemetry FFB](05-ffb-telemetry.md) | The future M5 layer, and what v1 must not foreclose |
| [06 — Protocol acquisition](06-protocol-acquisition.md) | **Critical path.** Capture method, probing, validation |
| [07 — Safety](07-safety.md) | Threat model and the rules that keep the hardware alive |
| [08 — Licensing](08-licensing.md) | GPL-3.0-only, boxflat reuse, provenance |

`captures/` holds capture-session findings — see the [template](captures/TEMPLATE.md).
Those notes are the project's real asset.
