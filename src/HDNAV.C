/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    HDNAV.C
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

#include "hdnav.h"

static unsigned int hdnav_nrfiles;
static struct HDNavFile hdnav_files[HDNAV_MAX_FILES];
static int cursor_pos;
static int start_pos;

/*
 *  hdnav_init - Initialize the navigator menu
 */
void hdnav_init() {
    hdnav_read_files();
    hdnav_print_files();
}

/*
 *  hdnav_display_commands - Display commands on bottom of screen
 */
void hdnav_display_commands() {
    gotoxy(1,25);
    set_hl();
    clreol();
    cputs("F1: HELP | F2: MKDIR | F10: EXIT");
    set_regular();
}

/*
 *  hdnav_change_folder - Change folder in HD navigator
 *
 *  Parameters:
 *      f - Pointer to HDNavFile on drive
 */
void hdnav_change_folder(const struct HDNavFile* f) {
    if(f->attrib & HDNAV_MASK_DIR) {
        chdir(f->filename);
    }
}

/*
 *  hdnav_get_file_entry - Get file entry in folder identified by id
 *
 *  Parameters:
 *      id - File id
 */
const struct HDNavFile* hdnav_get_file_entry(unsigned id) {
    if(id < hdnav_nrfiles) {
        return &hdnav_files[id];
    }
}

/*
 *  hdnav_read_files - Read all files in current folder
 */
void hdnav_read_files() {
    struct ffblk file;
    int done;
    unsigned int ctr = 0;

    done = findfirst("*.*", &file, FA_NORMAL | FA_DIREC);

    while(!done && ctr < HDNAV_MAX_FILES) {
        memcpy(hdnav_files[ctr].filename, file.ff_name, 13);
        hdnav_files[ctr].attrib = file.ff_attrib;
        hdnav_files[ctr].filesize = file.ff_fsize;
        done = findnext(&file);
        ctr++;
    }

    hdnav_nrfiles = ctr;
    hdnav_sort_files();
}

/*
 *  hdnav_read_files - Sort all files in current folder
 */
void hdnav_sort_files() {
    qsort(hdnav_files, hdnav_nrfiles, sizeof(struct HDNavFile), hdnav_file_compare);
}

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
int hdnav_file_compare(void* f1, void* f2) {
    const struct HDNavFile* file1 = (const struct HDNavFile*)f1;
    const struct HDNavFile* file2 = (const struct HDNavFile*)f2;

    unsigned char is_dir1 = (file1->attrib & HDNAV_MASK_DIR) != 0;
    unsigned char is_dir2 = (file2->attrib & HDNAV_MASK_DIR) != 0;

    if(is_dir1 && !is_dir2) {
        return -1;
    } else if(!is_dir1 && is_dir2) {
        return 1;
    }

    return strcmp(file1->filename, file2->filename);
}

/*
 * hdnav_print_files - Print (part of) current active folder to screen
 */
void hdnav_print_files() {
    unsigned int i,ctr;
    window(41,2,80,23);
    clrscr();

    ctr = 0;
    for(i=start_pos; i<hdnav_nrfiles; ++i) {
	hdnav_print_entry(++ctr, i);

	/* print at most 22 entries */
	if(ctr >= 22) {
	    break;
	}
    }

    window(1,1,80,25);
}

/*
 * hdnav_set_cursor - Set current cursor position
 */
void hdnav_set_cursor() {
    gotoxy(41, cursor_pos+2);
    putch('>');
    set_rect_attr(41,cursor_pos+2,80,cursor_pos+2,
		  display_mode == 0x03 ? BLACKONWHITE : WHITEONGREEN);
}

/*
 * hdnav_reset_cursor - Reset current cursor position
 */
void hdnav_reset_cursor() {
    cursor_pos = 0;
    start_pos = 0;
    hdnav_set_cursor();
}

/*
 * hdnav_get_cursor - Get current cursor position
 *
 *  Returns:
 *      Current cursor position (file id)
 */
int hdnav_get_cursor_pos() {
    return start_pos + cursor_pos;
}

/*
 * hdnav_remove_cursor - Remove the cursor
 */
void hdnav_remove_cursor() {
    gotoxy(41,cursor_pos+2);
    putch(' ');
    set_rect_attr(41,cursor_pos+2,80,cursor_pos+2,WHITEONBLACK);
}

/*
 *  hdnav_move_cursor - Move cursor on the screen
 *
 *  Parameters:
 *      d - Movement increment
 */
void hdnav_move_cursor(int d) {
    int old_start_pos = start_pos;

    /* remove old cursor */
    hdnav_remove_cursor();

    /* set new cursor position */
    cursor_pos += d;

    if((cursor_pos + start_pos) >= (int)hdnav_nrfiles) {
        if(hdnav_nrfiles <= 22) {
            cursor_pos = hdnav_nrfiles - 1;
            start_pos = 0;
        } else {
            cursor_pos = 21;
            start_pos = hdnav_nrfiles - 22;
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
            hdnav_scroll_up();
        break;
        case 1:
            hdnav_scroll_down();
        break;
        default:
            hdnav_print_files();
        break;
    }

    hdnav_set_cursor();
}

/*
 *  hdnav_scroll_down - Scroll file menu one page down
 */
void hdnav_scroll_down() {
    window(41,2,80,23);
    gotoxy(1,1);
    delline();
    hdnav_print_entry(22, start_pos + 21);
    window(1,1,80,25);
}

/*
 *  hdnav_scroll_down - Scroll file menu one page up
 */
void hdnav_scroll_up() {
    window(41,2,80,23);
    gotoxy(1,1);
    insline();
    hdnav_print_entry(0, start_pos);
    window(1,1,80,25);
}

/*
 * hdnav_print_entry - Print file entry to the screen
 *
 * Parameters:
 *      pos - Position where to print
 *      id  - Which file entry to print
 */
void hdnav_print_entry(unsigned char pos, unsigned int id) {
    const struct HDNavFile *f = &hdnav_files[id];

    gotoxy(1,pos); /* function assumes to be in NAV window !!*/

    if(f->attrib & HDNAV_MASK_DIR) { /* check if folder */
        cprintf("  %-25s [DIR]", f->filename);
    } else {
        cprintf("  %-22s %8lu", f->filename, f->filesize);
    }
}

/*
 * hdnav_create_folder - Create folder
 *
 * Ask the user to type in a folder name and create that folder
 */
void hdnav_create_folder() {
    char c = 0;
    unsigned ctr = 0;
    char dbuf[9] = {0};

    store_screen();

    /* print window */
    draw_textbox(30,14,50,15,"Enter folder name:");
    gotoxy(1,2);

    /* put in writing mode */
    while(c != 0x0D) {
        c = getch();
        gotoxy(1+ctr, 2);
        if(ctr < 8) {
            if((c>='0' & c<='9') || (c>='A' && c<='Z') || (c>='a' && c<='z')) {
            dbuf[ctr++] = c;
            putch(c);
            }
        }
        if(ctr > 0 && c == 8) {
            gotoxy(ctr, 2);
            putch(' ');
            dbuf[--ctr] = 0;
            gotoxy(1+ctr, 2);
        }
        if(c == 0x1B) {
            break;
        }
    }

    if(c == 0x0D) {
        mkdir(dbuf);
    }

    window(1,1,80,25);
    restore_screen();
    hdnav_read_files();
    hdnav_print_files();
    hdnav_reset_cursor();
}