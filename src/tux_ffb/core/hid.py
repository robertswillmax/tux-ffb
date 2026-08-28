"""Live axis and button state, read from evdev.

Position comes from the kernel, never from the serial channel. It is faster, it
is exactly what the game sees, it costs the config link nothing, and the serial
side does not report position anyway — ids that looked like position turned out
to be internal telemetry (docs/captures/2026-08-28-ab9-volatile-ids-are-not-position.md).

Note what evdev shows is the *output* of the base's axis processing: the response
curve, deadzone and input saturation have already been applied. There is no way
to see raw stick position from here.
"""

from __future__ import annotations

import fcntl
import glob
import os
import struct
import subprocess
import threading
from dataclasses import dataclass, field

EV_ABS, EV_KEY, EV_SYN = 0x03, 0x01, 0x00
ABS_X, ABS_Y = 0x00, 0x01
_EVENT = struct.Struct("llHHi")

VENDOR = "346e"


def find_node(vendor: str = VENDOR) -> str | None:
    for path in sorted(glob.glob("/dev/input/event*")):
        try:
            out = subprocess.run(["udevadm", "info", "--query=property", "--name", path],
                                 capture_output=True, text=True, timeout=2).stdout
        except Exception:
            continue
        if f"ID_VENDOR_ID={vendor}" in out:
            return path
    return None


def axis_info(node: str, axis: int) -> tuple[int, int, int] | None:
    """(value, min, max) via EVIOCGABS, without opening a read stream."""
    req = (2 << 30) | (24 << 16) | (0x45 << 8) | (0x40 + axis)
    buf = bytearray(24)
    try:
        with open(node, "rb") as fh:
            fcntl.ioctl(fh, req, buf)
    except OSError:
        return None
    value, lo, hi, *_ = struct.unpack("6i", bytes(buf))
    return (value, lo, hi) if hi > lo else None


def ff_effects(node: str) -> str | None:
    name = node.rsplit("/", 1)[-1]
    try:
        return open(f"/sys/class/input/{name}/device/capabilities/ff").read().strip()
    except OSError:
        return None


@dataclass
class AxisState:
    x: int = 32767
    y: int = 32767
    x_range: tuple[int, int] = (0, 65535)
    y_range: tuple[int, int] = (0, 65535)
    buttons: set[int] = field(default_factory=set)

    def fraction(self, axis: str) -> float:
        lo, hi = self.x_range if axis == "x" else self.y_range
        v = self.x if axis == "x" else self.y
        return (v - lo) / (hi - lo) if hi > lo else 0.5


class AxisMonitor:
    """Reads evdev in a background thread. Non-blocking, tolerant of unplugging."""

    def __init__(self, node: str | None = None):
        self.node = node or find_node()
        self.state = AxisState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        if self.node:
            for axis, attr in ((ABS_X, "x_range"), (ABS_Y, "y_range")):
                info = axis_info(self.node, axis)
                if info:
                    setattr(self.state, attr, (info[1], info[2]))
                    setattr(self.state, "x" if axis == ABS_X else "y", info[0])

    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive())

    def start(self) -> None:
        if not self.node or self.running:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def ensure_running(self) -> bool:
        """Re-acquire the node and restart if needed.

        The base is powered separately and is often absent when the app starts,
        and its evdev node can change across a re-plug or a VM passthrough
        cycle. A monitor created once and never rechecked simply stops working.
        """
        if self.running:
            return True
        node = find_node()
        if not node:
            return False
        if node != self.node:
            self.node = node
        for axis, attr in ((ABS_X, "x_range"), (ABS_Y, "y_range")):
            info = axis_info(self.node, axis)
            if info:
                setattr(self.state, attr, (info[1], info[2]))
                setattr(self.state, "x" if axis == ABS_X else "y", info[0])
        self._thread = None
        self.start()
        return self.running

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        try:
            fh = open(self.node, "rb", buffering=0)
        except OSError:
            return
        fcntl.fcntl(fh, fcntl.F_SETFL, fcntl.fcntl(fh, fcntl.F_GETFL) | os.O_NONBLOCK)
        while not self._stop.is_set():
            try:
                data = fh.read(_EVENT.size * 64)
            except BlockingIOError:
                self._stop.wait(0.004)
                continue
            except OSError:
                break
            if not data:
                self._stop.wait(0.004)
                continue
            for i in range(0, len(data) - _EVENT.size + 1, _EVENT.size):
                _, _, typ, code, value = _EVENT.unpack(data[i:i + _EVENT.size])
                if typ == EV_ABS:
                    if code == ABS_X:
                        self.state.x = value
                    elif code == ABS_Y:
                        self.state.y = value
                elif typ == EV_KEY:
                    (self.state.buttons.add if value else self.state.buttons.discard)(code)
        fh.close()
