"""Validate actual MAPDL SFELIST output; no solver invocation."""
from pathlib import Path
import argparse
import json
import re
from coupler import load,save

ROOT=Path(__file__).resolve().parent


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--log',type=Path,required=True); args=ap.parse_args()
    log=args.log.read_text(errors='replace')
    assert 'ITER4_PREFLIGHT_COMPLETE_NO_SOLVE' in log,'Preflight did not complete'
    assert '*** ERROR ***' not in log,'MAPDL reported errors'
    text=(ROOT/'validation/face_listing.txt').read_text(errors='replace')
    assert '*** ERROR ***' not in text,'MAPDL face-listing errors'
    mesh=load(ROOT/'mesh_map.json')
    reports=[]
    for i,row in enumerate(mesh['rows']):
        match=re.search(rf'ITER4_FACE_CASE_{i:02d}_BEGIN(.*?)ITER4_FACE_CASE_{i:02d}_END',text,re.S)
        assert match,('Missing face case',i)
        block=match[1]
        assert re.search(r'LIVE_HOT_ELEMENTS=\s*200\.',block),('Wrong live face count',i)
        # Native 2026 R1 SFELIST: element, face, node, film, bulk;
        # the following three nodes omit element and face columns.
        loads={}; active=None
        for line in block.splitlines():
            tokens=line.split()
            if len(tokens)==5 and all(t.isdigit() for t in tokens[:3]):
                active=(int(tokens[0]),int(tokens[1]))
                assert active not in loads,('Duplicate face',i,active)
                loads[active]=[(int(tokens[2]),float(tokens[3]),float(tokens[4]))]
            elif active is not None and len(tokens)==3 and tokens[0].isdigit():
                try: values=(int(tokens[0]),float(tokens[1]),float(tokens[2]))
                except ValueError: continue
                loads[active].append(values)
        found=set(loads)
        expected={(f['element'],f['face']) for f in row}
        assert found==expected,('SFELIST mapping mismatch',i,len(found),len(expected))
        cfg=load(ROOT/'config.json')
        for f in row:
            values=loads[f['element'],f['face']]
            assert len(values)==4 and {v[0] for v in values}==set(f['nodes']),('Face nodes',i,f)
            assert all(abs(v[1]-cfg['heating']['h0_W_m2_K'])<1e-5 and
                       abs(v[2]-cfg['heating']['gas_temperature_C'])<1e-5 for v in values),('Face load values',i,f)
        reports.append(dict(row=i,live_elements=200,listed_faces=len(found)))
    import hashlib
    save(ROOT/'validation/mapdl_preflight.json',dict(status='PASS_PREPROCESSOR_ONLY',
         input_manifest_sha256=hashlib.sha256((ROOT/'validation/input_manifest.json').read_bytes()).hexdigest(),
         solved=False,log=str(args.log),rows=reports,
         limitations='No SOLVE performed. Thermal convergence, UserMatTh runtime and restart/energy exports require the first authorized solve.'))
    print('MAPDL_64_FACE_CASES_VALIDATED_NO_SOLVE')


if __name__=='__main__': main()
