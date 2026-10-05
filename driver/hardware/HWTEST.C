/* Real-hardware runner. No emulator control ports. GPL-3.0-or-later. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>
#include <dos.h>
#include <dir.h>
#include <io.h>
#include <fcntl.h>
#include <alloc.h>
#include "OTTER.H"

static FILE *logfile;
static unsigned sequence, critical_count;
static int hardware_stress;
static unsigned critical_device, critical_error;
static void message(char *format, ...) {
    va_list ap;
    va_start(ap,format); vprintf(format,ap); va_end(ap); fflush(stdout);
    if(logfile) {
        va_start(ap,format); vfprintf(logfile,format,ap); va_end(ap);
        fflush(logfile);
    }
}
static int line(char *s) { message("%s\n",s); return 0; }
static void hardware_result(int ok,char *what) {
    int saved_errno=errno, saved_dos=_doserrno;
    struct DOSERROR extended;
    memset(&extended,0,sizeof(extended));
    if(!ok) dosexterr(&extended);
    message("%03u %s: %s\n",++sequence,ok?"PASS":"FAIL",what);
    if(!ok) message("    errno=%d DOS=%d extended=%d class=%u action=%u locus=%u\n",
        saved_errno,saved_dos,extended.exterror,(unsigned char)extended.class,
        (unsigned char)extended.action,(unsigned char)extended.locus);
}
/* Do not call DOS or stdio inside DOS's critical-error callback. */
static int critical(int errval,int ax,int bp,int si) {
    (void)errval; (void)bp;
    ++critical_count; critical_device=ax; critical_error=si;
    hardresume(3); return 0;
}
#define HARDWARE_TEST
#define printf message
#define puts line
#define main filesystem_probe
#include "PROBE.C"
#undef main
#undef puts
#undef printf

