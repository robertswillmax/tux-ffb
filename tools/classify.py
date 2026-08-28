#!/usr/bin/env python3
"""Partition group-30 ids: plain getters vs parameterised getters. READ-ONLY."""
import json, re, sys, time, threading, serial
MAGIC, START = 13, 0x7E
buf, lock, stop = bytearray(), threading.Lock(), threading.Event()
REJECT = re.compile(r"unexpect (?:sub_cmd|cmd_index)\s*:?\s*(\d+)")
PARAM  = re.compile(r"unexpected parameter|unexpect cmd_num")

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
        last = n; time.sleep(0.05)
    with lock: buf.clear()

plain, param, rejected, quiet = {}, {}, [], []
for cid in range(256):
    drain()
    ser.write(frame(30, 18, [cid])); ser.flush()
    time.sleep(0.35)
    with lock: data = bytes(buf)
    fr, t = parse(data)
    j = " ".join(t.split())
    val = next((p[1:].hex(" ") for p in fr if p[:1] == bytes([cid])), None)
    m = REJECT.search(j)
    if m and int(m.group(1)) == cid: rejected.append(cid)
    elif PARAM.search(j):
        param[str(cid)] = {"junk": val, "warn": PARAM.search(j).group(0)}
    elif val is not None: plain[str(cid)] = val
    else: quiet.append(cid)

print(f"plain getters (value trustworthy): {len(plain)}")
print(f"PARAMETERISED (needs an index; our value is junk): {len(param)}")
print(f"  {sorted((int(k) for k in param), key=int)}")
print(f"rejected: {len(rejected)}   no reply: {len(quiet)} {quiet}")
json.dump({"plain": plain, "param": param}, open("classified_mh16.json", "w"), indent=1)
stop.set(); time.sleep(0.2); ser.close()
