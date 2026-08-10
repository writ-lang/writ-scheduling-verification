# One image carrying both halves of the pipeline: CP-SAT to make the timetable,
# `pol` to audit it.
#
#   in a pol checkout:   make image          -> tags pol:latest, once
#   here:                docker compose up   -> all three acts
#
# POL_IMAGE is an ARG so the same file works against a registry the day one
# exists: --build-arg POL_IMAGE=ghcr.io/sajonaro/pol:0.1.0
ARG POL_IMAGE=pol:latest
FROM ${POL_IMAGE} AS engine

# python:3.12-slim is Debian 12, the same base the engine image is built on, so
# the binary and the stdlib copy across as they are — no OCaml toolchain here.
FROM python:3.12-slim
COPY --from=engine /usr/local/bin/pol /usr/local/bin/pol
COPY --from=engine /usr/local/share/pol/lib /usr/local/share/pol/lib

RUN pip install --no-cache-dir "ortools>=9.10" "pyyaml>=6" \
 && useradd -m runner

WORKDIR /timetable
COPY --chown=runner:runner . /timetable
RUN mkdir -p build && chown -R runner:runner /timetable
USER runner

# Prove the image is wired before anyone uses it: both halves, in one line each.
RUN python -c "from ortools.sat.python import cp_model; cp_model.CpModel()" \
 && pol --version

ENTRYPOINT ["./run.sh"]
CMD ["all"]
