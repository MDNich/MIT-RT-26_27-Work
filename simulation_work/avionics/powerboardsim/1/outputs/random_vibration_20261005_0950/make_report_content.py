from rv_paths import *
import csv,json,re,math
ma=json.loads((R/'modal_basis/audit.json').read_text())
allrows=[];bycase={}
for axis in ['X','Y','Z']:
 assert (R/axis/'RESULTS_VERIFIED.txt').exists()
 assert (R/axis/'field_coverage_audit.json').exists()
 assert (R/axis/'support_response_audit.json').exists()
 rows=list(csv.DictReader((R/axis/'result_summary.tsv').open(),delimiter='\t'))
 assert len(rows)==17
 for x in rows:
  match=re.fullmatch(r'\s*([-+0-9.eE]+)\s*\[(.*?)\]\s*',x['maximum'])
  assert match,x
  x['value']=float(match[1]);x['unit']=match[2]
  assert math.isfinite(x['value']) and x['value']>=0
 bycase[axis]={x['name']:x for x in rows};allrows+=rows

def value(axis,name,kind):
 row=bycase[axis][name];u=row['unit'];v=row['value']
 if kind=='u':
  assert u in ['m','mm'];return v*(1000 if u=='m' else 1)
 if kind=='a':
  assert u in ['m sec^-1 sec^-1','m sec^-2','m s^-2'];return v/9.80665
 if kind=='s':
  assert u in ['Pa','MPa'];return v*(1e-6 if u=='Pa' else 1)
 if kind=='e':
  assert u=='m m^-1';return v*1e6
 raise Exception(kind)
def fmt(v):return f'{v:.5g}'
C={'headline_rows':[],'pcb_u_rows':[],'pcb_a_rows':[],'all_u_rows':[],'all_a_rows':[],'stress_rows':[],'strain_rows':[],'image_captions':{}}
peaks={};stress={};assembly_stress={}
for axis in ['X','Y','Z']:
 du=[value(axis,'PCB RMS displacement '+c+' - base '+axis,'u') for c in ['X','Y','Z']]
 da=[value(axis,'PCB RMS absolute acceleration '+c+' - base '+axis,'a') for c in ['X','Y','Z']]
 au=[value(axis,'RMS displacement '+c+' - base '+axis,'u') for c in ['X','Y','Z']]
 aa=[value(axis,'RMS absolute acceleration '+c+' - base '+axis,'a') for c in ['X','Y','Z']]
 st=value(axis,'RMS equivalent stress - PCB','s');sta=value(axis,'RMS equivalent stress - all bodies','s');assembly_stress[axis]=sta
 strains=[value(axis,'RMS PCB normal strain '+c,'e') for c in ['X','Y','Z']]
 comp=['X','Y','Z'][du.index(max(du))];peaks[axis]=max(du);stress[axis]=st
 C['headline_rows'].append([axis,fmt(max(du)),comp,fmt(st)])
 for key,values in [('pcb_u_rows',du),('pcb_a_rows',da),('all_u_rows',au),('all_a_rows',aa),('strain_rows',strains)]:C[key].append([axis,*map(fmt,values)])
 C['stress_rows'].append([axis,fmt(st),fmt(sta)])
 C['image_captions'][axis]=f'{axis}-axis base excitation: PCB {comp}-direction RMS displacement. Spatial maximum {max(du):.5g} mm. ANSYS native result contour; displayed legend uses metres.'
 C['image_captions'][axis]+=' Colors show a statistical component response, not a modal eigenvector amplitude.'
