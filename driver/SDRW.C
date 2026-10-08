/* SPDX-License-Identifier: GPL-3.0-or-later
 * Resident CRC-checked SDHC/SDXC transport. No heap, DOS calls or diagnostics
 * strings. Each retry writes the same snapshotted sector to the same address.
 * Full reset/CRC initialization and matching CID/capacity precede retries.
 */
#include "RWSD.H"
#include <string.h>
U16 sd_port=0x330;
SdDiagnostic sd_diag;
U32 sd_last_lba;
int sd_write_enabled;
int sd_verify_writes=1;
static U8 identity[16], expected[512];
/* Filesystem scratch may supply a write's input. expected freezes it before
 * reception; successful verification restores these same bytes. Failure
 * aborts the caller, which must not reuse the overwritten scratch. */
U8 sd_scratch[512];
#define actual sd_scratch
static U32 allowed_first, allowed_end;
static U8 identified, protected_card, armed;
#ifndef HOST_TEST
#define rw_reg_write(o,v) outportb(sd_port+(o),(v))
#define rw_reg_read(o) inportb(sd_port+(o))
static U16 rw_ticks(void) { return *(volatile U16 far *)MK_FP(0x40,0x6c); }
#endif
U16 sd_ticks(void) { return rw_ticks(); }
int sd_card_info(U8 *cid,U32 *last_lba) {
    *last_lba=sd_last_lba;
    memset(cid,0,16);
    if (!identified) return 0;
    memcpy(cid,identity,16); return 1;
}
/* OUT base+0 starts a byte burst; two RX reads allow it to settle.
 * IN base+0 does not clock the card. OUT base+2/3 releases/asserts CS;
 * IN base+3 instead raises the board's MISO pull latch. */
static void settle(void) { (void)rw_reg_read(0); (void)rw_reg_read(0); }
static U8 io(U8 b) {
    rw_reg_write(0,b); settle(); return rw_reg_read(0);
}
static void select_card(int selected) {
    rw_reg_write(selected?3:2,255); settle();
}
static void finish(void) {
    (void)io(255); select_card(0); (void)io(255);
}
static int fail(U16 code) { sd_diag.error=code; return -1; }
/* SD CRC16 (x^16+x^12+x^5+1), initial remainder zero.
 * Byte tables avoid bit loops; they do not change SPI pacing or checks. */
