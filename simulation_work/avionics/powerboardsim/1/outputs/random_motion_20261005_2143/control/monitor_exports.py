from pathlib import Path
import subprocess,datetime,json
T=Path(__file__).resolve().parents[1];u='{e7540578-be7d-4ee0-9a40-8aa94dcb9efd}';out={'time':datetime.datetime.now().isoformat()}
for key,p in [('modal',r'C:\Temp\PBMotionVideos\modal_fig03_bolted_mode20\progress.txt'),('stress',r'C:\Temp\PBMotionVideos\random_fig18_pcb_stress\progress.txt'),('error',r'C:\Temp\PBMotionControl\request_error.txt')]:
 r=subprocess.run(['prlctl','exec',u,'cmd.exe','/c','type',p],capture_output=True,text=True,errors='replace',timeout=30)
 if r.returncode == 255:
  r=subprocess.run(['prlctl','exec',u,'cmd.exe','/c','type',p],capture_output=True,text=True,errors='replace',timeout=30)
 out[key]=r.stdout.strip() if r.returncode==0 else None
out['encoded_motion']=len(list((T/'videos').glob('*/ENCODED.json')))
out['encoded_modal']=len(list((T.parents[1]/'outputs/video_4k60_20261005_1928').glob('modal_*/ENCODED.json')))
(T/'LATEST_EXPORT_STATUS.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
