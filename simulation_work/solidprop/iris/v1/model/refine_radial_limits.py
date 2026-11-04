"""Separate spatial refinement from explicit surface-coupling time accuracy."""
from run_radial_studies import run
for case in ['sustainer_al','sustainer_cf','booster_al','booster_cf']:
    for n,dt in [(80,.003125),(160,.0015625),(320,.00078125)]:
        run(case,n,dt,300,f'property_refined_n{n}_dt{dt:g}')
