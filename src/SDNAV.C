
/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    SDNAV.C
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

#include "sdnav.h"

static int cursor_pos;
static int start_pos;

/*
 * sdnav_init - Initialize SD navigator
 */
void sdnav_init() {
    set_regular();
    window(1,1,80,25);
    clrscr(); /* clear complete screen */

    gotoxy(1,1);
    set_hl();
    clreol();
    cprintf("SD-CARD EXPLORER v%i.%i.%i", VERSION_MAJOR, VERSION_MINOR, VERSION_PATH);

    sdnav_display_commands();
}

/*
 *  sdnav_display_commands - Display commands on bottom of screen
 */
void sdnav_display_commands() {
    gotoxy(1,25);
    set_hl();
    clreol();
    cputs("F1: HELP | F3: COPY | F10: EXIT");
    set_regular();
}

/*
 *  sdnav_print_volume_label - Print volume label
 *
 *  Parameters:
 *      lbl - Label string
 */
void sdnav_print_volume_label(const char* lbl) {
    set_hl();
    window(1,1,80,25);
    gotoxy(60,25);
    cprintf("SDCARD: %.11s", lbl);
    set_regular();
}

/*
 * sdnav_print_files - Print files on SD card to screen
 */
void sdnav_print_files() {
    unsigned int i,ctr;
    window(1,2,40,23);
    clrscr();

    ctr = 0;
    for(i=start_pos; i<fat32_nrfiles; ++i) {
        sdnav_print_entry(++ctr, i);

        /* print at most 22 entries */
        if(ctr >= 22) {
            break;
        }
    }

    window(1,1,80,25);
}

/*
 * sdnav_set_cursor - Set cursor for SD navigator
 */
void sdnav_set_cursor() {
    gotoxy(1, cursor_pos+2);
    putch('>');
    set_rect_attr(1,cursor_pos+2,40,cursor_pos+2,
		  display_mode == 0x03 ? BLACKONWHITE : WHITEONGREEN);
}

/*
 * sdnav_reset_cursor - Reset cursor for SD navigator
 */
void sdnav_reset_cursor() {
    cursor_pos = 0;
    start_pos = 0;
    sdnav_set_cursor();
}

/*
 * sdnav_remove_cursor - Remove cursor from SD navigator
 */
void sdnav_remove_cursor() {
    gotoxy(1,cursor_pos+2);
    putch(' ');
    set_rect_attr(1,cursor_pos+2,40,cursor_pos+2,WHITEONBLACK);
}

/*
 * sdnav_get_cursor_pos - Get current cursor position
 *
 *  Returns:
 *      Current cursor position (file id)
 */
int sdnav_get_cursor_pos() {
    return start_pos + cursor_pos;
}

/*
 *  sdnav_move_cursor - Move cursor on the screen
 *
 *  Parameters:
 *      d - Movement increment
 */
void sdnav_move_cursor(int d) {
    int old_start_pos = start_pos;

    sdnav_remove_cursor();

    /* set new cursor position */
    cursor_pos += d;

    if((cursor_pos + start_pos) >= (int)fat32_nrfiles) {
        if(fat32_nrfiles <= 22) {
            cursor_pos = fat32_nrfiles - 1;
            start_pos = 0;
        } else {
            cursor_pos = 21;
            start_pos = fat32_nrfiles - 22;
        }
    } else if((cursor_pos + start_pos) < 0) {
        cursor_pos = 0;
        start_pos = 0;
    } else {
        if(cursor_pos > 21) {
            d = cursor_pos - 21;
            start_pos += d;
            cursor_pos -= d;
        } else if(cursor_pos < 0) {
            start_pos += cursor_pos;
            cursor_pos = 0;
        }
    }

    d = start_pos - old_start_pos;
    switch(d) {
    case 0:
        /* do nothing */
    break;
    case -1:
        sdnav_scroll_up();
    break;
    case 1:
        sdnav_scroll_down();
    break;
    default:
        sdnav_print_files();
    break;
    }

    sdnav_set_cursor();
}

/*
 *  sdnav_scroll_down - Scroll file menu one page down
 */
void sdnav_scroll_down() {
    window(1,2,40,23);
    gotoxy(1,1);
    delline();
    sdnav_print_entry(22, start_pos + 21);
    window(1,1,80,25);
}

/*
 *  sdnav_scroll_up - Scroll file menu one page up
 */
void sdnav_scroll_up() {
    window(1,2,40,23);
    gotoxy(1,1);
    insline();
    sdnav_print_entry(0, start_pos);
    window(1,1,80,25);
}

/*
 * sdnav_print_entry - Print file entry to the screen
 *
 * Parameters:
 *      pos - Position where to print
 *      id  - Which file entry to print
 */
void sdnav_print_entry(unsigned char pos, unsigned int id) {
    const struct FAT32File *entry = &fat32_files[id];
    gotoxy(1,pos);
    if(entry->attrib & MASK_DIR) {
    cprintf("  %-25s [DIR]", entry->basename);
    } else {
    cprintf("  %.8s.%.3s           %8lu", entry->basename, entry->extension, entry->filesize);
    }
}