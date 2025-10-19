/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    CRC16.H
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


#ifndef _CRC16_H
#define _CRC16_H

/**
 *  crc16_c - Compute CRC-16 checksum (X-MODEM standard) using custom assembly
 *            routines
 *
 *  This function calculates a 16-bit CRC (Cyclic Redundancy Check)
 *  using the X-MODEM polynomial 0x1021.
 *
 *  Parameters:
 *      ptr   - Pointer to input data buffer
 *      count - Number of bytes in the buffer
 *
 *  Returns:
 *      The computed 16-bit CRC value.
 */
unsigned crc16(const unsigned char[], unsigned nrbytes);

/**
 *  crc16_c - Compute CRC-16 checksum (X-MODEM standard)
 *
 *  This function calculates a 16-bit CRC (Cyclic Redundancy Check)
 *  using the X-MODEM polynomial 0x1021.
 *
 *  Parameters:
 *      ptr   - Pointer to input data buffer
 *      count - Number of bytes in the buffer
 *
 *  Returns:
 *      The computed 16-bit CRC value.
 */
unsigned crc16_c(const unsigned char *ptr, int count) {
    int crc;
    char i;

    crc = 0;
    while(--count >= 0) {
	crc = crc ^ (int) *ptr++ << 8;
	i = 8;
	do {
	     if(crc & 0x8000) {
		 crc = crc << 1 ^ 0x1021;
	     } else {
		 crc = crc << 1;
	     }
	} while(--i);
    }

    return crc;
}

#endif