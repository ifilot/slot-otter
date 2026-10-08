/* SPDX-License-Identifier: GPL-3.0-or-later
 * Streaming FAT16/FAT32 reader: no heap, DOS calls, writes, or directory-sized arrays.
 */
#include "OTTER.H"
#include <string.h>

Volume volume;
U8 fs_spc_shift, fs_required;
U16 fs_error;
/* Keep payload separate: copying a new file sector must not evict metadata.
 * FIFO replacement uses power-of-two masks, without division on an 8088. */
typedef struct { U32 lba; U8 bytes[512]; } CachedSector;
static U8 data_buffer[512];
static CachedSector fat_cache[4], directory_cache[2];
static U8 fat_next, directory_next;
static U8 *fat_buffer;
#ifdef HOST_TEST
void fs_copy(U8 *dest,const U8 *src,U16 count) { memcpy(dest,src,count); }
#endif
static U32 data_lba = 0xffffffffUL;

U16 get16(const U8 FAR *p) { return (U16)p[0] | ((U16)p[1] << 8); }
U32 get32(const U8 FAR *p) {
    return (U32)get16(p) | ((U32)get16(p + 2) << 16);
}
void put16(U8 FAR *p, U16 v) { p[0] = (U8)v; p[1] = (U8)(v >> 8); }
void put32(U8 FAR *p, U32 v) { put16(p, (U16)v); put16(p+2, (U16)(v>>16)); }
void fs_invalidate(void) {
    unsigned i;
    data_lba=0xffffffffUL;
    for (i=0;i<4;++i) fat_cache[i].lba=0xffffffffUL;
    for (i=0;i<2;++i) directory_cache[i].lba=0xffffffffUL;
    fat_next=directory_next=0;
}
/* Stores invalidate matching sectors before attempting the write. Mutation
 * proofs, remounts and media changes still discard all cached evidence. */
void fs_invalidate_sector(U32 lba) {
    unsigned i;
    if (data_lba==lba) data_lba=0xffffffffUL;
    for (i=0;i<4;++i)
        if (fat_cache[i].lba==lba) fat_cache[i].lba=0xffffffffUL;
    for (i=0;i<2;++i)
        if (directory_cache[i].lba==lba) directory_cache[i].lba=0xffffffffUL;
}

static int fail(U16 error) { fs_error = error; return -1; }
static U8 *cached_sector(U32 lba,CachedSector *cache,U8 mask,U8 *next) {
    unsigned i;
    int result;
    CachedSector *slot;
    for (i=0;i<=mask;++i)
        if (cache[i].lba==lba) return cache[i].bytes;
    slot=cache+*next; *next=(U8)((*next+1)&mask);
    /* Failed receives must never leave a valid cache tag or partial hit. */
    slot->lba=0xffffffffUL;
    result=sd_read(lba,slot->bytes);
    if (result) { (void)fail(result>0?(U16)result:E_READ); return 0; }
    slot->lba=lba;
    return slot->bytes;
}
/* Directory refreshes may hit RAM, but still authenticate the mounted card.
 * Mutation preflight uses fresh sd_read calls rather than this helper. */
int fs_read_metadata(U32 lba,U8 *buffer) {
    U8 *p;
    if (sd_check_media()) return fail(E_NOTREADY);
    p=cached_sector(lba,directory_cache,1,&directory_next);
    if (!p) return -1;
    memcpy(buffer,p,512);
    return 0;
}
static int sector(U32 lba, int fat) {
    int result;
    if (fat) {
        fat_buffer=cached_sector(lba,fat_cache,3,&fat_next);
        return fat_buffer?0:-1;
    }
    if (data_lba==lba) return 0;
    data_lba=0xffffffffUL;
    result=sd_read(lba,data_buffer);
    if (result) return fail(result>0?(U16)result:E_READ);
    data_lba=lba;
    return 0;
}
static int valid_cluster(U32 c) { return c >= 2 && c - 2 < volume.clusters; }
static U32 cluster_lba(U32 c) { return volume.data + ((c-2)<<fs_spc_shift); }
/* Keep EOF/bad/reserved values in the existing FAT32-shaped internal range.
 * The on-disk entry remains exactly two bytes for FAT16. */
