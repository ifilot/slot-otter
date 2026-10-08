#!/usr/bin/env python3
"""Compile performance regressions and require a behavioral assertion failure."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('omit audit exit authentication', 'RWFS.C',
     'if (n>=0x0ffffff8UL) {\n      if (sd_check_media())',
     'if (n>=0x0ffffff8UL) {\n      if (0)',
     'test_performance.PerformanceGuards.test_mid_audit_removal_and_replacement_never_accept_cached_proof'),
    ('ignore command CRC input', 'SDRW.C',
     'crc7_table[(U8)((crc<<1)^p[i])]', 'crc7_table[(U8)((crc<<1)^(p[i]&0))]',
     'test_performance.PerformanceGuards.test_varied_command_crc7'),
    ('truncate 64K cluster mask', 'RWFS.C',
     'if (!(f->size&(((U32)volume.spc<<9)-1UL)))',
     'if (!(f->size&((U16)((U32)volume.spc<<9)-1UL)))',
     'test_performance.PerformanceGuards.test_all_cluster_sizes_read_and_append_across_64k_boundary'),
    ('repeat identity per cached audit link', 'RWFS.C',
     'fs_error=0; n=fs_fat_entry(c);', 'fs_error=0; n=rw_fat(c);',
     'test_rw_fs.ResidentFilesystemTests.test_copy_chunk_read_budget_and_exact_data_for_both_cluster_sizes'),
]


def main():
    for name, filename, before, after, test in CASES:
        with tempfile.TemporaryDirectory(prefix='otter-perf-mutation-') as directory:
            work = Path(directory)
            for relative in ('OTTER.H', 'RWSD.H', 'RWFS.H', 'SDRW.C', 'RWFS.C', 'FAT32.C',
                             'tests/HOSTRW.C', 'tests/emulation/slot_model.c',
                             'tests/emulation/slot_model.h', 'tests/kit_fixture.py', 'tests/fixture.py'):
                target = work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            target = work / filename
            source = target.read_text()
            if source.count(before) != 1:
                raise RuntimeError('Mutation location changed: ' + name)
            target.write_text(source.replace(before, after))
            env = dict(os.environ, OTTER_TEST_SOURCE_ROOT=str(work))
            env.pop('OTTER_TEST_COVERAGE', None)
            result = subprocess.run([sys.executable, '-m', 'unittest', '-v', test],
                                    cwd=ROOT / 'tests', env=env, capture_output=True, text=True)
            if result.returncode == 0 or 'FAILED (failures=' not in result.stderr:
                print(result.stdout + result.stderr)
                raise RuntimeError('Mutation not caught by an assertion: ' + name)
            print('DETECTED: ' + name, flush=True)
    print(f'PASS: {len(CASES)} performance mutations detected')


if __name__ == '__main__':
    main()
