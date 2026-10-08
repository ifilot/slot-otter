/* Private genuine-DOS XCOPY timing probe. Not part of the hardware kit.
 * No SD port access: the child uses DOS file APIs through the resident driver.
 * Capture before unmount so its complete FAT audit is timed separately. */
#include "RWSD.H"
#include <dos.h>
#include <process.h>
#include <stdio.h>
#include <string.h>
static U32 ticks(void) {
    volatile U16 far *p=(volatile U16 far *)MK_FP(0x40,0x6c);
    U16 lo,hi;
    do { hi=p[1]; lo=p[0]; } while (hi!=p[1]);
    return ((U32)hi<<16)|lo;
}
static int query(U16 number,void *out,U16 size) {
    union REGS r; struct SREGS s;
    memset(&r,0,sizeof(r)); segread(&s); s.es=s.ds;
    r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f; r.x.si=number;
    r.x.cx=size; r.x.di=(U16)out; int86x(0x2f,&r,&r,&s);
    return r.x.cflag || r.x.cx!=size;
}
int main(int argc,char **argv) {
    SdDiagnostic before,after;
    DriverInfo info;
    U32 start,end,elapsed;
    int code;
    if (argc<3 || query(8,&info,sizeof(info)) ||
        query(4,&before,sizeof(before))) {
        puts("XCOPY PROBE FAIL: arguments or resident query unavailable"); return 2;
    }
    printf("XCOPY START: driver=%u flags=%u resident=%u readback=%s\n",
        info.version,info.flags,info.resident,(info.flags&8)?"OFF":"ON");
    fflush(stdout); argv[0]="XCOPY"; start=ticks();
    code=spawnv(P_WAIT,"A:\\XCOPY.EXE",argv); end=ticks();
    elapsed=end>=start?end-start:1573040UL-start+end;
    if (query(4,&after,sizeof(after))) { puts("XCOPY PROBE FAIL: final query"); return 2; }
    printf("XCOPY RESULT: exit=%d ticks=%lu completed=%lu transmissions=%lu retries=%lu error=%u poison=%u\n",
        code,elapsed,after.verified-before.verified,after.transmissions-before.transmissions,
        after.retries-before.retries,after.error,after.poisoned);
    return code>=0 && code<=255?code:2;
}
