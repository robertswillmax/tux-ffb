#!/usr/bin/env python3
"""
Decode MOZA serial frames out of a usbmon text capture.

Used to watch MOZA Cockpit talk to the base while the device is passed through
to the Windows VM. QEMU's USB passthrough goes through usbfs, and usbmon taps
below that, so every URB is visible on the host even though the host kernel has
no driver bound.

  sudo cat /sys/kernel/debug/usb/usbmon/<bus>u > cap.txt      # while Cockpit runs
  usbcap.py cap.txt <devnum>

Note: the usbmon *text* interface truncates payload at 32 bytes per URB. Command
frames are far shorter than that; long ASCII log frames from the base may clip.
"""
import re, sys

MAGIC, START = 13, 0x7E
LINE = re.compile(r"^(\S+)\s+(\d+)\s+([SCE])\s+([BCIZ])([io]):(\d+):(\d+):(\d+)\s+(.*)$")


def payloads(path, devnum):
    """Yield (direction, hexbytes) for URBs belonging to devnum."""
    for raw in open(path, errors="replace"):
        m = LINE.match(raw.strip())
        if not m:
            continue
        _, _, evt, xfer, io, bus, dev, ep, rest = m.groups()
        if int(dev) != devnum or xfer not in "BI":
            continue
        # data follows a '=' token
        if " = " not in rest:
            continue
        data = rest.split(" = ", 1)[1].replace(" ", "")
        try:
            b = bytes.fromhex(data)
        except ValueError:
            continue
        if b:
            yield ("OUT" if io == "o" else "IN"), b


def frames(stream):
    """Extract checksum-valid MOZA frames from a byte stream."""
    out, i = [], 0
    while i < len(stream):
        if stream[i] != START:
            i += 1; continue
        if i + 1 >= len(stream):
            break
        ln = stream[i + 1]; end = i + 4 + ln
        if not (1 <= ln <= 64) or end >= len(stream):
            i += 1; continue
        if ((sum(stream[i:end]) + MAGIC) & 0xFF) != stream[end]:
            i += 1; continue
        out.append(bytes(stream[i:end + 1]))
        i = end + 1
    return out


def describe(f):
    ln, grp, dev = f[1], f[2], f[3]
    body = f[4:-1]
    if grp & 0x80:
        kind = f"REPLY grp={grp & 0x7F}"
        dev = ((dev & 0x0F) << 4) | (dev >> 4)
    else:
        kind = {30: "GET ", 31: "SET "}.get(grp, f"grp={grp}")
    if grp == 0x0E and body[:1] == b"\x05":
        return f"  LOG   {body[1:].decode('utf-8', 'replace').strip()!r}"
    return (f"  {kind} dev={dev:<3} cmd={body[0] if body else '-':<4} "
            f"rest={body[1:].hex(' '):<20} raw={f.hex(' ')}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    path, devnum = sys.argv[1], int(sys.argv[2])
    for direction in ("OUT", "IN"):
        stream = bytearray()
        for d, b in payloads(path, devnum):
            if d == direction:
                stream.extend(b)
        fs = frames(stream)
        print(f"=== {direction}  ({len(stream)} bytes, {len(fs)} frames) ===")
        seen = {}
        for f in fs:
            key = f.hex()
            seen[key] = seen.get(key, 0) + 1
        for f in fs:
            pass
        # print unique frames with counts, preserving first-seen order
        done = set()
        for f in fs:
            k = f.hex()
            if k in done:
                continue
            done.add(k)
            n = seen[k]
            print(f"{describe(f)}   x{n}")
        print()