static const U16 crc16_table[256]={
    0x0000,0x1021,0x2042,0x3063,0x4084,0x50a5,0x60c6,0x70e7,
    0x8108,0x9129,0xa14a,0xb16b,0xc18c,0xd1ad,0xe1ce,0xf1ef,
    0x1231,0x0210,0x3273,0x2252,0x52b5,0x4294,0x72f7,0x62d6,
    0x9339,0x8318,0xb37b,0xa35a,0xd3bd,0xc39c,0xf3ff,0xe3de,
    0x2462,0x3443,0x0420,0x1401,0x64e6,0x74c7,0x44a4,0x5485,
    0xa56a,0xb54b,0x8528,0x9509,0xe5ee,0xf5cf,0xc5ac,0xd58d,
    0x3653,0x2672,0x1611,0x0630,0x76d7,0x66f6,0x5695,0x46b4,
    0xb75b,0xa77a,0x9719,0x8738,0xf7df,0xe7fe,0xd79d,0xc7bc,
    0x48c4,0x58e5,0x6886,0x78a7,0x0840,0x1861,0x2802,0x3823,
    0xc9cc,0xd9ed,0xe98e,0xf9af,0x8948,0x9969,0xa90a,0xb92b,
    0x5af5,0x4ad4,0x7ab7,0x6a96,0x1a71,0x0a50,0x3a33,0x2a12,
    0xdbfd,0xcbdc,0xfbbf,0xeb9e,0x9b79,0x8b58,0xbb3b,0xab1a,
    0x6ca6,0x7c87,0x4ce4,0x5cc5,0x2c22,0x3c03,0x0c60,0x1c41,
    0xedae,0xfd8f,0xcdec,0xddcd,0xad2a,0xbd0b,0x8d68,0x9d49,
    0x7e97,0x6eb6,0x5ed5,0x4ef4,0x3e13,0x2e32,0x1e51,0x0e70,
    0xff9f,0xefbe,0xdfdd,0xcffc,0xbf1b,0xaf3a,0x9f59,0x8f78,
    0x9188,0x81a9,0xb1ca,0xa1eb,0xd10c,0xc12d,0xf14e,0xe16f,
    0x1080,0x00a1,0x30c2,0x20e3,0x5004,0x4025,0x7046,0x6067,
    0x83b9,0x9398,0xa3fb,0xb3da,0xc33d,0xd31c,0xe37f,0xf35e,
    0x02b1,0x1290,0x22f3,0x32d2,0x4235,0x5214,0x6277,0x7256,
    0xb5ea,0xa5cb,0x95a8,0x8589,0xf56e,0xe54f,0xd52c,0xc50d,
    0x34e2,0x24c3,0x14a0,0x0481,0x7466,0x6447,0x5424,0x4405,
    0xa7db,0xb7fa,0x8799,0x97b8,0xe75f,0xf77e,0xc71d,0xd73c,
    0x26d3,0x36f2,0x0691,0x16b0,0x6657,0x7676,0x4615,0x5634,
    0xd94c,0xc96d,0xf90e,0xe92f,0x99c8,0x89e9,0xb98a,0xa9ab,
    0x5844,0x4865,0x7806,0x6827,0x18c0,0x08e1,0x3882,0x28a3,
    0xcb7d,0xdb5c,0xeb3f,0xfb1e,0x8bf9,0x9bd8,0xabbb,0xbb9a,
    0x4a75,0x5a54,0x6a37,0x7a16,0x0af1,0x1ad0,0x2ab3,0x3a92,
    0xfd2e,0xed0f,0xdd6c,0xcd4d,0xbdaa,0xad8b,0x9de8,0x8dc9,
    0x7c26,0x6c07,0x5c64,0x4c45,0x3ca2,0x2c83,0x1ce0,0x0cc1,
    0xef1f,0xff3e,0xcf5d,0xdf7c,0xaf9b,0xbfba,0x8fd9,0x9ff8,
    0x6e17,0x7e36,0x4e55,0x5e74,0x2e93,0x3eb2,0x0ed1,0x1ef0
};
/* Command CRC7 (x^7+x^3+1). Index contains the previous
 * seven-bit remainder and the next command byte. */
