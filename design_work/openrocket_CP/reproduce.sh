#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
mkdir -p work/atlas
unzip -oq inputs/atlas-native.zip -d work/atlas
python3 collect.py work/atlas --blind inputs/native-blind
python3 preferred.py
./run-java.sh
./run-iris.sh ras-source
./run-iris.sh user-source
./run-iris.sh preferred
python3 analyze.py
./run-trial.sh
python3 checks.py
python3 plots.py
python3 flight.py
./literature/run.sh
./literature/run-transfer.sh
python3 literature/score.py
python3 flight.py --extended
python3 literature/plot.py
python3 literature/export-patch.py
./followup/run-engine.sh
./followup/run-loads.sh
python3 followup/analyze.py
python3 followup/diagnostics.py
python3 followup/probes.py
python3 followup/figures.py
python3 make-tables.py
./docs/build.sh
python3 docs/package.py
