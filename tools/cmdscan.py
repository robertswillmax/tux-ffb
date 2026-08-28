#!/usr/bin/env python3
"""Robust group-30 scan: drain to quiet, send, wait for a frame echoing the id.
READ-ONLY. Runs twice; only values identical in both runs are reported."""
import json, re, sys, time, threading, serial
MAGIC, START = 13, 0x7E
buf, lock, stop = bytearray(), threading.Lock(), threading.Event()
REJECT = re.compile(r"unexpect (?:sub_cmd|cmd_index)\s*:?\s*(\d+)")

def frame(g, dv, cid, n=0):
    b = bytearray([START, len(cid)+n, g, dv]); b += bytes(cid)+bytes(n)
    b.append((sum(b)+MAGIC) & 0xFF); return bytes(b)

def parse(data):
    fr, tx, i = [], [], 0
    while i < len(data):
        if data[i] != START: i += 1; continue
        if i+1 >= len(data): break
        ln = data[i+1]; end = i+4+ln
        if not (1 <= ln <= 64) or end >= len(data): i += 1; continue
        if ((sum(data[i:end])+MAGIC) & 0xFF) != data[end]: i += 1; continue
        g, dv, p = data[i+2], data[i+3], bytes(data[i+4:end])
        if g == 0x0e and p[:1] == b'\x05': tx.append(p[1:])
        else: fr.append((g, dv, p))
        i = end+1
    return fr, b"".join(tx).decode("utf-8", "replace")

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.02, exclusive=False)
def rd():
    while not stop.is_set():
        d = ser.read(512)
        if d:
            with lock: buf.extend(d)
threading.Thread(target=rd, daemon=True).start()

def drain(quiet=0.06, cap=1.0):
    """Wait until nothing has arrived for `quiet` seconds, then clear."""
    t0 = time.time(); last = -1
    while time.time() - t0 < cap:
        with lock: n = len(buf)
        if n == last:
            time.sleep(quiet)
            with lock:
                if len(buf) == n: buf.clear(); return
        last = n; time.sleep(quiet)
    with lock: buf.clear()

def request(cid, timeout=0.5):
    drain()
    ser.write(frame(30, 18, [cid])); ser.flush()
    t0 = time.time()
    while time.time() - t0 < timeout:
        time.sleep(0.02)
        with lock: data = bytes(buf)
        fr, t = parse(data)
        for g, dv, p in fr:
            if p[:1] == bytes([cid]):
                return p[1:].hex(" "), None
        m = REJECT.search(" ".join(t.split()))
        if m and int(m.group(1)) == cid:
            return None, "rejected"
    return None, "timeout"

runs = []
for r in range(2):
    res, rej, to = {}, 0, []
    for cid in range(256):
        v, why = request(cid)
        if v is not None: res[str(cid)] = v
        elif why == "rejected": rej += 1
        else: to.append(cid)
    runs.append(res)
    print(f"run {r+1}: {len(res)} data, {rej} rejected, {len(to)} timeout {to if len(to)<12 else ''}")

keys = set(runs[0]) | set(runs[1])
agree = {k: runs[0][k] for k in keys if runs[0].get(k) == runs[1].get(k) and k in runs[0]}
differ = {k: [runs[0].get(k), runs[1].get(k)] for k in keys if k not in agree}
print(f"\nagree across both runs: {len(agree)}   differ (live/unstable): {len(differ)}")
for k in sorted(differ, key=int): print(f"  id {k:>3}  {differ[k]}")
json.dump({"agree": agree, "differ": differ}, open("alpha_robust.json", "w"), indent=1)
stop.set(); time.sleep(0.2); ser.close()
