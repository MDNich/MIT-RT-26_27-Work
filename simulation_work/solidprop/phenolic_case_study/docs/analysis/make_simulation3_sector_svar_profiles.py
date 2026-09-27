#!/usr/bin/env python3
"""Generate bilingual final SVAR figures for Simulation 3."""

import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import make_simulation2_svar_profiles as core  # noqa: E402


core.DEFAULT_RADIAL_CSV = HERE / "simulation3_sector_svar_radial_time_profiles_1pct.csv"
core.DEFAULT_AXIAL_CSV = HERE / "simulation3_sector_svar_axial_time_profiles_1pct.csv"
core.DEFAULT_HISTORY_CSV = HERE / "simulation3_sector_history_snapshot.csv"
core.DEFAULT_CONTOUR_DISTANCE_CSV = HERE / "simulation3_sector_recession_to_pyrolysis_contours_vs_time.csv"
core.PHE0_THICKNESS_MM = 1.270
core.LANGUAGES = ("fr", "en", "de")
core.OUTPUTS = {
    ("last_radial", 1, lang): HERE / f"simulation3_sector_svar1_radial_profile_1pct_{lang}.pdf"
    for lang in core.LANGUAGES
}
core.OUTPUTS.update({
    ("radial", idx, lang): HERE / f"simulation3_sector_svar{idx}_radial_time_profiles_1pct_{lang}.pdf"
    for idx in (1, 2) for lang in core.LANGUAGES
})
core.OUTPUTS.update({
    ("axial", idx, lang): HERE / f"simulation3_sector_svar{idx}_axial_time_profiles_1pct_{lang}.pdf"
    for idx in (1, 2) for lang in core.LANGUAGES
})
core.OUTPUTS.update({
    ("contour_distance", 1, lang): HERE / f"simulation3_sector_recession_to_pyrolysis_contours_vs_time_{lang}.pdf"
    for lang in core.LANGUAGES
})
core.TEXT["fr"]["last_title"] = (
    r"Simulation 3 : profil radial de SVAR1 au dernier état extrait"
    "\n"
    r"$t={time}\,\mathrm{{s}}$ ; ligne de récession $s={recession}\,\mathrm{{mm}}$"
)
core.TEXT["en"]["last_title"] = (
    r"Simulation 3: radial SVAR1 profile at the final extracted state"
    "\n"
    r"$t={time}\,\mathrm{{s}}$; recession line $s={recession}\,\mathrm{{mm}}$"
)
core.TEXT["fr"]["distance_title"] = (
    r"Simulation 3 : écart radial entre la récession virtuelle"
    "\n"
    r"et les contours de conversion pyrolytique"
)
core.TEXT["en"]["distance_title"] = (
    r"Simulation 3: radial separation between virtual recession"
    "\n"
    r"and pyrolysis-conversion contours"
)
core.TEXT["de"]["last_title"] = (
    r"Simulation 3: radiales SVAR1-Profil im letzten extrahierten Zustand"
    "\n"
    r"$t={time}\,\mathrm{{s}}$; Rezessionslinie $s={recession}\,\mathrm{{mm}}$"
)
core.TEXT["de"]["distance_title"] = (
    r"Simulation 3: radialer Abstand zwischen virtueller Rezession"
    "\n"
    r"und Pyrolyse-Umsatzkonturen"
)


if __name__ == "__main__":
    core.main()
