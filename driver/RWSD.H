/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef RWSD_H
#define RWSD_H
#include "OTTER.H"
#define E_WRITE 29
#define SD_TIMEOUT 101
#define SD_CRC 102
#define SD_REJECT 103
#define SD_STATUS 104
#define SD_VERIFY 105
#define SD_IDENTITY 106
#define SD_RANGE 107
typedef struct {
    /* Fixed 40-byte DOS diagnostic ABI; no pointers or compiler-sized ints.
     * verified counts completed sector calls; transmissions counts payloads
     * after accepted CMD24; retries counts recovery followed by another try.
     * first_* preserves the initial write failure even if a retry succeeds.
     * Other command fields can change on subsequent reads/identity checks. */
    U32 lba, verified, transmissions, retries;
    U16 error, first_error, stage, r1, token, status, attempts, poisoned;
    U16 first_stage, first_r1, first_token, first_status;
} SdDiagnostic;
/* stage is normally the SD command number. CMD24 sub-stages are 124 (data
 * response), 224 (accepted-write busy) and 324 (CRC-rejection busy).
 * Exact readback mismatch follows CMD17 and normally leaves stage=17. */
extern SdDiagnostic sd_diag;
extern U32 sd_last_lba;
extern int sd_write_enabled;
U16 sd_crc16(const U8 *p, U16 count);
/* Public SD calls return zero or a positive DOS error. SD_* values are the
 * finer diagnostic reason in sd_diag, not an INT 21h application error.
 * The armed range is [first,end), in absolute 512-byte sector addresses. */
int sd_write_arm(U32 first, U32 end);
void sd_write_disarm(void);
int sd_write(U32 lba, const U8 *buffer);
/* Poison blocks further reads/writes without erasing the failure snapshot.
 * sd_init clears it; sd_release only disarms and preserves diagnostics. */
#ifdef HOST_TEST
void rw_reg_write(U16 offset, U8 value);
U8 rw_reg_read(U16 offset);
U16 rw_ticks(void);
#endif
#endif
