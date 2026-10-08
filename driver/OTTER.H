/* Slot-otter DOS redirector and filesystem types. SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef OTTER_H
#define OTTER_H
#ifdef HOST_TEST
#include <stdint.h>
typedef uint8_t U8;
typedef uint16_t U16;
typedef uint32_t U32;
#define FAR
#else
#include <dos.h>
typedef unsigned char U8;
typedef unsigned int U16;
typedef unsigned long U32;
#define FAR far
#endif

#define E_NOTFOUND 2
#define E_PATH 3
#define E_HANDLES 4
#define E_ACCESS 5
#define E_INVALID 13
#define E_NOMORE 18
#define E_NOTREADY 21
#define E_READ 30
#define PATH_MAX 80

typedef struct {
    U32 fat, data, clusters, root;
    U8 spc;
    U32 start, total, fat_sectors, root_lba;
    U16 root_entries;
    U8 fat_bits;
} Volume;
#define ROOT16 0xffffffffUL
typedef struct { U32 cluster; U16 slot, hops; } DirCursor;
typedef struct { U32 first, cluster, index; } FileCursor;
extern Volume volume;
extern U8 fs_spc_shift;
/* Installation restriction: zero = automatic, otherwise 16 or 32. */
extern U8 fs_required;
extern U16 fs_error;
extern U16 sd_port;
int parse_port(const char *s, U16 *result);
void option_upper(char *s);
int sd_init(void);
int sd_check_media(void);
void sd_release(void);
int sd_read(U32 lba, U8 *buffer);
int fs_mount(void);
void fs_invalidate(void);
void fs_invalidate_sector(U32 lba);
/* Read-only metadata cache; callers use fresh reads for mutation proofs. */
int fs_read_metadata(U32 lba,U8 *buffer);
/* Raw cached FAT entry, including free/EOF; zero also requires fs_error check. */
U32 fs_fat_entry(U32 cluster);
U32 fs_fat_sector(U32 cluster);
U16 fs_fat_offset(U32 cluster);
U32 fs_fat_value(const U8 *sector,U32 cluster);
U32 fs_dir_lba(U32 cluster,U16 slot);
int fs_next(DirCursor *cursor, U8 entry[32]);
int fs_lookup(const char *path, U8 entry[32]);
int fs_parent(const char *path, U32 *cluster, char leaf[13]);
int fs_pattern(const char *name, U8 pattern[11], int wild);
U32 fs_entry_cluster(const U8 *entry);
int fs_read(FileCursor *cursor, U32 position, U8 FAR *buffer,
            U16 count, U16 *done);
/* Each far buffer is normalized; chunks must not wrap either offset. */
void fs_copy(U8 FAR *dest,const U8 FAR *src,U16 count);
U16 get16(const U8 FAR *p);
U32 get32(const U8 FAR *p);
void put16(U8 FAR *p, U16 v);
void put32(U8 FAR *p, U32 v);

/* Matches the saved 8086 stack in ENTRY.ASM exactly. */
typedef struct {
    U16 ax, bx, cx, dx, si, di, es, ds, bp, ip, cs, flags, param;
} Registers;
extern Registers regs;
extern U8 resident_stack[2048];
#ifndef HOST_TEST
extern void far redirect_entry(void);
void bridge_init(void interrupt far (*previous)(void));
#else
U8 *test_far_at(U16 seg, U16 off);
#endif
int dispatch(void);
extern U8 FAR *dos_sda;
extern U16 dos_name_offset, dos_attr_offset;
extern U16 dos_search_offset, dos_found_offset;
extern U8 drive_number, dos_major;
extern U8 FAR *drive_cds;
extern U8 media_online;
/* Unload descriptor: PSP, own vector offset/segment, previous offset/segment.
 * Saved CDS includes all bytes, even fields this redirector does not use. */
#ifdef RW_DRIVER
extern U16 unload_state[5];
extern U8 saved_cds[0x58];
#endif
U16 media_mount(void);
U16 media_unmount(void);
#endif