static int query(union REGS *r) {
    memset(r,0,sizeof(*r)); r->x.ax=0xd74f; int86(0x2f,r,r);
    return r->x.ax==0x4f54 && r->x.bx==0x524f;
}
static unsigned control(unsigned action) {
    union REGS r;
    memset(&r,0,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
    r.x.dx=0x524f; r.x.si=action; int86(0x2f,&r,&r);
    message("CONTROL %s: carry=%u AX=%u\n",action==1?"UNMOUNT":"MOUNT",r.x.cflag,r.x.ax);
    return r.x.cflag?r.x.ax:0;
}
static int marker(void) {
    int h,n;
    char text[32];
    h=open("S:\\KIT.TAG",O_RDONLY|O_BINARY);
    if(h<0) return 0;
    n=read(h,text,sizeof(text)); close(h);
    return n==sizeof("OTTER HARDWARE KIT\r\n")-1 &&
           !memcmp(text,"OTTER HARDWARE KIT\r\n",sizeof("OTTER HARDWARE KIT\r\n")-1);
}
static void mount_checks(int swap) {
    union REGS r;
    struct ffblk search;
    FILE *f;
    int h;
    unsigned result;
    h=open("S:\\README.TXT",O_RDONLY|O_BINARY);
    check(h>=0,"open handle for mount interlock");
    if(h<0) return;
    check(control(1)==5,"unmount refused while a file is open");
    check(control(2)==5,"mount refused while a file is open");
    close(h);
    check(chdir("S:\\SUBDIR")==0,"prepare current-directory reset check");
    check(findfirst("S:\\*.TXT",&search,0)==0,"prepare search invalidation check");
    result=control(1); check(result==0,"unmount with no open handles");
    if(result) return;
    query(&r); check(r.x.dx==0 && r.x.si==0,"offline query after unmount");
    f=fopen("S:\\README.TXT","rb"); check(f==0,"offline read rejected"); if(f) fclose(f);
    if(swap) {
        message("ACTION: remove the SD card now. Press ENTER after the slot is empty.\n");
        getchar();
        check(control(2)!=0,"empty-slot mount rejected without hanging");
        query(&r); check(r.x.dx==0,"empty-slot failure leaves driver offline");
        message("ACTION: reinsert the SAME test card. Press ENTER when inserted.\n");
        getchar();
    }
    result=control(2); check(result==0,"explicit remount succeeds");
    if(result) { message("STOP: card could not remount; keep the log and reboot.\n"); return; }
    check(findnext(&search)!=0,"old directory search invalidated across mount");
    f=fopen("S:README.TXT","rb"); check(f!=0,"drive current directory reset to root"); if(f) fclose(f);
    check(marker(),"fixture identity preserved after remount");
}
static void raw_checks(void) {
    static struct { unsigned char before[16],sector[512],after[16]; } block;
    unsigned i,j,error;
    unsigned long start,data;
    check(sd_init()==0,"SPI initialize SDHC/SDXC and read card identity");
    if(failures) { sd_release(); return; }
    check(sd_check_media()==0,"card identity and presence recheck");
    memset(&block,0xa5,sizeof(block));
    error=sd_read(0,block.sector); check(!error,"raw read MBR sector zero");
    message("RAW READ: error=%u port=%X LBA=0 signature=%02X%02X partition_type=%02X\n",
            error,sd_port,block.sector[511],block.sector[510],block.sector[450]);
    if(error) { sd_release(); return; }
    check(block.sector[510]==0x55 && block.sector[511]==0xaa && block.sector[450]==0x0c,
          "test image MBR signature and primary FAT32 partition");
    start=get32(block.sector+454);
    check(start==2048UL,"test partition starts at LBA 2048");
    if(failures) { sd_release(); return; }
    error=sd_read(start,block.sector); check(!error,"raw read FAT32 boot sector");
    if(error) { sd_release(); return; }
    check(get16(block.sector+11)==512 && block.sector[13]==1 && get32(block.sector+44)==2,
          "hardware fixture FAT32 geometry");
    data=start+get16(block.sector+14)+(unsigned long)block.sector[16]*get32(block.sector+36);
    for(j=0;j<8;++j) {
        error=sd_read(data+2,block.sector);
        check(!error && !memcmp(block.sector,"Hello from Slot-otter!\r\n",24),
              "repeat raw CMD17 read exact known bytes");
    }
    j=0; for(i=0;i<16;++i) if(block.before[i]!=0xa5 || block.after[i]!=0xa5) ++j;
    check(!j,"raw sector guards intact (512-byte payload, CRC excluded)");
    sd_release();
}
int main(int argc,char **argv) {
    union REGS r;
    int i,prep=0,swap=0,resident,extra=0;
    char drive[MAXDRIVE],dir[MAXDIR],name[MAXFILE],ext[MAXEXT];
    for(i=1;i<argc;++i) {
        option_upper(argv[i]);
        if(!strcmp(argv[i],"/PREP")) prep=1;
        else if(!strcmp(argv[i],"/STRESS")) hardware_stress=1;
        else if(!strcmp(argv[i],"/SWAP")) swap=1;
        else if(!strcmp(argv[i],"/EXTRA")) extra=1;
        else if(!strncmp(argv[i],"/PORT:",6) && parse_port(argv[i]+6,&sd_port)) {}
        else { puts("Usage: HWTEST [/PREP] [/PORT:330] [/STRESS] [/SWAP] [/EXTRA]"); return 2; }
    }
    if((prep && (extra || swap || hardware_stress)) || (extra && (swap || hardware_stress))) {
        puts("STOP: incompatible test modes; run them separately."); return 2;
    }
    /* Resolve the current drive before opening a log: never log onto S:. */
    if(getdisk()==18) { puts("STOP: run from local A: or C:, never from S:."); return 2; }
    fnsplit(argv[0],drive,dir,name,ext);
    if(drive[0]=='S' || drive[0]=='s') { puts("STOP: copy HWTEST to local storage first."); return 2; }
    logfile=fopen(extra?"EXTRA.LOG":prep?"PREP.LOG":hardware_stress?"STRESS.LOG":swap?"SWAP.LOG":"HWTEST.LOG","wt");
    if(!logfile) { puts("STOP: cannot create local log. Use a writable local directory."); return 2; }
    harderr(critical);
    message("OTTER HARDWARE KIT v1 / 8086 / read-only SD tests\n");
    message("DOS=%u.%u current_drive=%c port=%X mode=%s stress=%u swap=%u\n",
            _osmajor,_osminor,'A'+getdisk(),sd_port,prep?"PREP":"RESIDENT",hardware_stress,swap);
    message("WARNING: only use the supplied expendable test SD image. Write-denial tests attempt mutations.\n");
    message("Diagnostics are snapshots; DOS extended errors can describe an earlier failing operation.\n");
    resident=query(&r);
    if(prep) {
        if(resident) { message("STOP: /PREP requires a fresh boot with no OTTERFS installed.\n"); fclose(logfile); return 2; }
        raw_checks();
    } else {
        message("QUERY: present=%u drive=%u online=%u handles=%u port=%X\n",
                resident,r.x.cx,r.x.dx,r.x.si,r.x.di);
        if(!resident || r.x.cx!=18 || !r.x.dx || r.x.si || r.x.di!=sd_port || !marker()) {
            message("STOP: expected mounted OTTERFS S:, zero handles, matching port and KIT.TAG.\n");
            message("Check LASTDRIVE=S, install /DRIVE:S, card image, and /STATUS. No mutation tests ran.\n");
            fclose(logfile); return 2;
        }
        if(hardware_stress) message("WARNING: /STRESS allocates and overwrites ALL DOS free memory. Save work first.\n");
        if(extra) {
            FILE *f;
            unsigned n,k,bad=0;
            unsigned long position=0;
            f=fopen("EXEC.LOG","rb");
            check(f!=0,"local EXEC output available");
            if(f) { n=fread(buffer,1,sizeof(buffer),f); check(n==9 && !memcmp(buffer,"EXEC OK\r\n",9),"execute COM from resident drive"); fclose(f); }
            f=fopen("COPIED.BIN","rb");
            check(f!=0,"local DOS COPY result available");
            if(f) {
                while((n=fread(buffer,1,sizeof(buffer),f))!=0) {
                    for(k=0;k<n;++k) if(buffer[k]!=(unsigned char)((position+k)*7+3)) bad=1;
                    position+=n;
                }
                check(position==70000UL && !bad && !ferror(f),"DOS COPY exact 70000-byte fragmented file"); fclose(f);
            }
        } else {
            filesystem_probe();
            mount_checks(swap);
        }
    }
    check(!critical_count,"no DOS critical-error callbacks");
    if(critical_count) message("CRITICAL: count=%u last_AX=%X last_SI=%X\n",critical_count,critical_device,critical_error);
    message("HARDWARE RESULT: %u failures, %u checks. ERRORLEVEL=%u\n",failures,sequence,failures?1:0);
    message("Send this complete log, setup, DOS version, RAM size, and last visible checkpoint if hung.\n");
    i=ferror(logfile);
    if(fclose(logfile)!=0) i=1;
    if(i) { puts("STOP: local log write failed. Free disk space and repeat."); return 2; }
    return failures?1:0;
}
