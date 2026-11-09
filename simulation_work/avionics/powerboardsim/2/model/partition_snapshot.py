"""Take a read-only APFS snapshot of one completed increment in a live distributed installation."""
import argparse
import ctypes
import os
import re
import struct
import tempfile
from pathlib import Path

import numpy as np

from audit_local import ROOT, read
from film_identity import digest, verified, write_json
from native_rst import read_rst


def stamp(path):
    s = path.stat()
    return s.st_size, s.st_mtime_ns, s.st_ctime_ns


def converged_prefix(raw, steps, times, terminal):
    header=raw._resultheader['ls_table'][:,:2]
    count=len(steps)
    assert np.array_equal(header[:count],steps)
    tail=header[count:]
    assert not len(tail) or (terminal and len(tail)==1 and tail[0,1]==999999)
    assert np.all(np.diff(raw.time_values[:count])>0)
    assert np.allclose(raw.time_values[:count],times,rtol=0,atol=5.1e-6)
    return len(tail)


class IncompletePartitionRecord(ValueError):
    """The result-set header is present before its native data record is readable."""


def check_element_tables(path, raw, count):
    """Reject a named result set whose element offsets have not yet reached the partition file."""
    size = path.stat().st_size
    with path.open('rb') as stream:
        def integer_record(pointer, expected_words):
            start = 4 * int(pointer)
            if start < 0 or start + 12 + 4 * expected_words > size:
                raise IncompletePartitionRecord(f'{path.name} set {k+1}: record extends beyond the sealed partition')
            stream.seek(start)
            words, flags = struct.unpack('<II', stream.read(8))
            stream.seek(start + 8 + 4 * expected_words)
            trailer, = struct.unpack('<I', stream.read(4))
            if (words, flags, trailer) != (expected_words, 0x80000000, expected_words):
                raise IncompletePartitionRecord(f'{path.name} set {k+1}: incomplete or unsupported native integer record')

        for k, pointer in enumerate(raw._resultheader['rpointers'][:count]):
            integer_record(pointer, 200)
            offset = raw._result_solution_header(k)['ptrESL']
            if offset <= 0:
                raise IncompletePartitionRecord(f'{path.name} set {k+1}: no stored element solution')
            integer_record(int(pointer) + int(offset), 2 * len(raw._eeqv))


def capture(case, campaign, terminal=False):
    rt = ROOT/'.runtime'
    source = rt/'shared_native'/campaign/case
    state = read(rt/'receipts'/campaign/case/'status.json')
    assert state['case']==case and state['shared_scratch']
    if terminal:
        assert state['phase'] in ('solver_complete','failed') and 'exit' in state
        assert not (source/'file.lock').exists()
    else:
        assert state['phase']=='solving'
    spec = read(ROOT/'validation/board_surface_jobs.json')[case]
    deck = verified(source/'model.inp',spec['model_sha256'])
    listing = (source/'solve.out').read_bytes()
    pattern = rb'LOAD STEP\s+(\d+)\s+SUBSTEP\s+(\d+)\s+COMPLETED[^\r\n]*[\r\n]+\s*\*\*\* TIME\s*=\s*([\d.Ee+-]+)'
    if terminal:
        assert re.search(rb'NUMBER OF ERROR\s+MESSAGES ENCOUNTERED=\s*\d+',listing)
    events = list(re.finditer(pattern,listing))
    assert events
    ls, sb = map(int,events[-1].groups()[:2])
    generation=f'step{ls}_substep{sb}' + ('_terminal' if terminal else '')
    directory = rt/'partition_snapshots'/campaign/case
    final = directory/generation
    revision = 0
    while (final/'receipts.json').is_file():
        prior = read(final/'receipts.json')
        assert prior['model_sha256']==deck
        try:
            for name, record in prior['files'].items():
                verified(final/name, record['SHA256'])
                check_element_tables(final/name, read_rst(final/name,read_mesh=False), prior['sets'])
        except IncompletePartitionRecord:
            # Keep the original clone and its hashes. An updated on-disk table gets its own copy.
            revision += 1
            final = directory/(generation+f'_readback{revision}')
        else:
            return final
    final.parent.mkdir(parents=True,exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix=final.name+'_capture_',dir=final.parent))
    files = [source/f'file{i}.rst' for i in range(state['cores'])]
    before = [stamp(p) for p in files]
    clone = ctypes.CDLL(None,use_errno=True).clonefile
    clone.argtypes = [ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int]
    for path in files:
        if clone(os.fsencode(path),os.fsencode(root/path.name),0):
            raise OSError(ctypes.get_errno(),f'APFS clone failed for {path.name}')
    assert before==[stamp(p) for p in files], 'Partitions changed during capture. Discard this unsealed capture.'
    saved = root/'converged_listing.txt'
    saved.write_bytes(listing[:events[-1].end()])
    steps = np.array([[int(m[1]),int(m[2])] for m in events])
    times = np.array([float(m[3]) for m in events])
    manifest = {}
    excluded = []
    for p, state_before in zip(files,before,strict=True):
        dest = root/p.name
        assert dest.stat().st_size==state_before[0] and dest.stat().st_ino!=p.stat().st_ino
        raw = read_rst(dest,read_mesh=False)
        excluded.append(converged_prefix(raw,steps,times,terminal))
        check_element_tables(dest,raw,len(steps))
        manifest[p.name] = dict(bytes=state_before[0], SHA256=digest(dest))
    assert len(set(excluded))==1
    terminal_data={}
    if terminal:
        full=root/'terminal_listing.txt'
        full.write_bytes(listing)
        write_json(root/'terminal_status.json',state)
        terminal_data=dict(native_exit=state['exit'],terminal_listing_sha256=digest(full),
                           terminal_status_sha256=digest(root/'terminal_status.json'))
    write_json(root/'receipts.json',dict(capture_phase=state['phase'],diagnostic_sets_excluded=excluded[0],**terminal_data,case=case,campaign=campaign,model_sha256=deck,cores=state['cores'],
        converged_listing_sha256=digest(saved),sets=len(steps),last_loadstep=ls,last_substep=sb,
        last_time_s=float(raw.time_values[len(steps)-1]),files=manifest))
    root.rename(final)
    return final


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('case',choices=['flush_nylon_surf1_static','flush_aluminium_surf1_static'])
    p.add_argument('--campaign',default='nov08_01')
    p.add_argument('--terminal',action='store_true',help='Read a closed installation after recorded native exit.')
    a=p.parse_args()
    print(capture(a.case,a.campaign,a.terminal))
