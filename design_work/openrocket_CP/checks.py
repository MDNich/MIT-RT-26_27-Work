from analyze import *
from xml.etree import ElementTree as ET
import argparse
p=argparse.ArgumentParser(); p.add_argument('--work',type=Path,default=D/'work'); args=p.parse_args()
trial=rows(args.work/'trial-check.csv.gz'); engine=rows(R/'openrocket.csv.gz'); k=float(rows(R/'fits.csv')[0]['k'])
assert len(trial)==len(engine); dx=dn=0.
for u,v in zip(engine,trial):
    assert all(u[z]==v[z] for z in ('case','alpha_deg','mach','D_m'))
    assert max(abs(float(u[z])-float(v[z])) for z in ('x0_D','n0'))<1e-9
    x,n,y,q=[float(u[key]) for key in ('x0_D','n0','x1_D','n1')]
    dx=max(dx,abs(float(v['x1_D'])-mix(k,x,n,y,q)))
    dn=max(dn,abs(float(v['n1'])-((1-k)*n+k*q)))
assert dx<1e-8 and dn<1e-8
s,split,data=load(); geom=[];decomp=[]
for n,g in split.items():
    rd=ET.parse(I/'models'/(n+'.CDX1')).find('.//RocketDesign');b=rd.find('BodyTube');nose=rd.find('NoseCone');f=b.find('Fin')
    geom.append(dict(case=n,split=g,D_in=nose.findtext('Diameter'),nose_in=nose.findtext('Length'),body_in=b.findtext('Length'),shape=nose.findtext('Shape'),count=f.findtext('Count') if f is not None else 0,root=f.findtext('Chord') if f is not None else 0,tip=f.findtext('TipChord') if f is not None else 0,span=f.findtext('Span') if f is not None else 0,sweep=f.findtext('SweepDistance') if f is not None else 0,location=f.findtext('Location') if f is not None else 0,rogers=rd.findtext('ModifiedBarrowman')))
    # Measured at nonzero alpha so moment/force use consistent CP and CN at the same incidence.
    if n in ('Hsq','Hsq-span1.625','Hsq-sweep2','Ssq','Ssq-unswept','wide-unswept','short-span','highly-swept'):
        body='Sbody' if n.startswith('S') else 'Hbody'
        for m in [1.5,2.,2.5,3.]:
            def loads(name,w):
                tab=data[name,4];v=tab[:,np.isclose(tab[0],m)].ravel();_,x,N,y,Q,t,cn,_=v
                if w is None: return cn/np.deg2rad(4),cn*t/np.deg2rad(4)
                return (1-w)*N+w*Q, (1-w)*x*N+w*y*Q
            for model,w in [('RAS',None),('legacy',0),('finite',1),('fit',k)]:
                n1,j1=loads(n,w);n0,j0=loads(body,w)
                decomp.append(dict(case=n,body=body,mach=m,alpha_deg=4,model=model,body_N=n0,body_X=j0/n0,added_N=n1-n0,added_X=(j1-j0)/(n1-n0)))
write('geometry.csv',geom);write('body-fin-audit.csv',decomp)
print('static states',len(trial),'max native versus recombined CP (D), slope (/rad)',dx,dn)
(R/'numerical-checks.json').write_text(json.dumps(dict(states=len(trial),max_cp_delta_D=dx,max_load_delta=dn),indent=2)+'\n')
