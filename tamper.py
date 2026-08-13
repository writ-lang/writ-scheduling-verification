#!/usr/bin/env python3
"""Break a produced schedule on purpose, so the audit can be seen to bite.

A checker that only ever says "holds" has proved nothing about itself. Each
defect here is one a real pipeline produces — a botched manual edit, a lesson
lost in an export, a cover teacher dropped in without checking the syllabus —
and each should come back from `writ check` named, not merely counted.

    ./tamper.py schedule.json -o schedule.tampered.json [--defect clash …]
"""
import argparse
import json
import sys

from school import School


def name(b):
    return f"{b['group']}/{b['subject']} at {b['slot']}"


def clash(S, lessons):
    """Move one lesson on top of another: same room, same period."""
    a = lessons[0]
    b = next(x for x in lessons if x["group"] != a["group"] and x["room"] != a["room"])
    moved = name(b)
    b["room"], b["slot"] = a["room"], a["slot"]
    return f"double-booked {a['room']} at {a['slot']}: {moved} moved on top of {name(a)}"


def drop(_S, lessons):
    """Lose one lesson entirely — a hole in the programme."""
    gone = lessons.pop(len(lessons) // 2)
    return f"dropped {name(gone)}"


def unqualified(S, lessons):
    """Put a teacher in front of a subject they are not qualified in."""
    for b in lessons:
        wrong = next((t for t, spec in S.teachers.items()
                      if b["subject"] not in spec["teaches"]), None)
        if wrong:
            b["teacher"] = wrong
            return f"put {wrong} in front of {name(b)}"
    sys.exit("everybody is qualified in everything")


DEFECTS = {"clash": clash, "drop": drop, "unqualified": unqualified}

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("schedule")
ap.add_argument("--curriculum", default="curriculum.yaml")
ap.add_argument("-o", "--out", default="schedule.tampered.json")
ap.add_argument("--defect", action="append", choices=sorted(DEFECTS),
                help="repeatable; default is all three")
a = ap.parse_args()

S = School(a.curriculum)
sched = json.load(open(a.schedule))
sched["tampering"] = [DEFECTS[d](S, sched["lessons"]) for d in (a.defect or sorted(DEFECTS))]
sched["mode"] = sched.get("mode", "?") + " + tampered"

with open(a.out, "w") as f:
    f.write(json.dumps(sched, indent=1) + "\n")
for note in sched["tampering"]:
    print(f"  tampered: {note}", file=sys.stderr)
print(f"-> {a.out}", file=sys.stderr)
