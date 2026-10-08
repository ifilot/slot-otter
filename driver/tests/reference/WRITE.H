/* Standalone experimental write tester; never linked into OTTERFS.
 * GPL-3.0-or-later. */
#ifndef OTTER_WRITE_H
#define OTTER_WRITE_H
#include "OTTER.H"
#define WT_TIMEOUT 101
#define WT_CRC 102
#define WT_REJECT 103
#define WT_STATUS 104
#define WT_VERIFY 105
#define WT_MEDIA 106
#define WT_GUARD 107
#define WT_SPACE 108
#define WT_EXISTS 109
#define WT_NOTEMPTY 110
#define WT_POISON 111
#define WT_RANGE 112
extern unsigned wt_error, wt_stage, wt_r1, wt_token, wt_status, wt_poison;
extern U32 wt_lba, wt_writes, wt_reads, wt_busy_max, wt_busy_ticks;
extern U8 wt_cid[16], wt_csd[16], wt_ocr[4];
extern U32 wt_last_lba;
extern unsigned wt_reset_attempts, wt_cmd0_sent, wt_startup_miso;
extern const char *wt_phase;
extern int wt_no_crc, wt_crc_only, wt_normal_only, wt_probe_only;
extern unsigned wt_bad_cmd_count, wt_bad_cmd_crc, wt_bad_cmd_calculated;
extern unsigned wt_bad_cmd_r1, wt_bad_cmd_error;
extern U8 wt_bad_cmd_rx[6], wt_bad_cmd_response[100];
/* First 63 startup commands plus the most recent one if the trace fills. */
extern unsigned wt_init_count, wt_init_command[64], wt_init_r1[64], wt_init_error[64];
extern U32 wt_init_total, wt_init_argument[64];
extern unsigned wt_recovery_count, wt_recovery_r1[2], wt_recovery_status[2];
int wt_recover(void);
extern unsigned wt_trace, wt_write_r1, wt_write_token, wt_program_r1;
extern unsigned wt_program_status, wt_sent_crc, wt_calculated_crc, wt_write_crc;
extern unsigned wt_readback_valid, wt_repeat_valid, wt_repeat_error;
extern unsigned wt_packet_count, wt_packet_crc, wt_packet_calculated;
extern unsigned wt_packet_complete, wt_response_count;
extern unsigned wt_packet_sample_count;
extern U32 wt_packet_polls, wt_packet_ticks;
extern U8 wt_packet_tokens[32];
extern unsigned wt_readback_crc, wt_busy_sample_count, wt_status_sample_count;
extern unsigned wt_busy_entered, wt_status_entered, wt_cmd13_rx_count;
extern U8 wt_cmd13_rx[6];
extern U32 wt_write_busy_polls, wt_write_busy_ticks, wt_status_busy_polls, wt_status_busy_ticks;
extern U8 wt_busy_samples[32], wt_status_samples[32];
extern U8 wt_packet_data[512], wt_response_bytes[100];
extern U32 wt_write_lba;
extern U8 wt_expected[512], wt_readback[512], wt_repeat[512];
U8 wt_crc7(const U8 *p, unsigned n);
U16 wt_crc16(const U8 *p, unsigned n);
int wt_crc_mode(int enabled);
int wt_bad_command(void);
int wt_write(U32 lba, const U8 *p, int bad_crc);
void wt_disarm(void);
int wt_arm(U32 first, U32 end);
#ifdef HOST_TEST
void wt_reg_write(unsigned offset, U8 value);
U8 wt_reg_read(unsigned offset);
U8 wt_io(U8 value);
void wt_select(int selected);
void wt_pull_high(void);
U16 wt_ticks(void);
#endif

typedef struct {
  U32 first, last, size, lba;
  U16 offset;
  U8 directory;
} WFile;
extern U32 wf_start, wf_end, wf_fatsz, wf_allocated, wf_freed;
extern const char *wf_preflight;
extern int wf_allow_hints, wf_hint_mismatch;
int wf_prepare(void);
int wt_diagnose(void);
int wf_begin(void);
int wf_hint(U32 cluster);
int wf_finish(void);
int wf_mkdir(U32 parent, const char *name, WFile *file);
int wf_create(U32 parent, const char *name, WFile *file);
int wf_read(const WFile *file, U32 pos, U8 *data, U16 count, U16 *done);
int wf_append(WFile *file, const U8 *data, unsigned count);
int wf_overwrite(WFile *file, U32 pos, const U8 *data, unsigned count);
int wf_truncate(WFile *file, U32 size);
int wf_delete(WFile *file);
int wf_rmdir(WFile *file);
U32 wf_fat(U32 cluster);
#endif
