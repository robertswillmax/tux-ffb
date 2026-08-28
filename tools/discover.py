#!/usr/bin/env python3
"""
Rebuild the AB9 address manifest by exhaustive discovery.  READ-ONLY (group 30).

Pipelined, with adaptive splitting.  The firmware emits exactly one warning per
invalid request, so a batch's warning count is the number of invalid requests in
it: zero means all valid, len(batch) means all invalid, and anything between is
resolved by splitting the batch in half and recursing.  That keeps an exhaustive
sweep to minutes instead of hours while staying exact.

  discover.py <out-manifest.json> [max_index]
"""
import json, sys, time, threading, serial

MAGIC, START, GET, DEV = 13, 0x7E, 30, 18
NEEDS_PARAM = "unexpected parameter"
BAD_ID = ("unexpect cmd_index", "unexpect sub_cmd")
_buf, _lock, _stop = bytearray(), threading.Lock(), threading.Event()


def frame(cid, idx=None):
    p = [cid] if idx is None else [cid, idx]
    b = bytearray([START, len(p), GET, DEV]) + bytearray(p)
    b.append((sum(b) + MAGIC) & 0xFF)
    return bytes(b)


def parse(d):
    fr, tx, i = [], [], 0
    while i < len(d):
        if d[i] != START:
            i += 1; continue
        if i + 1 >= len(d):
            break
        ln = d[i + 1]; end = i + 4 + ln
        if not (1 <= ln <= 64) or end >= len(d):
            i += 1; continue
        if ((sum(d[i:end]) + MAGIC) & 0xFF) != d[end]:
            i += 1; continue
        g, p = d[i + 2], bytes(d[i + 4:end])
        (tx if (g == 0x0E and p[:1] == b"\x05") else fr).append(p[1:] if (g == 0x0E and p[:1] == b"\x05") else p)
        i = end + 1
    return fr, b"".join(tx).decode("utf-8", "replace")


def open_port():
    ser = serial.Serial("/dev/ttyACM0", 115200, timeout=0.005, exclusive=False)
    def pump():
        while not _stop.is_set():
            d = ser.read(2048)
            if d:
                with _lock: _buf.extend(d)
    threading.Thread(target=pump, daemon=True).start()
    time.sleep(0.3)
    return ser


def echo(r):
    return bytes([r[0]]) if r[1] is None else bytes([r[0], r[1]])


def send(ser, reqs, settle=0.45):
    with _lock: _buf.clear()
    ser.write(b"".join(frame(*r) for r in reqs)); ser.flush()
    time.sleep(settle if len(reqs) > 1 else 0.3)
    with _lock: d = bytes(_buf)
    fr, txt = parse(d)
    vals = {}
    for r in reqs:
        m = echo(r)
        hit = next((p for p in fr if p[:len(m)] == m), None)
        if hit is not None:
            vals[r] = hit[len(m):].hex(" ")
    return vals, txt.count(NEEDS_PARAM), sum(txt.count(b) for b in BAD_ID)


def resolve(ser, reqs, out, depth=0):
    """Classify every request in reqs, splitting when a batch is mixed."""
    if not reqs:
        return
    vals, n_param, n_bad = send(ser, reqs)
    n = len(reqs)
    if n_param == 0 and n_bad == 0:
        for r in reqs:
            out[r] = ("ok", vals.get(r))
        return
    if n_param >= n:
        for r in reqs: out[r] = ("needs_param", None)
        return
    if n_bad >= n:
        for r in reqs: out[r] = ("bad_id", None)
        return
    if n == 1:
        r = reqs[0]
        out[r] = ("needs_param" if n_param else "bad_id", None)
        return
    mid = n // 2
    resolve(ser, reqs[:mid], out, depth + 1)
    resolve(ser, reqs[mid:], out, depth + 1)


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    max_index = int(sys.argv[2]) if len(sys.argv) > 2 else 128
    ser = open_port()
    try:
        t0 = time.time()
        print("phase 1: plain sweep of all 256 command ids", flush=True)
        out = {}
        B = 16
        ids = [(c, None) for c in range(256)]
        for i in range(0, len(ids), B):
            resolve(ser, ids[i:i + B], out)
        plain = sorted(c for (c, _), (st, _) in out.items() if st == "ok")
        needs = sorted(c for (c, _), (st, _) in out.items() if st == "needs_param")
        print(f"  plain getters: {len(plain)}   need a parameter: {len(needs)}   "
              f"invalid: {256 - len(plain) - len(needs)}   [{time.time()-t0:.0f}s]", flush=True)
        print(f"  parameterised ids: {needs}", flush=True)

        print(f"\nphase 2: index sweep 0..{max_index-1} on {len(needs)} parameterised ids", flush=True)
        param = {}
        for k, cid in enumerate(needs):
            o = {}
            reqs = [(cid, i) for i in range(max_index)]
            for i in range(0, len(reqs), B):
                resolve(ser, reqs[i:i + B], o)
            good = {i: v for (c, i), (st, v) in o.items() if st == "ok"}
            param[cid] = dict(sorted(good.items()))
            print(f"  [{k+1}/{len(needs)}] id {cid}: {len(good)} valid indices"
                  f"  banks {sorted({i >> 4 for i in good})}   [{time.time()-t0:.0f}s]", flush=True)

        man = {"plain": plain,
               "param": [[c, sorted(v)] for c, v in param.items() if v]}
        json.dump(man, open(sys.argv[1], "w"), indent=1)
        total = len(plain) + sum(len(v) for v in param.values())
        print(f"\nmanifest written: {len(plain)} plain + "
              f"{sum(len(v) for v in param.values())} indexed = {total} addresses"
              f"   [{time.time()-t0:.0f}s]")
        json.dump({str(c): v for c, v in param.items()}, open(sys.argv[1] + ".values", "w"), indent=1)
    finally:
        _stop.set(); time.sleep(0.2); ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
