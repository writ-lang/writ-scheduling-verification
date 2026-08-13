#!/usr/bin/env python3
"""The curriculum, read once — the vocabulary every other script here shares.

Four scripts used to each re-derive the week, the lesson list and the "which
rooms could host this" rule from the YAML, which is three chances too many to
disagree with each other. They all ask this file instead.
"""
from dataclasses import dataclass

import yaml


def bucket(pairs):
    """[(k, v)…] -> {k: [v…]} — the only data structure any of this needs."""
    out = {}
    for k, v in pairs:
        out.setdefault(k, []).append(v)
    return out


@dataclass(frozen=True, order=True)
class Hour:
    """One contact hour the programme demands: 'the 3rd maths hour of 7a'.

    Writ has no numbers, so an hour has to be a THING before it can be counted;
    keeping it a thing on this side too means the two halves agree about what
    is being delivered.
    """
    group: str
    subject: str
    nth: int                       # 1-based, within its group's run of that subject


class School:
    def __init__(self, path="curriculum.yaml"):
        c = yaml.safe_load(open(path))
        self.week = c["week"]
        self.days, self.periods = self.week["days"], self.week["periods"]
        for name in ("rooms", "subjects", "teachers", "groups", "programme"):
            setattr(self, name, c[name])

        self.slots = [f"{d}-{p}" for d in self.days for p in self.periods]
        self.index = {s: i for i, s in enumerate(self.slots)}
        self.demand = [Hour(g, subj, k + 1)
                       for g, prog in self.programme.items()
                       for subj, hours in prog.items()
                       for k in range(hours)]

    # ── the week ────────────────────────────────────────────────────────────
    def day(self, slot):    return slot.rsplit("-", 1)[0]
    def period(self, slot): return slot.rsplit("-", 1)[1]
    def row(self, day):     return [s for s in self.slots if self.day(s) == day]

    def after(self, slot):
        """The next period on the same day, or None at the last bell."""
        row = self.row(self.day(slot))
        i = row.index(slot)
        return row[i + 1] if i + 1 < len(row) else None

    # ── what may go where ───────────────────────────────────────────────────
    def rooms_for(self, hour):
        need = self.subjects[hour.subject]["needs"]
        seats = self.groups[hour.group]["size"]
        return [r for r, spec in self.rooms.items()
                if spec["facility"] == need and spec["seats"] >= seats]

    def teachers_for(self, subject):
        return [t for t, spec in self.teachers.items() if subject in spec["teaches"]]

    def blocked(self, teacher):
        return set(self.teachers[teacher].get("unavailable", []))

    def gym_subjects(self):
        return {s for s, spec in self.subjects.items() if spec["needs"] == "gym"}

    # ── capacity, as a ladder of classes rather than a number ───────────────
    @property
    def sizes(self):
        return sorted({r["seats"] for r in self.rooms.values()} |
                      {g["size"] for g in self.groups.values()})

    def klass(self, seats):
        """The smallest class that seats this many — a room's or a group's."""
        return f"seats-{min(s for s in self.sizes if s >= seats)}"
