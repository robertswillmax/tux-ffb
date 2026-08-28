"""A connected AB9, and the operations that are safe to perform on it."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass

from .commands import FORBIDDEN_IDS, Setting, Table
from .transport import Transport


class UnsafeWrite(RuntimeError):
    pass


@dataclass
class Reading:
    setting: Setting
    address: tuple[int, ...]
    value: int | float | None

    @property
    def label(self) -> str:
        return self.setting.label(self.address)


class Device:
    def __init__(self, transport: Transport, table: Table | None = None):
        self.t = transport
        self.table = table or Table.load()

    # -- reading -----------------------------------------------------------
    def read(self, name: str) -> list[Reading]:
        s = self.table[name]
        got = self.t.request_many(s.addresses)
        return [Reading(s, a, s.decode(got[a])) if a in got else Reading(s, a, None)
                for a in s.addresses]

    def read_all(self) -> dict[str, list[Reading]]:
        by_addr = self.table.by_address()
        got = self.t.request_many(by_addr.keys())
        out: dict[str, list[Reading]] = {}
        for name, s in self.table.settings.items():
            out[name] = [Reading(s, a, s.decode(got[a])) if a in got
                         else Reading(s, a, None) for a in s.addresses]
        return out

    # -- writing -----------------------------------------------------------
    def write(self, name: str, value: int | float, *, index: int = 0,
              expect: int | float | None = None) -> tuple[bool, str]:
        """Write one address of a setting, then verify by reading it back.

        Read-back is not a courtesy. A write with the wrong wire width can be
        accepted, logged plausibly by the firmware, and store a different value
        entirely — observed on hardware. An unverified write is an unknown write.
        """
        s = self.table[name]
        if any(a[0] in FORBIDDEN_IDS for a in s.addresses):
            raise UnsafeWrite(f"{name!r} targets a forbidden id; refusing")
        if s.write_width is None and s.type != "float":
            raise UnsafeWrite(
                f"{name!r} has no verified write_width. Guessing the width can "
                f"store a value nobody chose, silently. Establish it first.")
        address = s.addresses[index]

        if expect is not None:
            current = self.read(name)[index].value
            if current != expect:
                return False, f"expected {expect} before writing, found {current}"

        payload = list(address) + list(s.encode(value))
        log = self.t.write_raw(payload)
        back = self.read(name)[index].value
        ok = back == value
        note = f"read back {back}" + ("" if ok else f", wanted {value}")
        if log.strip():
            note += " | " + " ".join(log.split())[:120]
        return ok, note

    # -- actions -----------------------------------------------------------
    def calibrate_cogging(self, progress: Callable[[int], None] | None = None,
                          timeout: float = 150.0) -> bool:
        """Run the cogging torque calibration (~53 s).

        Drives the motor: the stick must be free and untouched for the duration.
        This is the repair for a lost calibration — the base does not rebuild it
        at power-on, and each run is as good as any other, so regenerating beats
        restoring a stale copy.
        """
        act = self.table.actions["cogging-calibration"]
        cmd = act["cmd"]
        start = act["start"]
        self.t.write_raw([cmd] + list(int(start["write"]).to_bytes(start["write_width"], "big")))
        t0 = time.time()
        last = -1
        while time.time() - t0 < timeout:
            time.sleep(1.0)
            raw = self.t.request((cmd,))
            if raw is None:
                continue
            pct = int.from_bytes(raw, "big")
            if pct != last and progress:
                progress(pct)
            last = pct
            if pct >= 100:
                return True
        return False

    def calibration_percent(self) -> int | None:
        raw = self.t.request((self.table.actions["cogging-calibration"]["cmd"],))
        return int.from_bytes(raw, "big") if raw else None

    # -- backup ------------------------------------------------------------
    CAL_PARAMS = ([*range(300, 321)] + [400, 401, 402] + [1000, 1001]
                  + [*range(1900, 1906)] + [*range(2000, 2008)] + [*range(1, 21)])

    def backup_parameters(self) -> dict[int, int]:
        """Read the raw parameter store, including the cogging calibration data.

        Note there is no known write path back into this space, so this is a
        record rather than a restorable image. Calibration can be re-run instead.
        """
        return self.t.read_params(self.CAL_PARAMS)
