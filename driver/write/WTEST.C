/* Standalone direct-I/O write suite. No resident driver, no DOS S: writes. */
#include "WRITE.H"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#ifndef HOST_TEST
#include <dir.h>
#include <stdlib.h>
#endif
static FILE *logfile;
static unsigned failures, checks;
static int log_failed;
static U8 chunk[512], saved[512], observed[512];
static void diag_dump(const char *name, const U8 *p);
static void logline(const char *format, ...) {
  va_list a;
  va_start(a, format);
  vprintf(format, a);
  va_end(a);
  fflush(stdout);
  if (logfile) {
    va_start(a, format);
    vfprintf(logfile, format, a);
    va_end(a);
    if (fflush(logfile) != 0 || ferror(logfile)) {
      if (!log_failed)
        puts("STOP: local log write failed; SD writes disarmed.");
      log_failed = 1;
      wt_disarm();
      wt_poison = 1;
      wt_error = 113;
    }
  }
}
static void write_trace(void) {
  unsigned i, n = 0;
  if (!wt_trace || log_failed) return;
  logline("WRITE TRACE: LBA=%lu CRC_mode=%s data_CRC=%04X calculated=%04X "
          "CMD24_R1=%02X response=%02X CMD13_R1=%02X status=%02X\n",
          (unsigned long)wt_write_lba, wt_write_crc ? "ON" : "OFF",
          wt_sent_crc, wt_calculated_crc, wt_write_r1, wt_write_token,
          wt_program_r1, wt_program_status);
  logline("WRITE RESPONSE: polls=%u bytes:", wt_response_count);
  for (i = 0; i < wt_response_count; ++i) logline(" %02X", wt_response_bytes[i]);
  logline("\n");
  logline("WRITE BUSY: entered=%u nonready_polls=%lu ticks=%lu samples:",
          wt_busy_entered, wt_write_busy_polls, wt_write_busy_ticks);
  for (i = 0; i < wt_busy_sample_count; ++i) logline(" %02X", wt_busy_samples[i]);
  logline("\nSTATUS READY: entered=%u nonready_polls=%lu ticks=%lu samples:",
          wt_status_entered, wt_status_busy_polls, wt_status_busy_ticks);
  for (i = 0; i < wt_status_sample_count; ++i) logline(" %02X", wt_status_samples[i]);
  logline("\nCMD13 TRANSMIT RX:");
  for (i = 0; i < wt_cmd13_rx_count; ++i) logline(" %02X", wt_cmd13_rx[i]);
  logline("\nREADBACK POLICY: card_CRC=%s incoming_CRC16=verified\n",
          wt_readback_crc == 255 ? "not reached" : wt_readback_crc ? "ON" : "OFF");
  if (!wt_readback_valid) {
    logline("READBACK: no CRC-validated payload available\n");
    return;
  }
  for (i = 0; i < 512; ++i) {
    if (wt_expected[i] != wt_readback[i]) {
      if (n < 32)
        logline("WRITE DIFF: offset=%u expected=%02X actual=%02X\n",
                i, wt_expected[i], wt_readback[i]);
      ++n;
    }
  }
  logline("READBACK: differing_bytes=%u matches_original_scratch=%s "
          "repeat_valid=%u repeat_error=%u\n", n,
          wt_write_lba == wf_start + 8 && !memcmp(saved, wt_readback, 512) ?
            "YES" : "NO", wt_repeat_valid, wt_repeat_error);
  if (wt_repeat_valid)
    logline("REPEAT: matches_expected=%s matches_first=%s "
            "matches_original_scratch=%s\n",
            !memcmp(wt_expected, wt_repeat, 512) ? "YES" : "NO",
            !memcmp(wt_readback, wt_repeat, 512) ? "YES" : "NO",
            wt_write_lba == wf_start + 8 && !memcmp(saved, wt_repeat, 512) ? "YES" : "NO");
  if (n) {
    diag_dump("expected", wt_expected);
    diag_dump("readback", wt_readback);
    if (wt_repeat_valid) diag_dump("repeat", wt_repeat);
  }
}
static int check(int ok, const char *label) {
  unsigned i;
  logline("%03u %s: %s\n", ++checks, ok ? "PASS" : "FAIL", label);
  if (log_failed)
    ok = 0;
  if (ok && !log_failed) wt_error = 0;
  if (!ok) {
    if (!wt_error) wt_error = WT_VERIFY;
    ++failures;
    logline("PREFLIGHT: %s\n", wf_preflight);
    logline("TRANSPORT: phase=%s CMD0_packets=%u initial_MISO=%02X\n",
            wt_phase, wt_cmd0_sent, wt_startup_miso);
    logline("DETAIL: error=%u stage=%u LBA=%lu R1=%02X token=%02X status=%02X "
            "poison=%u\n",
            wt_error, wt_stage, (unsigned long)wt_lba, wt_r1, wt_token,
            wt_status, wt_poison);
    write_trace();
    if (wt_packet_polls) {
      logline("READ TOKEN TRACE: polls=%lu ticks=%lu samples:",
              (unsigned long)wt_packet_polls, (unsigned long)wt_packet_ticks);
      for (i = 0; i < wt_packet_sample_count; ++i) logline(" %02X", wt_packet_tokens[i]);
      logline("\n");
    }
    if (wt_packet_complete && wt_packet_crc != wt_packet_calculated) {
      logline("READ CRC: clocked_bytes=%u received=%04X calculated=%04X "
              "payload=UNTRUSTED source=%s (not used for verification)\n",
              wt_packet_count, wt_packet_crc, wt_packet_calculated,
              wt_trace && wt_repeat_error ? "repeat" : "primary");
      if (wt_packet_count == 512) diag_dump("untrusted", wt_packet_data);
    }
  }
  return ok;
}
#define REQUIRE(e, label)                                                      \
  do {                                                                         \
    if (!check((e), (label)))                                                  \
      goto out;                                                                \
  } while (0)
