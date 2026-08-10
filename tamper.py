#!/usr/bin/env python3
"""Break a produced schedule on purpose, so the audit can be seen to bite.

A checker that only ever says "holds" has proved nothing about itself. Each
defect below is one a real pipeline produces — a botched manual edit, a lesson
lost in an export, a cover teacher dropped in without checking the syllabus —
and each should come back from `pol check` named, not merely counted.

    ./tamper.py schedule.json -o schedule.tampered.json
"""
import argparse
import json
import sys


def double_book(lessons, note):
    """Move one lesson on top of another: same room, same period."""
    a = lessons[0]
    b = next((x for x in lessons
              if x["group"] != a["group"] and x["room"] != a["room"]), None)
    if b is None:
        sys.exit("nothing to double-book")
    note(f"double-booked {a['room']} at {a['day']}-{a['period']}: "
         f"{b['group']}/{b['subject']} moved on top of {a['group']}/{a['subject']}")
    b["room"], b["day"], b["period"] = a["room"], a["day"], a["period"]


def drop_an_hour(lessons, note):
    """Lose one lesson entirely — a hole in the programme."""
    victim = lessons[len(lessons) // 2]
    note(f"dropped {victim['group']}/{victim['subject']} at "
         f"{victim['day']}-{victim['period']}")
    lessons.remove(victim)


def wrong_teacher(lessons, note, curriculum):
    """Put a teacher in front of a subject they are not qualified in."""
    import yaml
    cur = yaml.safe_load(open(curriculum))
    for x in lessons:
        wrong = next((t for t, spec in cur["teachers"].items()
                      if x["subject"] not in spec["teaches"]), None)
        if wrong:
            note(f"put {wrong} in front of {x['group']}/{x['subject']} at "
                 f"{x['day']}-{x['period']}")
            x["teacher"] = wrong
            return
    sys.exit("everybody is qualified in everything")


DEFECTS = {"clash": double_book, "drop": drop_an_hour, "unqualified": wrong_teacher}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("schedule")
    ap.add_argument("--curriculum", default="curriculum.yaml")
    ap.add_argument("-o", "--out", default="schedule.tampered.json")
    ap.add_argument("--defect", action="append", choices=sorted(DEFECTS),
                    help="repeatable; default is all three")
    args = ap.parse_args()

    sched = json.load(open(args.schedule))
    lessons = sched["lessons"]
    notes = []
    for name in (args.defect or sorted(DEFECTS)):
        fn = DEFECTS[name]
        if name == "unqualified":
            fn(lessons, notes.append, args.curriculum)
        else:
            fn(lessons, notes.append)

    sched["mode"] = sched.get("mode", "?") + " + tampered"
    sched["tampering"] = notes
    with open(args.out, "w") as f:
        f.write(json.dumps(sched, indent=1) + "\n")
    for n in notes:
        print(f"  tampered: {n}", file=sys.stderr)
    print(f"-> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
