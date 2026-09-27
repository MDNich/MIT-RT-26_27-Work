# Controlled MIT OR / RASAero study - 27 September 2026

Start with the standalone LaTeX source `mit-or-rasaero-study.tex` and its compiled PDF `output/pdf/mit-or-rasaero-study.pdf`. The report follows the solid-propellant simulation style (`amsdtx`, Latin Modern serif, 0.75 in margins, small-caps title, contents and booktabs tables). All logo outlines and plot coordinates are embedded in the LaTeX file; no external assets are needed to compile it. `report.md` retains the original analysis text. The full numerical summary is `flight-statistics.csv`; detailed diagnostics are in `comparison-results.json`.

## Models

- `models/B01-smooth-square.ork`: 4 in / 6 kg dry / square fins.
- `models/B02-rough-square.ork`: B01 with rough finish. **Not physically roughness-matched across programs.**
- `models/B03-smooth-bevel.ork`: B01 with a 0.25 in leading bevel and blunt trailing edge.
- `models/B04-slender-square.ork`: 2.26 in / 1 kg dry / square fins.
- `models/B05-slender-bevel.ork`: B04 with a 0.25 in leading bevel and blunt trailing edge.

Each ORK contains both motor configurations and baseline simulation data. Use `*-turbulent.CDX1` for the primary RASAero comparison. `*-raw.CDX1` is the untouched MIT export. Plain `B0*.CDX1` files have the fin profile corrected where needed, but retain the export's transitional-flow setting for the sensitivity runs.

The Windows VM copies are under `C:\Users\Public\Documents\CodexRASAeroStudy`. MIT OR Windows verification ran under its `mit-or-validation` subdirectory using the exact MIT JAR, not the installed stock OpenRocket application engine.

## Run families

- `openrocket/BASE-MOTOR.csv`: baseline; requested step 0.01 s, actual default ~0.0025 s.
- `openrocket/*-dt005.csv`: requested step 0.005 s; actual step still ~0.0025 s because of the MIT timing override.
- `openrocket/*-actual-h00125.csv`: true half-step diagnostic; existing public timing globals set to 0.00125 s in the test process.
- `openrocket/*-ras-cd-replay.csv`: diagnostic replacing OR total/axial Cd with RAS output, not an independent prediction.
- `rasaero/BASE-turbulent-MOTOR.csv`: primary comparison.
- `rasaero/BASE-MOTOR.csv`: export-default flow sensitivity, with bevel geometry already corrected.
- `windows-validation/openrocket/`: baseline and requested-step repeats performed inside Windows.

OpenRocket histories use native core units (SI; radians for angles). RASAero units are in the CSV headers. Reported percent apogee differences use OR as the denominator, except the explicitly labeled replay table, which uses RAS. Peak speed, Mach and acceleration are restricted to ascent.

## Reproduction

The Java fixtures invoke the real installed MIT simulation and export APIs; they do not implement a separate flight solver. The tested JAR and source fingerprints are in `evidence/runtime.json` and `evidence/source-provenance.json`. Preserve the current output folder before regenerating, because the fixture builder overwrites its own generated files.

From this directory on the original Mac:

```bash
MIT_JAR=/Applications/OpenRocket_MIT.app/Contents/Resources/app/jar/OpenRocket-24.12.jar
MIT_JAVA=/Library/Java/JavaVirtualMachines/jdk-17.jdk/Contents/Home/bin
"$MIT_JAVA/javac" -cp "$MIT_JAR" scripts/ControlledStudy.java scripts/StateComparison.java scripts/DragReplay.java
"$MIT_JAVA/java" -Djava.awt.headless=true -Dopenrocket.bypass.motors=true -Dopenrocket.bypass.presets=true -cp "scripts:$MIT_JAR" ControlledStudy .
"$MIT_JAVA/java" -Djava.awt.headless=true -Dopenrocket.bypass.motors=true -Dopenrocket.bypass.presets=true -cp "scripts:$MIT_JAR" ControlledStudy . diagnostic
```

