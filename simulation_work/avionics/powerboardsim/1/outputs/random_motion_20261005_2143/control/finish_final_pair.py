from pathlib import Path
import subprocess,time
T=Path(__file__).resolve().parents[1];PY='/Users/mdn/miniforge3/bin/python3'
while not (T/'control/MODAL_RENDER_COMPLETE.txt').exists():time.sleep(5)
subprocess.run([PY,str(T/'control/finish_modal.py')],check=True)
subprocess.run([PY,str(T/'control/finish_available_videos.py'),'random_fig18_pcb_stress'],check=True)
subprocess.run([PY,str(T/'control/build_gallery.py')],check=True)
subprocess.run([PY,str(T/'control/build_legacy_gallery.py')],check=True)
print('ALL VIDEOS ENCODED - visual QA and reports remain',flush=True)
