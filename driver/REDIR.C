/* SPDX-License-Identifier: GPL-3.0-or-later
 * DOS 3.1-6.x INT 2F/11xx redirector. No INT 21 calls in resident code.
 * SDA/CDS/SFT offsets follow RBIL tables 01687,01690,01643,01641,01642.
 */
#include "OTTER.H"
#include <string.h>

Registers regs;
U8 resident_stack[2048];
U8 FAR *dos_sda;
U16 dos_name_offset, dos_attr_offset;
U16 dos_search_offset, dos_found_offset;
U8 drive_number, dos_major;
U8 FAR *drive_cds;
U8 media_online;
static U32 media_epoch=1;
#define MAX_OPEN 16
typedef struct { U8 FAR *sft; FileCursor cursor; } OpenFile;
static OpenFile files[MAX_OPEN];
#define MAX_SEARCH 32
typedef struct { DirCursor cursor; U32 serial, epoch; } Search;
static Search searches[MAX_SEARCH];
static U16 next_search;
static U32 search_serial;
/* Lookup consumes the path before writing its result; traversal uses its own
 * local entry. ENTRY's busy guard prevents another dispatch using this scratch. */
static union { char path[PATH_MAX]; U8 entry[32]; } scratch;
#define path (scratch.path)
#define entry (scratch.entry)

static U8 FAR *far_at(U16 seg, U16 off) {
#ifdef HOST_TEST
    return test_far_at(seg,off);
#else
    return (U8 far *)MK_FP(seg,off);
#endif
}
static U8 FAR *pointer_at(U8 FAR *p) { return far_at(get16(p+2), get16(p)); }
static int success(void) { regs.ax=0; regs.flags &= ~1; return 1; }
static int error(U16 code) { regs.ax=code; regs.flags |= 1; return 1; }
static U16 open_count(void) {
    U16 i, count=0;
    for (i=0;i<MAX_OPEN;++i) if (files[i].sft) ++count;
    return count;
}
static void offline(void) {
    media_online=0; ++media_epoch;
    fs_invalidate(); memset(&volume,0,sizeof(volume)); sd_release();
    if (drive_cds) {
        drive_cds[0]='A'+drive_number; drive_cds[1]=':';
        drive_cds[2]='\\'; drive_cds[3]=0;
    }
}
U16 media_unmount(void) {
    if (open_count()) return E_ACCESS;
    offline(); return 0;
}
U16 media_mount(void) {
    U16 result;
    if (open_count()) return E_ACCESS;
    offline();
    if (sd_init()) { sd_release(); return E_NOTREADY; }
    if (fs_mount()) { result=fs_error; offline(); return result; }
    media_online=1; return 0;
}
static int ready(void) {
    if (!media_online) return 0;
    if (sd_check_media()) { offline(); return 0; }
    return 1;
}
static int filesystem_error(void) {
    U16 code=fs_error;
    if (code==E_READ || code==E_NOTREADY) offline();
    return error(code);
}
static int get_path(void) {
    U8 FAR *p;
    U16 i;
    p=dos_sda+dos_name_offset;
    if (p[0] != 'A'+drive_number || p[1]!=':') return 0;
    for (i=0; i<PATH_MAX; ++i) {
        path[i]=p[i]; if (!p[i]) return 1;
    }
    path[0]=0; return -1;
}
static int our_sft(U8 FAR *sft) {
    return (get16(sft+5)&0x803f)==(0x8000|drive_number);
}
static int our_cds(U8 FAR *cds) {
    return cds[0]=='A'+drive_number && cds[1]==':' && (get16(cds+0x43)&0x8000);
}
static OpenFile *find_file(U8 FAR *sft) {
    U16 i;
    for (i=0; i<MAX_OPEN; ++i) if (files[i].sft==sft) return files+i;
    return 0;
}
static int open_file(U8 FAR *sft, U16 mode, int extended) {
    U16 i, action;
    U32 cluster;
    if ((mode&3)!=0) return error(E_ACCESS);
    if (extended) {
        action=dos_sda[0x2dd]; /* DOS also keeps internal flags in the next byte. */
        /* DOS COPY uses open-or-create (11h), even for a read-only source.
         * Permit its existing-file branch; lookup below never creates. */
        if (action!=1 && action!=0x11) return error(E_ACCESS);
    }
    if (fs_lookup(path, entry)) return filesystem_error();
    if (entry[11]&24) return error(E_ACCESS);
    cluster=fs_entry_cluster(entry);
    for (i=0; i<MAX_OPEN; ++i) if (!files[i].sft) break;
    if (i==MAX_OPEN) return error(E_HANDLES);
    files[i].sft=sft; files[i].cursor.first=cluster;
    files[i].cursor.cluster=cluster; files[i].cursor.index=0;
    /* Preserve reference count and DOS-owned sharing/PSP fields. */
    put16(sft+2, mode);
    sft[4]=entry[11]|1;
    put16(sft+5, 0xc000|drive_number|((mode&0x80)?0x1000:0));
    put32(sft+7, 0); put16(sft+11, 0);
    put16(sft+13, get16(entry+22)); put16(sft+15, get16(entry+24));
    put32(sft+17, get32(entry+28)); put32(sft+21, 0);
    put32(sft+25, 0); sft[29]=sft[30]=sft[31]=0;
    for (i=0; i<11; ++i) sft[32+i]=entry[i];
    if (extended) regs.cx=1;
    return success();
}
static int read_file(U8 FAR *sft) {
    OpenFile *file;
    U32 position, size;
    U16 count, done;
    int result;
    /* dispatch checks ready(); mounting refuses all open references, so an
     * old file cannot coexist with newly mounted media. */
    file=find_file(sft);
    if (!file) { regs.cx=0; return error(6); }
    position=get32(sft+21); size=get32(sft+17); count=regs.cx;
    if (position>=size || !count) { regs.cx=0; return success(); }
    if (size-position<count) count=(U16)(size-position);
    result=fs_read(&file->cursor, position, pointer_at(dos_sda+12), count, &done);
    put32(sft+21, position+done); regs.cx=done;
    return result ? filesystem_error() : success();
}

