#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
work="$root/work"
repo="${OR_REPO:-$root/../../../ActiveControl_MIT_RktTeam}"
jar="${OR_JAR:-$repo/clone/openrocket/build/libs/OpenRocket-MIT-v6.6.jar}"
python3 followup/fixtures.py
javac -cp "$jar" -d "$work/classes" followup/Loads.java
for variant in legacy full charts transfer handover; do
    cl="$work/classes:$jar"
    case "$variant" in charts|transfer|handover) cl="$work/$variant/classes:$cl";; esac
    java -Xmx2g -Djava.awt.headless=true -cp "$cl" Loads "$variant" "$root" > "$work/handover/loads-$variant.log" 2>&1
done
