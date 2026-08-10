#!/usr/bin/env python3
"""Print a produced schedule as the grid a head of year would actually read."""
import argparse
import json

from school import School, bucket

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("schedule")
ap.add_argument("--curriculum", default="curriculum.yaml")
ap.add_argument("--group", help="only this group")
a = ap.parse_args()

S = School(a.curriculum)
sched = json.load(open(a.schedule))
cells = {(b["group"], b["slot"]): f"{b['subject']}/{b['room']}" for b in sched["lessons"]}
W = 17

for g in S.groups:
    if a.group and g != a.group:
        continue
    print(f"\n{g}   ({sched.get('mode', '?')})")
    print("      " + "".join(d.ljust(W) for d in S.days))
    for p in S.periods:
        print(f"  {p}  " + "".join(cells.get((g, f"{d}-{p}"), "·").ljust(W) for d in S.days))
