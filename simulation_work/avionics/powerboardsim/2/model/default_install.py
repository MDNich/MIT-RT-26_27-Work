"""Prepare flush installation on the original default-contact meshes with their eight fixed supports."""
import argparse
import re

import numpy as np

from audit_local import ROOT, read
from extend_board import board_feet, build
from film_identity import verified, write_json
from prepare_board_install import support_post, text_commands
from stage_local_jobs import seal
from surface_board import inventory, revised, seat_surfaces, verify_faces


def stage():
    rt = ROOT/'.runtime'
    native = read(ROOT/'validation/bare_inputs.json')
    old_cases = read(ROOT/'validation/cased_inputs.json')
    mesh_path = rt/'mesh/case_3.npz'
    with np.load(mesh_path) as geometry:
        faces, pairs = seat_surfaces(geometry)
    registry = {}
    # Keep every original support and contact definition preceding the Workbench solution options.
    for mesh in ('original','refined'):
        base = rt/'inputs'/('bare_'+mesh)/'model.inp'
        source_sha = verified(base,native['bare_'+mesh]['staged_sha256'])
        deck = base.read_bytes()
        prefix, options = re.split(rb'(?im)^/gst,on,on\s*$',deck, maxsplit=1)
        assert b'cmsel,s,_fixedsu\r\nd,all,all' in prefix.lower()
        assert b'modopt,lanb,20,1.,10000.' in options.lower()
        assert not re.search(rb'(?im)^\s*(?:sload|psmesh|stabilize),|^\s*et,\d+,179\b',prefix)
        footprint = board_feet(deck)
        static_steps = text_commands([
            'FINISH','/PREP7','ETCONTROL,OFF','SHPP,WARN','ALLSEL,ALL','FINISH','/SOLU',
            'ANTYPE,STATIC','NLGEOM,ON','NROPT,FULL','AUTOTS,ON','KBC,0','NEQIT,60',
            'CNTR,OUT,YES','CNCHECK,DMP','RESCONTROL,DEFINE,LAST','OUTRES,ERASE',
            'OUTRES,ALL,NONE','OUTRES,NSOL,ALL','OUTRES,RSOL,ALL','OUTRES,CONT,ALL',
            'OUTRES,STRS,ALL,CASEPLA','OUTRES,EPEL,ALL,CASEPLA',
            'TIME,1','NSUBST,1','SOLVE','TIME,2','NSUBST,30,2400,20,OFF',
            *[f'D,{960111+j},UZ,.003' for j in range(4)],'SOLVE','FINISH'])
        modal = text_commands(['/BATCH','/ASSIGN,RSTP,file,rst','/SOLU','ANTYPE,,RESTART,2,,PERTURB',
            'PERTURB,MODAL,,CURRENT,DZEROKEEP','SOLVE,ELFORM','MODOPT,LANB,20,1.,10000.',
            'LANBOPTION,ON,,ALT1','OUTRES,ERASE','OUTRES,ALL,NONE','OUTRES,NSOL,ALL',
            'MXPAND,20','SOLVE','FINISH','/EXIT,NOSAVE'])
        for material in ('nylon','aluminium'):
            previous = rt/'inputs'/f'flush_{material}_{mesh}'/'model.inp'
            verified(previous,old_cases[f'flush_{material}_{mesh}']['staged_sha256'])
            geom, feet = build(mesh_path,footprint,material,0.,retreat_mm=3.)
            head = prefix+revised(geom.encode(),faces)
            assert head.count(b'CE,NEXT,0,')==24
            assert b'RMODIF,853,6,-0.0006' in head and b'R,870,-.004' not in head
            branch=f'flush_{material}_default_{mesh}'
            d=rt/'default_install_v1'/branch
            d.mkdir(parents=True,exist_ok=True)
            stat=seal(d/'static.inp',head+static_steps+support_post()+text_commands(['FINISH','/EXIT,NOSAVE']))
            mode=seal(d/'modal.inp',modal)
            pre=seal(d/'pre.inp',head+text_commands(inventory()))
            if material=='nylon':
                trial=rt/f'default_{mesh}_initial_v1';trial.mkdir(exist_ok=True)
                assert seal(trial/'pre.inp',(d/'pre.inp').read_bytes())==pre
            registry[branch]=dict(default_mesh=mesh,screw=material,bare_deck_sha256=source_sha,
                earlier_overclosed_deck_sha256=old_cases[f'flush_{material}_{mesh}']['staged_sha256'],
                preflight_sha256=pre,static_sha256=stat,modal_sha256=mode,feet=feet)
    write_json(ROOT/'validation/default_install_inputs.json',dict(branches=registry,tab_pairs=pairs,
        scope='Prepared models for the historical unpreloaded support and contact conditions. The added case screws drive four tabs by 3 mm. Static equilibrium and a separately checked modal restart are required for each installed comparison.'))


def stage_jobs():
    rt=ROOT/'.runtime'
    candidates=read(ROOT/'validation/default_install_inputs.json')
    results={}
    post=(ROOT/'model/board_surface_post.inp').read_text()
    select=' set,,,,,,,ii\n'
    assert post.count(select)==2
    post=post.replace(select,select+' *get,kss,active,0,set,sbst\n *if,kss,eq,999999,then\n *cycle\n *endif\n')
    post=post.replace('/com,BOARD_FACE_POST_FINISHED',support_post().decode().replace('\r\n','\n')+'/com,BOARD_FACE_POST_FINISHED')
    for branch,model in candidates['branches'].items():
        for kind,source in [('static','static'),('modal20','modal')]:
            case=f'{branch}_{kind}'
            folder=rt/'inputs'/case;folder.mkdir(exist_ok=True)
            deck=rt/'default_install_v1'/branch/f'{source}.inp'
            sha=verified(deck,model[source+'_sha256'])
            assert seal(folder/'model.inp',deck.read_bytes())==sha
            spec=dict(case=case,kind=kind,mesh=model['default_mesh'],model_sha256=sha,
                      parent=None if kind=='static' else branch+'_static')
            if kind=='static':spec['post_sha256']=seal(folder/'board_surface_post.inp',post.encode())
            name=folder/'surface_job.json'
            import json
            vh=seal(name,(json.dumps(spec,indent=2)+'\n').encode())
            results[case]=dict(**spec,spec_sha256=vh)
    write_json(ROOT/'validation/default_contact_jobs.json',results)


def audit(mesh):
    src=read(ROOT/'validation/default_install_inputs.json')
    branch=f'flush_nylon_default_{mesh}'
    trial=ROOT/'.runtime'/f'default_{mesh}_initial_v1'
    rec=verify_faces(trial,src['branches'][branch]['preflight_sha256'],src['tab_pairs'])
    rec.update(default_mesh=mesh,branch=branch,bare_deck_sha256=src['branches'][branch]['bare_deck_sha256'])
    write_json(ROOT/'validation'/f'default_{mesh}_initial.json',rec)
    print(mesh,rec['cell_interface_gap_mm'],'mm initial cell/assembly clearance')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('stage','jobs','audit'))
    parser.add_argument('mesh',choices=('original','refined'),nargs='?')
    args=parser.parse_args()
    if args.action=='stage':stage()
    elif args.action=='jobs':stage_jobs()
    elif args.mesh:audit(args.mesh)
    else:parser.error('The audit requires a default mesh name')