static void load_cursor(U8 FAR *dta, DirCursor *cursor) {
    *cursor=searches[get16(dta+13)].cursor;
}
static void save_cursor(U8 FAR *dta, DirCursor *cursor) {
    searches[get16(dta+13)].cursor=*cursor;
}
static int find_next(U8 FAR *dta) {
    DirCursor cursor;
    U16 i;
    U8 attr;
    int result, match;
    U16 slot=get16(dta+13);
    if (slot>=MAX_SEARCH || get16(dta+19)!=0x4f54 ||
        searches[slot].serial!=get32(dta+15) || searches[slot].epoch!=media_epoch)
        return error(E_NOMORE);
    load_cursor(dta, &cursor);
    while ((result=fs_next(&cursor, entry))==0) {
        attr=entry[11];
        if (attr&8) {
            if (!(dta[12]&8)) continue;
        } else {
            if (dta[12]==8 || (attr & 0x16 & ~dta[12])) continue;
        }
        match=1;
        for (i=0; i<11; ++i)
            if (dta[i+1]!='?' && dta[i+1]!=entry[i]) { match=0; break; }
        if (!match) continue;
        save_cursor(dta, &cursor);
        /* DOS expects a raw FAT directory entry at +21, not a public DTA. */
        for (i=0; i<32; ++i) dta[21+i]=entry[i];
        dta[32]|=1;               /* report files as read-only */
        for (i=0; i<21; ++i) dos_sda[dos_search_offset+i]=dta[i];
        for (i=0; i<32; ++i) dos_sda[dos_found_offset+i]=dta[21+i];
        return success();
    }
    save_cursor(dta, &cursor);
    return result<0 ? filesystem_error() : error(E_NOMORE);
}
static int find_first(U8 FAR *dta) {
    U32 parent;
    U8 pattern[11];
    U16 i;
    char leaf[13];
    DirCursor cursor;
    if (fs_parent(path, &parent, leaf)) return filesystem_error();
    if (!leaf[0] || fs_pattern(leaf, pattern, 1)) return error(E_PATH);
    dta[0]=0x80|drive_number;
    for (i=0; i<11; ++i) dta[i+1]=pattern[i];
    dta[12]=dos_sda[dos_attr_offset];
    cursor.cluster=parent; cursor.slot=cursor.hops=0;
    put16(dta+13,next_search); put32(dta+15,++search_serial);
    put16(dta+19,0x4f54);
    searches[next_search].serial=search_serial;
    searches[next_search].epoch=media_epoch;
    next_search=(next_search+1)%MAX_SEARCH;
    save_cursor(dta, &cursor);
    return find_next(dta);
}

