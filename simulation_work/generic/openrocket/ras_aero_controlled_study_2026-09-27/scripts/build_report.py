from pathlib import Path
import json,html,csv
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Image,KeepTogether
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.utils import ImageReader
R=Path(__file__).resolve().parents[1]
D=json.loads((R/'comparison-results.json').read_text()); C=[x for x in D if not x['design'].startswith('B02')]
O=R/'output/pdf';O.mkdir(parents=True,exist_ok=True)
OUT=O/'mit-or-rasaero-study.pdf'
S=getSampleStyleSheet()
INK=colors.HexColor('#173344');BLUE=colors.HexColor('#167d9a');LIGHT=colors.HexColor('#edf4f7')
S.add(ParagraphStyle(name='ReportTitle',fontName='Helvetica-Bold',fontSize=25,leading=29,textColor=INK,spaceAfter=13))
S.add(ParagraphStyle(name='SectionTitle',fontName='Helvetica-Bold',fontSize=19,leading=23,textColor=INK,spaceAfter=12))
S.add(ParagraphStyle(name='Sub',fontName='Helvetica-Bold',fontSize=11.5,leading=15,textColor=BLUE,spaceBefore=9,spaceAfter=6))
S.add(ParagraphStyle(name='ReportBody',fontName='Helvetica',fontSize=10,leading=14,textColor=INK,spaceAfter=8))
S.add(ParagraphStyle(name='SmallText',fontName='Helvetica',fontSize=8.4,leading=11,textColor=INK,spaceAfter=7))
S.add(ParagraphStyle(name='Cell',fontName='Helvetica',fontSize=8.1,leading=10.6,textColor=INK))
S.add(ParagraphStyle(name='HeadCell',fontName='Helvetica-Bold',fontSize=8.1,leading=10.6,textColor=colors.white))
story=[];md=[]
def para(t,style='ReportBody'):
 story.append(Paragraph(t,S[style]));md.append(t.replace('<b>','**').replace('</b>','**').replace('<br/>','\n')+'\n')
def title(t,first=False):
 story.append(Paragraph(t,S['ReportTitle' if first else 'SectionTitle']));md.append(('# ' if first else '## ')+t+'\n')
def sub(t):story.append(Paragraph(t,S['Sub']));md.append('### '+t+'\n')
def table(headers,rows,widths):
 cells=[[Paragraph(html.escape(str(x)).replace('\n','<br/>'),S['HeadCell' if i==0 else 'Cell']) for x in row] for i,row in enumerate([headers]+rows)]
 t=Table(cells,colWidths=widths,repeatRows=1,hAlign='LEFT')
 t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),INK),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),7),('RIGHTPADDING',(0,0),(-1,-1),7),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,LIGHT]),('LINEBELOW',(0,-1),(-1,-1),.5,colors.HexColor('#c8d6dd'))]))
 story.append(t);story.append(Spacer(1,9));md.extend(['| '+' | '.join(map(str,headers))+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(str(x).replace('\n',' / ') for x in row)+' |' for row in rows]+[''])
def figure(name,width=504):
 p=R/'figures'/name;iw,ih=ImageReader(str(p)).getSize();story.append(Image(str(p),width=width,height=width*ih/iw));md.append(f'![{name[:-4]}](figures/{name})\n')
def page():story.append(PageBreak())
def short(x):return x['design'][:3]+(' *' if x['design'].startswith('B02') else '')
def motor(x):return x['motor'].replace('-14A','')
manual='https://www.rasaero.com/dloads/RASAero%20II%20Users%20Manual.pdf'

