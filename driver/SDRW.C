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
/* Bulk 512-byte payloads only. The port stays in a register and the I/O is
 * inline, so each byte is OUT, three settling INs and the sampling IN. The
 * extra settling IN keeps OUT-to-sample at three full ISA bus cycles, never
 * shorter than io()'s two INs plus call overhead on a fast CPU, and above
 * the CPLD's 1.5 us request/result spacing on an 8088 bus. Command framing,
 * busy and token polling keep io(). Order and CS state are unchanged. */
#ifdef HOST_TEST
#define DATA_PORT 0
#define port_out(port,v) rw_reg_write((port),(v))
#define port_in(port) rw_reg_read(port)
#else
#define DATA_PORT sd_port
#define port_out(port,v) outportb((port),(v))
#define port_in(port) inportb(port)
#endif
#define bulk_settle(port) \
    { (void)port_in(port); (void)port_in(port); (void)port_in(port); }
static void receive(register U8 *p, U16 count) {
    register U16 port=DATA_PORT;
    U8 *end=p+count;
    while (p!=end) { port_out(port,255); bulk_settle(port); *p++=port_in(port); }
}
static void send(register const U8 *p, U16 count) {
    register U16 port=DATA_PORT;
    const U8 *end=p+count;
    while (p!=end) {
        port_out(port,*p++); bulk_settle(port); (void)port_in(port);
    }
}
static void select_card(int selected) {
    rw_reg_write(selected?3:2,255); settle();
}
static void finish(void) {
    (void)io(255); select_card(0); (void)io(255);
}
static int fail(U16 code) { sd_diag.error=code; return -1; }
/* SD CRC16 (x^16+x^12+x^5+1), initial remainder zero.
 * Split high/low byte tables avoid bit loops and the 16-bit shifts Turbo C
 * emits for crc<<8 and crc>>8; they do not change SPI pacing or checks. */
