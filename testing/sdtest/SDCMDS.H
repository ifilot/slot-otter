#ifndef _SDCMDS_H
#define _SDCMDS_H

#include<dos.h>

#define BASEPORT 0x330

/*
 * Send 80 'clearing bits' to the SD-card to reset it
 */
void cmdclr(unsigned baseio);

/*
 * Receive single non-0xFF byte from SD-card
 */
unsigned char sdrecvf(unsigned baseio);

/*
 * Send CMD00; includes additional processing bit
 */
unsigned char cmd00(unsigned baseio);

/*
 * Send CMD08; includes additional processing bit
 */
unsigned char cmd08(unsigned baseio, unsigned char *rsp);

/*
 * Send CMD55
 */
unsigned char cmd55(unsigned baseio);

/*
 * Send ACMD41
 */
unsigned char acmd41(unsigned baseio);

/*
 * Send CMD58
 */
unsigned char cmd58(unsigned baseio, unsigned char *rsp);

/*
 * Send CMD17
 */
unsigned char cmd17(unsigned baseio, unsigned long addr, unsigned char* buf);

/*
 * Enable the SD-card by setting /CS low
 */
void sden(unsigned baseio);

/*
 * Disable the SD-card by setting /CS high
 */
void sddis(unsigned baseio);

#endif _SDCMDS_H