int dispatch(void) {
    U8 fn;
    U8 FAR *sft, FAR *dta;
    U32 size, offset, position;
    int owned;
    OpenFile *file;
    if (regs.ax==0xd74f) {
        if (regs.bx==0x4f54 && regs.dx==0x524f) {
            if (regs.si==1 || regs.si==2) {
                U16 code=regs.si==1 ? media_unmount() : media_mount();
                return code ? error(code) : success();
            }
            return error(1);
        }
        (void)ready();
        regs.ax=0x4f54; regs.bx=0x524f; regs.cx=drive_number;
        regs.dx=media_online; regs.si=open_count(); regs.di=sd_port; regs.bp=2;
        regs.flags &= ~1;
        return 1;
    }
    if ((regs.ax&0xff00)!=0x1100) return 0;
    fn=(U8)regs.ax;
    sft=far_at(regs.es, regs.di); dta=pointer_at(dos_sda+12);
    if (fn==0) { regs.ax=0x11ff; regs.flags &= ~1; return 1; }
    if (fn==0x1c || fn==0x1a) {
        if (dta[0]!=(0x80|drive_number)) return 0;
        if (!ready()) return error(E_NOTREADY);
        return find_next(dta);
    }
    if (fn==6 || fn==7 || fn==8 || fn==9 || fn==0x0a ||
        fn==0x0b || fn==0x21 || fn==0x2d) {
        if (!our_sft(sft)) return 0;
        if (fn!=6 && fn!=7 && !ready()) {
            if (fn==8 || fn==9) regs.cx=0;
            return error(E_NOTREADY);
        }
        switch (fn) {
        case 6:
            if (get16(sft)) put16(sft, get16(sft)-1);
            if (!get16(sft)) { file=find_file(sft); if (file) file->sft=0; }
            return success();
        case 7: return success(); /* commit: no pending writes */
        case 8: return read_file(sft);
        case 9: regs.cx=0; return error(E_ACCESS);
        case 0x0a: return success(); /* immutable files: locks are harmless */
        case 0x21:
            size=get32(sft+17); offset=((U32)regs.cx<<16)|regs.dx;
            if (offset&0x80000000UL) {
                U32 magnitude;
                magnitude=~offset+1;
                if (magnitude>size) return error(1);
                position=size-magnitude;
            } else {
                if (offset>0xffffffffUL-size) return error(1);
                position=size+offset;
            }
            put32(sft+21, position); success();
            regs.ax=(U16)position; regs.dx=(U16)(position>>16); return 1;
        default: return error(E_ACCESS);
        }
    }
    if (fn==0x0c) {
        if (!our_cds(sft)) return 0;
        if (!ready()) return error(E_NOTREADY);
        success(); regs.ax=0xf800|volume.spc; regs.cx=512;
        regs.bx=volume.clusters>65535UL?65535U:(U16)volume.clusters;
        regs.dx=0; return 1;      /* no writable space on a read-only drive */
    }
    /* These calls are not associated with a filename or SFT. */
    if (fn==0x1d || fn==0x1e || fn==0x1f || fn==0x20 || fn==0x22 ||
        fn==0x23 || fn==0x24 || fn==0x25 || fn==0x26) return 0;
    if (fn!=1 && fn!=2 && fn!=3 && fn!=4 && fn!=5 && fn!=0x0e &&
        fn!=0x0f && fn!=0x11 && fn!=0x13 && fn!=0x16 && fn!=0x17 &&
        fn!=0x18 && fn!=0x19 && fn!=0x1b && fn!=0x2e) return 0;
    owned=get_path();
    if (!owned) return 0;
    if (owned<0) return error(E_PATH);
    if (!ready()) return error(E_NOTREADY);
    switch (fn) {
    case 5:
        if (fs_lookup(path, entry)) {
            if (fs_error==E_NOTFOUND) fs_error=E_PATH;
            return filesystem_error();
        }
        return (entry[11]&16) ? success() : error(E_PATH);
    case 0x0f:
        if (fs_lookup(path, entry)) return filesystem_error();
        success(); regs.ax=entry[11]|1;
        size=get32(entry+28); regs.bx=(U16)(size>>16); regs.di=(U16)size;
        regs.cx=get16(entry+22); regs.dx=get16(entry+24); return 1;
    case 0x16: return open_file(sft, regs.param, 0);
    case 0x19:
    case 0x1b: return find_first(dta);
    case 0x2e:
        if (dos_major<4) return error(1);
        return open_file(sft, get16(dos_sda+0x2e1), 1);
    default: return error(E_ACCESS); /* includes every pathname mutation */
    }
}
