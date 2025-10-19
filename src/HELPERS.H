/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    HELPERS.H
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

#ifndef __HELPERS_H
#define __HELPERS_H

#include <stdio.h>
#include <conio.h>
#include <stdlib.h>
#include <dir.h>
#include <dos.h>

#include "fatstruc.h"

#define BLACKONWHITE 112
#define WHITEONBLACK   7

/*
 *  print_block - Print nicely formatted block of 512 bytes to screen
 *
 *  Parameters:
 *      buf - Pointer to start of buffer
 */
void print_block(unsigned char buf[]);

/*
 *  print_line - Print 16 bytes of data to the screen
 *
 *  Parameters:
 *      ptr      - Pointer to start of buffer
 *      asciiptr - Pointer to ascii data
 *      addr     - Block address
 */
void print_line(unsigned char *ptr, unsigned char *asciiptr, unsigned addr);

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
void set_rect_attr(int left, int top, int right, int bottom, unsigned char attr);

/*
 *  set_regular - Set normal text colors
 */
void set_regular();

/*
 *  set_hl - Set highlight text colors
 */
void set_hl();

/*
 *  store_screen - Store whole screen in buffer
 */
void store_screen();

/*
 *  restore_screen - Restore whole screen in buffer
 */
void restore_screen();

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
void draw_textbox(int left, int top, int right, int bottom, const char* title);

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
int folder_exists(const char* path);

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
int file_exists(const char* path);

/*
 *  disable_cursor - Hide the text cursor
 *
 *  Uses BIOS interrupt 10h, function 01h to disable
 *  the blinking text cursor on the screen.
 */
void disable_cursor();

/*
 *  enable_cursor - Show the text cursor
 *
 *  Uses BIOS interrupt 10h, function 01h to restore
 *  the normal blinking text cursor.
 */
void enable_cursor();

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
void build_dos_filename(const struct FAT32File* f, char* path);

#endif