# Printed and archived source inputs

These are report copies of the four audited corrected-midpoint primary runtimes.
Each file is checked against its original sealed input manifest before copying.
`source_manifest.json` records hashes and provenance. Do not use this folder to
launch a second solver or modify a sealed running package.

The PDF prints the complete sustainer Al material, Fortran, MAPDL driver,
resume/export scripts, Python controller and mesh deck. It also prints the CF
material/orientation block with its original line numbers and the build commands.
The case folders preserve full decks/configurations for all four motors, including
their actual guest-local paths. `prepare_model.py` is the reproducible generator;
the sealed generated decks remain the source of truth for the executed runs.

The compiled DLL remains in `v1/model/usermatthLib.dll`. The source listing is
not a claim that compilation or another solve occurred during documentation.
