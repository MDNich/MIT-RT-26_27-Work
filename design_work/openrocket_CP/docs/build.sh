#!/usr/bin/env bash
set -euo pipefail
doc="$(cd "$(dirname "$0")" && pwd)"
work="${CP_WORK:-$doc/../work}"
for spec in writeup/supersonic-cp-calibration slides/supersonic-cp-slides; do
    sub="${spec%/*}"; name="${spec##*/}"; out="$work/tex/$sub"; mkdir -p "$out"
    out="$(cd "$out" && pwd)"
    (cd "$doc/$sub" && latexmk -pdf -interaction=nonstopmode -halt-on-error -outdir="$out" "$name.tex") > "$out/console.txt" 2>&1 || { tail -40 "$out/console.txt"; exit 1; }
    cp "$out/$name.pdf" "$doc/$sub/$name.pdf"
done
