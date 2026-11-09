"""Integrate a one-sided modal transfer function over the actual base spectrum. This is not a MAPDL PSD solve."""
import argparse,csv,json,re
import numpy as np
from seeded_motion import participation
from basis_comparison import field_files
from audit_local import ROOT,read
from native_rst import read_rst
from film_identity import verified,write_json,digest

def moments(mode_f,g,fk,sk,zeta,df):
    # Log-log interpolation of each actual input segment; endpoint weights once per segment.
    c=np.zeros((len(mode_f),len(mode_f)));wn=2*np.pi*mode_f;power=0.
    for l,h,sl,sh in zip(fk[:-1],fk[1:],sk[:-1],sk[1:],strict=True):
        f=np.linspace(l,h,int(np.ceil((h-l)/df))+1);step=f[1]-f[0]
        s=sl*(f/l)**(np.log(sh/sl)/np.log(h/l))
        wt=step*s;wt[[0,-1]]*=.5;power+=wt.sum()
        w=2*np.pi*f[:,None]
        a=-g[None,:]/(wn[None,:]**2-w**2+2j*zeta*w*wn[None,:])
        a*=np.sqrt(wt)[:,None];c+=(a.conj().T@a).real
    return .5*(c+c.T),float(power)

def rms_field(phi,covariance):
    eig,v=np.linalg.eigh(covariance)
    assert eig.min()>=-1e-13*eig.max()
    factor=v*np.sqrt(np.maximum(eig,0.))
    values=np.empty(phi.shape[:2])
    for start in range(0,len(phi),8192):
        projected=phi[start:start+8192].reshape(-1,len(eig))@factor
        values[start:start+8192]=1000*np.linalg.norm(projected,axis=1).reshape(-1,3)
    return values


