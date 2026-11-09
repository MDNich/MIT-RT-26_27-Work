"""Stage whole-board drawdown and step-3 restarts under new IDs only after native contact controls."""
import sys
from audit_local import ROOT,read
from film_identity import digest,write_json
from stage_local_jobs import seal

def stage():
    v=ROOT/'validation';rt=ROOT/'.runtime'
    geom=read(v/'board_surface_initial.json');a=read(v/'board_surface_candidates.json')['candidates']
    checks=['board_surface_initial','board_actuator_control','seat_surface_control']
    controls={k:digest(v/(k+'.json')) for k in checks}
    assert all(abs(row['initial_gap_mm']-3)<1e-4 for row in geom['pairs'].values()) and len(geom['pairs'])==4
    specs={}
    for m in ('nylon','aluminium'):
        branch='flush_'+m+'_surf1';c=a[m]
        for kind in ('static','basis','modal20'):
            case=branch+'_'+kind;dest=rt/'inputs'/case;dest.mkdir(exist_ok=True)
            src=(rt/'board_surface_v1'/m/'static.inp' if kind=='static' else rt/'board_install_v1'/m/(kind+'.inp'))
            sha=c['static_sha256'] if kind=='static' else c['restart_sha256'][kind]
            assert digest(src)==sha
            assert seal(dest/'model.inp',src.read_bytes())==sha
            spec=dict(case=case,model_sha256=sha,controls=controls,kind=kind,
                      parent=None if kind=='static' else branch+'_static')
            if kind=='static':
                spec['post_sha256']=seal(dest/'board_surface_post.inp',(ROOT/'model/board_surface_post.inp').read_bytes())
            p=dest/'surface_job.json'
            if p.exists():assert read(p)==spec
            else:write_json(p,spec)
            specs[case]=dict(spec_sha256=digest(p),**spec)
    write_json(v/'board_surface_jobs.json',specs)
if __name__=='__main__':stage()
