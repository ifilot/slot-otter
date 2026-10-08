/* CRC-checked SPI single-block transport, 8086, bounded waits.
 * GPL-3.0-or-later. */
#include "WRITE.H"
#include <string.h>
U16 sd_port = 0x330;
unsigned wt_error, wt_stage, wt_r1, wt_token, wt_status, wt_poison;
unsigned wt_reset_attempts;
U32 wt_lba, wt_writes, wt_reads, wt_busy_max, wt_busy_ticks, wt_last_lba;
U8 wt_cid[16], wt_csd[16], wt_ocr[4];
static U32 allowed_first, allowed_end;
static int armed, identified, crc_enabled, in_write, initializing, recovering;
int wt_no_crc, wt_crc_only, wt_normal_only, wt_probe_only;
unsigned wt_bad_cmd_count, wt_bad_cmd_crc, wt_bad_cmd_calculated;
unsigned wt_bad_cmd_r1, wt_bad_cmd_error;
U8 wt_bad_cmd_rx[6], wt_bad_cmd_response[100];
static int bad_command_trace;
unsigned wt_init_count, wt_init_command[64], wt_init_r1[64], wt_init_error[64];
U32 wt_init_total, wt_init_argument[64];
unsigned wt_recovery_count, wt_recovery_r1[2], wt_recovery_status[2];
unsigned wt_trace, wt_write_r1, wt_write_token, wt_program_r1;
unsigned wt_program_status, wt_sent_crc, wt_calculated_crc, wt_write_crc;
unsigned wt_readback_valid, wt_repeat_valid, wt_repeat_error;
unsigned wt_packet_count, wt_packet_crc, wt_packet_calculated;
unsigned wt_packet_complete, wt_response_count;
unsigned wt_packet_sample_count;
U32 wt_packet_polls, wt_packet_ticks;
U8 wt_packet_tokens[32];
unsigned wt_readback_crc, wt_busy_sample_count, wt_status_sample_count;
unsigned wt_busy_entered, wt_status_entered, wt_cmd13_rx_count;
U8 wt_cmd13_rx[6];
U32 wt_write_busy_polls, wt_write_busy_ticks, wt_status_busy_polls, wt_status_busy_ticks;
U8 wt_busy_samples[32], wt_status_samples[32];
U8 wt_packet_data[512], wt_response_bytes[100];
U32 wt_write_lba;
U8 wt_expected[512], wt_readback[512], wt_repeat[512];
#define verify_buffer wt_readback
unsigned wt_cmd0_sent, wt_startup_miso;
const char *wt_phase = "not started";
#ifndef HOST_TEST
#define wt_reg_write(offset, value) outportb(sd_port + (offset), (value))
#define wt_reg_read(offset) inportb(sd_port + (offset))
U16 wt_ticks(void) { return *(volatile U16 far *)MK_FP(0x40, 0x6c); }
#endif
/* RX reads do not pulse the clock. Allow the autonomous byte burst time to
 * complete before sampling RX, launching another burst or changing CS. */