title('MIT OpenRocket / RASAero II<br/>Controlled flight study',True)
para('27 September 2026 | Five new designs | Two motors per design | Windows 11 VM','SmallText')
para('<b>The main disagreement is aerodynamic drag, with a strong dependence on fin section.</b> After matching geometry and flow settings, RASAero predicts 1.0-27.8% lower apogee in the eight clean cases. Heavy beveled designs agree within 1.61%; the largest gaps occur on the slender rockets with square-edged fins.')
figure('apogee-difference.png')
para('* The rough-finish design B02 has unequal numerical roughness and is excluded from clean simulation attribution. Negative values mean RASAero predicts a lower apogee. All primary RASAero runs have All Turbulent Flow enabled.','SmallText')
sub('What the study establishes')
para('Replacing only MIT OR\'s drag coefficient with the curve recorded by RASAero reduces the eight clean apogee differences to <b>0.04-0.86%</b>. This supports drag modeling as the dominant cause. It does not determine which program better predicts real flight; no flight measurements were used.')
para('Three export issues need attention: turbulent-flow settings, beveled-fin geometry, and physical roughness mapping. A separate MIT time-step override is confirmed, but actual half-step refinement changes apogee by less than 0.02% here.')
para('RASAero was configured, run and exported through the Windows GUI. MIT OR used the installed MIT application JAR through its simulation/export APIs; all ten baseline cases and ten requested-step repeats were also run inside the VM. Mac/Windows apogees match exactly. This is a flight-prediction study, not a computational-speed benchmark.','SmallText')

page();title('1. Experimental design')
para('The rockets deliberately remove appendages, active control and multi-stage complications. B01/B03 and B04/B05 isolate fin-edge treatment at fixed planform and mass. B02 exposes the roughness mapping problem. These are simulation fixtures, not qualified flight hardware designs.')
table(['Parameter','B01 / B02 / B03','B04 / B05'],[
['Body diameter','4.000 in (101.60 mm)','2.260 in (57.404 mm)'],
['Overall length','60.000 in (1.524 m)','50.000 in (1.270 m)'],
['Tangent-ogive nose / body','12 / 48 in','10 / 40 in'],
['Fins: count; root / tip chord','4; 6 / 2 in','3; 5 / 2 in'],
['Fin span / leading-edge sweep','3.25 / 4 in','2.5 / 2.5 in'],
['Thickness; aft-edge inset','0.125 in; 0.500 in','0.125 in; 0.500 in'],
['Dry structure mass / dry CG','6.000 kg / 33 in from tip','1.000 kg / 27 in from tip'],
], [169,167,168])
table(['Design','Surface finish','Fin section'],[
['B01 smooth square','Zero roughness','Square'],['B02 rough square *','OR 60 micrometers; RAS 30.48 micrometers','Square'],['B03 smooth bevel','Zero roughness','0.25 in nose bevel; square trailing edge'],['B04 slender square','Zero roughness','Square'],['B05 slender bevel','Zero roughness','0.25 in nose bevel; square trailing edge']], [117,175,212])
sub('Shared flight conditions')
para('AeroTech I500T-14A and J570W use the same numerical RASP motor entries, preserved in models/study-motors.eng. Motors are aft-flush with zero overhang and no ignition delay. Dry mass/CG overrides include the structure and recovery system; motor mass and CG are added separately.')
para('Launch altitude 0 m; vertical 2 m rail; zero wind and turbulence; 15 C and 101325 Pa at sea level. MIT OR uses ISA, latitude 45 degrees, longitude 0 and flat-earth geometry. RASAero receives 59 F, 29.9214 inHg and a 6.5617 ft rail. Both use a 24 in parachute, Cd 0.8, at apogee with no delay. Motor ejection is disabled in OR.')
para('No lugs, rail guides, camera pods, tabs, fillets, transitions, fin cant, drag overrides or controllers. RASAero nozzle diameter is zero; plume/nozzle corrections are not investigated. Primary runs match the fully turbulent assumption: OR perfectFinish=false; RAS All Turbulent Flow=true.','SmallText')

