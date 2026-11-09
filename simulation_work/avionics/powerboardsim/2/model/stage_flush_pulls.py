"""Apply the checked flush installation and eight contact pairs to the archived pull variants."""
import json

from audit_local import ROOT,read
from film_identity import verified,write_json
from local_equilibrium import movement_deck
from stage_local_jobs import seal

SOURCES=('lateral_friction_locked_minus','lateral_friction_locked_fine','damage_cont_nominal')

def extra_kinematics(source):
    pilot=read(source/'mesh.json')['pilot']
    code=['allsel,all','set,last','*get,nsav,active,0,set,nset','*cfopen,damage_kinematics,csv','*vwrite',
          "('set,time,uy_mm,uz_mm,rotx,roty,rotz')",'*do,ik,1,nsav','set,,,,,,,ik',
          '*get,sb,active,0,set,sbst','*if,sb,eq,999999,then','*cycle','*endif','*get,tk,active,0,set,time']
    for var,item,direction in [('cy','u','y'),('cz','u','z'),('rx','rot','x'),('ry','rot','y'),('rz','rot','z')]:
        code.append(f'*get,{var},node,{pilot},{item},{direction}')
    return '\n'.join(code+['*vwrite,ik,tk,cy,cz,rx,ry,rz',"(F8.0,6(',',E19.11))",'*enddo','*cfclos','allsel,all',''])

def stage():
    root=ROOT/'.runtime';archives=read(ROOT/'validation/local_inputs.json')
    seat=read(ROOT/'validation/local_seat_jobs.json')
    original=root/'local_inputs/lateral_friction_locked'
    ref_text=(original/'run.dat').read_text()
    mark='SAVE,model,db'
    ref_head,ref_body=ref_text.split(mark)
    ref_pilot=read(original/'mesh.json')['pilot']
    result={}
    for material in ('nylon','aluminium'):
        key='flush_'+material+'_lateral_friction_locked_seatfaces1'
        template=root/'inputs'/key
        checked=read(template/'local_job.json')
        for n,v in checked['files'].items():verified(template/n,v)
        assert seat[key]['input_sha256']==checked['files']['model.inp']
        full_head,full_body=(template/'model.inp').read_text().split(mark)
        assert full_head.startswith(ref_head)
        geometry=full_head[len(ref_head):]
        anchor='TIME,3\nNSUBST,100,4000,20\n'
        start=full_body.index('TIME,3\nNSUBST,150,6000,75\n')
        end=full_body.index('TIME,4\nNSUBST,100,4000,20\n',start)
        install=full_body[start:end]
        assert ref_body.replace(anchor,install+anchor.replace('TIME,3','TIME,4'))==full_body
        moving_prefix=movement_deck(original,'pull',moving_screw_tops=True).split('finish\n/exit,nosave')[0]
        complete_readback=(template/'moving.inp').read_text()
        assert complete_readback.startswith(moving_prefix)
        readback=complete_readback[len(moving_prefix):]
        for source_name in SOURCES:
            source=root/'local_inputs'/source_name
            life=read(source/'config.json');mesh=read(source/'mesh.json')
            damage=source_name.startswith('damage_')
            post_name='post.dat' if damage else 'post_corrected.dat'
            for name in ('run.dat','mesh.json','config.json',post_name):
                verified(source/name,archives[source_name]['files'][name])
            head,body=(source/'run.dat').read_text().split(mark)
            pilot=mesh['pilot'];token=f'TSHAP,PILO\nE,{ref_pilot}\n'
            assert geometry.count(token)==1
            extra=geometry.replace(token,f'TSHAP,PILO\nE,{pilot}\n')
            if damage:
                token='*DO,JJ,1,32\n TIME,2+JJ*0.25'
                assert body.count(token)==1 and body.count('JJ+2')==3
                body=body.replace('JJ+2','JJ+3').replace(token,install+
                    '*GET,PBOK,ACTIVE,0,SOLU,CNVG\n*IF,PBOK,NE,1,THEN\n/EXIT,NOSAVE\n*ENDIF\n'
                    '*DO,JJ,1,32\n TIME,3+JJ*0.25')
            else:
                assert body.count(anchor)==1
                body=body.replace(anchor,install+anchor.replace('TIME,3','TIME,4'))
            case=f'flush_{material}_{source_name}_seatfaces1'
            dest=root/'inputs'/case;dest.mkdir(exist_ok=True)
            if source_name.endswith('_minus'):
                original_loaded=(template/'model.inp').read_text().split(f'D,{pilot},UX,0.5\nSOLVE')[0]
                altered=(head+extra+mark+body).split(f'D,{pilot},UX,-0.5\nSOLVE')[0]
                # The archived reverse deck spells the same four washer constants 0.1 instead of .1.
                assert altered.count(',,,0.1,.01,,.2')==4
                assert original_loaded==altered.replace(',,,0.1,.01,,.2',',,,.1,.01,,.2'), 'Reverse control changed before the pull command'
            post=(source/post_name).read_text()
            if damage:
                post=post.replace('*IF,LS,LT,3,THEN','*IF,LS,LT,4,THEN')
            else:
                post=post.replace('RESUME,solved,db','RESUME,model,db',1)
                post=post.replace('SET,,,,,,,II\n','SET,,,,,,,II\n*GET,ESUB,ACTIVE,0,SET,SBST\n*IF,ESUB,EQ,999999,THEN\n*CYCLE\n*ENDIF\n')
            job='tear' if damage else 'pull'
            base_read=movement_deck(source,job,moving_screw_tops=True)
            tail='finish\n/exit,nosave'
            assert base_read.count(tail)==1 and readback.count(tail)==1
            moving=base_read.replace(tail,readback.replace(tail,(extra_kinematics(source) if damage else '')+tail))
            files={n:seal(dest/n,t.encode()) for n,t in [('model.inp',head+extra+mark+body),('moving.inp',moving),('local_post.inp',post)]}
            spec=dict(checked,case=case,source=source_name,job=job,files=files,
                      cell_pull_mm=life['sign']*life['displacement_mm'],end_time=life['end_time']+1.,
                      original_run_sha256=archives[source_name]['files']['run.dat'],
                      nickel_faces_per_side=len(mesh['elements']),nominal_geometry_source=key)
            spec_hash=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
            result[case]=dict(spec_sha256=spec_hash,input_sha256=files['model.inp'],source=source_name)
    write_json(ROOT/'validation/flush_pull_variants.json',result)
if __name__=='__main__':stage()