U32 fs_fat_sector(U32 c) {
    /* Constant shifts let an 8088 compiler avoid a variable long-shift helper. */
    if (volume.fat_bits==16) return c>>8;
    return c>>7;
}
U16 fs_fat_offset(U32 c) {
    return volume.fat_bits==16?(U16)(c&255)*2:(U16)(c&127)*4;
}
U32 fs_fat_value(const U8 *p,U32 c) {
    U16 value;
    if (volume.fat_bits!=16) return get32(p+fs_fat_offset(c))&0x0fffffffUL;
    value=get16(p+fs_fat_offset(c));
    return value>=0xfff0U?0x0fff0000UL|value:(U32)value;
}
U32 fs_dir_lba(U32 c,U16 slot) {
    return (volume.fat_bits==16 && c==ROOT16?volume.root_lba:cluster_lba(c))+slot/16;
}
U32 fs_fat_entry(U32 c) {
    if (!valid_cluster(c)) { (void)fail(E_INVALID); return 0; }
    if (sector(volume.fat + fs_fat_sector(c), 1)) return 0;
    return fs_fat_value(fat_buffer,c);
}
static int next_cluster(U32 c, U32 *next) {
    fs_error=0; *next=fs_fat_entry(c);
    if (fs_error) return -1;
    if (*next >= 0x0ffffff8UL) return 1;
    if (!valid_cluster(*next)) return fail(E_INVALID);
    return 0;
}

int fs_mount(void) {
    U32 start, limit, total, fatsz, reserved, overhead, roots;
    U16 flags, entries;
    U8 nfats, active, i, found;
    fs_error = 0;
    fs_invalidate();
    memset(&volume, 0, sizeof(volume));
    if (sector(0, 0)) return -1;
    if (get16(data_buffer+510) != 0xaa55) return fail(E_INVALID);
    start = 0; limit = 0; found = 0;
    /* BPB geometry identifies a superfloppy. Otherwise use the first
     * supported primary MBR partition; extended partitions/GPT are excluded. */
    if (get16(data_buffer+11) != 512 || data_buffer[16] == 0) {
        for (i=0; i<4; ++i) {
            U8 *p;
            p = data_buffer + 446 + (U16)i*16;
            if (p[4]==4 || p[4]==6 || p[4]==14 || p[4]==20 || p[4]==22 ||
                p[4]==30 || p[4]==11 || p[4]==12 || p[4]==27 || p[4]==28) {
                start = get32(p+8); limit = get32(p+12); found = 1; break;
            }
        }
        if (!found || !start || !limit || start > 0xffffffffUL-limit)
            return fail(E_INVALID);
        if (sector(start, 0)) return -1;
    }
    if (get16(data_buffer+510)!=0xaa55 || get16(data_buffer+11)!=512)
        return fail(E_INVALID);
    volume.spc = data_buffer[13];
    nfats=data_buffer[16]; reserved=get16(data_buffer+14);
    entries=get16(data_buffer+17); fatsz=get16(data_buffer+22);
    total=get16(data_buffer+19);
    if (!total) total=get32(data_buffer+32);
    active=0;
    if (!fatsz) {
        if (entries || get16(data_buffer+42)) return fail(E_INVALID);
        fatsz=get32(data_buffer+36); flags=get16(data_buffer+40);
        active=(flags&0x80)?(U8)(flags&15):0;
    }
    if (!volume.spc || volume.spc>128 || (volume.spc&(volume.spc-1)) ||
        !reserved || !nfats || active>=nfats || !fatsz || !total ||
        (limit && total>limit) || start>0xffffffffUL-total ||
        reserved>=total || fatsz>(total-reserved)/nfats)
        return fail(E_INVALID);
    roots=((U32)entries+15)/16;
    overhead=reserved+fatsz*nfats;
    if (roots>=total-overhead) return fail(E_INVALID);
    overhead+=roots;
    /* Type is determined by cluster count, never the printable FAT label. */
    fs_spc_shift=0;
    while ((1U<<fs_spc_shift)<volume.spc) ++fs_spc_shift;
    volume.clusters=(total-overhead)>>fs_spc_shift;
    volume.fat_bits=volume.clusters<65525UL?16:32;
    if (volume.clusters<4085UL || volume.clusters>0x0fffffeeUL ||
        (fs_required && fs_required!=volume.fat_bits)) return fail(E_INVALID);
    if (volume.fat_bits==16) {
        /* Avoid data cluster numbers colliding with reserved FAT16 markers. */
        if (!entries || (entries&15) || !get16(data_buffer+22) ||
            volume.clusters>65518UL || fatsz<(volume.clusters+2+255)/256)
            return fail(E_INVALID);
        volume.root=ROOT16; volume.root_entries=entries;
        volume.root_lba=start+reserved+fatsz*nfats;
    } else {
        if (entries || get16(data_buffer+22) ||
            fatsz<(volume.clusters+2+127)/128) return fail(E_INVALID);
        volume.root=get32(data_buffer+44)&0x0fffffffUL;
        if (!valid_cluster(volume.root)) return fail(E_INVALID);
    }
    volume.start=start; volume.total=total; volume.fat_sectors=fatsz;
    volume.fat=start+reserved+fatsz*active;
    volume.data=start+overhead;
    return 0;
}

