"""Carry the six archived perfect-grip controls into each raised and flush enclosure comparison."""
import json

from audit_local import ROOT,read
from film_identity import verified,write_json
from local_equilibrium import movement_deck
from stage_local_jobs import seal


def stage():
    rt=ROOT/'.runtime'
    sources=read(ROOT/'validation/local_inputs.json')
    controls=sorted(k for k in sources if k.startswith('lateral_grip_'))
    assert len(controls)==6
    main='lateral_friction_locked'
    ref=rt/'local_inputs'/main
    base=ref/'run.dat'
    verified(base,sources[main]['files']['run.dat'])
    marker='SAVE,model,db'
    original_head,_=base.read_text().split(marker)
    reference_pilot=read(ref/'mesh.json')['pilot']
    manifest={}
    for position in ('stand3','flush'):
        flush=position=='flush'
        suffix='seatfaces1' if flush else 'pin1'
        registry=read(ROOT/'validation'/('local_seat_jobs.json' if flush else 'local_contact_retries.json'))
        for screw in ('nylon','aluminium'):
            template=f'{position}_{screw}_{main}_{suffix}'
            folder=rt/'inputs'/template
            original=read(folder/'local_job.json')
            verified(folder/'local_job.json',registry[template]['spec_sha256'])
            for name,sha in original['files'].items():
                verified(folder/name,sha)
            head,tail=(folder/'model.inp').read_text().split(marker)
            assert head.startswith(original_head)
            geometry=head[len(original_head):]
            target=f'TSHAP,PILO\nE,{reference_pilot}\n'
            assert geometry.count(target)==1
            end='finish\n/exit,nosave'
            native_prefix=movement_deck(ref,'pull',moving_screw_tops=flush).split(end)[0]
            moving=(folder/'moving.inp').read_text()
            assert moving.startswith(native_prefix)
            additional_readback=moving[len(native_prefix):]
            if flush:
                start=tail.index('TIME,3\nNSUBST,150,6000,75\n')
                finish=tail.index('TIME,4\nNSUBST,100,4000,20\n',start)
                install=tail[start:finish].replace('TIME,3\n','TIME,1\n')
                assert install.count('SOLVE')==1 and install.count(',UZ,3.0')==4
            for key in controls:
                source=rt/'local_inputs'/key
                for name in ('config.json','mesh.json','run.dat','post_corrected.dat'):
                    verified(source/name,sources[key]['files'][name])
                config=read(source/'config.json')
                mesh=read(source/'mesh.json')
                assert config['clamp'].startswith('perfect grip') and not config.get('bottom_pilots')
                pilot=mesh['pilot']
                prefix,load=(source/'run.dat').read_text().split(marker)
                assert load.count('TIME,1\nNSUBST,')==1
                case=f'{position}_{screw}_{key}_{suffix}'
                dest=rt/'inputs'/case
                dest.mkdir(exist_ok=True)
                post=(source/'post_corrected.dat').read_text()
                if flush:
                    # Hold the same lateral origin while seating. Other cell DOFs remain free.
                    load=load.replace('TIME,1\nNSUBST,', f'D,{pilot},UX,0\n'+install+
                         '*GET,PBOK,ACTIVE,0,SOLU,CNVG\n*IF,PBOK,NE,1,THEN\n/EXIT,NOSAVE\n*ENDIF\nTIME,2\nNSUBST,')
                    post=post.replace('RESUME,solved,db','RESUME,model,db',1)
                # A failed last increment can still leave a readable set numbered 999999.
                post=post.replace('SET,,,,,,,II\n','SET,,,,,,,II\n*GET,PBSS,ACTIVE,0,SET,SBST\n*IF,PBSS,EQ,999999,THEN\n*CYCLE\n*ENDIF\n')
                kinematics=movement_deck(source,'pull',moving_screw_tops=flush)
                assert kinematics.count(end)==1
                files={name:seal(dest/name,data.encode()) for name,data in (
                    ('model.inp',prefix+geometry.replace(target,f'TSHAP,PILO\nE,{pilot}\n')+marker+load),
                    ('local_post.inp',post),('moving.inp',kinematics.replace(end,additional_readback)))}
                spec=dict(case=case,source=key,cased=True,coupon=False,job='pull',cores=original['cores'],files=files,
                          screw_material=screw,case_template=template,absolute_search_mm=original['absolute_search_mm'])
                if flush:
                    spec.update(load_protocol='grip_install',installation_start_time=0.,installed_time=1.,end_time=2.,
                                top_travel_mm=3.,seat_pilots=original['seat_pilots'],cell_pull_mm=config['sign']*config['displacement_mm'],
                                nickel_faces_per_side=len(mesh['elements']))
                spec_hash=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
                manifest[case]=dict(source=key,reference_deck_sha256=sources[key]['files']['run.dat'],
                                    template=template,spec_sha256=spec_hash,input_sha256=files['model.inp'])
    write_json(ROOT/'validation/perfect_grip_cases.json',manifest)
    print(len(manifest),'perfect-grip comparisons staged')


if __name__=='__main__':
    stage()
