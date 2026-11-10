"""Project a unit lateral load on the installed boards and check the native normalization of the modes."""
import re
import struct

import numpy as np
from ansys.mapdl import reader
from ansys.mapdl.reader.rst import Result

from audit_local import ROOT, read
from basis_comparison import field_files
from case_stress import source
from film_identity import digest, verified, write_json
from local_equilibrium import positions
from snug_board_pull import BODIES, BRANCHES, CAMPAIGN, REGISTRY, mass_weights
from snug_edge_cell_travel import get_geometry
from stage_snug_fit import AUDIT


def rotations(folder, ledger, ids, frequency):
    """Read six-DOF nodes from native uncompressed DMP solution records, including internal beam nodes."""
    values=np.full((len(frequency),len(ids),6),np.nan)
    for file in sorted(folder.glob('file[0-9]*.rst')):
        domain=Result(str(file),read_mesh=False)
        nodes=domain._resultheader['neqv']
        selected=np.flatnonzero(np.isin(nodes,ids))
        if not len(selected):continue
        verified(file,ledger[file.name])
        assert np.array_equal(domain.time_values,frequency)
        target=positions(ids,nodes[selected])
        with file.open('rb') as stream:
            for mode in range(len(frequency)):
                header=domain._result_solution_header(mode)
                assert list(header['DOFS'][:6])==[1,2,3,4,5,6] and header['numdof']==6 and header['nnod']==len(nodes)
                offset=4*(int(domain._resultheader['rpointers'][mode])+int(header['ptrNSL']))
                stream.seek(offset)
                words,flags=struct.unpack('<II',stream.read(8))
                assert flags==0 and words==12*len(nodes)
                data=np.fromfile(stream,dtype='<f8',count=words//2).reshape(-1,6)[selected]
                assert len(data)==len(selected) and np.isfinite(data).all()
                old=values[mode,target];duplicate=np.isfinite(old).all(1)
                assert np.allclose(old[duplicate],data[duplicate],rtol=1e-10,atol=1e-8)
                values[mode,target]=data
    assert np.isfinite(values).all()
    return values


def equation_modes(branch, basis, folder, raw, d, sets):
    """Yield native expanded eigenvectors in the supplied physical node and DOF order."""
    freq=raw.time_values
    fields=field_files(basis['case'],CAMPAIGN,basis['rst_sha256'],len(freq)) if branch!='bare' else None
    physical=d[:,1]<3
    rot_ids=np.unique(d[~physical,0])
    if len(rot_ids):
        ledger=read(ROOT/'.runtime/receipts'/CAMPAIGN/basis['case']/'archived.json')
        rot=rotations(folder,{r['name']:r['sha256'] for r in ledger['files']},rot_ids,freq)
    for j in sets:
        phi=np.empty(len(d))
        if fields is None:
            n,u=raw.nodal_displacement(j)
        else:
            stem=fields[j+1];n=np.fromfile(stem.with_suffix('.ids'),'<i4')
            u=np.fromfile(stem.with_suffix('.u'),'<f8').reshape(-1,3)
        order=np.argsort(n);idx=order[positions(n[order],d[physical,0])]
        phi[physical]=u[idx,d[physical,1]]
        if len(rot_ids):
            take=order[positions(n[order],rot_ids)]
            assert np.allclose(u[take,:3],rot[j,:,:3],rtol=1e-9,atol=1.e-9)
            phi[~physical]=rot[j,positions(rot_ids,d[~physical,0]),d[~physical,1]]
        yield phi


def mass_check(branch, basis, folder, raw):
    src=branch+'_enforced'
    record=read(ROOT/'validation/motion'/f'{src}.json');assert record['basis_rst_sha256']==basis['rst_sha256']
    path=folder.parent/src/'file.full'
    sha=verified(path,record['smp_parent_sha256']['file.full'])
    full=reader.read_binary(path);d,k,m=full.load_km(sort=False);del full,k
    freq=raw.time_values
    rot_ids=np.unique(d[d[:,1]>=3,0])
    phi=np.column_stack(list(equation_modes(branch,basis,folder,raw,d,range(len(freq)))))
    gram=phi.T@(m@phi)
    gram=gram+gram.T-phi.T@(m.diagonal()[:,None]*phi)
    error=abs(gram-np.eye(len(freq)))
    print(branch,'modal mass error',float(error.max()),flush=True)
    assert error.max()<.001
    return dict(matrix_sha256=sha,matrix_equations=len(d),rotational_nodes=rot_ids.tolist(),
                diagonal_range=[float(gram.diagonal().min()),float(gram.diagonal().max())],
                max_abs_off_diagonal=float(abs(gram-np.diag(gram.diagonal())).max()))


def run(branch):
    xyz_record=read(REGISTRY)[branch+'_cellpush_x']
    basis,folder,raw=source(branch+'_basis',CAMPAIGN)
    mass=mass_check(branch,basis,folder,raw)
    modal,_,freq,_,relative,_,cell,_,_=get_geometry(branch,CAMPAIGN)
    assert modal['rst_sha256']==basis['rst_sha256']
    _,_,evidence=mass_weights(branch)
    path=ROOT/'.runtime/post'/CAMPAIGN/basis['case']/'cell_mass_mean.npz'
    verified(path,evidence['mean_shapes_sha256'])
    listing=folder/'solve.out';verified(listing,evidence['modal_listing_sha256'])
    text=listing.read_text(errors='replace')
    assert 'NORMALIZE THE MODE SHAPES TO THE MASS MATRIX' in text
    assert re.search(r'EXTRACT FREQUENCIES IN THE RANGE\s+1\.0+\s+TO\s+4000\.0',text)
    with np.load(path) as data:
        mean=np.stack([data['mean'][np.flatnonzero(data['materials']==m).item(),0] for m in BODIES])
        assert np.array_equal(freq,data['frequencies_Hz']) and np.allclose(cell[:,0]/1000,mean[0],atol=1e-12)
    q=mean[0]/(2*np.pi*freq)**2
    methods={}
    for cut in (2000,3000,3500,4000):
        take=freq<=cut
        H=(mean[:,take]/(2*np.pi*freq[take])**2)@mean[:,take].T
        assert np.allclose(H,H.T,atol=1e-15) and np.linalg.eigvalsh(H).min()>0
        assert np.isclose(H[0,0],np.sum((2*np.pi*freq[take]*q[take])**2),rtol=1e-12,atol=0)
        methods[str(cut)]=dict(modes=int(take.sum()),cell_X_compliance_um_per_N=(1e6*H).tolist(),
                               left_relative_to_its_clamps_X_um_per_N=float(1000*q[take]@relative[take,0]))
    proof=dict(branch=branch,case=basis['case'],campaign=CAMPAIGN,basis_sha256=basis['rst_sha256'],
               force_pattern_sha256=xyz_record['force_cards_sha256'],matching_direct_case=branch+'_cellpush_x',
               native_mass_check=mass,cutoff_Hz=methods,cell_order=list(BODIES),
               scope='Independent initial locked-state flexibility for a mass-distributed PCB-X load on each cell. '
                     'Columns identify load cells and rows identify observed mass centres relative to the fixed stand-offs. '
                     'Only the modes in the native 1–4000 Hz band are available. These projected values hold the installed contact state fixed.')
    write_json(AUDIT/f'{branch}_cell_flexibility.json',proof)
    print(branch,methods['4000'],flush=True)


def compare():
    from compare_pull import series
    from snug_board_pull import REFERENCE
    files=[AUDIT/f'{b}_cell_flexibility.json' for b in BRANCHES]
    if not all(p.is_file() for p in files):
        return
    cases={}
    for branch,path in zip(BRANCHES,files,strict=True):
        data=read(path);assert data['branch']==branch
        model=read(ROOT/'validation/global'/f'{branch}_basis.json')
        assert data['basis_sha256']==model['rst_sha256']
        a,b=[data['cutoff_Hz'][k] for k in ('3500','4000')]
        checks={}
        for name,r in (('3500',a),('4000',b)):
            C=np.array(r['cell_X_compliance_um_per_N'])
            checks[name]=[C[0,0],r['left_relative_to_its_clamps_X_um_per_N'],C[1,0]]
        cases[branch]=dict(source_sha256=digest(path),left_absolute_left_clamp_middle_absolute_um_per_N=checks['4000'],
                           shift_3500_to_4000_um_per_N=(np.array(checks['4000'])-checks['3500']).tolist())
    _,bare=series('bare_lateral_friction_locked')
    fixture=read(AUDIT/REFERENCE)
    native=[r for r in fixture['states'] if .0049<r['travel_mm']<.0101]
    assert len(native)==2 and all(r['both_contact_pairs']['861']['closed_faces']==0 for r in native)
    br=[r for r in bare if .0049<r['ux_mm']<.0101]
    assert len(br)==2
    for old,new in zip(br,native,strict=True):
        assert abs(old['cell_force_N']-new['cell_force_N'])<1e-8 and abs(old['ux_mm']-new['travel_mm'])<1e-8
    slope=1000*(br[1]['ux_mm']-br[0]['ux_mm'])/(br[1]['cell_force_N']-br[0]['cell_force_N'])
    write_json(AUDIT/'whole_board_initial_comparison.json',dict(cases=cases,
               matched_fixture_stations=[dict(travel_mm=r['ux_mm'],force_N=r['cell_force_N']) for r in br],
               initial_local_fixture_increment_um_per_N=slope,fixture_checkpoint_sha256=digest(AUDIT/REFERENCE),
               direct_control_registry_sha256=digest(REGISTRY),
               scope='Independent, truncated whole-board initial tangent and the early native bare/nylon shell-fixture increment. '
                     'Nonlinear whole-board response awaits the separate direct controls.'))


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('branch',choices=(*BRANCHES,'compare'))
    branch=p.parse_args().branch
    if branch!='compare':run(branch)
    compare()
