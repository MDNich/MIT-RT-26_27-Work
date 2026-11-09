#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
work="${CP_WORK:-$root/work}"
repo="${OR_REPO:-$root/../../../ActiveControl_MIT_RktTeam}"
jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
result="$root/results/followup"; mkdir -p "$result"
python3 followup/build.py
cl="$work/handover/classes:$work/classes:$jar"
java -Djava.awt.headless=true -cp "$cl" Sweep inputs/models "$result/static.csv.gz"
java -Djava.awt.headless=true -cp "$cl" Sweep inputs/native-final/models "$result/final.csv.gz"
java -Djava.awt.headless=true -cp "$cl" ChartTunnel reference/measurements.csv "$result/tunnel.csv" 2> "$work/handover/tunnel.log"
cp "$work/iris-replay.csv" "$work/handover/replay.csv"
java -Djava.awt.headless=true -cp "$cl" IrisState inputs/iris/preferred.ork "$work/handover/replay.csv" inputs/iris/booster_13.eng inputs/iris/sustainer_2.eng > "$work/handover/replay.log"
cp "$work/handover/replay.csv.out.csv" "$result/replay.csv"
OVERLAY="$work/handover/classes" ./run-iris.sh preferred handover
