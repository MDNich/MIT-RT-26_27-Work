from pathlib import Path
import xml.etree.ElementTree as E,json,shutil,hashlib,subprocess
R=Path(__file__).resolve().parents[1];P=R.parent
cases=[]
for old in json.loads((P/'cases.json').read_text()):
 n=old['name'];shutil.copy2(P/'models'/f'{n}.CDX1',R/'models'/f'{n}.CDX1');shutil.copy2(P/'rasaero'/f'{n}.csv',R/'rasaero'/f'{n}.csv');cases.append({'name':n,'parent':'previous/'+n,'group':'previous','changes':{}})
new=[]
def add(name,parent,group,**changes):new.append({'name':name,'parent':parent,'group':group,'changes':changes})
for key,shape in [('cone','Conical'),('vk','Von Karman Ogive'),('ellipsoid','Elliptical')]:
 for ln in [6,12,18]:add(f'Hbody-{key}{ln}','Hbody','nose',nose_shape=shape,nose_length=ln,body_length=59.9999-ln)
for ln in [8,24]:add(f'Hbody-ogive{ln}','Hbody','nose',nose_length=ln,body_length=59.9999-ln)
for base in ['Hsq','Hbev']:
 for v in [2,3]:add(f'{base}-sweep{v}',base,'sweep',sweep=v)
 for v in [1.625,4.875]:add(f'{base}-span{v}',base,'span',span=v)
 for v in [1,3]:add(f'{base}-tip{v}',base,'tip',tip=v,sweep=2)
 for v in [.03125,.375]:add(f'{base}-t{v}',base,'thickness',thickness=v)
for v in [.0625,.125,1]:add(f'Hbev-b{v}','Hbev','bevel',bevel=v)
add('Hbev-t0.0625','Hbev','thickness',thickness=.0625)
add('Hrounded','Hsq','profile',profile='Rounded')
for base in ['Hbody','Hsq']:
 for d in [1,2,3]+([4] if base=='Hsq' else []):add(f'{base}-nozzle{d}',base,'nozzle',nozzle=d)
for base in ['Hbody','Hsq','Hbev']:
 for key,surface in [('polished','Polished'),('paint','Smooth Paint'),('rough','Rough Camouflage Paint'),('galv','Galvanized Metal')]:add(f'{base}-{key}',base,'roughness',surface=surface)
for base in ['Hbody','Hsq','Hbev','Sbody','Ssq','Sbev']:add(base+'-transition',base,'transition',turbulence=False)
for base in ['Hsq','Hbev','Ssq','Sbev']:add(base+'-rogers',base,'normal-force',modified_barrowman=True)
for base in ['Hbody','Hsq','Hbev']:
 for factor in [.5,2]:add(f'{base}-scale{factor}',base,'Reynolds',scale=factor)
for c in new:
 tree=E.parse(P/'models'/f"{c['parent']}.CDX1");rd=tree.find('RocketDesign');b=rd.find('BodyTube');n=rd.find('NoseCone');f=b.find('Fin')
 for key,v in c['changes'].items():
  if key in ['sweep','span','tip','thickness','bevel','profile']:f.find({'sweep':'SweepDistance','span':'Span','tip':'TipChord','thickness':'Thickness','bevel':'FX1','profile':'AirfoilSection'}[key]).text=str(v)
  elif key=='nose_shape':n.find('Shape').text=v
  elif key=='nose_length':n.find('Length').text=str(v);b.find('Location').text=str(v)
  elif key=='body_length':b.find('Length').text=str(v)
  elif key=='surface':rd.find('Surface').text=v
  elif key=='turbulence':rd.find('Turbulence').text=str(v)
  elif key=='modified_barrowman':rd.find('ModifiedBarrowman').text=str(v)
  elif key=='nozzle':
   rd.find('SustainerNozzle').text=str(v)
   for sim in tree.findall('SimulationList/Simulation'):sim.find('SustainerNozzleDiameter').text=str(v)
  elif key=='scale':
   for part,tags in [(n,['Length','Diameter','BluntRadius','Location']),(b,['Length','Diameter','Location']),(f,['Chord','Span','SweepDistance','TipChord','Thickness','LERadius','Location','FX1','FX3'])]:
    if part is not None:
     for tag in tags:part.find(tag).text=str(float(part.findtext(tag))*v)
 rd.find('Comments').text='Extended controlled aerodynamic study: '+c['name']
 tree.write(R/'models'/f"{c['name']}.CDX1",encoding='utf-8',xml_declaration=True);cases.append(c)
(R/'cases.json').write_text(json.dumps(cases,indent=2)+'\n');(R/'new-cases.txt').write_text('\n'.join(c['name'] for c in new)+'\n')
before=json.loads((P/'evidence/or-preservation-before.json').read_text());files=[before['jar']]+[x['path'] for x in before['source_files']];(R/'evidence/or-before.json').write_text(json.dumps({p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in files},indent=2)+'\n')
print('TOTAL',len(cases),'NEW',len(new));print(' '.join(c['name'] for c in new))
