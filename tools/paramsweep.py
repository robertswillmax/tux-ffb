#!/usr/bin/env python3
"""Sweep the 25 parameterised getters across their index space. READ-ONLY (group 30)."""
import json, time, threading, serial
MAGIC, START = 13, 0x7E
buf, lock, stop = bytearray(), threading.Lock(), threading.Event()
PARAM_IDS = [147,148,149,150,151,152,171,172,173,180,181,182,183,196,197,199,
             205,206,209,210,218,219,220,221,225]
MAXIDX = 32

def frame(cid, idx):
    b = bytearray([START, 2, 30, 18, cid, idx]); b.append((sum(b)+MAGIC) & 0xFF)
    return bytes(b)

def parse(data):
    fr, tx, i = [], [], 0
    while i < len(data):
        if data[i] != START: i += 1; continue
        if i+1 >= len(data): break
        ln = data[i+1]; end = i+4+ln
        if not (1 <= ln <= 64) or end >= len(data): i += 1; continue
        if ((sum(data[i:end])+MAGIC) & 0xFF) != data[end]: i += 1; continue
        g, p = data[i+2], bytes(data[i+4:end])
        if g == 0x0e and p[:1] == b'\x05': tx.append(p[1:])
        else: fr.append(p)
        i = end+1
    return fr, b"".join(tx).decode("utf-8", "replace")

ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.02, exclusive=False)
def rd():
    while not stop.is_set():
        d = ser.read(512)
        if d:
            with lock: buf.extend(d)
threading.Thread(target=rd, daemon=True).start(); time.sleep(0.3)

def drain():
    last = -1
    while True:
        with lock: n = len(buf)
        if n == last: break
        last = n; time.sleep(0.04)
    with lock: buf.clear()

def read(cid, idx, timeout=0.45):
    drain()
    ser.write(frame(cid, idx)); ser.flush()
    t0, hit = time.time(), None
    while time.time() - t0 < timeout:
        time.sleep(0.02)
        with lock: data = bytes(buf)
        fr, _ = parse(data)
        hit = next((p for p in fr if p[:2] == bytes([cid, idx])), None)
        if hit: break
    time.sleep(0.12)                       # let a trailing WARN arrive
    with lock: data = bytes(buf)
    fr, t = parse(data)
    hit = next((p for p in fr if p[:2] == bytes([cid, idx])), hit)
    warn = "WARN" in t
    return (hit[2:].hex(" ") if hit else None), warn

out = {}
for cid in PARAM_IDS:
    good, bad = {}, 0
    for idx in range(MAXIDX):
        v, w = read(cid, idx)
        if v is not None and not w: good[idx] = v
        else: bad += 1
    out[str(cid)] = good
    vals = ", ".join(f"{i}={good[i]}" for i in sorted(good))
    print(f"id {cid:>3}: {len(good):>2}/{MAXIDX} valid indices   {vals[:120]}")
json.dump(out, open("paramsweep.json", "w"), indent=1)
stop.set(); time.sleep(0.2); ser.close()
