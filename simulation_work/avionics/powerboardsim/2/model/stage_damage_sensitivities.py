"""Place the archived nickel law, mesh and numerical controls into the four existing local case fixtures."""
import json
import re

from audit_local import ROOT,read
from film_identity import verified,write_json
from local_equilibrium import movement_deck
from stage_flush_pulls import extra_kinematics
from stage_local_jobs import seal

NOMINAL='damage_cont_nominal'
MARK='SAVE,model,db'
END='finish\n/exit,nosave'
RT=ROOT/'.runtime'


def template(case,catalog):
    folder=RT/'inputs'/case
    spec_path=folder/'local_job.json'
    verified(spec_path,catalog[case]['spec_sha256'])
    spec=read(spec_path)
    assert spec['case']==case and spec['files']['model.inp']==catalog[case]['input_sha256']
    for name,expected in spec['files'].items():
        verified(folder/name,expected)
    return folder,spec


def flush_loading(body,installation):
    # Preserve the archive's 0.25 mm pull increments and force-control tolerance.
    pattern=r'(?m)^(CNVTOL,F,,5e-05,,1\n)?(\*DO,JJ,1,(?:2|32)\n TIME,)2(\+JJ\*0\.25)$'
    result,count=re.subn(pattern,lambda m:installation+(m[1] or '')+m[2]+'3'+m[3],body)
    assert count==1 and result.count('JJ+2')==3
    return result.replace('JJ+2','JJ+3')


def stage():
    sources=read(ROOT/'validation/local_inputs.json')
    targets=[s for s in sources if s.startswith('damage_cont')]
    assert len(targets)==12 and NOMINAL in targets
    for name in targets:
        for f in ('config.json','run.dat','mesh.json','post.dat'):
            verified(RT/'local_inputs'/name/f,sources[name]['files'][f])
    archive=RT/'local_inputs'/NOMINAL
    controls={}
    for position in ('stand3','flush'):
        flush=position=='flush'
        suffix='seatfaces1' if flush else 'pin1'
        existing=read(ROOT/'validation'/('flush_pull_variants.json' if flush else 'local_contact_retries.json'))
        geometry_registry=dict(existing)
        if flush:geometry_registry.update(read(ROOT/'validation/local_seat_jobs.json'))
        for screw in ('nylon','aluminium'):
            tag=f'{position}_{screw}_'
            nominal=tag+NOMINAL+'_'+suffix
            folder,original=template(nominal,existing)
            sealed_body=(folder/'model.inp').read_text().split(MARK)[1]
            installation=''
            if flush:
                a=sealed_body.index('TIME,3\nNSUBST,150,6000,75\n')
                b=sealed_body.index('*DO,JJ,1,32\n TIME,3+JJ*0.25',a)
                installation=sealed_body[a:b]
            prefix=movement_deck(archive,'tear',moving_screw_tops=flush).split(END)[0]
            motion=(folder/'moving.inp').read_text()
            assert motion.startswith(prefix)
            readback=motion[len(prefix):]
            for name in targets:
                source=RT/'local_inputs'/name
                config=read(source/'config.json')
                size='_fine' if config['mesh_factor']==2 else ''
                assert config['mesh_factor'] in (1,2)
                recipe='lateral_friction_locked'+size
                original_lateral=RT/'local_inputs'/recipe
                verified(original_lateral/'run.dat',sources[recipe]['files']['run.dat'])
                verified(original_lateral/'mesh.json',sources[recipe]['files']['mesh.json'])
                assert sources[name]['files']['mesh.json']==sources[recipe]['files']['mesh.json']
                geometry_case=tag+recipe+'_'+suffix
                physical,physical_spec=template(geometry_case,geometry_registry)
                base_head=(original_lateral/'run.dat').read_text().split(MARK)[0]
                extended=(physical/'model.inp').read_text().split(MARK)[0]
                assert extended.startswith(base_head)
                geometry=extended[len(base_head):]
                assert geometry.count('ET,850,SOLID187')==1
                bare_head,body=(source/'run.dat').read_text().split(MARK)
                post=(source/'post.dat').read_text()
                tail=readback
                if flush:
                    body=flush_loading(body,installation)
                    assert post.count('*IF,LS,LT,3,THEN')>=1
                    post=post.replace('*IF,LS,LT,3,THEN','*IF,LS,LT,4,THEN')
                    assert tail.count(extra_kinematics(archive))==1
                    tail=tail.replace(extra_kinematics(archive),extra_kinematics(source))
                moving=movement_deck(source,'tear',moving_screw_tops=flush).split(END)[0]+tail
                model=bare_head+geometry+MARK+body
                texts={'model.inp':model,'moving.inp':moving,'local_post.inp':post}
                if name==NOMINAL:
                    for file,data in texts.items():
                        assert (folder/file).read_text()==data,(nominal,file)
                    continue
                case=tag+name+'_'+suffix
                dest=RT/'inputs'/case
                dest.mkdir(exist_ok=True)
                files={file:seal(dest/file,data.encode()) for file,data in texts.items()}
                spec=dict(original,case=case,source=name,files=files,cores=config.get('solver_ranks',4),
                          sensitivity_reference=nominal,original_run_sha256=sources[name]['files']['run.dat'])
                # source_attempt belongs to the nominal contact-search retry, not to this new source.
                spec.pop('source_attempt',None)
                if flush:
                    spec.update(end_time=config['end_time']+1.,cell_pull_mm=config['sign']*config['displacement_mm'],
                        nickel_faces_per_side=len(read(source/'mesh.json')['elements']),nominal_geometry_source=geometry_case)
                spec_sha=seal(dest/'local_job.json',(json.dumps(spec,indent=2)+'\n').encode())
                controls[case]=dict(source=name,original_run_sha256=spec['original_run_sha256'],spec_sha256=spec_sha,
                       input_sha256=files['model.inp'],nominal=nominal,nominal_spec_sha256=existing[nominal]['spec_sha256'],
                       geometry_case=geometry_case,geometry_input_sha256=physical_spec['files']['model.inp'],
                       archive_mesh_sha256=sources[name]['files']['mesh.json'])
    assert len(controls)==44
    write_json(ROOT/'validation/damage_variant_inputs.json',controls)
    print('Matched all four existing nominal decks and readbacks. Sealed',len(controls),'additional fixtures.')


if __name__=='__main__':
    stage()
