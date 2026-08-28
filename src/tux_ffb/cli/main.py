"""tux-ffb command line.

Not a lesser sibling of the GUI: this is the debugging tool, the scripting
surface, and the thing that works over SSH. Everything it does goes through
core/, which has no toolkit dependency.
"""

from __future__ import annotations

import argparse
import json
import sys

from ..core.commands import Table
from ..core.device import Device, UnsafeWrite
from ..core.transport import Transport

PORT_HELP = "serial device (default: discovered by USB id)"


def _fmt(v):
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:g}"
    return str(v)


def cmd_devices(args) -> int:
    from ..core.discovery import find_ports
    ports = find_ports()
    if not ports:
        print("  no MOZA flight base found")
        print("  (the base is powered separately — check it is switched on)")
        return 1
    for path, pid in ports:
        print(f"  {path}   346e:{pid}")
    return 0


def cmd_list(args) -> int:
    table = Table.load()
    print(f"{len(table.settings)} settings\n")
    for name, s in table.settings.items():
        flags = []
        if not s.effect_verified:
            flags.append("effect:unverified")
        if not s.writable:
            flags.append("read-only")
        print(f"  {name:<22} {len(s.addresses)} addr  {s.type:<6} "
              f"{(s.unit or ''):<8} {' '.join(flags)}")
    for name in table.actions:
        print(f"\n  action: {name}")
    return 0


def cmd_dump(args) -> int:
    with Transport(args.port) as t:
        dev = Device(t)
        readings = dev.read_all()
        if args.json:
            print(json.dumps({n: [{"addr": list(r.address), "value": r.value} for r in rs]
                              for n, rs in readings.items()}, indent=1))
            return 0
        for name, rs in readings.items():
            s = rs[0].setting
            mark = "" if s.effect_verified else "  (effect unverified)"
            if len(rs) == 1:
                print(f"  {name:<22} {_fmt(rs[0].value)}{mark}")
            else:
                vals = ", ".join(_fmt(r.value) for r in rs)
                print(f"  {name:<22} [{vals}]{mark}")
    return 0


def cmd_get(args) -> int:
    with Transport(args.port) as t:
        for r in Device(t).read(args.name):
            print(f"  {r.label:<28} {_fmt(r.value)}")
    return 0


def cmd_set(args) -> int:
    with Transport(args.port) as t:
        dev = Device(t)
        try:
            ok, note = dev.write(args.name, args.value, index=args.index,
                                 expect=args.expect)
        except UnsafeWrite as e:
            print(f"refused: {e}")
            return 2
        print(f"  {'OK' if ok else 'FAILED'}: {args.name} = {args.value} — {note}")
        return 0 if ok else 1


def cmd_backup(args) -> int:
    with Transport(args.port) as t:
        dev = Device(t)
        data = {"settings": {n: [r.value for r in rs] for n, rs in dev.read_all().items()},
                "parameters": dev.backup_parameters()}
    with open(args.file, "w") as fh:
        json.dump(data, fh, indent=1)
    print(f"  wrote {len(data['settings'])} settings and "
          f"{len(data['parameters'])} raw parameters to {args.file}")
    print("  note: parameters are a record, not a restorable image — there is no known\n"
          "        write path into that space. A lost calibration is re-run, not restored.")
    return 0


def cmd_calibrate(args) -> int:
    with Transport(args.port) as t:
        dev = Device(t)
        pct = dev.calibration_percent()
        print(f"  current calibration reads {pct}%")
        if not args.yes:
            print("\n  This drives the motor for about 53 seconds.")
            print("  The stick must be free and untouched for the whole run.")
            print("  Re-run with --yes to proceed.")
            return 0
        print("\n  calibrating — do not touch the stick\n")
        ok = dev.calibrate_cogging(progress=lambda p: print(f"    {p:>3}%", flush=True))
        print(f"\n  {'complete' if ok else 'DID NOT COMPLETE'}")
        return 0 if ok else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="tux-ffb-cli",
                                 description="Configure MOZA force-feedback flight bases")
    ap.add_argument("--port", default=None, help=PORT_HELP)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("devices", help="list detected bases").set_defaults(fn=cmd_devices)
    sub.add_parser("list", help="show known settings").set_defaults(fn=cmd_list)
    p = sub.add_parser("dump", help="read every setting"); p.add_argument("--json", action="store_true")
    p.set_defaults(fn=cmd_dump)
    p = sub.add_parser("get", help="read one setting"); p.add_argument("name")
    p.set_defaults(fn=cmd_get)
    p = sub.add_parser("set", help="write one setting")
    p.add_argument("name"); p.add_argument("value", type=int)
    p.add_argument("--index", type=int, default=0, help="which address of a multi-address setting")
    p.add_argument("--expect", type=int, help="abort unless the current value matches")
    p.set_defaults(fn=cmd_set)
    p = sub.add_parser("backup", help="record settings and raw parameters")
    p.add_argument("file"); p.set_defaults(fn=cmd_backup)
    p = sub.add_parser("calibrate", help="run the cogging torque calibration")
    p.add_argument("--yes", action="store_true", help="actually run it")
    p.set_defaults(fn=cmd_calibrate)

    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
