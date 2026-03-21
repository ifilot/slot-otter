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
    cputs("This is a placeholder help screen.");
    gotoxy(1,5);
    cputs("Suggested sections:");
    gotoxy(3,6);
    cputs("- Keyboard shortcuts");
    gotoxy(3,7);
    cputs("- SD-card requirements");
    gotoxy(3,8);
    cputs("- Error handling");
    gotoxy(3,9);
    cputs("- Troubleshooting and FAQ");
    gotoxy(3,10);
    cputs("- Version and credits");

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
