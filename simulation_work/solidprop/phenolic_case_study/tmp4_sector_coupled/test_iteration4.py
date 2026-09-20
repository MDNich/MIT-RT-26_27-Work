"""Unit/integration tests with synthetic fields. Never starts ANSYS."""
from pathlib import Path
import copy
import math
import re
import tempfile
import unittest
import coupler as c

ROOT=Path(__file__).resolve().parent


class Iteration4Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cfg=c.load(ROOT/'config.json'); cls.mesh=c.load(ROOT/'mesh_map.json')

    def state(self):
        return c.initial_state(self.mesh,self.cfg)

    def synthetic(self,s,p,alpha=None,T=22.):
        """Construct consistent *synthetic* field exports, not ANSYS results."""
        dead={str(f['element']) for row in self.mesh['rows'][:p['layer']] for f in row}
        temp={n:T for n in self.mesh['nodes']}
        fields={eid:[s['alpha'].get(eid,0.) if alpha is None else alpha,0.,0.,0.]
                for eid in self.mesh['elements'] if eid not in dead}
        energy={eid:[0.,0.,0.,0.,0.] for eid in fields}
        hot=0.
        for i,f in enumerate(self.mesh['rows'][p['layer']]):
            power=f['area']*p['faces'][i]['h']*(self.cfg['heating']['gas_temperature_C']-T)
            energy[str(f['element'])][2]=-power
            hot+=power
        energy[next(iter(energy))][0]=hot+sum(p['forces'].values())
        return temp,fields,energy

    def test_geometry(self):
        self.assertEqual(len(self.mesh['nodes']),54540)
        self.assertEqual(len(self.mesh['elements']),35200)
        self.assertEqual(len(self.mesh['rows']),64)
        all_e=[]
        for i,row in enumerate(self.mesh['rows']):
            self.assertEqual(len(row),200)
            self.assertEqual(len({n for f in row for n in f['nodes']}),303)
            radius=.066675+i*.00127/64
            for f in row:
                for nid in f['nodes']:
                    x,y,z=self.mesh['nodes'][str(nid)]
                    self.assertAlmostEqual(math.hypot(x,z),radius,places=9)
                all_e.append(f['element'])
        self.assertEqual(len(set(all_e)),12800)

    def test_no_automatic_solve(self):
        for name in ('model_base.inp','preflight_no_solve.inp','material_iteration4.apdl'):
            self.assertIsNone(re.search(r'^\s*SOLVE\b',(ROOT/name).read_text(),re.M|re.I))
        self.assertIn('if (-not $Run -and -not $PreflightMapdl)',(ROOT/'launch_iteration4.ps1').read_text())

    def test_configuration_pressure_not_invented(self):
        c.validate_config(self.cfg)
        self.assertIsNone(self.cfg['char_law']['pressure_Pa'])
        bad=copy.deepcopy(self.cfg); bad['char_law']['mode']='species'
        with self.assertRaises(AssertionError): c.validate_config(bad)

    def test_char_rate_limits(self):
        law=copy.deepcopy(self.cfg['char_law'])
        self.assertLess(c.char_rate(500,law),c.char_rate(1000,law))
        self.assertLess(c.char_rate(2500,law),law['mass_transfer_cap_kg_m2_s'])
        law['reactive_activity']=0
        self.assertEqual(c.char_rate(2000,law),0)
        law['reactive_activity']=1; law['pressure_Pa']=0
        self.assertEqual(c.char_rate(2000,law),0)

    def test_blowing(self):
        self.assertEqual(c.blowing(1000,0,1600),1000)
        self.assertGreater(c.blowing(1000,.01,1600),c.blowing(1000,.1,1600))
        self.assertGreater(c.blowing(1000,.1,1600),0)

    def test_virgin_cannot_be_consumed_as_char(self):
        s=self.state(); s['temperatures']={n:1800 for n in self.mesh['nodes']}
        p,commands=c.prepare_step(self.mesh,self.cfg,s)
        self.assertEqual(p['totals']['char_rate_kg_s'],0)
        self.assertEqual(p['totals']['ablation_sink_W'],0)
        self.assertEqual(len(re.findall(r'^SFE,',commands,re.M)),800)

    def test_char_mass_energy_coupling(self):
        s=self.state(); s['temperatures']={n:1400 for n in self.mesh['nodes']}
        s['alpha']={eid:1 for eid,e in self.mesh['elements'].items() if e['mat']==1}
        p,commands=c.prepare_step(self.mesh,self.cfg,s)
        self.assertGreater(p['totals']['char_rate_kg_s'],0)
        self.assertAlmostEqual(p['totals']['ablation_sink_W'],
            p['totals']['char_rate_kg_s']*self.cfg['char_law']['effective_endothermic_cost_J_kg'])
        self.assertAlmostEqual(sum(p['forces'].values()),p['totals']['hot_radiation_W']+
            p['totals']['outer_radiation_W']-p['totals']['ablation_sink_W'])
        for f in p['faces']:
            self.assertLessEqual(f['char_rate']*p['dt'],f['char_available']+1e-20)

    def test_all_surface_transfers(self):
        s=self.state()
        for i in range(64):
            s['layer']=i
            s['pending_kills']=[f['element'] for f in self.mesh['rows'][i-1]] if i else []
            p,commands=c.prepare_step(self.mesh,self.cfg,s)
            actual={(int(e),int(face)) for e,face in re.findall(r'^SFE,(\d+),(\d+),CONV,0',commands,re.M)}
            expected={(f['element'],f['face']) for f in self.mesh['rows'][i]+self.mesh['outer']}
            self.assertEqual(actual,expected)
            killed={int(e) for e in re.findall(r'^EKILL,(\d+)',commands,re.M)}
            self.assertEqual(killed,set(s['pending_kills']))
            self.assertFalse({e for e,f in actual}&killed)

    def test_accept_mass_balance_and_power(self):
        s=self.state(); p,_=c.prepare_step(self.mesh,self.cfg,s)
        temp,fields,energy=self.synthetic(s,p,alpha=.01)
        new,record=c.accept_step(self.mesh,self.cfg,s,p,temp,fields,energy,p['target'])
        self.assertEqual(new['index'],1)
        self.assertAlmostEqual(record['mass_residual_kg'],0,places=16)
        self.assertAlmostEqual(record['energy_residual_W'],0,places=12)
        self.assertGreater(new['gas_cumulative_kg'],0)
        self.assertEqual(record['rows_removed'],0)

    def test_missing_heat_is_rejected(self):
        s=self.state(); p,_=c.prepare_step(self.mesh,self.cfg,s)
        temp,fields,energy=self.synthetic(s,p)
        for value in energy.values(): value[2]=0
        with self.assertRaisesRegex(ValueError,'hot-side convection'):
            c.accept_step(self.mesh,self.cfg,s,p,temp,fields,energy,p['target'])

    def test_bad_energy_is_rejected(self):
        s=self.state(); p,_=c.prepare_step(self.mesh,self.cfg,s)
        temp,fields,energy=self.synthetic(s,p)
        energy[next(iter(energy))][0]+=100
        with self.assertRaisesRegex(ValueError,'energy audit'):
            c.accept_step(self.mesh,self.cfg,s,p,temp,fields,energy,p['target'])

    def test_time_and_missing_fields_fail_closed(self):
        s=self.state(); p,_=c.prepare_step(self.mesh,self.cfg,s)
        temp,fields,energy=self.synthetic(s,p)
        with self.assertRaisesRegex(ValueError,'time'):
            c.accept_step(self.mesh,self.cfg,s,p,temp,fields,energy,0)
        fields.pop(next(iter(fields)))
        with self.assertRaisesRegex(ValueError,'Missing'):
            c.accept_step(self.mesh,self.cfg,s,p,temp,fields,energy,p['target'])

    def test_row_deletion_is_scheduled_not_claimed_applied(self):
        s=self.state(); rv=1250.; rc=600.
        s['alpha']={eid:1. for eid,e in self.mesh['elements'].items() if e['mat']==1}
        s['gas_cumulative_kg']=sum((rv-rc)*e['volume'] for e in self.mesh['elements'].values() if e['mat']==1)
        s['char_consumed']={str(f['element']):rc*f['volume']*(1-1e-8) for f in self.mesh['rows'][0]}
        s['char_cumulative_kg']=sum(s['char_consumed'].values())
        p,_=c.prepare_step(self.mesh,self.cfg,s)
        temp,fields,energy=self.synthetic(s,p)
        new,record=c.accept_step(self.mesh,self.cfg,s,p,temp,fields,energy,p['target'])
        self.assertEqual(record['rows_removed'],0)
        self.assertEqual(record['rows_scheduled'],1)
        self.assertEqual(len(new['pending_kills']),200)
        p2,commands=c.prepare_step(self.mesh,self.cfg,new)
        self.assertEqual(p2['layer'],1)
        self.assertEqual(len(re.findall(r'^EKILL,',commands,re.M)),200)
        temp,fields,energy=self.synthetic(new,p2)
        new2,rec2=c.accept_step(self.mesh,self.cfg,new,p2,temp,fields,energy,p2['target'])
        self.assertEqual(rec2['rows_removed'],1)
        self.assertAlmostEqual(rec2['mass_residual_kg'],0,places=15)

    def test_duplicate_export_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'field.txt'; p.write_text('1 2\n1 3\n')
            with self.assertRaisesRegex(ValueError,'Duplicate'): c.read_rows(p)

    def test_sensible_energy_integral(self):
        self.assertEqual(c.sensible_enthalpy(22,22),(0,0))
        self.assertAlmostEqual(c.sensible_enthalpy(25,22)[0],2700)
        self.assertEqual(c.sensible_enthalpy(22,25),(-2700,-2400))


if __name__=='__main__':
    import sys
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Iteration4Tests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    c.save(ROOT/'validation/unit_tests.json',dict(tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful(),
        data='Synthetic controller fixtures and copied mesh, NOT solved thermal results',solve_started=False))
    sys.exit(0 if result.wasSuccessful() else 1)
