#!/usr/bin/env python3
"""
Write one AB9 setting, safely.  Group 31 (Main_set) only.

  setval.py <cmd_id> <index|-> <value> [--expect N] [--width N]

Guards, in order:
  1. reads the current value first and aborts unless it matches --expect
     (when given) — protects against writing to a misidentified address
  2. takes a full snapshot backup before writing
  3. writes, then captures the firmware's own log line for the write
  4. reads the value back
  5. diffs the whole address space to catch side effects

Nothing here may target a group other than 31; see docs/07-safety.md.
"""
import json, subprocess, sys, time, threading, serial

MAGIC, START, DEV, GET, SET = 13, 0x7E, 18, 30, 31
_buf, _lock = bytearray(), threading.Lock()


def frame(group, payload):
    b = bytearray([START, len(payload), group, DEV]) + bytearray(payload)
    b.append((sum(b) + MAGIC) & 0xFF)
    return bytes(b)


def parse(d):
    fr, tx, i = [], [], 0
    while i < len(d):
        if d[i] != START:
            i += 1; continue
        if i + 1 >= len(d): break
        ln = d[i + 1]; end = i + 4 + ln
        if not (1 <= ln <= 64) or end >= len(d): i += 1; continue
        if ((sum(d[i:end]) + MAGIC) & 0xFF) != d[end]: i += 1; continue
        g, p = d[i + 2], bytes(d[i + 4:end])
        if g == 0x0E and p[:1] == b"\x05": tx.append(p[1:])
        else: fr.append(p)
        i = end + 1
    return fr, b"".join(tx).decode("utf-8", "replace")


def main():
    a = [x for x in sys.argv[1:] if not x.startswith("--")]
    opt = {x.split("=")[0]: x.split("=")[1] for x in sys.argv[1:] if x.startswith("--") and "=" in x}
    if len(a) < 3:
        print(__doc__); return 2
    cid = int(a[0]); idx = None if a[1] == "-" else int(a[1]); val = int(a[2])
    # Wire width differs by address kind, measured 2026-08-28:
    #   parameterised (has an index): 1-byte value
    #   plain (no index):             2-byte value — a 1-byte value is rejected
    #                                 with "unexpected parameter"
    width = int(opt.get("--width", 1 if idx is not None else 2))
    expect = int(opt["--expect"]) if "--expect" in opt else None
    addr = [cid] + ([] if idx is None else [idx])

    # Backup FIRST, while the port is still free. snapshot.py opens the same
    # device, and two processes on one CDC-ACM port corrupt both streams — the
    # pump thread dies with "device reports readiness to read but returned no
    # data". Never hold the port across a subprocess that also needs it.
    subprocess.run([sys.executable, "tools/snapshot.py", "capture", "/tmp/_setval_pre.json"],
                   check=True, capture_output=True)
    print("1. backup captured -> /tmp/_setval_pre.json")

    # Refuse unknown addresses. Writing to an address with no table entry means
    # guessing its width, and a wrong width can store a value nobody chose with
    # no warning at all — see docs/captures/2026-08-28-INCIDENT-*.md.
    if "--unsafe" not in sys.argv:
        import re
        try:
            tbl = open("data/protocol/ab9-settings.yaml").read()
        except OSError:
            tbl = ""
        if not re.search(rf"cmd:\s*{cid}\b", tbl):
            print(f"REFUSED: id {cid} has no entry in ab9-settings.yaml.\n"
                  f"  Writing an unknown address means guessing its width, and a wrong\n"
                  f"  width can silently store the wrong value. Add a table entry with a\n"
                  f"  verified write_width, or pass --unsafe if you accept that risk.")
            return 2

    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.005, exclusive=False)
    stop = threading.Event()
    def pump():
        while not stop.is_set():
            d = ser.read(2048)
            if d:
                with _lock: _buf.extend(d)
    threading.Thread(target=pump, daemon=True).start(); time.sleep(0.4)

    def drain():
        last = -1
        while True:
            with _lock: n = len(_buf)
            if n == last: break
            last = n; time.sleep(0.05)
        with _lock: _buf.clear()

    def read():
        drain(); ser.write(frame(GET, addr)); ser.flush(); time.sleep(0.4)
        with _lock: d = bytes(_buf)
        fr, t = parse(d)
        m = bytes(addr)
        hit = next((p for p in fr if p[:len(m)] == m), None)
        return (int.from_bytes(hit[len(m):], "big") if hit else None), " ".join(t.split())

    loc = f"id {cid}" + ("" if idx is None else f" bank {idx>>4} slot {idx&15}")
    try:
        before, _ = read()
        print(f"2. current {loc} = {before}")
        if expect is not None and before != expect:
            print(f"   ABORT: expected {expect}, found {before}. Not writing."); return 1

        msg = frame(SET, addr + list(val.to_bytes(width, "big")))
        print(f"3. WRITE {msg.hex(' ')}   ({loc} = {val})")
        drain(); ser.write(msg); ser.flush(); time.sleep(0.6)
        with _lock: d = bytes(_buf)
        fr, t = parse(d)
        log = [l for l in t.splitlines() if l.strip()]
        for l in log: print(f"   firmware: {l.strip()}")

        after, warn = read()
        ok = after == val
        print(f"4. read back = {after}   {'OK' if ok else 'MISMATCH'}"
              + (f"   warn: {warn[:60]}" if warn.strip() else ""))
    finally:
        stop.set(); time.sleep(0.2); ser.close()

    subprocess.run([sys.executable, "tools/snapshot.py", "capture", "/tmp/_setval_post.json"],
                   check=True, capture_output=True)
    print("5. side-effect check:")
    subprocess.run([sys.executable, "tools/snapshot.py", "diff",
                    "/tmp/_setval_pre.json", "/tmp/_setval_post.json"])
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
