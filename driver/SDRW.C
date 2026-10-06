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
static U8 identity[16], expected[512], actual[512];
static U32 allowed_first, allowed_end;
static U8 identified, protected_card, armed;
#ifndef HOST_TEST
#define rw_reg_write(o,v) outportb(sd_port+(o),(v))
#define rw_reg_read(o) inportb(sd_port+(o))
static U16 rw_ticks(void) { return *(volatile U16 far *)MK_FP(0x40,0x6c); }
#endif
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
U16 sd_crc16(const U8 *p, U16 count) {
    U16 crc=0, i;
    while (count--) {
        crc^=(U16)*p++<<8;
        for (i=0;i<8;++i)
            crc=(U16)((crc<<1)^((crc&0x8000)?0x1021:0));
    }
    return crc;
}
static U8 crc7(const U8 *p) {
    U8 crc=0,b;
    U16 i,n;
    for (n=0;n<5;++n) {
        b=p[n];
        for (i=0;i<8;++i) {
            crc<<=1; if ((b^crc)&128) crc^=9; b<<=1;
        }
    }
    return (U8)((crc<<1)|1);
}
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
    if (read_block(lba,actual)) return -1;
    if (memcmp(expected,actual,512)) return fail(SD_VERIFY);
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
