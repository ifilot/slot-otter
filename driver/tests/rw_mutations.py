#!/usr/bin/env python3
"""Resident retry safety mutations. Only runtime assertion failures count."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('report stale read LBA', [('sd_diag.error=0; sd_diag.lba=lba;', 'sd_diag.error=0;')],
     'test_readonly_initialization_and_crc_checked_read'),
    ('release rejected CRC before busy completion', [
        ('sd_diag.stage=324;\n            if (ready(90,2)) { finish(); return -1; }',
         'sd_diag.stage=324;')],
     'test_transient_wire_crc_error_completes_rejection_then_resets'),
    ('four total attempts', [('sd_diag.attempts<=3', 'sd_diag.attempts<=4'),
                             ('sd_diag.attempts==3', 'sd_diag.attempts==4')],
     'test_persistent_mismatch_stops_after_three_total_attempts'),
    ('ignore full readback comparison', [('memcmp(expected,actual,512)', 'memcmp(expected,actual,0)')],
     'test_persistent_mismatch_stops_after_three_total_attempts'),
    ('ignore incoming CRC', [('return crc==sd_crc16(p,count)?0:fail(SD_CRC);',
                             'return (crc & 0)?fail(SD_CRC):0;')],
     'test_readonly_initialization_and_crc_checked_read'),
    ('refresh snapshot on retry', [('sd_diag.error=0;\n        if (!write_once(lba))',
                                   'sd_diag.error=0; memcpy(expected,buffer,512);\n        if (!write_once(lba))')],
     'test_retry_snapshot_survives_callers_buffer_change'),
    ('skip recovery identity comparison', [('memcmp(cid,identity,16) || sd_last_lba!=capacity',
                                          'memcmp(cid,identity,0) || sd_last_lba!=capacity')],
     'test_changed_identity_on_recovery_never_writes_replacement'),
    ('CID without sector recovery', [('return read_block(lba,actual);', '(void)lba; return 0;')],
     'test_failed_read_access_after_reset_prevents_another_write'),
    ('skip reset on retry', [('if (initialize()) return -1;', 'if (0) return -1;')],
     'test_transient_mismatch_reinitializes_then_retries_identical_packet'),
    ('lose poison latch', [('sd_diag.poisoned=1; armed=0;\n    return sd_diag.error',
                            'sd_diag.poisoned=0; armed=0;\n    return sd_diag.error')],
     'test_persistent_rejection_stops_after_three_total_attempts'),
    ('ignore programming status', [('if (sd_diag.r1 || sd_diag.status)',
                                    'if (sd_diag.r1)')],
     'test_transient_rejection_and_status_error_recover'),
    ('write wrong data CRC', [('U16 crc=sd_crc16(expected,512),i;', 'U16 crc=0,i;')],
     'test_success_exact_sector_crc_and_no_neighbors_changed'),
    ('permit writes while readonly', [('if (!sd_write_enabled || protected_card)',
                                       'if (protected_card)')],
     'test_default_readonly_and_disarmed_guard'),
]


def main():
    for name, changes, test in CASES:
        with tempfile.TemporaryDirectory(prefix='otter-rw-mutation-') as folder:
            work = Path(folder)
            for relative in ('OTTER.H', 'RWSD.H', 'SDRW.C', 'tests/HOSTRW.C',
                             'emulation/slot_model.c', 'emulation/slot_model.h'):
                target = work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            target = work / 'SDRW.C'
            source = target.read_text()
            for before, after in changes:
                if source.count(before) != 1:
                    raise RuntimeError('Mutation location changed: ' + name)
                source = source.replace(before, after)
            target.write_text(source)
            env = dict(os.environ, OTTER_TEST_SOURCE_ROOT=str(work))
            env.pop('OTTER_TEST_COVERAGE', None)
            result = subprocess.run([sys.executable, '-m', 'unittest', '-v',
                                     'test_rw_transport.ResidentTransportTests.' + test],
                                    cwd=ROOT / 'tests', env=env, capture_output=True, text=True)
            if result.returncode == 0 or 'FAILED (failures=' not in result.stderr:
                print(result.stdout + result.stderr)
                raise RuntimeError('Mutation not detected by an assertion: ' + name)
            print('DETECTED: ' + name, flush=True)
    print(f'PASS: {len(CASES)} resident transport mutations detected')


if __name__ == '__main__':
    main()
