"""Input perturbations within the explicitly limited independent model."""
import argparse
from run_radial_studies import run

p=argparse.ArgumentParser();p.add_argument('group',choices=['materials','heating']);args=p.parse_args()
cases=['sustainer_al','sustainer_cf','booster_al','booster_cf']
for case in cases:
    if args.group=='materials':
        for pressure in [600,1000]:
            run(case,80,.003125,300,f'fine_pressure{pressure}',overrides={
                'char_law':{'pressure_Pa':pressure*6894.757293168,'pressure_nominal_psi':pressure},
                'provenance':{'sensitivity':'Inherited 600-1000 psi pressure bracket; independent exploratory input perturbation'}})
        for prop in ['k','cp']:
            for scale in [.8,1.2]:
                run(case,80,.003125,300,f'fine_phenolic_{prop}_{scale:g}',overrides={
                    'material':{f'phenolic_{prop}_scale':scale},
                    'provenance':{'sensitivity':'Plus/minus 20 percent engineering perturbation; not a measured material uncertainty interval'}})
        if case.endswith('_cf'):
            for k in [.5,.6]:
                run(case,80,.003125,300,f'fine_cf_radial_k{k:g}',overrides={
                    '_root':{'cf_radial_k':k},'provenance':{'sensitivity':'Published woven-CF through-thickness surrogate range; not actual Iris material data'}})
            run(case,80,.003125,300,'fine_cf_nasa_reference',overrides={
                '_root':{'cf_radial_k':.3832,'cf_cp_constant_J_kg_K':886.},
                'material':{'aluminium_density_kg_m3':1596.},
                'provenance':{'sensitivity':'Alternative carbon-epoxy thermal-model tuple from Pauken TFAWS 2012 slide 14: rho1596 k0.3832 cp886. Different composite, not measured Iris properties.'}})
    else:
        for h in [500,2000]:
            run(case,80,.003125,300,f'fine_h{h}',overrides={'heating':{'h0_W_m2_K':h},
                'provenance':{'sensitivity':'Broad engineering heat-transfer scenario, not a statistical interval'}})
        for eps in [.1,.3]:
            run(case,80,.003125,300,f'fine_radiation{eps:g}',overrides={'heating':{'hot_effective_emissivity':eps},
                'provenance':{'sensitivity':'Separate hot-radiation scenario at inherited gas/radiative temperature'}})
        for scale in [.5,2.]:
            run(case,80,.003125,300,f'fine_charcost{scale:g}',overrides={'char_law':{'effective_endothermic_cost_J_kg':35e6*scale},
                'provenance':{'sensitivity':'Factor-two perturbation of uncalibrated effective removal cost; not measured kinetic uncertainty'}})
