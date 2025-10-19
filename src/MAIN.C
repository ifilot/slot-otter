/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    MAIN.C
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

#include <stdio.h>
#include <dos.h>

#include "sd.h"
#include "fat32.h"
#include "helpers.h"
#include "hdnav.h"
#include "sdnav.h"

#define STATE_MAIN_MENU 0
#define STATE_SD        1
#define STATE_HDNAV     2
#define STATE_EXIT      -1
#define CWDBUFLEN	256

int state_main_menu();
int state_sd();
int state_hdnav();
void init_fat();
int boot_sd_card();

static char cwd[CWDBUFLEN];

int main() {
    const struct FAT32File* f;
    int c;
    int ret;
    int state = STATE_SD;

    /* try to boot the sd card */
    if(boot_sd_card() != 0) {
    sddis(BASEPORT);
    return -1;
    }

    /* store current working directory */
    getcwd(cwd, CWDBUFLEN);

    /* initialize view */
    sdnav_init();
    disable_cursor();

    /* initialize navigation */
    hdnav_init();

    /* initialize SD card */
    init_fat();

    while(state != STATE_EXIT) {
        switch(state) {
            case STATE_MAIN_MENU:
                state = state_main_menu();
            break;
            case STATE_SD:
                state = state_sd();
            break;
            case STATE_HDNAV:
                state = state_hdnav();
            break;
            default:
                state = state_main_menu();
            break;
        }
    }

    /* disable SD card */
    sddis(BASEPORT);

    /* close view */
    window(1,1,80,25);
    textbackground(BLACK);
    textcolor(WHITE);
    clrscr();

    /* restore starting cwd */
    chdir(cwd);

    /* restore cursor */
    enable_cursor();

    return 0;
}

/*
 * main menu state of the program
 */
int state_main_menu() {
    int c;
    while(1) {
    c = getch();
    if(c == 0) { /* special key */
        c = getch();
        switch(c) {
        case 0x44:
            return STATE_EXIT;
        }
    }
    }
}

/*
 * user is in SD navigation panel
 */
int state_sd() {
    unsigned char c;
    int fpos;
    const struct FAT32File* f;
    char filename[13];

    while(1) {
    c = getch();
    if(c == 0) {
        c = getch();
        switch(c) {
        case 0x44:
            return STATE_EXIT;
        case 0x49:
            sdnav_move_cursor(-22);
        break;
        case 0x51:
            sdnav_move_cursor(22);
        break;
        }
    }
    switch(c) {
        case 0x09:
            sdnav_remove_cursor();
            hdnav_set_cursor();
            hdnav_display_commands();
            return STATE_HDNAV;
        case 0x3D:
            fpos = sdnav_get_cursor_pos();
            f = fat32_get_file_entry(fpos);
            if(memcmp(f->basename, ".       ", 8) == 0 ||
            memcmp(f->basename, "..      ", 8) == 0) {
                break;
            }
            if(f->attrib & MASK_DIR) {
                fat32_transfer_folder(f);
            } else {
                build_dos_filename(f, filename);
                fat32_transfer_file(f, filename);
            }
            hdnav_read_files();
            hdnav_print_files();
            hdnav_reset_cursor();
            hdnav_remove_cursor();
        break;
        case 0x50:
            sdnav_move_cursor(1);
        break;
        case 0x48:
            sdnav_move_cursor(-1);
        break;
        case 0x0D:
            fpos = sdnav_get_cursor_pos();
            f = fat32_get_file_entry(fpos);
            if(f->attrib & MASK_DIR) {
                fat32_set_current_folder(f);
                sdnav_print_files();
                sdnav_reset_cursor();
            }
        break;
    }
    }
}

/*
 * user is in HD navigation panel
 */
int state_hdnav() {
    unsigned char c;
    int fpos;
    const struct HDNavFile* f;

    while(1) {
        c = getch();
        if(c == 0) {
            c = getch();
            switch(c) {
            case 0x3C:
                hdnav_create_folder();
            break;
            case 0x44:
                return STATE_EXIT;
            case 0x49:
                hdnav_move_cursor(-22);
            break;
            case 0x51:
                hdnav_move_cursor(22);
            break;
            }
        }
        
        switch(c) {
            case 0x09:
                hdnav_remove_cursor();
                sdnav_set_cursor();
                sdnav_display_commands();
                return STATE_SD;
            case 0x50:
                hdnav_move_cursor(1);
            break;
            case 0x48:
                hdnav_move_cursor(-1);
            break;
            case 0x0D:
                fpos = hdnav_get_cursor_pos();
                f = hdnav_get_file_entry(fpos);
                if(f->attrib & HDNAV_MASK_DIR) {
                    hdnav_change_folder(f);
                    hdnav_read_files();
                    hdnav_print_files();
                    hdnav_reset_cursor();
                }
            break;
        }
    }
}

/*
 *  boot_sd_card - Try to open the SD card
 */
int boot_sd_card() {
    static unsigned char buf[514];
    int res = -1;
    unsigned attempts = 0;
    while(res != 0 && attempts < 10) {
    attempts++;
    printf("Trying to open SD card (%i)\n", attempts);
    res = sd_boot();
    if(res != 0) {
        printf("Cannot open SD-card, exiting...\n");
        continue;
    }
    res = cmd17(BASEPORT, 0x00000000, buf);
    if(res != 0) {
        printf("Cannot read boot sector.\n");
        continue;
    }
    if(buf[510] != 0x55 || buf[511] != 0xAA) {
        printf("Cannot read boot sector pattern.\n");
        res = -1;
        continue;
    }
    }
    return res;
}

/*
 *  init_fat - Try to initialize the FAT32 system
 */
void init_fat() {
    fat32_open_partition();
    sdnav_print_volume_label(fat32_partition.volume_label);
    fat32_read_current_folder();
    sdnav_print_files();
    sdnav_reset_cursor();
}