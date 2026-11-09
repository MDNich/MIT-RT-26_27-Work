"""Locate material-reference crossings and separate axial and bending stresses in the case screws."""
import argparse
import re

import numpy as np
from ansys.mapdl import reader
from scipy.spatial import cKDTree

from audit_local import ROOT, read, table
from film_identity import digest, verified, write_json
from native_rst import read_rst

PLA = {'in_plane_tension_MPa':52.3, 'layer_tension_MPa':40.5, 'layer_tensile_strain':float(np.log1p(.018))}
TDS = 'https://wiki.polymaker.com/polymaker-products/more-about-our-products/documents/technical-data-sheets/pla/polylite-tm-pla'
BEAM_REF = 'https://ansyshelp.ansys.com/public/views/secured/corp/v261/en/ans_elem/Hlp_E_BEAM188.html'


def run(case, campaign, *, pull=False):
    root = ROOT/'.runtime'
    folder = root/'archive'/campaign/case
    receipts = root/'receipts'/campaign/case
    ledger = read(receipts/'archived.json')
    assert ledger['case']==case and ledger['campaign']==campaign and (receipts/'released.txt').is_file()
    hashes = {row['name']:row['sha256'] for row in ledger['files']}
    local = (folder/'local_job.json').is_file()
    job = read(folder/'local_job.json')['job'] if local else 'file'
    if pull and not local:raise ValueError('Pull material audit requires a local fixture')
    verified(folder/(job+'.rst'),hashes[job+'.rst'])
    verified(folder/'model.inp',hashes['model.inp'])
    deck = (folder/'model.inp').read_text()
    scope = ('partial_local','local','review_local') if local else ('global','review_global')
    proofs = [ROOT/'validation'/k/(case+'.json') for k in scope]
    verdict = next(read(p) for p in proofs if p.is_file())
    assert verdict['rst_sha256']==hashes[job+'.rst']
    rt = reader.read_binary(str(folder/(job+'.rst'))) if local else read_rst(folder/'file.rst')
    length = 1. if local else 1000.
    stress = 1. if local else 1e-6
    state = rt._resultheader['ls_table']
    indices = np.flatnonzero((state[:, 1] != 999999) & ((state[:, 0] <= 3) | pull))
    if local:
        fixed = table(root/'post'/campaign/case/'whole_fixture_balance.csv')
        ids = fixed['native_set'].astype(int)
        travel = fixed['ux_mm'] if pull else fixed['screw1_u_mm_z']
    elif case.startswith('flush_'):
        verified(folder/'board_drives.csv',hashes['board_drives.csv'])
        drive = table(folder/'board_drives.csv')
        fixed = drive[drive['foot']==0]
        ids = fixed['set'].astype(int)
        travel = length*fixed['travel_m']
    else:
        ids = indices + 1
        travel = np.zeros(len(ids))
    assert np.array_equal(ids[:len(indices)],indices+1)
    if 'flush_' in case and not pull:
        assert np.allclose(travel[:len(indices)],3*np.clip(rt.time_values[indices]-2,0,1),rtol=0,atol=1e-6)
    grid = rt.grid.cell_data
    def elements(t):
        return np.sort(grid['ansys_elem_num'][grid['ansys_etype']==t])
    solids, beams = elements(850), elements(851)
    assert len(solids)>1000 and len(beams)==4
    E = float(re.search(r'(?im)^mp,ex,851,([^,\r\n]+)',deck)[1])*stress
    assert E in (3000.,69000.)
    prop = {}
    for k in ('EX','EY','EZ','PRXY','PRYZ','PRXZ','GXY','GYZ','GXZ'):
        prop[k] = float(re.search(r'(?im)^mp,'+k+r',850,([^,\r\n]+)',deck)[1])
    mod = np.array([prop[k] for k in ('EX','EY','EZ')])*stress
    comp = np.diag(1/mod)
    for i,j,k in ((0,1,'PRXY'),(1,2,'PRYZ'),(0,2,'PRXZ')):
        comp[i,j]=comp[j,i]=-prop[k]/mod[i]
    shear = stress*np.array([prop[k] for k in ('GXY','GYZ','GXZ')])
    bound = np.array(sorted({int(n) for n in re.findall(r'(?im)^CERIG,95000[1357],(\d+),UXYZ',deck)}))
    assert len(bound)>=12
    xyz = rt.mesh.nodes*length
    mount = cKDTree(xyz[np.searchsorted(rt.mesh.nnum,bound)])
    nodes = None
    cross = {}
    records = []
    solid_error=beam_error=axial_error=0.
    for k in indices:
        values = {}
        for field, width in [('ENS',6),('EEL',7)]:
            enum, data, labels = rt.element_solution_data(int(k),field)
            si,bi=(np.searchsorted(enum,els) for els in (solids,beams))
            assert np.array_equal(enum[si],solids) and np.array_equal(enum[bi],beams)
            ids_s = np.stack([labels[i] for i in si])
            assert ids_s.shape==(len(solids),4)
            if nodes is None:
                nodes = ids_s
                flat_nodes=nodes.ravel()
                xyz_s=xyz[np.searchsorted(rt.mesh.nnum,flat_nodes)]
                distance=mount.query(xyz_s)[0]
                away=np.flatnonzero(distance>=2.)
            else:
                assert np.array_equal(ids_s,nodes)
            assert np.array_equal(np.stack([labels[i] for i in bi]),np.arange(950001,950009).reshape(4,2))
            sa=np.stack([data[i] for i in si]).reshape(-1,width).astype(float)
            ba=np.stack([data[i] for i in bi]).reshape(4,2,25,3).astype(float)
            assert np.isfinite(sa).all() and np.isfinite(ba).all()
            values[field]=sa,ba
        S,B=values['ENS']
        S*=stress
        B*=stress
        strain,beam_strain=values['EEL']
        computed=np.column_stack((S[:,:3]@comp,S[:,3:]/shear))
        serr=np.max(abs(computed-strain[:,:6]))/max(1e-6,np.abs(strain[:,:6]).max())
        berr=np.max(abs(B[:,:,:,0]-E*beam_strain[:,:,:,0]))/max(.01,abs(B).max())
        assert serr<.001 and berr<.001,(k,serr,berr)
        solid_error=max(solid_error,serr)
        beam_error=max(beam_error,berr)
        x,y,z,txy=S[:,:4].T
        fields={'in_plane_tension_MPa':(x+y)*.5+np.hypot((x-y)*.5,txy),'layer_tension_MPa':z,
                'layer_tensile_strain':strain[:,2]}
        row=dict(native_set=int(k)+1,loadstep=int(state[k,0]),time_s=float(rt.time_values[k]),travel_mm=float(travel[len(records)]))
        if pull:
            row['cell_force_N']=float(fixed['cell_fx_N'][len(records)])
            assert np.isclose(fixed['time'][len(records)],rt.time_values[k],atol=1.e-9,rtol=0)
        for name,field in fields.items():
            full=field.reshape(-1,4)
            elem=int(np.argmax(full.min(axis=1)))
            finite_corner=4*elem+int(full[elem].argmin())
            row[name+'_elements_all_four_above']=int(np.count_nonzero(np.all(full>=PLA[name],axis=1)))
            for label,idx in (('all',int(field.argmax())),('away',int(away[np.argmax(field[away])])),('all_four',finite_corner)):
                key=label+'_'+name
                row[key]=float(field[idx])
                if key not in cross and field[idx]>=PLA[name]:
                    cross[key]=dict(last_below_mm=None if not records else records[-1]['travel_mm'],first_above_mm=row['travel_mm'],
                        native_set=row['native_set'],value=float(field[idx]),limit=PLA[name],element=int(solids[idx//4]),
                        node=int(flat_nodes[idx]),xyz_mm=xyz_s[idx].tolist(),distance_to_bearing_nodes_mm=float(distance[idx]))
        longitudinal=B[:,:,:,0]
        # For this circular section the centre and symmetric mean isolate the direct component.
        direct=longitudinal.mean(axis=2)
        assert np.allclose(direct,longitudinal[:,:,0],atol=.001,rtol=1e-5)
        row['four_screws']=dict(peak_fiber_tension_MPa=longitudinal.max(axis=(1,2)).tolist(),
              maximum_direct_MPa=direct.max(axis=1).tolist(),peak_abs_bending_MPa=abs(longitudinal-direct[:,:,None]).max(axis=(1,2)).tolist())
        if local:
            enum,data,_=rt.element_solution_data(int(k),'EMS')
            misc=np.stack([data[i] for i in np.searchsorted(enum,beams)])
            axial=misc[:,[0,13]]/misc[:,[12,25]]
            err=abs(axial-direct).max()/max(1.,abs(direct).max())
            assert err <.015,(k,err)
            axial_error=max(axial_error,float(err))
        records.append(row)
    if pull:
        description='All converged states through local lateral loading. Travel is the signed X displacement of the battery pilot. '
    else:
        description='Converged static load states through drawdown. '
    out=ROOT/'validation'/('pull_material' if pull else 'installation_material')/(case+'.json')
    write_json(out,dict(case=case,campaign=campaign,rst_sha256=hashes[job+'.rst'],input_sha256=hashes['model.inp'],
        contact_verdict_sha256=digest(next(p for p in proofs if p.is_file())),reference_properties=PLA,coupon_engineering_elongation_Z=.018,PLA_source=TDS,
        beam_section_reference=BEAM_REF,case_tets=len(solids),section_nodes_per_beam_end=25,constitutive_relative_errors=dict(
            PLA=float(solid_error),beam_axial=float(beam_error),**({'beam_direct_vs_native_force_area':axial_error} if local else {})),
        temperature_scope='Printed coupons under uniaxial tension. The material directions follow the layer orientation assumed for the case.',
        first_reference_crossings=cross,history=records,scope=description+'Stresses are material-frame '
        'FE corner or beam-section values. A circular elastic shank represents the screws. The collar nodes enforce a plane bearing footprint. '
        'The minimum distance for away results is 2 mm from the original coupled PLA bearing nodes.'))
    print(case,len(records),'states',cross,records[-1]['four_screws'],flush=True)
    return out


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case')
    p.add_argument('campaign',nargs='?',default='nov08_01')
    p.add_argument('--pull',action='store_true',help='Check the full local history against the battery pilot travel.')
    a=p.parse_args()
    run(a.case,a.campaign,pull=a.pull)
