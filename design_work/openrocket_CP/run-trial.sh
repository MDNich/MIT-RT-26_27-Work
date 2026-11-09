#!/usr/bin/env bash
# Build a study-only class overlay, run the actual calculator and the integrator, never edit the engine or installed JAR.
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"; repo="${OR_REPO:-$here/../../../ActiveControl_MIT_RktTeam}"
work="${CP_WORK:-$here/work}"; jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
trial="$work/overlay"; mkdir -p "$trial/classes"
python3 - "$here/results/fits.csv" "$repo/clone/openrocket/core/src/main/java/info/openrocket/core/aerodynamics/barrowman/FinSetCalc.java" "$trial/FinSetCalc.java" <<'PY'
import csv,sys,pathlib
row=next(csv.DictReader(open(sys.argv[1]))); k=float(row['k']); assert row['excluded']=='none' and 0<=k<=1
s=pathlib.Path(sys.argv[2]).read_text(); old='double weight = finiteWing.weight('; assert s.count(old)==1
pathlib.Path(sys.argv[3]).write_text(s.replace(old,f'double weight = {k:.3f} * finiteWing.weight('))
PY
javac -encoding UTF-8 -cp "$jar" -d "$trial/classes" "$trial/FinSetCalc.java"
java -Djava.awt.headless=true -cp "$trial/classes:$work/classes:$jar" Sweep "$here/inputs/models" "$work/trial-check.csv.gz"
OVERLAY="$trial/classes" "$here/run-iris.sh" ras-source calibrated
OVERLAY="$trial/classes" "$here/run-iris.sh" preferred calibrated
