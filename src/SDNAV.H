/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    SDNAV.H
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

#ifndef _SDNAV_H
#define _SDNAV_H

#include <conio.h>
#include "fat32.h"
#include "helpers.h"
#include "version.h"

/*
 * sdnav_init - Initialize SD navigator
 */
void sdnav_init();

/*
 *  sdnav_display_commands - Display commands on bottom of screen
 */
void sdnav_display_commands();

/*
 *  sdnav_print_volume_label - Print volume label
 *
 *  Parameters:
 *      lbl - Label string
 */
void sdnav_print_volume_label(const char* lbl);

/*
 * sdnav_print_files - Print files on SD card to screen
 */
void sdnav_print_files();

/*
 * sdnav_remove_cursor - Remove cursor from SD navigator
 */
void sdnav_remove_cursor();

/*
 * sdnav_set_cursor - Set cursor for SD navigator
 */
void sdnav_set_cursor();

/*
 * sdnav_reset_cursor - Reset cursor for SD navigator
 */
void sdnav_reset_cursor();

/*
 * sdnav_get_cursor_pos - Get current cursor position
 *
 *  Returns:
 *      Current cursor position (file id)
 */
int sdnav_get_cursor_pos();

/*
 *  sdnav_move_cursor - Move cursor on the screen
 *
 *  Parameters:
 *      d - Movement increment
 */
void sdnav_move_cursor(int d);

/*
 *  sdnav_scroll_down - Scroll file menu one page down
 */
void sdnav_scroll_down();

/*
 *  sdnav_scroll_up - Scroll file menu one page up
 */
void sdnav_scroll_up();

/*
 * sdnav_print_entry - Print file entry to the screen
 *
 * Parameters:
 *      pos - Position where to print
 *      id  - Which file entry to print
 */
void sdnav_print_entry(unsigned char pos, unsigned int id);

#endif