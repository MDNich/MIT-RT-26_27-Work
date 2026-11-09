#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"; cd "$root"
work="${CP_WORK:-$root/work}";repo="${OR_REPO:-$root/../../../ActiveControl_MIT_RktTeam}";jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
mkdir -p "$work/afterbody" results/afterbody
python3 afterbody/build.py
javac -cp "$work/classes:$jar" -d "$work/classes" afterbody/AirframeSweep.java
cl="$work/afterbody/classes:$work/classes:$jar"
action="${1:-all}"
case "$action" in all|sweep|replay) ;; *) exit 2;; esac
for mode in previous segments center tail crossflow combined narrow; do
    if [[ "$action" != replay ]]; then
        java -Djava.awt.headless=true "-Dstudy.afterbody=$mode" -cp "$cl" AirframeSweep "$root" "results/afterbody/$mode.csv"
    fi
    if [[ "$action" == sweep ]]; then continue; fi
    cp "$work/iris-replay.csv" "$work/afterbody/$mode-replay.csv"
    java -Djava.awt.headless=true "-Dstudy.afterbody=$mode" -cp "$cl" IrisState inputs/iris/preferred.ork "$work/afterbody/$mode-replay.csv" inputs/iris/{booster_13,sustainer_2}.eng > "$work/afterbody/$mode-replay.log"
    cp "$work/afterbody/$mode-replay.csv.out.csv" "results/afterbody/$mode-replay.csv"
done
if [[ "$action" == sweep ]]; then exit 0; fi
java -Djava.awt.headless=true -Dstudy.afterbody=combined -cp "$cl" ChartTunnel reference/measurements.csv results/afterbody/earlier-tunnel.csv 2> "$work/afterbody/earlier-tunnel.log"
if grep -Ei 'abrupt|invalid|exception' "$work/afterbody/earlier-tunnel.log"; then exit 1; fi
java -Djava.awt.headless=true -Dstudy.afterbody=narrow -cp "$cl" ChartTunnel reference/measurements.csv results/afterbody/narrow-tunnel.csv 2> "$work/afterbody/narrow-tunnel.log"
if grep -Ei 'abrupt|invalid|exception' "$work/afterbody/narrow-tunnel.log"; then exit 1; fi
if [[ "$action" == replay ]]; then exit 0; fi
JAVA_TOOL_OPTIONS="-Dstudy.afterbody=combined" OVERLAY="$work/afterbody/classes" ./run-iris.sh preferred afterbody
JAVA_TOOL_OPTIONS="-Dstudy.afterbody=narrow" OVERLAY="$work/afterbody/classes" ./run-iris.sh preferred afterbody-narrow
