#!/usr/bin/env python3
"""Produce a timetable from the curriculum with CP-SAT.

CP-SAT (Google OR-Tools) is a constraint solver: you declare unknowns and the
rules they must obey, and it searches for an assignment obeying all of them —
or proves none exists. Here the unknown is one true/false variable per
(hour, period, room, teacher) combination, and "the timetable" is the set of
variables it turns on.

This is the MAKER half of the pipeline. It knows the hard constraints anyone
would think to write down, and nothing else. What it does not know is the
subject of the audit next door.

    ./solve.py                  the timetable as specified
    ./solve.py --strict         the same, plus the rules the audit found missing
"""
import argparse
import json
import sys

from ortools.sat.python import cp_model

from school import Hour, School, bucket


def model(S, strict):
    m = cp_model.CpModel()

    # The unknowns: could THIS hour be taught in THIS period, room and teacher?
    # Combinations the estate or the staff list rules out never become variables.
    place = {(h, s, r, t): m.new_bool_var(f"{h}@{s}/{r}/{t}")
             for h in S.demand
             for s in S.slots
             for r in S.rooms_for(h)
             for t in S.teachers_for(h.subject) if s not in S.blocked(t)}
    if not place:
        sys.exit("nothing can be placed at all — check rooms, staff and sizes")
    by = lambda key: bucket((key(k), v) for k, v in place.items())

    for vs in by(lambda k: k[0]).values():          # every hour, exactly once
        m.add_exactly_one(vs)
    for vs in by(lambda k: k[1:3]).values():        # a room holds one lesson
        m.add_at_most_one(vs)
    for vs in by(lambda k: (k[1], k[3])).values():  # a teacher teaches one
        m.add_at_most_one(vs)

    # A group is in at most one lesson per period — and `busy` names that fact
    # so the strict rules below can talk about free periods.
    busy = {(g, s): m.new_bool_var(f"busy:{g}:{s}") for g in S.groups for s in S.slots}
    mine = by(lambda k: (k[0].group, k[1]))
    for key, b in busy.items():
        m.add(sum(mine.get(key, [])) == b)

    # Symmetry: the k-th hour of a subject comes before the (k+1)-th. Without
    # it the solver rediscovers the same timetable in every possible order.
    when = {h: m.new_int_var(0, len(S.slots) - 1, f"when:{h}") for h in S.demand}
    offsets = bucket((k[0], S.index[k[1]] * v) for k, v in place.items())
    for h in S.demand:
        m.add(when[h] == sum(offsets[h]))
        if h.nth > 1:
            m.add(when[Hour(h.group, h.subject, h.nth - 1)] < when[h])

    if strict:
        add_school_rules(m, S, place, busy)
    return m, place


def add_school_rules(m, S, place, busy):
    """What the audit found missing, stated as constraints the solver can use."""
    by_day = bucket(((k[0].group, k[0].subject, S.day(k[1])), v) for k, v in place.items())
    for vs in by_day.values():
        m.add(sum(vs) <= 1)          # one hour of a subject per day — no runs, no doubling

    for g in S.groups:               # no free period BETWEEN lessons: a day is one block
        for d in S.days:
            row = S.row(d)
            for i, first in enumerate(row):
                for j in range(i + 2, len(row)):
                    for gap in row[i + 1:j]:
                        m.add(busy[g, first] + busy[g, row[j]] - busy[g, gap] <= 1)

    gym = S.gym_subjects()           # never first thing, never with a lesson straight after
    for (h, s, _r, _t), v in place.items():
        if h.subject not in gym:
            continue
        if S.period(s) == S.periods[0]:
            m.add(v == 0)
        if S.after(s):
            m.add_implication(v, busy[h.group, S.after(s)].negated())


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--curriculum", default="curriculum.yaml")
    ap.add_argument("--strict", action="store_true",
                    help="also encode the rules the audit found missing")
    ap.add_argument("--out", default="-")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    S = School(args.curriculum)
    m, place = model(S, args.strict)

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = args.seed
    solver.parameters.max_time_in_seconds = 120.0
    if solver.solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sys.exit("CP-SAT: no timetable satisfies the curriculum — the estate, the "
                 "staff or the programme has to give")

    # The output is a plain list of placed lessons: no ordinals, no derived
    # fields, nothing the auditor would then be taking on trust from the solver.
    lessons = sorted(({"group": h.group, "subject": h.subject,
                       "teacher": t, "room": r, "slot": s}
                      for (h, s, r, t), v in place.items() if solver.value(v)),
                     key=lambda b: (b["group"], b["subject"], S.index[b["slot"]]))
    out = {"produced_by": "cp-sat",
           "mode": "strict" if args.strict else "as-specified",
           "wall_seconds": round(solver.wall_time, 3), "lessons": lessons}

    if args.out == "-":
        print(json.dumps(out, indent=1))
        return
    with open(args.out, "w") as f:
        f.write(json.dumps(out, indent=1) + "\n")
    print(f"CP-SAT {out['mode']}: {len(lessons)} lessons placed in "
          f"{out['wall_seconds']}s -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
