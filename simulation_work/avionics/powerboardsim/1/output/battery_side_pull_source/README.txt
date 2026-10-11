Power board - edge battery lateral pull. Issued 5 October 2026.

This is an exploratory local deformation study. There is no calibrated tearing
law and no qualified breaking load. Read the report assumptions before reuse.

latex/ contains the editable report, external PNGs, native PGFPlots and CSVs.
cases/ contains the accepted as-run decks, native logs and exported results.
audit/ records geometry, material sources, checks and excluded-attempt diagnosis.
procedure/audit_case.py is a portable NumPy-based audit of a solved case folder.
SHA256.json hashes every file included except the manifest itself.

REPRODUCTION
1. Make a NEW local run folder. Copy run.dat, preflight.dat,
   post_corrected.dat, config.json and mesh.json from one accepted case.
2. Use MAPDL 2026 R1.02 (26.1 UP20260202); units are N, mm and MPa.
3. Run the one-line commands below from that fresh folder using ANSYS261.exe:
   -b nolist -s noread -smp -np 1 -p preppost -j check -i preflight.dat -o preflight.out
   Check zero errors and the inventory before any solve.
   -b nolist -s noread -smp -np 4 -p ansys -j pull -i run.dat -o run.out
   Wait for native completion; do not rerun in the same folder after a failure.
   -b nolist -s noread -smp -np 1 -p preppost -j post -i post_corrected.dat -o post_corrected.out
   The postprocessor reads solved.db and pull.rst; it does not solve.
   If the pre/post seat is occupied, -p ansys is also valid for this read-only stage.
4. Run python audit_case.py <fresh-case-folder> with Python and NumPy.
   Check zero errors, target endpoint, equilibrium, constant clamp UZ during pull,
   and the 750 N transfer where applicable. Review all warnings.
5. Compare the native CSVs against the provided case exports.
6. From latex/, run pdflatex power_board_battery_side_pull.tex twice.

Large RST/DB binary files and full vendor publications are not included in this
bundle. Rerunning the included decks recreates the numerical binaries. Original
binaries and stopped-attempt data remain in outputs/battery_side_pull_20261005.
The source assembly CAD itself is not included in this bundle.