static void settle(void) {
  (void)wt_reg_read(0);
  (void)wt_reg_read(0);
}
U8 wt_io(U8 b) {
  wt_reg_write(0, b);
  settle();
  return wt_reg_read(0);
}
void wt_pull_high(void) { (void)wt_reg_read(3); }
void wt_select(int selected) {
  wt_reg_write(selected ? 3 : 2, 255);
  settle();
}
static void idle_clocks(void) {
  unsigned i;
  /* Exact working cmdclr: one load/pulse, twelve pulse-only operations. */
  wt_reg_write(0, 255);
  settle();
  for (i = 0; i < 12; ++i) {
    wt_reg_write(1, 255);
    settle();
  }
}
U8 wt_crc7(const U8 *p, unsigned n) {
  U8 crc = 0, b;
  unsigned i;
  while (n--) {
    b = *p++;
    for (i = 0; i < 8; ++i) {
      crc <<= 1;
      if ((b ^ crc) & 0x80)
        crc ^= 9;
      b <<= 1;
    }
  }
  return (U8)((crc << 1) | 1);
}
U16 wt_crc16(const U8 *p, unsigned n) {
  U16 crc = 0;
  unsigned i;
  while (n--) {
    crc ^= (U16)*p++ << 8;
    for (i = 0; i < 8; ++i)
      crc = (U16)((crc << 1) ^ ((crc & 0x8000) ? 0x1021 : 0));
  }
  return crc;
}
static int error(unsigned code) {
  wt_error = code;
  return -1;
}
static void finish(void) {
  (void)wt_io(255);
  wt_select(0);
  (void)wt_io(255);
}
static int wait_ready_record(unsigned ticks, unsigned trace_phase) {
  U16 start = wt_ticks();
  U32 polls = 0;
  U8 value;
  int timed_out = 0;
  unsigned ready_bytes = 0;
  if (trace_phase == 1) wt_busy_entered = 1;
  if (trace_phase == 2) wt_status_entered = 1;
  do {
    value = wt_io(255);
    if (trace_phase == 1 && wt_busy_sample_count < 32)
      wt_busy_samples[wt_busy_sample_count++] = value;
    if (trace_phase == 2 && wt_status_sample_count < 32)
      wt_status_samples[wt_status_sample_count++] = value;
    if (value == 255) {
      /* Two selected idle bytes allow a short post-response busy delay.
       * Readiness is observed, rather than requiring every card to go busy. */
      if (++ready_bytes >= (unsigned)(trace_phase == 1 ? 2 : 1) + (recovering ? 1U : 0U)) break;
      continue;
    }
    ready_bytes = 0;
    if (++polls == 4000000UL || (U16)(wt_ticks() - start) >= ticks) {
      timed_out = 1;
      break;
    }
  } while (1);
  if (polls > wt_busy_max) wt_busy_max = polls;
  if ((U16)(wt_ticks() - start) > wt_busy_ticks)
    wt_busy_ticks = (U16)(wt_ticks() - start);
  if (trace_phase == 1) {
    wt_write_busy_polls = polls;
    wt_write_busy_ticks = (U16)(wt_ticks() - start);
  }
  if (trace_phase == 2) {
    wt_status_busy_polls = polls;
    wt_status_busy_ticks = (U16)(wt_ticks() - start);
  }
  return timed_out ? error(WT_TIMEOUT) : 0;
}
static int wait_ready(unsigned ticks) { return wait_ready_record(ticks, 0); }
static int command_wire(unsigned number, U32 argument, int bad_crc) {
  U8 packet[6], incoming;
  unsigned i;
  wt_packet_complete = wt_packet_count = 0;
  wt_packet_sample_count = 0;
  wt_packet_polls = wt_packet_ticks = 0;
  wt_stage = number;
  wt_r1 = 255;
  wt_token = 255;
  wt_status = 0;
  finish();
  wt_select(1);
  wt_phase = "ready before command";
  /* CMD0 enters SPI mode: do not require SPI-ready before sending reset. */
  if (number != 0 && (number == 13 && in_write && wt_trace
      ? wait_ready_record(90, 2) : wait_ready(90))) {
    finish();
    return -1;
  }
  if (!number && wt_reset_attempts == 1)
    wt_startup_miso = wt_io(255);
  wt_phase = "command transmission";
  packet[0] = (U8)(0x40 | number);
  packet[1] = (U8)(argument >> 24);
  packet[2] = (U8)(argument >> 16);
  packet[3] = (U8)(argument >> 8);
  packet[4] = (U8)argument;
  packet[5] = wt_crc7(packet, 5);
  if (bad_command_trace) wt_bad_cmd_calculated = packet[5];
  if (bad_crc)
    packet[5] ^= 2;
  for (i = 0; i < 6; ++i) {
    incoming = wt_io(packet[i]);
    if (bad_command_trace) {
      wt_bad_cmd_crc = packet[5];
      wt_bad_cmd_rx[i] = incoming;
    }
    if (number == 13 && ((in_write && wt_trace) || recovering)) {
      if (in_write && wt_trace) wt_cmd13_rx[wt_cmd13_rx_count++] = incoming;
      if (incoming != 255) {
        /* Busy arriving after the ready poll must not masquerade as R1/R2. */
        wt_phase = "card not ready during CMD13 transmission";
        finish();
        return error(WT_TIMEOUT);
      }
    }
  }
  if (!number) ++wt_cmd0_sent;
  wt_phase = "response after command";
  for (i = 0; i < 100; ++i) {
    wt_r1 = wt_io(255);
    if (bad_command_trace) wt_bad_cmd_response[wt_bad_cmd_count++] = (U8)wt_r1;
    if (!(wt_r1 & 0x80))
      return 0;
  }
  finish();
  return error(WT_TIMEOUT);
}
static int command(unsigned number, U32 argument, int bad_crc) {
  int result = command_wire(number, argument, bad_crc);
  unsigned index;
  if (initializing) {
    ++wt_init_total;
    index = wt_init_count < 64 ? wt_init_count++ : 63;
    wt_init_command[index] = number;
    wt_init_argument[index] = argument;
    wt_init_r1[index] = wt_r1;
    wt_init_error[index] = result ? wt_error : 0;
  }
  return result;
}
static int packet(U8 *p, unsigned count) {
  U16 start = wt_ticks(), crc;
  U32 polls = 0;
  unsigned i;
  wt_phase = "data token and CRC";
  do {
    wt_token = wt_io(255);
    if (wt_packet_sample_count < 32)
      wt_packet_tokens[wt_packet_sample_count++] = (U8)wt_token;
    wt_packet_polls = ++polls;
    wt_packet_ticks = (U16)(wt_ticks() - start);
    if (wt_token != 255 && wt_token != 0xfe)
      return error(WT_REJECT);
    if (polls == 4000000UL || wt_packet_ticks >= 36)
      return error(WT_TIMEOUT);
  } while (wt_token != 0xfe);
  for (i = 0; i < count; ++i)
    p[i] = wt_io(255);
  wt_packet_count = count;
  crc = (U16)wt_io(255) << 8;
  crc |= wt_io(255);
  wt_packet_complete = 1;
  wt_packet_crc = crc;
  wt_packet_calculated = wt_crc16(p, count);
  if (crc != wt_packet_calculated) {
    memcpy(wt_packet_data, p, count);
    return error(WT_CRC);
  }
  return 0;
}
void wt_disarm(void) { armed = 0; }
int wt_arm(U32 first, U32 end) {
  if (!identified || wt_poison || !first || end <= first ||
      end - 1 > wt_last_lba)
    return error(WT_GUARD);
  allowed_first = first;
  allowed_end = end;
  armed = 1;
  return 0;
}
void sd_release(void) {
  finish();
  identified = 0;
  armed = 0;
}
static int initialize_card(void) {
  U16 started;
  U8 reply[4];
  unsigned i;
  U32 attempts;
  wt_error = wt_poison = wt_reset_attempts = wt_cmd0_sent = 0;
  wt_startup_miso = 255;
  wt_phase = "board startup";
  wt_trace = 0;
  wt_stage = 0;
  wt_lba = 0;
  wt_r1 = wt_token = 255;
  wt_status = 0;
  memset(wt_cid, 0, 16);
  memset(wt_csd, 0, 16);
  memset(wt_ocr, 0, 4);
  armed = identified = crc_enabled = 0;
  wt_writes = wt_reads = 0;
  wt_busy_max = wt_busy_ticks = 0;
  /* IN base+3 sets the board's MISO pull latch high. OUT base+3 only
   * selects the card; it does not initialize that separate latch. */
  wt_pull_high();
  started = wt_ticks();
  do {
    wt_select(0);
    idle_clocks();
    ++wt_reset_attempts;
    if (!command(0, 0, 0) && wt_r1 == 1)
      break;
    finish();
    if (wt_reset_attempts == 100 || (U16)(wt_ticks() - started) >= 90)
      return error(WT_MEDIA);
  } while (1);
  wt_error = 0;
  finish();
  if (command(8, 0x1aa, 0)) return -1;
  if (wt_r1 != 1) { finish(); return error(WT_MEDIA); }
  for (i = 0; i < 4; ++i)
    reply[i] = wt_io(255);
  finish();
  if (reply[2] != 1 || reply[3] != 0xaa)
    return error(WT_MEDIA);
  if (!wt_no_crc) {
    if (command(59, 1, 0)) return -1;
    if (wt_r1 != 1) {
      finish();
      return error(WT_CRC);
    }
    finish();
    crc_enabled = 1;
  }
  started = wt_ticks();
  attempts = 0;
  do {
    if (command(55, 0, 0)) return -1;
    /* CMD55 may report ready while ACMD41 was still idle on the previous
     * iteration. Accept both non-error states, but always issue ACMD41. */
    if (wt_r1 != 0 && wt_r1 != 1) { finish(); return error(WT_MEDIA); }
    finish();
    if (command(41, 0x40000000UL, 0))
      return -1;
    finish();
    if (wt_r1 != 0 && wt_r1 != 1)
      return error(WT_MEDIA);
    if (++attempts == 65535UL || (U16)(wt_ticks() - started) >= 90)
      return error(WT_TIMEOUT);
  } while (wt_r1);
  if (command(58, 0, 0)) return -1;
  if (wt_r1) { finish(); return error(WT_MEDIA); }
  for (i = 0; i < 4; ++i)
    wt_ocr[i] = wt_io(255);
  finish();
  if ((wt_ocr[0] & 0xc0) != 0xc0)
    return error(WT_MEDIA);
  if (!wt_no_crc) {
    if (command(59, 1, 0)) return -1;
    if (wt_r1) { finish(); return error(WT_CRC); }
    finish();
  }
  if (command(10, 0, 0)) return -1;
  if (wt_r1) { finish(); return error(WT_REJECT); }
  if (packet(wt_cid, 16)) {
    finish();
    return -1;
  }
  finish();
  if (command(9, 0, 0)) return -1;
  if (wt_r1) { finish(); return error(WT_REJECT); }
  if (packet(wt_csd, 16)) {
    finish();
    return -1;
  }
  finish();
  if ((wt_csd[0] >> 6) != 1 || (wt_csd[14] & 0x30))
    return error(WT_GUARD);
  wt_last_lba =
      (((U32)(wt_csd[7] & 63) << 16) | ((U32)wt_csd[8] << 8) | wt_csd[9]);
  wt_last_lba = (wt_last_lba << 10) | 1023UL;
  identified = 1;
  wt_error = 0;
  return 0;
}
int sd_init(void) {
  int result;
  wt_init_count = 0;
  wt_init_total = 0;
  wt_recovery_count = 0;
  initializing = 1;
  result = initialize_card();
  initializing = 0;
  return result;
}
int sd_check_media(void) {
  U8 cid[16];
  int result;
  if (!identified || wt_poison)
    return error(WT_MEDIA);
  if (command(10, 0, 0)) return -1;
  if (wt_r1) {
    finish();
    return error(WT_MEDIA);
  }
  result = packet(cid, 16);
  finish();
  if (result)
    return -1;
  return memcmp(cid, wt_cid, 16) ? error(WT_MEDIA) : 0;
}
int sd_read(U32 lba, U8 *p) {
  int result;
  if (!in_write) wt_trace = 0;
  wt_error = 0;
  wt_lba = lba;
  ++wt_reads;
  if (!identified || lba > wt_last_lba)
    return error(WT_RANGE);
  if (command(17, lba, 0))
    return -1;
  if (wt_r1) {
    finish();
    return error(WT_REJECT);
  }
  result = packet(p, 512);
  finish();
  return result;
}
int wt_crc_mode(int enabled) {
  if (wt_no_crc) {
    if (enabled) return error(WT_GUARD);
    return 0; /* NOCRC relies on CMD0 reset default, never sends CMD59. */
  }
  if (command(59, (U32)enabled, 0))
    return -1;
  finish();
  if (wt_r1)
    return error(WT_CRC);
  crc_enabled = enabled;
  return 0;
}
int wt_bad_command(void) {
  int result;
  wt_bad_cmd_count = 0;
  wt_bad_cmd_crc = wt_bad_cmd_calculated = wt_bad_cmd_r1 = 255;
  memset(wt_bad_cmd_rx, 255, 6);
  bad_command_trace = 1;
  result = command(13, 0, 1);
  bad_command_trace = 0;
  wt_bad_cmd_r1 = wt_r1;
  if (!result) {
    finish();
    result = wt_r1 == 8 ? 0 : error(WT_CRC);
  }
  wt_bad_cmd_error = result ? wt_error : 0;
  return result;
}
/* Consume status after a deliberately rejected CRC probe. Only the expected
 * command-CRC error may appear on the first status read; the next must be clean.
 * An R1 CRC/illegal-command error has no R2 byte in SPI mode. No write retries. */
