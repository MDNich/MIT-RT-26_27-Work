"""Freeze CDX1 + exact native columns (no curve interpolation). Inputs can be checked against upstream hashes."""
import argparse, csv, gzip, hashlib, json, shutil, io
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
D = Path(__file__).resolve().parent
p = argparse.ArgumentParser()
p.add_argument('atlas', type=Path)
p.add_argument('--blind', type=Path, help='optional prepared models/ and rasaero/ directories')
a = p.parse_args()
design = json.loads((D/'design.json').read_text())
digest = lambda x: hashlib.sha256(x.read_bytes()).hexdigest()
root = D/'inputs'; root.mkdir(exist_ok=True)
geoms = root/'models'; geoms.mkdir(exist_ok=True)
rows = []
for split in ('fit','holdout','control','sensitivity','blind'):
    for case in design[split]:
        source = a.blind if split == 'blind' else a.atlas
        model = source/'models'/(case+'.CDX1')
        raw = source/'rasaero'/(case+'.csv')
        shutil.copyfile(model,geoms/model.name)
        rows.append((case,split,digest(model),digest(raw)))
        if len(rows)==1:
            out=io.StringIO(newline=''); w=csv.writer(out,lineterminator='\n')
            w.writerow(['case','mach','alpha_deg','cp_in','cn','cna_0_4'])
        kept=set()
        with raw.open(encoding='utf-8-sig') as f:
            for r in csv.DictReader(f):
                m=float(r['Mach']); alpha=float(r['Alpha'])
                if .10-1e-8<=m<=5.00+1e-8 and alpha in (0,2,4):
                    k=round(m*100); assert abs(m-k/100)<1e-6 and (k,alpha) not in kept
                    kept.add((k,alpha)); w.writerow([case,k/100,int(alpha),r['CP'],r['CN'],r['CNalpha (0 to 4 deg) (per rad)']])
        assert all((i,al) in kept for i in range(10,(300 if split=='blind' else 500)+1) for al in (0,2,4))
(root/'ras-states.csv.gz').write_bytes(gzip.compress(out.getvalue().encode(),mtime=0))
with (root/'sources.csv').open('w') as f:
    w=csv.writer(f);w.writerow(['case','split','cdx_sha256','raw_export_sha256']);w.writerows(rows)
