#!/usr/bin/env python3
"""Transcribe the curriculum and a produced schedule into a Pol instance.

A TRANSCRIBER, not a checker, and the distinction is the basis of trusting the
audit. It decides exactly one thing: `b-nth`, which hour of that subject a
lesson is, by position in the week. Everything else is a literal copy.

Even that one decision is checked rather than trusted — `hours-not-doubled` in
timetable.claims fails if two lessons get the same ordinal, and
`curriculum-delivered` / `nothing-extra` force the numbering to be a bijection
onto the programme. A transcriber that miscounted is caught by the file it is
feeding.

    ./to_pol.py schedule.json -o timetable.pol
"""
import argparse
import json
import os
import sys

from school import School, bucket

# Members of the enumerated types timetable.lib.pol declares. Names are global
# across the loaded universe and may not be redeclared (Pol §7), so an entity
# in curriculum.yaml may not take one of these.
RESERVED = {"plain", "computers", "gym", "vacant", "school", "slot", "room",
            "teacher", "subject", "group", "demand", "booking", "ordinal",
            "qualification", "blackout", "facility", "size-t", "day-t",
            "period-t", "id-t"}


class Names:
    """Every entity name emitted, kept distinct — as Pol requires."""

    def __init__(self):
        self.seen = set()

    def __call__(self, base):
        if base in RESERVED:
            sys.exit(f"'{base}' is a reserved name — rename it in curriculum.yaml")
        name, n = base, 1
        while name in self.seen:            # a damaged schedule may repeat one
            n += 1
            name = f"{base}-again{n}"
        self.seen.add(name)
        return name


def clause(kind, name, **slots):
    """(kind name (arrow value) …) — the one shape an instance is made of."""
    body = "".join(f" ({k.replace('_', '-')} {v})" for k, v in slots.items())
    return f"  ({kind} {name}{body})"


def week(S, fresh):
    yield f"  (day-t {' '.join(S.days)})"
    yield f"  (period-t {' '.join(S.periods)})"
    for i, s in enumerate(S.slots):
        yield clause("slot", fresh(s), next=S.slots[i + 1] if i + 1 < len(S.slots) else "vacant",
                     day=S.day(s), period=S.period(s))


def capacity(S, fresh):
    """Seat counts as a ladder of classes: Pol compares by walking, not by <."""
    if len(S.sizes) > 4:
        sys.exit(f"{len(S.sizes)} distinct capacities, but `fits` in "
                 f"timetable.lib.pol walks a ladder of 4 — extend the form or "
                 f"bucket the capacities")
    for i, n in enumerate(S.sizes):
        yield clause("size-t", fresh(S.klass(n)),
                     bigger=S.klass(S.sizes[i + 1]) if i + 1 < len(S.sizes) else "vacant")


def estate(S, fresh):
    for r, spec in S.rooms.items():
        yield clause("room", fresh(r), provides=spec["facility"], holds=S.klass(spec["seats"]))
    for t in S.teachers:
        yield clause("teacher", fresh(t))
    for s, spec in S.subjects.items():
        yield clause("subject", fresh(s), needs=spec["needs"])
    for g, spec in S.groups.items():
        yield clause("group", fresh(g), size=S.klass(spec["size"]))


def permissions(S, fresh):
    for t, spec in S.teachers.items():
        for s in spec["teaches"]:
            yield clause("qualification", fresh(f"may-{t}-{s}"), q_teacher=t, q_subj=s)
        for u in spec.get("unavailable", []):
            yield clause("blackout", fresh(f"not-{t}-{u}"), x_teacher=t, x_slot=u)


def curriculum(S, fresh, ordinals):
    yield f"  (ordinal {' '.join(ordinals)})"
    for h in S.demand:
        yield clause("demand", fresh(f"owed-{h.group}-{h.subject}-{h.nth}"),
                     d_group=h.group, d_subj=h.subject, d_nth=f"hour-{h.nth}")


def timetable(S, fresh, lessons):
    """The lessons, each carrying WHICH hour of its subject it is.

    That ordinal is the only thing this file works out, and it is worked out by
    position in the week — the schedule is sorted, never interpreted.
    """
    runs = bucket(((b["group"], b["subject"]), b) for b in lessons)
    ids, rows = [], []
    for run in runs.values():
        for nth, b in enumerate(sorted(run, key=lambda b: S.index[b["slot"]]), 1):
            at = f"{b['group']}-{b['subject']}-{b['slot']}"
            ids.append(fresh(f"id-{at}"))
            rows.append(clause("booking", fresh(at),
                               b_group=b["group"], b_subj=b["subject"],
                               b_teacher=b["teacher"], b_room=b["room"],
                               b_slot=b["slot"], b_nth=f"hour-{nth}", b_id=ids[-1]))
    yield f"  (id-t {' '.join(ids)})"
    yield from rows


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("schedule")
    ap.add_argument("--curriculum", default="curriculum.yaml")
    ap.add_argument("-o", "--out", default="timetable.pol")
    ap.add_argument("--lib", default="timetable.lib.pol")
    args = ap.parse_args()

    S = School(args.curriculum)
    sched = json.load(open(args.schedule))
    lessons = sched["lessons"]
    fresh = Names()

    # Enough ordinals to name every hour — demanded or delivered, since an
    # over-delivering schedule must be nameable in order to be reported.
    taught = bucket(((b["group"], b["subject"]), b) for b in lessons)
    top = max([1] + [h.nth for h in S.demand] + [len(v) for v in taught.values()])
    ordinals = [f"hour-{k}" for k in range(1, top + 1)]

    sections = [("the week", week(S, fresh)),
                ("capacity, as a small named scale", capacity(S, fresh)),
                ("the estate, the staff, the syllabus", estate(S, fresh)),
                ("who may teach what, and who is away when", permissions(S, fresh)),
                ("THE CURRICULUM: one entity per hour the programme demands",
                 curriculum(S, fresh, ordinals)),
                ("THE TIMETABLE: one entity per lesson the solver placed",
                 timetable(S, fresh, lessons))]

    body = [f"; GENERATED by to_pol.py from {os.path.basename(args.curriculum)} "
            f"and {os.path.basename(args.schedule)} — do not edit.",
            f"; The schedule was produced by: {sched.get('produced_by', '?')} "
            f"({sched.get('mode', '?')}).",
            f'(load "{args.lib}")', "", "(instance week school"]
    for title, lines in sections:
        body += [f"  ; ── {title} ──", *lines]
    body += ["  )", "", "(use school)", "(initial week)", "",
             "; Where the curriculum runs out. Declared in the library, invoked here",
             "; because a loaded file may not carry a transition of its own.",
             "(silence-windows a b c)", "(silence-doubling a b)"]

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w") as f:
        f.write("\n".join(body) + "\n")
    print(f"transcribed {len(lessons)} lessons against {len(S.demand)} demanded "
          f"hours -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
