#!/usr/bin/env python3
"""Enumerate the nested address space under a command id.  READ-ONLY.

id 225 (and id 15) are not single settings: a read takes an index and, for many
indices, a further sub-selector. The trim and follow block lives here, which is
why a flat scan of the command space never found it.

  enum225.py [cmd] [max_index] [max_sub]
"""
import json, sys, time, threading, serial

MAGIC, START = 13, 0x7E
_buf, _lock = bytearray(), threading.Lock()


def frame(payload):
    b = bytearray([START, len(payload), 30, 18]) + bytearray(payload)
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
        g, p = d[i + 2], bytes(d[i + 4:end])
        if not (g == 0x0E and p[:1] == b"\x05"):
            out.append(p)
        i = end + 1
    return out


def main():
    cmd = int(sys.argv[1]) if len(sys.argv) > 1 else 225
    max_idx = int(sys.argv[2]) if len(sys.argv) > 2 else 64
    max_sub = int(sys.argv[3]) if len(sys.argv) > 3 else 48
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.005, exclusive=False)
    stop = threading.Event()
    def pump():
        while not stop.is_set():
            d = ser.read(4096)
            if d:
                with _lock: _buf.extend(d)
    threading.Thread(target=pump, daemon=True).start(); time.sleep(0.4)

    # Two-level and three-level addresses MUST be probed in separate passes.
    # A reply to (cmd, idx, sub) has a payload beginning cmd, idx, sub — which
    # matches the two-level address (cmd, idx) by prefix. Mixing them in one
    # batch mis-attributes three-level replies to two-level addresses.
    levels = [[(cmd, i) for i in range(max_idx)],
              [(cmd, i, s) for i in range(max_idx) for s in range(max_sub)]]
    found, B = {}, 128
    t0 = time.time()
    batches = [lvl[i:i + B] for lvl in levels for i in range(0, len(lvl), B)]
    for chunk in batches:
        with _lock: _buf.clear()
        ser.write(b"".join(frame(list(a)) for a in chunk)); ser.flush()
        pending = set(chunk)
        deadline = time.time() + 0.7
        while pending and time.time() < deadline:
            time.sleep(0.01)
            with _lock: d = bytes(_buf)
            for p in parse(d):
                for a in list(pending):
                    # exact-length match only; a longer payload belongs to a
                    # deeper address, not this one
                    if p[:len(a)] == bytes(a) and len(p) > len(a):
                        found[a] = p[len(a):].hex(" ")
                        pending.discard(a)
                        break
    stop.set(); time.sleep(0.2); ser.close()

    two = {a: v for a, v in found.items() if len(a) == 2}
    three = {a: v for a, v in found.items() if len(a) == 3}
    print(f"id {cmd}: {len(two)} two-level, {len(three)} three-level addresses "
          f"[{time.time()-t0:.0f}s]")
    print("\ntwo-level (cmd, idx):")
    for a in sorted(two):
        print(f"   idx {a[1]:>3} (0x{a[1]:02x}) = {two[a]}")
    print("\nthree-level (cmd, idx, sub), grouped by index:")
    by_idx = {}
    for a, v in three.items():
        by_idx.setdefault(a[1], []).append((a[2], v))
    for idx in sorted(by_idx):
        subs = sorted(by_idx[idx])
        vals = "  ".join(f"{s:#04x}={v}" for s, v in subs[:8])
        more = f"  (+{len(subs)-8} more)" if len(subs) > 8 else ""
        print(f"   idx {idx:>3} (0x{idx:02x}): {len(subs):>2} subs   {vals}{more}")
    json.dump({f"{a[1]}" + (f".{a[2]}" if len(a) > 2 else ""): v
               for a, v in found.items()}, open(f"/tmp/enum{cmd}.json", "w"), indent=1)


if __name__ == "__main__":
    main()
