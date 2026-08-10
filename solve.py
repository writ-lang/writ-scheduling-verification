#!/usr/bin/env python3
"""Produce a timetable from the curriculum with CP-SAT.

This is the MAKER half of the pipeline. It knows the hard constraints anyone
would think to write down — deliver the programme, nothing in two places at
once, the right kind of room, a big enough room, a qualified teacher who is
free — and it knows nothing else. What it does not know is the subject of the
audit next door.

    ./solve.py                  the timetable as specified
    ./solve.py --strict         the same, with the audit's findings encoded too

Writes a schedule as JSON on stdout or to --out. The output is a plain list of
placed lessons: no ordinals, no derived fields, nothing the checker would then
be taking on trust from the solver.
"""
import argparse
import json
import sys

import yaml
from ortools.sat.python import cp_model


def load(path):
    with open(path) as f:
        return yaml.safe_load(f)


def build(cur, strict):
    days = cur["week"]["days"]
    periods = cur["week"]["periods"]
    slots = [(d, p) for d in days for p in periods]          # week order
    sidx = {s: i for i, s in enumerate(slots)}
    day_of = {i: s[0] for i, s in enumerate(slots)}
    per_of = {i: s[1] for i, s in enumerate(slots)}
    by_day = {d: [i for i, s in enumerate(slots) if s[0] == d] for d in days}

    rooms, subjects, teachers, groups = (
        cur["rooms"], cur["subjects"], cur["teachers"], cur["groups"])

    blocked = {t: {sidx[tuple(u.split("-", 1))] for u in spec.get("unavailable", [])}
               for t, spec in teachers.items()}

    # One lesson per contact hour the programme demands.
    lessons = [(g, subj, k)
               for g, prog in cur["programme"].items()
               for subj, hours in prog.items()
               for k in range(hours)]

    def rooms_for(g, subj):
        return [r for r, spec in rooms.items()
                if spec["facility"] == subjects[subj]["needs"]
                and spec["seats"] >= groups[g]["size"]]

    def teachers_for(subj):
        return [t for t, spec in teachers.items() if subj in spec["teaches"]]

    m = cp_model.CpModel()
    x = {}                                   # (lesson, slot, room, teacher) -> bool
    for li, (g, subj, k) in enumerate(lessons):
        rs, ts = rooms_for(g, subj), teachers_for(subj)
        if not rs:
            sys.exit(f"no room can host {subj} for {g} — the curriculum is infeasible")
        if not ts:
            sys.exit(f"nobody is qualified to teach {subj} — the curriculum is infeasible")
        for si in range(len(slots)):
            for r in rs:
                for t in ts:
                    if si in blocked[t]:
                        continue             # teacher unavailable: never a variable
                    x[li, si, r, t] = m.new_bool_var(f"x{li}_{si}_{r}_{t}")

    by_lesson, by_room_slot, by_teacher_slot, by_group_slot = ({}, {}, {}, {})
    for (li, si, r, t), v in x.items():
        by_lesson.setdefault(li, []).append(v)
        by_room_slot.setdefault((r, si), []).append(v)
        by_teacher_slot.setdefault((t, si), []).append(v)
        by_group_slot.setdefault((lessons[li][0], si), []).append(v)

    # Every demanded hour is placed exactly once.
    for li in range(len(lessons)):
        m.add_exactly_one(by_lesson[li])

    # Nothing in two places at once.
    for vs in by_room_slot.values():
        m.add_at_most_one(vs)
    for vs in by_teacher_slot.values():
        m.add_at_most_one(vs)

    busy = {}                                # (group, slot) -> bool
    for g in groups:
        for si in range(len(slots)):
            b = m.new_bool_var(f"busy_{g}_{si}")
            m.add(sum(by_group_slot.get((g, si), [])) == b)   # ≤ 1 per period
            busy[g, si] = b

    # Symmetry: the k-th hour of a subject comes before the (k+1)-th.
    pos = {}
    slot_terms = {}
    for (li, si, _r, _t), v in x.items():
        slot_terms.setdefault(li, []).append(si * v)
    for li in range(len(lessons)):
        v = m.new_int_var(0, len(slots) - 1, f"pos{li}")
        m.add(v == sum(slot_terms[li]))
        pos[li] = v
    for li, (g, subj, k) in enumerate(lessons):
        for lj, (g2, subj2, k2) in enumerate(lessons):
            if g == g2 and subj == subj2 and k2 == k + 1:
                m.add(pos[li] < pos[lj])

    if strict:
        # ---- what the audit found, encoded ---------------------------------
        sport = [s for s in subjects if subjects[s]["needs"] == "gym"]
        for g in groups:
            for d in days:
                day_slots = by_day[d]
                # no three hours of one subject back to back
                for subj in subjects:
                    mine = [li for li, (lg, ls, _) in enumerate(lessons)
                            if lg == g and ls == subj]
                    for a in range(len(day_slots) - 2):
                        run = day_slots[a:a + 3]
                        m.add(sum(v for key, v in x.items()
                                  if key[0] in mine and key[1] in run) <= 2)
                # no two hours of one subject on the same day
                for subj in subjects:
                    mine = [li for li, (lg, ls, _) in enumerate(lessons)
                            if lg == g and ls == subj]
                    m.add(sum(v for key, v in x.items()
                              if key[0] in mine and key[1] in day_slots) <= 1)
                # no free period BETWEEN two lessons: the day is one block
                for a in range(len(day_slots)):
                    for c in range(a + 2, len(day_slots)):
                        for b in range(a + 1, c):
                            m.add(busy[g, day_slots[a]] + busy[g, day_slots[c]]
                                  - busy[g, day_slots[b]] <= 1)
        for key, v in x.items():
            li, si = key[0], key[1]
            subj = lessons[li][1]
            if subj in sport:
                # never first thing, and never with a lesson straight after
                if per_of[si] == periods[0]:
                    m.add(v == 0)
                g = lessons[li][0]
                if si + 1 < len(slots) and day_of[si + 1] == day_of[si]:
                    m.add_implication(v, busy[g, si + 1].negated())

    return m, x, lessons, slots


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--curriculum", default="curriculum.yaml")
    ap.add_argument("--strict", action="store_true",
                    help="also encode the rules the audit found missing")
    ap.add_argument("--out", default="-")
    ap.add_argument("--seed", type=int, default=1)
    args = ap.parse_args()

    cur = load(args.curriculum)
    m, x, lessons, slots = build(cur, args.strict)

    solver = cp_model.CpSolver()
    solver.parameters.random_seed = args.seed
    solver.parameters.max_time_in_seconds = 60.0
    status = solver.solve(m)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sys.exit(f"CP-SAT: no timetable satisfies the curriculum ({solver.status_name(status)})")

    placed = []
    for (li, si, r, t), v in x.items():
        if solver.value(v):
            g, subj, _ = lessons[li]
            d, p = slots[si]
            placed.append({"group": g, "subject": subj, "teacher": t,
                           "room": r, "day": d, "period": p})
    placed.sort(key=lambda b: (b["group"], b["subject"], slots.index((b["day"], b["period"]))))

    out = {"produced_by": "cp-sat", "mode": "strict" if args.strict else "as-specified",
           "wall_seconds": round(solver.wall_time, 3), "lessons": placed}
    text = json.dumps(out, indent=1)
    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w") as f:
            f.write(text + "\n")
        print(f"CP-SAT {out['mode']}: {len(placed)} lessons placed in "
              f"{out['wall_seconds']}s -> {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
