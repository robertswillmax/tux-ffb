#!/usr/bin/env python3
"""
Fast AB9 state snapshot / diff.  READ-ONLY — group 30 (Main_get) only.

The MOZA protocol echoes the command id (and, for indexed reads, the index) in
every reply, so requests do not need to be serialised: fire a batch, then match
replies to requests by their echo.  A full 213-address snapshot takes ~0.1 s
instead of ~7 minutes.

  snapshot.py capture <out.json>              read every address in the manifest
  snapshot.py diff <before.json> <after.json> compare two snapshots
  snapshot.py discover <manifest.json>        slow full sweep, rebuilds manifest

Typical probe loop:
  snapshot.py capture before.json      # ~0.1s
  ...change one setting in Cockpit, bring the base back...
  snapshot.py capture after.json
  snapshot.py diff before.json after.json
"""
import json, struct, sys, time, threading, serial

MAGIC, START, PORT = 13, 0x7E, "/dev/ttyACM0"
GET_GROUP, DEV = 30, 18          # Main_get. Never a set group — see docs/07-safety.md.

# Ids whose value legitimately changes on its own; noise in a settings diff.
# 15 and 225 are NOT noise - they are nested sub-spaces whose plain read
# returns a changing value. The whole trim block lives inside 225.
VOLATILE = {184, 185, 215, 216, 114, 198,
            163, 164, 165, 166, 167, 168}  # boot-time calibration, re-measured each power-on

_buf, _lock, _stop = bytearray(), threading.Lock(), threading.Event()


def _frame(cid, idx=None):
    payload = [cid] if idx is None else [cid, idx]
    b = bytearray([START, len(payload), GET_GROUP, DEV]) + bytearray(payload)
    b.append((sum(b) + MAGIC) & 0xFF)
    return bytes(b)


def _parse(data):
    """Return payloads of well-formed non-ASCII frames. The 0x0e/0x05 channel is
    the firmware's async log broadcast, never a reply — see the enumeration note."""
    out, i = [], 0
    while i < len(data):
        if data[i] != START:
            i += 1; continue
        if i + 1 >= len(data):
            break
        ln = data[i + 1]; end = i + 4 + ln
        if not (1 <= ln <= 64) or end >= len(data):
            i += 1; continue
        if ((sum(data[i:end]) + MAGIC) & 0xFF) != data[end]:
            i += 1; continue
        grp, p = data[i + 2], bytes(data[i + 4:end])
        if not (grp == 0x0E and p[:1] == b"\x05"):
            out.append(p)
        i = end + 1
    return out


def _open():
    ser = serial.Serial(PORT, 115200, timeout=0.005, exclusive=False)
    def pump():
        while not _stop.is_set():
            d = ser.read(2048)
            if d:
                with _lock: _buf.extend(d)
    threading.Thread(target=pump, daemon=True).start()
    time.sleep(0.3)
    return ser


def _echo(addr):
    return bytes([addr[1]]) if addr[0] == "g" else bytes([addr[1], addr[2]])


def capture(ser, addrs, batch=128, timeout=0.7, rounds=3):
    """Pipelined read. Returns {addr: hexvalue}, [missing addrs]."""
    got, missing = {}, list(addrs)
    for _ in range(rounds):
        nxt = []
        for i in range(0, len(missing), batch):
            chunk = missing[i:i + batch]
            with _lock: _buf.clear()
            ser.write(b"".join(_frame(a[1], a[2] if a[0] == "p" else None) for a in chunk))
            ser.flush()
            t0, pending = time.time(), list(chunk)
            while pending and time.time() - t0 < timeout:
                time.sleep(0.01)
                with _lock: data = bytes(_buf)
                frames = _parse(data)
                still = []
                for a in pending:
                    m = _echo(a)
                    hit = next((p for p in frames if p[:len(m)] == m), None)
                    if hit is None: still.append(a)
                    else: got[a] = hit[len(m):].hex(" ")
                pending = still
            nxt += pending
        missing = nxt
        if not missing:
            break
    return got, missing


def discover(ser, max_index=80):
    """Slow full sweep: find every readable address. Use when the manifest may be
    stale (e.g. a firmware change, or indices appearing/disappearing)."""
    plain, param = [], []
    for cid in range(256):
        got, _ = capture(ser, [("g", cid)], batch=1, timeout=0.5, rounds=1)
        if got: plain.append(cid)
    for cid in range(256):
        hits = []
        for idx in range(max_index):
            got, _ = capture(ser, [("p", cid, idx)], batch=1, timeout=0.4, rounds=1)
            if got: hits.append(idx)
        if hits: param.append((cid, hits))
    return plain, param


def fmt(h):
    if h is None: return "-"
    b = bytes.fromhex(h.replace(" ", ""))
    if len(b) == 4:
        f = struct.unpack(">f", b)[0]
        if abs(f) < 1e9: return f"{f:g}"
    return str(int.from_bytes(b, "big"))


def load_manifest(path):
    m = json.load(open(path))
    addrs = [("g", c) for c in m["plain"]]
    for cid, idxs in m["param"]:
        addrs += [("p", cid, i) for i in idxs]
    return addrs


def main():
    if len(sys.argv) < 2:
        print(__doc__); return 2
    cmd = sys.argv[1]
    here = __file__.rsplit("/", 1)[0]
    manifest = f"{here}/../data/protocol/ab9-manifest.json"

    if cmd == "diff":
        a = {tuple(json.loads(k)): v for k, v in json.load(open(sys.argv[2]))["values"].items()}
        b = {tuple(json.loads(k)): v for k, v in json.load(open(sys.argv[3]))["values"].items()}
        changed = sorted([k for k in set(a) | set(b) if a.get(k) != b.get(k)],
                         key=lambda k: (k[1], k[2] if len(k) > 2 else -1))
        real = [k for k in changed if k[1] not in VOLATILE]
        noise = [k for k in changed if k[1] in VOLATILE]
        print(f"{len(real)} setting(s) changed" + (f", {len(noise)} volatile id(s) ignored" if noise else ""))
        for k in real:
            loc = f"id {k[1]}" if k[0] == "g" else f"id {k[1]} bank {k[2] >> 4} slot {k[2] & 15}"
            print(f"  {loc:<28} {fmt(a.get(k)):>10}  ->  {fmt(b.get(k)):>10}")
        if noise:
            print("  (volatile, shown for completeness: " +
                  ", ".join(sorted({str(k[1]) for k in noise})) + ")")
        return 0

    ser = _open()
    try:
        if cmd == "capture":
            addrs = load_manifest(manifest)
            t0 = time.time()
            got, missing = capture(ser, addrs)
            out = {"values": {json.dumps(list(k)): v for k, v in got.items()},
                   "missing": [list(k) for k in missing]}
            json.dump(out, open(sys.argv[2], "w"), indent=1)
            print(f"captured {len(got)}/{len(addrs)} addresses in {time.time()-t0:.2f}s"
                  + (f", {len(missing)} missing" if missing else ""))
        elif cmd == "discover":
            plain, param = discover(ser)
            json.dump({"plain": plain, "param": param}, open(sys.argv[2], "w"), indent=1)
            print(f"discovered {len(plain)} plain, {len(param)} parameterised")
        else:
            print(__doc__); return 2
    finally:
        _stop.set(); time.sleep(0.2); ser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
