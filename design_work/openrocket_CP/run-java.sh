#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="${OR_REPO:-$here/../../../ActiveControl_MIT_RktTeam}"
jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
work="${CP_WORK:-$here/work}"
mkdir -p "$work/classes"
javac -encoding UTF-8 -cp "$jar" -d "$work/classes" "$here/Sweep.java" "$here/IrisState.java" "$here/reference/FinModelBenchmark.java" "$here/reference/CompareFlights.java"
java -Djava.awt.headless=true -cp "$work/classes:$jar" Sweep "$here/inputs/models" "$here/results/openrocket.csv.gz"
java -Djava.awt.headless=true -cp "$work/classes:$jar" FinModelBenchmark "$here/reference/measurements.csv" "$here/results/tunnel.csv"
