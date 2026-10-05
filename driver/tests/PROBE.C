/* Real-DOS integration probe. Build: tcc -ms -I.. PROBE.C */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <dir.h>
#include <io.h>
#include <fcntl.h>
#include <alloc.h>

static unsigned failures;
static unsigned char buffer[4096];
static void check(int ok, char *what) {
#ifdef HARDWARE_TEST
    hardware_result(ok,what);
#else
    printf("%s: %s\n",ok?"PASS":"FAIL",what);
#endif
    fflush(stdout);
    if (!ok) ++failures;
}
/* Walk DOS's allocation chain, then overwrite all remaining DOS free memory.
 * This catches resident-size mistakes that otherwise survive until a large
 * game reuses memory released by the TSR. No fixed footprint is assumed. */
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
int main(void) {
    FILE *f, *g;
    unsigned i, n, mismatch;
#ifdef HARDWARE_TEST
    long first_bad;
    unsigned jft_unavailable;
#endif
    long pos;
    int h[17], j;
    unsigned char far *allocation, far *cross;
    struct SREGS s;
    struct ffblk a, b;
    union REGS r;
    puts("OTTERFS real DOS integration probe"); fflush(stdout);
    f=fopen("S:\\README.TXT","rb");
    check(f!=0,"open read-only file");
    if (f) {
        n=fread(buffer,1,sizeof(buffer),f);
#ifdef HARDWARE_TEST
        printf("DETAIL: small read length=%u EOF=%u ferror=%u\n",n,feof(f),ferror(f));
#endif
        check(n==24 && !memcmp(buffer,"Hello from Slot-otter!\r\n",24),"read exact content and EOF");
        check(fseek(f,-3L,SEEK_END)==0 && fgetc(f)=='!',"seek from end");
        fclose(f);
    }
    f=fopen("S:\\BIG.BIN","rb"); check(f!=0,"open fragmented large file");
    if (f) {
        pos=0; mismatch=0;
#ifdef HARDWARE_TEST
        first_bad=-1;
#endif
        while ((n=fread(buffer,1,sizeof(buffer),f))!=0) {
            for (i=0;i<n;++i) if (buffer[i]!=(unsigned char)((pos+i)*7+3)) {
                mismatch=1;
#ifdef HARDWARE_TEST
                if(first_bad<0) first_bad=pos+i;
#endif
            }
            pos+=n;
        }
#ifdef HARDWARE_TEST
        printf("DETAIL: large read length=%ld first_bad_offset=%ld EOF=%u ferror=%u\n",
               pos,first_bad,feof(f),ferror(f));
#endif
        check(pos==70000L && !mismatch && !ferror(f),"read 70000 bytes across clusters and 64 KiB");
        check(fseek(f,511L,SEEK_SET)==0 && fgetc(f)==(unsigned char)(511L*7+3),"backward seek");
        fclose(f);
    }
    check(findfirst("S:\\*.TXT",&a,0)==0,"findfirst wildcard");
    check(findfirst("S:\\SUBDIR\\*.*",&b,FA_DIREC)==0,"independent directory search");
    check(findnext(&a)==0,"resume first search");
    check(findfirst("S:\\HELLO.COM",&a,0)==0,"directory chain traversal");
    j=_chmod("S:\\README.TXT",0);
    check(j>=0 && (j&FA_RDONLY),"read-only attributes");
    check(chdir("S:\\SUBDIR")==0,"change directory");
    f=fopen("S:INNER.TXT","rb"); check(f!=0,"drive-relative path"); if(f) fclose(f);
    f=fopen("S:\\HIGH.TXT","rb");
    check(f!=0,"32-bit cluster number");
    if(f) { n=fread(buffer,1,5,f); check(n==5&&!memcmp(buffer,"HIGH\n",5),"high-cluster content"); fclose(f); }
    f=fopen("S:\\EMPTY.TXT","rb");
    check(f!=0,"empty file open"); if(f) { check(fgetc(f)==EOF,"empty file EOF"); fclose(f); }
    f=fopen("S:\\README.TXT","wb"); check(f==0,"reject truncate"); if(f) fclose(f);
    f=fopen("S:\\NEW.TXT","wb"); check(f==0,"reject create"); if(f) fclose(f);
    check(unlink("S:\\README.TXT")!=0,"reject delete");
    check(rename("S:\\README.TXT","S:\\OTHER.TXT")!=0,"reject rename");
    check(mkdir("S:\\NEW")!=0,"reject mkdir");
    check(rmdir("S:\\SUBDIR")!=0,"reject rmdir");
    check(_chmod("S:\\README.TXT",1,0)<0,"reject set attributes");
    j=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    if (j>=0) {
        check(write(j,"X",1)<0,"reject write through read-only handle");
        r.x.ax=0x5701; r.x.bx=j; r.x.cx=0; r.x.dx=0;
        int86(0x21,&r,&r);
        close(j);
        j=open("S:\\README.TXT",O_RDONLY|O_BINARY);
        r.x.ax=0x5700; r.x.bx=j; int86(0x21,&r,&r);
        check(!r.x.cflag && r.x.cx==0x6000 && r.x.dx==0x5821,
              "handle timestamp change cannot persist to SD"); close(j);
    }
    j=open("S:\\BIG.BIN",O_RDONLY|O_BINARY);
    allocation=(unsigned char far *)farmalloc(70000UL);
    check(j>=0 && allocation!=0,"allocate conventional-memory far buffer");
    if (j>=0 && allocation) {
        cross=(unsigned char far *)MK_FP(FP_SEG(allocation)+(FP_OFF(allocation)>>4),0xff00);
        segread(&s); s.ds=FP_SEG(cross); r.x.dx=FP_OFF(cross);
        r.h.ah=0x3f; r.x.bx=j; r.x.cx=1024;
        int86x(0x21,&r,&r,&s);
        mismatch=0;
        /* Normalize verification pointers: the supplied DOS buffer spans offset FFFF. */
        for(i=0;i<1024;++i) {
            unsigned char far *p;
            p=(unsigned char far *)MK_FP(FP_SEG(cross)+((0xff00UL+i)>>4),
                                        (unsigned)((0xff00UL+i)&15));
            if(*p!=(unsigned char)(i*7+3)) ++mismatch;
        }
#ifdef HARDWARE_TEST
        printf("DETAIL: segment-crossing read carry=%u AX=%u mismatches=%u buffer=%04X:%04X\n",
               r.x.cflag,r.x.ax,mismatch,FP_SEG(cross),FP_OFF(cross));
#endif
        check(!r.x.cflag && r.x.ax==1024 && !mismatch,"DOS read buffer crossing a 64 KiB segment boundary");
    }
    if(j>=0) close(j); if(allocation) farfree(allocation);
    r.x.ax=0x6700; r.x.bx=40; int86(0x21,&r,&r);
#ifdef HARDWARE_TEST
    jft_unavailable=r.x.cflag;
    printf("DETAIL: expand DOS handle table carry=%u AX=%u\n",r.x.cflag,r.x.ax);
#endif
    for(j=0;j<17;++j) h[j]=open("S:\\README.TXT",O_RDONLY|O_BINARY);
#ifdef HARDWARE_TEST
    if(jft_unavailable) puts("WARNING/SKIP: DOS could not expand the process handle table; 16-slot capacity not tested");
    else
#endif
    check(h[0]>=0 && h[15]>=0 && h[16]<0,"16 independent resident file slots");
    /* Turbo C close() rejects DOS handles >= its NFDS=20, even though DOS
     * successfully opens handle 20 after 6700h. Close through DOS directly. */
    mismatch=0;
    for(j=0;j<17;++j) if(h[j]>=0) {
        r.h.ah=0x3e; r.x.bx=h[j]; int86(0x21,&r,&r);
        if(r.x.cflag) ++mismatch;
    }
    check(!mismatch,"close every handle including DOS handle 20");
    f=fopen("S:\\README.TXT","rb"); g=fopen("S:\\README.TXT","rb");
    check(f&&g,"reuse slots after closing");
    if(f&&g) check(fgetc(f)=='H' && fgetc(f)=='e' && fgetc(g)=='H',"independent file positions");
    if(f) fclose(f); if(g) fclose(g);
    r.x.ax=0xd74f; int86(0x2f,&r,&r);
    check(r.x.ax==0x4f54 && r.x.bx==0x524f && r.x.cx==18,"resident installation query");
#ifdef HARDWARE_TEST
    if (hardware_stress) memory_pressure();
    else puts("SKIP: exhaustive free-memory overwrite (use /STRESS for this test)");
#else
    memory_pressure();
#endif
    printf("RESULT: %u failures\n",failures); fflush(stdout);
    return failures?1:0;
}
