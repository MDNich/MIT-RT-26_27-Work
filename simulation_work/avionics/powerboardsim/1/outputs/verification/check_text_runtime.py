import System
root = r'Z:\Developer\MIT_Rkt_Team\2026-7\MIT-RT-26_27-Work\simulation_work\avionics\powerboardsim\1\outputs'
name = u'Coll\u00e9 - Power_Board_Batt_Screw_defeatured_2|Part 24[1] vers LPattern1[14]'
message = 'VERIFIED object=9000 name=' + name + ' source=[20450, 20454, 20459] target=[23197] Bonded/MPC pinball=0.3 mm'
try:
    bad = str(message)
except UnicodeDecodeError:
    print('Original failure reproduced: accented French contact name rejected by str().')
else:
    raise Exception('Original failure was not reproduced.')
# Extract and execute the actual repaired logging function, with real .NET I/O.
script = System.IO.File.ReadAllText(root + r'\repair_battery_mounts.py')
compile(script, 'repair_battery_mounts.py', 'exec')
start = script.index('def log(message):')
end = script.index('\ncreated =', start)
path = root + r'\verification\unicode_log_verified.txt'
writer = System.IO.StreamWriter(path, False)
context = {'writer': writer}
exec(compile(script[start:end], '<actual log function>', 'exec'), context)
expected = [message, u'Fran\u00e7ais: pi\u00e8ce, g\u00e9om\u00e9trie', u'Hungarian: K\u00e9perny\u0151', u'CONTACT_DEFINITIONS_VERIFIED: 5; newly created=2']
for item in expected:
    context['log'](item)
writer.Close()
actual = System.IO.File.ReadAllLines(path)
assert list(actual) == expected
print('PASS: actual repair logger preserves French and Hungarian text through real .NET file I/O.')
print('PASS: five-contact completion message remains readable after accented names.')
print('PASS: full repair script compiles in ANSYS IronPython 2.7.')
