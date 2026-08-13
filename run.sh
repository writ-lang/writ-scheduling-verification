#!/usr/bin/env bash
# Copyright (C) 2026 Alex Kunich
# SPDX-License-Identifier: AGPL-3.0-or-later
# The whole pipeline, in three acts. Each act asserts what it expects, so this
# script is a test of the audit and not merely a demonstration of it.
#
#   ./run.sh audit    solve as specified -> transcribe -> check   (findings expected)
#   ./run.sh tamper   break that schedule -> check                (caught, by name)
#   ./run.sh strict   solve with the findings encoded -> check    (clean)
#   ./run.sh all      all three; exits 0 only if every act behaved as expected
#
# `writ check` exits 1 when it HAS A FINDING, which is a verdict and not an
# error — so acts 1 and 2 expect 1, and act 3 expects 0.
set -uo pipefail
cd "$(dirname "$0")"

WRIT=${WRIT:-writ}
PY=${PY:-python3}
# Outputs go to build/. Under `docker compose` that may be a bind mount the
# container's user cannot write to; fall back rather than fail the run.
B=build
mkdir -p $B 2>/dev/null
if ! [ -w $B ]; then B=$(mktemp -d); echo "build/ is not writable — using $B"; fi

pass=0 fail=0
ok()   { printf '  \033[32m✓\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$1"; fail=$((fail+1)); }
head() { printf '\n\033[1m── %s\033[0m\n' "$1"; }

# expect_exit CODE FILE MESSAGE
expect_exit() { [ "$1" = "$2" ] && ok "$3 (exit $2)" || bad "$3 — expected exit $1, got $2"; }
# says PATTERN FILE MESSAGE
says() { grep -qE "$1" "$2" && ok "$3" || bad "$3 — no '$1' in the report"; }
# silent PATTERN FILE MESSAGE
silent() { grep -qE "$1" "$2" && bad "$3 — found '$1'" || ok "$3"; }

check() {  # check SCHEDULE REPORT
  # The model is generated BESIDE the claims and the library: `writ` resolves a
  # --claims file, and every (load …) inside it, against the model's own
  # directory — and `writ query timetable.writ NAME` finds timetable.claims by
  # that same sibling rule.
  $PY ./to_writ.py "$1" -o timetable.writ || exit 2
  cp timetable.writ "$B/$(basename "${2%.txt}").writ"
  $WRIT check timetable.writ --claims timetable.claims > "$2" 2>&1
  local rc=$?
  cat "$2"
  return $rc
}

CONFORMANCE='fails +(curriculum-delivered|nothing-extra|hours-not-doubled|no-group-clash|no-teacher-clash|no-room-clash|room-fit|room-big-enough|teacher-qualified|teacher-available)'

act_audit() {
  head "ACT 1 — the timetable as specified, audited"
  $PY ./solve.py --out $B/schedule.json || exit 2
  $PY ./show.py $B/schedule.json --group g-7a     # what the solver produced
  check $B/schedule.json $B/audit.txt; rc=$?
  expect_exit 1 $rc "writ has findings to report"
  silent "$CONFORMANCE" $B/audit.txt \
    "the solver delivers the curriculum and nothing collides — both halves agree"
  says 'fails +(no-triple-run|sport-not-first|time-to-change-after-sport)' $B/audit.txt \
    "at least one rule nobody told the solver is broken"
  says '^gaps: [1-9]' $B/audit.txt \
    "the curriculum's silences are reported rather than guessed past"
}

act_tamper() {
  head "ACT 2 — the same timetable, damaged in three ways"
  $PY ./tamper.py $B/schedule.json --out $B/schedule.tampered.json || exit 2
  check $B/schedule.tampered.json $B/tamper.txt; rc=$?
  expect_exit 1 $rc "writ has findings to report"
  says 'fails +no-room-clash'          $B/tamper.txt "the double-booking is caught"
  says 'fails +curriculum-delivered'   $B/tamper.txt "the lost hour is caught"
  says 'fails +teacher-qualified'      $B/tamper.txt "the unqualified cover is caught"
  says 'missing-hours'                 $B/tamper.txt "the queries name the offenders"
}

act_strict() {
  head "ACT 3 — solved again with the findings encoded"
  $PY ./solve.py --strict --out $B/schedule.strict.json || exit 2
  check $B/schedule.strict.json $B/strict.txt; rc=$?
  expect_exit 0 $rc "nothing left to report"
  silent 'fails ' $B/strict.txt "every property holds"
  says '^gaps: none' $B/strict.txt "no silence is reached any more"
}

case "${1:-all}" in
  audit)  act_audit ;;
  tamper) act_audit > /dev/null 2>&1; act_tamper ;;
  strict) act_strict ;;
  all)    act_audit; act_tamper; act_strict ;;
  *) echo "usage: $0 [audit|tamper|strict|all]" >&2; exit 2 ;;
esac

printf '\n%s passed, %s failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
