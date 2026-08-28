"""Find the base's serial port.

Never assume /dev/ttyACM0. The node number moves — a VM passthrough cycle is
enough to shift it — and other CDC-ACM devices can hold the low numbers. The
port is identified by the USB vendor id of the interface behind it.

Also filters by product: MOZA's racing bases share vendor 0x346e and are
boxflat's business, not ours. Two applications fighting over one port produces
exactly the sort of intermittent fault nobody can reproduce.
"""

from __future__ import annotations

import glob
from pathlib import Path

VENDOR = "346e"
FLIGHT_PRODUCTS = {"1000"}          # AB9. AB6 unknown; see docs/03-device-model.md


def _usb_parent(tty: Path) -> Path | None:
    """Walk up from a tty device to the USB device node holding idVendor."""
    node = (tty / "device").resolve()
    for _ in range(8):
        if (node / "idVendor").exists():
            return node
        if node.parent == node:
            break
        node = node.parent
    return None


def find_ports(vendor: str = VENDOR,
               products: set[str] | None = FLIGHT_PRODUCTS) -> list[tuple[str, str]]:
    """Return [(path, product_id)] for every matching serial port."""
    out = []
    for path in sorted(glob.glob("/dev/ttyACM*")):
        sysfs = Path("/sys/class/tty") / Path(path).name
        if not sysfs.exists():
            continue
        usb = _usb_parent(sysfs)
        if usb is None:
            continue
        try:
            vid = (usb / "idVendor").read_text().strip().lower()
            pid = (usb / "idProduct").read_text().strip().lower()
        except OSError:
            continue
        if vid != vendor:
            continue
        if products and pid not in products:
            continue                 # a racing base: boxflat's, not ours
        out.append((path, pid))
    return out


def find_port(default: str | None = None) -> str | None:
    ports = find_ports()
    if ports:
        return ports[0][0]
    return default