static const U8 crc7_table[256]={
    0x00,0x09,0x12,0x1b,0x24,0x2d,0x36,0x3f,
    0x48,0x41,0x5a,0x53,0x6c,0x65,0x7e,0x77,
    0x19,0x10,0x0b,0x02,0x3d,0x34,0x2f,0x26,
    0x51,0x58,0x43,0x4a,0x75,0x7c,0x67,0x6e,
    0x32,0x3b,0x20,0x29,0x16,0x1f,0x04,0x0d,
    0x7a,0x73,0x68,0x61,0x5e,0x57,0x4c,0x45,
    0x2b,0x22,0x39,0x30,0x0f,0x06,0x1d,0x14,
    0x63,0x6a,0x71,0x78,0x47,0x4e,0x55,0x5c,
    0x64,0x6d,0x76,0x7f,0x40,0x49,0x52,0x5b,
    0x2c,0x25,0x3e,0x37,0x08,0x01,0x1a,0x13,
    0x7d,0x74,0x6f,0x66,0x59,0x50,0x4b,0x42,
    0x35,0x3c,0x27,0x2e,0x11,0x18,0x03,0x0a,
    0x56,0x5f,0x44,0x4d,0x72,0x7b,0x60,0x69,
    0x1e,0x17,0x0c,0x05,0x3a,0x33,0x28,0x21,
    0x4f,0x46,0x5d,0x54,0x6b,0x62,0x79,0x70,
    0x07,0x0e,0x15,0x1c,0x23,0x2a,0x31,0x38,
    0x41,0x48,0x53,0x5a,0x65,0x6c,0x77,0x7e,
    0x09,0x00,0x1b,0x12,0x2d,0x24,0x3f,0x36,
    0x58,0x51,0x4a,0x43,0x7c,0x75,0x6e,0x67,
    0x10,0x19,0x02,0x0b,0x34,0x3d,0x26,0x2f,
    0x73,0x7a,0x61,0x68,0x57,0x5e,0x45,0x4c,
    0x3b,0x32,0x29,0x20,0x1f,0x16,0x0d,0x04,
    0x6a,0x63,0x78,0x71,0x4e,0x47,0x5c,0x55,
    0x22,0x2b,0x30,0x39,0x06,0x0f,0x14,0x1d,
    0x25,0x2c,0x37,0x3e,0x01,0x08,0x13,0x1a,
    0x6d,0x64,0x7f,0x76,0x49,0x40,0x5b,0x52,
    0x3c,0x35,0x2e,0x27,0x18,0x11,0x0a,0x03,
    0x74,0x7d,0x66,0x6f,0x50,0x59,0x42,0x4b,
    0x17,0x1e,0x05,0x0c,0x33,0x3a,0x21,0x28,
    0x5f,0x56,0x4d,0x44,0x7b,0x72,0x69,0x60,
    0x0e,0x07,0x1c,0x15,0x2a,0x23,0x38,0x31,
    0x46,0x4f,0x54,0x5d,0x62,0x6b,0x70,0x79
};
U16 sd_crc16(const U8 *p,U16 count) {
    U16 crc=0;
    while (count--) crc=(U16)((crc<<8)^crc16_table[((crc>>8)^*p++)&255]);
    return crc;
}
static U8 crc7(const U8 *p) {
    U8 crc=0;
    U16 i;
    for (i=0;i<5;++i) crc=crc7_table[(U8)((crc<<1)^p[i])];
    return (U8)((crc<<1)|1);
}
#ifdef HOST_TEST
/* Expose command CRC only to the independent host oracle. */
U8 sd_test_crc7(const U8 *p) { return crc7(p); }
#endif
/* BIOS ticks are about 55 ms. Unsigned subtraction tolerates low-word wrap;
 * the poll limit also bounds a wait when the BIOS clock is not advancing. */
