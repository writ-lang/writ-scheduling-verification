#!/usr/bin/env python3
"""Print a produced schedule as the grid a head of year would actually read."""
import argparse
import json
from collections import defaultdict

import yaml

ap = argparse.ArgumentParser()
ap.add_argument("schedule")
ap.add_argument("--curriculum", default="curriculum.yaml")
ap.add_argument("--group", help="only this group")
a = ap.parse_args()

cur = yaml.safe_load(open(a.curriculum))
sched = json.load(open(a.schedule))
days, periods = cur["week"]["days"], cur["week"]["periods"]

cells = defaultdict(dict)
for b in sched["lessons"]:
    cells[b["group"]][b["day"], b["period"]] = f"{b['subject']}/{b['room']}"

w = 17
for g in cur["groups"]:
    if a.group and g != a.group:
        continue
    print(f"\n{g}   ({sched.get('mode', '?')})")
    print("      " + "".join(d.ljust(w) for d in days))
    for p in periods:
        row = "".join((cells[g].get((d, p), "·")).ljust(w) for d in days)
        print(f"  {p}  {row}")
