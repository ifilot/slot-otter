/* Resident writer hardware qualification through DOS APIs only.
 * Turbo C 2.0, small model, 8086. GPL-3.0-or-later. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>
#include <dos.h>
#include <dir.h>
#include <io.h>
#include <fcntl.h>
#include <process.h>
#include "RWSD.H"
#include "KITHASH.H"
#include "TESTCHLD.C"

static FILE *logfile;
static unsigned sequence;
static char tester_path[128];
static unsigned long started, phase_started;
static const char *phase_name;
static void report(void);
static void stop(int code);
static unsigned long ticks(void) {
    volatile unsigned far *clock=(volatile unsigned far *)MK_FP(0x40,0x6c);
    unsigned hi,lo;
    do { hi=clock[1]; lo=clock[0]; } while (hi!=clock[1]);
    return ((unsigned long)hi<<16)|lo;
}
static unsigned long elapsed(unsigned long start) {
    unsigned long now=ticks();
    return now>=start?now-start:now+0x1800b0UL-start;
}
static void message(const char *format,...) {
    va_list ap;
    union REGS r;
    va_start(ap,format); vprintf(format,ap); va_end(ap); fflush(stdout);
    if(logfile) {
        va_start(ap,format); vfprintf(logfile,format,ap); va_end(ap);
        if(fflush(logfile) || ferror(logfile)) {
            puts("STOP: local log write failed; no further test operations.");
            exit(2);
        }
        /* Commit the LOCAL log so its last checkpoint survives a reset and
         * remains visible without waiting for this program to close it. */
        memset(&r,0,sizeof(r)); r.x.ax=0x6800; r.x.bx=fileno(logfile);
        int86(0x21,&r,&r);
        if(r.x.cflag) { puts("STOP: local log commit failed."); exit(2); }
    }
}
static int line(const char *text) { message("%s\n",text); return 0; }
static void timing(const char *name,unsigned long start) {
    unsigned long count=elapsed(start), tenths=(count*100+91)/182;
    message("TIMING: %s ticks=%lu seconds=%lu.%lu\n",name,count,tenths/10,tenths%10);
}
static void hardware_phase(const char *name) {
    if(phase_name) timing(phase_name,phase_started);
    phase_name=name; phase_started=ticks(); message("PHASE: %s\n",name);
}
static void hardware_result(int ok,const char *name) {
    int saved_errno=errno,saved_dos=_doserrno;
    struct DOSERROR ex;
    memset(&ex,0,sizeof(ex));
    if(!ok) dosexterr(&ex);
    message("%03u %s: %s\n",++sequence,ok?"PASS":"FAIL",name);
    if(!ok) {
        message("ERROR: errno=%d DOS=%d extended=%d class=%u action=%u locus=%u\n",
                saved_errno,saved_dos,ex.exterror,(unsigned char)ex.class,
                (unsigned char)ex.action,(unsigned char)ex.locus);
        message("C errno/DOS errno and extended errors can be stale after direct INT 21h or logging.\n");
        report(); stop(1);
    }
}
/* Share the native DOS probe, not its raw transport or card model. These
 * substitutions add local logging and stop at the first unexpected failure. */
#define RW_HARDWARE_TEST
#define printf message
#define puts line
#define main api_probe
#include "RWPROBE.C"
#undef main
#undef puts
#undef printf

