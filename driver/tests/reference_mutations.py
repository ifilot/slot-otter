#!/usr/bin/env python3
"""Check critical write regressions on temporary source copies; compile errors do not count."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
CASES=[
 ('accept idle state as successful CRC rejection','WSD.C','result = wt_r1 == 8 ? 0 : error(WT_CRC);',
  'result = (wt_r1 & 8) ? 0 : error(WT_CRC);','test_command_crc_probe_does_not_accept_idle_plus_crc_error'),
 ('release CS before CRC-rejection completion','WSD.C','if (code == WT_CRC) {',
  'if (0) {','test_rejected_data_busy_is_completed_before_cs_release'),
 ('lose bad-command response snapshot','WSD.C','wt_bad_cmd_r1 = wt_r1;',
  'wt_bad_cmd_r1 = 255;','test_bad_command_trace_keeps_crc_r1_and_response_after_recovery'),
 ('run command error in data-only mode','WTEST.C','if (wt_probe_only != 2) {',
  'if (1) {','test_data_only_probe_retains_rejection_trace_before_recovery'),
 ('run data error in command-only mode','WTEST.C','if (wt_probe_only != 1) {',
  'if (1) {','test_command_only_probe_full_filesystem_and_persistence'),
 ('skip immediate scratch read after CRC error','WTEST.C','result = sd_read(wf_start + 8, observed);',
  'memcpy(observed, saved, 512); wt_error = 0; result = 0;','test_data_probe_read_timeout_reproduces_intenso_without_command_probe'),
 ('omit poison after failed post-probe read','WTEST.C','    wt_poison = 1;\n    if (!result) { diag_dump("saved-original", saved);',
  '    if (!result) { diag_dump("saved-original", saved);','test_data_probe_read_timeout_reproduces_intenso_without_command_probe'),
 ('reject ready CMD55','WSD.C','if (wt_r1 != 0 && wt_r1 != 1) { finish(); return error(WT_MEDIA); }',
  'if (wt_r1 != 1) { finish(); return error(WT_MEDIA); }','test_ready_cmd55_still_requires_acmd41_and_card_validation'),
 ('omit pre-fault patterns','WTEST.C','if (raw_patterns("PRE-FAULT")) goto out;',
  'if (0) goto out;','test_ff_corruption_before_faults_stops_without_negative_probes'),
 ('omit post-probe patterns','WTEST.C','if (raw_patterns(phase)) return 0;',
  'if (0) return 0;','test_ff_corruption_only_after_faults_has_unambiguous_phase'),
 ('lose recovery status guard','WSD.C','(wt_r1 == 0 && wt_status != 0)',
  '(0)','test_probe_recovery_never_hides_programming_status_error'),
 ('lose startup trace final record','WSD.C','wt_init_count < 64 ? wt_init_count++ : 63',
  'wt_init_count < 64 ? wt_init_count++ : 0','test_startup_trace_retains_last_command_after_overflow'),
 ('accept busy as CMD13 status','WSD.C','if (incoming != 255)',
  'if (0 && incoming != 255)','test_busy_during_cmd13_transmission_is_safe_stop'),
 ('omit post-response readiness confirmation','WSD.C','(trace_phase == 1 ? 2 : 1)',
  '1','test_late_busy_does_not_hide_programming_error'),
 ('skip valid CRC-OFF control','WTEST.C','REQUIRE(!wt_write(wf_start + 8, chunk, 0),\n                "CRC-OFF valid-data-CRC control: exact write and readback");',
  'REQUIRE(1, "CRC-OFF valid-data-CRC control: exact write and readback");','test_accepted_ignored_off_write_has_exact_diagnostics'),
 ('lose per-write busy polls','WSD.C','wt_write_busy_polls = polls;',
  'wt_write_busy_polls = 0;','test_write_busy_trace_is_per_write_and_resets'),
 ('omit late busy phase trace','WSD.C','wt_status_busy_polls = polls;',
  'wt_status_busy_polls = 0;','test_late_busy_trace_captures_status_ready_wait'),
 ('replace mismatch error with repeat error','WSD.C','return error(result ? wt_error : WT_VERIFY);',
  'return error(result ? wt_error : wt_repeat_error);','test_repeat_crc_failure_preserves_first_mismatch'),
 ('lose failed packet CRC evidence','WSD.C','  wt_packet_complete = 1;',
  '  wt_packet_complete = 0;','test_crc_failure_log_retains_untrusted_payload'),
 ('hide empty-file cluster error','WTEST.C','if (!size && file.first) { wt_error = WT_VERIFY; return -1; }',
  'if (!size && file.first) { return -1; }','test_empty_file_with_cluster_reports_verify_error'),
 ('mask marker read CRC','WFS.C','if (fs_read(&cursor, 0, block, sizeof(tag) - 1, &done))\n    return wt_error ? -1 : fail(WT_GUARD);',
  'if (fs_read(&cursor, 0, block, sizeof(tag) - 1, &done))\n    return fail(WT_GUARD);','test_marker_transport_crc_error_preserved'),
 ('replace NOCRC dummy with computed CRC','WSD.C','if (wt_no_crc) crc = 0xffff;', 'if (0) crc = 0xffff;','test_nocrc_init_without_cmd59_and_dummy_data_crc'),
 ('lose original write response token','WSD.C','wt_write_token = wt_token;', 'wt_write_token = 255;','test_accepted_ignored_off_write_has_exact_diagnostics'),
 ('accept a failed first readback after repeat','WSD.C','wt_repeat_valid = !wt_repeat_error;',
  'wt_repeat_valid = !wt_repeat_error; if (wt_repeat_valid && !memcmp(p, wt_repeat, 512)) return 0;','test_repeat_matching_expected_never_clears_first_failure'),
 ('skip receive CRC in NOCRC mode','WSD.C','if (crc != wt_packet_calculated)',
  'if (!wt_no_crc && crc != wt_packet_calculated)','test_nocrc_still_checks_read_crc'),
 ('require SPI ready before CMD0','WSD.C','if (number != 0 && (number == 13 && in_write && wt_trace\n      ? wait_ready_record(90, 2) : wait_ready(90)))',
  'if (wait_ready(90))','test_native_nonready_card_receives_reset_and_warm_restart'),
 ('omit exact startup clock train','WSD.C','    idle_clocks();','    if (0) idle_clocks();','test_native_nonready_card_receives_reset_and_warm_restart'),
 ('sample byte without settling','WSD.C','  wt_reg_write(0, b);\n  settle();','  wt_reg_write(0, b);','test_native_card_delayed_byte_completion_reads_and_writes'),
 ('hide preflight backup CRC error','WFS.C','if (sd_read(wf_start + s + 6, other))\n      return -1;',
  'if (sd_read(wf_start + s + 6, other))\n      return fail(WT_GUARD);','test_diagnostic_backup_crc_error_is_not_safety_error'),
 ('allow nonhint FSInfo differences','WFS.C','if ((i < 488 || i >= 496) && block[i] != other[i])',
  'if (0 && block[i] != other[i])','test_allow_hints_cannot_bypass_nonhint_difference'),
 ('allow hint differences without opt-in','WFS.C','if (!wf_allow_hints) return fail(WT_GUARD);',
  'if (0) return fail(WT_GUARD);','test_diagnostic_fsinfo_hint_mismatch_is_precise'),
 ('omit board MISO pull initialization','WSD.C','  wt_pull_high();','  /* omitted */','test_cold_start_initializes_board_and_idle_clocks'),
 ('omit CMD0 startup retries','WSD.C','if (wt_reset_attempts == 100 ||','if (wt_reset_attempts == 1 ||','test_cold_start_retries_unanswered_cmd0'),
 ('wrong transmitted data CRC','WSD.C','crc = wt_crc16(p, 512);','crc = 0;','test_valid_write_and_busy'),
 ('omit CRC enable before ACMD41','WSD.C','    crc_enabled = 1;',
  '    crc_enabled = 1; wt_crc_mode(0);','test_strict_card_even_with_crc_disabled'),
 ('ignore read CRC','WSD.C','if (crc != wt_packet_calculated)',
  'if (0 && crc != wt_packet_calculated)','test_read_crc_error'),
 ('omit post-programming status','WSD.C','if (wt_r1 || wt_status)', 'if (0)','test_delayed_programming_error_stops'),
 ('disable block-write fence','WSD.C','if (!armed || lba < allowed_first || lba >= allowed_end)',
  'if (0)','test_write_fence_without_arm'),
 ('ignore corrupt readback','WSD.C','if (result || memcmp(p, verify_buffer, 512))',
  'if (result || (p == NULL && verify_buffer[0] == 0))','test_corrupt_readback_stops'),
 ('omit FAT mirror','WFS.C','if (store(lba, block) || store(lba + wf_fatsz, block))',
  'if (store(lba, block))','test_full_suite_spc1_persistence_and_protected_files'),
 ('lose published size','WFS.C','put32(block + f->offset + 28, f->size);',
  'put32(block + f->offset + 28, 0);','test_full_suite_spc1_persistence_and_protected_files'),
 ('leak deleted clusters','WFS.C','if (store(f->lba, block) || release_chain(f->first))',
  'if (store(f->lba, block))','test_partial_append_overwrite_truncate_delete'),
]

def main():
 for name,file,before,after,test in CASES:
  with tempfile.TemporaryDirectory(prefix='otter-write-mutation-') as folder:
   work=Path(folder)/'driver'
   shutil.copytree(ROOT,work,ignore=shutil.ignore_patterns('dist','logs','__pycache__','*.EXE','*.MAP','*.OBJ'))
   target=work/'tests/reference'/file; original=target.read_text()
   if original.count(before)!=1: raise RuntimeError(f'Mutation location changed: {name}')
   target.write_text(original.replace(before,after))
   env=dict(os.environ,OTTER_TEST_SOURCE_ROOT=str(work)); env.pop('OTTER_TEST_COVERAGE',None)
   result=subprocess.run([sys.executable,'-m','unittest','-v','test_write.WriteTests.'+test],
                         cwd=ROOT/'tests',env=env,text=True,capture_output=True)
   if result.returncode==0 or 'FAILED (failures=' not in result.stderr:
    print(result.stdout+result.stderr); raise RuntimeError(f'Mutation not detected by an assertion: {name}')
   print('DETECTED: '+name,flush=True)
 print(f'PASS: {len(CASES)} critical write regressions detected')
if __name__=='__main__': main()
