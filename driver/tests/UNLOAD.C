/* Genuine DOS unload regression. Test-only; never ships as a resident driver.
 * EXEC a separate process so DOS itself proves vector/CDS restoration and
 * complete memory reclamation. All probes run on a private card image. */
#include <dos.h>
#include <stdio.h>
#include <string.h>
#include <io.h>
#include <fcntl.h>
extern unsigned _psp;
extern void far ulhook(void);
extern void hook_init(void interrupt far (*previous)(void));
unsigned _heaplen=4096, _stklen=2048;
static unsigned failures;
static unsigned char tail[129], saved[88], buffer[512];
static struct {
    unsigned environment;
    unsigned char far *command;
    void far *fcb1, far *fcb2;
} block;
static void check(int ok,char *what) {
    printf("%s: %s\n",ok?"PASS":"FAIL",what); fflush(stdout);
    if (!ok) ++failures;
}
static unsigned largest(void) {
    union REGS r;
    r.h.ah=0x48; r.x.bx=0xffff; int86(0x21,&r,&r);
    check(r.x.cflag,"oversize allocation only queries largest DOS block");
    return r.x.bx;
}
static unsigned long free_memory(void) {
    union REGS r; struct SREGS s;
    unsigned mcb,i,size;
    unsigned char far *p;
    unsigned long total=0;
    r.h.ah=0x52; int86x(0x21,&r,&r,&s);
    mcb=*(unsigned far *)MK_FP(s.es,r.x.bx-2);
    for (i=0;i<1000;++i) {
        p=(unsigned char far *)MK_FP(mcb,0);
        if (p[0]!='M' && p[0]!='Z') break;
        size=*(unsigned far *)(p+3);
        if (!*(unsigned far *)(p+1)) total+=size+1;
        if (p[0]=='Z') return total;
        mcb+=size+1;
    }
    check(0,"DOS memory chain remains valid"); return total;
}
static void run(char *command,unsigned status,unsigned resident) {
    union REGS r; struct SREGS s;
    unsigned n=strlen(command);
    static char program[]="A:\\OTTERSD.EXE";
    tail[0]=n; memcpy(tail+1,command,n); tail[n+1]=13;
    block.environment=0; block.command=tail;
    block.fcb1=MK_FP(_psp,0x5c); block.fcb2=MK_FP(_psp,0x6c);
    segread(&s); s.es=s.ds;
    r.x.ax=0x4b00; r.x.dx=(unsigned)program; r.x.bx=(unsigned)&block;
    int86x(0x21,&r,&r,&s);
    check(!r.x.cflag,"EXEC installer/control process");
    if (r.x.cflag) return;
    r.x.ax=0x4d00; int86(0x21,&r,&r);
    printf("COMMAND %s: exit=%u type=%u\n",command,r.h.al,r.h.ah);
    check(r.h.al==status && r.h.ah==(resident?3:0),"expected exit status and TSR type");
}
static int present(void) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; int86(0x2f,&r,&r);
    return r.x.ax==0x4f54 && r.x.bx==0x524f;
}
int main(int argc,char **argv) {
    union REGS r; struct SREGS s;
    unsigned char far *lol,far *cds;
    unsigned length,i,cycle,base_largest,held,psp,owner;
    unsigned char far *mcb;
    unsigned long base_free,resident_free;
    int handle,writable=argc>1 && strcmp(argv[1],"/RO");
    void interrupt far (*original)(void);
    void interrupt far (*installed)(void);
    int fast=argc>1 && (!strcmp(argv[1],"/FAST") || !strcmp(argv[1],"/FNV"));
    char *install=argc>1 && !strcmp(argv[1],"/FNV")?
        "/DRIVE:S /PORT:330 /RW /NOVERIFY /SKIPFATCHECK":fast?
        "/DRIVE:S /PORT:330 /RW /SKIPFATCHECK":argc>1 && !strcmp(argv[1],"/NV")?
        "/DRIVE:S /PORT:330 /RW /NOVERIFY":writable?
        "/DRIVE:S /PORT:330 /RW":"/DRIVE:S /PORT:330 /RO";
    setbuf(stdout,NULL);
    r.h.ah=0x30; int86(0x21,&r,&r); length=r.h.al==3?81:88;
    r.h.ah=0x52; int86x(0x21,&r,&r,&s);
    lol=(unsigned char far *)MK_FP(s.es,r.x.bx);
    cds=(unsigned char far *)MK_FP(*(unsigned far *)(lol+24),
         *(unsigned far *)(lol+22)+18*length);
    for(i=0;i<length;++i) saved[i]=cds[i];
    original=getvect(0x2f); base_largest=largest(); base_free=free_memory();
    run("/UNLOAD",1,0);
    for(cycle=0;cycle<3;++cycle) {
        run(install,0,1); check(present(),"resident discovery after installation");
        if(fast) {
            run("/MOUNT",0,0);
            memset(&r,0,sizeof(r)); segread(&s); s.es=s.ds;
            r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f;
            r.x.si=8; r.x.cx=32; r.x.di=(unsigned)buffer;
            int86x(0x2f,&r,&r,&s);
            check(!r.x.cflag && (*(unsigned *)(buffer+28)&16),
                  "fast FAT mount policy survives remount and reports in ABI");
        }
        installed=getvect(0x2f); resident_free=free_memory();
        memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
        r.x.dx=0x524f; r.x.si=9; int86(0x2f,&r,&r);
        psp=r.x.ax; mcb=(unsigned char far *)MK_FP(psp-1,0);
        owner=*(unsigned far *)(mcb+1);
        check(owner==psp,"resident MCB belongs to resident PSP");
        *(unsigned far *)(mcb+1)=_psp;
        run("/UNLOAD",1,0);
        *(unsigned far *)(mcb+1)=owner;
        check(present() && getvect(0x2f)==installed && free_memory()==resident_free,
              "invalid ownership refusal preserves driver and DOS allocations");
        check(resident_free<base_free,"installation occupies DOS memory");
        printf("MEMORY resident_bytes=%lu baseline_largest=%u\n",
            (base_free-resident_free)*16,base_largest);
        handle=open("S:\\README.TXT",O_RDONLY|O_BINARY);
        check(handle>=0,"open card file before refusal test");
        run("/UNLOAD",1,0);
        check(present() && getvect(0x2f)==installed && free_memory()==resident_free,
              "open-handle refusal retains vector and allocation");
        if(handle>=0) { check(read(handle,buffer,1)==1,"refused unload leaves file usable"); close(handle); }
        r.h.ah=0x0e; r.h.dl=18; int86(0x21,&r,&r);
        run("/UNLOAD",1,0); check(getvect(0x2f)==installed,"current-drive refusal preserves hook");
        r.h.ah=0x0e; r.h.dl=0; int86(0x21,&r,&r);
        hook_init(installed); setvect(0x2f,(void interrupt far (*)(void))ulhook);
        run("/UNLOAD",1,0);
        check(getvect(0x2f)==(void interrupt far (*)(void))ulhook && present(),
              "later interrupt hook refusal preserves entire chain");
        setvect(0x2f,installed);
        if(writable && cycle) {
            handle=open("S:\\UNLOAD.BIN",O_RDONLY|O_BINARY);
            check(handle>=0,"reload reopens previously committed file");
            if(handle>=0) {
                check(read(handle,buffer,sizeof(buffer))==sizeof(buffer),"reload reads committed file");
                for(i=0;i<sizeof(buffer) && buffer[i]==(unsigned char)(i*7+3);++i);
                check(i==sizeof(buffer),"reload preserves exact committed pattern"); close(handle);
            }
        }
        if(writable) {
            handle=open("S:\\UNLOAD.BIN",O_CREAT|O_TRUNC|O_WRONLY|O_BINARY,0x180);
            check(handle>=0,"create durable file before unload");
            for(i=0;i<sizeof(buffer);++i) buffer[i]=(unsigned char)(i*7+3);
            if(handle>=0) { for(i=0;i<8;++i) check(write(handle,buffer,sizeof(buffer))==sizeof(buffer),"write pattern");
                           check(!close(handle),"close dirty file before unload"); }
        }
        if(cycle==1) {
            run("/UNMOUNT",0,0);
            check(present(),"unmount retains resident until full unload");
        }
        /* An unrelated live DOS allocation above the TSR must survive. */
        r.h.ah=0x48; r.x.bx=64; int86(0x21,&r,&r);
        check(!r.x.cflag,"allocate unrelated block above resident"); held=r.x.cflag?0:r.x.ax;
        if(held) *(unsigned far *)MK_FP(held,0)=0xa55a;
        run("/UNLOAD",0,0);
        check(!present(),"resident discovery removed");
        check(getvect(0x2f)==original,"original INT 2F restored exactly");
        for(i=0;i<length && cds[i]==saved[i];++i);
        check(i==length,"all original CDS bytes restored exactly");
        if(held) {
            check(*(unsigned far *)MK_FP(held,0)==0xa55a,"unrelated allocation survives unload");
            segread(&s); s.es=held; r.h.ah=0x49; int86x(0x21,&r,&r,&s);
            check(!r.x.cflag,"release unrelated allocation");
        }
        check(free_memory()==base_free,"all resident memory reclaimed without leaks");
        check(largest()==base_largest,"largest executable DOS block restored");
        run("/UNLOAD",1,0);
    }
    printf("UNLOAD RESULT: %u failures\n",failures);
    return failures?1:0;
}
