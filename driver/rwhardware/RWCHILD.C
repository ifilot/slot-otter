/* Test DOS's process-exit close callbacks, not C library handle cleanup.
 * All opens use INT 21h directly and deliberately remain open at exit.
 * Turbo C 2.0 / 8086. GPL-3.0-or-later. */
#include <dos.h>
#include <string.h>
int main(void) {
    union REGS r;
    unsigned i,first=0;
    static char name[]="S:\\RWTEMP\\DATA.BIN";
    for(i=0;i<6;++i) {
        memset(&r,0,sizeof(r)); r.x.ax=0x3d42; r.x.dx=(unsigned)name;
        int86(0x21,&r,&r); if(r.x.cflag) return 1;
        if(!i) first=r.x.ax;
    }
    memset(&r,0,sizeof(r)); r.x.ax=0x5c00; r.x.bx=first;
    r.x.di=1; int86(0x21,&r,&r);
    if(r.x.cflag) return 2;
    /* DOS must close all six SFTs and release the region lock on termination. */
    return 0;
}
