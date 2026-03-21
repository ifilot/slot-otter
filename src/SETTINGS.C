#include <conio.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#include "helpers.h"
#include "cfg.h"
#include "settings.h"

int settings_show() {
    char input[16];
    unsigned long value;
    char* endptr;
    int c;
    int idx = 0;

    store_screen();
    set_regular();
    window(1,1,80,25);
    clrscr();

    set_hl();
    gotoxy(1,1);
    cputs(" OTTERNAV SETTINGS ");
    set_regular();

    gotoxy(1,3);
    cprintf("Current BASE_PORT: 0x%X", cfg_get_base_port());
    gotoxy(1,5);
    cputs("Enter new BASE_PORT (hex, e.g. 0x330). Press ESC to cancel.");
    gotoxy(1,7);
    cputs("BASE_PORT: ");

    memset(input, 0, sizeof(input));

    while(1) {
        gotoxy(12 + idx, 7);
        c = getch();

        if(c == 27) {
            restore_screen();
            window(1,1,80,25);
            return 0;
        }

        if(c == 13) {
            if(idx == 0) {
                continue;
            }
            input[idx] = '\0';
            if(!(idx > 2 && input[0] == '0' && (input[1] == 'x' || input[1] == 'X'))) {
                gotoxy(1,9);
                cputs("Please use hexadecimal format (0xNNN).         ");
                continue;
            }

            value = strtoul(input, &endptr, 16);
            if(*endptr != '\0') {
                gotoxy(1,9);
                cputs("Invalid hexadecimal value.                       ");
                continue;
            }

            cfg_set_base_port((unsigned)value);
            cfg_save(CFG_FILENAME);
            restore_screen();
            window(1,1,80,25);
            return 1;
        }

        if(c == 8) {
            if(idx > 0) {
                idx--;
                gotoxy(12 + idx, 7);
                putch(' ');
                gotoxy(12 + idx, 7);
            }
            continue;
        }

        if(idx < (int)(sizeof(input) - 1)) {
            if((c >= '0' && c <= '9') ||
               (c >= 'a' && c <= 'f') ||
               (c >= 'A' && c <= 'F') ||
               c == 'x' || c == 'X') {
                input[idx++] = (char)c;
                putch(c);
            }
        }
    }
}
