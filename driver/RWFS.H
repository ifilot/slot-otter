/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef RWFS_H
#define RWFS_H
#include "RWSD.H"
#define E_EXISTS 80
#define E_FULL 39
#define E_NOTEMPTY 5
typedef struct {
    /* lba/offset is the containing directory slot; parent is its directory.
     * first/size cache file metadata and are published before successful
     * completion; failed mutations may leave this cache ahead of disk.
     * last is an append aid, recomputed after another handle changes size. */
    U32 first, last, size, lba, parent;
    U16 offset, time, date;
    U8 directory, attr;
} RwFile;
extern U32 rw_start, rw_end, rw_fatsz, rw_allocated, rw_freed;
/* Operations return 0 or -1 with fs_error. rw_fat returns zero for both a
 * free entry and failure: clear/check fs_error when traversing a chain.
 * Paths and names use DOS short aliases; this module does not create LFNs. */
int rw_mount(void);
/* Invalidate disarms without committing. Flush verifies mirrors and marks
 * the volume clean; callers must explicitly flush before safe removal. */
void rw_invalidate(void);
int rw_begin(void);
int rw_flush(void);
int rw_lookup(const char *path, RwFile *file);
int rw_refresh(RwFile *file);
int rw_mkdir(U32 parent, const char *name, RwFile *file);
int rw_create(U32 parent, const char *name, RwFile *file);
int rw_read(const RwFile *file, U32 pos, U8 FAR *data, U16 count, U16 *done);
/* A null append buffer supplies zeroes (gap/extension initialization). */
int rw_append(RwFile *file, const U8 FAR *data, U16 count);
int rw_overwrite(RwFile *file, U32 pos, const U8 FAR *data, U16 count);
int rw_truncate(RwFile *file, U32 size);
/* done reports completed bytes; count==0 resizes the file to pos. */
int rw_write(RwFile *file, U32 pos, const U8 FAR *data, U16 count, U16 *done);
int rw_resize(RwFile *file, U32 size);
int rw_delete(RwFile *file);
int rw_rmdir(RwFile *file);
int rw_metadata(RwFile *file, U8 attr, U16 time, U16 date);
int rw_rename(RwFile *file, const char *destination);
int rw_free_space(U32 *count);
U32 rw_fat(U32 cluster);
#endif
