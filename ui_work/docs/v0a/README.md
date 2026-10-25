# Rocket GNC Monitor v0a — version 0.1.1

[Read the complete PDF](Rocket_GNC_Monitor_v0a.pdf). The editable project starts at [main.tex](main.tex).

The report documents the published [v0.1.1 application](https://github.com/MIT-Rocket-Team/RT_Telemetry_UI/releases/tag/v0.1.1), commit `1923244f1a962049d6f66958816e009edd459e21`, reviewed on 25 October 2026.

- **Part I:** installation, wizard/CLI, Launch and Away workspaces, source modes and connections, URRG locations, state and rocket graphics, physical/virtual pointing, Balius/Iris video, legacy controls, simulation, recordings, flights, networking, settings and shortcuts.
- **Part II:** standalone repository and module map, threading/lifecycle, station and pose contracts, wire formats, storage/archives, video, simulation, graphics, native/universal builds, release evidence and extension guidance.
- **Appendices:** all 42 mission fields, 20 normalized sample fields, 43 legacy CSV columns, validated examples, source index and glossary.

All 12 diagrams are editable TikZ with LaTeX text. The report uses Latin Modern and the KOMA-Script/blue-heading/table style adapted for the preceding v0 report from the supplied GenMAPS report. It contains no screenshots or raster figures. The application itself continues to use Lucida Grande.

The manual distinguishes working local features from pending Launch uplink enable, Iris target switching, remote station transport, LTU metrics and sensor fusion. It documents the released two-window Launch interface and APRS support; subsequent requested application changes are not silently incorporated into this fixed release manual.

## Build the PDF

From this directory, with a LaTeX distribution, `latexmk`, KOMA-Script, TikZ/PGF, Latin Modern and the packages named in `report-style.sty`:

```sh
make
make clean
```

`make` compiles `main.tex` into `build/` and copies the finished `Rocket_GNC_Monitor_v0a.pdf` here. `make clean` removes only this report's `build/` directory and retains the final PDF. No application checkout, network, shell escape or external diagram renderer is required. Opening the directory in the Codex LaTeX editor also provides a source/PDF preview; its compiler may paginate differently from the published pdfLaTeX build.

## Refresh the frozen references

Run with a Python 3.12+ environment containing the application's dependencies:

```sh
make reference \
  APP=/path/to/RT_Telemetry_UI \
  PYTHON=/path/to/RT_Telemetry_UI/.venv/bin/python
make
```

`build_reference.py` reads **committed v0.1.1**, extracts it into a temporary directory and removes that temporary copy on exit. It does not import the mutable working tree or modify the application checkout. It asserts schema field coverage, generates complete tables/examples, validates the examples with release code and hashes all tracked application files. Review the prose before intentionally changing the source ref; generating tables does not update behavioral documentation automatically.

`examples/` contains illustrative inputs, not surveyed launch configurations. The URRG template deliberately leaves the site unestablished, elevations at zero and the legacy height interpretation unknown. The reference is synthetic and unsuitable as a LIVE reference.

## Verification and retained evidence

The final report is visually reviewed after rendering. `evidence/documentation-validation.json` records the PDF hash, page/figure/font checks, source links and build diagnostics. `evidence/reference-validation.json` records schema/example validation; `evidence/source-manifest.json` identifies the exact application source bytes.

Application test results in the report come from the release's migration validation record, with build-source revisions and platform limitations preserved. Documentation compilation does not rerun application tests or establish hardware acceptance.

Only authored sources, frozen reference tables, small example/evidence files and the finished PDF are retained. Build logs, page renders, environments, vendor binaries, sessions and application packages are excluded. The old `../v0` report is unchanged.
