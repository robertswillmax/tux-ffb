#!/usr/bin/env python3
"""
Capture and analyse the AB9's axis output as a TIME SERIES.

  axistrace.py capture <out.jsonl> [secs] [axis]     stream samples to disk;
                                                     readable while still running
  axistrace.py analyse <in.json>                     plateaus, reversals, trace

Why time series and not a value histogram: a rescaling deadzone and a remapping
response curve both preserve continuity and full travel, so neither shows up as
a gap in the set of observed values.  What they change is the *relationship*
between physical position and output over time — a clamp shows as a plateau, and
a non-monotonic curve shows as a direction reversal during a one-way sweep.
Analysing only distinct values misses both.  (Learned the hard way, 2026-08-28.)
"""
import fcntl, glob, json, os, struct, subprocess, sys, time

EV_ABS = 3
AXES = {"x": 0, "y": 1, "z": 2}


def node():
    for e in sorted(glob.glob("/dev/input/event*")):
        out = subprocess.run(["udevadm", "info", "--query=property", "--name", e],
                             capture_output=True, text=True).stdout
        if "ID_VENDOR_ID=346e" in out:
            return e
    sys.exit("AB9 evdev node not found — is the base powered and on the host?")


def capture(path, seconds, axis):
    dev, code = node(), AXES[axis]
    f = open(dev, "rb", buffering=0)
    fcntl.fcntl(f, fcntl.F_SETFL, fcntl.fcntl(f, fcntl.F_GETFL) | os.O_NONBLOCK)
    print(f"recording {dev} ABS_{axis.upper()} for {seconds}s -> {path} (streaming)", flush=True)
    out = open(path, "w", buffering=1)
    samples, t0, last = [], time.time(), 0.0
    while time.time() - t0 < seconds:
        try:
            d = f.read(24 * 64)
        except BlockingIOError:
            time.sleep(0.002); continue
        if not d:
            time.sleep(0.002); continue
        for i in range(0, len(d) - 23, 24):
            s, us, typ, c, val = struct.unpack("llHHi", d[i:i + 24])
            if typ == EV_ABS and c == code:
                rec = (s + us / 1e6, val)
                samples.append(rec)
                out.write(json.dumps(rec) + "\n")
        now = time.time()
        if now - last > 0.25:
            out.flush(); os.fsync(out.fileno()); last = now
    out.flush(); out.close(); f.close()
    print(f"{len(samples)} samples written to {path}")
    return samples


def load(path):
    """Accept a streamed .jsonl, or a legacy whole-file JSON array."""
    text = open(path).read().strip()
    if not text:
        return []
    if text.startswith("[") and "\n" not in text:
        return [tuple(s) for s in json.loads(text)]
    return [tuple(json.loads(ln)) for ln in text.splitlines() if ln.strip()]


def analyse(samples):
    if len(samples) < 50:
        print(f"only {len(samples)} samples — not enough motion to analyse"); return
    t0 = samples[0][0]
    ts = [t - t0 for t, _ in samples]
    vs = [v for _, v in samples]
    print(f"{len(samples)} samples over {ts[-1]:.1f}s   range {min(vs)}..{max(vs)}")

    plats = [(ts[i-1], ts[i] - ts[i-1], vs[i-1], vs[i])
             for i in range(1, len(samples)) if ts[i] - ts[i-1] > 0.25]
    print(f"\nplateaus (>0.25s with no reported change): {len(plats)}")
    for t, dt, v0, v1 in sorted(plats, key=lambda x: -x[1])[:8]:
        print(f"  t={t:5.1f}s  held {dt:5.2f}s at {v0}  then jumped to {v1}  ({v1-v0:+d})")

    W = 15
    sm = [sum(vs[max(0, i-W):i+W+1]) / len(vs[max(0, i-W):i+W+1]) for i in range(len(vs))]
    revs, last = [], 0
    for i in range(1, len(sm)):
        d = sm[i] - sm[i-1]
        if abs(d) < 8:
            continue
        dirn = 1 if d > 0 else -1
        if last and dirn != last:
            revs.append((ts[i], sm[i]))
        last = dirn
    merged = []
    for t, v in revs:
        if not merged or t - merged[-1][0] > 0.4:
            merged.append((t, v))
    print(f"\ndirection reversals in the smoothed output: {len(merged)}")
    for t, v in merged[:15]:
        print(f"  t={t:5.1f}s  output turned around at {int(v)}")

    print("\ntrace (output vs time):")
    n = 44
    for r in range(n):
        lo, hi = r * len(vs) // n, (r + 1) * len(vs) // n
        seg = vs[lo:hi]
        if not seg:
            continue
        m = sum(seg) // len(seg)
        print(f"  t={ts[lo]:5.1f}s {m:>6} |{' ' * int(m / 65535 * 66)}#")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__); sys.exit(2)
    if sys.argv[1] == "capture":
        analyse(capture(sys.argv[2], float(sys.argv[3]) if len(sys.argv) > 3 else 30,
                        sys.argv[4] if len(sys.argv) > 4 else "y"))
    elif sys.argv[1] == "analyse":
        analyse(load(sys.argv[2]))
    else:
        print(__doc__); sys.exit(2)