page();title('2. Model equivalence and remaining differences')
table(['Item','Observed difference / treatment','Consequence'],[
['Fin-section export','MIT TRIANGULAR exports as Square with a warning. In the GUI, B03/B05 were changed to Hexagonal Blunt Base, FX1=0.25 in, LE radius=0.','Primary bevel runs preserve the pointed leading bevel and blunt trailing edge. Raw exports are retained.'],
['Flow assumption','Exporter writes Turbulence=False; MIT OR uses perfectFinish=false. All Turbulent Flow was enabled in RAS for every primary case.','A settings mismatch is removed before solver attribution. Default-flow runs are retained as sensitivity data.'],
['Surface roughness','B02: OR NORMAL=60 micrometers; RAS Rough Camouflage Paint=0.0012 in=30.48 micrometers. All other designs use zero.','B02 is a mapping diagnostic, not an equivalent-model comparison.'],
['Geometry and units','RAS body length is rounded down by 0.0001 in. Other checked external dimensions match the export.','2.54 micrometer length rounding is negligible at the displayed precision.'],
['Mass and CG','OR retains components and motors; RAS uses entered launch mass/CG and motor data. Launch errors <0.023 g and <0.003 mm.','Initial mass properties match closely. Exported burn mass histories still differ by up to 2.28 g / 6.00 g for I500 / J570.'],
['Dynamics','RAS no-wind mode is 2DOF; MIT OR retains its dynamics solver. RAS ascent angle of attack is exactly zero.','This axial benchmark does not compare wind response, damping, CP accuracy or control dynamics.'],
['Atmosphere / gravity','ISA versus RAS U.S. Standard Atmosphere implementation; equal sea-level inputs. OR explicitly uses flat geometry.','Implementations and numerical evaluation remain possible sources of sub-percent residuals.'],
['Sampling / integration','RAS CSV requested every 0.01 s; OR actual step is about 0.0025 s. RAS Mach, velocity and force columns show sample staggering.','Use direct exported peaks and explicitly matched Mach for aerodynamic comparisons; avoid inferring atmosphere from row-wise force balance.'],
['Recovery / internals','Same nominal chute diameter, Cd and apogee trigger. Construction/inertia details are aggregated in RAS.','Ascent metrics are primary. Descent and landing loads are not validated.']
], [85,239,180])
para('RASAero was run with a per-process English number-format launcher to avoid the VM locale misreading decimal points. The installed application binary and global Windows locale were not modified. The saved native files and CSV outputs were checked for valid decimal values.','SmallText')

page();title('3. Flight statistics')
para('Primary results: fully turbulent in both programs. Heights are above launch level (also MSL here). Maximum speed and Mach are ascent values. Percent difference is 100 x (RAS / OR - 1). I500 denotes the exact I500T-14A curve.','SmallText')
table(['Case','Motor','Apogee OR / RAS\n(m)','Difference','Max speed OR / RAS\n(m/s)','Max Mach OR / RAS'],[[short(x),motor(x),f"{x['openrocket']['apogee_m']:.1f} / {x['rasaero']['apogee_m']:.1f}",f"{x['delta_pct']['apogee_m']:+.2f}%",f"{x['openrocket']['vmax_m_s']:.1f} / {x['rasaero']['vmax_m_s']:.1f}",f"{x['openrocket']['mach_max']:.3f} / {x['rasaero']['mach_max']:.3f}"] for x in D],[44,50,113,67,117,113])
table(['Case','Motor','Time to apogee OR / RAS (s)','Peak ascent acceleration OR / RAS (m/s2)'],[[short(x),motor(x),f"{x['openrocket']['time_to_apogee_s']:.3f} / {x['rasaero']['time_to_apogee_s']:.3f}",f"{x['openrocket']['accel_max_m_s2']:.2f} / {x['rasaero']['accel_max_m_s2']:.2f}"] for x in D],[55,60,175,214])
para('* B02 is not matched in roughness. Its numbers are included for completeness, not to rank aerodynamic solvers. Peak acceleration is especially sensitive to output sampling and should not be interpreted as independently validated loading. Native RAS summary apogees agree with all ten CSV-derived apogees within 0.005 m.','SmallText')

