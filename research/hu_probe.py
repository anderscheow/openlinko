"""Snapshot and diff the J5 head unit's VHAL properties (read-only).

Use it to find which property holds drive mode / regen level:

    python research/hu_probe.py snap before            # car in Normal, regen Low
    (change ONE setting in the car's own menu)
    python research/hu_probe.py snap after
    python research/hu_probe.py diff before after

    python research/hu_probe.py watch                  # live: print props as they change

Seat / mirror hunt (press the seat memory button, fold the mirrors, move the seat with
its own switches, one thing at a time, and note which props move):

    python research/hu_probe.py --focus seat watch

Needs the laptop on the same hotspot/LAN as the head unit (ADB on :5555, root via su).
It only ever runs `lshal debug ... --get`; it never writes a property.
"""
import argparse
import os
import re
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "tools"))
import headunit as hu  # noqa: E402

ROOT = hu.ROOT
NAMES = os.path.join(ROOT, ".claude", "headunit-assets", "vhal", "names.tsv")
SNAPS = os.path.join(ROOT, ".claude", "headunit-assets", "vhal", "snaps")

# Props worth watching first for a Kinex-style app (drive mode / regen / pedal feel).
PRESETS = {
    "drive": r"REGEN|EGYREC|DRIVEMODE|DRVMOD|PEDAL|CREEP|BRAKE|EPS|STEER|SPORT|ECO",
    "seat": r"SEAT|MIRR|FOLD|SCU|DSM|PSM|MEM|LUMB|HDREST",
}
FOCUS = re.compile(PRESETS["drive"], re.I)

_BLOCK = re.compile(r"\.prop = (\d+)(.*?)(?=\.prop = |\Z)", re.S)
_VALS = re.compile(r"(int32|int64|float)Values = \[\d+\]\{([^}]*)\}")


def load_names():
    names = {}
    with open(NAMES, encoding="utf-8") as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 2:
                names[int(parts[1], 16)] = parts[0]
    return names


def read_all(a, pre, ids, chunk=150):
    """{prop_id: 'value string'} for every id that answers."""
    out = {}
    for i in range(0, len(ids), chunk):
        part = " ".join(map(str, ids[i:i + chunk]))
        raw = a.shell(pre + "sh -c 'for p in %s; do lshal debug %s --get $p 2>&1; done'" % (part, hu.VHAL), timeout=90)
        for pid, body in _BLOCK.findall(raw):
            vals = [("%s:%s" % (t, v.strip())) for t, v in _VALS.findall(body) if v.strip()]
            if vals:
                out[int(pid)] = " ".join(vals)
    return out


def connect(ip):
    if not ip:
        ok = [d["ip"] for d in hu.scan()["found"] if "error" not in d]
        ip = ok[0] if ok else None
    if not ip:
        sys.exit("No head unit found on this network. Pass --ip.")
    a = hu.Adb(ip)
    a.__enter__()
    a.connect()
    pre = hu._root_prefix(a)
    if pre is None:
        sys.exit("No root shell on %s; cannot read VHAL." % ip)
    print("connected to %s (root via %r)" % (ip, pre or "uid 0"), file=sys.stderr)
    return a, pre


def snap_path(name):
    return os.path.join(SNAPS, name + ".tsv")


def save(name, vals, names):
    os.makedirs(SNAPS, exist_ok=True)
    with open(snap_path(name), "w", encoding="utf-8") as f:
        for pid in sorted(vals):
            f.write("%s\t0x%08x\t%s\n" % (names.get(pid, "?"), pid, vals[pid]))


def load(name):
    vals = {}
    with open(snap_path(name), encoding="utf-8") as f:
        for line in f:
            n, pid, v = line.rstrip("\n").split("\t", 2)
            vals[int(pid, 16)] = (n, v)
    return vals


def cmd_snap(args):
    names = load_names()
    a, pre = connect(args.ip)
    ids = sorted(names)
    t = time.time()
    vals = read_all(a, pre, ids)
    save(args.name, vals, names)
    print("saved %d/%d props to %s in %.1fs" % (len(vals), len(ids), snap_path(args.name), time.time() - t))


def cmd_diff(args):
    a, b = load(args.a), load(args.b)
    rows = [(pid, a.get(pid, ("?", "-"))[0] if pid in a else b[pid][0],
             a.get(pid, (0, "-"))[1], b.get(pid, (0, "-"))[1])
            for pid in sorted(set(a) | set(b)) if a.get(pid, (0, None))[1] != b.get(pid, (0, None))[1]]
    rows.sort(key=lambda r: (not FOCUS.search(r[1]), r[1]))
    for pid, n, va, vb in rows:
        mark = "*" if FOCUS.search(n) else " "
        print("%s %-44s 0x%08x  %s  ->  %s" % (mark, n, pid, va, vb))
    print("\n%d changed (* = drive-mode/regen/brake related)" % len(rows))


def cmd_watch(args):
    names = load_names()
    a, pre = connect(args.ip)
    ids = sorted(pid for pid, n in names.items() if args.all or FOCUS.search(n))
    print("watching %d props, Ctrl+C to stop" % len(ids), file=sys.stderr)
    last = read_all(a, pre, ids)
    for pid in ids:
        if pid in last:
            print("  %-44s %s" % (names[pid], last[pid]))
    try:
        while True:
            time.sleep(args.every)
            now = read_all(a, pre, ids)
            for pid, v in now.items():
                if last.get(pid) != v:
                    print("%s %-44s %s -> %s" % (time.strftime("%H:%M:%S"), names[pid], last.get(pid, "-"), v))
            last = now
    except KeyboardInterrupt:
        pass


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ip", help="head unit IP (default: scan the local /24)")
    p.add_argument("--focus", choices=sorted(PRESETS), default="drive",
                   help="which props watch/diff put first (default: drive)")
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snap"); s.add_argument("name"); s.set_defaults(fn=cmd_snap)
    d = sub.add_parser("diff"); d.add_argument("a"); d.add_argument("b"); d.set_defaults(fn=cmd_diff)
    w = sub.add_parser("watch"); w.add_argument("--every", type=float, default=1.0)
    w.add_argument("--all", action="store_true", help="watch every prop, not just the --focus ones")
    w.set_defaults(fn=cmd_watch)
    args = p.parse_args()
    global FOCUS
    FOCUS = re.compile(PRESETS[args.focus], re.I)
    args.fn(args)


if __name__ == "__main__":
    main()
