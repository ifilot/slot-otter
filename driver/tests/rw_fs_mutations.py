#!/usr/bin/env python3
"""Filesystem safety mutations must compile and fail a behavioral assertion."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
CASES=[
    ('scan a nonexistent single-FAT mirror','if (!mirrored || fat_count<2) return 0;',
     'if (!mirrored) return 0;',
     'test_single_fat_mount_skips_empty_comparison_and_preserves_writes'),
    ('hide directory chain read error','if (chain_valid(parent)) return -1;',
     'if (chain_valid(parent)) return fail(E_INVALID);',
     'test_clean_preflight_read_errors_remain_transport_errors'),
    ('hide rmdir directory read error','if (result < 0)\n    return -1;',
     'if (result < 0) return fail(E_INVALID);',
     'test_rmdir_scan_preserves_read_error'),
    ('permit writes after dirty FAT inconsistency','if (dirty) sd_diag.poisoned=1;',
     'if (0) sd_diag.poisoned=1;',
     'test_mirror_inconsistency_during_dirty_session_stops_later_mutations'),
    ('ignore backup boot geometry','get16(block+510)!=0xaa55 || memcmp(block+11,other+11,41)',
     'get16(block+510)!=0xaa55 || memcmp(block+11,other+11,0)',
     'test_backup_boot_geometry_mismatch_refuses_mount_before_writes'),
    ('skip gap zeroing','if (pos>f->size && rw_resize(f,pos)) return -1;',
     'if (pos>f->size) f->size=pos;',
     'test_write_past_eof_zeros_gap_and_overwrite_append_combination'),
    ('leave stale gap contents','} else memset(block+offset,0,n);',
     '} else memset(block+offset,0x73,n);',
     'test_zero_length_write_truncates_and_extends_with_zeros'),
    ('lose partial disk-full size publication','if (publish(f)) return -1;\n            return fail(E_FULL);',
     'return fail(E_FULL);',
     'test_partial_disk_full_publishes_only_completed_bytes'),
    ('ignore file allocation length','if (count<needed || (f->directory && !count))',
     'if ((count<needed && needed==0) || (f->directory && !count))',
     'test_corrupt_and_short_chains_refuse_overwrite_before_mutation'),
    ('permit forged slot alignment','f->offset>480 || (f->offset&31)',
     '(f->offset>480 && f->offset==0) || (f->offset&0)',
     'test_overflow_write_and_forged_directory_location_refuse_without_writes'),
    ('ignore readonly deletion','if (f->directory || (f->attr&1))\n    return fail(E_ACCESS);',
     'if (f->directory) return fail(E_ACCESS);',
     'test_readonly_attribute_enforced_and_timestamp_persists'),
    ('leak deleted clusters','store(f->lba, block) || release_chain(f->first)',
     'store(f->lba, block)',
     'test_free_count_tracks_allocation_and_release'),
    ('skip long-name cleanup','  if (chain_valid(f->parent) || read_sector(f->lba,block)) return -1;',
     '  if (f->parent) return 0;\n  if (chain_valid(f->parent) || read_sector(f->lba,block)) return -1;',
     'test_delete_short_alias_erases_associated_long_name_entries'),
    ('preserve long-name entries instead of erase','block[off]=229;',
     'block[off]=block[off];',
     'test_rename_short_alias_erases_associated_long_name_entries'),
    ('omit moved directory parent update','next=parent==volume.root?0:parent;',
     'next=f->parent==volume.root?0:f->parent;',
     'test_move_directory_updates_parent_and_refuses_descendant'),
    ('allow move into descendant','if (c==f->first) return fail(E_ACCESS);',
     'if (0) return fail(E_ACCESS);',
     'test_move_directory_updates_parent_and_refuses_descendant'),
    ('expose entries beyond old end marker','block[next_off]=0;',
     'block[next_off]=block[next_off];',
     'test_create_at_end_marker_does_not_expose_stale_entries'),
    ('ignore inactive FAT selection','volume.fat!=first_fat+(U32)active_fat*rw_fatsz',
     'volume.fat!=first_fat',
     'test_active_fat_leaves_inactive_copy_untouched'),
    ('omit mirrored FAT writes','if (store(first_fat+(U32)i*rw_fatsz+(c>>7),block)) return -1;',
     'if (0) return -1;',
     'test_new_root_file_roundtrip_and_originals_preserved'),
    ('ignore dot-like files in rmdir',
     'if ((memcmp(entry,".          ",11) && memcmp(entry,"..         ",11)) || entry[11]!=16)',
     'if (entry[0]!=\'.\')',
     'test_dot_prefixed_non_dot_entry_blocks_rmdir'),
]


def main():
    for name,before,after,test in CASES:
        with tempfile.TemporaryDirectory(prefix='otter-rwfs-mutation-') as folder:
            work=Path(folder)
            for relative in ('OTTER.H','RWSD.H','RWFS.H','SDRW.C','RWFS.C','FAT32.C',
                             'tests/HOSTRW.C','emulation/slot_model.c','emulation/slot_model.h',
                             'write/build.py','hardware/build.py'):
                target=work/relative; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/relative,target)
            # build.py imports the ordinary fixture generator via the tests path.
            (work/'tests/fixture.py').write_bytes((ROOT/'tests/fixture.py').read_bytes())
            target=work/'RWFS.C';source=target.read_text()
            if source.count(before)!=1: raise RuntimeError('Mutation location changed: '+name)
            target.write_text(source.replace(before,after))
            env=dict(os.environ,OTTER_TEST_SOURCE_ROOT=str(work));env.pop('OTTER_TEST_COVERAGE',None)
            result=subprocess.run([sys.executable,'-m','unittest','-v',
                'test_rw_fs.ResidentFilesystemTests.'+test],cwd=ROOT/'tests',env=env,
                text=True,capture_output=True)
            if result.returncode==0 or 'FAILED (failures=' not in result.stderr:
                print(result.stdout+result.stderr)
                raise RuntimeError('Mutation not caught by runtime assertion: '+name)
            print('DETECTED: '+name,flush=True)
    print(f'PASS: {len(CASES)} resident filesystem mutations detected')


if __name__=='__main__':main()