U32 fs_entry_cluster(const U8 *e) {
    if (volume.fat_bits==16) return get16(e+26);
    return (((U32)get16(e+20) << 16) | get16(e+26)) & 0x0fffffffUL;
}
/* 0 = entry, 1 = end, -1 = error. Deleted and LFN entries are skipped. */
int fs_next(DirCursor *cursor, U8 entry[32]) {
    U16 slots;
    U32 next;
    U8 *p;
    int result;
    slots = (U16)volume.spc*16;
    for (;;) {
        if (!cursor->cluster) return 1;
        if (volume.fat_bits==16 && cursor->cluster==ROOT16) {
            if (cursor->slot>=volume.root_entries) { cursor->cluster=0; return 1; }
        } else {
            if (!valid_cluster(cursor->cluster)) return fail(E_INVALID);
            if (cursor->slot >= slots) {
                if (cursor->hops == 65535U || (U32)cursor->hops >= volume.clusters)
                    return fail(E_INVALID);
                ++cursor->hops;
                result = next_cluster(cursor->cluster, &next);
                if (result < 0) return -1;
                if (result == 1) { cursor->cluster = 0; return 1; }
                cursor->cluster = next; cursor->slot = 0;
            }
        }
        p=cached_sector(fs_dir_lba(cursor->cluster,cursor->slot),
                        directory_cache,1,&directory_next);
        if (!p) return -1;
        memcpy(entry,p+(cursor->slot%16)*32,32);
        ++cursor->slot;
        if (!entry[0]) { cursor->cluster = 0; return 1; }
        if (entry[0] == 0xe5 || entry[11] == 0x0f) continue;
        if (entry[0] == 0x05) entry[0] = 0xe5;
        return 0;
    }
}

static U8 upper(U8 c) { return c >= 'a' && c <= 'z' ? c-32 : c; }
int fs_pattern(const char *name, U8 pattern[11], int wild) {
    U16 pos, end;
    U8 c;
    memset(pattern, ' ', 11);
    if (!strcmp(name, ".") || !strcmp(name, "..")) {
        pattern[0]='.'; if (name[1]) pattern[1]='.'; return 0;
    }
    pos = 0; end = 8;
    while ((c = (U8)*name++) != 0) {
        if (c == '.') {
            if (end == 11) return fail(E_PATH);
            pos=8; end=11; continue;
        }
        if (c == '*' && wild) {
            while (pos < end) pattern[pos++] = '?';
            while (*name && *name != '.') ++name;
            continue;
        }
        if (pos >= end || c <= 32 || strchr("\"/\\[]:;=,+<>|", c) ||
            ((!wild) && (c=='*' || c=='?'))) return fail(E_PATH);
        pattern[pos++] = upper(c);
    }
    if (pattern[0]==' ') return fail(E_PATH);
    return 0;
}

