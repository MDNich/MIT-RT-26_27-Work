"""Audit fresh continuous scout provenance/bookkeeping, not physical validity."""
import json
import numpy as np
from ops import ROOT, TMP, atomic, disks, utc
from continuous_heating_campaign import digest, decode_state
from radial_model import RadialModel


def main():
    disks()
    plan_path=ROOT/'configs/continuous_heating_campaign.json'
    plan=json.loads(plan_path.read_text());sha=digest(plan_path)
    for source,archive in plan['archived_sources'].items():
        assert digest(ROOT/archive)==plan['source_hashes'][source]
    records=[]
    for item in plan['cases']:
        path=ROOT/'validation/continuous_heating'/f"{item['tag']}.json"
        result=json.loads(path.read_text())
        checkpoint=TMP/'continuous_heating'/f"{item['tag']}_checkpoint.json"
        saved=json.loads(checkpoint.read_text());state=decode_state(saved['state'])
        assert result['plan_sha256']==saved['plan_sha256']==sha
        assert result['configuration']==item['configuration']
        assert result['source_hashes']==plan['source_hashes']
        assert not result['eligible_for_motor_lifetime'] and not result['numerical_convergence_established']
        assert result['energy_balance_passed'] and result['mass_balance_passed']
        assert result['max_energy_relative_error']<1e-6 and result['max_mass_relative_error']<1e-8
        times=[r['time_s'] for r in result['history']]
        assert all(b>a for a,b in zip(times,times[1:]))
        assert abs(times[-1]-state.time)<1e-10
        cfg=item['configuration'];model=RadialModel(cfg)
        initial=cfg['material']['virgin_reference_density_kg_m3']*sum(model.vol[:model.np])
        remaining=model.summary(state)['solid_remaining_kg_per_rad_m']
        residual=initial-remaining-state.gas_total-state.char_total-state.eject_total
        relative=abs(residual)/initial
        assert relative<1e-10
        bracket=result['model_exhaustion_bracket_s']
        if bracket is not None:
            assert state.layer==model.np and result['final']['remaining_mm']==0
            assert bracket[0]<bracket[1] and abs(bracket[1]-state.time)<1e-10
        scope=result['property_limit_bracket_s']
        records.append(dict(case=item['case'],record_sha256=digest(path),checkpoint_sha256=digest(checkpoint),
            model_exhaustion_bracket_s=bracket,property_limit_bracket_s=scope,
            initial_mass_kg_per_rad_m=initial,remaining_mass_kg_per_rad_m=remaining,
            gas_mass_kg_per_rad_m=state.gas_total,char_mass_kg_per_rad_m=state.char_total,
            ejected_residual_mass_kg_per_rad_m=state.eject_total,
            cumulative_mass_relative_error=relative,max_step_energy_error=result['max_energy_relative_error'],
            history_samples=len(times)))
    atomic(ROOT/'validation/continuous_heating_scout_audit.json',dict(checked_utc=utc(),passed=True,
        plan_sha256=sha,records=records,eligible_for_motor_lifetime=False,numerical_convergence_established=False,
        qualification='Source, configuration, state history, finite-row exhaustion bookkeeping and cumulative mass audit only. '
        'Step energy closure is the inherited equation balance, not validation of physical open-system enthalpy. '
        'Post-scope events and finite-row model sensitivity still prevent physical motor-lifetime interpretation.'))
    print(json.dumps(records,indent=2))


if __name__=='__main__':main()
