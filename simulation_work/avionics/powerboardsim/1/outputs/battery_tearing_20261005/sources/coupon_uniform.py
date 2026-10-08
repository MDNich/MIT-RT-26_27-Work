"""One in-plane integration point and tied transverse edge for a uniform material test.
This diagnostic does not replace the fully integrated attachment shell formulation.
"""
from generate import coupon,S,seal
import json,sys
case=sys.argv[1]
coupon(case)
D=S/'runtime'/case
for name in ['model.inp','preflight.dat','run.dat']:
    text=(D/name).read_text().replace('KEYOPT,1,3,2','KEYOPT,1,3,0')
    text=text.replace('D,2,UY,0\n','D,2,UY,0\nCP,1,UY,3,4\n')
    (D/name).write_text(text)
cfg=json.loads((D/'config.json').read_text())
cfg.update(integration='One in-plane integration point; top edge UY coupled',qualification='Homogeneous material-law proof; attachment uses full integration')
seal(D,cfg)
