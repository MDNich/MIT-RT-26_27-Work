from pathlib import Path
import shutil,json,hashlib,numpy as np
T=Path(__file__).resolve().parents[1];P=T.parents[1];O=P/'output/latex/random_vibration/reproduction/motion';O.mkdir(parents=True,exist_ok=True)
items=[]
def cp(src,rel):
 src=Path(src)
 if not src.exists():return
 dst=O/rel;dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dst)
 items.append({'path':str(dst.relative_to(O)),'source':str(src),'bytes':dst.stat().st_size,'sha256':hashlib.sha256(dst.read_bytes()).hexdigest()})
for n in ['generate_input.py','prepare_basis.py','prepare_transient.py','prepare_expansion.py','verify_transient.py','verify_expansion.py','render_explicit_template.py','collect_frames_native.py','unpack_frames.py','make_video_legend.py','encode_motion.py','pcb_stress_motion_v5.py','motion_q_X.py','render_stress.py','stress_gui_pilot_v5.py','bmp_pilot.py','restore_v5.py','compare_warp_native1000.py','stress_reference.pydata','repair_XZ_frames.py']:
 cp(T/'control'/n,Path('scripts')/n)
for n in ['STRESS_RESULT_ID.txt','MODAL_RESULT_ID.txt','bmp_pilot_audit.txt','stress_gui_pilot_v5_audit.txt','modal_gui_pilot_v5_audit.txt']:
 cp(T/'control'/n,Path('audits')/n)
for n in ['modal_validation_shapes.csv','dpf_stress_ACCEPTED.json','dpf_superposition_proof.json','dpf_pcb_basis_proof.json','dpf_stress_unaveraged_frames.json','stress_video_fields_ACCEPTED.json','GRAPHICS_SCALE_ACCEPTED.json','MOTION_PILOT_ACCEPTED.json','delivery_plan.json']:
 cp(T/n,Path('audits')/n)
for a in 'XYZ':
 cp(T/'inputs'/(a+'_audit.json'),Path('inputs')/(a+'_audit.json'))
 for stage in ['transient','expand']:
  src=T/(stage+'_'+a)
  for n in ['manifest.json','preflight.dat','run.dat','preflight.out','solve.out','ACCEPTED.json','native_node_checks.csv','times.txt','rst.sha256']:
   cp(src/n,Path('native')/(stage+'_'+a)/n)
 src=T/('transient_'+a)/'modal_coordinates.npy';q=np.load(src,mmap_mode='r');idx=[np.argmin(abs(q[:,0]-(1+k/16384))) for k in range(1,481)]
 dst=O/'inputs'/('modal_coordinates_'+a+'_clip.csv');np.savetxt(dst,q[idx],delimiter=',',header='mcf_time_s,'+','.join('q%d'%i for i in range(1,39)),comments='',fmt='%.17g')
for v in (T/'videos').iterdir():
 if not(v/'ENCODED.json').exists():continue
 for n in ['manifest.json','export.py','frame_audit.csv','field_audit.txt','REPAIRED.txt','camera_audit.txt','FRAMES_VALIDATED.json','TIMES_VALIDATED.json','ENCODED.json','encode_command.json']:
  cp(v/n,Path('videos')/v.name/n)
(O/'README.txt').write_text('''Random-vibration motion reproduction supplement, 6 October 2026.
Read sections 19 onward of power_board_random_vibration.tex before reuse.

The original project root is the powerboardsim/1 directory. T denotes its
outputs/random_motion_20261005_2143 directory. Scripts retain these project
relationships and the documented Windows C:\\Temp paths. They are evidence
and reproduction sources, not a one-click installer. Create a NEW runtime,
adapt paths and verified IDs, and preserve original result files.

The three complete native solves use 750 N per fastener, the 38-mode
prestressed basis, 2% damping, separate seeded X/Y/Z base acceleration,
65536 Hz integration, and a 9 s duration. The video window contains 480
states at 16384 Hz from 1.00006103515625 to 1.029296875 s.

Included CSVs retain the MCF's rounded time column for provenance.
For exact video times use 1 + (frame_index+1)/16384, not rounded MCF times.
The supplied generate_input.py recreates all input samples from the seeds.
Large binary Workbench, modal restart, and result files remain in the
preserved project/native archives identified by the report and manifests.
They are not duplicated in this compact source bundle.

Rendering uses native Mechanical fields and geometry. Every evaluated result
must have the expected time before export. Keep the camera and legend fixed.
Reject repeated/stale result states caused by a lost license. Encode only
480 valid 3840x2160 images at 60 fps; decode the complete output for checking.
Displacement is relative to the base, visually multiplied by 50. Playback
is slowed by 16384/60. The result is one seeded realization, not an RMS movie.

Dynamic stress is reconstructed from six modal stress components in global
coordinates before evaluating von Mises. Static clamp stress is excluded.
The Figure 18 motion view uses elemental-nodal, unaveraged stress values.
The source manifest and per-video audits record the completed outputs.
''')
for f in (O/'inputs').glob('modal_coordinates_*_clip.csv'):
 items.append({'path':str(f.relative_to(O)),'source':'selected rows of accepted native MCF coordinates','bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
(O/'MANIFEST.json').write_text(json.dumps(items,indent=2));print(O,len(items))
