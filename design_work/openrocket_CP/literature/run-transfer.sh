#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"; work="${CP_WORK:-$here/work}"; repo="${OR_REPO:-$here/../../../ActiveControl_MIT_RktTeam}"
jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
python3 "$here/literature/transfer.py"
python3 "$here/literature/build-transfer.py"
cl="$work/transfer/classes:$work/classes:$jar"
for set in endpoints final; do
  models="$here/inputs/models"; if [[ "$set" == final ]]; then models="$here/inputs/native-final/models"; fi
  java -Djava.awt.headless=true -cp "$cl" Sweep "$models" "$here/results/$set-transfer.csv.gz"
done
java -Djava.awt.headless=true -cp "$cl" ChartTunnel "$here/reference/measurements.csv" "$here/results/transfer-tunnel.csv" 2> "$work/transfer-tunnel-audit.log"
OVERLAY="$work/transfer/classes" "$here/run-iris.sh" preferred transfer
cp "$work/iris-replay.csv" "$work/transfer-iris.csv"
java -Djava.awt.headless=true -cp "$cl" IrisState "$here/inputs/iris/preferred.ork" "$work/transfer-iris.csv" "$here/inputs/iris/booster_13.eng" "$here/inputs/iris/sustainer_2.eng" > "$work/transfer-iris-static.log"
cp "$work/transfer-iris.csv.out.csv" "$here/results/transfer-iris-static.csv"
