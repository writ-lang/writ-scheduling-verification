# A timetable CP-SAT makes and `pol` audits

CP-SAT is very good at producing a timetable that satisfies the constraints it
was given. It has nothing to say about the constraints it was *not* given, and
that is where school timetables actually go wrong: the schedule is feasible,
optimal, and unusable, because nobody wrote down that a class should not be sent
straight from PE into maths, or that the programme never said what a group does
in a free period.

So the two tools are given different jobs:

| | knows | produces |
|---|---|---|
| `solve.py` (CP-SAT) | the hard constraints anyone would think to encode | a timetable |
| `pol` | what a timetable must be for the school to accept it | a verdict, with the offending lessons named |

They share one file — [curriculum.yaml](curriculum.yaml) — and nothing else. The
auditor never sees the solver's model, which is the only reason its answer is
worth anything.

## Run it

```console
$ cd ../pol && make image          # tags pol:latest, once
$ cd ../pol-scheduling-verification
$ docker compose up                # all three acts
$ docker compose run --rm audit    # or just one
```

Or on a host that already has `pol`, Python, `ortools` and `pyyaml`:

```console
$ ./run.sh all
```

`run.sh` asserts what each act should produce, so it is a test of the audit and
not just a demonstration of it — it exits 0 only if all twelve assertions hold.
Note that `pol check` exits **1 when it has a finding**, which is a verdict and
not an error: acts 1 and 2 expect 1, act 3 expects 0.

## The three acts

**Act 1 — the timetable as specified.** CP-SAT places 60 lessons in under a
second. Everything the solver was told holds when checked independently:

```
holds  curriculum-delivered      holds  no-room-clash
holds  nothing-extra             holds  room-fit
holds  hours-not-doubled         holds  room-big-enough
holds  no-group-clash            holds  teacher-qualified
holds  no-teacher-clash          holds  teacher-available
```

and then:

```
gaps: 2
  window-unstated   — "the curriculum is silent: may a group have a free period
                       BETWEEN two lessons, and who supervises it?"
  doubling-unstated — "the curriculum is silent: may two hours of one subject
                       fall on the same day?"
fails  sport-not-first
fails  time-to-change-after-sport
```

Two rules any teacher would state out loud, broken; and two questions the
curriculum never answered, which the solver therefore settled by accident. The
gaps are the more valuable half: **they are questions to put back to whoever
wrote the curriculum**, derived mechanically rather than noticed by someone
reading a grid.

**Act 2 — the same timetable, damaged.** [tamper.py](tamper.py) double-books a
room, loses one lesson in the export, and drops in an unqualified cover teacher
— the three things a real pipeline does to a schedule between the solver and the
noticeboard. Each comes back named, not merely counted:

```
fails  no-room-clash             clashes  (at state 0)
fails  curriculum-delivered        a = g-7a-art-thu-p3, b = g-7b-art-thu-p3
fails  teacher-qualified         missing-hours  (at state 0)
                                   d = owed-g-7b-math-5
                                 unqualified  (at state 0)
                                   b = g-7a-art-thu-p3
```

A failing property says *that* the timetable is wrong; the queries beside it say
*which lessons* make it wrong. `pol query timetable.pol clashes` asks one on its
own.

**Act 3 — solved again with the findings encoded.** `./solve.py --strict` adds
what act 1 exposed. The audit then comes back `gaps: none`, every property
holds, exit 0. That is the loop the pipeline exists to close: **audit, tighten
the model, re-audit** — and the audit is the thing that stays fixed while the
solver changes.

## What `pol` is asked

All of it lives in [timetable.claims](timetable.claims), hand-written and
stable across terms. Point it at next year's schedule unchanged.

- **I. Does it deliver the curriculum** — every hour owed, no hour invented, no
  hour claimed twice.
- **II. Is it physically possible** — no group, teacher or room in two places at
  once; the right kind of room; a big enough room; a qualified teacher who is
  available. This restates, independently, what the CP model was told. If it
  ever fails, the two halves disagree and one of them is wrong.
- **III. Is it a timetable a school would accept** — the rules nobody encodes.
  This section is why the file exists.

### Counting hours without arithmetic

Pol has no numbers, so "five hours of maths a week" is not the numeral 5: it is
five `demand` entities, told apart by an `ordinal`. Each lesson carries the same
ordinal — which hour of that subject it is, by position in the week. Then

- `curriculum-delivered` — no demand without a lesson,
- `nothing-extra` — no lesson without a demand,
- `hours-not-doubled` — no two lessons claiming one demand,

make lesson↔demand a **bijection**, which counts the hours exactly without ever
counting. The same trick handles room capacity: seat counts become a ladder of
classes walked by `bigger`, and "does this group fit" is a four-step walk
([`fits`](timetable.lib.pol)) rather than a comparison.

### The trust boundary

An audit is only as good as what it declines to take on faith.
[to_pol.py](to_pol.py) is a transcriber, not a checker: it copies the curriculum
and the schedule into a Pol instance and **decides exactly one thing** — each
lesson's ordinal, by position in week order. Even that is checked rather than
trusted: a miscounting transcriber breaks the bijection above and the file it is
feeding says so. What remains on faith is that the transcription of
`curriculum.yaml` is faithful, and the three files are short enough to read.

## What it costs

Every arrow in the schema is `fixed`, because a decided timetable has nothing
left to vary. So the state space is **one state**, and `pol check` spends its
time evaluating questions rather than enumerating situations:

| lessons | CP-SAT | `pol check` | states |
|---|---|---|---|
| 60 (3 groups, 5 days) | 0.9 s | 0.26 s | 1 |
| 240 (12 groups, 5 days) | 29 s | 6.0 s | 1 |

The cost is in the quantifiers, not the search: `no-triple-run` binds three
lessons at once, so it is cubic in the number of lessons and dominates the
6 seconds. Everything else is quadratic or linear.

This is the direction in which Pol scales for scheduling, and the other one is
worth knowing about too: asking Pol to *generate* the timetable — moves that
place lessons, `possible` for a full week — hits the engine's 200 000-state cap
at about fifteen lesson-hours, because the set of hours still owed is genuinely
part of the state. Making a timetable is a search problem and belongs to CP-SAT.
Judging one is a decision problem, and that is what is here.

## The files

| | |
|---|---|
| [curriculum.yaml](curriculum.yaml) | what must be taught, by whom, where — the only shared input |
| [solve.py](solve.py) | CP-SAT: the maker. `--strict` adds what the audit found |
| [to_pol.py](to_pol.py) | the transcriber: curriculum + schedule → a Pol instance |
| [timetable.lib.pol](timetable.lib.pol) | the vocabulary of a school week, and where the curriculum runs out |
| [timetable.claims](timetable.claims) | the questions — hand-written, term after term |
| [tamper.py](tamper.py) | three realistic defects, so the audit can be seen to bite |
| [show.py](show.py) | a produced schedule as a readable grid |
| [run.sh](run.sh) | the three acts, each asserting what it expects |

`timetable.pol` is generated beside the claims file and is not checked in:
`pol` resolves a `--claims` file, and every `(load …)` inside it, against the
model's own directory — and `pol query timetable.pol NAME` finds
`timetable.claims` by that same sibling rule.