C['worst_stress_axis']=max(stress,key=stress.get)
w=C['worst_stress_axis']
C['stress_caption']=f'Highest PCB equivalent-stress RMS occurs for {w}-axis base excitation: {stress[w]:.5g} MPa. Unaveraged Segalman--Fulcher result. Static clamp stress is separate; the native Gaussian probability label does not apply to equivalent stress.'
d=max(peaks,key=peaks.get)
C['summary']=[f'Three separate random-vibration analyses of the complete populated assembly were completed using the supplied 20--2000 Hz acceleration PSD and an exploratory constant modal damping ratio of 2%. The model inherits the converged, locked six-bolt state from the 750 N-per-bolt static study. The calculated response uses all 38 prestressed modes between 485.964 and 3986.075 Hz.',f'The largest PCB directional displacement RMS is {peaks[d]:.5g} mm under {d}-axis excitation. The greatest PCB equivalent-stress RMS is {stress[w]:.5g} MPa under {w}-axis excitation. Results below are separate directional load cases; they are not a simultaneous three-axis environment.']
C['stress_alert']=f'The highest whole-assembly elastic equivalent-stress RMS is {max(assembly_stress.values()):.5g} MPa under {max(assembly_stress,key=assembly_stress.get)}-axis excitation. The localized hardware maxima require mesh, connection and material validation; numerical completion is not evidence of structural adequacy.'
C['solver_rows']=[]
for axis in ['X','Y','Z']:
 native=Path((R/axis/'accepted_native_directory.txt').read_text())
 audit=json.loads((native/'native_solver_audit.json').read_text())
 assert audit['errors']==0
 C['solver_rows'].append([axis,str(audit['errors']),str(audit['warnings']),'17 / 17','781 / 781'])
