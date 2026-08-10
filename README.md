# A school timetable, made by one tool and judged by another

This is a small, complete, runnable example of an idea that generalises well
beyond schools: **let one program produce the answer and a different program,
which has never seen how it was produced, decide whether the answer is
acceptable.**

You do not need to know either tool to read on. Both are introduced below.

## The problem

A school has to publish a timetable. The inputs are ordinary:

- **groups** of pupils — `g-7a` has 28 of them;
- **subjects**, some of which demand something of a room: maths needs a computer
  room, sport needs a gym, literature needs any ordinary classroom;
- a **programme** (a curriculum): how many hours per week each group owes each
  subject — five hours of maths, three of sport, and so on;
- **rooms**, each with a facility and a number of seats;
- **teachers**, each qualified in certain subjects, some unavailable at certain
  times.

The timetable has to place every hour the programme demands into a period of the
week, in a room, with a teacher, such that no group, teacher or room is in two
places at once, every room suits its subject and seats its group, and no teacher
is booked when they are away. In this example that is 60 lessons across 30
periods — and the number of ways to try is far past counting by hand.

**And here is the thing that makes the example worth building.** Satisfying all
of that is not the same as being *acceptable*. A timetable can meet every stated
constraint and still be one no school would publish — pupils sent straight from
PE into maths with no time to change, a class starting Monday with sport, a free
period stranded in the middle of a day with nobody assigned to supervise it.
Those rules are real, everybody knows them, and nobody writes them down, so no
solver ever hears about them.

That is the gap this repository is about: not *is the timetable feasible*, but
*is it any good, and what did nobody say?*

## The two tools

### CP-SAT — the maker

