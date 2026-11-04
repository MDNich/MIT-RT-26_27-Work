"""Compare accepted uninterrupted/restarted states and native pulse control."""
import gzip,json
from ops import ROOT,TMP,atomic,disks
from validate_run import validate

def state_at(runtime,index):
    with gzip.open(runtime/'checkpoints'/f'state_{index:06d}.json.gz','rt') as f:return json.load(f)

def main():
    disks();runs=TMP/'runs'
    reference=runs/'sustainer_al_restart_reference';base=runs/'sustainer_al_baseline7_n20_dt0125'
    if (reference/'phase_run_exit.json').exists():
        checked=validate(reference);a=state_at(reference,88);b=state_at(base,88)
        terr=max(abs(a['temperatures'][key]-b['temperatures'][key]) for key in a['temperatures'])
        aerr=max(abs(a['alpha'][key]-b['alpha'][key]) for key in a['alpha'])
        integrals=max(abs(a['energy_integrals'][key]-b['energy_integrals'][key])/max(abs(a['energy_integrals'][key]),1e-10) for key in a['energy_integrals'])
        assert terr<1e-5 and aerr<1e-8 and integrals<1e-6,(terr,aerr,integrals)
        assert a['layer']==b['layer']
        atomic(ROOT/'validation/restart_comparison.json',dict(passed=True,time_s=a['time_s'],max_nodal_temperature_difference_K=terr,max_conversion_difference=aerr,max_relative_energy_integral_difference=integrals,reference_native=checked))
        print('Uninterrupted/restarted physical states agree')
    pulse=runs/'sustainer_al_pulse_control'
    if (pulse/'phase_run_exit.json').exists():
        checked=validate(pulse)
        history=[json.loads(p.read_text()) for p in sorted((pulse/'checkpoints').glob('audit_*.json'))]
        cool=[a for a in history if a['time_s']>1+1e-8]
        assert len(cool)==5
        assert all(not a['exposure_on'] and a['gas_temperature_C']==22 and a['ablation_sink_W']==0 and a['hot_power_actual_W']<0 for a in cool)
        atomic(ROOT/'validation/native_pulse_control.json',dict(passed=True,cooling_steps=len(cool),last=cool[-1],native=checked))
        print('Native pulse/cooling boundary transfer passed')

if __name__=='__main__':main()