C['method_sections']=[('Assembly and loading',['The board lies in the global XY plane; Z is normal to the PCB. The same eight mounting faces are fixed, and a single coherent base motion is applied to their 781 mesh nodes in the specified axis. Native checks matched these nodes exactly to the geometry scopes. Standard gravity is 9.80665 m/s²; the four PSD ordinates were converted to SI acceleration²/Hz before solving.','All six bolts inherit the locked equilibrium at static time 2, load step 2, substep 4. Verified locked reactions range from 749.9968 to 749.99945 N. Battery connections remain limited to the nickel strips; no battery-to-PCB bond was added.']),('Mesh and modal basis',['The shared refined quadratic mesh has 368,754 geometry-mesh nodes and 112,902 solid elements across 208 bodies. The solver has additional contact and pretension entities. PCB sizing is 0.7 mm and bolt sizing is 0.4 mm. This random-vibration study did not change that mesh.','The modal extraction is undamped, starts at 1 Hz, and requests up to 60 modes through 4000 Hz. There are 38 modes in that interval. The first 20 frequencies match the accepted earlier bolt study to the exported precision. Stress and strain recovery were enabled before this solve.']),('Numerical checks',[f'The modal solve completed with zero errors. Extracted translational effective-mass fractions are X {ma["effective_mass_fraction"]["X"]*100:.2f}%, Y {ma["effective_mass_fraction"]["Y"]*100:.2f}% and Z {ma["effective_mass_fraction"]["Z"]*100:.2f}%. The frequency range exceeds 1.5 times the 2000 Hz PSD limit, but a modal-basis convergence study has not been established.','Each random case passed a native input check without PFACT or SOLVE, followed by an authorized solve. Input hashes, damping, spectrum ordinates, mounting nodes, solver completion and complete finite response fields were checked. All 781 supports reproduce the prescribed 14.136 g RMS acceleration in each case. No insignificant modes were excluded. Velocity and absolute acceleration were retained alongside relative displacement.'])]
C['qualification_sections']=[('Exploratory assumptions',['The 2% damping ratio was selected by the user as an exploratory assumption; no damping measurement was supplied. Peak response near resonance is damping-sensitive. This report does not establish a damping uncertainty interval.','Inherited isotropic PCB properties are E = 23.33024 GPa, Poisson ratio 0.15 and density 1969.7774 kg/m³. Batteries use a homogeneous E = 200 GPa, Poisson ratio 0.3 and density 2200 kg/m³. These idealizations have not been correlated with the actual board laminate or cell construction.']),('Contact and stress limitations',['The bolt model uses existing solid shafts with pretension cuts and MPC shaft-to-hole connections. Washer-to-PCB frictionless seats use Adjust to Touch to bridge a 0.746 mm CAD gap. This is an assumed assembled seating condition. The random response is linearized about the locked state; it does not predict contact opening, slip transitions or bolt loosening.','The inherited model contains thin nickel-strip mesh-quality warnings, including highly distorted tetrahedra, and hardware constraint-overlap warnings. The expanded modal solve reports 2251 warnings, including inherited shape warnings and repeated ACT parameter definitions. These warnings have not been eliminated.','The static model previously produced a peak elastic equivalent stress of approximately 1.142 GPa. That localized value and the random stress maxima require mesh, contact and material validation before any strength conclusion. The static mean and random equivalent-stress RMS must not be added as if they were compatible stress tensors.']),('Statistical interpretation',['RMS displacement and acceleration characterize stationary zero-mean vibration. Three-sigma scaling is an estimate of excursions at a point, not a guaranteed maximum over a test or flight. Equivalent stress uses a non-Gaussian statistical measure. The generic 68.269% / 1-sigma label on native ANSYS equivalent-stress plots must not be interpreted as a Gaussian coverage probability. A displayed time of 0 s is the stored result-set label, not an instantaneous vibration state. No test duration, fatigue law or acceptance limits were supplied, so no fatigue life or pass/fail margin is claimed.']),('Evidence and reproducibility',[f'The preserved run is outputs/random_vibration_20261005_0950. It contains the input specification, native input decks, preflight logs, modal participation tables, solver logs, CSV/TSV result tables, and ANSYS contour images. Expanded modal analysis ID: 4254. Random analysis IDs: X 4259, Y 4264, Z 4269.','Solver: ANSYS Mechanical/MAPDL 2026 R1.02, build 26.1 UP20260202, Windows 11 in Parallels; 12 distributed processes. Each random case was solved in an isolated Windows runtime, archived with SHA-256 hashes, and imported into its Mechanical analysis by reference for field recovery. This recovered a Mechanical result-handoff failure; the accepted numerical solutions have zero solver errors. The source project remains powerboardsim_v1.wbpj. The prior default-contact/modal comparison is preserved separately. The report source keeps ANSYS contours as external PNG files and draws both graphs using editable native PGFPlots code and numerical data tables.'])]
hotspot_rows=list(csv.DictReader((R/'stress_hotspot_bodies.tsv').open(),delimiter='\t'))
hotspot=max((row for row in hotspot_rows if row['scope'].endswith('all bodies')),key=lambda row:float(row['stress_pa_rounded']))
C['method_sections'].append(('Highest assembly stress location',[f"The greatest assembly stress occurs under {hotspot['case']}-axis excitation in CAD body {hotspot['body'].split('|')[-1]} (geometry ID {hotspot['geometry_id']}). Its exported maximum is at node {hotspot['node']}, element {hotspot['element']}. This localized fastener-model result requires validation before it can support a strength judgment."]))
C['references']=[('ANSYS Mechanical 2026 R1: Random Vibration Analysis','https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/wb_sim/ds_spectral_analysis_type.html'),('ANSYS Theory Reference 2026 R1: Spectrum Analysis','https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_thry/thy_anproc7.html'),('ANSYS 2026 R1: PSDUNIT and excitation units','https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_PSDUNIT.html'),('ANSYS 2026 R1: Input PSD curve-fit display','https://ansyshelp.ansys.com/public/Views/Secured/corp/v261/en/ans_cmd/Hlp_C_PSDGRAPH.html')]
(R/'report_content.json').write_text(json.dumps(C,indent=2,ensure_ascii=False))
out=P/'output/power_board_random_vibration_results.csv'
with out.open('w') as f:
 writer=csv.DictWriter(f,fieldnames=list(allrows[0]));writer.writeheader();writer.writerows(allrows)
print(json.dumps(C['headline_rows'],indent=2));print(out)
