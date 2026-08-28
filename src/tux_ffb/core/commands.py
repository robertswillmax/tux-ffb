"""The settings table: what exists, where it lives, and what may be written to it.

Loaded from data/protocol/ab9-settings.yaml. Everything in that file was
established by differential capture against real hardware, and each entry records
its provenance and whether its *effect* has been observed — a separate claim from
whether it stores (docs/07-safety.md).
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from pathlib import Path

import yaml

# Motor and calibration registers. Writing these caused real damage on
# 2026-08-28; none has a known legitimate use. No flag enables them.
# 195 was here too, on the theory that it was a calibration-validity flag.
# A Cockpit capture shows it is hardware trim mode. Removed.
FORBIDDEN_IDS = {193, 222}

def _default_table() -> Path:
    """Locate the settings table.

    Installed, it sits beside the package; from a source checkout it is at the
    repository root, where the docs reference it. Try the packaged copy first
    so an installed build never picks up a stray checkout.
    """
    packaged = Path(__file__).resolve().parent.parent / "data" / "protocol" / "ab9-settings.yaml"
    if packaged.exists():
        return packaged
    return Path(__file__).resolve().parents[3] / "data" / "protocol" / "ab9-settings.yaml"


def _addr(cmd: int, bank: int | None, slot: int | None,
          index: int | None = None) -> tuple[int, ...]:
    """Build a wire address.

    The device has three address depths, all seen in captured traffic:
      (cmd,)                 plain
      (cmd, bank<<4|slot)    indexed
      (cmd, index, bank<<4|slot)   nested — id 225 and id 15, where the whole
                             force-sensing and trim blocks live
    """
    sel = None if (bank is None and slot is None) else ((bank or 0) << 4) | (slot or 0)
    if index is not None:
        return (cmd, index) if sel is None else (cmd, index, sel)
    return (cmd,) if sel is None else (cmd, sel)


@dataclass(frozen=True)
class Setting:
    name: str
    raw: dict

    @property
    def type(self) -> str:
        return self.raw.get("type", "int")

    @property
    def unit(self) -> str | None:
        return self.raw.get("unit")

    @property
    def effect_verified(self) -> bool:
        return self.raw.get("effect") == "confirmed"

    @property
    def write_width(self) -> int | None:
        """Wire width for a write. Per-address and NOT inferable — a wrong width
        can store a value nobody chose, with no warning. Absent means unknown,
        and unknown means we refuse to write."""
        return self.raw.get("write_width")

    @property
    def addresses(self) -> list[tuple[int, ...]]:
        r = self.raw
        if "cmds" in r:
            return [(c,) for c in r["cmds"]]
        cmd = r["cmd"]
        bank = r.get("bank")
        index = r.get("index")
        if "slots" in r:
            return [_addr(cmd, bank, s, index) for s in r["slots"]]
        if "slot" in r:
            return [_addr(cmd, bank, r["slot"], index)]
        if index is not None:
            return [(cmd, index)]
        return [(cmd,)]

    @property
    def writable(self) -> bool:
        has_width = self.write_width is not None or self.type == "float"
        return has_width and not any(a[0] in FORBIDDEN_IDS for a in self.addresses)

    def encode(self, value: int | float) -> bytes:
        """Encode a value for the wire at this setting's verified width.

        Floats go out as 4-byte big-endian IEEE-754, matching how the Z-axis
        curve is stored. Integers use the setting's write_width, which is
        per-setting: parameterised settings take one byte and plain ones take
        two, with `grip-type` the known exception at one.
        """
        if self.type == "float":
            import struct as _s
            return _s.pack(">f", float(value))
        width = self.write_width
        if width is None:
            raise ValueError(f"{self.name}: no verified write_width")
        return int(value).to_bytes(width, "big")

    def decode(self, value: bytes) -> int | float | None:
        if not value:
            return None
        if self.type == "float" and len(value) == 4:
            return struct.unpack(">f", value)[0]
        return int.from_bytes(value, "big")

    def label(self, address: tuple[int, ...]) -> str:
        if len(address) == 1:
            return f"id {address[0]}"
        if len(address) == 2:
            # A two-level address is either an index into a nested space or a
            # bank/slot selector. Only the entry knows which; decoding an index
            # as bank/slot prints nonsense like "bank 2 slot 7" for index 39.
            if "index" in self.raw and "slot" not in self.raw and "slots" not in self.raw:
                return f"id {address[0]} idx {address[1]}"
            return f"id {address[0]} bank {address[1] >> 4} slot {address[1] & 15}"
        return (f"id {address[0]} idx {address[1]} "
                f"bank {address[2] >> 4} slot {address[2] & 15}")


@dataclass
class Table:
    settings: dict[str, Setting] = field(default_factory=dict)
    actions: dict[str, dict] = field(default_factory=dict)
    presets: dict[str, dict] = field(default_factory=dict)
    meta: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "Table":
        doc = yaml.safe_load(Path(path or _default_table()).read_text())
        return cls(
            settings={k: Setting(k, v) for k, v in (doc.get("settings") or {}).items()},
            actions=doc.get("actions") or {},
            presets=doc.get("presets") or {},
            meta=doc.get("meta") or {},
        )

    def __getitem__(self, name: str) -> Setting:
        try:
            return self.settings[name]
        except KeyError:
            raise KeyError(f"no setting named {name!r}") from None

    def by_address(self) -> dict[tuple[int, ...], tuple[Setting, int]]:
        """Map each address to its setting and index within that setting."""
        out: dict[tuple[int, ...], tuple[Setting, int]] = {}
        for s in self.settings.values():
            for i, a in enumerate(s.addresses):
                out[a] = (s, i)
        return out
