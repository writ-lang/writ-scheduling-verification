# A school timetable, made by one tool and judged by another

<img src="docs/images/writ-mark-200.png" alt="writ" width="120" align="left" hspace="16" vspace="4">

**One program produces the answer; a different program, which never saw how it
was produced, decides whether the answer is acceptable.**

A school timetable must place every lesson the curriculum demands in a period,
a room and with a teacher, with no clashes. A constraint solver does that well.
But a timetable can satisfy every stated rule and still be one no school would
publish — sport first thing Monday, no time to change after PE, a free period
nobody supervises. Those rules are real and nobody writes them down, so no
solver hears about them. This repository asks the second question: *is the
timetable any good, and what did nobody say?*

<br clear="left">

## How it works

```
curriculum.yaml ──► solve.py (CP-SAT) ──► schedule.json     the maker
       │                                       │
       └──────────► to_writ.py ◄────────────────┘
                        │
                  timetable.writ ──► writ check --claims timetable.claims
                                          │                 the judge
                                    holds / fails / gaps / the offenders, named
```

- **[CP-SAT](https://developers.google.com/optimization/cp/cp_solver)** (Google
  OR-Tools) builds the week from [curriculum.yaml](curriculum.yaml).
- **[writ](https://github.com/writ-lang/writ)** judges it against
  [timetable.claims](timetable.claims), questions written once and reused
  every term. [to_writ.py](to_writ.py) only transcribes.

The two share only the curriculum. The judge never sees the solver's
constraints, so it can catch what the solver was never told.

## Run it

```sh
cd ../writ && make image && cd -     # the writ image, once
docker compose up                    # all three acts
```

Or natively with `writ`, Python, `ortools` and `pyyaml`: `./run.sh all`,
which asserts what each act must produce.

## Three acts

**1 — The timetable as specified.** CP-SAT places 60 lessons in a second. Every
rule it was given holds when checked independently. Then:

```
fails  sport-not-first
fails  time-to-change-after-sport

gaps: 2
  window-unstated   — "the curriculum is silent: may a group have a free period
                       BETWEEN two lessons, and who supervises it?"
  doubling-unstated — "the curriculum is silent: may two hours of one subject
                       fall on the same day?"
```

Two unwritten rules broken, and two questions nobody answered — which the
solver therefore settled by accident. The gaps are questions to put back to
whoever wrote the curriculum.

**2 — The same timetable, damaged.** [tamper.py](tamper.py) double-books a
room, loses a lesson and adds an unqualified cover teacher. Each defect comes
back named — not just *that* the timetable is wrong, but *which lessons* make
it so.

**3 — Solved again, with the findings added.** `./solve.py --strict` encodes
what act 1 exposed. The audit then reports no gaps and every property holds:
audit, tighten, re-audit.

## Counting without numbers

writ has no arithmetic — that is what lets it answer *never* questions by
census. So "five hours of maths" is five `demand` entities, and three
properties make lesson ↔ demand a bijection: every hour taught, none invented,
none taught twice. Exact counting, never counted.

Judging is cheap because a decided timetable has nothing left to vary: the
model is a single situation, and all the work is in the questions (0.26 s for
60 lessons, 6 s for 240). *Making* a timetable is a search problem and belongs
to CP-SAT.

A frozen version, with the schedule committed as a fixture, is the
`timetable/` scenario in [writ-problems](https://github.com/writ-lang/writ-problems).
