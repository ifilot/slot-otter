/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "OTTER.H"
#include <string.h>
U16 sd_port = 0x330;
void cmdclr(unsigned port);
void sddis(unsigned port);
unsigned char cmd00(unsigned port);
unsigned char cmd08(unsigned port, unsigned char *response);
unsigned char cmd55(unsigned port);
unsigned char acmd41(unsigned port);
unsigned char cmd58(unsigned port, unsigned char *response);
unsigned char cmd17(unsigned port, unsigned long lba, unsigned char *buffer);
static U8 card_id[16];
static int identity_valid;

void sd_release(void) {
    sddis(sd_port); identity_valid=0;
    (void)inportb(sd_port+3);
}
/* CMD10 uses a 16-byte data packet. All waits are bounded; no DOS calls. */
static int read_id(U8 id[16]) {
    U16 trial, i;
    U8 response;
    outportb(sd_port,0xff); outportb(sd_port+3,0xff);
    outportb(sd_port,0x4a);
    for (i=0;i<4;++i) outportb(sd_port,0);
    outportb(sd_port,1);
    response=0xff;
    for (trial=0;trial<100;++trial) {
        outportb(sd_port+1,0xff); response=inportb(sd_port);
        if (response!=0xff) break;
    }
    if (response) { sddis(sd_port); return -1; }
    for (trial=0;trial<65535U;++trial) {
        outportb(sd_port+1,0xff); response=inportb(sd_port);
        if (response==0xfe) break;
    }
    if (trial==65535U) { sddis(sd_port); return -1; }
    outportb(sd_port+1,0xff);
    for (i=0;i<18;++i) {
        response=inportb(sd_port+1);
        if (i<16) id[i]=response;
    }
    outportb(sd_port,0xff); sddis(sd_port);
    return 0;
}
int sd_check_media(void) {
    U8 id[16];
    /* A selected, initialized card drives idle MISO high. The empty socket
     * follows the schematic's weak pull latch instead. Restore it afterward. */
    outportb(sd_port+3,0xff); (void)inportb(sd_port+2);
    outportb(sd_port,0xff);
    if (inportb(sd_port)==0) {
        (void)inportb(sd_port+3); sddis(sd_port); return -1;
    }
    (void)inportb(sd_port+3); sddis(sd_port);
    return !identity_valid || read_id(id) || memcmp(id,card_id,16) ? -1 : 0;
}

int sd_init(void) {
    U16 trial, started;
    U8 reply[5];
    identity_valid=0;
    (void)inportb(sd_port+3);      /* schematic: pull MISO high when absent */
    for (trial=0; trial<100; ++trial) {
        sddis(sd_port); cmdclr(sd_port);
        if (cmd00(sd_port)==1) break;
    }
    if (trial==100 || cmd08(sd_port, reply)!=1 ||
        reply[3]!=1 || reply[4]!=0xaa) return -1;
    started=*(volatile U16 far *)MK_FP(0x40,0x6c);
    for (trial=0; trial<65535U; ++trial) {
        if (cmd55(sd_port)==1 && acmd41(sd_port)==0) break;
        if ((U16)(*(volatile U16 far *)MK_FP(0x40,0x6c)-started)>=36)
            return -1;
    }
    if (trial==65535U || cmd58(sd_port, reply)!=0 ||
        (reply[1]&0xc0)!=0xc0) return -1;
    /* SDHC/SDXC block addressing only, matching the existing card utility. */
    if (read_id(card_id)) return -1;
    identity_valid=1;
    return 0;
}
int sd_read(U32 lba, U8 *buffer) {
    if (sd_check_media()) return E_NOTREADY;
    /* The filesystem invalidates the cache tag before calling us and publishes
     * it only on success. CMD17 consumes CRC separately from the payload. */
    if (cmd17(sd_port, lba, buffer)) return E_READ;
    return 0;
}
