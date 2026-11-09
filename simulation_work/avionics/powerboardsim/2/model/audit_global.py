"""Check completed global structural, modal or PSD output before dispatching its dependants."""
from pathlib import Path
import csv,hashlib,json,re,sys
import numpy as np
from ansys.mapdl import reader
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def audit(case,campaign):
    receipt=ROOT/'.runtime/receipts'/campaign/case
    d=ROOT/'.runtime/archive'/campaign/case
    meta=load(receipt/'archived.json')
    assert load(receipt/'status.json')['phase']=='solver_complete' and meta['case']==case
    assert all((d/f['name']).stat().st_size==f['bytes'] for f in meta['files'])
    lst=(d/'solve.out').read_text(errors='replace')
    assert 'RUN COMPLETED' in lst and re.search(r'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*0\b',lst)
    rst=reader.read_binary(str(d/'file.rst'))
    t=np.asarray(rst.time_values);g=rst.grid
    assert len(t)>0 and np.all(np.isfinite(t))
    nid,disp=rst.nodal_displacement(len(t)-1)
    valid=np.all(np.isfinite(disp[:,:3]),axis=1)
    assert valid.sum()>1000
    result=dict(case=case,campaign=campaign,sets=len(t),rst_sha256=next(f['sha256'] for f in meta['files'] if f['name']=='file.rst'),last_time_or_hz=float(t[-1]),finite_displacement_nodes=int(valid.sum()),max_vector_u=float(np.max(np.linalg.norm(disp[valid,:3],axis=1))),warnings=int(re.search(r'NUMBER OF WARNING\s+MESSAGES ENCOUNTERED=\s*(\d+)',lst)[1]))
    if case.endswith('_static'):
        data=np.loadtxt(d/'bolt_preload_audit.csv',skiprows=1,delimiter=',');assert data.shape==(12,5)
        assert abs(t[-1]-2)<1e-8 and np.max(np.abs(data[6:,4]-750))<1
        result['locked_bolt_reactions_N']=data[6:,4].tolist()
        if not case.startswith('bare'):
            with (d/'case_contact.csv').open() as f:
                rows=list(csv.DictReader(f))
            last={key:float(value) for key,value in rows[-1].items()}
            assert abs(last['time_s']-2)<1e-8 and last['n_contact']>0
            assert last['n_contact']==sum(last[k] for k in ('far','near','sliding','sticking'))
            assert np.all(np.isfinite(list(last.values())))
            result['installed_contact_summary']=last
            result['contact_scope']='Engineering interpretation requires penetration, seating loads and PLA stress review.'
    elif '_psd_' in case:
        # Workbench writes the statistical result sets after the modal basis; select PSD labels in the field audit.
        assert re.search(r'PSD ANALYSIS|POWER SPECTRAL DENSITY',lst,re.I)
        from psd_fields import recover
        result['native_psd_fields']=recover(d/'file.rst')
    else:
        assert np.all(np.diff(t)>0)
        if case.endswith('_basis'):assert len(t)>=20 and t[-1]<=4000.0001
        else:assert len(t)==20
        result['frequencies_Hz']=t.tolist()
    if not case.startswith('bare'):
        for mat in (850,851):assert np.count_nonzero(g.cell_data['ansys_material_type']==mat)>0
    out=ROOT/'validation/global';out.mkdir(exist_ok=True);dest=out/(case+'.json')
    temp=dest.with_suffix('.tmp');temp.write_text(json.dumps(result,indent=2)+'\n');temp.replace(dest)
    print(case,'verified',flush=True)
if __name__=='__main__':audit(*sys.argv[1:])
