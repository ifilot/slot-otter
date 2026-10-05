/* SPDX-License-Identifier: GPL-3.0-or-later
 * Streaming FAT32 reader: no heap, DOS calls, writes, or directory-sized arrays.
 */
#include "OTTER.H"
#include <string.h>

Volume volume;
U16 fs_error;
static U8 data_buffer[512], fat_buffer[512];
static U32 data_lba = 0xffffffffUL, fat_lba = 0xffffffffUL;

U16 get16(const U8 FAR *p) { return (U16)p[0] | ((U16)p[1] << 8); }
U32 get32(const U8 FAR *p) {
    return (U32)get16(p) | ((U32)get16(p + 2) << 16);
}
void put16(U8 FAR *p, U16 v) { p[0] = (U8)v; p[1] = (U8)(v >> 8); }
void put32(U8 FAR *p, U32 v) { put16(p, (U16)v); put16(p+2, (U16)(v>>16)); }
void fs_invalidate(void) { data_lba = fat_lba = 0xffffffffUL; }

static int fail(U16 error) { fs_error = error; return -1; }
static int sector(U32 lba, int fat) {
    int result;
    U32 *tag;
    U8 *buffer;
    tag = fat ? &fat_lba : &data_lba;
    buffer = fat ? fat_buffer : data_buffer;
    if (*tag == lba) return 0;
    *tag = 0xffffffffUL;
    result=sd_read(lba, buffer);
    if (result) return fail(result>0 ? (U16)result : E_READ);
    *tag = lba;
    return 0;
}
static int valid_cluster(U32 c) { return c >= 2 && c - 2 < volume.clusters; }
static U32 cluster_lba(U32 c) { return volume.data + (c-2)*volume.spc; }
static int next_cluster(U32 c, U32 *next) {
    if (!valid_cluster(c)) return fail(E_INVALID);
    if (sector(volume.fat + (c >> 7), 1)) return -1;
    *next = get32(fat_buffer + (U16)(c & 127)*4) & 0x0fffffffUL;
    if (*next >= 0x0ffffff8UL) return 1;
    if (!valid_cluster(*next)) return fail(E_INVALID);
    return 0;
}

int fs_mount(void) {
    U32 start, limit, total, fatsz, reserved, overhead;
    U16 flags;
    U8 nfats, active, i, found;
    fs_error = 0;
    fs_invalidate();
    memset(&volume, 0, sizeof(volume));
    if (sector(0, 0)) return -1;
    if (get16(data_buffer+510) != 0xaa55) return fail(E_INVALID);
    start = 0; limit = 0; found = 0;
    /* Accept a FAT32 superfloppy or the first FAT32 primary MBR partition. */
    if (get16(data_buffer+11) != 512 || data_buffer[16] == 0 ||
        get16(data_buffer+17) != 0 || get16(data_buffer+22) != 0) {
        for (i=0; i<4; ++i) {
            U8 *p;
            p = data_buffer + 446 + (U16)i*16;
            if (p[4] == 0x0b || p[4] == 0x0c || p[4] == 0x1b || p[4] == 0x1c) {
                start = get32(p+8); limit = get32(p+12); found = 1; break;
            }
        }
        if (!found || !start || !limit || start > 0xffffffffUL-limit)
            return fail(E_INVALID);
        if (sector(start, 0)) return -1;
    }
    if (get16(data_buffer+510) != 0xaa55 || get16(data_buffer+11) != 512 ||
        get16(data_buffer+17) || get16(data_buffer+22) || get16(data_buffer+42))
        return fail(E_INVALID);
    volume.spc = data_buffer[13];
    nfats = data_buffer[16]; reserved = get16(data_buffer+14);
    fatsz = get32(data_buffer+36); total = get32(data_buffer+32);
    flags = get16(data_buffer+40);
    active = (flags & 0x80) ? (U8)(flags & 15) : 0;
    if (!volume.spc || volume.spc > 128 || (volume.spc & (volume.spc-1)) ||
        !reserved || !nfats || active >= nfats || !fatsz || !total ||
        (limit && total > limit) || start > 0xffffffffUL-total ||
        fatsz > (total-reserved)/nfats || reserved >= total)
        return fail(E_INVALID);
    overhead = reserved + fatsz*nfats;
    if (overhead >= total) return fail(E_INVALID);
    volume.clusters = (total-overhead)/volume.spc;
    if (volume.clusters < 65525UL || volume.clusters > 0x0fffffeeUL ||
        fatsz < (volume.clusters+2+127)/128) return fail(E_INVALID);
    volume.fat = start + reserved + fatsz*active;
    volume.data = start + overhead;
    volume.root = get32(data_buffer+44) & 0x0fffffffUL;
    if (!valid_cluster(volume.root)) return fail(E_INVALID);
    return 0;
}

U32 fs_entry_cluster(const U8 *e) {
    return (((U32)get16(e+20) << 16) | get16(e+26)) & 0x0fffffffUL;
}
/* 0 = entry, 1 = end, -1 = error. Deleted and LFN entries are skipped. */
int fs_next(DirCursor *cursor, U8 entry[32]) {
    U16 slots;
    U32 next;
    int result;
    slots = (U16)volume.spc*16;
    for (;;) {
        if (!cursor->cluster) return 1;
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
        if (sector(cluster_lba(cursor->cluster) + cursor->slot/16, 0)) return -1;
        memcpy(entry, data_buffer + (cursor->slot % 16)*32, 32);
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
        if (!valid_cluster(*cluster)) return fail(E_INVALID);
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
    U16 offset, chunk, i;
    int result;
    *done = 0;
    wanted = (position/512)/volume.spc;
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
        lba=cluster_lba(cursor->cluster)+(position/512)%volume.spc;
        offset=(U16)(position & 511);
        chunk=512-offset; if (chunk > count) chunk=count;
        if (sector(lba, 0)) return -1;
#ifndef HOST_TEST
        /* Normalize before every chunk, so a DOS buffer may cross 64 KiB. */
        buffer=(U8 far *)MK_FP(FP_SEG(buffer)+(FP_OFF(buffer)>>4), FP_OFF(buffer)&15);
#endif
        for (i=0; i<chunk; ++i) buffer[i]=data_buffer[offset+i];
        buffer+=chunk; position+=chunk; *done+=chunk; count-=chunk;
        if (count && (position/512)%volume.spc==0 && !(position&511)) {
            if (cursor->index+1 >= volume.clusters) return fail(E_INVALID);
            result=next_cluster(cursor->cluster, &next);
            if (result) return result < 0 ? -1 : fail(E_INVALID);
            cursor->cluster=next; ++cursor->index;
        }
    }
    return 0;
}
