"""Audit the sealed native annular eigenmode once its guest exports are copied.

The fixture action checks the reader and rejection paths without starting ANSYS.
A real result is accepted only from the dedicated archived runtime directory.
"""
import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from ops import ROOT, TMP, atomic, disks, utc
from prepare_native_conduction_mode import PACKAGE

RUN = TMP / 'runs' / PACKAGE.name
LOG = 'irmode64.out'
DECK = 'annular_mode.inp'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def evaluate(expected, log, time_text, node_text):
    endings = ['IRIS_ANNULAR_MODE_END', 'RUN COMPLETED']
    if not all(s in log for s in endings):
        raise ValueError('Missing normal native job termination')
    for kind in ['WARNING', 'ERROR']:
        totals = re.findall(rf'NUMBER OF {kind}\s+MESSAGES ENCOUNTERED=\s*(\d+)', log)
        if totals != ['0'] or re.search(rf'\*\*\* {kind} \*\*\*', log):
            raise ValueError(f'Native {kind.lower()} count requires review')
    for pattern in [r'Number of processes requested\s*:\s*1\b',
                    r'Number of threads per process requested\s*:\s*10\b',
                    r'Total number of cores requested\s*:\s*10\s*\(Shared Memory Parallel\)']:
        if not re.search(pattern, log):
            raise ValueError('Expected one ten-core SMP process in native statistics')
    t = float(time_text.strip())
    if not math.isclose(t, expected['terminal_time_s'], rel_tol=1e-10, abs_tol=1e-11):
        raise ValueError('Native terminal time differs from the analytical comparison time')
    reference = {int(key): value for key, value in expected['expected_final_C'].items()}
    differences = {}
    for line in node_text.splitlines():
        if not line.strip():
            continue
        node, value = line.split()
        if not re.fullmatch(r'[0-9]+(?:\.0*)?', node):
            raise ValueError('Expected integer node identifier')
        node, value = int(node.partition('.')[0]), float(value)
        if node in differences or node not in reference or not math.isfinite(value):
            raise ValueError('Duplicate, unrecognised or nonfinite node export')
        differences[node] = value - reference[node]
    if differences.keys() != reference.keys() or len(differences) != expected['nodes']:
        raise ValueError('Incomplete native nodal temperature export')
    worst = max(differences, key=lambda node: abs(differences[node]))
    maximum = abs(differences[worst])
    if maximum > expected['max_analytic_error_target_K']:
        raise ValueError(f'Maximum nodal error {maximum:g} K exceeds the sealed tolerance')
    return dict(passed=True, nodes=len(differences), terminal_time_s=t, worst_node=worst,
                max_nodal_error_K=maximum, rms_nodal_error_K=math.sqrt(
                    math.fsum(v*v for v in differences.values()) / len(differences)))


def fixture(expected):
    log = ('IRIS_ANNULAR_MODE_END\nNUMBER OF WARNING MESSAGES ENCOUNTERED= 0\n'
           'NUMBER OF ERROR   MESSAGES ENCOUNTERED= 0\nNumber of processes requested : 1\n'
           'Number of threads per process requested : 10\nTotal number of cores requested : '
           '10 (Shared Memory Parallel)\nRUN COMPLETED')
    entries = [f'{n}. {value:.16E}' for n, value in expected['expected_final_C'].items()]
    t = str(expected['terminal_time_s'])
    nominal = evaluate(expected, log, t, '\n'.join(entries))
    bad = {
        'missing_node': (log,t,entries[:-1]),
        'duplicate_node': (log,t,entries + entries[:1]),
        'unknown_node': (log,t,entries[1:] + ['0. 22.0']),
        'nonfinite_export': (log,t,['1. NaN'] + entries[1:]),
        'large_field_error': (log,t,['1. 1000'] + entries[1:]),
        'wrong_final_time': (log,'0',entries),
        'wrong_parallel_request': (log.replace('10 (Shared', '1 (Shared'),t,entries),
        'unfinished_log': (log.replace('RUN COMPLETED',''),t,entries),
        'unreviewed_warning': (log+'\n*** WARNING ***',t,entries),
    }
    for name, (trial_log, trial_time, nodes) in bad.items():
        try:
            evaluate(expected,trial_log,trial_time,'\n'.join(nodes))
        except ValueError:
            continue
        raise RuntimeError(f'Unexpected fixture acceptance: {name}')
    return dict(scope='Manufactured reader fixtures only. No native run.', accepted_fixture=nominal,
                correctly_rejected=list(bad))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['fixture','audit'])
    args = parser.parse_args()
    disks()
    expected_file = PACKAGE/'expected.json'
    expected = json.loads(expected_file.read_text())
    if digest(PACKAGE/DECK) != expected['input_sha256']:
        raise ValueError('Mismatch in sealed deck')
    if args.action == 'fixture':
        result = fixture(expected)
        name = 'native_conduction_mode_reader_checks.json'
    else:
        if digest(RUN/DECK) != expected['input_sha256']:
            raise ValueError('Archived guest deck differs from sealed input')
        receipt = json.loads((RUN/'guest_terminal.json').read_text(encoding='utf-8-sig'))
        if (receipt['job'] != expected['job'] or receipt['exit_code'] != 0 or
                receipt['guest_input_sha256'].lower() != expected['input_sha256']):
            raise ValueError('Native job, exit status or input digest differs')
        exports = [LOG,'mode_time.txt','mode_end.txt']
        hashes = {n:digest(RUN/n) for n in exports}
        if hashes != {n:receipt['guest_sha256'][n].lower() for n in exports}:
            raise ValueError('Guest-export hashes differ from archived files')
        log = (RUN/LOG).read_text(encoding='utf-8',errors='replace')
        result = evaluate(expected,log,(RUN/'mode_time.txt').read_text(encoding='ascii'),
                          (RUN/'mode_end.txt').read_text(encoding='ascii'))
        result.update(scope='Native inert annular conduction verification only',
                      guest_receipt_sha256=digest(RUN/'guest_terminal.json'),exports=hashes)
        name = 'native_annular_mode64_smp10.json'
    result.update(checked_utc=utc(),expected_sha256=digest(expected_file),reader_sha256=digest(Path(__file__)))
    atomic(ROOT/'validation'/name,result)
    print(result['scope'])


if __name__ == '__main__':
    main()
