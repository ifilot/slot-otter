#!/usr/bin/env python3
"""Require real assertion failures for targeted writable DOS callback defects."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ('restart every writable read','REDIR.C','if (!rw_read_serial || file->read_serial!=rw_read_serial ||',
     'if (1 || file->read_serial!=rw_read_serial ||',
     'test_read_cache.Fat32ReadCacheTests.test_sequential_read_walk_and_metadata_budget'),
    ('retain cursors across writes','RWFS.C','  invalidate_reads();\n  fs_invalidate_sector(lba);',
     '  fs_invalidate_sector(lba);',
     'test_read_cache.Fat32ReadCacheTests.test_tail_relinked_with_same_first_cluster_invalidates_retained_cursor'),
    ('recycle wrapped serial','RWFS.C','  if (rw_read_serial) ++rw_read_serial;',
     '  if (++rw_read_serial==0) rw_read_serial=1;',
     'test_read_cache.Fat16ReadCacheTests.test_serial_wrap_disables_retention_without_recycling_old_cursors'),
    ('disable directory cache hits','FAT32.C','if (cache[i].lba==lba) return cache[i].bytes;',
     'if (cache==fat_cache && cache[i].lba==lba) return cache[i].bytes;',
     'test_read_cache.Fat16ReadCacheTests.test_two_directory_sectors_survive_interleaved_file_reads'),
    ('omit directory store invalidation','FAT32.C','if (directory_cache[i].lba==lba) directory_cache[i].lba=0xffffffffUL;',
     'if (0) directory_cache[i].lba=0xffffffffUL;',
     'test_read_cache.Fat16ReadCacheTests.test_selective_directory_invalidation_preserves_other_cached_sector'),
    ('shrink FAT cache to one sector','FAT32.C','cached_sector(lba,fat_cache,3,&fat_next)',
     'cached_sector(lba,fat_cache,0,&fat_next)',
     'test_read_cache.Fat16ReadCacheTests.test_four_fat_sectors_survive_interleaved_lookups'),

    ('hide fast mount policy','REDIR.C','if (rw_skip_fat_check) info.flags|=16;',
     'if (0) info.flags|=16;', 'test_skipfatcheck_policy_is_reported_and_persists_across_remount'),
    ('forget fast policy on remount','REDIR.C','U16 media_mount(void) {',
     'U16 media_mount(void) { rw_skip_fat_check=0;',
     'test_skipfatcheck_policy_is_reported_and_persists_across_remount'),
    ('forget lost dirty session', 'REDIR.C',
     'if (rw_dirty_session()) unload_blocked=1;',
     'if (0) unload_blocked=1;', 'test_unload_discovery_cannot_hide_dirty_card_removal'),
    ('unload with open files', 'REDIR.C',
     'if (open_count()) return error(E_ACCESS);',
     'if (0) return error(E_ACCESS);', 'test_unload_refuses_open_handles_and_later_vector_without_writes'),
    ('unload beneath a later hook', 'REDIR.C',
     'get16(vector+2)!=unload_state[2]',
     '0', 'test_unload_refuses_open_handles_and_later_vector_without_writes'),
    ('skip unload commit', 'REDIR.C',
     'if (sd_write_enabled && media_online && rw_flush())\n                    return error(fs_error);',
     'if (0) return error(fs_error);', 'test_unload_commits_closed_file_and_restores_entire_cds'),
    ('ignore unload poison', 'REDIR.C',
     'if (unload_blocked || (sd_write_enabled && sd_diag.poisoned))\n                    return error(E_NOTREADY);',
     'if (0) return error(E_NOTREADY);', 'test_unload_failed_commit_keeps_drive_installed_and_retry_refuses_poison'),
    ('truncate DOS 4 CDS restoration', 'REDIR.C',
     'i<(dos_major==3?0x51:0x58)',
     'i<0x51', 'test_unload_commits_closed_file_and_restores_entire_cds'),
    ('leave logical total unscaled', 'REDIR.C', 'total>>=1; free>>=1; unit<<=1;',
     'total>>=0; free>>=1; unit<<=1;', 'test_disk_space_scaling_boundaries'),
    ('leave logical free count unscaled', 'REDIR.C', 'total>>=1; free>>=1; unit<<=1;',
     'total>>=1; free>>=0; unit<<=1;', 'test_disk_space_scaling_boundaries'),
    ('round logical free count upward', 'REDIR.C', 'total>>=1; free>>=1; unit<<=1;',
     'total>>=1; free=(free+1)>>1; unit<<=1;', 'test_disk_space_scaling_boundaries'),
    ('scan FATs on every close', 'RWOPS.C', '!code && !closing && rw_flush()',
     '!code && rw_flush()', 'test_twenty_closes_do_not_rescan_fats'),
    ('skip explicit commit verification', 'RWOPS.C', '!code && !closing && rw_flush()',
     '!code && 0 && rw_flush()', 'test_commit_detects_untouched_mirror_corruption_after_close'),
    ('discard dirty session on live remount', 'REDIR.C',
     'if (sd_write_enabled && media_online && rw_flush()) {\n        result=fs_error;',
     'if (0) {\n        result=fs_error;', 'test_online_remount_flushes_dirty_closed_files_first'),
    ('write through read-only open', 'RWOPS.C',
     'if (!(get16(sft+2)&3)) return error(E_ACCESS);',
     'if (0) return error(E_ACCESS);', 'test_access_modes_and_invalid_open_modes'),
    ('read through write-only open', 'REDIR.C',
     'if ((get16(sft+2)&3)==1)', 'if (0)', 'test_access_modes_and_invalid_open_modes'),
    ('ignore sharing denial', 'RWOPS.C',
     'if (shared(&f,mode))', 'if (shared(&f,mode) && 0)',
     'test_sharing_denial_both_directions_and_compatibility_processes'),
    ('ignore locked reads', 'REDIR.C',
     'if (locked(file,position,count))', 'if (locked(file,position,count) && 0)',
     'test_region_locks_guard_reads_writes_truncation_and_final_close'),
    ('ignore locked writes', 'RWOPS.C',
     'if (locked(file,range_start,range_length))',
     'if (locked(file,range_start,range_length) && 0)',
     'test_region_locks_guard_reads_writes_truncation_and_final_close'),
    ('release locks before final close', 'RWOPS.C',
     'if (!get16(sft)) { unlock_file(sft);', 'if (1) { unlock_file(sft);',
     'test_region_locks_guard_reads_writes_truncation_and_final_close'),
    ('lose duplicate reference count', 'RWOPS.C', 'get16(sft)-1', '0',
     'test_region_locks_guard_reads_writes_truncation_and_final_close'),
    ('lose shared SFT size updates', 'RWOPS.C',
     'put32(files[i].sft+17,FILE_DISK(file).size);', 'put32(files[i].sft+17,0);',
     'test_shared_handles_refresh_first_cluster_size_and_preserve_positions'),
    ('lose committed timestamp', 'RWOPS.C',
     'rw_metadata(&FILE_DISK(file),FILE_DISK(file).attr,time,date)',
     'rw_metadata(&FILE_DISK(file),FILE_DISK(file).attr,time^1,date)',
     'test_set_file_timestamp_via_sft_commit_persists'),
    ('report short write as full write', 'RWOPS.C', 'regs.cx=done;', 'regs.cx=count;',
     'test_disk_full_returns_short_write_and_published_prefix'),
    ('use incorrect rename buffer', 'RWOPS.C',
     'destination=dos_sda+dos_name_offset+128;',
     'destination=dos_sda+dos_name_offset+80;',
     'test_directory_attributes_rename_delete_and_cwd_interlock'),
    ('allow delete with live handle', 'RWOPS.C',
     'if (file_busy(&f))', 'if (file_busy(&f) && 0)',
     'test_directory_attributes_rename_delete_and_cwd_interlock'),
]


def main():
    for name, filename, before, after, test in CASES:
        with tempfile.TemporaryDirectory(prefix='otter-rwredir-mutation-') as directory:
            work = Path(directory)
            for relative in ('OTTER.H', 'RWSD.H', 'RWFS.H', 'SDRW.C', 'RWFS.C',
                             'REDIR.C', 'RWOPS.C', 'FAT32.C', 'tests/HOSTRD.C',
                             'tests/HOSTRWD.C', 'tests/HOSTRW.C',
                             'tests/emulation/slot_model.c', 'tests/emulation/slot_model.h',
                             'tests/kit_fixture.py', 'tests/fixture.py'):
                target = work/relative; target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT/relative, target)
            target = work/filename; original = target.read_text()
            assert before in original, f'Mutation anchor changed: {name}'
            target.write_text(original.replace(before, after))
            env = dict(os.environ, OTTER_TEST_SOURCE_ROOT=str(work))
            env.pop('OTTER_TEST_COVERAGE', None)
            result = subprocess.run([sys.executable, '-m', 'unittest', '-v',
                test if '.' in test else 'test_rw_redirector.WritableRedirectorTests.'+test], cwd=ROOT/'tests',
                env=env, capture_output=True, text=True)
            if result.returncode==0 or 'FAILED (failures=' not in result.stderr:
                print(result.stdout+result.stderr)
                raise RuntimeError(f'Mutation not detected by an assertion: {name}')
            print('DETECTED: '+name, flush=True)
    print(f'PASS: {len(CASES)} writable redirector mutations detected')


if __name__ == '__main__':
    main()
