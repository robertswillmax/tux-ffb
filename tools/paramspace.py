#!/usr/bin/env python3
"""
Survey the AB9's raw parameter channel.  READ-ONLY.

Group 14 / cmd 0 is a flat parameter view addressed by 16-bit index, returning a
32-bit value — almost certainly the (Table, Param) store the firmware's write
logs refer to. Discovered by watching MOZA Cockpit read it during a cogging
calibration.

  request:  7e 03 0e 12 00 <idx_hi> <idx_lo> <ck>
  reply:    7e 07 8e 21 00 <idx_hi> <idx_lo> <b3 b2 b1 b0> <ck>

  paramspace.py <out.json> [max_index]
"""
import json, struct, sys, time, threading, serial

MAGIC, START, DEV, GRP = 13, 0x7E, 18, 14
_buf, _lock, _stop = bytearray(), threading.Lock(), threading.Event()


def frame(idx):
    b = bytearray([START, 3, GRP, DEV, 0, (idx >> 8) & 0xFF, idx & 0xFF])
    b.append((sum(b) + MAGIC) & 0xFF)
    return bytes(b)


def parse(d):
    out, i = [], 0
    while i < len(d):
        if d[i] != START:
            i += 1; continue
        if i + 1 >= len(d): break
        ln = d[i + 1]; end = i + 4 + ln
        if not (1 <= ln <= 64) or end >= len(d): i += 1; continue
        if ((sum(d[i:end]) + MAGIC) & 0xFF) != d[end]: i += 1; continue
        out.append((d[i + 2], bytes(d[i + 4:end])))
        i = end + 1
    return out


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "paramspace.json"
    hi = int(sys.argv[2]) if len(sys.argv) > 2 else 8192
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.005, exclusive=False)
    def pump():
        while not _stop.is_set():
            d = ser.read(4096)
            if d:
                with _lock: _buf.extend(d)
    threading.Thread(target=pump, daemon=True).start(); time.sleep(0.4)

    found, B = {}, 96
    t0 = time.time()
    for base in range(0, hi, B):
        chunk = list(range(base, min(base + B, hi)))
        with _lock: _buf.clear()
        ser.write(b"".join(frame(i) for i in chunk)); ser.flush()
        deadline = time.time() + 0.6
        pending = set(chunk)
        while pending and time.time() < deadline:
            time.sleep(0.01)
            with _lock: d = bytes(_buf)
            for grp, p in parse(d):
                if not (grp & 0x80) or p[:1] != b"\x00" or len(p) < 3:
                    continue
                idx = (p[1] << 8) | p[2]
                if idx in pending:
                    found[idx] = p[3:].hex(" ")
                    pending.discard(idx)
        if base % 1024 == 0:
            print(f"  ...{base}/{hi}  found {len(found)}  [{time.time()-t0:.0f}s]", flush=True)
    json.dump(found, open(out_path, "w"), indent=1)
    print(f"\n{len(found)} parameters readable in index range 0..{hi-1}   [{time.time()-t0:.0f}s]")
    runs, keys = [], sorted(found)
    if keys:
        s = p = keys[0]
        for k in keys[1:]:
            if k == p + 1: p = k
            else: runs.append((s, p)); s = p = k
        runs.append((s, p))
        print(f"contiguous index blocks ({len(runs)}):")
        for a, b in runs[:40]:
            print(f"  {a:>5}-{b:<5} ({b-a+1:>4} params)")
    _stop.set(); time.sleep(0.2); ser.close()


if __name__ == "__main__":
    main()