static const U8 crc16_hi[256]={
    0x00,0x10,0x20,0x30,0x40,0x50,0x60,0x70,
    0x81,0x91,0xa1,0xb1,0xc1,0xd1,0xe1,0xf1,
    0x12,0x02,0x32,0x22,0x52,0x42,0x72,0x62,
    0x93,0x83,0xb3,0xa3,0xd3,0xc3,0xf3,0xe3,
    0x24,0x34,0x04,0x14,0x64,0x74,0x44,0x54,
    0xa5,0xb5,0x85,0x95,0xe5,0xf5,0xc5,0xd5,
    0x36,0x26,0x16,0x06,0x76,0x66,0x56,0x46,
    0xb7,0xa7,0x97,0x87,0xf7,0xe7,0xd7,0xc7,
    0x48,0x58,0x68,0x78,0x08,0x18,0x28,0x38,
    0xc9,0xd9,0xe9,0xf9,0x89,0x99,0xa9,0xb9,
    0x5a,0x4a,0x7a,0x6a,0x1a,0x0a,0x3a,0x2a,
    0xdb,0xcb,0xfb,0xeb,0x9b,0x8b,0xbb,0xab,
    0x6c,0x7c,0x4c,0x5c,0x2c,0x3c,0x0c,0x1c,
    0xed,0xfd,0xcd,0xdd,0xad,0xbd,0x8d,0x9d,
    0x7e,0x6e,0x5e,0x4e,0x3e,0x2e,0x1e,0x0e,
    0xff,0xef,0xdf,0xcf,0xbf,0xaf,0x9f,0x8f,
    0x91,0x81,0xb1,0xa1,0xd1,0xc1,0xf1,0xe1,
    0x10,0x00,0x30,0x20,0x50,0x40,0x70,0x60,
    0x83,0x93,0xa3,0xb3,0xc3,0xd3,0xe3,0xf3,
    0x02,0x12,0x22,0x32,0x42,0x52,0x62,0x72,
    0xb5,0xa5,0x95,0x85,0xf5,0xe5,0xd5,0xc5,
    0x34,0x24,0x14,0x04,0x74,0x64,0x54,0x44,
    0xa7,0xb7,0x87,0x97,0xe7,0xf7,0xc7,0xd7,
    0x26,0x36,0x06,0x16,0x66,0x76,0x46,0x56,
    0xd9,0xc9,0xf9,0xe9,0x99,0x89,0xb9,0xa9,
    0x58,0x48,0x78,0x68,0x18,0x08,0x38,0x28,
    0xcb,0xdb,0xeb,0xfb,0x8b,0x9b,0xab,0xbb,
    0x4a,0x5a,0x6a,0x7a,0x0a,0x1a,0x2a,0x3a,
    0xfd,0xed,0xdd,0xcd,0xbd,0xad,0x9d,0x8d,
    0x7c,0x6c,0x5c,0x4c,0x3c,0x2c,0x1c,0x0c,
    0xef,0xff,0xcf,0xdf,0xaf,0xbf,0x8f,0x9f,
    0x6e,0x7e,0x4e,0x5e,0x2e,0x3e,0x0e,0x1e
};
static const U8 crc16_lo[256]={
    0x00,0x21,0x42,0x63,0x84,0xa5,0xc6,0xe7,
    0x08,0x29,0x4a,0x6b,0x8c,0xad,0xce,0xef,
    0x31,0x10,0x73,0x52,0xb5,0x94,0xf7,0xd6,
    0x39,0x18,0x7b,0x5a,0xbd,0x9c,0xff,0xde,
    0x62,0x43,0x20,0x01,0xe6,0xc7,0xa4,0x85,
    0x6a,0x4b,0x28,0x09,0xee,0xcf,0xac,0x8d,
    0x53,0x72,0x11,0x30,0xd7,0xf6,0x95,0xb4,
    0x5b,0x7a,0x19,0x38,0xdf,0xfe,0x9d,0xbc,
    0xc4,0xe5,0x86,0xa7,0x40,0x61,0x02,0x23,
    0xcc,0xed,0x8e,0xaf,0x48,0x69,0x0a,0x2b,
    0xf5,0xd4,0xb7,0x96,0x71,0x50,0x33,0x12,
    0xfd,0xdc,0xbf,0x9e,0x79,0x58,0x3b,0x1a,
    0xa6,0x87,0xe4,0xc5,0x22,0x03,0x60,0x41,
    0xae,0x8f,0xec,0xcd,0x2a,0x0b,0x68,0x49,
    0x97,0xb6,0xd5,0xf4,0x13,0x32,0x51,0x70,
    0x9f,0xbe,0xdd,0xfc,0x1b,0x3a,0x59,0x78,
    0x88,0xa9,0xca,0xeb,0x0c,0x2d,0x4e,0x6f,
    0x80,0xa1,0xc2,0xe3,0x04,0x25,0x46,0x67,
    0xb9,0x98,0xfb,0xda,0x3d,0x1c,0x7f,0x5e,
    0xb1,0x90,0xf3,0xd2,0x35,0x14,0x77,0x56,
    0xea,0xcb,0xa8,0x89,0x6e,0x4f,0x2c,0x0d,
    0xe2,0xc3,0xa0,0x81,0x66,0x47,0x24,0x05,
    0xdb,0xfa,0x99,0xb8,0x5f,0x7e,0x1d,0x3c,
    0xd3,0xf2,0x91,0xb0,0x57,0x76,0x15,0x34,
    0x4c,0x6d,0x0e,0x2f,0xc8,0xe9,0x8a,0xab,
    0x44,0x65,0x06,0x27,0xc0,0xe1,0x82,0xa3,
    0x7d,0x5c,0x3f,0x1e,0xf9,0xd8,0xbb,0x9a,
    0x75,0x54,0x37,0x16,0xf1,0xd0,0xb3,0x92,
    0x2e,0x0f,0x6c,0x4d,0xaa,0x8b,0xe8,0xc9,
    0x26,0x07,0x64,0x45,0xa2,0x83,0xe0,0xc1,
    0x1f,0x3e,0x5d,0x7c,0x9b,0xba,0xd9,0xf8,
    0x17,0x36,0x55,0x74,0x93,0xb2,0xd1,0xf0
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
U16 sd_crc16(register const U8 *p,U16 count) {
    /* crc'=(crc<<8)^T[(crc>>8)^b], one byte lane at a time. b[1] is the
     * high byte on the little-endian 8086 and on the x86 host tests. */
    union { U16 w; U8 b[2]; } crc;
    const U8 *end=p+count;
    register U16 i;
    crc.w=0;
    while (p!=end) {
        i=crc.b[1]^*p++; crc.b[1]=crc.b[0]^crc16_hi[i]; crc.b[0]=crc16_lo[i];
    }
    return crc.w;
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
    U16 start=rw_ticks(),crc;
    U32 polls;
    for (polls=0;polls<4000000UL;++polls) {
        sd_diag.token=io(255);
        if (sd_diag.token==254) break;
        if (sd_diag.token!=255) return fail(SD_REJECT);
        if ((U16)(rw_ticks()-start)>=36) return fail(SD_TIMEOUT);
    }
    if (polls==4000000UL) return fail(SD_TIMEOUT);
    receive(p,count);
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
    send(expected,512);
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
