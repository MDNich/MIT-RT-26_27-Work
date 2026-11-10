"""Trace each tab's lateral load into the screw, spacer and printed bearing on the original tied mounts."""
import argparse
import re
from pathlib import Path

import numpy as np
from ansys.mapdl import reader

from audit_local import ROOT,read,table
from film_identity import digest,verified,write_json
from local_bearing_load import bearing_readback
from local_equilibrium import positions,SCREW_PILOTS
from screw_vibration import section,screw_elements
from stage_snug_fit import AUDIT,INPUTS
from tab_seating import point_fields,read_point_file


def reactions(rst,deck,tetrahedra,stations):
    modulus=float(next(line.strip().split(',')[-1] for line in deck.splitlines()
                       if line.upper().startswith('MP,EX,851,')))
    assert modulus in (3000.,69000.)
    ring_radius=3.75
    bearing=bearing_readback(rst,deck,tetrahedra,ring_radius)
    beams,beam_indices=screw_elements(rst)
    grid=rst.grid.cell_data
    seats=np.sort(grid['ansys_elem_num'][grid['ansys_etype']==854])
    assert len(seats)==4
    out=[]
    for row in stations:
        k=row['native_set']-1
        if not row['within_screens']:
            break
        tabs=bearing(k+1)
        stress=section(rst,k,beam_indices,'ENS')
        strain=section(rst,k,beam_indices,'EEL')
        assert np.allclose(stress,modulus*strain,atol=1e-4,rtol=2e-6)
        mean=stress.mean(axis=2)
        assert np.allclose(mean,stress[:,:,0],atol=1e-4,rtol=1e-5)
        ids,forces,labels=rst.element_solution_data(k,'ENF')
        n,native,_=rst.element_solution_data(k,'EMS')
        RF,nodes,dofs=rst.nodal_reaction_forces(k)
        for i,(tab,b,s,pilot) in enumerate(zip(tabs,beams,seats,SCREW_PILOTS,strict=True)):
            bi,si=positions(ids,[b,s]);assert list(labels[bi])==[tab['pilot'],pilot]
            beam=forces[bi].reshape(-1,6)[:2,:3]
            spacer=forces[si].reshape(2,3) if forces[si] is not None else np.zeros((2,3))
            hit=(nodes==pilot)&(dofs<=3)
            reaction=np.bincount(dofs[hit]-1,weights=RF[hit],minlength=3)
            assert np.allclose(-beam[1]-spacer[1],reaction,atol=.002,rtol=1e-5)
            assert np.allclose(tab['force_XYZ_N'],reaction,atol=.002,rtol=1e-5)
            smisc=native[positions(n,[b])[0]]
            axial=smisc[[0,13]]/smisc[[12,25]]
            assert np.max(abs(mean[i]-axial))<.015*max(1.,abs(mean[i]).max())
            end,point=np.unravel_index(np.argmax(stress[i]),(2,25))
            total=float(stress[i,end,point]);direct=float(mean[i,end])
            tab.update(fixed_pilot=pilot,lateral_resistance_N=-float(reaction[0]),
                       board_support_RF_N=reaction.tolist(),shank_end_force_on_tab_N=beam[0].tolist(),
                       spacer_end_force_on_tab_N=spacer[0].tolist(),
                       peak_shank_fibre_MPa=total,direct_stress_at_peak_MPa=direct,
                       bending_stress_at_peak_MPa=total-direct,peak_shank_end='IJ'[end])
        assert abs(max(t['peak_shank_fibre_MPa'] for t in tabs)-row['screw_peak_fibre_MPa'])<1e-5
        assert abs(sum(t['lateral_resistance_N'] for t in tabs)-row['screw_support_resistance_N'])<.005
        out.append(dict(native_set=k+1,cell_travel_mm=row['travel_mm'],cell_force_N=row['cell_force_N'],tabs=tabs))
    assert out
    return out


def ring_nodes(deck):
    rings={n-1:np.array([int(i) for i in re.findall(r'(?im)^CERIG,'+str(n-1)+r',(\d+),UXYZ$',deck)])
           for n in SCREW_PILOTS}
    nodes=sorted({2481,*rings,*SCREW_PILOTS,*[int(n) for ring in rings.values() for n in ring]})
    return rings,nodes


def tab_motion(raw,states,rings,nodes,u):
    assert len(states)==len(u)
    assert np.max(abs(u[:,positions(nodes,SCREW_PILOTS)]))<1e-7
    assert np.max(abs(u[:,positions(nodes,[2481])[0],0]-[r['cell_travel_mm'] for r in states]))<1e-7
    largest=0.
    for i,(pilot,ring) in enumerate(rings.items()):
        center=raw.mesh.nodes[positions(raw.mesh.nnum,[pilot])[0]]
        arms=raw.mesh.nodes[positions(raw.mesh.nnum,ring)]-center
        # CERIG imposes u(node)=u(pilot)+theta cross reference arm.
        design=np.zeros((len(ring),3,6));design[:,:,:3]=np.eye(3)
        for axis in range(3):
            design[:,:,3+axis]=np.cross(np.eye(3)[axis],arms)
        design=design.reshape(-1,6)
        field=u[:,positions(nodes,ring)].reshape(len(u),-1)
        fit,_,rank,_=np.linalg.lstsq(design,field.T,rcond=None)
        assert rank==6
        residual=float(np.max(abs((design@fit).T-field)))
        pilot_error=float(np.max(abs(fit[:3].T-u[:,positions(nodes,[pilot])[0]])))
        assert residual<1e-6 and pilot_error<1e-6
        largest=max(largest,residual,pilot_error)
        for row,components in zip(states,fit.T,strict=True):
            tab=row['tabs'][i];assert tab['pilot']==pilot and tab['bearing_nodes']==len(ring)
            tab['translation_XYZ_mm']=components[:3].tolist()
            tab['CERIG_rotation_XYZ_rad']=components[3:].tolist()
    return largest


