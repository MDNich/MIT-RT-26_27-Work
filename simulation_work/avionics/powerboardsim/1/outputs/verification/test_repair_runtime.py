import System
import re
p=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\repair_and_solve_modal.py'
s=System.IO.File.ReadAllText(p)
compile(s,p,'exec')
ns={'System':System,'re':re}
helpers=s[s.index('def text(value):'):s.index('# End pure helper functions')]
exec compile(helpers,'repair_helpers','exec') in ns
check=ns['row_is_connected']
assert check('Closed','24')
assert check(u'Ferm\u00e9','')
assert not check('Inactive','24')
assert not check('Inactif','N/A')
assert not check('Far Open','0')
assert not check('Near Open','0')
assert not check('','')
parse=ns['parse_frequencies']
assert parse('No frequency output')==[]
assert parse('FREQUENCIES FROM BLOCK LANCZOS ITERATION\n\nMODE FREQUENCY\n\n1 0.000000\n2 1.20D+02\n\nOTHER\n1 400.0')==[0.0,120.0]
base=r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs\fresh_connections_20261004_193530757\solver_before_1656\solve.out'
f=parse(System.IO.File.ReadAllText(base))
assert len(f)==20 and all(x==0.0 for x in f)
out=System.IO.Path.Combine(System.IO.Path.GetTempPath(),'repair_unicode_verified.txt')
ns['write'](out,u'Ferm\u00e9 / \u0151\n')
assert ns['read'](out)==u'Ferm\u00e9 / \u0151\n'
print('PASS: ANSYS IronPython compilation; contact gate; 20 baseline zero modes parsed; .NET Unicode round-trip.')