static void control(union REGS *r,unsigned action) {
    memset(r,0,sizeof(*r)); r->x.ax=0xd74f; r->x.bx=0x4f54;
    r->x.dx=0x524f; r->x.si=action; int86(0x2f,r,r);
}
static int discovery(union REGS *r) {
    memset(r,0,sizeof(*r)); r->x.ax=0xd74f; int86(0x2f,r,r);
    return r->x.ax==0x4f54 && r->x.bx==0x524f;
}
static void report(void) {
    /* Fields are valid only when their private query returns CF clear. */
    union REGS r;
    struct SREGS s;
    SdDiagnostic d;
    memset(&d,0,sizeof(d)); segread(&s); s.es=s.ds;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
    r.x.dx=0x524f; r.x.si=4; r.x.cx=sizeof(d); r.x.di=(unsigned)&d;
    int86x(0x2f,&r,&r,&s);
    message("SD: query_CF=%u error=%u stage=%u LBA=%lu R1=%02X token=%02X status=%02X poison=%u attempts=%u\n",
            r.x.cflag,d.error,d.stage,d.lba,d.r1,d.token,d.status,d.poisoned,d.attempts);
    message("FIRST: error=%u stage=%u R1=%02X token=%02X status=%02X\n",
            d.first_error,d.first_stage,d.first_r1,d.first_token,d.first_status);
    message("COUNTERS: verified=%lu transmissions=%lu retries=%lu\n",
            d.verified,d.transmissions,d.retries);
    control(&r,6);
    message("LAST CALLBACK: function=%04X DOS_error=%u CF=%u (sticky)\n",r.x.ax,r.x.bx,r.x.cflag);
    control(&r,7);
    message("STACK: used=%u untouched=%u capacity=%u CF=%u (observed use)\n",
            r.x.ax,r.x.bx,r.x.cx,r.x.cflag);
    message("CRITICAL: count=%u last_AX=%04X last_SI=%u FAIL returned\n",
            critical_count,critical_device,critical_error);
}
static void stop(int code) {
    int bad;
    if(phase_name) timing(phase_name,phase_started);
    timing("total",started);
    message("HWRT RESULT: %s checks=%u ERRORLEVEL=%u\n",code?"STOP/FAIL":"PASS",sequence,code);
    if(code) message("STOP: retain this log and last checkpoint. Reboot; re-image before new writes.\n");
    bad=ferror(logfile); if(fclose(logfile)) bad=1; logfile=0;
    if(bad) { puts("STOP: local log could not be saved."); code=2; }
    exit(code);
}
static void card_report(void) {
    DriverInfo info;
    union REGS r;
    struct SREGS s;
    unsigned i;
    unsigned long unit;
    char product[6], cid_text[33];
    static const char digits[]="0123456789ABCDEF";
    memset(&info,0,sizeof(info)); memset(&r,0,sizeof(r)); segread(&s); s.es=s.ds;
    r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f; r.x.si=8;
    r.x.cx=sizeof(info); r.x.di=(unsigned)&info; int86x(0x2f,&r,&r,&s);
    if(r.x.cflag || r.x.cx!=sizeof(info) || info.abi!=1 || info.version!=OTTER_VERSION) {
        message("STOP: driver/tester versions do not match; use the complete same kit.\n"); stop(2);
    }
    message("BUILD: driver=" OTTER_VERSION_TEXT " ABI=%u resident=%u flags=%u\n",info.abi,info.resident,info.flags);
    message("POLICY: write_readback=%s; CRC/status checks remain enabled\n",
            (info.flags&8)?"DISABLED (silent corruption can escape)":"enabled");
    message("POLICY: mount_fat_check=%s; FAT sector and commit comparisons remain enabled\n",
            !(info.flags&2)?"not applicable (read-only)":
            (info.flags&16)?"SKIPPED (existing mismatches may surface later)":"enabled");
    message("FILESYSTEM: %s; restriction=%s\n",
            !(info.flags&4)?"offline":(info.flags&32)?"FAT16":"FAT32",
            (info.flags&64)?"FAT16":(info.flags&128)?"FAT32":"automatic");
    if (info.flags&8) message("COUNTERS NOTE: legacy verified field counts completed, unverified writes.\n");
    message("MOUNT TIMING: SD_ticks=%u filesystem_ticks=%u (18.2 ticks/second)\n",info.sd_ticks,info.fs_ticks);
    if(!(info.flags&1)) { message("STOP: mounted card identity unavailable.\n"); stop(2); }
    for(i=0;i<5;++i) product[i]=info.cid[i+3]>=32 && info.cid[i+3]<127?info.cid[i+3]:'?';
    product[5]=0;
    for(i=0;i<16;++i) {
        cid_text[i*2]=digits[info.cid[i]>>4];
        cid_text[i*2+1]=digits[info.cid[i]&15];
    }
    cid_text[32]=0;
    message("CARD: cached mounted CID=%s manufacturer=%02X product=%s serial=%02X%02X%02X%02X capacity_MiB=%lu\n",
        cid_text,info.cid[0],product,info.cid[9],info.cid[10],info.cid[11],info.cid[12],
        info.last_lba/2048UL+((info.last_lba%2048UL)==2047));
    /* DOS sees logical units, independently of FAT32 physical clusters.
     * Print the actual INT 21h result so capacity errors can be diagnosed
     * without trusting DIR's decimal formatting or assuming card=partition. */
    memset(&r,0,sizeof(r)); r.x.ax=0x3600; r.x.dx=19;
    int86(0x21,&r,&r);
    if(r.x.ax==0xffff || !r.x.ax || r.x.cx!=512 || r.x.bx>r.x.dx) {
        message("STOP: DOS disk-space query invalid AX=%04X BX=%u CX=%u DX=%u\n",
                r.x.ax,r.x.bx,r.x.cx,r.x.dx); report(); stop(2);
    }
    unit=(unsigned long)r.x.ax*r.x.cx;
    message("DOS SPACE: sectors_per_unit=%u bytes_per_sector=%u total_units=%u free_units=%u total_bytes=%lu free_bytes=%lu\n",
            r.x.ax,r.x.cx,r.x.dx,r.x.bx,unit*r.x.dx,unit*r.x.bx);
}
static int exact(const char *name,const char *expected) {
    char text[80];
    int h,n;
    h=open(name,O_RDONLY|O_BINARY); if(h<0) return 0;
    n=read(h,text,sizeof(text)); if(close(h)) return 0;
    return n==(int)strlen(expected) && !memcmp(text,expected,n);
}
static unsigned char pattern(unsigned long offset,unsigned seed) {
    /* Different deterministic patterns expose all-zero/all-FF stale writes
     * and sector/address confusion. Multiplication intentionally wraps U32. */
    if(seed==0) return 0;
    if(seed==1) return 255;
    return (unsigned char)((offset*7+3+(offset>>8)*13+seed*31)^(offset>>16));
}
static void stream(const char *name,unsigned long length,unsigned seed,int writing) {
    unsigned n,i;
    unsigned long pos=0;
    int h,got;
    h=writing?request(0x3c00,0,0,(unsigned)name):opened((char *)name,0);
    check(h>=0,writing?"create streamed pattern file":"open persisted pattern file");
    while(pos<length) {
        n=length-pos>sizeof(buffer)?sizeof(buffer):(unsigned)(length-pos);
        if(writing) {
            for(i=0;i<n;++i) buffer[i]=pattern(pos+i,seed);
            got=request(0x4000,h,n,(unsigned)buffer);
            if(got!=n) {
                message("WRITE DETAIL: file=%s offset=%lu requested=%u returned=%d\n",name,pos,n,got);
                check(0,"streamed write completed exact byte count");
            }
        } else {
            got=request(0x3f00,h,n,(unsigned)buffer);
            if(got!=n) {
                message("READ DETAIL: file=%s offset=%lu requested=%u returned=%d\n",name,pos,n,got);
                check(0,"streamed read completed exact byte count");
            }
            for(i=0;i<n;++i) if(buffer[i]!=pattern(pos+i,seed)) {
                message("MISMATCH: file=%s offset=%lu expected=%02X actual=%02X\n",
                        name,pos+i,pattern(pos+i,seed),buffer[i]);
                check(0,"streamed file exact bytes");
            }
        }
        pos+=n;
        if(!(pos%16384UL) || pos==length)
            message("PROGRESS: %s %s %lu/%lu bytes\n",writing?"write":"verify",name,pos,length);
    }
    if(writing) check(request(0x6800,h,0,0)>=0,"commit streamed file");
    else check(request(0x3f00,h,1,(unsigned)buffer)==0,"persisted file EOF exact");
    check(request(0x3e00,h,0,0)>=0,"close streamed file");
}
static void verify(void) {
    unsigned i,n,bad=0;
    int h;
    check(exact("S:\\RWTEMP\\DONE.TAG","OTTER RW RESULTS v1\r\n"),"completed test marker before verification");
    h=opened("S:\\RWTEMP\\DATA.BIN",0); check(h>=0,"open core API result");
    n=request(0x3f00,h,sizeof(buffer),(unsigned)buffer);
    check(n==1924,"core API result size after reboot/remount");
    for(i=0;i<n;++i) {
        unsigned char e;
        e=i<513?(unsigned char)(i%251):i<900?0:(unsigned char)((i-900)%251);
        if(i==511) e='O'; if(i==512) e='V';
        if(buffer[i]!=e) {
            if(!bad) message("MISMATCH: DATA.BIN offset=%u expected=%02X actual=%02X\n",i,e,buffer[i]);
            ++bad;
        }
    }
    check(!bad,"core API result exact persisted bytes");
    check(request(0x3f00,h,1,(unsigned)buffer)==0,"core API result EOF exact");
    {
        union REGS r;
        memset(&r,0,sizeof(r)); r.x.ax=0x5700; r.x.bx=h; int86(0x21,&r,&r);
        check(!r.x.cflag && r.x.cx==0x7441 && r.x.dx==0x5821,"explicit timestamp persists after reboot/remount");
    }
    check(request(0x3e00,h,0,0)>=0,"close core API result");
    stream("S:\\RWTEMP\\ZERO.BIN",1025UL,0,0);
    stream("S:\\RWTEMP\\FF.BIN",1025UL,1,0);
    stream("S:\\RWTEMP\\LARGE.BIN",70000UL,2,0);
    stream("S:\\RWTEMP\\FRAG.BIN",8208UL,3,0);
}
static void originals(void) {
    int h,got;
    unsigned i,n;
    unsigned long pos=0;
    check(exact("S:\\README.TXT","Hello from Slot-otter!\r\n"),"original README preserved");
    check(exact("S:\\HIGH.TXT","HIGH\n"),"original cluster above 65535 preserved");
    h=opened("S:\\BIG.BIN",0); check(h>=0,"original fragmented fixture accessible");
    while(pos<70000UL) {
        n=70000UL-pos>sizeof(buffer)?sizeof(buffer):(unsigned)(70000UL-pos);
        got=request(0x3f00,h,n,(unsigned)buffer);
        check(got==n,"original fragmented read byte count");
        for(i=0;i<n;++i) if(buffer[i]!=(unsigned char)((pos+i)*7+3)) {
            message("MISMATCH: BIG.BIN offset=%lu expected=%02X actual=%02X\n",
                    pos+i,(unsigned char)((pos+i)*7+3),buffer[i]);
            check(0,"original fragmented fixture preserved");
        }
        pos+=n;
    }
    check(request(0x3f00,h,1,(unsigned)buffer)==0,"original fragmented EOF exact");
    check(request(0x3e00,h,0,0)>=0,"close original fixture");
}
static void finish_test(void) {
    int h,g;
    unsigned i,k;
    unsigned long pos=0;
    char name[40];
    union REGS r;
    hardware_phase("directory moves and sharing");
    check(mkdir("S:\\RWTEMP\\TREEA")==0,"create directory-move source parent");
    check(mkdir("S:\\RWTEMP\\TREEA\\CHILD")==0,"create directory-move child");
    check(mkdir("S:\\RWTEMP\\TREEB")==0,"create directory-move target parent");
    h=request(0x3c00,0,0,(unsigned)"S:\\RWTEMP\\TREEA\\CHILD\\INNER.TXT");
    check(h>=0,"create file inside directory to move");
    check(request(0x4000,h,3,(unsigned)"DIR")==3,"write directory-move fixture");
    check(request(0x3e00,h,0,0)>=0,"close directory-move fixture");
    check(rename("S:\\RWTEMP\\TREEA\\CHILD","S:\\RWTEMP\\TREEB\\CHILD")==0,
          "move nonempty directory across parents");
    check(exact("S:\\RWTEMP\\TREEB\\CHILD\\INNER.TXT","DIR"),"moved directory child data accessible");
    check(chdir("S:\\RWTEMP\\TREEB\\CHILD")==0,"select moved directory");
    check(chdir("S:..")==0,"moved directory dot-dot resolves to new parent");
    {
        char cwd[80];
        check(getcurdir(19,cwd)==0 && !strcmp(cwd,"RWTEMP\\TREEB"),"new parent current directory exact");
    }
    check(rename("S:\\RWTEMP\\TREEB","S:\\RWTEMP\\RENAMED")!=0,"reject rename of current-directory ancestor");
    check(chdir("S:\\")==0,"restore root current directory");
    check(rename("S:\\RWTEMP\\TREEB","S:\\RWTEMP\\TREEB\\CHILD\\DESC")!=0,
          "reject directory move into its descendant");
    check(rename("S:\\RWTEMP\\TREEB","S:\\RWTEMP\\RENAMED")==0,"rename directory within parent");
    check(exact("S:\\RWTEMP\\RENAMED\\CHILD\\INNER.TXT","DIR"),"directory rename preserves child data");
    check(unlink("S:\\RWTEMP\\RENAMED\\CHILD\\INNER.TXT")==0,"delete moved child file");
    check(rmdir("S:\\RWTEMP\\RENAMED\\CHILD")==0,"remove moved child directory");
    check(rmdir("S:\\RWTEMP\\RENAMED")==0 && rmdir("S:\\RWTEMP\\TREEA")==0,"remove both empty parents");
    h=opened("S:\\RWTEMP\\DATA.BIN",0x12); check(h>=0,"open deny-all sharing handle");
    check(rejected(opened("S:\\RWTEMP\\DATA.BIN",0x40),32),"deny-all rejects another reader for sharing reason 32");
    check(request(0x3e00,h,0,0)>=0,"close deny-all handle");
    /* One beyond the sixteen lock slots exposes leaks on normal DOS exit.
     * This is not an abnormal-abort or FCB record-I/O qualification. */
    hardware_phase("DOS process-exit cleanup");
    for(i=0;i<17;++i) {
        message("PROCESS EXIT: iteration=%u/17, six unclosed handles and one lock\n",i+1);
        check(spawnl(P_WAIT,tester_path,tester_path,"/CHILD",NULL)==0,
              "DOS child exit releases previous locks and permits another child");
        check(discovery(&r) && !r.x.si,"DOS child exit releases every resident file slot");
    }
    h=opened("S:\\RWTEMP\\DATA.BIN",0x42); check(h>=0,"open result for persistent timestamp");
    check(request(0x5701,h,0x7441,0x5821)>=0,"set final known timestamp");
    check(request(0x3e00,h,0,0)>=0,"commit final known timestamp on close");
    hardware_phase("interleaved cluster allocation");
    h=request(0x3c00,0,0,(unsigned)"S:\\RWTEMP\\FRAG.BIN");
    check(h>=0,"create interleaved allocation file");
    for(i=0;i<16;++i) {
        message("PROGRESS: allocation spacer %u/16\n",i+1);
        for(k=0;k<513;++k) buffer[k]=pattern(pos+k,3);
        check(request(0x4000,h,513,(unsigned)buffer)==513,"append between interleaved allocations");
        pos+=513;
        sprintf(name,"S:\\RWTEMP\\G%02u.TMP",i);
        g=request(0x3c00,0,0,(unsigned)name); check(g>=0,"create allocation spacer");
        check(request(0x4000,g,1,(unsigned)"G")==1,"allocate spacer cluster");
        check(request(0x3e00,g,0,0)>=0,"close allocation spacer");
    }
    check(request(0x3e00,h,0,0)>=0,"close interleaved allocation result");
    for(i=0;i<16;++i) {
        sprintf(name,"S:\\RWTEMP\\G%02u.TMP",i);
        check(unlink(name)==0,"delete interleaved spacer and reclaim its cluster");
    }
    stream("S:\\RWTEMP\\FRAG.BIN",8208UL,3,0);
    hardware_phase("streamed zero, FF and large files");
    stream("S:\\RWTEMP\\ZERO.BIN",1025UL,0,1);
    stream("S:\\RWTEMP\\FF.BIN",1025UL,1,1);
    stream("S:\\RWTEMP\\LARGE.BIN",70000UL,2,1);
    stream("S:\\RWTEMP\\ZERO.BIN",1025UL,0,0);
    stream("S:\\RWTEMP\\FF.BIN",1025UL,1,0);
    stream("S:\\RWTEMP\\LARGE.BIN",70000UL,2,0);
    originals();
    h=request(0x3c00,0,0,(unsigned)"S:\\RWTEMP\\DONE.TAG");
    check(h>=0,"create completion marker only after verification");
    check(request(0x4000,h,21,(unsigned)"OTTER RW RESULTS v1\r\n")==21,"write completion marker");
    check(request(0x6800,h,0,0)>=0,"commit completion marker");
    check(request(0x3e00,h,0,0)>=0,"close completion marker");
}
static void swap(void) {
    union REGS r;
    control(&r,1); check(!r.x.cflag,"unmount before removal");
    message("ACTION: remove SD card now; press ENTER after the slot is empty.\n"); getchar();
    control(&r,2); check(r.x.cflag,"empty-slot mount returns bounded error");
    message("EMPTY-SLOT: DOS error=%u\n",r.x.ax); report();
    check(discovery(&r) && !r.x.dx,"empty slot leaves drive offline");
    message("ACTION: reinsert SAME test card; press ENTER when inserted.\n"); getchar();
    control(&r,2); check(!r.x.cflag,"explicit remount after insertion");
    check(exact("S:\\RW.TAG","OTTER RESIDENT WRITE KIT v1\r\n"),"supplied kit image marker after swap (not unique card identity)");
    verify(); originals();
}
int main(int argc,char **argv) {
    union REGS r;
    unsigned port=0x330,i,erase=0,mode=0;
    int h;
    char drive[MAXDRIVE],dir[MAXDIR],name[MAXFILE],ext[MAXEXT];
    const char *logname="RWINFO.LOG";
    /* Private self-exec child exits with raw DOS handles/lock. It precedes
     * logging and the normal zero-open-handle guard deliberately. */
    if(argc==2 && !strcmp(argv[1],"/CHILD")) return process_exit_child();
    started=ticks();
    if(strlen(argv[0])>=sizeof(tester_path)) return 2;
    strcpy(tester_path,argv[0]);
    for(i=1;i<(unsigned)argc;++i) {
        option_upper(argv[i]);
        if(!strcmp(argv[i],"/ERASE")) erase=1;
        else if(!strncmp(argv[i],"/PORT:",6) && parse_port(argv[i]+6,&port)) {}
        else if(!strcmp(argv[i],"/INFO") && !mode) mode=1;
        else if(!strcmp(argv[i],"/TEST") && !mode) { mode=2; logname="RWTEST.LOG"; }
        else if(!strcmp(argv[i],"/VERIFY") && !mode) { mode=3; logname="RWVERIFY.LOG"; }
        else if(!strcmp(argv[i],"/STRESS") && !mode) { mode=4; logname="RWSTRESS.LOG"; }
        else if(!strcmp(argv[i],"/SWAP") && !mode) { mode=5; logname="RWSWAP.LOG"; }
        else if(!strcmp(argv[i],"/MEMORY") && !mode) { mode=6; logname="RWMEM.LOG"; }
        else { puts("Usage: HWRT /INFO|/TEST|/VERIFY|/STRESS|/SWAP|/MEMORY [/ERASE] [/PORT:330]"); return 2; }
    }
    if(!mode || ((mode==2 || mode==4)!=erase)) {
        puts("STOP: /TEST and /STRESS require /ERASE; other modes prohibit it."); return 2;
    }
    fnsplit(argv[0],drive,dir,name,ext);
    if(getdisk()==18 || drive[0]=='S' || drive[0]=='s') {
        puts("STOP: copy the kit to local A:/C: and run there, never from S:."); return 2;
    }
    logfile=fopen(logname,"wt");
    if(!logfile) { puts("STOP: cannot create a local log file."); return 2; }
    harderr(critical);
    message("HWRT v" OTTER_VERSION_TEXT " / 8086 DOS API hardware test / source=%s\n",KIT_SOURCE);
    message("DOS=%u.%u local=%c: port=%03X mode=%u\n",_osmajor,_osminor,'A'+getdisk(),port,mode);
    message("WARNING: expendable supplied image only. /ERASE authorizes test-file creation/deletion.\n");
    if(!discovery(&r)) { message("STOP: no resident OTTER driver found.\n"); stop(2); }
    message("DRIVER: drive=%u online=%u open_slots=%u port=%03X\n",r.x.cx,r.x.dx,r.x.si,r.x.di);
    if(r.x.cx!=18 || r.x.di!=port || !r.x.dx || r.x.si) {
        message("STOP: require enhanced mounted S: driver, matching port, zero open slots.\n"); report(); stop(2);
    }
    control(&r,5);
    message("MODE: writable=%u attempts=%u online=%u\n",r.x.bx,r.x.cx,r.x.dx);
    if(r.x.cflag || r.x.cx!=3 || ((mode==2 || mode==4) && !r.x.bx)) {
        message("STOP: enhanced driver required; writing requires installation with /RW.\n"); stop(2);
    }
    card_report();
    hardware_phase("image identification");
    check(exact("S:\\RW.TAG","OTTER RESIDENT WRITE KIT v1\r\n"),"supplied expendable resident-write image marker");
    if(mode==2) {
        check(access(tester_path,0)==0,"local self-executable for process-exit test available");
        h=opened("S:\\RWTEMP\\DONE.TAG",0);
        if(h>=0) { request(0x3e00,h,0,0); message("STOP: prior results exist; re-image before /TEST.\n"); stop(2); }
        /* mkdir in the probe also refuses any unfinished prior RWTEMP. */
        hardware_phase("core DOS file APIs"); api_probe(1,argv); finish_test();
        hardware_phase("final saved-data verification"); verify();
    } else if(mode==3) { hardware_phase("saved-data verification"); verify(); originals(); }
    else if(mode==4) {
        hardware_phase("stress allocation, write, verify and deletion");
        verify();
        for(i=0;i<20;++i) {
            message("STRESS: iteration=%u/20; allocation/write/verify/delete\n",i+1);
            stream("S:\\RWTEMP\\LOOP.TMP",8193UL,i+2,1);
            stream("S:\\RWTEMP\\LOOP.TMP",8193UL,i+2,0);
            check(unlink("S:\\RWTEMP\\LOOP.TMP")==0,"delete scratch file and reclaim clusters");
        }
        verify(); originals();
    } else if(mode==5) { hardware_phase("controlled card removal and re-insertion"); swap(); }
    else if(mode==6) {
        hardware_phase("DOS memory pressure");
        message("WARNING: /MEMORY allocates and overwrites ALL free DOS memory. Save work first.\n");
        verify(); memory_pressure(); verify();
    }
    else originals();
    check(discovery(&r) && r.x.dx && !r.x.si,"driver remains online with zero open slots");
    check(!critical_count,"no unexpected DOS critical errors");
    report(); stop(0); return 0;
}
