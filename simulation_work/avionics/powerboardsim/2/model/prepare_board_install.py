"""Prepare candidate flush whole-board decks in a separate tree. No production queue release."""
import json
import numpy as np
from extend_board import ROOT,board_feet,build
from stage_local_jobs import digest,seal


def text_commands(lines):
    return ('\r\n'.join(lines)+'\r\n').encode()


def support_post():
    lines=['/POST1','ALLSEL,ALL','RSYS,0','SET,LAST','*GET,NSAV,ACTIVE,0,SET,NSET',
           '*CFOPEN,board_drives,csv','*VWRITE',"('set,time_s,foot,board_z_m,head_z_m,travel_m,drive_N,top_rot,tab_rot')",
           '*DO,IK,1,NSAV','SET,,,,,,,IK','*GET,ISB,ACTIVE,0,SET,SBST','*IF,ISB,EQ,999999,THEN',
           '*CYCLE','*ENDIF','*GET,TK,ACTIVE,0,SET,TIME','*DO,JJ,0,3','BP=960101+JJ','ACTN=960111+JJ',
           'UP=950002+2*JJ','DN=UP-1','*GET,BZ,NODE,BP,U,Z','*GET,HZ,NODE,UP,U,Z','*GET,AZ,NODE,ACTN,U,Z',
           '*GET,AF,NODE,ACTN,RF,FZ']
    for node,prefix in [('UP','TH'),('DN','TL')]:
        lines += [f'*GET,{prefix}{a},NODE,{node},ROT,{a}' for a in 'XYZ']
        lines.append(f'{prefix}=SQRT({prefix}X**2+{prefix}Y**2+{prefix}Z**2)')
    return text_commands(lines+['*VWRITE,IK,TK,JJ,BZ,HZ,AZ,AF,TH,TL',"(F6.0,',',E16.9,',',F3.0,6(',',E16.9))",
                                '*ENDDO','*ENDDO','*CFCLOS','ALLSEL,ALL'])


def stage():
    ref=ROOT/'.runtime/inputs/bare_static/model.inp'
    data=ref.read_bytes();feet=board_feet(data);mesh=ROOT/'.runtime/mesh/case_3.npz'
    anchor=b'/gst,on,on';assert data.lower().count(anchor)==1;at=data.lower().index(anchor)
    marker=b'/com,*************** FINISHED SOLVE FOR LS 2 *************\r\nfini'
    assert data.count(marker)==1
    records={}
    for material in ['nylon','aluminium']:
        model,feet_new=build(mesh,feet,material,0.,retreat_mm=3.)
        old,feet_base=build(mesh,feet,material,0.)
        historic=ROOT/f'.runtime/inputs/flush_{material}_static/model.inp'
        assert digest(data[:at]+old.encode()+data[at:])==digest(historic.read_bytes())
        for f0,f1 in zip(feet_base,feet_new,strict=True):
            assert np.isclose(f0['grip_mm'],f1['grip_mm'],rtol=0,atol=1e-8) and f0['bearing_nodes']==f1['bearing_nodes']
        assert model.count('CE,NEXT,0,')==24 and model.count('RMODIF,853,6,-0.0006')==1
        head=data[:at]+model.encode()
        main=head+data[at:]
        seat=text_commands(['! Advance four short grips relative to their flexible PCB feet after the original six bolts lock.',
            'ALLSEL,ALL','KBC,0','AUTOTS,ON','TIME,3','NSUBST,30,2400,20,OFF','NEQIT,60',
            *[f'D,{960111+i},UZ,0.003' for i in range(4)],'SOLVE','! End installed load step.'])
        main=main.replace(marker,marker[:-4]+seat+b'fini')
        pb=b'*DO,PBSTEP,1,2';assert main.count(pb)==1
        main=main.replace(pb,b'*DO,PBSTEP,1,3')
        post=b'! ****** End   Command Snippet ******\r\nxmlo,ENCODING';assert main.count(post)==1
        main=main.replace(post,support_post()+post)
        dest=ROOT/f'.runtime/board_install_v1/{material}';dest.mkdir(exist_ok=True,parents=True)
        static=seal(dest/'static.inp',main)
        rest={}
        for key in ['basis','modal20']:
            modal=(ROOT/f'.runtime/inputs/bare_{key}/model.inp').read_bytes()
            tag=b'antype,,restart,,,perturbation'
            assert modal.lower().count(tag)==1 and b'current,dzerokeep' in modal.lower()
            modal=modal.replace(tag,b'antype,,restart,3,,perturbation')
            rest[key]=seal(dest/(key+'.inp'),modal)
        inv=text_commands(['FINISH','/PREP7','/GOPR','ALLSEL,ALL','*CFOPEN,board_inventory,csv','*VWRITE',
                           "('type,elements')",'*DO,JT,850,856','ESEL,S,TYPE,,JT','*GET,NN,ELEM,0,COUNT',
                            '*VWRITE,JT,NN',"(F5.0,',',F10.0)",'*ENDDO','*CFCLOS','ALLSEL,ALL','FINISH',
                            '/SOLU','ANTYPE,STATIC','NLGEOM,ON','CNCHECK,DETAIL,853,853',
                            '/COM,BOARD_APPROACH_INITIAL_CHECK_DONE','FINISH','/EXIT,NOSAVE'])
        preflight=seal(dest/'pre.inp',head+inv)
        records[material]=dict(static_sha256=static,preflight_sha256=preflight,modal_restart_sha256=rest,
            initial_board_to_tab_separation_mm=3.,imposed_relative_travel_mm=3.,feet=feet_new,
            nominal_maximum_step_travel_mm=.15,scope='Candidate only. Native constraint control, whole-board preflight, seating and material scope must be checked before use.')
    (ROOT/'validation/board_install_candidates.json').write_text(json.dumps(records,indent=2)+'\n')


if __name__=='__main__':stage()
