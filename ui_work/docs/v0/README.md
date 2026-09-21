# Rocket GNC Monitor v0 documentation

The main deliverable is `Rocket_GNC_Monitor_v0.pdf`, built from `Rocket_GNC_Monitor_v0.tex`.

- **Part I:** complete functionality and operator guide.
- **Part II:** developer architecture, source ownership, protocols, persistence, testing, packaging and extension recipes.
- **Appendices:** complete mission/sample/CSV field references, examples, glossary and source/evidence index.

All drawings are native TikZ; all text uses LaTeX fonts. `report-style.sty` adapts the typography, colors, tables, headers and spacing of the user-supplied GenMAPS architecture report. Its subject matter and authorship are not copied.

## Rebuild

From this directory, with a LaTeX distribution containing KOMA-Script, TikZ/PGF, Latin Modern, latexmk and the packages in `report-style.sty`:

```sh
make
# Or directly:
latexmk -pdf -interaction=nonstopmode -halt-on-error -file-line-error Rocket_GNC_Monitor_v0.tex
```

No shell escape, raster figures, external diagram renderer or network is needed. `make clean` removes LaTeX auxiliary files while retaining the PDF. The report's links to app source expect the existing repository layout (`../../rocket_UI_v0`). Those links are supplementary: the prose, figures and schema appendices stand alone.

`examples/` contains documented illustrative inputs, not certified launch configurations. `evidence/` records the exact implementation reviewed and the existing validation results. `build/` holds documentation QA intermediates. Build intermediates are excluded from version control.

The schema appendices, examples and source inventory can be refreshed with the app's configured Python environment:

```sh
../../rocket_UI_v0/.venv/bin/python build_reference.py
make
```

Review the prose against any code changes before publishing a regenerated report. The historical application-validation file records the previous application checks; it is not a claim that the documentation build reruns them.

## Documentation checks

The published PDF has 40 pages and eight TikZ diagrams, embedded Latin Modern fonts, and no raster images. All pages were rendered and reviewed; the LaTeX build has no overfull boxes or undefined references. The examples load through the application's validators, 39 source links resolve, and 77 implementation-file hashes match the source inventory. Results are recorded in `evidence/documentation-validation-2026-09-21.json`.

The September 21 refresh includes the virtual antenna pointer, MGRS/relative mission coordinates, OpenRocket trajectory playback and repaired macOS dropdowns, alongside persistent Settings, the bundled v6.2 engine and Digital/Analog video. Current application results (107 passing tests and verified Mac packaging) are in `evidence/application-validation-pointer-location-2026-09-21.json`; the earlier files retain their historical results.
