/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    CFG.C
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

#ifndef _CFG_H
#define _CFG_H

#include <stdio.h>

/* OTTERNAV configuration is stored in this file; this file always resides
 * in the same directory as OTTERNAV.EXE */
#define CFG_FILENAME "OTTERNAV.INI"
#define CFG_DEFAULT_BASE_PORT 0x330

/*
 *  cfg_init - Load configuration or create defaults
 *
 *  Parameters:
 *      filename - Path to INI file
 */
void cfg_init(const char* filename);

/*
 *  cfg_save - Persist configuration to disk
 *
 *  Parameters:
 *      filename - Path to INI file
 */
void cfg_save(const char* filename);

/*
 *  cfg_get_base_port - Get current base I/O port
 */
unsigned cfg_get_base_port();

/*
 *  cfg_set_base_port - Set current base I/O port
 *
 *  Parameters:
 *      base_port - New base port address
 */
void cfg_set_base_port(unsigned base_port);

#endif
