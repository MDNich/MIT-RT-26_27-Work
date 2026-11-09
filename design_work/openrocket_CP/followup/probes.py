"""Near-zero normal slope from native flight probes; compare time alignments without dividing by individual small angles."""
from pathlib import Path
import argparse,csv,math
import numpy as np
from analyze import ROOT,O,read,write,D,PARTS,TERMS

def estimate(path):
    raw=read(path)
    col=lambda s:np.array([float(r[s]) for r in raw])
    time=col('Time (sec)');m=col('Mach Number');alpha=np.deg2rad(col('Angle of Attack (deg)'))
    lift=col('CL');drag=col('CD');cp=col('CP (in)');stage=np.array([r['Stage'] for r in raw])
    assert np.all(np.diff(time)>0)
    fits=[]
    for branch in ('ascent','coast'):
        # Branch names here identify increasing/decreasing Mach, not the motor's thrust state.
        sign=1 if branch=='ascent' else -1
        indices=[i for i in range(2,len(m)-2) if 2.75<=m[i]<=2.85 and
                 np.max(abs(alpha[i-1:i+1]))<np.radians(.05) and
                 np.all(np.diff(m[i-2:i+3])*sign>0) and np.all(stage[i-2:i+3]==stage[i])]
        idx=np.array(indices,dtype=int)
        if len(idx)<3 or min(m[idx])>=2.8 or max(m[idx])<=2.8:continue
        dm=m[idx]-2.8
        for lag in (-2,-1,0,1,2):
            angle=alpha[idx+lag]
            cn=lift[idx]*np.cos(angle)+drag[idx]*np.sin(angle)
            # Minimize force residuals directly. The intercept A is the slope at M=2.80.
            mat=np.column_stack([angle,angle*dm])
            coef,_,rank,_=np.linalg.lstsq(mat,cn,rcond=None)
            if rank!=2:continue
            residual=cn-mat@coef
            xi=np.argsort(m[idx]);station=np.interp(2.8,m[idx][xi],cp[idx][xi])
            fits.append(dict(branch=branch,lag=lag,rows=len(idx),mach_min=min(m[idx]),mach_max=max(m[idx]),
                max_abs_inc_deg=np.degrees(max(abs(angle))),slope_at_2p8=coef[0],slope_mach_derivative=coef[1],
                scaled_residual=np.linalg.norm(residual)/np.linalg.norm(angle),cp_in_at_2p8=station))
    return fits
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('registry',type=Path,default=ROOT/'followup/probe-files.csv',nargs='?')
    args=parser.parse_args(); registry=read(args.registry)
    fits=[];selected={}
    for case in registry:
        entries=estimate(ROOT/case['file'])
        if not entries:
            raise ValueError(f"No qualifying Mach bracket for {case['run']} {case['part']}")
        for branch in ('ascent','coast'):
            candidates=[r for r in entries if r['branch']==branch]
            if not candidates or min(candidates,key=lambda r:r['scaled_residual'])['lag']!=-1:
                raise ValueError(f"Preceding-angle alignment did not win for {case['part']} {branch}")
        for r in entries:fits.append(dict(part=case['part'],run=case['run'],**r))
        if case['use_for_components']=='yes':
            selected[case['part']]=[r for r in entries if r['lag']==-1]
    write('probe-alignment.csv',fits)
    if set(selected)!=set(PARTS):raise ValueError('Missing component probe')
    states=[r for r in read(O/'states.csv') if r['model']=='transfer' and r['fixture']=='ork' and
            float(r['mach'])==2.8 and float(r['alpha_deg'])==0]
    or_pair={r['geometry']:np.array([float(r['N']),float(r['J'])]) for r in states}
    summary=[]
    static_cp={}
    for part in PARTS:
        static=read(ROOT/'inputs/iris-components/rasaero'/(part+'.csv'))
        static_cp[part]=float(next(v['CP'] for v in static if float(v['Mach'])==2.80 and float(v['Alpha'])==0))
    for branch in ('ascent','coast'):
        if not all(any(r['branch']==branch for r in selected[p]) for p in PARTS):continue
        q={p:next(r for r in selected[p] if r['branch']==branch) for p in PARTS}
        xref=static_cp['finned']/D;N=or_pair['finned'][0]
        old=np.zeros(2);total=0
        for p,term in zip(PARTS,TERMS):
            v=q[p];n=v['slope_at_2p8']*((4.02/D)**2 if p=='forebody' else 1)
            error=or_pair[p]-n*np.array([1,static_cp[p]/D]);dn,dj=error-old;old=error
            dx=(dj-xref*dn)/N;total+=dx
            summary.append(dict(branch=branch,part=p,term=term,native_N_common=n,native_static_cp_in=static_cp[p],native_flight_cp_in=v['cp_in_at_2p8'],
                                delta_N=dn,delta_J=dj,cp_contribution_D=dx))
        assert abs(total-or_pair['finned'][1]/N+xref)<1e-9
    if summary:write('probe-attribution.csv',summary)
if __name__=='__main__':main()