/* Include the sector number: adjacent sectors must not have identical data. */
static U8 pattern(U32 position, unsigned seed) {
  return (U8)(position * 7 + seed + (position >> 9) * 13 +
              (position >> 17) * 19);
}
static void fill(U32 pos, unsigned n, unsigned seed) {
  unsigned i;
  for (i = 0; i < n; ++i)
    chunk[i] = pattern(pos + i, seed);
}
static int append_pattern(WFile *f, U32 size, unsigned seed) {
  U32 pos = f->size;
  unsigned n;
  while (pos < size) {
    n = (unsigned)(size - pos > 512 ? 512 : size - pos);
    fill(pos, n, seed);
    if (wf_append(f, chunk, n))
      return -1;
    pos += n;
    if (!(pos % 4096UL) || pos == size) {
      logline("PROGRESS: append bytes=%lu/%lu accepted_writes=%lu\n",
              (unsigned long)pos, (unsigned long)size, (unsigned long)wt_writes);
      if (log_failed) return -1;
    }
  }
  return 0;
}
static int verify_file(const char *path, U32 size, unsigned seed, int patched) {
  U8 entry[32];
  WFile file;
  U32 pos = 0;
  U16 done;
  unsigned i, n;
  fs_invalidate();
  wt_error = 0;
  if (fs_lookup(path, entry)) {
    if (!wt_error) wt_error = WT_VERIFY;
    return -1;
  }
  if (get32(entry + 28) != size) {
    wt_error = WT_VERIFY;
    return -1;
  }
  memset(&file, 0, sizeof(file));
  file.first = fs_entry_cluster(entry);
  file.size = size;
  if (!size && file.first) { wt_error = WT_VERIFY; return -1; }
  while (pos < size) {
    n = (unsigned)(size - pos > 512 ? 512 : size - pos);
    if (wf_read(&file, pos, observed, n, &done) || done != n) {
      if (!wt_error) wt_error = WT_VERIFY;
      return -1;
    }
    for (i = 0; i < n; ++i) {
      U8 want = pattern(pos + i, seed);
      if (patched && pos + i >= 510 && pos + i < 514)
        want = 0xe7;
      if (observed[i] != want) {
        logline("DATA: %s offset=%lu expected=%02X actual=%02X\n", path,
                (unsigned long)(pos + i), want, observed[i]);
        wt_error = WT_VERIFY;
        return -1;
      }
    }
    pos += n;
    if (size >= 4096 && (!(pos % 8192UL) || pos == size)) {
      logline("PROGRESS: verify %s bytes=%lu/%lu\n", path,
              (unsigned long)pos, (unsigned long)size);
      if (log_failed) return -1;
    }
  }
  if (wf_read(&file, size, observed, 1, &done) || done) {
    if (!wt_error) wt_error = WT_VERIFY;
    return -1;
  }
  return 0;
}
static int verify_suite(void) {
  static const char *names[] = {"Z0.BIN",   "B1.BIN",    "B511.BIN", "B512.BIN",
                                "B513.BIN", "B4096.BIN", "BIG.BIN"};
  static const U32 sizes[] = {0, 1, 511, 512, 513, 4096, 70000};
  char path[80];
  unsigned i;
  U8 e[32];
  for (i = 0; i < 7; ++i) {
    sprintf(path, "WTEST\\%s", names[i]);
    if (!check(!verify_file(path, sizes[i], 3 + i, 0), path))
      return -1;
  }
  if (!check(!verify_file("WTEST\\SUB\\NOTE.BIN", 1025, 19, 0),
             "nested file content and EOF"))
    return -1;
  if (!check(!verify_file("WTEST\\APPEND.BIN", 1535, 29, 1),
             "append and cross-sector overwrite persisted"))
    return -1;
  if (!check(!verify_file("WTEST\\SHORT.BIN", 17, 39, 0),
             "truncate-to-zero and reallocation persisted"))
    return -1;
  if (!check(fs_lookup("WTEST\\DELETE.BIN", e) < 0 && fs_error == E_NOTFOUND,
             "deleted file absent"))
    return -1;
  if (!check(fs_lookup("WTEST\\EMPTY", e) < 0 && fs_error == E_NOTFOUND,
             "removed empty directory absent"))
    return -1;
  if (!check(!verify_file("WTEST\\HIGHNEW.BIN", 1537, 79, 0),
             "new high-cluster file persists"))
    return -1;
  if (!check(
          !verify_file("WTEST\\FRAGNEW.BIN", (U32)volume.spc * 512 * 4, 59, 0),
          "fragmented new file persists"))
    return -1;
  if (!check(fs_lookup("WTEST\\GAPS.BIN", e) < 0 && fs_error == E_NOTFOUND,
             "deleted interleaved gap file absent"))
    return -1;
  sprintf(path, "WTEST\\E%03u.TXT", (16U * volume.spc + 2U) % 1000U);
  if (!check(!verify_file(path, 0, 0, 0),
             "last grown-directory entry persists"))
    return -1;
  return 0;
}
/* Old read fixtures are protected and checked before/after the write suite. */
static int protected_text(void) {
  U8 e[32];
  FileCursor c;
  U16 n;
  fs_invalidate();
  wt_error = 0;
  if (fs_lookup("README.TXT", e)) {
    if (!wt_error) wt_error = WT_VERIFY;
    return -1;
  }
  if (get32(e + 28) != 24) { wt_error = WT_VERIFY; return -1; }
  c.first = fs_entry_cluster(e);
  c.cluster = c.first;
  c.index = 0;
  if (fs_read(&c, 0, observed, 24, &n) || n != 24 ||
      memcmp(observed, "Hello from Slot-otter!\r\n", 24)) {
    if (!wt_error) wt_error = WT_VERIFY;
    return -1;
  }
  return 0;
}
static int raw_patterns(const char *phase) {
  unsigned i, j;
  for (j = 0; j < 16; ++j) {
    for (i = 0; i < 512; ++i)
      chunk[i] = j == 0 ? 0 : j == 1 ? 255 : j == 2 ? 0x55 :
                 j == 3 ? 0xaa : (U8)(i * 37 + j * 13);
    logline("PATTERN: phase=%s index=%u kind=%s LBA=%lu CRC=%04X\n",
            phase, j, j == 0 ? "ZERO" : j == 1 ? "FF" :
            j == 2 ? "55" : j == 3 ? "AA" : "MIXED",
            (unsigned long)(wf_start + 8), wt_crc16(chunk, 512));
    if (!check(!wt_write(wf_start + 8, chunk, 0),
               "raw CMD24 pattern, busy completion, CMD13 status, CRC and readback"))
      return -1;
    write_trace();
    if (log_failed) return -1;
  }
  return 0;
}
static int recover_probe(const char *name) {
  int result = wt_recover();
  unsigned i;
  logline("RECOVERY: after=%s status_reads=%u\n", name, wt_recovery_count);
  for (i = 0; i < wt_recovery_count; ++i)
    logline("RECOVERY STATUS: read=%u R1=%02X R2=%02X%s\n", i,
            wt_recovery_r1[i], wt_recovery_status[i],
            wt_recovery_r1[i] & 12 ? " (no R2 for command error)" : "");
  return check(!result, "post-probe status consumed, clean status and matching CID");
}
static int command_probe(void) {
  int result = wt_bad_command();
  unsigned i;
  logline("PROBE COMMAND: CMD=13 sent_CRC7=%02X correct_CRC7=%02X R1=%02X error=%u TX_RX:",
          wt_bad_cmd_crc, wt_bad_cmd_calculated, wt_bad_cmd_r1, wt_bad_cmd_error);
  for (i = 0; i < 6; ++i) logline(" %02X", wt_bad_cmd_rx[i]);
  logline("\nPROBE COMMAND RESPONSE: polls=%u bytes:", wt_bad_cmd_count);
  for (i = 0; i < wt_bad_cmd_count; ++i) logline(" %02X", wt_bad_cmd_response[i]);
  logline("\n");
  return check(!result, "CRC-enabled card rejects a bad command CRC");
}
static int qualify_after_probe(const char *name, const char *phase) {
  unsigned i;
  int result;
  if (!recover_probe(name)) return 0;
  logline("ACCESS CHECK: after=%s operation=read-original LBA=%lu\n",
          name, (unsigned long)(wf_start + 8));
  result = sd_read(wf_start + 8, observed);
  if (!result && memcmp(saved, observed, 512)) wt_error = WT_VERIFY;
  /* On failure preserve the first read and do not issue another SD write. */
  if (result || wt_error) {
    wt_poison = 1;
    if (!result) { diag_dump("saved-original", saved); diag_dump("post-probe", observed); }
    check(0, "post-probe scratch read and original payload unchanged");
    return 0;
  }
  if (!check(1, "post-probe scratch read and original payload unchanged")) return 0;
  logline("PHASE: %s normal patterns after %s\n", phase, name);
  /* Change EVERY byte, even if the saved reserved sector was not all zero. */
  for (i = 0; i < 512; ++i) chunk[i] = saved[i] ^ 0x96;
  if (!check(!wt_write(wf_start + 8, chunk, 0),
             "post-probe changing write with exact readback")) return 0;
  write_trace();
  if (log_failed) return 0;
  memset(observed, 0x96, 512);
  if (memcmp(chunk, observed, 512)) {
    if (!check(!wt_write(wf_start + 8, observed, 0),
               "seed 96 before post-probe raw patterns")) return 0;
    write_trace();
    if (log_failed) return 0;
  }
  if (raw_patterns(phase)) return 0;
  if (!check(!wt_write(wf_start + 8, saved, 0),
             "scratch restored after isolated probe qualification")) return 0;
  write_trace();
  return !log_failed;
}
int wt_suite(int write_mode) {
  WFile dir, sub, file, temp;
  U8 entry[32];
  unsigned i, j, n;
  U32 pos, old_first;
  static const char *names[] = {"Z0.BIN",   "B1.BIN",    "B511.BIN", "B512.BIN",
                                "B513.BIN", "B4096.BIN", "BIG.BIN"};
  static const U32 sizes[] = {0, 1, 511, 512, 513, 4096, 70000};
  char name[13], path[80];
  int result;
  failures = checks = 0;
  REQUIRE(!wf_prepare(), "marked FAT32 volume, geometry, clean flags, backups "
                         "and FAT mirrors valid");
  if (wf_hint_mismatch)
    logline("WARNING: /ALLOWHINTS accepted only differing FSInfo allocation "
            "hints; FAT is scanned and both hints become UNKNOWN before allocation.\n");
  REQUIRE(!protected_text(), "original read fixture intact before tests");
  if (!write_mode) {
    verify_suite();
    goto out;
  }
  result = fs_lookup("WTEST", entry);
  if (result >= 0)
    wt_error = WT_EXISTS;
  else if (fs_error != E_NOTFOUND && !wt_error)
    wt_error = WT_GUARD;
  REQUIRE(result < 0 && fs_error == E_NOTFOUND,
          "fresh test image (WTEST must not exist)");
  REQUIRE(!wt_arm(wf_start + 8, wf_start + 9),
          "arm only one reserved scratch sector");
  REQUIRE(!sd_read(wf_start + 8, saved),
          "save scratch sector before destructive CRC tests");
  /* Qualify ordinary writes before deliberate bad-CRC characterization. */
  memset(chunk, 0x96, 512);
  REQUIRE(!wt_write(wf_start + 8, chunk, 0),
          "baseline normal write, busy/status and exact readback");
  write_trace();
  logline("PHASE: PRE-FAULT normal patterns before any deliberate CRC errors\n");
  /* Baseline 96, then ZERO/FF/55/AA/mixed: every pattern changes the last
   * verified payload, including ZERO on an initially zero scratch sector. */
  if (raw_patterns("PRE-FAULT")) goto out;
  REQUIRE(!wt_write(wf_start + 8, saved, 0),
          "baseline scratch restoration with exact readback");
  write_trace();
  memset(chunk, 0x96, 512);
  if (!wt_no_crc && !wt_normal_only) {
    logline("PHASE: FAULT-PROBES deliberate CRC errors on scratch only\n");
    if (wt_probe_only != 2) {
      logline("PROBE BEGIN: bad-command-CRC (no data-CRC error yet)\n");
      if (!command_probe()) goto out;
      if (!qualify_after_probe("bad-command-CRC", "AFTER-COMMAND-CRC")) goto out;
    } else logline("SKIP: /DATACRC omits the bad-command probe\n");
    if (wt_probe_only != 1) {
      memset(chunk, 0x96, 512);
      logline("PROBE BEGIN: bad-data-CRC (correct data CRC xor 0001)\n");
      result = wt_write(wf_start + 8, chunk, 1);
      logline("PROBE DATA RESULT: return=%d error=%u stage=%u poison=%u\n",
              result, wt_error, wt_stage, wt_poison);
      write_trace(); /* Preserve rejection and completion BEFORE recovery. */
      REQUIRE(result < 0 && wt_error == WT_CRC && !wt_poison,
              "CRC-enabled card reports a completed data-CRC rejection");
      if (!qualify_after_probe("bad-data-CRC", "AFTER-DATA-CRC")) goto out;
    } else logline("SKIP: /CMDCRC omits the bad-data probe\n");
    memset(chunk, 0x96, 512);
    if (!wt_crc_only && !wt_probe_only) {
      result = wt_crc_mode(0);
      if (result < 0 && wt_r1 == 4) {
        logline("WARNING/SKIP: card refuses disabling CRC; continuing with CRC enabled\n");
      } else if (result < 0) {
        check(0, "disable CRC for card-policy characterization");
        goto out;
      } else {
        REQUIRE(1, "disable CRC for card-policy characterization");
        logline("PROBE: CRC-OFF with VALID data CRC; identity/readback switch "
                "CRC ON, matching the invalid-CRC probe sequence\n");
        REQUIRE(!wt_write(wf_start + 8, chunk, 0),
                "CRC-OFF valid-data-CRC control: exact write and readback");
        write_trace();
        REQUIRE(!wt_write(wf_start + 8, saved, 0),
                "restore scratch before CRC-OFF invalid-data-CRC probe");
        write_trace();
        REQUIRE(!wt_crc_mode(0), "disable CRC again for invalid-data-CRC probe");
        logline("PROBE: CRC-OFF with INVALID data CRC; correct CRC xor 0001\n");
        result = wt_write(wf_start + 8, chunk, 1);
        if (!result || (wt_error == WT_CRC && !wt_poison)) write_trace();
        if (!result)
          logline("CARD POLICY: accepts unchecked data when CRC is disabled\n");
        else if (wt_error == WT_CRC && !wt_poison)
          logline("CARD POLICY: still checks data CRC while CRC is disabled\n");
        else {
          check(0, "CRC-disabled diagnostic produced an unexpected failure");
          goto out;
        }
      }
      REQUIRE(!wt_crc_mode(1), "re-enable CRC before all normal writes");
      if (!recover_probe("CRC-policy-probes")) goto out;
      logline("PHASE: AFTER-OFF-PROBES normal patterns after CRC-OFF characterization\n");
      memset(chunk, 0x96, 512);
      REQUIRE(!wt_write(wf_start + 8, chunk, 0),
              "post-fault changing-pattern seed with exact readback");
      if (raw_patterns("AFTER-OFF-PROBES")) goto out;
      REQUIRE(!wt_write(wf_start + 8, saved, 0),
              "scratch restored after post-fault raw pattern tests");
    } else logline("SKIP: selected CRC-enabled probes omit CRC-OFF characterization\n");
  } else logline("SKIP: normal-only policy omits intentional CRC errors and CMD59 switching\n");
  logline("PHASE: FILESYSTEM allocation, directories, files and persistence\n");
  REQUIRE(wt_write(0, chunk, 0) < 0 && wt_error == WT_GUARD,
          "write fence refuses MBR sector zero");
  REQUIRE(wt_write(wf_start + 9, chunk, 0) < 0 && wt_error == WT_GUARD,
          "write fence refuses adjacent sector");
  REQUIRE(!wf_begin(),
          "invalidate FSInfo hints and arm bounded test partition");
  REQUIRE(wf_create(volume.root, "ILLEGAL.BIN", &file) < 0 &&
              wt_error == WT_GUARD,
          "writer refuses files outside its owned test tree");
  REQUIRE(!wf_mkdir(volume.root, "WTEST", &dir),
          "create new root test directory with dot entries");
  REQUIRE(!wf_mkdir(dir.first, "SUB", &sub),
          "create nested directory with parent entry");
  REQUIRE(!wf_create(sub.first, "NOTE.BIN", &file) &&
              !append_pattern(&file, 1025, 19),
          "allocate and write nested file");
  REQUIRE(wf_rmdir(&sub) < 0 && wt_error == WT_NOTEMPTY,
          "refuse removal of nonempty directory");
  for (i = 0; i < 7; ++i) {
    REQUIRE(!wf_create(dir.first, names[i], &file) &&
                !append_pattern(&file, sizes[i], 3 + i),
            "create boundary-sized file and allocate its chain");
    sprintf(path, "WTEST\\%s", names[i]);
    REQUIRE(!verify_file(path, sizes[i], 3 + i, 0), path);
  }
  REQUIRE(wf_create(dir.first, "BIG.BIN", &file) < 0 && wt_error == WT_EXISTS,
          "duplicate filename refused without truncation");
  /* Fill a whole directory cluster, then extend its FAT chain. */
  for (i = 0; i < 16U * volume.spc + 3U; ++i) {
    sprintf(name, "E%03u.TXT", i % 1000);
    REQUIRE(!wf_create(dir.first, name, &file),
            "grow directory past first cluster");
  }
  REQUIRE(wf_fat(dir.first) < 0x0ffffff8UL,
          "directory has automatically allocated another cluster");
  REQUIRE(!wf_create(dir.first, "APPEND.BIN", &file) &&
              !append_pattern(&file, 511, 29),
          "initial partial-sector file");
  REQUIRE(!append_pattern(&file, 1535, 29),
          "append through sector and cluster boundaries");
  memset(chunk, 0xe7, 4);
  REQUIRE(!wf_overwrite(&file, 510, chunk, 4),
          "overwrite four bytes across sector boundary");
  REQUIRE(!verify_file("WTEST\\APPEND.BIN", 1535, 29, 1),
          "overwrite preserves adjacent bytes");
  REQUIRE(wf_overwrite(&file, 1534, chunk, 4) < 0 && wt_error == WT_RANGE,
          "overwrite cannot silently extend a file");
  REQUIRE(!wf_create(dir.first, "SHORT.BIN", &file) &&
              !append_pattern(&file, 7000, 39),
          "allocate file for truncate tests");
  old_first = file.first;
  REQUIRE(!wf_truncate(&file, 513) &&
              !verify_file("WTEST\\SHORT.BIN", 513, 39, 0),
          "truncate publishes shorter size and frees tail clusters");
  REQUIRE(!wf_truncate(&file, 0) && !wf_fat(old_first),
          "truncate to zero releases first cluster");
  REQUIRE(!append_pattern(&file, 17, 39) && file.first == old_first,
          "freed cluster reused for new data");
  REQUIRE(!wf_create(dir.first, "DELETE.BIN", &temp) &&
              !append_pattern(&temp, 2048, 49),
          "create file for delete and free-space tests");
  old_first = temp.first;
  REQUIRE(!wf_delete(&temp) && !wf_fat(old_first),
          "delete removes directory entry and releases chain");
  REQUIRE(!wf_mkdir(dir.first, "EMPTY", &temp), "create empty directory");
  REQUIRE(!wf_rmdir(&temp), "remove empty directory and release cluster");
  /* Force noncontiguous allocation by interleaving two growing files. */
  REQUIRE(!wf_create(dir.first, "FRAGNEW.BIN", &file) &&
              !wf_create(dir.first, "GAPS.BIN", &temp),
          "create interleaved allocation files");
  n = (unsigned)volume.spc * 512;
  for (j = 0; j < 4; ++j) {
    pos = (U32)(j + 1) * n;
    REQUIRE(!append_pattern(&file, pos, 59) && !append_pattern(&temp, pos, 69),
            "interleaved cluster allocation");
  }
  REQUIRE(wf_fat(file.first) != file.first + 1,
          "new file is deliberately fragmented");
  REQUIRE(!verify_file("WTEST\\FRAGNEW.BIN", (U32)n * 4, 59, 0),
          "read back new fragmented chain");
  REQUIRE(!wf_delete(&temp), "delete interleaved gap file");
  REQUIRE(!wf_hint(66000), "start allocation search at protected high cluster");
  REQUIRE(!wf_create(dir.first, "HIGHNEW.BIN", &file) &&
              !append_pattern(&file, 1537, 79),
          "allocate and write beyond cluster/sector 65535");
  REQUIRE(file.first == 66001UL,
          "allocator skips occupied high cluster without modifying it");
  REQUIRE(!verify_file("WTEST\\HIGHNEW.BIN", 1537, 79, 0),
          "new high-cluster data and FAT links verified");
  REQUIRE(!verify_suite(),
          "read all created results through independent streaming reader");
  REQUIRE(!protected_text(), "original read fixture preserved after writes");
  REQUIRE(!sd_check_media(), "card identity unchanged at completion");
  REQUIRE(!wf_finish(),
          "FAT mirrors rechecked and clean flag set only after verification");
out:
  wt_disarm();
  logline("STATS: accepted_writes=%lu reads=%lu allocated=%lu freed=%lu "
          "max_busy_clocks=%lu max_busy_ticks=%lu\n",
          wt_writes, wt_reads, wf_allocated, wf_freed, wt_busy_max,
          wt_busy_ticks);
  if (log_failed)
    return 2;
  logline("%s RESULT: %u failures, %u checks. ERRORLEVEL=%u\n", write_mode ? "WRITE" : "VERIFY", failures,
          checks, failures ? 1 : 0);
  if (failures && !write_mode) logline("STOP: preserve WVERIFY.LOG for diagnosis.\n");
  if (failures && write_mode)
    logline("STOP: preserve WRITE.LOG; re-image the expendable card before "
            "another write run. No retry or repair.\n");
  return log_failed ? 2 : failures ? 1 : 0;
}
/* Diagnostic reads only: retain strict write guards, never repair metadata. */
static void diag_fsinfo(const char *name, const U8 *p) {
  logline("FSINFO %s: lead=%08lX struct=%08lX trail=%08lX "
          "free=%lu next=%lu signatures=%s\n", name,
          (unsigned long)get32(p), (unsigned long)get32(p + 484),
          (unsigned long)get32(p + 508), (unsigned long)get32(p + 488),
          (unsigned long)get32(p + 492),
          get32(p) == 0x41615252UL && get32(p + 484) == 0x61417272UL &&
          get32(p + 508) == 0xaa550000UL ? "valid" : "INVALID");
}
static void diag_dump(const char *name, const U8 *p) {
  unsigned i, j;
  for (i = 0; i < 512 && !log_failed; i += 16) {
    logline("HEX %s %03u:", name, i);
    for (j = 0; j < 16; ++j)
      logline(" %02X", p[i + j]);
    logline("\n");
  }
}
static void diag_pair(U32 primary, U32 backup, int fsinfo) {
  int a, b;
  unsigned i, differences = 0, hints = 0;
  logline("PAIR: %s primary_LBA=%lu backup_LBA=%lu\n",
          fsinfo ? "FSInfo" : "boot", (unsigned long)primary,
          (unsigned long)backup);
  a = sd_read(primary, saved);
  check(!a, "diagnostic primary sector read and CRC");
  if (log_failed) return;
  b = sd_read(backup, observed);
  check(!b, "diagnostic backup sector read and CRC");
  if (log_failed) return;
  if (a || b) {
    logline("PAIR: unavailable; failed reads are not compared\n");
    return;
  }
  if (fsinfo) {
    diag_fsinfo("primary", saved);
    diag_fsinfo("backup", observed);
  }
  for (i = 0; i < 512; ++i) {
    if (saved[i] != observed[i]) {
      if (differences < 32)
        logline("DIFF: offset=%u primary=%02X backup=%02X\n",
                i, saved[i], observed[i]);
      ++differences;
      if (fsinfo && i >= 488 && i < 496) ++hints;
    }
  }
  logline("COMPARE: differing_bytes=%u hint_bytes=%u other_bytes=%u\n",
          differences, hints, differences - hints);
  if (differences > 32) logline("DIFF: remaining differences omitted; see HEX\n");
  if (fsinfo) {
    diag_dump("primary", saved);
    diag_dump("backup", observed);
  }
}
int wt_diagnose(void) {
  int result;
  failures = checks = 0;
  wt_disarm();
  wf_allow_hints = 0;
  logline("DIAGNOSTIC ONLY: sector reads, no writes or repairs.\n");
  result = wf_prepare();
  check(!result, "read-only marked-image preflight");
  if (log_failed) return 2;
  logline("ALLOWHINTS ELIGIBLE: %s\n",
          wf_hint_mismatch ? "YES (valid sectors differ only at offsets 488..495)" :
                             "NO (no hint-only preflight exception identified)");
  /* Read the known image locations only after checking the actual MBR. */
  if (!check(!sd_read(0, chunk), "diagnostic MBR read and CRC")) goto out;
  if (!check(chunk[450] == 0x0c && get32(chunk + 454) == 2048UL &&
             get32(chunk + 458) >= 8 && wt_last_lba >= 2055UL,
             "diagnostic locations inside marked primary partition")) goto out;
  diag_pair(2048UL, 2054UL, 0);
  if (!log_failed) diag_pair(2049UL, 2055UL, 1);
out:
  wt_disarm();
  logline("DIAG RESULT: failures=%u accepted_writes=%lu ERRORLEVEL=%u\n",
          failures, (unsigned long)wt_writes, failures ? 1 : 0);
  return log_failed ? 2 : failures ? 1 : 0;
}
#ifdef HOST_TEST
int wt_test_verify_file(const char *path, U32 size, unsigned seed) {
  return verify_file(path, size, seed, 0);
}
void wt_test_log(const char *path) {
  if (logfile)
    fclose(logfile);
  logfile = path ? fopen(path, "wt") : 0;
  log_failed = 0;
}
#endif
#ifndef HOST_TEST
int main(int argc, char **argv) {
  int i, writing = 0, verify = 0, batch = 0, diagnostic = 0, info = 0, answer, retval;
  union REGS r;
  char cwd[80];
  for (i = 1; i < argc; ++i) {
    option_upper(argv[i]);
    if (!strcmp(argv[i], "/WRITE"))
      writing = 1;
    else if (!strcmp(argv[i], "/NOCRC"))
      wt_no_crc = 1;
    else if (!strcmp(argv[i], "/CRCONLY"))
      wt_crc_only = 1;
    else if (!strcmp(argv[i], "/NORMAL"))
      wt_normal_only = 1;
    else if (!strcmp(argv[i], "/CMDCRC")) {
      if (wt_probe_only == 2) { puts("STOP: select one CRC probe."); return 2; }
      wt_probe_only = 1;
    } else if (!strcmp(argv[i], "/DATACRC")) {
      if (wt_probe_only == 1) { puts("STOP: select one CRC probe."); return 2; }
      wt_probe_only = 2;
    }
    else if (!strcmp(argv[i], "/ALLOWHINTS"))
      wf_allow_hints = 1;
    else if (!strcmp(argv[i], "/DIAG"))
      diagnostic = 1;
    else if (!strcmp(argv[i], "/VERIFY"))
      verify = 1;
    else if (!strcmp(argv[i], "/BATCH"))
      batch = 1;
    else if (!strcmp(argv[i], "/INFO")) {
      info = 1;
    } else if (!strncmp(argv[i], "/PORT:", 6) &&
               parse_port(argv[i] + 6, &sd_port)) {
    } else {
      puts("WTTEST [/INFO | /DIAG | /WRITE [/BATCH] [/ALLOWHINTS] [/CRCONLY | /NORMAL | /CMDCRC | /DATACRC] | /VERIFY] [/NOCRC] [/PORT:330]");
      return 2;
    }
  }
  if ((info && (writing || verify || diagnostic)) || (writing && verify) || (batch && !writing) ||
      (diagnostic && (writing || verify || batch)) ||
      (wf_allow_hints && !writing) || (wt_no_crc && wt_crc_only) ||
      (wt_crc_only && !writing) || (wt_normal_only && !writing) ||
      (wt_normal_only && (wt_no_crc || wt_crc_only)) ||
      (wt_probe_only && (!writing || wt_normal_only || wt_no_crc || wt_crc_only))) {
    puts("STOP: conflicting or inapplicable options; use one operation mode.");
    return 2;
  }
  memset(&r, 0, sizeof(r));
  r.x.ax = 0xd74f;
  int86(0x2f, &r, &r);
  if (r.x.ax == 0x4f54 && r.x.bx == 0x524f) {
    puts("STOP: reboot without OTTERFS; raw testing requires NO resident "
         "driver.");
    return 2;
  }
  if (getdisk() == 18 || !getcwd(cwd, sizeof(cwd))) {
    puts("STOP: run from local DOS storage.");
    return 2;
  }
  logfile = fopen(diagnostic ? "WDIAG.LOG"
                  : verify    ? "WVERIFY.LOG"
                  : writing ? "WRITE.LOG"
                            : "WINFO.LOG",
                  "wt");
  if (!logfile) {
    puts("STOP: cannot create local log.");
    return 2;
  }
  logline("OTTER WRITE KIT v1.7 EXPERIMENTAL, DOS=%u.%u port=%X local=%s\n",
          _osmajor, _osminor, sd_port, cwd);
  logline("OPTIONS: mode=%s CRC_policy=%s ALLOWHINTS=%u BATCH=%u\n",
          writing ? "WRITE" : verify ? "VERIFY" : diagnostic ? "DIAG" : "INFO",
          wt_no_crc ? "NOCRC" : wt_normal_only ? "NORMAL" : wt_probe_only == 1 ? "CMDCRC" : wt_probe_only == 2 ? "DATACRC" : wt_crc_only ? "CRCONLY" : "DEFAULT",
          (unsigned)wf_allow_hints, (unsigned)batch);
  retval = sd_init();
  logline("STARTUP: CMD0 attempts=%u packets=%u initial_MISO=%02X "
          "(MISO pull high; load FF + 12 clock-only pulses)\n",
          wt_reset_attempts, wt_cmd0_sent, wt_startup_miso);
  logline("INIT TRACE: commands=%lu retained=%u (R1 and transport error)\n",
          wt_init_total, wt_init_count);
  for (i = 0; i < wt_init_count; ++i) {
    if (i == 63 && wt_init_total > 64)
      logline("INIT TRACE: omitted_middle=%lu; final record follows\n", wt_init_total - 64);
    logline("INIT CMD: sequence=%lu CMD=%u arg=%08lX R1=%02X error=%u\n",
            i == 63 ? wt_init_total : (U32)i + 1, wt_init_command[i],
            wt_init_argument[i], wt_init_r1[i], wt_init_error[i]);
  }
  logline("OCR: %02X %02X %02X %02X (partial if initialization failed)\n",
          wt_ocr[0], wt_ocr[1], wt_ocr[2], wt_ocr[3]);
  logline("CID:");
  for (i = 0; i < 16; ++i)
    logline(" %02X", wt_cid[i]);
  logline("\nCSD:");
  for (i = 0; i < 16; ++i)
    logline(" %02X", wt_csd[i]);
  logline("\n");
  if (retval) {
    check(0, "initialize SDHC/SDXC with requested CRC policy and valid CSD/CID");
    retval = 1;
    goto done;
  }
  logline("\nCARD: last_LBA=%lu CRC=%s command_CRC=valid read_CRC=verified\n",
          wt_last_lba, wt_no_crc ? "reset-default-OFF data_CRC=dummy-FFFF" : "enabled");
  if (log_failed) {
    retval = 2;
    goto done;
  }
  if (diagnostic) {
    retval = wt_diagnose();
    goto done;
  }
  if (!writing && !verify) {
    logline("INFO ONLY: no block writes issued.\n");
    retval = 0;
    goto done;
  }
  logline("WARNING: expendable marked WRITE image only. Power loss/failure can "
          "leave FAT mirrors inconsistent or clusters leaked.\n");
  if (writing && !batch) {
    logline("Confirm destructive test by typing WRITE and ENTER: ");
    {
      char confirmation[16];
      if (!fgets(confirmation, sizeof(confirmation), stdin) ||
          strcmp(confirmation, "WRITE\n")) {
        logline("Cancelled: no block writes issued.\n");
        retval = 2;
        goto done;
      }
    }
  }
  retval = wt_suite(writing);
done:
  sd_release();
  i = ferror(logfile);
  answer = fclose(logfile);
  if (i || answer) {
    puts("STOP: local log write failure; no result can be trusted.");
    return 2;
  }
  return retval;
}
#endif
