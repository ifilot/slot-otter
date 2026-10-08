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
    ('read file allocation slack','if (file->size - pos < count)',
     'if (0 && file->size - pos < count)',
     'test_file_allocation.Fat16AllocationTests.test_small_appends_leave_slack_untouched_and_bound_wire_work'),
    ('omit directory growth initialization','next = allocate(1);',
     'next = allocate(0);',
     'test_file_allocation.Fat16AllocationTests.test_directory_growth_clears_new_cluster_before_linking'),
    ('clear regular-file clusters again','c = allocate(0);',
     'c = allocate(1);',
     'test_file_allocation.Fat16AllocationTests.test_small_appends_leave_slack_untouched_and_bound_wire_work'),
    ('omit new directory initialization','f->first = f->last = allocate(1);',
     'f->first = f->last = allocate(0);',
     'test_file_allocation.Fat32AllocationTests.test_directory_allocation_clears_stale_entries'),
    ('expose stale extension bytes','} else memset(block+offset,0,n);',
     '} else memset(block+offset,0xa5,n);',
     'test_file_allocation.Fat16AllocationTests.test_gap_extension_truncation_and_reuse_initialize_visible_bytes'),

    ('skip fast dirty-flag FAT header check','if (rw_skip_fat_check && head_mirrors()) return -1;\n  if (volume.fat_bits==16) {',
     'if (0) return -1;\n  if (volume.fat_bits==16) {',
     'test_skipfatcheck_still_checks_fat_sector_zero_before_mount_and_write'),
    ('ignore fast mount option','if (!rw_skip_fat_check && mirrors()) return -1;',
     'if (mirrors()) return -1;', 'test_skipfatcheck_reduces_mount_reads_without_writes'),
    ('skip strict mount scan','if (!rw_skip_fat_check && mirrors()) return -1;',
     'if (0) return -1;', 'test_skipfatcheck_reduces_mount_reads_without_writes'),
    ('skip fast mount FAT header check','if (rw_skip_fat_check && head_mirrors()) return -1;\n  if (fsinfo_lba',
     'if (0) return -1;\n  if (fsinfo_lba', 'test_skipfatcheck_still_checks_fat_sector_zero_before_mount_and_write'),
    ('skip dirty commit comparison in fast mode','if (mirrors() || mark_clean(1)) return -1;',
     'if ((!rw_skip_fat_check && mirrors()) || mark_clean(1)) return -1;',
     'test_skipfatcheck_untouched_mismatch_is_detected_at_dirty_commit'),
    ('skip modified FAT comparisons in fast mode','if (mirrored) for (i=1;i<fat_count;++i) {',
     'if (mirrored && !rw_skip_fat_check) for (i=1;i<fat_count;++i) {',
     'test_skipfatcheck_still_compares_modified_fat_sectors'),
    ('capture physical tail instead of logical EOF','if (at && *count==wanted) *at=c;',
     'if (at && *count>=wanted) *at=c;',
     'test_append_uses_logical_eof_with_nonempty_surplus_chain'),
    ('stop proof at logical EOF','    if (n>=0x0ffffff8UL) {',
     '    if (*count==wanted || n>=0x0ffffff8UL) {',
     'test_corrupt_surplus_tail_still_refuses_append_before_writes'),
    ('omit forward overwrite cluster advance','    if (count && !(pos&(((U32)volume.spc<<9)-1UL))) {',
     '    if (0) {',
     'test_fragmented_overwrite_forward_walk_preserves_edges'),
    ('treat free link as end of nonempty chain','    if (n>=0x0ffffff8UL) {',
     '    if (!n || n>=0x0ffffff8UL) {',
     'test_free_or_reserved_link_is_never_valid_nonempty_chain'),
    ('retain FAT cache across mutations','  fs_invalidate();\n  if (!begun',
     '  if (!begun','test_fresh_chain_validation_detects_crc_fault_despite_warm_cache'),
    ('retain stale FAT after stores','  fs_invalidate_sector(lba);\n  result=sd_write(lba,p);',
     '  result=sd_write(lba,p);','test_fat_cache_invalidation_after_truncate_and_remount'),
    ('overwrite partial sector without preimage','    if ((offset || n!=512) && read_sector(lba, block))\n      return -1;\n#ifndef HOST_TEST',
     '    if (0 && read_sector(lba, block)) return -1;\n#ifndef HOST_TEST',
     'test_noverify_full_sector_replaces_without_preimage_partial_preserves'),
    ('scan a nonexistent single-FAT mirror','if (!mirrored || fat_count<2) return 0;',
     'if (!mirrored) return 0;',
     'test_single_fat_mount_skips_empty_comparison_and_preserves_writes'),
    ('hide directory chain read error','if (chain_valid(parent)) return -1;',
     'if (chain_valid(parent)) return fail(E_INVALID);',
     'test_clean_preflight_read_errors_remain_transport_errors'),
    ('hide rmdir directory read error','if (result < 0)\n    return -1;',
     'if (result < 0) return fail(E_INVALID);',
     'test_rmdir_scan_preserves_read_error'),
    ('permit writes after dirty FAT inconsistency','static int inconsistent(void) {\n  if (dirty) sd_diag.poisoned=1;',
     'static int inconsistent(void) {\n  if (0) sd_diag.poisoned=1;',
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
    ('permit forged slot alignment','(offset&31) || offset>480',
     '(offset&0) || (offset>480 && offset==0)',
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
    ('omit mirrored FAT writes','if (store(first_fat+(U32)i*rw_fatsz+fs_fat_sector(c),block)) return -1;',
     'if (0) return -1;',
     'test_new_root_file_roundtrip_and_originals_preserved'),
    ('ignore dot-like files in rmdir',
     'if ((memcmp(entry,".          ",11) && memcmp(entry,"..         ",11)) || entry[11]!=16)',
     'if (entry[0]!=\'.\')',
     'test_dot_prefixed_non_dot_entry_blocks_rmdir'),
    ('FAT16 high word overwrite','if (volume.fat_bits==32)\n    put16(block + f->offset + 20',
     'if (1)\n    put16(block + f->offset + 20','test_fat16.Fat16Tests.test_fat16_reserved_directory_high_word_is_preserved'),
    ('FAT16 wide entry write','if (volume.fat_bits==16) put16(block+offset,(U16)value);',
     'if (volume.fat_bits==16) put32(block+offset,value);','test_fat16.Fat16Tests.test_two_byte_fat_store_preserves_neighbor_entry'),
    ('FAT16 ignore full root','if (!free_lba) return fail(E_FULL);',
     'if (!free_lba) return fail(E_INVALID);','test_fat16.Fat16Tests.test_root_full_fails_without_allocating_then_reuses_deleted'),
    ('FAT16 wrong clean bit','if (clean) flags|=0x8000UL; else flags&=~0x8000UL;',
     'if (clean) flags|=0x08000000UL; else flags&=~0x08000000UL;','test_fat16.Fat16Tests.test_clean_flags_use_fat16_bits_and_keep_mirrors'),


]


def main():
    for name,before,after,test in CASES:
        with tempfile.TemporaryDirectory(prefix='otter-rwfs-mutation-') as folder:
            work=Path(folder)
            for relative in ('OTTER.H','RWSD.H','RWFS.H','SDRW.C','RWFS.C','FAT32.C',
                             'tests/HOSTRW.C','tests/emulation/slot_model.c','tests/emulation/slot_model.h',
                             'tests/kit_fixture.py'):
                target=work/relative; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copyfile(ROOT/relative,target)
            # build.py imports the ordinary fixture generator via the tests path.
            (work/'tests/fixture.py').write_bytes((ROOT/'tests/fixture.py').read_bytes())
            target=work/'RWFS.C';source=target.read_text()
            if source.count(before)!=1: raise RuntimeError('Mutation location changed: '+name)
            target.write_text(source.replace(before,after))
            env=dict(os.environ,OTTER_TEST_SOURCE_ROOT=str(work));env.pop('OTTER_TEST_COVERAGE',None)
            result=subprocess.run([sys.executable,'-m','unittest','-v',
                test if '.' in test else 'test_rw_fs.ResidentFilesystemTests.'+test],cwd=ROOT/'tests',env=env,
                text=True,capture_output=True)
            if result.returncode==0 or 'FAILED (failures=' not in result.stderr:
                print(result.stdout+result.stderr)
                raise RuntimeError('Mutation not caught by runtime assertion: '+name)
            print('DETECTED: '+name,flush=True)
    print(f'PASS: {len(CASES)} resident filesystem mutations detected')


if __name__=='__main__':main()
