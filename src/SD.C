/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    SD.C
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

#include "sd.h"

/*
 * sd_boot - Boot SD card
 *
 * Returns:
 *      0 if success, otherwise on fail
 */
int sd_boot() {
    int i, j, ctr;
    unsigned char v, c1, c2;
    unsigned char *ptr;
    unsigned char rsp5[5];

    sd_set_miso_high(BASEPORT);

    ctr = 0;
    v = 0xFF;
    while(v != 0x01 & ctr < MAXTRIAL) {
        sddis(BASEPORT);
        cmdclr(BASEPORT);
        sden(BASEPORT);
        v = cmd00(BASEPORT);	/* put card in idle state */
        ctr++;
    }

    if(ctr >= MAXTRIAL) {
        printf("Cannot put card in idle mode.\n");
        printf("Try to reinsert the card.\n");
        sddis(BASEPORT);
        return -1;
    }
    
    printf("CMD00 response: %02X\n", v);
    v = cmd08(BASEPORT, rsp5);	/* send cmd08 */
    printf("CMD08 response: ");
    
    for(i=0; i<5; ++i) {
        printf("%02X ", rsp5[i]);
    }
    printf("\n");

    /* TRY ACMD41 */
    v = 0xFF;
    ctr = 0;
    while(v != 0x00 && ctr < MAXTRIAL) {
        delay(1); /* wait one ms */
        v = cmd55(BASEPORT);
        if(v == 0xFF) {
            continue;	/* try again on 0xFF */
        }
        v = acmd41(BASEPORT);
        ctr++;
    }

    if(ctr >= MAXTRIAL) {
        printf("Unable to send ACMD41 after %i attempts.\n", ctr);
        return -1;
    } else {
        printf("ACMD41 response: %02X (%i)\n", v, ctr);
    }

    /* CMD58 - READ OCR */
    v = cmd58(BASEPORT, rsp5);
    printf("CMD58 response: ");
    for(i=0; i<5; ++i) {
        printf("%02X ", rsp5[i]);
    }
    
    printf("\n");
    return 0;
}

/*
 * Pulls the MISO line low
 *
 * Parameters:
 *      ioport - Which base IO address
 */
void sd_set_miso_low(unsigned ioport) {
    outportb(ioport | 0x02, 0xFF);
}

/*
 * Pulls the MISO line high
 *
 * Parameters:
 *      ioport - Which base IO address
 */
void sd_set_miso_high(unsigned ioport) {
    outportb(ioport | 0x03, 0xFF);
}

/*
 * Disables SD card (pulls /ENABLE HIGH)
 *
 * Parameters:
 *      ioport - Which base IO address
 */
void sd_disable(unsigned ioport) {
    sddis(ioport);
}