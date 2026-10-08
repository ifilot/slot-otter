/* Restricted SFN FAT32 writer for a marked expendable test volume.
 * GPL-3.0-or-later. Data is initialized before links; directory size is
 * published after data. Not transactional: a failed metadata write latches
 * STOP; never auto-repair. */
#include "WRITE.H"
#include <string.h>
U32 wf_start, wf_end, wf_fatsz, wf_allocated, wf_freed;
static U8 block[512], other[512];
static U32 hint, owned[32];
static unsigned own_count, begun;
const char *wf_preflight = "not started";
int wf_allow_hints, wf_hint_mismatch;
static int fail(unsigned code) {
  wt_error = code;
  return -1;
}
static int valid(U32 c) { return c >= 2 && c - 2 < volume.clusters; }
static U32 address(U32 c) { return volume.data + (c - 2) * volume.spc; }
static int store(U32 lba, const U8 *p) {
  if (!begun || wt_poison)
    return fail(WT_POISON);
  if (lba < wf_start || lba >= wf_end || lba == wf_start || lba == wf_start + 6)
    return fail(WT_GUARD);
  if (wt_write(lba, p, 0)) {
    wt_poison = 1;
    return -1;
  }
  fs_invalidate();
  return 0;
}
U32 wf_fat(U32 c) {
  if (!valid(c)) {
    fail(WT_RANGE);
    return 0;
  }
  if (sd_read(volume.fat + (c >> 7), block))
    return 0;
  return get32(block + (unsigned)(c & 127) * 4) & 0x0fffffffUL;
}
static int setfat(U32 c, U32 value) {
  U32 lba = volume.fat + (c >> 7);
  unsigned offset = (unsigned)(c & 127) * 4;
  if (!valid(c))
    return fail(WT_RANGE);
  if (sd_read(lba, block) || sd_read(lba + wf_fatsz, other))
    return -1;
  if (memcmp(block, other, 512))
    return fail(WT_GUARD);
  put32(block + offset, (get32(block + offset) & 0xf0000000UL) | value);
  if (store(lba, block) || store(lba + wf_fatsz, block))
    return -1;
  return 0;
}
int wf_hint(U32 cluster) {
  if (!valid(cluster))
    return fail(WT_RANGE);
  hint = cluster;
  return 0;
}
static U32 allocate(void) {
  U32 c, i, value, tag = 0xffffffffUL, lba;
  unsigned s;
  c = hint;
  for (i = 0; i < volume.clusters; ++i) {
    lba = volume.fat + (c >> 7);
    if (lba != tag) {
      if (sd_read(lba, block))
        return 0;
      tag = lba;
    }
    value = get32(block + (unsigned)(c & 127) * 4) & 0x0fffffffUL;
    if (!value) {
      if (setfat(c, 0x0fffffffUL))
        return 0;
      memset(other, 0, 512);
      for (s = 0; s < volume.spc; ++s)
        if (store(address(c) + s, other))
          return 0;
      hint = c + 1;
      if (!valid(hint))
        hint = 2;
      ++wf_allocated;
      return c;
    }
    if (++c == volume.clusters + 2)
      c = 2;
  }
  fail(WT_SPACE);
  return 0;
}
static int chain_valid(U32 c) {
  U32 n, i, slow = c;
  if (!c)
    return 0;
  for (i = 0; i < volume.clusters; ++i) {
    if (!valid(c))
      return fail(WT_GUARD);
    wt_error = 0;
    n = wf_fat(c);
    if (wt_error)
      return -1;
    if (n >= 0x0ffffff8UL)
      return 0;
    c = n;
    if (i & 1) {
      wt_error = 0;
      slow = wf_fat(slow);
      if (wt_error)
        return -1;
    }
    if (c == slow)
      return fail(WT_GUARD);
  }
  return fail(WT_GUARD);
}
static int release_chain(U32 c) {
  U32 next, i, first = c;
  for (i = 0; c && i < volume.clusters; ++i) {
    wt_error = 0;
    next = wf_fat(c);
    if (wt_error || setfat(c, 0))
      return -1;
    ++wf_freed;
    c = next >= 0x0ffffff8UL ? 0 : next;
  }
  if (c)
    return fail(WT_GUARD);
  if (first)
    hint = first;
  return 0;
}
static int parent_owned(U32 c) {
  unsigned i;
  for (i = 0; i < own_count; ++i)
    if (owned[i] == c)
      return 1;
  return 0;
}
static int publish(WFile *f) {
  if (sd_read(f->lba, block))
    return -1;
  put16(block + f->offset + 20, (U16)(f->first >> 16));
  put16(block + f->offset + 26, (U16)f->first);
  put32(block + f->offset + 28, f->size);
  return store(f->lba, block);
}
static int valid_fsinfo(const U8 *p) {
  return get32(p) == 0x41615252UL && get32(p + 484) == 0x61417272UL &&
         get32(p + 508) == 0xaa550000UL;
}
int wf_prepare(void) {
  U8 e[32];
  FileCursor cursor;
  U16 done;
  U32 total, i;
  unsigned s;
  static const char tag[] = "OTTER WRITE TEST v1\r\n";
  wt_error = 0;
  begun = own_count = 0;
  wf_hint_mismatch = 0;
  wf_allocated = wf_freed = 0;
  wt_disarm();
  wf_preflight = "mount and MBR read";
  if (fs_mount() || sd_read(0, block))
    return wt_error ? -1 : fail(WT_GUARD);
  wf_preflight = "marked primary partition";
  if (block[450] != 0x0c || get32(block + 454) != 2048UL)
    return fail(WT_GUARD);
  wf_start = get32(block + 454);
  total = get32(block + 458);
  if (total > 0xffffffffUL - wf_start)
    return fail(WT_RANGE);
  wf_end = wf_start + total;
  wf_preflight = "partition capacity and boot read";
  if (wf_end - 1 > wt_last_lba)
    return fail(WT_GUARD);
  if (sd_read(wf_start, block))
    return -1;
  wf_fatsz = get32(block + 36);
  wf_preflight = "volume serial and required geometry";
  if (get32(block + 67) != 0x57545231UL || get16(block + 14) != 32 ||
      block[16] != 2 || get16(block + 40) != 0 || get16(block + 48) != 1 ||
      get16(block + 50) != 6 || get32(block + 32) != total ||
      volume.root != 2 || volume.clusters != 70000UL ||
      (volume.spc != 1 && volume.spc != 8))
    return fail(WT_GUARD);
  wf_preflight = "FAT clean and no-error flags";
  if (sd_read(volume.fat, block))
    return -1;
  if ((get32(block + 4) & 0x0c000000UL) != 0x0c000000UL)
    return fail(WT_GUARD);
  wf_preflight = "WRITE.TAG lookup and size";
  if (fs_lookup("WRITE.TAG", e))
    return wt_error ? -1 : fail(WT_GUARD);
  if (get32(e + 28) != sizeof(tag) - 1)
    return fail(WT_GUARD);
  cursor.first = fs_entry_cluster(e);
  cursor.cluster = cursor.first;
  cursor.index = 0;
  wf_preflight = "WRITE.TAG contents";
  if (fs_read(&cursor, 0, block, sizeof(tag) - 1, &done))
    return wt_error ? -1 : fail(WT_GUARD);
  if (done != sizeof(tag) - 1 || memcmp(block, tag, sizeof(tag) - 1))
    return fail(WT_GUARD);
  /* All mirrors and boot/FSInfo backups must agree before any write. */
  wf_preflight = "all FAT mirrors equal";
  for (i = 0; i < wf_fatsz; ++i) {
    if (sd_read(volume.fat + i, block) ||
        sd_read(volume.fat + wf_fatsz + i, other))
      return -1;
    if (memcmp(block, other, 512))
      return fail(WT_GUARD);
  }
  for (s = 0; s < 2; ++s) {
    wf_preflight = s ? "FSInfo primary read" : "boot primary read";
    if (sd_read(wf_start + s, block))
      return -1;
    wf_preflight = s ? "FSInfo backup read" : "boot backup read";
    if (sd_read(wf_start + s + 6, other))
      return -1;
    if (s) {
      wf_preflight = "FSInfo signatures";
      if (!valid_fsinfo(block) || !valid_fsinfo(other))
        return fail(WT_GUARD);
    }
    wf_preflight = s ? "FSInfo primary/backup byte equality" :
                       "boot primary/backup byte equality";
    if (memcmp(block, other, 512)) {
      if (!s) return fail(WT_GUARD);
      /* The only optional exception is the two cached allocation hints. */
      for (i = 0; i < 512; ++i)
        if ((i < 488 || i >= 496) && block[i] != other[i])
          return fail(WT_GUARD);
      wf_hint_mismatch = 1;
      if (!wf_allow_hints) return fail(WT_GUARD);
    }
  }
  hint = 2;
  wf_preflight = "passed";
  wt_error = 0;
  return 0;
}
static int mark_clean(int clean) {
  U32 flags;
  if (sd_read(volume.fat, block) || sd_read(volume.fat + wf_fatsz, other))
    return -1;
  if (memcmp(block, other, 512))
    return fail(WT_GUARD);
  flags = get32(block + 4);
  if (clean)
    flags |= 0x08000000UL;
  else
    flags &= ~0x08000000UL;
  put32(block + 4, flags);
  return store(volume.fat, block) || store(volume.fat + wf_fatsz, block) ? -1
                                                                         : 0;
}
int wf_finish(void) {
  U32 i;
  for (i = 0; i < wf_fatsz; ++i) {
    if (sd_read(volume.fat + i, block) ||
        sd_read(volume.fat + wf_fatsz + i, other))
      return -1;
    if (memcmp(block, other, 512))
      return fail(WT_GUARD);
  }
  return mark_clean(1);
}
int wf_begin(void) {
  if (wt_arm(wf_start + 1, wf_end))
    return -1;
  begun = 1;
  if (sd_read(wf_start + 1, block))
    return -1;
  put32(block + 488, 0xffffffffUL);
  put32(block + 492, 0xffffffffUL);
  if (store(wf_start + 1, block) || store(wf_start + 7, block))
    return -1;
  return mark_clean(0);
}
static int create(U32 parent, const char *name, WFile *f, int directory) {
  U8 pattern[11], entry[32];
  U32 c, next, i, free_lba = 0;
  unsigned sector, offset, free_offset = 0;
  int end = 0;
  if (!begun || wt_poison)
    return fail(WT_POISON);
  if (!parent_owned(parent) &&
      !(parent == volume.root && directory && !strcmp(name, "WTEST")))
    return fail(WT_GUARD);
  if (directory && own_count == 32)
    return fail(WT_SPACE);
  if (fs_pattern(name, pattern, 0) || !strcmp(name, ".") || !strcmp(name, ".."))
    return fail(WT_GUARD);
  c = parent;
  for (i = 0; i < volume.clusters; ++i) {
    if (!valid(c))
      return fail(WT_GUARD);
    for (sector = 0; sector < volume.spc && !end; ++sector) {
      if (sd_read(address(c) + sector, block))
        return -1;
      for (offset = 0; offset < 512; offset += 32) {
        if (block[offset] == 0 || block[offset] == 0xe5) {
          if (!free_lba) {
            free_lba = address(c) + sector;
            free_offset = offset;
          }
          if (!block[offset]) {
            end = 1;
            break;
          }
        } else if (!memcmp(block + offset, pattern, 11))
          return fail(WT_EXISTS);
      }
    }
    if (end)
      break;
    wt_error = 0;
    next = wf_fat(c);
    if (wt_error)
      return -1;
    if (next >= 0x0ffffff8UL) {
      if (!free_lba) {
        next = allocate();
        if (!next || setfat(c, next))
          return -1;
        free_lba = address(next);
        free_offset = 0;
      }
      break;
    }
    c = next;
  }
  if (!free_lba || i == volume.clusters)
    return fail(WT_GUARD);
  memset(f, 0, sizeof(*f));
  f->lba = free_lba;
  f->offset = free_offset;
  f->directory = (U8)directory;
  if (directory) {
    f->first = f->last = allocate();
    if (!f->first)
      return -1;
    memset(other, 0, 512);
    memset(other, ' ', 11);
    other[0] = '.';
    other[11] = 16;
    put16(other + 20, (U16)(f->first >> 16));
    put16(other + 26, (U16)f->first);
    memset(other + 32, ' ', 11);
    other[32] = '.';
    other[33] = '.';
    other[43] = 16;
    next = parent == volume.root ? 0 : parent;
    put16(other + 52, (U16)(next >> 16));
    put16(other + 58, (U16)next);
    if (store(address(f->first), other))
      return -1;
  }
  memset(entry, 0, 32);
  memcpy(entry, pattern, 11);
  entry[11] = (U8)(directory ? 16 : 32);
  put16(entry + 22, 0x6000);
  put16(entry + 24, 0x5821);
  put16(entry + 20, (U16)(f->first >> 16));
  put16(entry + 26, (U16)f->first);
  if (sd_read(free_lba, block))
    return -1;
  memcpy(block + free_offset, entry, 32);
  if (store(free_lba, block))
    return -1;
  if (directory)
    owned[own_count++] = f->first;
  wt_error = 0;
  return 0;
}
int wf_mkdir(U32 p, const char *n, WFile *f) { return create(p, n, f, 1); }
int wf_create(U32 p, const char *n, WFile *f) { return create(p, n, f, 0); }
static U32 locate(WFile *f, U32 pos) {
  U32 c = f->first, i, n, index = pos / ((U32)volume.spc * 512);
  for (i = 0; i < index; ++i) {
    wt_error = 0;
    n = wf_fat(c);
    if (wt_error || !valid(n)) {
      fail(WT_GUARD);
      return 0;
    }
    c = n;
  }
  if (!valid(c)) {
    fail(WT_GUARD);
    return 0;
  }
  return c;
}
int wf_overwrite(WFile *f, U32 pos, const U8 *data, unsigned count) {
  U32 c, lba;
  unsigned offset, n;
  if (f->directory || pos > f->size || count > f->size - pos)
    return fail(WT_RANGE);
  while (count) {
    c = locate(f, pos);
    if (!c)
      return -1;
    lba = address(c) + (pos / 512) % volume.spc;
    offset = (unsigned)(pos % 512);
    n = 512 - offset;
    if (n > count)
      n = count;
    if (sd_read(lba, block))
      return -1;
    memcpy(block + offset, data, n);
    if (store(lba, block))
      return -1;
    pos += n;
    data += n;
    count -= n;
  }
  wt_error = 0;
  return 0;
}
int wf_append(WFile *f, const U8 *data, unsigned count) {
  U32 c, lba;
  unsigned offset, n;
  U32 old_size = f->size;
  if (f->directory || f->size > 0xffffffffUL - count)
    return fail(WT_RANGE);
  while (count) {
    if (!(f->size % ((U32)volume.spc * 512))) {
      c = allocate();
      if (!c)
        return -1;
      if (f->last && setfat(f->last, c))
        return -1;
      if (!f->first)
        f->first = c;
      f->last = c;
    }
    lba = address(f->last) + (f->size / 512) % volume.spc;
    offset = (unsigned)(f->size % 512);
    n = 512 - offset;
    if (n > count)
      n = count;
    if (sd_read(lba, block))
      return -1;
    memcpy(block + offset, data, n);
    if (store(lba, block))
      return -1;
    f->size += n;
    data += n;
    count -= n;
  }
  if (f->size != old_size && publish(f))
    return -1;
  wt_error = 0;
  return 0;
}
int wf_truncate(WFile *f, U32 size) {
  U32 c, next = 0;
  if (f->directory || size > f->size)
    return fail(WT_RANGE);
  if (chain_valid(f->first))
    return -1;
  if (size == f->size)
    return 0;
  c = size ? locate(f, size - 1) : 0;
  if (size && !c)
    return -1;
  if (c) {
    wt_error = 0;
    next = wf_fat(c);
    if (wt_error)
      return -1;
    if (next >= 0x0ffffff8UL)
      next = 0;
  } else
    next = f->first;
  f->size = size;
  f->last = c;
  if (!size)
    f->first = 0;
  if (publish(f))
    return -1;
  if (c && setfat(c, 0x0fffffffUL))
    return -1;
  if (release_chain(next))
    return -1;
  wt_error = 0;
  return 0;
}
int wf_delete(WFile *f) {
  if (f->directory)
    return fail(WT_GUARD);
  if (chain_valid(f->first) || sd_read(f->lba, block))
    return -1;
  block[f->offset] = 0xe5;
  if (store(f->lba, block) || release_chain(f->first))
    return -1;
  memset(f, 0, sizeof(*f));
  wt_error = 0;
  return 0;
}
int wf_rmdir(WFile *f) {
  DirCursor cursor;
  U8 entry[32];
  int result;
  unsigned i;
  if (!f->directory || !parent_owned(f->first))
    return fail(WT_GUARD);
  cursor.cluster = f->first;
  cursor.slot = cursor.hops = 0;
  fs_invalidate();
  while ((result = fs_next(&cursor, entry)) == 0)
    if (entry[0] != '.')
      return fail(WT_NOTEMPTY);
  if (result < 0)
    return fail(WT_GUARD);
  for (i = 0; i < own_count; ++i)
    if (owned[i] == f->first)
      owned[i] = 0;
  f->directory = 0;
  return wf_delete(f);
}

/* File-level size clamp around the independently tested raw FAT reader. */
int wf_read(const WFile *file, U32 pos, U8 *data, U16 count, U16 *done) {
  FileCursor cursor;
  *done = 0;
  if (file->directory)
    return fail(WT_RANGE);
  if (pos >= file->size || !count)
    return 0;
  if (file->size - pos < count)
    count = (U16)(file->size - pos);
  cursor.first = file->first;
  cursor.cluster = file->first;
  cursor.index = 0;
  return fs_read(&cursor, pos, data, count, done);
}
