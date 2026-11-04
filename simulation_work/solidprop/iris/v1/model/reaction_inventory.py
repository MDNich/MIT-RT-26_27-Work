"""Atom-balanced bookkeeping and fuel-envelope estimates, not burn-rate design."""
import json
import math
from ops import ROOT, disks

def main():
    disks()
    weights={'N':14.007,'H':1.008,'Cl':35.45,'O':15.999,'Al':26.9815385}
    species={'NH4ClO4':{'N':1,'H':4,'Cl':1,'O':4},'Al':{'Al':1},
             'Al2O3':{'Al':2,'O':3},'AlCl3':{'Al':1,'Cl':3},
             'NO':{'N':1,'O':1},'H2O':{'H':2,'O':1}}
    reactants={'NH4ClO4':3,'Al':3};products={'Al2O3':1,'AlCl3':1,'NO':3,'H2O':6}
    molar={s:sum(weights[a]*n for a,n in atoms.items()) for s,atoms in species.items()}
    atoms=lambda side:{a:sum(n*species[s].get(a,0) for s,n in side.items()) for a in weights}
    assert atoms(reactants)==atoms(products)
    total=sum(molar[s]*n for s,n in reactants.items())
    assert abs(total-sum(molar[s]*n for s,n in products.items()))<1e-10
    fractions={s:molar[s]*n/total for s,n in reactants.items()}
    density=1/(fractions['NH4ClO4']/1950+fractions['Al']/2700)
    motors={}
    for name,ri in [('sustainer',1.5625*.0254),('booster',2.5625*.0254)]:
        motors[name]=dict(outer_radius_m=ri,solid_cylinder_volume_at_1m_m3=math.pi*ri**2,
                         ideal_binary_full_cylinder_mass_at_1m_kg=density*math.pi*ri**2,
                         ideal_binary_full_cylinder_mass_length_range_kg=[density*math.pi*ri**2*l for l in [.75,1.25]],
                         mass_formula='mass = occupied_volume_fraction * density * pi * outer_radius^2 * length')
    result=dict(reaction='3 NH4ClO4 + 3 Al -> Al2O3 + AlCl3 + 3 NO + 6 H2O',
                atoms_each_side=atoms(reactants),molar_masses_g_mol=molar,
                reactant_mass_fractions=fractions,product_mass_fractions={s:molar[s]*n/total for s,n in products.items()},
                ideal_binary_density_kg_m3=density,motors=motors,
                assumptions=['The stated reaction is used for bookkeeping only; it is not an equilibrium product calculation.',
                             'Full-cylinder values assume no port, binder, voids or inhibited gaps. Multiply by actual occupied-volume fraction.',
                             'Density is an ideal additive-volume AP/Al assumption, not a measured propellant density.',
                             'Mass and length do not determine burn duration or liner heat flux without grain geometry and burn/flow data.'],
                sources={'AP_density_kg_m3':1950,'AP_density_source':'https://www.sigmaaldrich.com/US/en/product/aldrich/455822',
                         'Al_density_kg_m3':2700,'Al_density_source':'Previous v0 material configuration'})
    (ROOT/'validation/reaction_inventory.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()
