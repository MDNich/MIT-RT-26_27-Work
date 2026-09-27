from pathlib import Path
import json,xml.etree.ElementTree as E,subprocess
R=Path(__file__).resolve().parents[1]
new=[('Hsq-nearzero','Hsq',{'thickness':.001}),('Hbev-nearzero','Hbev',{'thickness':.001}),('Ssq-thin','Ssq',{'thickness':.0625}),('Ssq-thick','Ssq',{'thickness':.25}),('Hbody-nozzle','Hbody',{'nozzle':4}),('Sbody-nozzle','Sbody',{'nozzle':2.26}),('Hbody-nose6','Hbody',{'nose_length':6,'body_length':53.9999}),('Hbody-nose18','Hbody',{'nose_length':18,'body_length':41.9999}),('Hsq-long','Hsq',{'body_length':96}),('Hbev-gentle','Hbev',{'bevel':.5})]
manifest=json.loads((R/'cases.json').read_text())
for name,parent,changes in new:
 root=E.parse(R/'models'/f'{parent}.CDX1');rd=root.find('RocketDesign');body=rd.find('BodyTube');fin=body.find('Fin');nose=rd.find('NoseCone')
 for key,v in changes.items():
  if key in ['thickness','bevel']:fin.find({'thickness':'Thickness','bevel':'FX1'}[key]).text=str(v)
  elif key=='body_length':body.find('Length').text=str(v)
  elif key=='nose_length':nose.find('Length').text=str(v);body.find('Location').text=str(v)
  elif key=='nozzle':
   rd.find('SustainerNozzle').text=str(v)
   for sim in root.findall('SimulationList/Simulation'):sim.find('SustainerNozzleDiameter').text=str(v)
 rd.find('Comments').text='Aerodynamic diagnostic: '+name
 root.write(R/'models'/f'{name}.CDX1',encoding='utf-8',xml_declaration=True)
 if not any(x['name']==name for x in manifest):manifest.append({'name':name,'parent':parent,'changes':changes})
(R/'cases.json').write_text(json.dumps(manifest,indent=2)+'\n')
source='\\\\Mac\\Home\\'+str((R/'models').relative_to('/Users/mdn')).replace('/','\\')+r'\*.CDX1'
subprocess.run(['prlctl','exec','Windows 11','cmd.exe','/c','copy',source,r'C:\Users\Public\Documents\CodexRASAeroStudy\aero'],check=True)
print(' '.join(x[0] for x in new))
