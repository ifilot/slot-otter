/* Installation-only far C. Generated INITTAIL/INITDATA segments are released
 * after the retained call gates restore CRT vectors and keep the resident core.
 * Near pointers still use original DGROUP; every code call crosses far gates.
 * No runtime/library near calls are permitted in the generated installer ASM.
 */
#define RW_DRIVER
#define INSTALL_BUILD
/* SPDX-License-Identifier: GPL-3.0-or-later */
#include "OTTER.H"

#include "RWSD.H"
#include "INSTALL.H"



static U16 far i_strlen(const char *p) { U16 n=0; while (*p++) ++n; return n; }
static int far i_strcmp(const char *a,const char *b) {
    while (*a && *a==*b) { ++a; ++b; }
    return (U8)*a-(U8)*b;
}
static int far i_strncmp(const char *a,const char *b,U16 n) {
    while (n && *a && *a==*b) { ++a; ++b; --n; }
    return n?(U8)*a-(U8)*b:0;
}
static void far i_fill(void *p,U8 value,U16 n) {
    U8 *out=p; while (n--) *out++=value;
}
static void far i_zero(void *p,U16 n) { i_fill(p,0,n); }

#define PORT_SCOPE static
#define PORT_CALL far
#define PORT_PARSE i_parse_port
#define PORT_UPPER i_option_upper
#include "PORTBODY.H"

extern unsigned _psp;
extern U8 resident_end;

/* Installer/control output only. Avoid pulling stdio formatting, streams and
 * buffering into the TSR. DOS handle 1 preserves command-line redirection. */
static void far text(const char *value) {
    union REGS r;
    r.x.ax=0x4000; r.x.bx=1; r.x.cx=i_strlen(value); r.x.dx=(U16)value;
    int86(0x21,&r,&r);
}
static void far line(const char *value) { text(value); text("\r\n"); }
static void far number(U16 value, U16 base, U16 width) {
    char buffer[12], *p=buffer+11;
    U16 digit;
    *p=0;
    do {
        digit=(U16)(value%base); value/=base;
        *--p=(char)(digit<10?'0'+digit:'A'+digit-10);
        if (width) --width;
    } while (value);
    while (width--) *--p='0';
    text(p);
}
static void far letter(U16 drive) { char value[2]; value[0]='A'+drive; value[1]=0; text(value); }
static void far mount_error(U16 code) {
    text("Cannot mount card (DOS error "); number(code,10,0);
    line("); drive is offline.");
}
static int far usage(void) {
#ifdef RW_DRIVER
    line("OTTERWR 0.4 - Slot-otter verified FAT32 drive");
    line("Usage: OTTERWR /DRIVE:S [/PORT:330] [/RW | /RO]");
    line("Writing is disabled unless /RW is supplied at installation.");
#else
    line("OTTERWR 0.2 - read-only Slot-otter FAT32 drive");
    line("Usage: OTTERWR /DRIVE:S [/PORT:330]");
#endif
    line("       OTTERWR /MOUNT | /UNMOUNT | /STATUS");
    line("Requires DOS 3.1-6.x, 8088+, SDHC/SDXC, and LASTDRIVE >= letter.");
    return 1;
}
int far installer(int argc, char **argv) {
    union REGS r;
    struct SREGS s;
    U8 far *lol, far *cds;
    void interrupt far (*previous)(void);
    U16 cds_size, paragraphs, env, mounted;
    U16 port;
    int i, have_drive, command, have_port, have_access;
    have_drive=command=have_port=have_access=0;
    for (i=1; i<argc; ++i) {
        i_option_upper(argv[i]);
        if (!i_strncmp(argv[i], "/DRIVE:", 7) && i_strlen(argv[i])==8 &&
            argv[i][7]>='C' && argv[i][7]<='Z') {
            drive_number=argv[i][7]-'A'; have_drive=1;
        } else if (!i_strncmp(argv[i], "/PORT:", 6)) {
            if (!i_parse_port(argv[i]+6,&port))
                return usage();
            sd_port=(U16)port; have_port=1;
#ifdef RW_DRIVER
        } else if (!i_strcmp(argv[i],"/RW") && !have_access) {
            sd_write_enabled=1; have_access=1;
        } else if (!i_strcmp(argv[i],"/RO") && !have_access) {
            sd_write_enabled=0; have_access=1;
#endif
        } else if (!i_strcmp(argv[i],"/MOUNT") && !command) command=2;
        else if (!i_strcmp(argv[i],"/UNMOUNT") && !command) command=1;
        else if (!i_strcmp(argv[i],"/STATUS") && !command) command=3;
        else return usage();
    }
    if ((!command && !have_drive) || (command && (have_drive || have_port)))
        return usage();
#ifdef RW_DRIVER
    if (command && have_access) return usage();
#endif
    i_zero(&r,sizeof(r)); r.x.ax=0xd74f; int86(0x2f,&r,&r);
    if (command) {
        if (r.x.ax!=0x4f54 || r.x.bx!=0x524f) {
            line("OTTERWR is not resident."); return 1;
        }
        if (command==3) {
            text("OTTERWR "); letter(r.x.cx); text(r.x.dx?": mounted, ":": offline, ");
            number(r.x.si,10,0); text(" open files, port "); number(r.x.di,16,3); line(".");
            return 0;
        }
        i_zero(&r,sizeof(r)); r.x.ax=0xd74f; r.x.bx=0x4f54;
        r.x.dx=0x524f; r.x.si=command; int86(0x2f,&r,&r);
        if (r.x.cflag) {
            if (r.x.ax==5) line("Close all files on the drive before mounting or unmounting.");
            else mount_error(r.x.ax);
            return 1;
        }
        line(command==1?"OTTERWR drive is offline; card may be removed.":
#ifdef RW_DRIVER
                           "OTTERWR card mounted in its installed access mode.");
#else
                           "OTTERWR card mounted read-only.");
#endif
        return 0;
    }
    if (r.x.ax==0x4f54 && r.x.bx==0x524f) {
        text("OTTERWR is already resident on "); letter(r.x.cx); line(":."); return 1;
    }
    r.h.ah=0x30; int86(0x21,&r,&r); dos_major=r.h.al;
    if (dos_major<3 || dos_major>6 || (dos_major==3 && r.h.ah<10)) {
        line("Unsupported DOS version; requires MS/PC-DOS 3.1-6.x."); return 1;
    }
    r.x.ax=0x5d06; r.x.dx=0; segread(&s); int86x(0x21,&r,&r,&s);
    if (r.x.cflag) { line("Cannot obtain DOS SDA."); return 1; }
    dos_sda=(U8 far *)MK_FP(s.ds,r.x.si);
    dos_name_offset=dos_major==3?0x92:0x9e;
    dos_attr_offset=dos_major==3?0x23a:0x24d;
    dos_search_offset=dos_major==3?0x192:0x19e;
    dos_found_offset=dos_search_offset+21;
    r.h.ah=0x52; int86x(0x21,&r,&r,&s);
    lol=(U8 far *)MK_FP(s.es,r.x.bx);
    if (drive_number>=lol[0x21]) {
        text("Set LASTDRIVE="); letter(drive_number); line(" or higher in CONFIG.SYS and reboot.");
        return 1;
    }
    cds_size=dos_major==3?0x51:0x58;
    cds=(U8 far *)MK_FP(get16(lol+0x18), get16(lol+0x16)+drive_number*cds_size);
    if (get16(cds+0x43)&0xc000) { line("Drive letter is already in use."); return 1; }
    drive_cds=cds;
    line("Initializing SD card and checking filesystem; FAT comparison may take time.");
    mounted=media_mount();
    text("Mount timing: SD "); number(mount_sd_ticks,10,0);
    text(", filesystem "); number(mount_fs_ticks,10,0);
    line(" BIOS ticks (about 18.2 ticks/second).");
    /* Bound Turbo C's startup allocation with _heaplen/_stklen above.
     * The resident callbacks use their own static stack and no heap. */
    segread(&s);
    /* Keep all linked code/data and the private callback stack; release the
     * startup stack/heap beyond the linker-checked _BSSEND marker. keep()
     * restores CRT interrupt vectors before DOS terminates this process. */
    paragraphs=(U16)(s.ds-_psp+(((U16)&resident_end+15U)>>4));
    resident_bytes=paragraphs*16;
    text("OTTERWR: "); letter(drive_number);
