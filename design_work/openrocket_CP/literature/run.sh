#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
work="${CP_WORK:-$here/work}"
repo="${OR_REPO:-$here/../../../ActiveControl_MIT_RktTeam}"
jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
python3 "$here/literature/build.py"
cl="$work/charts/classes:$work/classes:$jar"
java -Djava.awt.headless=true -Dstudy.wingOnly=true -cp "$cl" Sweep "$here/inputs/models" "$here/results/chart-wing.csv.gz"
java -Djava.awt.headless=true -cp "$cl" Sweep "$here/inputs/models" "$here/results/chart-combined.csv.gz"
java -Djava.awt.headless=true -cp "$work/classes:$jar" Sweep "$here/inputs/native-final/models" "$here/results/final-endpoints.csv.gz"
java -Djava.awt.headless=true -Dstudy.wingOnly=true -cp "$cl" Sweep "$here/inputs/native-final/models" "$here/results/final-wing.csv.gz"
java -Djava.awt.headless=true -cp "$cl" Sweep "$here/inputs/native-final/models" "$here/results/final-combined.csv.gz"
# This is an evaluation of independent candidates: retain all data even for a model that loses a comparison.
python3 - "$here" "$work" <<'PY'
from pathlib import Path
import sys
root,work=map(Path,sys.argv[1:])
s=(root/'reference/FinModelBenchmark.java').read_text().replace('public final class FinModelBenchmark','public final class ChartTunnel')
s=s.replace('throw new AssertionError("Candidate failed supersonic error comparison','System.err.println("Candidate failed supersonic error comparison')
s=s.replace('throw new AssertionError("Abrupt or invalid load:','System.err.println("Abrupt or invalid load:')
(work/'ChartTunnel.java').write_text(s)
PY
javac -cp "$jar" -d "$work/classes" "$work/ChartTunnel.java"
java -Djava.awt.headless=true -cp "$cl" ChartTunnel "$here/reference/measurements.csv" "$here/results/chart-tunnel.csv" 2> "$work/chart-tunnel-audit.log"
java -Djava.awt.headless=true -Dstudy.wingOnly=true -cp "$cl" ChartTunnel "$here/reference/measurements.csv" "$here/results/wing-tunnel.csv" 2> "$work/wing-tunnel-audit.log"
OVERLAY="$work/charts/classes" "$here/run-iris.sh" preferred charts
java -Djava.awt.headless=true -cp "$cl" IrisState "$here/inputs/iris/preferred.ork" "$work/iris-replay.csv" "$here/inputs/iris/booster_13.eng" "$here/inputs/iris/sustainer_2.eng" > "$work/chart-iris-static.log"
cp "$work/iris-replay.csv.out.csv" "$here/results/chart-iris-static.csv"
