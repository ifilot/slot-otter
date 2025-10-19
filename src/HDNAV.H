/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    HDNAV.H
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

#ifndef _HDNAV_H
#define _HDNAV_H

#include <stdio.h>
#include <dir.h>
#include <string.h>
#include "helpers.h"

#define HDNAV_MAX_FILES 256

#define FA_NORMAL 	0x00
#define FA_DIREC  	0x10
#define HDNAV_MASK_DIR 	0x10

struct HDNavFile {
    char filename[13];
    unsigned char attrib;
    unsigned long filesize;
};

extern struct HDNavFile hdnav_files[HDNAV_MAX_FILES];
extern unsigned int hdnav_nrfiles;

/*
 *  hdnav_init - Initialize the navigator menu
 */
void hdnav_init();

/*
 *  hdnav_display_commands - Display commands on bottom of screen
 */
void hdnav_display_commands();

/*
 *  hdnav_change_folder - Change folder in HD navigator
 *
 *  Parameters:
 *      f - Pointer to HDNavFile on drive
 */
void hdnav_change_folder(const struct HDNavFile* f);

/*
 *  hdnav_get_file_entry - Get file entry in folder identified by id
 *
 *  Parameters:
 *      id - File id
 */
const struct HDNavFile* hdnav_get_file_entry();

/*
 *  hdnav_read_files - Read all files in current folder
 */
void hdnav_read_files();

/*
 *  hdnav_read_files - Sort all files in current folder
 */
void hdnav_sort_files();

/*
 *  hdnav_file_compare - Compare two files
 *
 *  Parameters:
 *      f1 - Pointer to HDNavFile file1
 *      f2 - Pointer to HDNavFile file2
 *
 *  Returns:
 *      -1 if file1 < file2
 *      +1 if file1 > file2
 */
int hdnav_file_compare(void* f1, void* f2);

/*
 * hdnav_print_files - Print (part of) current active folder to screen
 */
void hdnav_print_files();

/*
 * hdnav_set_cursor - Set current cursor position
 */
void hdnav_set_cursor();

/*
 * hdnav_reset_cursor - Reset current cursor position
 */
void hdnav_reset_cursor();

/*
 * hdnav_get_cursor - Get current cursor position
 *
 *  Returns:
 *      Current cursor position (file id)
 */
int hdnav_get_cursor_pos();

/*
 * hdnav_remove_cursor - Remove the cursor
 */
void hdnav_remove_cursor();

/*
 *  hdnav_move_cursor - Move cursor on the screen
 *
 *  Parameters:
 *      d - Movement increment
 */
void hdnav_move_cursor(int d);

/*
 *  hdnav_scroll_down - Scroll file menu one page down
 */
void hdnav_scroll_down();

/*
 *  hdnav_scroll_down - Scroll file menu one page up
 */
void hdnav_scroll_up();

/*
 * hdnav_print_entry - Print file entry to the screen
 *
 * Parameters:
 *      pos - Position where to print
 *      id  - Which file entry to print
 */
void hdnav_print_entry(unsigned char pos, unsigned int id);

/*
 * hdnav_create_folder - Create folder
 *
 * Ask the user to type in a folder name and create that folder
 */
void hdnav_create_folder();

#endif