int wt_recover(void) {
  unsigned i;
  wt_recovery_count = 0;
  wt_trace = 0;
  if (wt_poison) return error(WT_POISON);
  for (i = 0; i < 2; ++i) {
    recovering = 1;
    if (command(13, 0, 0)) {
      recovering = 0; wt_poison = 1; return -1;
    }
    recovering = 0;
    wt_recovery_r1[i] = wt_r1;
    wt_status = (wt_r1 & 12) ? 255 : wt_io(255);
    wt_recovery_status[i] = wt_status;
    ++wt_recovery_count;
    finish();
    if ((wt_r1 != 0 && (i != 0 || wt_r1 != 8)) ||
        (wt_r1 == 0 && wt_status != 0)) {
      wt_poison = 1;
      return error(WT_STATUS);
    }
  }
  if (sd_check_media()) { wt_poison = 1; return -1; }
  wt_error = 0;
  return 0;
}
static int write_block(U32 lba, const U8 *p, int bad_crc) {
  U16 crc;
  unsigned i;
  int result, off_probe = !crc_enabled && !wt_no_crc;
  wt_lba = lba;
  wt_trace = 0;
  if (wt_poison)
    return error(WT_POISON);
  if (!armed || lba < allowed_first || lba >= allowed_end)
    return error(WT_GUARD);
  /* Identity is CRC-checked with CRC enabled, even for an OFF diagnostic. */
  if (off_probe && wt_crc_mode(1)) {
    wt_poison = 1;
    return -1;
  }
  if (sd_check_media()) {
    wt_poison = 1;
    return -1;
  }
  if (off_probe && wt_crc_mode(0)) {
    wt_poison = 1;
    return -1;
  }
  wt_lba = lba;
  wt_trace = 1;
  wt_write_lba = lba;
  wt_write_r1 = wt_write_token = wt_program_r1 = wt_program_status = 255;
  wt_readback_valid = wt_repeat_valid = wt_repeat_error = 0;
  wt_response_count = 0;
  wt_readback_crc = 255;
  wt_busy_sample_count = wt_status_sample_count = 0;
  wt_busy_entered = wt_status_entered = wt_cmd13_rx_count = 0;
  wt_write_busy_polls = wt_write_busy_ticks = 0;
  wt_status_busy_polls = wt_status_busy_ticks = 0;
  wt_write_crc = crc_enabled;
  memcpy(wt_expected, p, 512);
  /* Precompute CRC before CMD24: avoid a long pause inside the data packet. */
  crc = wt_crc16(p, 512);
  wt_calculated_crc = crc;
  if (wt_no_crc) crc = 0xffff;
  if (bad_crc)
    crc ^= 1;
  wt_sent_crc = crc;
  if (command(24, lba, 0)) {
    wt_write_r1 = wt_r1;
    wt_poison = 1;
    return -1;
  }
  wt_write_r1 = wt_r1;
  if (wt_r1) {
    finish();
    wt_poison = 1;
    return error(WT_REJECT);
  }
  wt_io(255);
  wt_io(0xfe);
  for (i = 0; i < 512; ++i)
    wt_io(p[i]);
  wt_io((U8)(crc >> 8));
  wt_io((U8)crc);
  wt_stage = 124;
  wt_phase = "write response";
  for (i = 0; i < 100; ++i) {
    wt_token = wt_io(255);
    wt_response_bytes[wt_response_count++] = (U8)wt_token;
    if (wt_token != 255)
      break;
  }
  wt_write_token = wt_token;
  if ((wt_token & 31) != 5) {
    unsigned code = (wt_token & 31) == 11 ? WT_CRC
                    : wt_token == 255     ? WT_TIMEOUT
                                          : WT_REJECT;
    if (code == WT_CRC) {
      /* A rejection token is not a completed transaction. Observe release
       * while CS stays asserted, just as for accepted data, before deselect. */
      wt_stage = 324;
      wt_phase = "CRC rejection busy completion";
      if (wait_ready_record(90, 1)) {
        finish(); wt_poison = 1; return -1;
      }
    }
    finish();
    if (!bad_crc || code != WT_CRC)
      wt_poison = 1;
    return error(code);
  }
  ++wt_writes;
  wt_stage = 224;
  wt_phase = "write busy completion";
  if (wait_ready_record(90, 1)) {
    finish();
    wt_poison = 1;
    return -1;
  }
  finish();
  if (command(13, 0, 0)) {
    wt_poison = 1;
    return -1;
  }
  wt_program_r1 = wt_r1;
  wt_status = wt_io(255);
  wt_program_status = wt_status;
  finish();
  if (wt_r1 || wt_status) {
    wt_poison = 1;
    return error(WT_STATUS);
  }
  /* The valid and invalid OFF controls use identical identity/mode/readback
   * transitions, isolating the transmitted data CRC as the changed variable. */
  if (off_probe && wt_crc_mode(1)) {
    wt_poison = 1;
    return -1;
  }
  wt_readback_crc = crc_enabled;
  result = sd_read(lba, verify_buffer);
  wt_readback_valid = !result;
  if (result || memcmp(p, verify_buffer, 512)) {
    if (!result) {
      /* A second READ diagnoses delayed/unstable data. Never retry a write
       * or accept the failed first readback because a later read matches. */
      unsigned first_stage = wt_stage, first_r1 = wt_r1;
      unsigned first_token = wt_token, first_status = wt_status;
      const char *first_phase = wt_phase;
      wt_repeat_error = sd_read(lba, wt_repeat) ? wt_error : 0;
      wt_repeat_valid = !wt_repeat_error;
      wt_stage = first_stage; wt_r1 = first_r1;
      wt_token = first_token; wt_status = first_status; wt_phase = first_phase;
    }
    wt_poison = 1;
    return error(result ? wt_error : WT_VERIFY);
  }
  wt_error = 0;
  return 0;
}

int wt_write(U32 lba, const U8 *p, int bad_crc) {
  int result;
  in_write = 1;
  result = write_block(lba, p, bad_crc);
  in_write = 0;
  return result;
}
