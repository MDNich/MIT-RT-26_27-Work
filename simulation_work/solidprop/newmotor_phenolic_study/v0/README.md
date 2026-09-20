# New motor phenolic study — v0

This directory contains the reproducible inputs and bilingual preparation
report for the new two-layer motor model.  The nominal diameters are:

- aluminium OD: 6.000 in (152.400 mm);
- aluminium ID / phenolic OD: 5.625 in (142.875 mm);
- phenolic ID: 5.250 in (133.350 mm).

The resulting radial thicknesses are 4.7625 mm for both phenolic and
aluminium.  The analysis uses a 0.10° sector, a 50 mm axial coupon, and a
full-ring scale factor of 3600.

## Directory policy

- `model/`: version-controlled generators, controller, UserMatTh source and
  prebuilt ANSYS 2026 R1 DLL;
- `geometry/`: a native MAPDL database containing the two glued volumes plus
  a machine-readable validation record;
- `docs/fr` and `docs/en`: the French report and its English translation;
- `ansystmp/`: ignored Windows runtime, native preflight logs, restart files,
  RTH files, checkpoints, and eventual results.  Nothing in this directory is
  intended for Git.

## Rebuild and native preflight

From macOS, run `model/prepare_model.py`; it creates the ignored runtime under
`ansystmp/windows` without solving.  Windows maps this `v0` directory as drive
`V:`.  The prepared runtime is therefore `V:\ansystmp\windows`.

In Windows PowerShell:

```powershell
V:\ansystmp\windows\launch_v0.ps1 -Preflight
```

The preflight reads the complete native deck but contains no `SOLVE`.  The
accepted package has 229,665 nodes and 152,000 linear SOLID70 hexahedra and
completed with zero MAPDL warnings and zero MAPDL errors.

The simulation is not started by the preparation workflow.  Its first launch
requires an explicit `-Run`.  A clean pause is requested with
`request_pause.ps1`; resume requires both `-Run -Resume` and an accepted
checkpoint.  The local licence is fixed to `1055@localhost`, and a second
ANSYS/MPI process is refused while one already exists.

## Primary result

The principal history quantity is the remaining phenolic thickness,

`phenolic_remaining_thickness_m`,

accompanied by removed thickness, removed initial-equivalent mass, pyrolysis
gas mass, oxidized-char mass, mass residual, and the energy audit.  This keeps
"removed phenolic", "pyrolysis gas", and "burned char" separate instead of
combining physically different quantities.