page();title('4. Drag-model evidence')
para('MIT OR\'s installed aerodynamic calculator was evaluated at RASAero\'s reported Mach, altitude and zero angle of attack along ascent, using OR\'s ISA atmosphere. The plots show the J570 coast branch above 30 m/s. Matching Mach explicitly avoids the export\'s Mach/velocity sample offset. Residual atmosphere/Reynolds differences remain.')
figure('drag-comparison.png')
table(['J570 case','MIT OR Cd','RAS Cd','RAS / OR'],[[short(x),f"{x['diagnostics']['same_state_peak_or_cd']:.3f}",f"{x['diagnostics']['same_state_peak_ras_cd']:.3f}",f"{x['diagnostics']['same_state_peak_ras_cd']/x['diagnostics']['same_state_peak_or_cd']:.2f}"] for x in C if x['motor']=='J570W'],[138,122,122,122])
para('Table: coefficients at the RAS maximum-speed row, with OR evaluated at that row\'s reported Mach and altitude. Both coefficients use the body frontal reference area. These are comparisons of model predictions, not measured drag.','SmallText')
para('The square-fin discrepancies persist at common flight states, so they cannot be explained solely by the trajectories reaching different speeds. Beveling changes RASAero\'s predicted drag and apogee much more than MIT OR\'s in these fixtures. RAS component drag decomposition was not available in the flight export, so the total gap cannot yet be assigned uniquely to fin pressure, fin friction or interference.')

page();title('5. Attribution and numerical checks')
sub('Replace drag; retain MIT OR\'s flight solver')
para('A diagnostic listener substitutes RASAero\'s trajectory-derived Cd(Mach) into OR\'s total and axial drag coefficients. Powered and coast curves are interpolated separately. OR retains its motor, mass, atmosphere, gravity, integrator and other aerodynamic terms. This is an attribution experiment using RAS output, not an independent validation or a recommended production calibration.')
table(['Case','Motor','Original gap vs RAS','OR + RAS drag\napogee (m)','Replay residual\nvs RAS'],[[short(x),motor(x),f"{100*(x['openrocket']['apogee_m']/x['rasaero']['apogee_m']-1):+.2f}%",f"{x['diagnostics']['cd_replay_apogee_m']:.2f}",f"{x['diagnostics']['cd_replay_residual_pct']:+.3f}%"] for x in C],[62,63,121,129,129])
para('This table uses RAS as the denominator in both difference columns; the flight-statistics table uses OR. All replay apogees are within 0.86% of RAS. The curve is not a complete Cd(Mach, Reynolds number, angle-of-attack) surface; interpolation, altitude dependence and sample timing limit interpretation of the small residual.','SmallText')
sub('Checks against alternative explanations')
table(['Check','Result'],[
['Shared motor curve','At common exported times: maximum thrust difference 0.00213 N (I500) and 0.00060 N (J570). Thrust RMSE below 0.00041 N.'],
['Requested time step','Requests of 0.010 and 0.005 s do not change the actual ~0.0025 s step or the flight statistics. Source and installed bytecode confirm a global-step override.'],
['Actual half-step convergence','Set the existing public timing globals from 0.0025 to 0.00125 s in the test process. Largest absolute apogee change across ten cases: 0.0163%. No application source was changed.'],
['Windows / Mac repeat','Same MIT JAR and fixture builder: all ten baseline apogees and time histories of altitude, mass, thrust and time match exactly. Remaining compared columns differ only at floating-point roundoff (<8e-15).'],
['Output verification','All ten RAS native summary apogees agree with exported CSV peaks. Corrected CDX1 files retain the intended geometry, flow flag and launch settings.']
],[142,362])

page();title('6. Flow-setting sensitivity')
para('The primary comparison matches fully turbulent flow. The initial RAS exports instead allow laminar flow and transition. Turning on All Turbulent Flow lowers RAS apogee by 1.7-19.5% in the clean cases; leaving that setting unmatched can make agreement look much better by cancellation.')
table(['Case','Motor','RAS default flow\napogee (m)','RAS all turbulent\napogee (m)','Change'],[[short(x),motor(x),f"{x['rasaero_export_defaults']['apogee_m']:.1f}",f"{x['rasaero']['apogee_m']:.1f}",f"{x['diagnostics']['flow_switch_apogee_pct']:+.2f}%"] for x in D],[62,65,145,145,87])
para('In these default-flow sensitivity runs the beveled-fin geometry had already been corrected. "Default" refers only to the flow flag, not to an entirely uncorrected export. The manual describes RAS default transition at Reynolds number 500,000 and the checked option as immediate turbulent flow [1, pp. 55-56].','SmallText')
sub('Why the roughness result is not a solver comparison')
para('OR\'s NORMAL finish represents 60 micrometers. The exported RAS category, Rough Camouflage Paint, represents 30.48 micrometers [1, p. 53]. Equal category intent therefore does not give equal physical roughness. B02 remains explicitly confounded. An improvement to rough-surface aerodynamics cannot be inferred from its flight difference until physical roughness is matched.')
sub('Interpretation of the matched setting')
para('Fully turbulent flow is chosen to match the current OR configuration, not because this study proves that every real rocket is fully turbulent from the tip. A separate measured validation should determine appropriate transition and roughness assumptions. Matching the checkbox removes one disagreement in assumptions; it does not force the two programs to use identical friction correlations.')

