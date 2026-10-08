from rv_paths import *
import json,csv,hashlib,shutil,zipfile,datetime
D=P/'output/latex/random_vibration'
tex=D/'power_board_random_vibration.tex'
s=tex.read_text()
assert '\\includegraphics' in s and 'EmbeddedRaster' not in s and 'pdf:stream' not in s
assert len(list((D/'figures').iterdir()))==8
assert (R/'ALL_CASES_VERIFIED.txt').exists()
pdf=P/'output/pdf/power_board_random_vibration.pdf';shutil.copy2(D/pdf.name,pdf)
readme='''POWER BOARD RANDOM VIBRATION - 5 OCTOBER 2026

The report contains separate X, Y and Z base-excitation cases for the model
with six locked bolts preloaded to 750 N each and 2% assumed modal damping.
These are exploratory linear elastic results, not a qualified strength or
fatigue assessment. See the report's model and qualification sections.

Files
- power_board_random_vibration.tex: editable LaTeX report.
- figures/: eight external ANSYS PNG contours referenced by includegraphics.
- plots/: editable native PGFPlots/TikZ code for both graphs.
- data/: ordinary CSV data read by the modal effective-mass LaTeX plot.
- assembly_body_response_audit.csv: body inventory and per-case response coverage.
- assembly_scope_audit.json: all 208 meshed bodies, including 172 ECAD bodies,
  have finite response values in all three cases.
- power_board_random_vibration.pdf: compiled and visually checked report.
- power_board_random_vibration_results.csv: 51 result-object summaries; numeric
  values retain the explicit native units in the unit column.
- modal_frequencies.csv: 38 prestressed frequencies used by the PSD analyses.
- stress_hotspot_bodies.tsv: native nodal/elemental maxima mapped to CAD bodies.
- study_config.json: original study specification and initial source identifiers.
  The expanded modal analysis actually used is 4254; PSD analyses are 4259,
  4264 and 4269. See verification_summary.json for final accepted identities.

Compile from this folder with an installed TeX distribution, or upload this
folder including figures/, plots/ and data/ to a LaTeX project editor:
    pdflatex power_board_random_vibration.tex
    pdflatex power_board_random_vibration.tex
Both graphs are native LaTeX plots, not included raster or PDF graphics.
No shell escape, raster payload, or generated image byte data is in the source.
The Codex built-in standalone preview does not currently resolve this external
asset folders. The supplied PDF was successfully built with pdfLaTeX.

The preserved native solver evidence is in the source project directory:
outputs/random_vibration_20261005_0950/
The three Mechanical analyses are solved and reference the accepted archived
result files there. Keep that directory with the Workbench project.
'''
(D/'README.txt').write_text(readme)
for src,name in [(R/'assembly_body_response_audit.csv','assembly_body_response_audit.csv'),(R/'assembly_scope_audit.json','assembly_scope_audit.json'),(P/'output/power_board_random_vibration_results.csv','power_board_random_vibration_results.csv'),(R/'modal_basis/frequencies.csv','modal_frequencies.csv'),(R/'stress_hotspot_bodies.tsv','stress_hotspot_bodies.tsv'),(R/'study_config.json','study_config.json')]:shutil.copy2(src,D/name)
summary={'completed_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'expanded_modal':json.loads((R/'modal_basis/audit.json').read_text()),'cases':{},'project_saved_after_verification':True,'pdf_pages':9,'pdf_visual_qa':'all nine pages visually checked; editable LaTeX graphs and four added full-assembly views','external_graphics':8,'native_latex_plots':2,'latex_compile':'pdfLaTeX successful, no warnings','native_editor_compile':'external figure folder unsupported','pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest()}
for axis in ['X','Y','Z']:
 C=Path((R/axis/'accepted_native_directory.txt').read_text())
 summary['cases'][axis]={'native':json.loads((C/'native_solver_audit.json').read_text()),'support_response':json.loads((R/axis/'support_response_audit.json').read_text()),'finite_complete_fields':len(json.loads((R/axis/'field_coverage_audit.json').read_text())),'mechanical_analysis_id':{'X':4259,'Y':4264,'Z':4269}[axis]}
summary['assembly_scope']=json.loads((R/'assembly_scope_audit.json').read_text())
(D/'verification_summary.json').write_text(json.dumps(summary,indent=2))
(R/'completion_audit.json').write_text(json.dumps(summary,indent=2))
files=[tex,D/pdf.name,D/'README.txt',*sorted((D/'figures').iterdir()),*sorted((D/'plots').iterdir()),*sorted((D/'data').iterdir()),D/'assembly_body_response_audit.csv',D/'assembly_scope_audit.json',D/'power_board_random_vibration_results.csv',D/'modal_frequencies.csv',D/'stress_hotspot_bodies.tsv',D/'study_config.json',D/'verification_summary.json']
z=P/'output/power_board_random_vibration_latex.zip'
with zipfile.ZipFile(z,'w',zipfile.ZIP_DEFLATED) as archive:
 for f in files:archive.write(f,'power_board_random_vibration/'+str(f.relative_to(D)))
with zipfile.ZipFile(z) as archive:assert archive.testzip() is None
for src,dst in [('rv_make_content.py','make_report_content.py'),('build_rv_report.py','build_latex_report.py'),('rv_import_request.py','import_request.py'),('rv_finalize_request.py','finalize_request.py'),('rv_plot_mass.py','plot_modal_mass.py'),('rv_package.py','package_report.py'),('rv_make_latex_plots.py','make_latex_plots.py'),('rv_assembly_export.py','export_assembly_views.py'),('rv_verify_assembly.py','verify_assembly_scope.py')]:shutil.copy2('/tmp/'+src,R/dst)
for f in [pdf,tex,z]:print(f,f.stat().st_size)
