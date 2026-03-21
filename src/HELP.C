/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    HELP.C
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

#include <conio.h>

#include "helpers.h"
#include "help.h"

void help_show() {
    int c;

    store_screen();
    set_regular();
    window(1,1,80,25);
    clrscr();

    set_hl();
    gotoxy(1,1);
    cputs(" OTTERNAV HELP ");
    set_regular();

    gotoxy(1,3);
    cputs("OTTERNAV interfaces with a FAT32 formatted SD card in MSDOS using the Slototter");
    gotoxy(1,4);
    cputs("ISA card. More info is found here: https://github.com/ifilot/slot-otter");

    gotoxy(1,6);
    cputs("OTTERNAV uses two panels for facile navigation. The left panel reflects the");
    gotoxy(1,7);
    cputs("contents of the SD-CARD. The right panel your local hard drive. Using the TAB");
    gotoxy(1,8);
    cputs("key, one can swap between the two panels. To copy files over, select the file");
    gotoxy(1,9);
    cputs("or folder on the left hand side and navigate to the desired target folder on");
    gotoxy(1,10);
    cputs("the right hand side. Either create a new folder on your hard drive or directly");
    gotoxy(1,11);
    cputs("copy the files or folder over to the destination folder.");

    gotoxy(1,13);
    cputs("If you encounter any problems or issues while using OTTERNAV, please submit");
    gotoxy(1,14);
    cputs("a ticket via https://github.com/ifilot/slot-otter/issues.");

    gotoxy(1,16);
    cputs("OTTERNAV is free software: you can redistribute it and/or modify");
    gotoxy(1,17);
    cputs("it under the terms of the GNU General Public License as published by");
    gotoxy(1,18);
    cputs("the Free Software Foundation, either version 3 of the License, or");
    gotoxy(1,19);
    cputs("(at your option) any later version.");
    
    

    gotoxy(1,24);
    set_hl();
    cputs("Press ESC to return");

    while(1) {
        c = getch();
        if(c == 27) {
            break;
        }
    }

    restore_screen();
    window(1,1,80,25);
}
