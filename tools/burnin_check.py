#!/usr/bin/env python3
"""Check that hackterm --screensaver doesn't keep any screen cell the same for long.

Runs the screensaver headlessly on a fake clock and samples the whole terminal every
--every seconds. For each cell it tracks two streaks:

  same  the cell shows the same lit glyph in the same colours   (target: < 2 min)
  lit   the cell is lit at all, whatever it shows               (target: the blackout interval)

A cell counts as lit when it shows a visible glyph or a background brighter than near-black.

  tools/burnin_check.py                      2 hours at 160x45 and 80x24
  tools/burnin_check.py --hours 0.5 --size 120x40 --theme 2
"""
import argparse
import importlib.util
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("hackterm", os.path.join(HERE, "..", "hackterm.py"))
hk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hk)

DARK = 0.04   # luminance at or below this counts as off


def run(W, H, hours, every, theme, seed):
    hk.R.seed(seed)
    clock = {"t": 0.0}
    real_strftime = time.strftime
    hk.time.strftime = lambda fmt, *a: real_strftime(fmt, time.gmtime(1_800_000_000 + clock["t"]))
    app = hk.App(boot=True)
    app.ti = theme % len(app.themes)
    app.start_saver()
    app.resize(W, H)
    n = W * H
    lum_cache = {}

    def lum(c):
        v = lum_cache.get(c)
        if v is None:
            v = lum_cache[c] = hk.lum(c)
        return v

    prev = [None] * n
    same_start = [0.0] * n
    lit_start = [None] * n
    worst_same = [0.0] * n
    worst_lit = [0.0] * n
    what = [""] * n
    steps = max(1, int(round(every / 0.1)))
    t, end = 0.0, hours * 3600
    while t <= end:
        for _ in range(steps):
            clock["t"] = t
            app.update(0.1, t)
            t += 0.1
        app.draw(t)
        ch, fg, bg = app.scr.compose()
        for i in range(n):
            c, f, b = ch[i], fg[i], bg[i]
            lit = (c != " " and lum(f) > DARK) or lum(b) > DARK
            if not lit:
                lit_start[i] = None
                prev[i] = None
                continue
            if lit_start[i] is None:
                lit_start[i] = t
            d = t - lit_start[i]
            if d > worst_lit[i]:
                worst_lit[i] = d
            key = (c, f, b)
            if key != prev[i]:
                prev[i] = key
                same_start[i] = t
            d = t - same_start[i]
            if d > worst_same[i]:
                worst_same[i] = d
                what[i] = c
    return worst_same, worst_lit, what


def report(W, H, worst_same, worst_lit, what, max_same, max_lit):
    n = W * H
    ms = max(range(n), key=worst_same.__getitem__)
    ml = max(range(n), key=worst_lit.__getitem__)
    over_same = sum(v > max_same for v in worst_same)
    over_lit = sum(v > max_lit for v in worst_lit)
    print(f"{W}x{H}: longest same  {worst_same[ms] / 60:5.1f} min at ({ms % W},{ms // W}) {what[ms]!r}; "
          f"{over_same} cells over {max_same / 60:g} min")
    print(f"{W}x{H}: longest lit   {worst_lit[ml] / 60:5.1f} min at ({ml % W},{ml // W}); "
          f"{over_lit} cells over {max_lit / 60:g} min")
    if over_same:   # what the stuck cells are showing, most common first
        tally = {}
        for i in range(n):
            if worst_same[i] > max_same:
                tally[what[i]] = tally.get(what[i], 0) + 1
        print("   stuck glyphs:", sorted(tally.items(), key=lambda kv: -kv[1])[:12])
    return over_same == 0 and over_lit == 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hours", type=float, default=2.0)
    ap.add_argument("--size", action="append", help="WxH; repeatable (default 160x45 and 80x24)")
    ap.add_argument("--every", type=float, default=2.0, help="seconds between samples (default 2)")
    ap.add_argument("--theme", type=int, default=0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--max-same", type=float, default=2.0, help="minutes (default 2)")
    lit_default = (hk.BLACKOUT_EVERY + 30) / 60   # the blackouts are what end a busy cell's streak
    ap.add_argument("--max-lit", type=float, default=lit_default, help=f"minutes (default {lit_default:g})")
    a = ap.parse_args()
    ok = True
    for s in a.size or ["160x45", "80x24"]:
        W, H = (int(v) for v in s.lower().split("x"))
        res = run(W, H, a.hours, a.every, a.theme, a.seed)
        ok &= report(W, H, *res, a.max_same * 60, a.max_lit * 60)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