In Windows RASAero, open each exported model, select the correct motors, and apply the report's corrections. For B03/B05 choose **Hexagonal Blunt Base**, FX1 **0.25 in**, leading-edge radius **0**. Run each motor with All Turbulent Flow off and then on, export flight CSV at 0.01 s, and save each native model. Preserve the same filename conventions above. GUI helper source is in `scripts/windows-ui`; it is session-specific and must be reviewed for current process IDs, paths and coordinates before use. The English-number launcher changes only process culture and loads the installed executable.

After the RASAero files exist:

```bash
"$MIT_JAVA/java" -Djava.awt.headless=true -Dopenrocket.bypass.motors=true -Dopenrocket.bypass.presets=true -cp "scripts:$MIT_JAR" StateComparison .
"$MIT_JAVA/java" -Djava.awt.headless=true -Dopenrocket.bypass.motors=true -Dopenrocket.bypass.presets=true -cp "scripts:$MIT_JAR" DragReplay .
python3 scripts/analyze_study.py
python3 scripts/make_figures.py
```

`build_latex_report.py` regenerates the standalone source from the preserved numerical data, analysis text and logo outlines. Compile `mit-or-rasaero-study.tex` with the built-in LaTeX editor or `latexmk -pdf mit-or-rasaero-study.tex`. Its source and preview were successfully checked with the built-in compiler. The older `build_report.py` is retained only as provenance for the superseded ReportLab layout; do not use it for the current report format. System Python with NumPy was used to generate the LaTeX plot coordinates. To run the Java builder in Windows, use `;` as the classpath separator and the bundled Java at `C:\Program Files\OpenRocket\jre\bin\java.exe`. The Windows JAR hash was checked against the Mac MIT JAR before execution.

## Interpretation notes

The common-state drag check matches **reported Mach and altitude**, not Mach reconstructed from the RASAero velocity column; exported columns can be staggered in time. The stored raw diagnostic JSON also contains exploratory inferred density/gravity quantities, which were not used for conclusions because of this staggering. The motor depletion histories match only approximately, despite nearly identical initial mass and thrust histories.

Agreement with RASAero is not physical validation. These are idealized axial simulation fixtures; the rough-finish pair is explicitly confounded, and transonic/body correlations require independent experimental evidence. No MIT application source was modified.

## Aerodynamic follow-up

The updated report includes a 25-configuration fixed-Mach investigation. See `aerodynamic-investigation/README.md` for the raw Windows exports, paired body/fin decomposition, independent nose-term trial, and limitations. The original flight models and results are preserved; no aerodynamic changes have been installed in MIT OR. The nose-only proposal reduces aggregate mean absolute body Cd error by 83.8% on six geometries at Mach 1.32–3, while the report identifies separate fin-profile, Reynolds and base-drag work.

## Extended coefficient atlas

The follow-up studies have now been executed: **92 configurations, 82,800 matched Mach/angle points, 42 figure sheets and 176 plot panels**. Open `aerodynamic-investigation/extended/index.html` for the searchable gallery, or read Section 11 of the updated standalone LaTeX report. Each figure is also supplied as SVG and PNG.

The extension adds 67 Windows RASAero GUI exports and evaluates all 92 configurations through the installed MIT OR aerodynamic API at Mach 0.01–3.00 and angles of attack 0, 2 and 4 degrees. It covers nose shape and fineness, fin thickness/bevel/sweep/span/taper/profile, geometric scale, physical roughness, flow transition, nozzle area, and Rogers Modified Barrowman. See `aerodynamic-investigation/extended/README.md` for coefficient conventions, matching limitations, and reproduction details. These are coefficient sweeps; the earlier flight results remain preserved.

`aerodynamic-investigation/extended/matched-coefficients.csv` contains the common-state coefficient table. Raw exports and all native model inputs are retained alongside it. Exact physical roughness comparisons use an explicitly labeled reconstruction of the existing OR friction correlation, verified against 24 native OR finish sweeps. The report distinguishes these from direct native-engine values. MIT OR application files remain unchanged. `manifest-sha256.json` records packaged-file hashes; `study-data.zip` contains the report, plots, data, model inputs, and study helpers.
