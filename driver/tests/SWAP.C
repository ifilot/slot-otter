/* Real DOS swap tests; requires OTTER_MODEL_TEST adapter's host port 334. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <dir.h>
#include <io.h>
#include <fcntl.h>

static unsigned failures;
static void check(int ok, char *what) {
    printf("%s: %s\n",ok?"PASS":"FAIL",what); fflush(stdout);
    if (!ok) ++failures;
}
static int log_contains(char *name, char *text) {
    FILE *f=fopen(name,"rt");
    char line[180];
    int found=0;
    if (!f) return 0;
    while(fgets(line,sizeof(line),f)) if(strstr(line,text)) found=1;
    fclose(f); return found;
}
static unsigned control(unsigned command) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
    r.x.dx=0x524f; r.x.si=command; int86(0x2f,&r,&r);
    return r.x.cflag?r.x.ax:0;
}
static unsigned online(void) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; int86(0x2f,&r,&r);
    return r.x.dx;
}
static int byte_at_start(int h) {
    unsigned char b;
    if (lseek(h,0L,SEEK_SET)!=0 || read(h,&b,1)!=1) return -1;
    return b;
}
static void missing_read(int h, char *what) {
    union REGS r;
    unsigned char b=0x99;
    memset(&r,0,sizeof(r)); r.h.ah=0x3f; r.x.bx=h;
    r.x.cx=1; r.x.dx=(unsigned)&b; int86(0x21,&r,&r);
    /* DOS may translate a redirector not-ready error into access denied. */
    check(r.x.cflag && (r.x.ax==21 || r.x.ax==5) && b==0x99,what);
}
int main(void) {
    int h;
    struct ffblk search;
    char cwd[80];
    check(!online(),"resident installation with empty slot");
    check(control(2)==21 && !online(),"mount empty slot returns not ready");
    system("otterfs /mount > empty.txt");
    check(log_contains("empty.txt","DOS error 21"),"CLI mount empty slot fails");
    outportb(0x334,1);
    check(system("otterfs /mount > mount.txt")==0 && online(),"CLI mount inserted card");
    h=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    check(h>=0 && byte_at_start(h)=='H',"read first card");
    check(control(1)==5 && control(2)==5,"open handles block unmount and remount");
    system("otterfs /unmount > busy.txt");
    check(log_contains("busy.txt","Close all files"),"CLI refuses unmount with open file");
    if (h>=0) close(h);
    check(findfirst("S:\\*.TXT",&search,0)==0,"start search before unmount");
    check(chdir("S:\\SUBDIR")==0,"set current directory before unmount");
    check(system("otterfs /unmount > unmount.txt")==0 && !online(),"CLI unmount");
    check(control(1)==0,"unmount is idempotent");
    check(getcurdir(19,cwd)==0 && !cwd[0],"unmount resets drive current directory");
    outportb(0x334,2);
    check(control(2)==0 && online(),"mount replacement with different cluster size");
    check(findnext(&search)!=0,"reject search belonging to previous mount");
    h=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    check(h>=0 && byte_at_start(h)=='Z',"replacement uses fresh geometry and sector cache");
    outportb(0x334,0);
    if(h>=0) missing_read(h,"removal rejects cached sector read");
    check(!online(),"removal leaves driver offline");
    outportb(0x334,1);
    check(control(2)==5,"removed card handles must still be closed");
    if(h>=0) check(close(h)==0,"close stale file while offline");
    check(control(2)==0,"explicit mount after closing stale handle");
    h=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    check(h>=0 && byte_at_start(h)=='H',"cache original card again");
    outportb(0x334,3);
    if(h>=0) missing_read(h,"CID detects already initialized replacement before cached read");
    check(!online(),"replacement never mounts automatically");
    if(h>=0) close(h);
    check(control(2)==0,"mount already initialized replacement explicitly");
    h=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    check(h>=0 && byte_at_start(h)=='Z',"read new card after CID mismatch");
    if(h>=0) close(h);
    outportb(0x334,0);
    check(!online(),"status query detects removal without an open file");
    check(control(1)==0,"unmount second card");
    outportb(0x334,1); check(control(2)==0,"restore first card for filesystem probe");
    printf("SWAP RESULT: %u failures\n",failures);
    return failures?1:0;
}
