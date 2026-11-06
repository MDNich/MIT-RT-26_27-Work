"""Prepare or verify a sealed native transient coupon. This script never launches MAPDL."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import tempfile

import numpy as np
from scipy.optimize import brentq
from scipy.special import j0, y0

from ops import ROOT, atomic, disks
from prepare_model import create_mesh

PACKAGE = ROOT/'configs/native_verification/annular_mode64_smp10'
PARENT = ROOT/'configs/sustainer_al_pulse7_midpoint_joint320_geom005_smp10.json'


def inputs():
    cfg = json.loads(PARENT.read_text())
    assert cfg['ranks'] == 10 and cfg['parallel_mode'] == 'smp'
    assert cfg['mesh_measure_convention'] == 'straight_sided_hex'
    cfg['geometry'].update(inner_radius_m=.04,phenolic_outer_radius_m=.045,outer_radius_m=.05,
                           phenolic_thickness_m=.005,aluminium_thickness_m=.005,
                           phenolic_radial_rows=32,aluminium_radial_rows=32)
    _, nodes, elements = create_mesh(cfg)
    r0,r1,k,rho,cp = .04,.05,.6,1250.,1000.
    def shape(z,r):
        return j0(z*r)*y0(z*r0)-y0(z*r)*j0(z*r0)
    wave = brentq(lambda z: shape(z,r1),200.,400.)
    endpoint = rho*cp/(wave**2*k)
    radii = np.array([math.hypot(x,z) for _,x,_,z in nodes])
    phi = shape(wave,radii)
    amp = 100.*phi/phi[np.argmax(abs(phi))]
    boundary = np.isclose(radii,r0,rtol=0,atol=1e-12) | np.isclose(radii,r1,rtol=0,atol=1e-12)
    amp[boundary] = 0.
    pre = ['! Iris transient annular conduction verification. Use -smp -np 10.',
           '/CLEAR,START','/PREP7','ET,1,SOLID278','MP,KXX,1,0.6','MP,C,1,1000','MP,DENS,1,1250',
           'TYPE,1','MAT,1']
    pre += [f'N,{n},{x:.16g},{y:.16g},{z:.16g}' for n,x,y,z in nodes]
    pre += ['EN,'+','.join(map(str,[eid,*ids])) for eid,_,ids in elements]
    pre += ['FINISH','/SOLU','ANTYPE,TRANS','TRNOPT,FULL','AUTOTS,OFF','KBC,1','TUNIF,22']
    pre += [f'IC,{node[0]},TEMP,{22.+a:.15g}' for node,a in zip(nodes,amp)]
    pre += [f'D,{node[0]},TEMP,22' for node,at_face in zip(nodes,boundary) if at_face]
    pre += [f'TIME,{endpoint:.16g}','NSUBST,256,256,256','OUTRES,ALL,LAST','SOLVE','FINISH','/POST1',
            'SET,LAST','*GET,MODETIME,ACTIVE,0,SET,TIME','*CFOPEN,mode_time,txt','*VWRITE,MODETIME',
            '(E24.16)','*CFCLOSE','*CFOPEN,mode_end,txt',f'*DO,MODEID,1,{len(nodes)}',
            '*GET,MODET,NODE,MODEID,TEMP','*VWRITE,MODEID,MODET','(F10.0,1X,E24.16)','*ENDDO',
            '*CFCLOSE','FINISH','/COM,IRIS_ANNULAR_MODE_END','/EXIT,NOSAVE']
    data = {'description':'Homogeneous inert annular sector, first radial Dirichlet eigenmode. '
                        'Independent analytic temperature reference; manufactured model verification only.',
            'geometry':cfg['geometry'],'nodes':len(nodes),'elements':len(elements),'fixed_substeps':256,
            'solver':'MAPDL 2026 R1, SOLID278, shared memory, 10 cores','job':'irmode64',
            'terminal_time_s':endpoint,'wavenumber_per_m':wave,'max_analytic_error_target_K':.25,
            'parent_config_sha256':hashlib.sha256(PARENT.read_bytes()).hexdigest(),
            'candidate_conduction_test_sha256':hashlib.sha256((ROOT/'model/check_moving_surface_conduction.py').read_bytes()).hexdigest(),
            'expected_final_C':{str(n[0]):float(22.+a/math.e) for n,a in zip(nodes,amp)}}
    return '\n'.join(pre)+'\n',data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['prepare','verify-input'])
    args = parser.parse_args()
    disks()
    deck, expected = inputs()
    name = 'annular_mode.inp'
    sha = hashlib.sha256(deck.encode('ascii')).hexdigest()
    expected.update(input_sha256=sha,prepared_only=True)
    if args.action == 'prepare':
        if PACKAGE.exists():
            raise FileExistsError('Existing inputs are sealed')
        PACKAGE.parent.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=PACKAGE.parent) as temporary:
            stage = Path(temporary)/'new'
            stage.mkdir()
            (stage/name).write_text(deck,encoding='ascii')
            atomic(stage/'expected.json',expected)
            stage.rename(PACKAGE)
    assert (PACKAGE/name).read_bytes() == deck.encode('ascii')
    assert json.loads((PACKAGE/'expected.json').read_text()) == expected
    print(f'Sealed input verified: {expected["nodes"]} nodes, {expected["elements"]} elements, SHA256 {sha}')


if __name__ == '__main__':
    main()
