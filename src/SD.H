/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    SD.H
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

#ifndef _SD_H
#define _SD_H

#define MAXTRIAL 100

#include <dos.h>
#include "sdcmds.h"

/*
 * sd_boot - Boot SD card
 *
 * Returns:
 *      0 if success, otherwise on fail
 */
int sd_boot();

/*
 * Pulls the MISO line low
 *
 * Parameters:
 *      ioport - Which base IO address
 */
void sd_set_miso_low(unsigned ioport);

/*
 * Pulls the MISO line high
 *
 * Parameters:
 *      ioport - Which base IO address
 */
void sd_set_miso_high(unsigned ioport);

/*
 * Disables SD card (pulls /ENABLE HIGH)
 *
 * Parameters:
 *      ioport - Which base IO address
 */
void sd_disable(unsigned ioport);

#endif _SD_H