[CP-SAT](https://developers.google.com/optimization/cp/cp_solver) is the
constraint solver in Google's OR-Tools, free and open source. You give it
**unknowns** and **rules those unknowns must obey**; it searches for values
satisfying every rule at once, or proves no such values exist. It is the
standard tool for timetabling, staff rostering, vehicle routing — problems too
big to enumerate but tightly enough constrained to search.

In [solve.py](solve.py) the unknowns are true/false variables, one per
*(hour, period, room, teacher)* combination that is not ruled out on its face,
and the rules are the constraints listed above. The timetable is whichever
variables the solver turns on. It takes about a second.

What CP-SAT cannot do is tell you what you forgot to ask it. It answers the
question it was given, exactly and only.

### pol — the judge

[pol](https://github.com/sajonaro/pol) is a small language for writing a domain
down and a tool that answers questions about it. A model has three parts: a
**schema** (what kinds of thing exist and how they point at each other), an
**instance** (one filling-in of that schema — the actual rooms, teachers and
lessons), and **transitions** (moves that may happen). `pol` builds every
situation the model allows and answers your questions by exhaustion, showing its
evidence.

The questions live in a **separate file** — a `.claims` file the model cannot
see — which is what makes them reusable: one question suite, many timetables.
Four kinds of answer appear in this repository:

| in the claims file | in the report | means |
|---|---|---|
| `(property N (never …))` | `holds N` / `fails N` | this must never happen — and it does not / it does |
| `(query N …)` | rows of names | *which* things satisfy a condition — the offenders, named |
| `(gap "…")` in the model | `gaps: 2` + the message | the rules are **silent** here; the tool reports the hole rather than guessing past it |
| — | exit `0` / `1` | `1` means *there is a finding to report*, which is a verdict, not a crash |

`gap` is the unusual one and the most useful here. Where an ordinary checker
must either accept or reject, a Pol model can say *the curriculum does not
answer this*, and `pol` reports it as a hole with the route to it.

## The idea

The two halves share **one file** — [curriculum.yaml](curriculum.yaml) — and
nothing else. The judge never sees the solver's model, and the solver never sees
the questions. That separation is the entire reason the verdict means anything:
if the checker were derived from the solver's own constraints it could only ever
confirm them.

```
curriculum.yaml ──► solve.py (CP-SAT) ──► schedule.json   "here is a timetable"
       │                                       │
       └──────────► to_pol.py ◄────────────────┘          transcribe both into
                        │                                  one Pol instance
                  timetable.pol ──► pol check --claims timetable.claims
                                          │
                                    holds / fails / gaps / named offenders
```

## Run it

With Docker, nothing else installed:

```console
$ cd ../pol && make image          # builds the pol engine image, once
$ cd ../pol-scheduling-verification
$ docker compose up                # all three acts
$ docker compose run --rm audit    # or just one of them
```

Or natively, given `pol`, Python, `ortools` and `pyyaml`:

```console
$ ./run.sh all
```

[run.sh](run.sh) asserts what each act should produce — twelve assertions — so
it is a test of the audit rather than a demonstration of it, and exits 0 only if
every one holds. Remember that `pol check` exits **1 when it has a finding**:
acts 1 and 2 expect 1, act 3 expects 0.

## What happens, in three acts

### Act 1 — the timetable as specified

CP-SAT places 60 lessons in under a second. Everything it was told holds when
checked independently, in a language it has never seen:

```
holds  curriculum-delivered      holds  no-room-clash
holds  nothing-extra             holds  room-fit
holds  hours-not-doubled         holds  room-big-enough
holds  no-group-clash            holds  teacher-qualified
holds  no-teacher-clash          holds  teacher-available
```

That agreement is worth having on its own: two statements of one requirement,
written in two languages by two different processes, agreeing. If they ever
disagree, one of them is wrong and you have found out cheaply.

Then the part the solver could not have told you:

```
fails  sport-not-first
fails  time-to-change-after-sport

gaps: 2
  window-unstated   — "the curriculum is silent: may a group have a free period
                       BETWEEN two lessons, and who supervises it?"
  doubling-unstated — "the curriculum is silent: may two hours of one subject
                       fall on the same day?"
```

Two rules any teacher would state out loud, broken — the timetable is feasible,
optimal and unpublishable. And two questions nobody answered, which the solver
therefore settled by accident. **The gaps are the more valuable half**: they are
questions to put back to whoever wrote the curriculum, produced mechanically
rather than noticed by someone squinting at a grid.

### Act 2 — the same timetable, damaged

[tamper.py](tamper.py) does three things a real pipeline does to a schedule
between the solver and the noticeboard: double-books a room, loses one lesson in
an export, and drops in a cover teacher who is not qualified. Each comes back
*named*:

```
fails  no-room-clash          clashes:        a = g-7a-art-thu-p3
fails  curriculum-delivered                   b = g-7b-art-thu-p3
fails  teacher-qualified      missing-hours:  d = owed-g-7b-math-5
                              unqualified:    b = g-7a-art-thu-p3
```

A failing property says *that* the timetable is wrong; the queries beside it say
*which lessons* make it wrong. `pol query timetable.pol clashes` asks one on its
own.

### Act 3 — solved again, with the findings encoded

`./solve.py --strict` adds to the CP model what act 1 exposed. The audit then
reports `gaps: none`, every property holds, exit 0. That is the loop the
arrangement exists to close: **audit, tighten the model, re-audit** — with the
questions the fixed point and the solver the thing that changes.

## What `pol` is asked

All of it is in [timetable.claims](timetable.claims), hand-written and stable
across terms — point it at next year's schedule unchanged.

- **I. Does it deliver the curriculum?** Every hour owed is taught, no hour is
  invented, no hour is claimed twice.
- **II. Is it physically possible?** No group, teacher or room in two places at
  once; the right kind of room; a big enough room; a qualified teacher who is
  not away. This restates, independently, what CP-SAT was told.
- **III. Would a school accept it?** The rules nobody encodes. This section is
  why the file exists.

### Counting hours when the language has no numbers

Pol deliberately has no arithmetic — that is what lets it answer *never*
questions by exhaustive census rather than by search. So "five hours of maths a
week" cannot be the numeral 5. It is **five `demand` entities**, told apart by
an ordinal (first hour, second hour…), and each lesson carries the ordinal of
the hour it fills. Then three properties do the counting between them:

- `curriculum-delivered` — no demand without a lesson,
- `nothing-extra` — no lesson without a demand,
- `hours-not-doubled` — no two lessons claiming one demand,

which together make lesson↔demand a **bijection**: exact counting, never
counted. Room capacity is the same move sideways — seat counts become a ladder
of classes walked by `bigger`, so "does this group fit" is a four-step walk
rather than a comparison.

### The trust boundary

An audit is only as good as what it refuses to take on faith.
[to_pol.py](to_pol.py) is a transcriber, not a checker: it copies the curriculum
and the schedule into a Pol instance and **decides exactly one thing** — each
lesson's ordinal, by position in the week. Even that is checked rather than
trusted, since a miscounting transcriber breaks the bijection above and the file
it is feeding says so. What remains on faith is that `curriculum.yaml` was
transcribed faithfully — and the transcriber is short enough to read.

## What it costs

Every arrow in the schema is *fixed*: a decided timetable has nothing left to
vary. Pol builds its situations as the product of everything that *can* vary, so
that product is empty and there is exactly **one situation**. The tool spends
its whole run evaluating questions rather than exploring:

| lessons | CP-SAT | `pol check` | situations |
|---|---|---|---|
| 60 (3 groups, 5 days) | 0.9 s | 0.26 s | 1 |
| 240 (12 groups, 5 days) | 29 s | 6.0 s | 1 |

The cost is in the questions, not in search: `no-triple-run` compares three
lessons at once, so it is cubic in the number of lessons and accounts for most
of those 6 seconds. Everything else is quadratic or linear.

Worth knowing about the other direction too. Asking Pol to *generate* the
timetable — moves that place lessons one at a time, and a question asking
whether a full week is reachable — hits the engine's 200 000-situation ceiling
at about fifteen lesson-hours, because the set of hours still owed is genuinely
part of the situation. **Making** a timetable is a search problem and belongs to
CP-SAT; **judging** one is a decision problem, and that is what is here.

## The files

| | |
|---|---|
| [curriculum.yaml](curriculum.yaml) | what must be taught, by whom, where — the only shared input |
| [school.py](school.py) | the curriculum read once: the week, the hours, who may go where |
| [solve.py](solve.py) | CP-SAT, the maker. `--strict` adds what the audit found |
| [to_pol.py](to_pol.py) | the transcriber: curriculum + schedule → a Pol instance |
| [timetable.lib.pol](timetable.lib.pol) | the vocabulary of a school week, and the two places the curriculum runs out |
| [timetable.claims](timetable.claims) | the questions — hand-written, term after term |
| [tamper.py](tamper.py) | three realistic defects, so the audit can be seen to bite |
| [show.py](show.py) | a schedule as a readable grid |
| [run.sh](run.sh) | the three acts, each asserting what it expects |

`timetable.pol` is generated beside the claims file and is not checked in: `pol`
resolves a `--claims` file, and every `(load …)` inside it, against the model's
own directory — and `pol query timetable.pol NAME` finds `timetable.claims` by
that same sibling rule.

A frozen, solver-free version of this audit lives as the `timetable/` scenario
in [pol-problems](https://github.com/sajonaro/pol-problems), where the schedule
is committed as a fixture so the verdicts can be asserted exactly.
