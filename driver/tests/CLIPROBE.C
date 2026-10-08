/* Actual DOS EXEC, command-tail/environment ABI, exit status/vector regression. */
#include <dos.h>
#include <stdio.h>
#include <string.h>
extern unsigned _psp;
static unsigned failures, envseg;
static unsigned char tail[129];
static struct {
    unsigned environment;
    unsigned char far *command;
    void far *fcb1, far *fcb2;
} block;
static void check(int ok, char *what) {
    printf("%s: %s\n",ok?"PASS":"FAIL",what); fflush(stdout);
    if(!ok) ++failures;
}
static unsigned long free_memory(void) {
    union REGS r; struct SREGS s;
    unsigned mcb, i, size;
    unsigned char far *p;
    unsigned long total=0;
    r.h.ah=0x52; int86x(0x21,&r,&r,&s);
    mcb=*(unsigned far *)MK_FP(s.es,r.x.bx-2);
    for(i=0;i<1000;++i) {
        p=(unsigned char far *)MK_FP(mcb,0);
        if(p[0]!='M' && p[0]!='Z') break;
        size=*(unsigned far *)(p+3);
        if(!*(unsigned far *)(p+1)) total+=size+1;
        if(p[0]=='Z') break;
        mcb+=size+1;
    }
    return total;
}
static void run(char *command, unsigned status, unsigned resident) {
    union REGS r; struct SREGS s;
    void interrupt far (*vectors[4])(void);
    unsigned ints[4]={0,4,5,6}, i, length=strlen(command), kind, code;
    unsigned long before;
    static char program[]="OTTERSD.EXE";
    if(length>127) { check(0,"test command fits DOS command tail"); return; }
    for(i=0;i<4;++i) vectors[i]=getvect(ints[i]);
    before=free_memory();
    tail[0]=length; memcpy(tail+1,command,length); tail[length+1]=13;
    block.environment=envseg; block.command=tail;
    block.fcb1=MK_FP(_psp,0x5c); block.fcb2=MK_FP(_psp,0x6c);
    segread(&s); s.es=s.ds;
    r.x.ax=0x4b00; r.x.dx=(unsigned)program; r.x.bx=(unsigned)&block;
    int86x(0x21,&r,&r,&s);
    check(!r.x.cflag,"EXEC child with 10 KiB inherited environment");
    if(r.x.cflag) return;
    r.x.ax=0x4d00; int86(0x21,&r,&r); code=r.h.al; kind=r.h.ah;
    printf("Child '%s': type %u code %u\n",command,kind,code);
    check(code==status && kind==(resident?3:0),"child exit type and ERRORLEVEL");
    for(i=0;i<4;++i) check(getvect(ints[i])==vectors[i],"child restores CRT interrupt vector");
    if(!resident) check(free_memory()==before,"ordinary child releases all DOS allocations");
}
int main(void) {
    union REGS r; struct SREGS s;
    unsigned i, j, offset=0;
    unsigned char far *env;
    char padded[128];
    r.h.ah=0x48; r.x.bx=1024; int86(0x21,&r,&r);
    check(!r.x.cflag,"allocate custom 16 KiB environment block");
    if(r.x.cflag) return 1;
    envseg=r.x.ax; env=(unsigned char far *)MK_FP(envseg,0);
    for(i=0;i<100;++i) {
        env[offset++]='P'; env[offset++]='A'; env[offset++]='D';
        env[offset++]='0'+i/10; env[offset++]='0'+i%10; env[offset++]='=';
        for(j=0;j<100;++j) env[offset++]='X';
        env[offset++]=0;
    }
    env[offset++]=0; env[offset++]=1; env[offset++]=0;
    for(i=0;i<sizeof("A:\\OTTERSD.EXE");++i) env[offset++]=("A:\\OTTERSD.EXE")[i];
    run("",1,0); run("/status",1,0); run("/unknown",1,0);
    run("/drive:s /port:10000",1,0); run("/drive:s /port:333",1,0);
    run("/drive:s /port:-fffffd00",1,0); run("/mount /drive:s",1,0);
#ifdef UNIFIED_DRIVER
    run("/drive:s /fat16 /fat32",1,0); run("/drive:s /fat16 /fat16",1,0);
    run("/status /fat16",1,0); run("/mount /fat32",1,0);
    run("/unload /fat16",1,0);
    run("/drive:s /skipfatcheck",1,0); run("/drive:s /ro /skipfatcheck",1,0);
    run("/drive:s /rw /skipfatcheck /skipfatcheck",1,0);
    run("/status /skipfatcheck",1,0); run("/mount /skipfatcheck",1,0);
    run("/unload /skipfatcheck",1,0);
    run("/drive:s /ro /rw",1,0); run("/status /ro",1,0);
    run("/drive:s /noverify",1,0); run("/drive:s /ro /noverify",1,0);
    run("/drive:s /rw /noverify /noverify",1,0); run("/status /noverify",1,0);
    run("/drive:s /rw /rw",1,0); run("/drive:s /ro /ro",1,0);
    run("\t\"/drive:s\"\t\"/port:+0x330\" /ro",0,1);
#else
    run("\t\"/drive:s\"\t\"/port:+0x330\"",0,1);
#endif
    run("/drive:s /port:0000330",1,0);
    run("\t\"/status\"",0,0);
    memset(padded,' ',127); memcpy(padded,"/status",7); padded[127]=0;
    run(padded,0,0);
    /* Mount may fail with an empty socket; unmount must always succeed here. */
    run("/unmount",0,0);
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; int86(0x2f,&r,&r);
    if(r.x.dx) check(0,"unmount leaves drive offline");
    r.h.ah=0x49; segread(&s); s.es=envseg; int86x(0x21,&r,&r,&s);
    check(!r.x.cflag,"release custom environment block");
    printf("CLI RESULT: %u failures\n",failures);
    return failures?1:0;
}
