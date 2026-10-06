/* Actual MS-DOS API integration probe; not the final hardware test kit.
 * Build: tcc -ms RWPROBE.C. GPL-3.0-or-later. */
#include <stdio.h>
#include <string.h>
#include <dos.h>
#include <dir.h>
#include <io.h>
#include <fcntl.h>
#include <alloc.h>
#include "RWSD.H"
static unsigned failures,checks;
static unsigned last_dos_error;
static unsigned last_dos_function;
static unsigned critical_count,critical_device,critical_error;
static unsigned char buffer[2048];
/* INT 24h must return FAIL without calling DOS or the C I/O library. */
static int critical(int errval,int ax,int bp,int si) {
    (void)errval; (void)bp;
    ++critical_count; critical_device=ax; critical_error=si;
    hardresume(3); return 0;
}
static void check(int ok,const char *name) {
#ifdef RW_HARDWARE_TEST
    hardware_result(ok,name);
#else
    printf("%03u %s: %s\n",++checks,ok?"PASS":"FAIL",name);
    fflush(stdout); if (!ok) ++failures;
#endif
}
static int request(unsigned ax,unsigned bx,unsigned cx,unsigned dx) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=ax; r.x.bx=bx; r.x.cx=cx; r.x.dx=dx;
    int86(0x21,&r,&r);
    last_dos_error=r.x.cflag?r.x.ax:0;
    last_dos_function=ax;
    if (r.x.cflag) printf("DOS ERROR: function=%04X AX=%u\n",ax,r.x.ax);
    return r.x.cflag?-1:r.x.ax;
}
static int rejected(int result,unsigned expected) {
    union REGS r;
    unsigned mapped,fn;
    if(result>=0) return 0;
    /* DOS 5/6 may map remote sharing/locking errors to access denied. Check
     * the actual callback reason and online state, not merely any failed I/O. */
    mapped=last_dos_error;
    fn=(last_dos_function&0xff00)==0x3f00?0x1108:
       (last_dos_function&0xff00)==0x4000?0x1109:0x1116;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f; r.x.si=6;
    int86(0x2f,&r,&r);
    printf("REJECTION: DOS=%u callback=%04X reason=%u\n",mapped,r.x.ax,r.x.bx);
    if(r.x.cflag || r.x.ax!=fn || r.x.bx!=expected) return 0;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; int86(0x2f,&r,&r);
    return r.x.ax==0x4f54 && r.x.dx &&
           (mapped==expected || (mapped==5 && (expected==32 || expected==33)));
}
static int opened(char *name,unsigned mode) {
    return request(0x3d00|mode,0,0,(unsigned)name);
}
static int server_delete(char *name) {
    unsigned parameters[11];
    union REGS r;
    struct SREGS s;
    char canonical[128];
    memset(parameters,0,sizeof(parameters));
    memset(&r,0,sizeof(r)); r.x.ax=0x6200; int86(0x21,&r,&r);
    parameters[10]=r.x.bx; segread(&s); s.es=s.ds;
    memset(&r,0,sizeof(r)); r.x.ax=0x6000; r.x.si=(unsigned)name; r.x.di=(unsigned)canonical;
    int86x(0x21,&r,&r,&s);
    printf("SERVER CANONICAL: carry=%u error=%u name=%s\n",r.x.cflag,r.x.ax,
           r.x.cflag?"<failed>":canonical);
    if(r.x.cflag) return -1;
    segread(&s);
    parameters[0]=0x4100; parameters[3]=(unsigned)canonical; parameters[6]=s.ds;
    printf("SERVER DPL: DS=%04X SS=%04X DX=%04X PSP=%04X\n",s.ds,s.ss,
           parameters[3],parameters[10]);
    /* Ordinary 41h rejects wildcards before the redirector is called.
     * This optional server-interface experiment still returns error 3 on
     * DOS 5/6. FCB deletion and COMMAND.COM DEL are the validated paths. */
    return request(0x5d00,0,0,(unsigned)parameters);
}
static void trace_names(void) {
    /* Optional /SERVER trace uses DOS 4-6 SDA offsets, not DOS 3 offsets. */
    union REGS r;
    struct SREGS s;
    unsigned char far *sda,far *name;
    unsigned i,off;
    char text[81];
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f; r.x.si=6;
    int86(0x2f,&r,&r);
    printf("DRIVER LAST ERROR: function=%04X error=%u carry=%u\n",r.x.ax,r.x.bx,r.x.cflag);
    memset(&r,0,sizeof(r)); r.x.ax=0x5d06; segread(&s); int86x(0x21,&r,&r,&s);
    sda=(unsigned char far *)MK_FP(s.ds,r.x.si);
    for(i=0;i<80;++i) { text[i]=sda[0x9e+i]; if(!text[i]) break; } text[80]=0;
    printf("SDA NAME BUFFER: %s\n",text);
    off=*(unsigned far *)(sda+0x292); name=(unsigned char far *)MK_FP(s.ds,off);
    for(i=0;i<80;++i) { text[i]=name[i]; if(!text[i]) break; } text[80]=0;
    printf("SDA NAME POINTER: %04X:%04X => %s\n",s.ds,off,text);
}
static void transport_report(const char *phase) {
    SdDiagnostic d;
    union REGS r;
    struct SREGS s;
    memset(&r,0,sizeof(r)); segread(&s); s.es=s.ds;
    r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f; r.x.si=4;
    r.x.cx=sizeof(d); r.x.di=(unsigned)&d; int86x(0x2f,&r,&r,&s);
    if(r.x.cflag) { puts("DIAGNOSTIC QUERY FAILED"); return; }
    printf("TRANSPORT phase=%s verified=%lu transmissions=%lu retries=%lu error=%u first=%u poison=%u LBA=%lu stage=%u attempts=%u\n",
           phase,d.verified,d.transmissions,d.retries,d.error,d.first_error,d.poisoned,
           d.lba,d.stage,d.attempts);
}
static unsigned long seek(int handle,unsigned long position) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0x4200; r.x.bx=handle;
    r.x.cx=(unsigned)(position>>16); r.x.dx=(unsigned)position;
    int86(0x21,&r,&r);
    return r.x.cflag?0xffffffffUL:((unsigned long)r.x.dx<<16)|r.x.ax;
}
static int region(int handle,int unlock,unsigned long start,unsigned long length) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0x5c00|unlock; r.x.bx=handle;
    r.x.cx=(unsigned)(start>>16); r.x.dx=(unsigned)start;
    r.x.si=(unsigned)(length>>16); r.x.di=(unsigned)length;
    int86(0x21,&r,&r);
    printf("LOCK DETAIL: unlock=%u carry=%u error=%u\n",unlock,r.x.cflag,r.x.ax);
    return r.x.cflag?-1:0;
}
static void memory_pressure(void) {
    union REGS r;
    struct SREGS s;
    unsigned mcb, size, segment, i, k, found=0, count=0, mismatch;
    static unsigned segments[64];
    unsigned char far *header, far *p;
    void interrupt far (*handler)(void);
    int h;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; int86(0x2f,&r,&r);
    check(r.x.si==0,"all resident file handles closed before memory pressure");
    handler=getvect(0x2f);
    r.h.ah=0x52; int86x(0x21,&r,&r,&s);
    mcb=*(unsigned far *)MK_FP(s.es,r.x.bx-2);
    for(k=0;k<1000;++k) {
        header=(unsigned char far *)MK_FP(mcb,0);
        if(header[0]!='M' && header[0]!='Z') break;
        size=*(unsigned far *)(header+3);
        if(FP_SEG(handler)>mcb && (unsigned long)FP_SEG(handler)<(unsigned long)mcb+1+size) {
            printf("RESIDENT MCB: %lu bytes\n",(unsigned long)size*16);
            found=1; break;
        }
        if(header[0]=='Z') break;
        mcb+=size+1;
    }
    check(found,"interrupt handler lies inside allocated resident DOS block");
    /* Exhaust every free block, including fragmented environment allocations. */
    while(count<64) {
        r.h.ah=0x48; r.x.bx=0xffff; int86(0x21,&r,&r);
        size=r.x.bx;
        if(r.x.cflag && r.x.ax==8 && !size) break;
        if(!r.x.cflag || r.x.ax!=8) { check(0,"query free DOS memory"); break; }
        r.h.ah=0x48; r.x.bx=size; int86(0x21,&r,&r);
        if(r.x.cflag) { check(0,"allocate free DOS memory"); break; }
        segment=r.x.ax; segments[count++]=segment;
        for(k=0;k<size;++k) {
            p=(unsigned char far *)MK_FP(segment+k,0);
            for(i=0;i<16;++i) p[i]=0xa5;
        }
    }
    check(count>0 && count<64 && r.x.cflag && r.x.ax==8 && r.x.bx==0,
          "allocate and overwrite every free DOS memory block");
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
    r.x.dx=0x524f; r.x.si=1; int86(0x2f,&r,&r);
    check(!r.x.cflag,"unmount while free DOS memory is overwritten");
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
    r.x.dx=0x524f; r.x.si=2; int86(0x2f,&r,&r);
    check(!r.x.cflag,"remount while free DOS memory is overwritten");
    h=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    check(h>=0 && read(h,buffer,24)==24 && !memcmp(buffer,"Hello from Slot-otter!\r\n",24),
          "read after overwriting all available DOS memory");
    if(h>=0) close(h);
    mismatch=0;
    for(i=0;i<count;++i) {
        r.h.ah=0x49; s.es=segments[i]; int86x(0x21,&r,&r,&s);
        if(r.x.cflag) ++mismatch;
    }
    check(!mismatch,"release memory pressure allocations");
}
int main(int argc,char **argv) {
    union REGS r;
    struct SREGS s;
    unsigned i,bad,time,date;
    int a,b,c;
    char name[40];
    unsigned char fcb[37];
    unsigned char far *allocation,far *cross,far *p;
    harderr(critical);
#ifdef RW_HARDWARE_TEST
    puts("Resident DOS API tests on the guarded expendable hardware image.");
#else
    puts("Writable resident DOS API probe v0.1; disposable emulator image only.");
#endif
    check(mkdir("S:\\RWTEMP")==0,"create test directory");
    a=request(0x3c00,0,0,(unsigned)"S:\\RWTEMP\\DATA.BIN");
    check(a>=0,"create file through DOS");
    if (a<0) goto finish;
    for (i=0;i<1025;++i) buffer[i]=(unsigned char)(i%251);
    check(request(0x4000,a,1025,(unsigned)buffer)==1025,"write across three sectors");
    check(seek(a,511)==511,"seek backward");
    check(request(0x4000,a,8,(unsigned)"OVERLAP!")==8,"overwrite sector boundary");
    check(seek(a,1500)==1500,"seek beyond EOF");
    check(request(0x4000,a,4,(unsigned)"TAIL")==4,"write past EOF with zero gap");
    check(request(0x6800,a,0,0)>=0,"DOS commit");
    b=request(0x4500,a,0,0);
    check(b>=0,"duplicate handle shares SFT");
    if (b>=0) {
        check(seek(b,0)==0,"seek duplicated handle");
        check(request(0x3f00,a,5,(unsigned)buffer)==5 && !memcmp(buffer,"\0\1\2\3\4",5),
              "duplicate position affects original handle");
        request(0x3e00,b,0,0);
    }
    check(seek(a,0)==0,"rewind modified file");
    check(request(0x3f00,a,2048,(unsigned)buffer)==1504,"read complete file size");
    bad=0;
    for (i=0;i<1504;++i) {
        unsigned char expected;
        expected=i<1025?(unsigned char)(i%251):0;
        if (i>=511 && i<519) expected="OVERLAP!"[i-511];
        if (i>=1500) expected="TAIL"[i-1500];
        if (buffer[i]!=expected) ++bad;
    }
    check(!bad,"exact file content, overwritten bytes and zero gap");
    check(seek(a,513)==513 && request(0x4000,a,0,0)==0,"zero-length DOS write truncates");
    check(seek(a,1025)==1025 && request(0x4000,a,0,0)==0,"zero-length DOS write extends");
    check(request(0x5701,a,0x7441,0x5821)>=0,"set timestamp through DOS handle");
    check(request(0x3e00,a,0,0)>=0,"close commits timestamp");
    a=opened("S:\\RWTEMP\\DATA.BIN",0x42);
    check(a>=0,"reopen with sharing enabled");
    if (a<0) goto finish;
    memset(&r,0,sizeof(r)); r.x.ax=0x5700; r.x.bx=a; int86(0x21,&r,&r);
    time=r.x.cx; date=r.x.dx;
    check(!r.x.cflag && time==0x7441 && date==0x5821,"timestamp persists after reopen");
    b=opened("S:\\RWTEMP\\DATA.BIN",0x42);
    check(b>=0,"open second independent shared handle");
    if (b>=0) {
        check(region(a,0,4,8)==0,"lock region through DOS");
        seek(b,4);
        check(rejected(request(0x3f00,b,1,(unsigned)buffer),33),"other handle read rejected for lock reason 33");
        check(rejected(request(0x4000,b,1,(unsigned)"X"),33),"other handle write rejected for lock reason 33");
        check(region(a,1,4,8)==0,"unlock region through DOS");
        check(request(0x3f00,b,1,(unsigned)buffer)==1,"read allowed after unlock");
        request(0x3e00,b,0,0);
    }
    allocation=(unsigned char far *)farmalloc(70000UL);
    check(allocation!=0,"allocate conventional far buffer");
    if (allocation) {
        /* Deliberately start at FF00h: the transfer crosses offset rollover
         * during both overwrite and append, not merely at a sector boundary. */
        cross=(unsigned char far *)MK_FP(FP_SEG(allocation)+(FP_OFF(allocation)>>4),0xff00);
        for(i=0;i<1024;++i) {
            p=(unsigned char far *)MK_FP(FP_SEG(cross)+((0xff00UL+i)>>4),(unsigned)((0xff00UL+i)&15));
            *p=(unsigned char)(i%251);
        }
        seek(a,900);
        memset(&r,0,sizeof(r)); r.x.ax=0x4000; r.x.bx=a; r.x.cx=1024; r.x.dx=FP_OFF(cross);
        segread(&s); s.ds=FP_SEG(cross); int86x(0x21,&r,&r,&s);
        printf("FAR WRITE: carry=%u AX=%u\n",r.x.cflag,r.x.ax);
        check(!r.x.cflag && r.x.ax==1024,"DOS write crosses 64 KiB during overwrite and append");
        seek(a,900);
        bad=request(0x3f00,a,1024,(unsigned)buffer)!=1024;
        for(i=0;i<1024;++i) if(buffer[i]!=(unsigned char)(i%251)) ++bad;
        check(!bad,"far write exact data");
        farfree(allocation);
    }
    request(0x3e00,a,0,0);
    check(mkdir("S:\\RWTEMP\\SUB")==0,"create nested directory");
    check(rename("S:\\RWTEMP\\DATA.BIN","S:\\RWTEMP\\SUB\\MOVED.BIN")==0,"rename across directories");
    check(rmdir("S:\\RWTEMP\\SUB")!=0,"reject deleting nonempty directory");
    check(rename("S:\\RWTEMP\\SUB\\MOVED.BIN","S:\\RWTEMP\\DATA.BIN")==0,"rename file back");
    check(rmdir("S:\\RWTEMP\\SUB")==0,"remove empty directory");
    a=request(0x3c00,0,1,(unsigned)"S:\\RWTEMP\\RO.BIN");
    check(a>=0,"create file with readonly attribute");
    if (a>=0) {
        check(request(0x4000,a,7,(unsigned)"INITIAL")==7,"initial readonly create handle can write");
        request(0x3e00,a,0,0);
        check(rejected(opened("S:\\RWTEMP\\RO.BIN",1),5),"readonly file returns access error 5 to subsequent writer");
        check(request(0x4301,0,32,(unsigned)"S:\\RWTEMP\\RO.BIN")>=0,"clear readonly attribute");
        check(unlink("S:\\RWTEMP\\RO.BIN")==0,"delete file and release clusters");
    }
    memset(&r,0,sizeof(r)); r.x.ax=0x6c00; r.x.bx=0x42; r.x.cx=2;
    r.x.dx=0x10; r.x.si=(unsigned)"S:\\RWTEMP\\EXT.BIN";
    int86(0x21,&r,&r); c=r.x.ax;
    printf("EXTENDED OPEN: carry=%u AX=%u action=%u\n",r.x.cflag,r.x.ax,r.x.cx);
    check(!r.x.cflag,"extended create/open DOS API");
    if (!r.x.cflag) {
        check(request(0x4000,c,3,(unsigned)"EXT")==3,"write extended-created file");
        request(0x3e00,c,0,0);
        check(request(0x4300,0,0,(unsigned)"S:\\RWTEMP\\EXT.BIN")&2,"extended attributes come from correct SDA field");
        request(0x4301,0,32,(unsigned)"S:\\RWTEMP\\EXT.BIN"); unlink("S:\\RWTEMP\\EXT.BIN");
    }
    bad=0;
    for(i=0;i<20;++i) {
        sprintf(name,"S:\\RWTEMP\\P%02u.TMP",i);
        a=request(0x3c00,0,0,(unsigned)name);
        if(a<0) ++bad;
        else if(request(0x3e00,a,0,0)<0) ++bad;
    }
    check(!bad,"grow directory with twenty new entries");
    if(argc>1 && !strcmp(argv[1],"/SERVER")) {
        a=server_delete("S:\\RWTEMP\\P???????.TMP");
        if(a<0) trace_names();
        check(a>=0,"DOS server wildcard delete (optional diagnostic)");
    } else {
        check(chdir("S:\\RWTEMP")==0,"select directory for DOS FCB wildcard delete");
        memset(fcb,0,sizeof(fcb)); fcb[0]=19; memcpy(fcb+1,"P???????TMP",11);
        memset(&r,0,sizeof(r)); r.x.ax=0x1300; r.x.dx=(unsigned)fcb;
        int86(0x21,&r,&r);
        printf("FCB DELETE: AL=%02X\n",r.h.al);
        check(r.h.al==0,"DOS FCB wildcard delete across directory chain");
        check(chdir("S:\\")==0,"restore root current directory");
    }
    bad=0;
    for(i=0;i<20;++i) {
        sprintf(name,"S:\\RWTEMP\\P%02u.TMP",i); a=opened(name,0);
        if(a>=0) { ++bad; request(0x3e00,a,0,0); }
    }
    check(!bad,"all twenty wildcard-deleted files absent");
    memset(&r,0,sizeof(r)); r.x.ax=0x3600; r.x.dx=19; int86(0x21,&r,&r);
    check(r.x.ax!=0xffff && r.x.bx>0,"report writable disk free space");
    transport_report("WRITE");
#ifndef RW_HARDWARE_TEST
    memory_pressure();
#endif
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54; r.x.dx=0x524f; r.x.si=7;
    int86(0x2f,&r,&r);
    printf("RESIDENT STACK: used=%u unused=%u capacity=%u\n",r.x.ax,r.x.bx,r.x.cx);
    check(!r.x.cflag && r.x.cx==2048 && r.x.ax+r.x.bx==2048 && r.x.bx>=128,
          "resident private stack retains at least 128 guard bytes");
finish:
    transport_report("FINISH");
    printf("CRITICAL ERRORS: count=%u device=%04X error=%u (FAIL returned)\n",
           critical_count,critical_device,critical_error);
#ifndef RW_HARDWARE_TEST
    printf("RW PROBE RESULT: %u failures, %u checks\n",failures,checks); fflush(stdout);
#else
    puts("Core DOS API checks completed. Memory pressure is a separate /MEMORY run.");
#endif
    return failures?1:0;
}
