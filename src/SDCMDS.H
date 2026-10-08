/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    SDCMDS.H
 *  Author:  Ivo Filot <ivo@ivofilot.nl>
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <https://www.gnu.org/licenses/>.
 * ===================================================================== */

#ifndef _SDCMDS_H
#define _SDCMDS_H

#include<dos.h>


/*
 * Send idle clocks to the SD-card.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *
 * Notes:
 *      The assembly currently sends 12 bytes of 0xFF, or 96 clock pulses.
 *      This is used while bringing the card into SPI mode.
 */
void cmdclr(unsigned baseio);

/*
 * Receive a single non-0xFF byte from the SD-card.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *
 * Returns:
 *      First received byte that is not 0xFF, or 0xFF if no such byte is
 *      received within 10 attempts.
 */
unsigned char sdrecvf(unsigned baseio);

/*
 * Send CMD00: GO_IDLE_STATE.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *
 * Returns:
 *      R1 response byte from the card. During initialization, 0x01 indicates
 *      that the card has entered idle state.
 */
unsigned char cmd00(unsigned baseio);

/*
 * Send CMD08: SEND_IF_COND.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *      rsp    - Pointer to a 5-byte response buffer. The assembly stores the
 *               complete R7 response here:
 *                   rsp[0] = R1 status byte
 *                   rsp[1] = voltage/check-pattern byte 3
 *                   rsp[2] = voltage/check-pattern byte 2
 *                   rsp[3] = voltage/check-pattern byte 1
 *                   rsp[4] = voltage/check-pattern byte 0
 *
 * Returns:
 *      Same value as rsp[0], the initial R1 response byte returned by CMD08.
 */
unsigned char cmd08(unsigned baseio, unsigned char rsp[]);

/*
 * Send CMD55: APP_CMD.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *
 * Returns:
 *      R1 response byte from the card. A following ACMD is only meaningful if
 *      this command is accepted by the card.
 */
unsigned char cmd55(unsigned baseio);

/*
 * Send ACMD41: SD_SEND_OP_COND.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *
 * Returns:
 *      R1 response byte from the card. During initialization, 0x00 indicates
 *      that the card has left idle state and is ready.
 */
unsigned char acmd41(unsigned baseio);

/*
 * Send CMD58: READ_OCR.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *      rsp    - Pointer to a 5-byte response buffer. The assembly stores the
 *               complete R3 response here:
 *                   rsp[0] = R1 status byte
 *                   rsp[1] = OCR byte 3
 *                   rsp[2] = OCR byte 2
 *                   rsp[3] = OCR byte 1
 *                   rsp[4] = OCR byte 0
 *
 * Returns:
 *      Same value as rsp[0], the initial R1 response byte returned by CMD58.
 */
unsigned char cmd58(unsigned baseio, unsigned char rsp[]);

/*
 * Send CMD17: READ_SINGLE_BLOCK.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *      addr   - 32-bit command argument sent to the card, MSB first. For the
 *               initialized high-capacity cards used by this project, this is
 *               the sector/LBA address.
 *      buf    - Pointer to a 514-byte destination buffer. The assembly stores
 *               the 512-byte block payload followed by the 2-byte CRC from
 *               the card.
 *
 * Returns:
 *      0x00 on successful read.
 *      0xFF if the data token is not received before timeout.
 *      Otherwise, the non-zero R1 command response returned by the card.
 */
unsigned char cmd17(unsigned baseio, unsigned long addr, unsigned char* buf);

/*
 * Send CMD24: WRITE_SINGLE_BLOCK.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 *      addr   - 32-bit command argument sent to the card, MSB first. For the
 *               initialized high-capacity cards used by this project, this is
 *               the sector/LBA address.
 *      buf    - Pointer to a 514-byte source buffer. The assembly sends the
 *               first 512 bytes as the block payload and the final 2 bytes as
 *               the CRC bytes required by the SD write protocol.
 *
 * Returns:
 *      0x00 on successful write.
 *      0xFF on command/response/busy timeout.
 *      Otherwise, either the non-zero R1 command response or the masked data
 *      response token from the card. A masked data response of 0x05 means
 *      accepted and is consumed internally before success is returned.
 */
unsigned char cmd24(unsigned baseio, unsigned long addr, unsigned char* buf);

/*
 * Enable the SD-card by setting /CS low.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 */
void sden(unsigned baseio);

/*
 * Disable the SD-card by setting /CS high.
 *
 * Parameters:
 *      baseio - Base I/O port of the SD-card interface.
 */
void sddis(unsigned baseio);

#endif _SDCMDS_H