page();title('7. Recommended MIT OR improvements')
table(['Priority / status','Change','Acceptance evidence'],[
['1 / Confirmed export issue','Map perfectFinish=false to RAS Turbulence=True. For transition-enabled OR configurations, explain that transition correlations can still differ. Location: RocketDesignDTO.','Export/reload regression fixtures verify the effective flow assumption and preserve it on save.'],
['1 / Confirmed export issue','Map MIT TRIANGULAR leading bevel to Hexagonal Blunt Base; populate FX1 from the bevel length and preserve thickness/radius. Current mapping warns and substitutes Square. Locations: RASAeroCommonConstants, FinDTO.','Round-trip square and 0.25 in beveled fixtures; compare dimensions and native GUI geometry.'],
['1 / Confirmed mapping limitation','Show source and destination roughness in physical units. Warn whenever no exact RAS category exists; offer explicit mapping choices. Location: surface-finish conversion / ExternalComponent.','A 60 micrometer OR finish must not be presented as numerically equivalent to 30.48 micrometers.'],
['1 / Confirmed timing issue','Restore user/adaptive/event limits for normal flights; isolate controller timing. RK4SimulationStepper currently replaces the selected step with a global theTimeStep when no controller is active.','Tests verify requested limits, event boundaries and refinement. This fix improves timing correctness; it is not expected to close this study\'s drag gap.'],
['2 / Aerodynamic investigation','Audit blunt-fin pressure/base drag, sweep treatment and turbulent fin friction/interference. FinSetCalc treats square fore-drag via stagnation pressure; BarrowmanCalculator shares a rocket-length Reynolds correlation across components.','Compare component drag at common Mach/Re/angle of attack against primary experimental data. Test square and beveled pairs without changing mass or planform.'],
['2 / Validation capability','Add an aerodynamic breakdown export and a reproducible benchmark suite using these fixtures: friction, pressure, base, total Cd; Mach, Reynolds, atmosphere, step size and warnings.','Track matched-case residuals and export audits in CI. Use RAS agreement as a regression signal, not as physical truth.'],
['3 / Physical calibration research','Validate transonic/body and bevel correlations with independent flight coast-down or wind-tunnel data; examine component-local Reynolds/transition alternatives.','Hold out independent geometries/fin sections and quantify uncertainty before changing default correlations.']
],[95,239,170])
para('The code locations refer to the current MIT working tree associated with the tested application. Its source contains custom changes beyond the recorded Git HEAD; SHA-256 hashes of inspected files and installed JAR are preserved. No MIT application code was modified as part of this study.','SmallText')

