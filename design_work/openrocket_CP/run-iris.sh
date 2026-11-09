#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
repo="${OR_REPO:-$here/../../../ActiveControl_MIT_RktTeam}"
jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
work="${CP_WORK:-$here/work}"
name="${1:-ras-source}"; prefix="${2:-native}"
[[ "$name" == ras-source || "$name" == preferred || "$name" == user-source ]]
mkdir -p "$work/$prefix-$name"
java -Xmx2g -Djava.awt.headless=true -cp "${OVERLAY:-$work/classes}:$work/classes:$jar" CompareFlights "$here/inputs/iris/$name.ork" "$work/$prefix-$name" "$here/inputs/iris/booster_13.eng" "$here/inputs/iris/sustainer_2.eng" > "$work/$prefix-$name/run.log" 2>&1
for m in legacy candidate; do gzip -nc "$work/$prefix-$name/$m-sustainer.csv" > "$here/results/$prefix-$name-$m.csv.gz"; done