static int child(U32 parent, const char *name, U8 entry[32]) {
    DirCursor cursor;
    U8 pattern[11];
    int result;
    if (fs_pattern(name, pattern, 0)) return -1;
    cursor.cluster=parent; cursor.slot=cursor.hops=0;
    while ((result=fs_next(&cursor, entry))==0) {
        if (!(entry[11] & 8) && !memcmp(entry, pattern, 11)) return 0;
    }
    if (result < 0) return -1;
    return fail(E_NOTFOUND);
}

int fs_parent(const char *path, U32 *cluster, char leaf[13]) {
    char component[13];
    U8 entry[32];
    U16 n;
    const char *p;
    *cluster = volume.root;
    p = path;
    if (p[0] && p[1]==':') p+=2;
    while (*p=='\\') ++p;
    if (!*p) { leaf[0]=0; return 0; }
    for (;;) {
        n=0;
        while (*p && *p!='\\') {
            if (n==12) return fail(E_PATH);
            component[n++]=*p++;
        }
        component[n]=0;
        if (!*p) { strcpy(leaf, component); return 0; }
        while (*p=='\\') ++p;
        if (!strcmp(component, ".")) continue;
        if (!strcmp(component, "..") && *cluster==volume.root) continue;
        if (child(*cluster, component, entry)) {
            if (fs_error==E_NOTFOUND) fs_error=E_PATH;
            return -1;
        }
        if (!(entry[11]&16)) return fail(E_PATH);
        *cluster=fs_entry_cluster(entry);
        if (!*cluster) *cluster=volume.root;
        if (*cluster!=volume.root && !valid_cluster(*cluster)) return fail(E_INVALID);
        if (!*p) { leaf[0]=0; return 0; }
    }
}
int fs_lookup(const char *path, U8 entry[32]) {
    U32 parent;
    char leaf[13];
    if (fs_parent(path, &parent, leaf)) return -1;
    if (!leaf[0] || !strcmp(leaf, ".") ||
        (!strcmp(leaf, "..") && parent==volume.root)) {
        memset(entry, 0, 32); memset(entry, ' ', 11);
        entry[11]=16; put16(entry+20, (U16)(parent>>16));
        put16(entry+26, (U16)parent); return 0;
    }
    return child(parent, leaf, entry);
}

int fs_read(FileCursor *cursor, U32 position, U8 FAR *buffer,
            U16 count, U16 *done) {
    U32 wanted, next, lba;
    U16 offset, chunk;
    int result;
    *done = 0;
    wanted = position>>(9+fs_spc_shift);
    if (!valid_cluster(cursor->first) || wanted >= volume.clusters)
        return fail(E_INVALID);
    if (!valid_cluster(cursor->cluster) || wanted < cursor->index) {
        cursor->cluster=cursor->first; cursor->index=0;
    }
    while (cursor->index < wanted) {
        result=next_cluster(cursor->cluster, &next);
        if (result) return result < 0 ? -1 : fail(E_INVALID);
        cursor->cluster=next; ++cursor->index;
    }
    while (count) {
        lba=cluster_lba(cursor->cluster)+((position>>9)&(volume.spc-1U));
        offset=(U16)(position & 511);
        chunk=512-offset; if (chunk > count) chunk=count;
        if (sector(lba, 0)) return -1;
#ifndef HOST_TEST
        /* Normalize before every chunk, so a DOS buffer may cross 64 KiB. */
        buffer=(U8 far *)MK_FP(FP_SEG(buffer)+(FP_OFF(buffer)>>4), FP_OFF(buffer)&15);
#endif
        fs_copy(buffer,data_buffer+offset,chunk);
        buffer+=chunk; position+=chunk; *done+=chunk; count-=chunk;
        if (count && !(position&(((U32)volume.spc<<9)-1UL))) {
            if (cursor->index+1 >= volume.clusters) return fail(E_INVALID);
            result=next_cluster(cursor->cluster, &next);
            if (result) return result < 0 ? -1 : fail(E_INVALID);
            cursor->cluster=next; ++cursor->index;
        }
    }
    return 0;
}