static int ready(U16 ticks, U16 consecutive) {
    U16 start=rw_ticks(), idle=0;
    U32 polls;
    for (polls=0;polls<4000000UL;++polls) {
        if (io(255)==255) { if (++idle==consecutive) return 0; }
        else idle=0;
        if ((U16)(rw_ticks()-start)>=ticks) break;
    }
    return fail(SD_TIMEOUT);
}
static int command(U8 cmd, U32 arg) {
    U8 p[6], value;
    U16 i;
    sd_diag.stage=cmd; sd_diag.r1=sd_diag.token=255; sd_diag.status=0;
    finish(); select_card(1);
    /* A cold card may hold MISO low. CMD0 must precede the usual ready wait. */
    if (cmd && ready(90,cmd==13?2:1)) { finish(); return -1; }
    p[0]=(U8)(64|cmd); p[1]=(U8)(arg>>24); p[2]=(U8)(arg>>16);
    p[3]=(U8)(arg>>8); p[4]=(U8)arg; p[5]=crc7(p);
    for (i=0;i<6;++i) {
        value=io(p[i]);
        /* A late busy byte cannot be interpreted as clean CMD13 status. */
        if (cmd==13 && value!=255) { finish(); return fail(SD_TIMEOUT); }
    }
    for (i=0;i<100;++i) {
        sd_diag.r1=io(255);
        if (!(sd_diag.r1&128)) return 0;
    }
    finish(); return fail(SD_TIMEOUT);
}
static int packet(U8 *p, U16 count) {
    U16 start=rw_ticks(),i,crc;
    U32 polls;
    for (polls=0;polls<4000000UL;++polls) {
        sd_diag.token=io(255);
        if (sd_diag.token==254) break;
        if (sd_diag.token!=255) return fail(SD_REJECT);
        if ((U16)(rw_ticks()-start)>=36) return fail(SD_TIMEOUT);
    }
    if (polls==4000000UL) return fail(SD_TIMEOUT);
    for (i=0;i<count;++i) p[i]=io(255);
    crc=(U16)io(255)<<8; crc|=io(255);
    return crc==sd_crc16(p,count)?0:fail(SD_CRC);
}
static int read_register(U8 cmd, U8 *p) {
    int result;
    if (command(cmd,0)) return -1;
    if (sd_diag.r1) { finish(); return fail(SD_IDENTITY); }
    result=packet(p,16); finish(); return result;
}
static int initialize(void) {
    U8 reply[4], csd[16];
    U16 start,i,trial;
    identified=0; protected_card=0;
    /* Wake with MISO pulled high and at least 74 clocks while CS is released.
     * OUT base+1 clocks a byte without loading TX; RX reads only settle it. */
    (void)rw_reg_read(3);
    start=rw_ticks();
    for (trial=0;trial<100;++trial) {
        select_card(0); (void)io(255);
        for (i=0;i<12;++i) { rw_reg_write(1,255); settle(); }
        if (!command(0,0) && sd_diag.r1==1) break;
        finish();
        if ((U16)(rw_ticks()-start)>=90) return fail(SD_IDENTITY);
    }
    if (trial==100) return fail(SD_IDENTITY);
    finish();
    if (command(8,0x1aaUL)) return -1;
    if (sd_diag.r1!=1) { finish(); return fail(SD_IDENTITY); }
    for (i=0;i<4;++i) reply[i]=io(255);
    finish();
    if (reply[2]!=1 || reply[3]!=170) return fail(SD_IDENTITY);
    if (command(59,1)) return -1;
    finish(); if (sd_diag.r1!=1) return fail(SD_CRC);
    start=rw_ticks();
    for (trial=0;trial<65535U;++trial) {
        if (command(55,0)) return -1;
        finish(); if (sd_diag.r1>1) return fail(SD_IDENTITY);
        if (command(41,0x40000000UL)) return -1;
        finish(); if (!sd_diag.r1) break;
        if (sd_diag.r1!=1) return fail(SD_IDENTITY);
        if ((U16)(rw_ticks()-start)>=90) return fail(SD_TIMEOUT);
    }
    if (trial==65535U) return fail(SD_TIMEOUT);
    if (command(58,0)) return -1;
    if (sd_diag.r1) { finish(); return fail(SD_IDENTITY); }
    for (i=0;i<4;++i) reply[i]=io(255);
    finish(); if ((reply[0]&192)!=192) return fail(SD_IDENTITY);
    if (command(59,1)) return -1;
    finish(); if (sd_diag.r1) return fail(SD_CRC);
    if (read_register(10,identity) || read_register(9,csd)) return -1;
    if ((csd[0]>>6)!=1) return fail(SD_RANGE);
    sd_last_lba=(((U32)(csd[7]&63)<<16)|((U32)csd[8]<<8)|csd[9]);
    sd_last_lba=(sd_last_lba<<10)|1023UL;
    protected_card=(U8)(csd[14]&48); identified=1; sd_diag.error=0;
    return 0;
}
void sd_write_disarm(void) { armed=0; }
void sd_release(void) {
    /* Preserve failure evidence for the application's diagnostic query. */
    finish(); identified=0; armed=0; (void)rw_reg_read(3);
}
int sd_init(void) {
    /* Explicit remount starts a new session; filesystem preflight must then
     * succeed before sd_write_arm can permit any sector mutations. */
    memset(&sd_diag,0,sizeof(sd_diag)); armed=0;
    return initialize()?E_NOTREADY:0;
}
int sd_check_media(void) {
    U8 cid[16];
    if (!identified || sd_diag.poisoned) return E_NOTREADY;
    if (read_register(10,cid) || memcmp(cid,identity,16)) {
        if (!sd_diag.error) (void)fail(SD_IDENTITY);
        identified=0; return E_NOTREADY;
    }
    return 0;
}
static int read_block(U32 lba, U8 *p) {
    int result;
    if (command(17,lba)) return -1;
    if (sd_diag.r1) { finish(); return fail(SD_REJECT); }
    result=packet(p,512); finish(); return result;
}
int sd_read(U32 lba, U8 *buffer) {
    if (sd_diag.poisoned) return E_NOTREADY;
    sd_diag.error=0; sd_diag.lba=lba;
    if (sd_check_media()) return E_NOTREADY;
    if (lba>sd_last_lba) { (void)fail(SD_RANGE); return E_READ; }
    return read_block(lba,buffer)?E_READ:0;
}
int sd_write_arm(U32 first, U32 end) {
    armed=0;
    if (!sd_write_enabled || protected_card) return E_ACCESS;
    if (!identified || sd_diag.poisoned) return E_NOTREADY;
    if (first>=end || end-1>sd_last_lba) return E_INVALID;
    allowed_first=first; allowed_end=end; armed=1; return 0;
}
static int write_once(U32 lba) {
    U16 crc=sd_crc16(expected,512),i;
    if (command(24,lba)) return -1;
    if (sd_diag.r1) { finish(); return fail(SD_REJECT); }
    ++sd_diag.transmissions;
    (void)io(255); (void)io(254);
    for (i=0;i<512;++i) (void)io(expected[i]);
    (void)io((U8)(crc>>8)); (void)io((U8)crc);
    sd_diag.stage=124;
    for (i=0;i<100;++i) {
        sd_diag.token=io(255); if (sd_diag.token!=255) break;
    }
    if ((sd_diag.token&31)!=5) {
        U16 code=(sd_diag.token&31)==11?SD_CRC:
                 sd_diag.token==255?SD_TIMEOUT:SD_REJECT;
        if (code==SD_CRC) {
            sd_diag.stage=324;
            if (ready(90,2)) { finish(); return -1; }
        }
        finish(); return fail(code);
    }
    sd_diag.stage=224;
    if (ready(90,2)) { finish(); return -1; }
    finish();
    if (command(13,0)) return -1;
    sd_diag.status=io(255); finish();
    if (sd_diag.r1 || sd_diag.status) return fail(SD_STATUS);
    if (sd_check_media()) return fail(SD_IDENTITY);
    if (sd_verify_writes) {
        if (read_block(lba,actual)) return -1;
        if (memcmp(expected,actual,512)) return fail(SD_VERIFY);
    } else {
        /* Recovery reads overwrite shared scratch. Restore its frozen input
         * even when this successful attempt has no post-write readback. */
        memcpy(actual,expected,512);
    }
    return 0;
}
static int recover(U32 lba) {
    U8 cid[16];
    U32 capacity=sd_last_lba;
    memcpy(cid,identity,16);
    if (initialize()) return -1;
    if (memcmp(cid,identity,16) || sd_last_lba!=capacity || protected_card)
        return fail(SD_IDENTITY);
    if (sd_check_media()) return fail(SD_IDENTITY);
    /* CID/status alone do not establish usable sector access. This read must
     * have valid CRC, but need not equal expected: the retry replaces it. */
    return read_block(lba,actual);
}
int sd_write(U32 lba, const U8 *buffer) {
    U16 first=0;
    if (sd_diag.poisoned) return E_NOTREADY;
    sd_diag.lba=lba; sd_diag.attempts=0; sd_diag.first_error=0;
    sd_diag.first_stage=sd_diag.first_r1=sd_diag.first_token=sd_diag.first_status=0;
    if (!sd_write_enabled || !armed || protected_card) return E_ACCESS;
    if (sd_check_media()) { sd_diag.poisoned=1; armed=0; return E_NOTREADY; }
    if (lba<allowed_first || lba>=allowed_end) return E_ACCESS;
    /* Freeze the entire payload once. Reset/recovery must never change this
     * snapshot or the target LBA. Three attempts includes the initial one. */
    memcpy(expected,buffer,512);
    for (sd_diag.attempts=1;sd_diag.attempts<=3;++sd_diag.attempts) {
        sd_diag.error=0;
        if (!write_once(lba)) {
            ++sd_diag.verified; sd_diag.error=0; return 0;
        }
        if (!first) {
            first=sd_diag.error;
            sd_diag.first_stage=sd_diag.stage; sd_diag.first_r1=sd_diag.r1;
            sd_diag.first_token=sd_diag.token; sd_diag.first_status=sd_diag.status;
        }
        sd_diag.first_error=first;
        if (sd_diag.attempts==3 || recover(lba)) break;
        ++sd_diag.retries;
    }
    sd_diag.poisoned=1; armed=0;
    return sd_diag.error==SD_IDENTITY?E_NOTREADY:E_WRITE;
}