#ifdef RW_DRIVER
    text(sd_write_enabled?": verified read/write, port ":": read-only, port ");
#else
    text(": read-only, port ");
#endif
    number(sd_port,16,3); text(", resident "); number(paragraphs*16,10,0); line(" bytes.");
    if (mounted) {
        text("Drive offline (DOS error "); number(mounted,10,0);
        line("). Insert a card and run OTTERWR /MOUNT.");
    }
    else line("Card mounted. Run OTTERWR /UNMOUNT before removing it or running OTTERNAV.");
    /* A TSR must release its inherited standard handles, especially redirected
     * output. Direct writes have no C buffers to flush. */
    for (i=0;i<5;++i) { r.x.ax=0x3e00; r.x.bx=i; int86(0x21,&r,&r); }
    env=get16((U8 far *)MK_FP(_psp,0x2c));
    if (env) { r.h.ah=0x49; s.es=env; int86x(0x21,&r,&r,&s); }
#ifdef RW_DRIVER
    /* Fill before installing the bridge. The private query scans untouched
     * A5 bytes for observed stack use; IRQ use is included, not predicted. */
    i_fill(resident_stack,0xa5,sizeof(resident_stack));
#endif
    previous=getvect(0x2f); bridge_init(previous);
    /* DOS updates the CDS path after our change-directory validation. */
    cds[0]='A'+drive_number; cds[1]=':'; cds[2]='\\'; cds[3]=0;
    put16(cds+0x43,0xc080); put32(cds+0x45,0);
    put32(cds+0x49,0xffffffffUL); put16(cds+0x4d,0);
    put16(cds+0x4f,2);
    if (dos_major>=4) { cds[0x51]=4; put32(cds+0x52,0); put16(cds+0x56,0); }
    setvect(0x2f,(void interrupt far (*)(void))redirect_entry);
    keep(0,paragraphs);
    return 0;
}
