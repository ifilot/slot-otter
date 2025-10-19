/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    HELPERS.C
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

#include "helpers.h"

static char screenbuf[80*25*2];

/*
 *  print_block - Print nicely formatted block of 512 bytes to screen
 *
 *  Parameters:
 *      buf - Pointer to start of buffer
 */
void print_block(unsigned char buf[]) {
    int i,j;
    unsigned char *ptr = buf;
    unsigned char *asciiptr = buf;
    unsigned addr = 0;

    for(i=0; i<16; ++i) {
        print_line(ptr, asciiptr, addr);
        addr += 16;
        ptr += 16;
        asciiptr += 16;
    }
    
    printf("Press any key to continue to next 256 bytes.");
    getch();
    printf("\r");
    for(i=0; i<16; ++i) {
        print_line(ptr, asciiptr, addr);
        addr += 16;
        ptr += 16;
        asciiptr += 16;
    }
}

/*
 *  print_line - Print 16 bytes of data to the screen
 *
 *  Parameters:
 *      ptr      - Pointer to start of buffer
 *      asciiptr - Pointer to ascii data
 *      addr     - Block address
 */
void print_line(unsigned char *ptr, unsigned char *asciiptr, unsigned addr) {
    int j;
    unsigned char v;

    /* print address in hex format */
    printf("%04X | ", addr);

    /* print each byte in hex format */
    for(j=0; j<16; ++j) {
        printf("%02X ", *(ptr++));
    }

    /* show ASCII representation */
    printf(" | ");
    for(j=0; j<16; ++j) {
        v = *(asciiptr++);
        if(v >= 0x20 && v <= 0x7E) {
            putchar((char)v);
        } else {
            putchar('.');
        }
    }
    printf(" | \n");
}

/*
 *  set_rect_attr - Set text attributes for a rectangular area
 *
 *  Parameters:
 *      left, top     - Upper-left corner coordinates (1-based)
 *      right, bottom - Lower-right corner coordinates
 *      attr          - Text attribute byte (color/intensity)
 *
 *  Description:
 *      Reads a rectangular region of text from the screen using
 *      gettext(), modifies only the attribute byte for each cell,
 *      then writes the region back using puttext().
 *
 *      Each text cell is 2 bytes: character + attribute.
 *      The function allocates a temporary buffer, modifies
 *      attributes, and restores the block.
 */
void set_rect_attr(int left, int top, int right, int bottom, unsigned char attr) {
    unsigned width = right - left + 1;
    unsigned height = bottom - top + 1;
    unsigned cells = width * height;
    unsigned i;

    void *buf = malloc(cells * 2);
    if(!buf) {
        return;
    }

    if(gettext(left, top, right, bottom, buf)) {
        unsigned char* p = (unsigned char*)buf;
        for(i=0; i<cells; ++i) {
            p[2*i + 1] = attr;
        }
        puttext(left, top, right, bottom, buf);
    }
    free(buf);
}

/*
 *  set_regular - Set normal text colors
 */
void set_regular() {
    textbackground(BLACK);
    textcolor(LIGHTGRAY);
}

/*
 *  set_hl - Set highlight text colors
 */
void set_hl() {
    textbackground(WHITE);
    textcolor(BLACK);
}

/*
 *  store_screen - Store whole screen in buffer
 */
void store_screen() {
    gettext(1,1,80,25,screenbuf);
}

/*
 *  restore_screen - Restore whole screen in buffer
 */
void restore_screen() {
    puttext(1,1,80,25,screenbuf);
}

/*
 *  draw_textbox - Draw a simple text window with title
 *
 *  Parameters:
 *      left, top     - Upper-left corner of the box
 *      right, bottom - Lower-right corner of the box
 *      title         - Text to display at the top
 *
 *  Creates a text-mode window using window() and clrscr(),
 *  then prints the given title string at the top-left corner.
 */
void draw_textbox(int left, int top, int right, int bottom, const char *title) {
    window(left, top, right, bottom);
    clrscr();
    gotoxy(left, top);
    cprintf("%s", title);
}

/*
 *  folder_exists - Check if a directory exists
 *
 *  Parameters:
 *      path - Path to the folder to test
 *
 *  Returns:
 *      1 if the directory exists, otherwise 0.
 *
 *  Uses findfirst() from <dir.h> to check if a directory
 *  entry exists for the given path.
 */
int folder_exists(const char* path) {
    struct ffblk ff;
    if(findfirst(path, &ff, FA_DIREC) == 0) {
    return (ff.ff_attrib & FA_DIREC) != 0;
    }
    return 0;
}

/*
 *  file_exists - Check if a regular file exists
 *
 *  Parameters:
 *      path - Path to the file to test
 *
 *  Returns:
 *      1 if the file exists, otherwise 0.
 *
 *  Uses findfirst() from <dir.h> to check if the given
 *  path refers to a normal file (not a directory).
 */
int file_exists(const char* path) {
    struct ffblk ff;
    if(findfirst(path, &ff, FA_RDONLY | FA_HIDDEN | FA_SYSTEM | FA_ARCH) == 0) {
        return (ff.ff_attrib & FA_DIREC) == 0;
    }
    return 0;
}

/*
 *  disable_cursor - Hide the text cursor
 *
 *  Uses BIOS interrupt 10h, function 01h to disable
 *  the blinking text cursor on the screen.
 */
void disable_cursor() {
    union REGS r;
    r.h.ah = 1;
    r.h.ch = 0x20;
    r.h.cl = 0x20;
    int86(0x10, &r, &r);
}

/*
 *  enable_cursor - Show the text cursor
 *
 *  Uses BIOS interrupt 10h, function 01h to restore
 *  the normal blinking text cursor.
 */
void enable_cursor() {
    union REGS r;
    r.h.ah = 1;
    r.h.ch = 6;
    r.h.cl = 7;
    int86(0x10, &r, &r);
}

/*
 *  build_dos_filename - Build DOS 8.3 filename from FAT32 entry
 *
 *  Parameters:
 *      f    - Pointer to FAT32File structure
 *      path - Output buffer (at least 13 bytes)
 *
 *  Converts a FAT32 file entry name and extension into
 *  a standard DOS 8.3 filename format.  Removes padding
 *  spaces and adds a period if an extension is present.
 *
 *  Example:
 *      basename = "CONFIG  ", extension = "SYS"
 *      Result: "CONFIG.SYS"
 */
void build_dos_filename(const struct FAT32File* f, char *path) {
    char base[9];
    char ext[4];
    char* ptr;

    memset(path, 0, 13);
    memcpy(base, f->basename, 8);
        base[8] = 0;
    ptr = (char*)strchr(base, ' ');
    *ptr = 0;
    
    strcat(path, base);
    memcpy(ext, f->extension, 3);
    ext[3] = 0;
    
    ptr = (char*)strchr(ext, ' ');
    *ptr = 0;

    if(ptr != ext) {
        strcat(path, ".");
    }
    strcat(path, ext);
}