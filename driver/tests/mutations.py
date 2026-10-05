#!/usr/bin/env python3
"""Check that targeted regressions are caught. Mutate temporary source copies only.

A compiler error does not count as detection; each mutation must build and then
fail an assertion in an existing test. This is a targeted sensitivity check, not
an exhaustive mutation score.
"""
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
CASES = [
    ("allow writes", "REDIR.C", "if ((mode&3)!=0)", "if (0)",
     "test_redirector.RedirectorTests.test_read_only_open_actions_and_mutations"),
    ("skip removal checks", "REDIR.C", "if (sd_check_media())", "if (0)",
     "test_redirector.RedirectorTests.test_removal_and_identity_change_reject_cached_reads"),
    ("keep stale search generation", "REDIR.C", "++media_epoch", "media_epoch+=0",
     "test_redirector.RedirectorTests.test_mount_generation_and_empty_slot_recovery"),
    ("lose reference counts", "REDIR.C", "get16(sft)-1", "0",
     "test_redirector.RedirectorTests.test_capacity_reference_counts_and_slot_reuse"),
    ("truncate every read", "REDIR.C", "count=regs.cx", "count=1",
     "test_redirector.RedirectorTests.test_reads_eof_zero_count_and_independent_positions"),
    ("advance failed FAT hop", "FAT32.C", "result=next_cluster(cursor->cluster, &next);",
     "++cursor->index; result=next_cluster(cursor->cluster, &next);",
     "test_fs.FilesystemTests.test_invalid_and_premature_chain_end_never_advance_file_cursor"),
    ("reuse stale sector cache", "FAT32.C", "void fs_invalidate(void) { data_lba = fat_lba = 0xffffffffUL; }",
     "void fs_invalidate(void) { }",
     "test_fs.FilesystemTests.test_invalidation_forces_fresh_data_and_fat"),
    ("allow remount with open handles", "REDIR.C", "if (open_count()) return E_ACCESS;",
     "if (0) return E_ACCESS;",
     "test_redirector.RedirectorTests.test_duplicate_stale_references_block_remount_until_final_close"),
    ("lose active FAT selection", "FAT32.C", "fatsz*active", "fatsz*0",
     "test_fs.FilesystemTests.test_superfloppy_active_fat_and_multi_sector_clusters"),
]


def main():
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"),
                    "-p", "test_*.py"], check=True)
    for name, filename, before, after, test in CASES:
        with tempfile.TemporaryDirectory(prefix="otter-mutation-") as directory:
            work = pathlib.Path(directory)
            for relative in ["OTTER.H", "REDIR.C", "FAT32.C", "tests/HOSTRD.C", "tests/HOSTSD.C"]:
                target = work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            target = work / filename
            original = target.read_text()
            if before not in original:
                raise RuntimeError(f"Mutation location changed: {name}; update this check")
            target.write_text(original.replace(before, after))
            env = dict(os.environ, OTTER_TEST_SOURCE_ROOT=str(work))
            env.pop("OTTER_TEST_COVERAGE", None)
            result = subprocess.run([sys.executable, "-m", "unittest", "-v", test],
                                    cwd=ROOT / "tests", env=env, capture_output=True, text=True)
            if result.returncode == 0 or "FAILED (failures=" not in result.stderr:
                print(result.stdout + result.stderr)
                raise RuntimeError(f"Mutation not caught by an assertion: {name}")
            print(f"DETECTED: {name}", flush=True)
    print(f"PASS: {len(CASES)} targeted regressions detected")


if __name__ == "__main__":
    main()