page();title('8. Limits, evidence and reproduction')
sub('What remains unresolved')
para('There are eight matched design/motor pairs, not eight independent physical experiments. The matrix covers only zero-wind, single-stage, axial flights and two motor curves. It does not establish CP/stability accuracy, controller behavior, staging, recovery loads or high-Mach performance. B04/B05 with J570 trigger OR\'s warning that body calculations may be inaccurate at supersonic speeds.')
para('The total drag difference is well supported; its detailed component cause is still an investigation. Mass depletion, atmosphere/gravity, sample timing and Cd interpolation can contribute to the remaining sub-percent residual. This study does not establish that RASAero is more accurate, and it does not justify a universal multiplier on OR drag.')
sub('Execution and provenance')
para('RASAero II runs in the Windows 11 VM (executable file/product version 1.0.2.0). Its GUI was used to edit profiles/flow settings, rerun each pair, save native CDX1 models and export flight CSVs. A per-process culture wrapper loads the installed executable unchanged. MIT OR designs and exports use the installed application\'s Java APIs. The same MIT JAR was copied to the VM and executed with bundled OpenJDK 17.0.16+12-LTS for repeat verification.')
para('MIT JAR SHA-256:<br/>d39a932bd26ba8ac9235c01332a93492f90e01f2a465e488d7fa541f31e3f4e6<br/>Source HEAD: e8867552ba16bf53dc67ea4da55fc3c45697048b (plus local custom changes).','SmallText')
table(['Study folder','Contents / usage'],[
['models/','Five ORKs with simulated data; raw exports; GUI-corrected exports. Use *-turbulent.CDX1 for the primary comparison. study-motors.eng preserves the two motor curves.'],
['openrocket/ and rasaero/','Raw numerical histories. OR -dt005 files test the requested step; -actual-h00125 files test a true half-step; -ras-cd-replay files are the attribution diagnostic. RAS -turbulent files are primary.'],
['evidence/','Screenshots, export warnings, model audit, common-Mach aerodynamic evaluations, runtime/source hashes, convergence logs and native-summary checks.'],
['windows-validation/','MIT OR baseline/repeat histories and execution log from the Windows VM.'],
['scripts/ and figures/','Fixture generator, analysis and diagnostic source, GUI automation helpers, report/plot builders and standalone scientific figures.'],
['comparison-results.json','Machine-readable flight statistics and diagnostics; report.md is the editable report companion.']
],[145,359])
para('For reproduction: run ControlledStudy against the installed MIT JAR, then open each export in RAS and apply the documented profile/flow corrections. Confirm the same engine entries and launch settings; rerun and export CSV at 0.01 s. Run the actual-step diagnostic, StateComparison, DragReplay and analyze_study.py. The archived UI helpers retain session-specific window coordinates/PID and need adjustment for a new desktop session.','SmallText')
sub('References')
para(f'[1] RASAero II User Manual: profiles p. 15, roughness p. 53, flow pp. 55-56, flight dynamics/atmosphere pp. 79-80. <link href="{manual}" color="#167d9a">Official manual (PDF)</link>. Documentation was inspected from the locally retrieved manual.','SmallText')
para('[2] Installed MIT OpenRocket JAR and associated source tree; evidence/runtime.json and evidence/source-provenance.json identify the exact local artifacts. [3] Native models, raw outputs and GUI evidence in this study directory. All reported flight results are computed from those retained outputs.','SmallText')

def footer(c,doc):
 c.saveState();c.setStrokeColor(colors.HexColor('#c8d6dd'));c.line(54,42,558,42);c.setFont('Helvetica',8);c.setFillColor(INK);c.drawString(54,29,'MIT OR / RASAero controlled study | 27 Sep 2026');c.drawRightString(558,29,str(doc.page));c.restoreState()
doc=SimpleDocTemplate(str(OUT),pagesize=(612,792),rightMargin=54,leftMargin=54,topMargin=46,bottomMargin=56,title='MIT OpenRocket / RASAero II - Controlled Flight Study',author='MIT Rocket Team study')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
(R/'report.md').write_text('\n'.join(md)+'\n')
with (R/'flight-statistics.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['design','motor','roughness_matched','or_apogee_m','ras_apogee_m','delta_apogee_pct','or_vmax_m_s','ras_vmax_m_s','or_max_mach','ras_max_mach','or_time_to_apogee_s','ras_time_to_apogee_s','or_peak_ascent_acceleration_m_s2','ras_peak_ascent_acceleration_m_s2'])
 for x in D:w.writerow([x['design'],x['motor'],not x['design'].startswith('B02'),x['openrocket']['apogee_m'],x['rasaero']['apogee_m'],x['delta_pct']['apogee_m'],x['openrocket']['vmax_m_s'],x['rasaero']['vmax_m_s'],x['openrocket']['mach_max'],x['rasaero']['mach_max'],x['openrocket']['time_to_apogee_s'],x['rasaero']['time_to_apogee_s'],x['openrocket']['accel_max_m_s2'],x['rasaero']['accel_max_m_s2']])
print(OUT)
