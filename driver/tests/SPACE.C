/* Genuine DOS capacity probe. Turbo C 2.0, small model, 8086.
 * Test-only executable: never shipped as a second public hardware utility.
 * The Python harness compares these results to the independent on-disk FAT.
 */
#include <dos.h>
#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <io.h>
static unsigned char data[5000];
static int space(const char *phase) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0x3600; r.x.dx=19;
    int86(0x21,&r,&r);
    printf("SPACE %s: sectors=%u bytes=%u total=%u free=%u\n",
           phase,r.x.ax,r.x.cx,r.x.dx,r.x.bx);
    return r.x.ax!=0xffff && r.x.ax && r.x.cx==512 && r.x.bx<=r.x.dx;
}
int main(int argc,char **argv) {
    int h,ro=argc==2 && !strcmp(argv[1],"/RO");
    unsigned i;
    if(!space("before")) return 1;
    if(ro) {
        h=open("S:\\SPACE.BIN",O_CREAT|O_TRUNC|O_BINARY|O_RDWR,0);
        if(h>=0) { close(h); puts("FAIL: read-only create succeeded"); return 1; }
    } else {
        for(i=0;i<sizeof(data);++i) data[i]=(unsigned char)(i*7+3);
        h=open("S:\\SPACE.BIN",O_CREAT|O_TRUNC|O_BINARY|O_RDWR,0);
        if(h<0) { puts("FAIL: create"); return 1; }
        if(write(h,data,sizeof(data))!=sizeof(data)) { close(h); puts("FAIL: write"); return 1; }
        if(close(h)) { puts("FAIL: close"); return 1; }
    }
    if(!space("after")) return 1;
    puts("SPACE PASS"); return 0;
}