def run(branch,campaign,*,cutoffs=False):
    case=branch+'_basis';p=read(ROOT/'validation/global'/f'{case}.json');assert p['campaign']==campaign
    ledger=read(ROOT/'.runtime/receipts'/campaign/case/'archived.json')
    d=ROOT/'.runtime/archive'/campaign/case;rst=d/'file.rst';verified(rst,p['rst_sha256'])
    txt=d/'solve.out';verified(txt,next(v['sha256'] for v in ledger['files'] if v['name']=='solve.out'))
    listing=txt.read_text(errors='replace');r=read_rst(rst);freq=np.asarray(p['frequencies_Hz']);assert np.array_equal(freq,r.time_values)
    mat=r.grid.cell_data['ansys_material_type'];solid=np.isin(r.grid.cell_data['ansys_elem_type_num'],[185,186,187])
    scope={k:np.unique(r.grid.extract_cells(solid&mask).point_data['ansys_node_num'])
           for k,mask in [('assembly',solid),('pcb',mat==208),('cells',np.isin(mat,[176,187,191])),('nickel',np.isin(mat,[174,179,180,186,189,193])),('case',mat==850)] if (solid&mask).any()}
    ids=scope['assembly'];scopes={k:np.searchsorted(ids,v) for k,v in scope.items()}
    phi=np.empty((len(ids),3,len(freq)),float)
    stems={} if branch=='bare' else field_files(case,campaign,p['rst_sha256'],len(freq))
    for k in range(len(freq)):
        if stems:
            stem=stems[k+1];n=np.fromfile(stem.with_suffix('.ids'),'<i4');u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        else:n,u=r.nodal_displacement(k);u=u[:,:3]
        sort=np.argsort(n);i=sort[np.searchsorted(n[sort],ids)];assert np.array_equal(n[i],ids);phi[:,:,k]=u[i]
    assert np.isfinite(phi).all()
    out={};diffs=[];truncation={};octbase=ROOT/'validation/october_psd_reference'
    for ax in 'XYZ':
        path=ROOT/f'.runtime/inputs/bare_psd_{ax}/model.inp';src=path.read_text()
        def numbers(card):return np.array([float(x) for x in re.search(r'^'+card+r',1,,?([^\n!]+)',src,re.I|re.M)[1].split(',')])
        fk=numbers('PSDFRQ');sk=numbers('PSDVAL');zeta=float(re.search(r'^\s*dmprat,([\d.Ee+-]+)',src,re.M|re.I)[1])
        assert np.array_equal(fk,[20,50,800,2000]) and np.all(sk>0) and zeta==.02 and 'psdres,disp,rel' in src.lower()
        gamma=participation(listing,ax);c,power=moments(freq,gamma,fk,sk,zeta,.125);c2,_=moments(freq,gamma,fk,sk,zeta,.25)
        quaderr=float(np.linalg.norm(c2-c)/np.linalg.norm(c));assert quaderr<1e-5
        gvals=rms_field(phi,c)
        if cutoffs:
            truncation[ax]={}
            for limit in (2000,3000,3500,4000):
                count=int(np.searchsorted(freq,limit,side='right'))
                assert count>0
                field=gvals if count==len(freq) else rms_field(phi[:,:,:count],c[:count,:count])
                levels={}
                for name,indices in scopes.items():
                    peaks=field[indices].max(axis=0)
                    reference=gvals[indices].max(axis=0)
                    levels[name]=dict(peak_XYZ_RMS_mm=peaks.tolist(),
                        change_from_full_basis_percent=(100*(peaks/reference-1)).tolist())
                truncation[ax][str(limit)]=dict(retained=count,last_mode_Hz=float(freq[count-1]),scopes=levels)
        fields={};octref={}
        if branch=='bare':
            provenance=read(octbase/'sources.json')[ax];ref=octbase/provenance['file'];verified(ref,provenance['sha256'])
            with ref.open() as f:octref={k['name']:float(k['maximum'].split()[0])*1000 for k in csv.DictReader(f,delimiter='\t') if k['category']=='DirectionalDeformation'}
        for nm,i in scopes.items():
            imax=np.argmax(gvals[i],axis=0);vals=gvals[i][imax,np.arange(3)]
            fields[nm]=dict(peak_directional_RMS_mm=vals.tolist(),peak_node=ids[i][imax].tolist())
            if nm in ('assembly','pcb') and octref:
                key=('PCB RMS displacement ' if nm=='pcb' else 'RMS displacement ')
                refv=np.array([octref[key+v+' - base '+ax] for v in 'XYZ'])
                rel=vals/refv-1;diffs.extend(abs(rel));fields[nm].update(october_native_mm=refv.tolist(),relative_difference=rel.tolist())
        out[ax]=dict(axes_order='XYZ',base_RMS_m_s2=float(np.sqrt(power)),frequency_grid_halving_covariance_relative_change=quaderr,
                     spectra_source_sha256=digest(path),scopes=fields)
    rec=dict(method='Independent frequency integration of signed native mode shapes and participation. Relative displacement, single-axis loading, 2% damping. No nonlinear opening or closure is modeled.',
        case=case,campaign=campaign,rst_sha256=p['rst_sha256'],base_cases=out)
    if branch=='bare':
        rec['max_relative_difference_over_18_October_peaks']=float(max(diffs));rec['baseline_5pct_screen_passed']=bool(max(diffs)<.05)
    else:rec['baseline_5pct_screen_passed']=read(ROOT/'validation/independent_psd/bare_basis.json')['baseline_5pct_screen_passed']
    dest=ROOT/'validation/independent_psd'/f'{case}.json'
    if cutoffs:
        existing=read(dest)
        assert rec['rst_sha256']==existing['rst_sha256']
        for ax in 'XYZ':
            for scope,entry in rec['base_cases'][ax]['scopes'].items():
                original=existing['base_cases'][ax]['scopes'][scope]
                assert np.allclose(entry['peak_directional_RMS_mm'],original['peak_directional_RMS_mm'],rtol=1e-10,atol=1e-12)
        write_json(ROOT/'validation/modal_cutoff'/f'{case}.json',dict(case=case,campaign=campaign,
            native_rst_sha256=p['rst_sha256'],full_response_sha256=digest(dest),base_cases=truncation,
            scope='Independent displacement integration on nested subsets of the same native basis. The input spectrum spans 20–2000 Hz at every cutoff. Differences are relative to the available modes through 4000 Hz.'))
    else:
        write_json(dest,rec)
    print(case,'5 percent baseline screen',rec['baseline_5pct_screen_passed'],'max discrepancy',rec.get('max_relative_difference_over_18_October_peaks'),flush=True)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('branch');parser.add_argument('campaign')
    parser.add_argument('--cutoffs',action='store_true')
    args=parser.parse_args()
    run(args.branch,args.campaign,cutoffs=args.cutoffs)