def checkpoint(folder):
    capture=read(folder/'capture.json')
    p=AUDIT/f"{capture['case']}_{folder.name}_checkpoint.json"
    record=read(p);case=record['case'];sha=record['rst_sha256']
    verified(folder/'pull.rst',sha);verified(INPUTS/case/'model.inp',record['input_sha256'])
    rst=reader.read_binary(folder/'pull.rst');deck=(INPUTS/case/'model.inp').read_text()
    states=reactions(rst,deck,record['case_tetrahedra'],record['states'])
    rings,nodes=ring_nodes(deck);sets=[r['native_set'] for r in record['states']]
    out=folder/'dpf_bearings'
    field,_=read_point_file(folder/'pull.rst',out,sha,sets,nodes)
    err=tab_motion(rst,states,rings,np.array(nodes),field[:len(states)])
    force_file=folder/'dpf_forces/forces.json'
    verified(force_file,record['equilibrium']['DPF_reaction_sha256'])
    dpf=read(force_file);assert dpf['source_sha256']==sha
    for row in states:
        actual=dpf['sets'][row['native_set']-1]
        assert actual['native_set']==row['native_set']
        for tab in row['tabs']:
            assert np.allclose(actual['forces_N'].get(str(tab['fixed_pilot']),[0.]*3),
                               tab['board_support_RF_N'],atol=1.e-6,rtol=0)
    result=dict(case=case,rst_sha256=sha,checkpoint_sha256=digest(p),bearing_radius_mm=3.75,
                states=states,bearing_U_sha256=digest(out/'displacements.bin'),bearing_request_sha256=digest(out/'request.json'),
                maximum_CERIG_rigid_field_or_pilot_error_mm=err,scope='Signed solid nodal forces and moments on the tied footprints. Axial offset and '
                'minimum opposing force are reference-configuration quantities. The beam end J is at the '
                'fixed PCB support. The shanks and compression-only spacers have no imposed assembly torque.')
    write_json(AUDIT/f'{case}_{folder.name}_mount_reactions.json',result)
    print('Checked',len(states),'stations, four mount load paths at each.')


def archive(case,comparison,folder,sha):
    """Recover the supported tied-mount path and test all overlapping stationary copies."""
    material_file=ROOT/'validation/pull_material'/(case+'.json')
    material=read(material_file)
    assert material['rst_sha256']==comparison['native_rst_sha256']==sha['pull.rst']
    assert material['input_sha256']==comparison['input_sha256']==sha['model.inp']
    verified(folder/'model.inp',sha['model.inp']);verified(folder/'pull.rst',sha['pull.rst'])
    balance=table(ROOT/'.runtime/post'/material['campaign']/case/'whole_fixture_balance.csv')
    if 'accepted_equilibrium_prefix' in comparison:
        balance=balance[:comparison['accepted_equilibrium_prefix']]
    assert len(balance)==len(material['history'])
    last=comparison['equal_travel']
    supported=last['cased']['set'] if last else 0
    last_set=comparison.get('parent_screen_last_set',supported)
    checks=[];source=[]
    for m,br in zip(material['history'],balance,strict=True):
        k=m['native_set']
        assert br['native_set']==k and abs(br['ux_mm']-m['travel_mm'])<1e-7
        if k>last_set:
            break
        source.append(dict(native_set=k,within_screens=True,travel_mm=m['travel_mm'],
                           cell_force_N=br['cell_fx_N'],screw_support_resistance_N=-br['screw_support_N_x'],
                           screw_peak_fibre_MPa=max(m['four_screws']['peak_fiber_tension_MPa'])))
    states=[]
    if source:
        raw=reader.read_binary(folder/'pull.rst')
        deck=(folder/'model.inp').read_text()
        states=reactions(raw,deck,material['case_tets'],source)
        rings,points=ring_nodes(deck)
        nodes,field=point_fields(raw,[r['native_set'] for r in states],points,field_directory='tab_bearing_motion')
        tab_motion(raw,states,rings,nodes,field)
    for path in sorted(AUDIT.glob(case+'_*_mount_reactions.json')):
        cp=read(path)
        assert cp['case']==case and cp['checkpoint_sha256'] in {r['checkpoint_sha256'] for r in comparison['verified_checkpoints']}
        assert 0<len(cp['states'])<=len(states)
        for saved,full in zip(cp['states'],states):
            assert saved['native_set']==full['native_set']
            for a,b in zip(saved['tabs'],full['tabs'],strict=True):
                assert a['pilot']==b['pilot'] and a['peak_shank_end']==b['peak_shank_end']
                for f in ('force_XYZ_N','moment_XYZ_Nmm','direct_stress_at_peak_MPa','peak_shank_fibre_MPa',
                          'minimum_opposing_load_N','lateral_resistance_N','spacer_end_force_on_tab_N','translation_XYZ_mm','CERIG_rotation_XYZ_rad'):
                    np.testing.assert_allclose(a[f],b[f],atol=1e-6,rtol=1e-6)
        checks.append(dict(source=path.name,sha256=digest(path),stations=len(cp['states'])))
    out=AUDIT/f'{case}_bearing_history.json'
    write_json(out,dict(case=case,rst_sha256=sha['pull.rst'],material_sha256=digest(material_file),
                        checkpoint_reconciliations=checks,states=states,bearing_radius_mm=3.75,last_comparison_set=supported))
    return out


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('folder',type=Path);checkpoint(parser.parse_args().folder)
