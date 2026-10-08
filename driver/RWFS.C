/* Resident SFN FAT16/FAT32 writer, adapted from the independently tested writer.
 * GPL-3.0-or-later. Data is initialized before links; directory size is
 * published after data. Transport write failures, dirty-session read failures
 * and dirty-session FAT mirror mismatches poison the session. Ordinary input
 * validation errors need not do so. Verified sectors do not make a multi-sector
 * operation atomic; interrupted operations require external checking/repair. */
#include "RWFS.H"
#include <string.h>
U32 rw_start, rw_end, rw_fatsz, rw_allocated, rw_freed;
U8 rw_skip_fat_check;
/* Fixed scratch keeps the resident code heap-free and non-reentrant.
 * ENTRY's busy guard serializes dispatch. begun means mounted and armed;
 * dirty means mutations have begun, not that a sector awaits transmission. */
static U8 block[512];
/* This scratch is dead across a block[] store. An other[] store snapshots
 * before readback and restores it on success, including reset/retry paths. */
#define other sd_scratch
static U32 hint, first_fat, fsinfo_lba, backup_info, backup_boot;
static U8 fat_count, active_fat, mirrored;
static unsigned begun, dirty;
U32 rw_read_serial=1;
static void invalidate_reads(void) {
  /* Never recycle a serial: dormant handles must not inherit an old cursor.
   * After wrap, reads always start fresh for the rest of this installation. */
  if (rw_read_serial) ++rw_read_serial;
}
static int chain_valid(U32 c);
static int validate_file(RwFile *f);
static int erase_lfn(RwFile *f);
static int same_name(const U8 *raw,const U8 *pattern) {
  return (raw[0]==5?229:raw[0])==pattern[0] && !memcmp(raw+1,pattern+1,10);
}
static int fail(unsigned code) {
  fs_error = code;
  return -1;
}
static int inconsistent(void) {
  if (dirty) sd_diag.poisoned=1;
  return fail(E_INVALID);
}
static int read_sector(U32 lba,U8 *p) {
  int result=sd_read(lba,p);
  if (result && dirty) sd_diag.poisoned=1;
  return result?fail((U16)result):0;
}
static int valid(U32 c) { return c >= 2 && c - 2 < volume.clusters; }
static U32 address(U32 c) { return volume.data + ((c - 2)<<fs_spc_shift); }
/* The fixed FAT16 root is outside the cluster area. Never admit a FAT or
 * reserved sector as a writable directory slot. */
static int slot_valid(U32 lba,U16 offset) {
  if ((offset&31) || offset>480 || lba>=rw_end) return 0;
  if (lba>=volume.data) return 1;
  return volume.fat_bits==16 && lba>=volume.root_lba &&
         lba-volume.root_lba<(U32)volume.root_entries/16;
}
static int raw_store(U32 lba, const U8 *p) {
  int result;
  if (!begun || sd_diag.poisoned) return fail(E_NOTREADY);
  if (lba < rw_start || lba >= rw_end || lba == rw_start || lba == backup_boot ||
      (lba < first_fat && lba != fsinfo_lba && lba != backup_info))
    return fail(E_ACCESS);
  invalidate_reads();
  fs_invalidate_sector(lba);
  result=sd_write(lba,p);
  if (result) return fail((U16)result);
  return 0;
}
static int store(U32 lba, const U8 *p) {
  if (!dirty) return fail(E_INVALID);
  return raw_store(lba,p);
}
U32 rw_fat(U32 c) {
  if (!valid(c)) {
    fail(E_INVALID);
    return 0;
  }
  /* Reuse the reader's FAT buffer rather than receiving 512 bytes per link.
   * Identity remains checked even on hits; stores invalidate matching sectors. */
  fs_error=0;
  if (sd_check_media()) {
    if (dirty) sd_diag.poisoned=1;
    (void)fail(E_NOTREADY); return 0;
  }
  c=fs_fat_entry(c);
  if (fs_error && dirty) sd_diag.poisoned=1;
  return c;
}
int rw_lookup(const char *path, RwFile *f) {
  U32 parent;
  char leaf[13];
  U8 pattern[11], e[32];
  DirCursor cursor;
  int result;
  fs_error=0;
  if (fs_parent(path,&parent,leaf)) return -1;
  if (!leaf[0] || !strcmp(leaf,".") || (!strcmp(leaf,"..") && parent==volume.root)) {
    memset(f,0,sizeof(*f)); f->first=parent; f->parent=parent;
    f->directory=1; f->attr=16; return 0;
  }
  if (fs_pattern(leaf,pattern,0)) return -1;
  cursor.cluster=parent; cursor.slot=cursor.hops=0;
  while ((result=fs_next(&cursor,e))==0) {
    if ((e[11]&8) || memcmp(e,pattern,11)) continue;
    memset(f,0,sizeof(*f)); f->first=fs_entry_cluster(e); f->size=get32(e+28);
    f->lba=fs_dir_lba(cursor.cluster,(U16)(cursor.slot-1));
    f->offset=(U16)((cursor.slot-1)%16)*32; f->parent=parent;
    f->attr=e[11]; f->directory=(U8)((e[11]&16)!=0);
    f->time=get16(e+22); f->date=get16(e+24); return 0;
  }
  return result<0?-1:fail(E_NOTFOUND);
}
int rw_free_space(U32 *count) {
  U32 c,tag=0xffffffffUL,lba;
  *count=0;
  for (c=2;c<volume.clusters+2;++c) {
    lba=volume.fat+fs_fat_sector(c);
    if (lba!=tag) { if (read_sector(lba,block)) return -1; tag=lba; }
    if (!fs_fat_value(block,c)) ++*count;
  }
  return 0;
}
/* Open handles identify a directory slot, not a cached starting cluster.
 * Another permitted handle may allocate the first cluster or truncate it. */
int rw_refresh(RwFile *f) {
  U8 *e;
  if (!begun || sd_diag.poisoned) return fail(E_NOTREADY);
  if (!slot_valid(f->lba,f->offset))
    return fail(E_INVALID);
  if (fs_read_metadata(f->lba,block)) {
    if (dirty) sd_diag.poisoned=1;
    return -1;
  }
  e=block+f->offset;
  if (!e[0] || e[0]==229 || (e[11]&24)) return fail(E_INVALID);
  f->first=fs_entry_cluster(e); f->last=0; f->size=get32(e+28);
  f->attr=e[11]; f->time=get16(e+22); f->date=get16(e+24);
  fs_error=0; return 0;
}
int rw_metadata(RwFile *f,U8 attr,U16 time,U16 date) {
  if (!f->lba || (attr&0xd8)!=(f->attr&0x10)) return fail(E_ACCESS);
  if (validate_file(f)) return -1;
  if (rw_begin() || read_sector(f->lba,block)) return -1;
  block[f->offset+11]=attr;
  put16(block+f->offset+22,time); put16(block+f->offset+24,date);
  if (store(f->lba,block)) return -1;
  f->attr=attr; f->time=time; f->date=date; return 0;
}
/* block already contains this primary FAT sector. Compare every mirror
 * before changing it; the allocation scan can supply the same fresh read. */
static int setfat_loaded(U32 c, U32 value) {
  U32 lba=volume.fat+fs_fat_sector(c);
  unsigned offset=fs_fat_offset(c), i;
  if (!valid(c)) return fail(E_INVALID);
  if (mirrored) for (i=1;i<fat_count;++i) {
    if (read_sector(first_fat+(U32)i*rw_fatsz+fs_fat_sector(c),other)) return -1;
    if (memcmp(block,other,512)) return inconsistent();
  }
  if (volume.fat_bits==16) put16(block+offset,(U16)value);
  else put32(block+offset,(get32(block+offset)&0xf0000000UL)|value);
  if (store(lba,block)) return -1;
  if (mirrored) for (i=1;i<fat_count;++i)
    if (store(first_fat+(U32)i*rw_fatsz+fs_fat_sector(c),block)) return -1;
  return 0;
}
static int setfat(U32 c,U32 value) {
  if (!valid(c)) return fail(E_INVALID);
  if (read_sector(volume.fat+fs_fat_sector(c),block)) return -1;
  return setfat_loaded(c,value);
}
static U32 allocate(int clear) {
  /* Reserve as EOF. Directory clusters must be cleared before linking:
   * their entries are scanned without a byte-size limit. Regular files
   * instead initialize only bytes made visible by the published file size.
   * An interruption can leak this reservation; there is no journal. */
  U32 c, i, value, tag = 0xffffffffUL, lba;
  unsigned s;
  if (rw_begin()) return 0;
  c = hint;
  for (i = 0; i < volume.clusters; ++i) {
    lba = volume.fat + fs_fat_sector(c);
    if (lba != tag) {
      if (read_sector(lba, block))
        return 0;
      tag = lba;
    }
    value = fs_fat_value(block,c);
    if (!value) {
      if (setfat_loaded(c, 0x0fffffffUL))
        return 0;
      if (clear) {
        memset(other, 0, 512);
        for (s = 0; s < volume.spc; ++s)
          if (store(address(c) + s, other))
            return 0;
      }
      hint = c + 1;
      if (!valid(hint))
        hint = 2;
      ++rw_allocated;
      return c;
    }
    if (++c == volume.clusters + 2)
      c = 2;
  }
  fail(E_FULL);
  return 0;
}
/* Brent cycle detection visits each link once. Unlike a slow/fast pair, it
 * does not alternate between distant FAT sectors and evict the small cache.
 * The cluster count also establishes allocation length before mutation. */
static int chain_length(U32 c,U32 *count,U32 wanted,U32 *at) {
  U32 n, i, anchor=c, power=1, length=0;
  *count=0;
  if (at) *at=0;
  if (!c) return 0;
  /* Authenticate at both audit boundaries. Cache misses authenticate
   * again through sd_read; no write can use an unfinished proof. */
  if (sd_check_media()) {
    if (dirty) sd_diag.poisoned=1;
    return fail(E_NOTREADY);
  }
  for (i=0;i<volume.clusters;++i) {
    if (!valid(c)) return fail(E_INVALID);
    fs_error=0; n=fs_fat_entry(c);
    if (fs_error) { if (dirty) sd_diag.poisoned=1; return -1; }
    ++*count;
    /* Capture logical EOF without stopping the proof of surplus allocation. */
    if (at && *count==wanted) *at=c;
    if (n>=0x0ffffff8UL) {
      if (sd_check_media()) {
        if (dirty) sd_diag.poisoned=1;
        return fail(E_NOTREADY);
      }
      return 0;
    }
    ++length;
    if (n==anchor) return fail(E_INVALID);
    if (length==power) { anchor=n; power<<=1; length=0; }
    c=n;
  }
  return fail(E_INVALID);
}
static int chain_valid(U32 c) {
  U32 count;
  fs_invalidate();
  if (volume.fat_bits==16 && c==ROOT16) {
    if (sd_check_media()) {
      if (dirty) sd_diag.poisoned=1;
      return fail(E_NOTREADY);
    }
    return 0;
  }
  return chain_length(c,&count,0,0);
}
/* Verify both the directory location and every FAT link before mutation. */
static int validate_file(RwFile *f) {
  U32 count=0,needed;
  U8 *e;
  /* Begin each mutation with fresh FAT evidence. Cache only within this
   * validation/traversal; external changes never inherit a prior proof. */
  fs_invalidate();
  if (!begun || sd_diag.poisoned) return fail(E_NOTREADY);
  if (!slot_valid(f->lba,f->offset))
    return fail(E_INVALID);
  if (read_sector(f->lba,block)) return -1;
  e=block+f->offset;
  if (!e[0] || e[0]==229 || (e[11]&8) ||
      fs_entry_cluster(e)!=f->first || get32(e+28)!=f->size ||
      ((e[11]&16)!=0)!=f->directory) return fail(E_INVALID);
  needed=f->size?((f->size-1)>>(9+fs_spc_shift))+1:0;
  if (chain_length(f->first,&count,needed,&f->last)) return -1;
  if (count<needed || (f->directory && !count)) return fail(E_INVALID);
  return 0;
}
static int release_chain(U32 c) {
  U32 next, i, first = c;
  for (i = 0; c && i < volume.clusters; ++i) {
    fs_error = 0;
    next = rw_fat(c);
    if (fs_error || setfat(c, 0))
      return -1;
    ++rw_freed;
    c = next >= 0x0ffffff8UL ? 0 : next;
  }
  if (c)
    return fail(E_INVALID);
  if (first)
    hint = first;
  return 0;
}
static int publish(RwFile *f) {
  if (read_sector(f->lba, block))
    return -1;
  if (volume.fat_bits==32)
    put16(block + f->offset + 20, (U16)(f->first >> 16));
  put16(block + f->offset + 26, (U16)f->first);
  put32(block + f->offset + 28, f->size);
  block[f->offset+11]|=32; f->attr|=32;
  return store(f->lba, block);
}
/* Raw directory iteration retains LFN positions; fs_next deliberately skips
 * them. Constant memory, including when the sequence crosses a FAT boundary. */
static int dir_slot(DirCursor *cur,U32 *lba,U16 *offset) {
  U32 next;
  if (volume.fat_bits==16 && cur->cluster==ROOT16) {
    if (cur->slot>=volume.root_entries) return 1;
    *lba=fs_dir_lba(cur->cluster,cur->slot);
    *offset=(U16)(cur->slot%16)*32; return 0;
  }
  if (!valid(cur->cluster)) return fail(E_INVALID);
  if (cur->slot>=(U16)volume.spc*16) {
    if (++cur->hops==0 || (U32)cur->hops>=volume.clusters) return fail(E_INVALID);
    fs_error=0; next=rw_fat(cur->cluster); if (fs_error) return -1;
    if (next>=0x0ffffff8UL) return 1;
    if (!valid(next)) return fail(E_INVALID);
    cur->cluster=next; cur->slot=0;
  }
  *lba=address(cur->cluster)+cur->slot/16;
  *offset=(U16)(cur->slot%16)*32; return 0;
}
static U8 name_checksum(const U8 *name) {
  U8 sum=0;
  U16 i;
  for (i=0;i<11;++i) sum=(U8)(((sum&1)?128:0)+(sum>>1)+name[i]);
  return sum;
}
static int erase_lfn(RwFile *f) {
  DirCursor cur,start;
  U32 lba;
  U16 off,remaining=0,count=0,i;
  U8 wanted,checksum=0,*e,ordinal;
  int result;
  if (chain_valid(f->parent) || read_sector(f->lba,block)) return -1;
  wanted=name_checksum(block+f->offset);
  cur.cluster=f->parent; cur.slot=cur.hops=0;
  memset(&start,0,sizeof(start));
  for (;;) {
    result=dir_slot(&cur,&lba,&off);
    if (result) return result<0?-1:fail(E_INVALID);
    if (read_sector(lba,block)) return -1;
    e=block+off;
    if (lba==f->lba && off==f->offset) break;
    if (!e[0]) return fail(E_INVALID);
    if (e[11]==15 && e[12]==0 && get16(e+26)==0 && !(e[0]&128)) {
      ordinal=(U8)(e[0]&63);
      if (e[0]&64) {
        count=0;
        if (ordinal && ordinal<=20) {
          start=cur; count=ordinal; remaining=ordinal; checksum=e[13];
        }
      }
      if (!count || !remaining || ordinal!=remaining || e[13]!=checksum) count=0;
      else --remaining;
    } else count=0;
    ++cur.slot;
  }
  if (!count || remaining || checksum!=wanted) return 0;
  cur=start;
  for (i=0;i<count;++i) {
    if (dir_slot(&cur,&lba,&off) || read_sector(lba,block)) return -1;
    block[off]=229;
    if (store(lba,block)) return -1;
    ++cur.slot;
  }
  return 0;
}
static int valid_fsinfo(const U8 *p) {
  return get32(p) == 0x41615252UL && get32(p + 484) == 0x61417272UL &&
         get32(p + 508) == 0xaa550000UL;
}
void rw_invalidate(void) {
  invalidate_reads();
  begun=dirty=0; sd_write_disarm(); fs_invalidate();
}
/* block contains primary FAT sector zero. Never overwrite a disagreeing
 * mirror while publishing clean/dirty flags, even with fast mounting. */
static int head_mirrors(void) {
  unsigned f;
  if (!mirrored) return 0;
  for (f=1;f<fat_count;++f) {
    if (read_sector(first_fat+(U32)f*rw_fatsz,other)) return -1;
    if (memcmp(block,other,512)) return inconsistent();
  }
  return 0;
}
static int mirrors(void) {
  U32 i;
  unsigned f;
  if (!mirrored || fat_count<2) return 0;
  for (i=0;i<rw_fatsz;++i) {
    if (read_sector(first_fat+i,block)) return -1;
    for (f=1;f<fat_count;++f) {
      if (read_sector(first_fat+(U32)f*rw_fatsz+i,other)) return -1;
      if (memcmp(block,other,512)) return inconsistent();
    }
  }
  return 0;
}
int rw_mount(void) {
  /* Read-only preflight precedes arming: geometry/capacity, backup BPB, enabled
   * FAT mirrors, clean/error flags and optional FSInfo signatures. This is
   * not a whole-volume consistency or cross-linked-cluster scan. */
  U32 start=0,total;
  U16 reserved,flags,info,backup;
  int result;
  rw_invalidate(); rw_allocated=rw_freed=0;
  if (fs_mount()) return -1;
  start=volume.start;
  if (read_sector(start,block)) return -1;
  reserved=get16(block+14); fat_count=block[16];
  flags=volume.fat_bits==16?0:get16(block+40);
  mirrored=(U8)((flags&128)==0); active_fat=mirrored?0:(U8)(flags&15);
  rw_fatsz=volume.fat_sectors; total=volume.total;
  rw_start=start; rw_end=start+total; first_fat=start+reserved;
  if (rw_end-1>sd_last_lba || volume.fat!=first_fat+(U32)active_fat*rw_fatsz)
    return fail(E_INVALID);
  info=backup=0;
  if (volume.fat_bits==32) { info=get16(block+48); backup=get16(block+50); }
  fsinfo_lba=backup_info=backup_boot=0xffffffffUL;
  if (backup && backup!=65535U) {
    if (backup>=reserved) return fail(E_INVALID);
    backup_boot=start+backup;
  }
  if (info && info!=65535U) {
    if (info>=reserved || start+info==backup_boot) return fail(E_INVALID);
    fsinfo_lba=start+info;
    if (backup_boot!=0xffffffffUL && (U32)backup+info<reserved)
      backup_info=backup_boot+info;
  }
  if (backup_boot!=0xffffffffUL) {
    memcpy(other,block,512);
    if (read_sector(backup_boot,block)) return -1;
    if (get16(block+510)!=0xaa55 || memcmp(block+11,other+11,41))
      return fail(E_INVALID);
  }
  if (!rw_skip_fat_check && mirrors()) return -1;
  if (read_sector(volume.fat,block)) return -1;
  if (volume.fat_bits==16) {
    if ((get16(block+2)&0xc000U)!=0xc000U) return fail(E_INVALID);
  } else if ((get32(block+4)&0x0c000000UL)!=0x0c000000UL) return fail(E_INVALID);
  /* The clean/error flags share FAT sector zero with allocation entries.
   * mark_clean copies that whole sector to each mirror. Even a fast mount
   * must compare it first, so the first write cannot hide a disagreement. */
  if (rw_skip_fat_check && head_mirrors()) return -1;
  if (fsinfo_lba!=0xffffffffUL) {
    if (read_sector(fsinfo_lba,block)) return -1;
    if (!valid_fsinfo(block)) return fail(E_INVALID);
    if (backup_info!=0xffffffffUL) {
      if (read_sector(backup_info,block)) return -1;
      if (!valid_fsinfo(block)) return fail(E_INVALID);
    }
  }
  result=sd_write_arm(start+1,rw_end);
  if (result) return fail((U16)result);
  hint=2; begun=1; fs_error=0; return 0;
}
static int mark_clean(int clean) {
  unsigned f;
  U32 flags;
  if (read_sector(volume.fat,block)) return -1;
  if (rw_skip_fat_check && head_mirrors()) return -1;
  if (volume.fat_bits==16) {
    flags=get16(block+2);
    if (clean) flags|=0x8000UL; else flags&=~0x8000UL;
    put16(block+2,(U16)flags);
  } else {
    flags=get32(block+4);
    if (clean) flags|=0x08000000UL; else flags&=~0x08000000UL;
    put32(block+4,flags);
  }
  if (raw_store(volume.fat,block)) return -1;
  if (mirrored) for (f=1;f<fat_count;++f)
    if (raw_store(first_fat+(U32)f*rw_fatsz,block)) return -1;
  return 0;
}
int rw_begin(void) {
  /* Clear the clean flag before mutations; discard both FSInfo hints. The
   * flag detects interruption but is neither a journal nor automatic repair. */
  U32 lba;
  unsigned i;
  if (!begun || sd_diag.poisoned) return fail(E_NOTREADY);
  if (dirty) return 0;
  if (mark_clean(0)) return -1;
  dirty=1;
  for (i=0;i<2;++i) {
    lba=i?backup_info:fsinfo_lba;
    if (lba==0xffffffffUL) continue;
    if (read_sector(lba,other)) return -1;
    put32(other+488,0xffffffffUL); put32(other+492,0xffffffffUL);
    if (raw_store(lba,other)) return -1;
  }
  return 0;
}
int rw_dirty_session(void) { return dirty!=0; }
int rw_flush(void) {
  /* Every store is already verified. Commit checks mirrors before publishing
   * the clean flag; FAT-mirror-inconsistent or poisoned sessions cannot become
   * clean. Flush does not perform a global chain/crosslink consistency scan. */
  if (!begun || sd_diag.poisoned) return fail(E_NOTREADY);
  if (!dirty) return 0;
  if (mirrors() || mark_clean(1)) return -1;
  dirty=0; return 0;
}
/* FAT16's root cannot grow. Find an existing free slot without allocating
 * clusters or changing the FAT; a full root is an ordinary disk-full error. */
static int reserve_root(const U8 pattern[11],U32 *target,U16 *slot) {
  U16 n,offset,free_offset=0;
  U32 lba,tag=0xffffffffUL,free_lba=0;
  if (chain_valid(ROOT16)) return -1;
  for (n=0;n<volume.root_entries;++n) {
    lba=fs_dir_lba(ROOT16,n); offset=(U16)(n%16)*32;
    if (tag!=lba) { if (read_sector(lba,block)) return -1; tag=lba; }
    if (!block[offset] || block[offset]==229) {
      if (!free_lba) { free_lba=lba; free_offset=offset; }
      if (!block[offset]) break;
    } else if (same_name(block+offset,pattern)) return fail(E_EXISTS);
  }
  if (!free_lba) return fail(E_FULL);
  *target=free_lba; *slot=free_offset; return 0;
}
static int reserve_slot(U32 parent,const U8 pattern[11],U32 *target,U16 *slot) {
  U32 c,next,i,free_lba=0;
  unsigned sector,offset,free_offset=0;
  int end=0;
  if (!begun || sd_diag.poisoned) return fail(E_NOTREADY);
  if (volume.fat_bits==16 && parent==ROOT16)
    return reserve_root(pattern,target,slot);
  if (!valid(parent)) return fail(E_INVALID);
  if (chain_valid(parent)) return -1;
  c = parent;
  for (i = 0; i < volume.clusters; ++i) {
    if (!valid(c))
      return fail(E_INVALID);
    for (sector = 0; sector < volume.spc && !end; ++sector) {
      if (read_sector(address(c) + sector, block))
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
        } else if (same_name(block + offset, pattern))
          return fail(E_EXISTS);
      }
    }
    if (end)
      break;
    fs_error = 0;
    next = rw_fat(c);
    if (fs_error)
      return -1;
    if (next >= 0x0ffffff8UL) {
      if (!free_lba) {
        next = allocate(1);
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
    return fail(E_INVALID);
  *target=free_lba; *slot=(U16)free_offset; return 0;
}
static int write_entry(U32 parent,U32 lba,U16 off,const U8 entry[32]) {
  /* Replacing an end marker must first establish the next zero marker, even
   * when that slot lies in the next sector/cluster. Otherwise stale entries
   * beyond the former end would become visible. */
  DirCursor cur;
  U32 next_lba;
  U16 next_off;
  int result;
  if (read_sector(lba,block)) return -1;
  if (!block[off]) {
    cur.cluster=parent; cur.slot=cur.hops=0;
    for (;;) {
      result=dir_slot(&cur,&next_lba,&next_off);
      if (result) return result<0?-1:fail(E_INVALID);
      if (next_lba==lba && next_off==off) break;
      ++cur.slot;
    }
    ++cur.slot;
    result=dir_slot(&cur,&next_lba,&next_off);
    if (result<0) return -1;
    if (!result) {
      if (read_sector(next_lba,block)) return -1;
      block[next_off]=0;
      if (next_lba!=lba && store(next_lba,block)) return -1;
    }
    if (result || next_lba!=lba) {
      if (read_sector(lba,block)) return -1;
    }
  }
  memcpy(block+off,entry,32);
  return store(lba,block);
}
static int create(U32 parent, const char *name, RwFile *f, int directory) {
  U8 pattern[11],entry[32];
  U32 next,free_lba;
  U16 free_offset;
  if (fs_pattern(name,pattern,0)) return -1;
  if (!strcmp(name,".") || !strcmp(name,"..")) return fail(E_INVALID);
  if (reserve_slot(parent,pattern,&free_lba,&free_offset)) return -1;
  if (rw_begin()) return -1;
  memset(f, 0, sizeof(*f));
  f->lba = free_lba;
  f->offset = free_offset;
  f->directory = (U8)directory;
  f->parent=parent; f->attr=(U8)(directory?16:32);
  if (directory) {
    f->first = f->last = allocate(1);
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
  if (entry[0]==229) entry[0]=5;
  entry[11] = (U8)(directory ? 16 : 32);
  put16(entry + 22, f->time);
  put16(entry + 24, f->date);
  put16(entry + 20, (U16)(f->first >> 16));
  put16(entry + 26, (U16)f->first);
  if (write_entry(parent,free_lba,free_offset,entry))
    return -1;
  fs_error = 0;
  return 0;
}
int rw_mkdir(U32 p, const char *n, RwFile *f) { return create(p, n, f, 1); }
int rw_create(U32 p, const char *n, RwFile *f) { return create(p, n, f, 0); }
int rw_rename(RwFile *f,const char *destination) {
  /* Cross-parent moves update '..', publish destination, then erase source.
   * Interrupted moves may leave duplicates or an inconsistent parent link.
   * Same-parent rename only replaces the alias in its existing slot. */
  U32 parent,c,next,target;
  U16 off;
  char leaf[13];
  U8 pattern[11],entry[32];
  RwFile existing;
  U32 hops;
  if (f->attr&1) return fail(E_ACCESS);
  if (validate_file(f) || fs_parent(destination,&parent,leaf)) return -1;
  if (!leaf[0] || !strcmp(leaf,".") || !strcmp(leaf,"..")) return fail(E_ACCESS);
  if (fs_pattern(leaf,pattern,0)) return -1;
  if (!rw_lookup(destination,&existing)) {
    if (existing.lba==f->lba && existing.offset==f->offset) return 0;
    return fail(E_EXISTS);
  }
  if (fs_error!=E_NOTFOUND) return -1;
  if (f->directory) {
    c=parent;
    for (hops=0;c!=volume.root && hops<volume.clusters;++hops) {
      if (c==f->first) return fail(E_ACCESS);
      if (!valid(c)) return fail(E_INVALID);
      if (read_sector(address(c),block)) return -1;
      if (memcmp(block,".          ",11) || block[11]!=16 ||
          memcmp(block+32,"..         ",11) || block[43]!=16)
        return fail(E_INVALID);
      next=fs_entry_cluster(block+32); c=next?next:volume.root;
    }
    if (hops==volume.clusters || c==f->first) return fail(E_ACCESS);
  }
  if (parent==f->parent) {
    if (rw_begin() || erase_lfn(f) || read_sector(f->lba,block)) return -1;
    memcpy(block+f->offset,pattern,11);
    if (block[f->offset]==229) block[f->offset]=5;
    return store(f->lba,block);
  }
  if (reserve_slot(parent,pattern,&target,&off)) return -1;
  if (rw_begin() || erase_lfn(f) || read_sector(f->lba,block)) return -1;
  memcpy(entry,block+f->offset,32); memcpy(entry,pattern,11);
  if (entry[0]==229) entry[0]=5;
  if (f->directory) {
    if (read_sector(address(f->first),block)) return -1;
    if (memcmp(block+32,"..         ",11) || block[43]!=16) return fail(E_INVALID);
    next=parent==volume.root?0:parent;
    if (volume.fat_bits==32) put16(block+52,(U16)(next>>16));
    put16(block+58,(U16)next);
    if (store(address(f->first),block)) return -1;
  }
  if (write_entry(parent,target,off,entry) || read_sector(f->lba,block)) return -1;
  block[f->offset]=229;
  if (store(f->lba,block)) return -1;
  f->parent=parent; f->lba=target; f->offset=off; fs_error=0; return 0;
}
static U32 locate(RwFile *f, U32 pos) {
  U32 c = f->first, i, n, index = pos >> (9+fs_spc_shift);
  for (i = 0; i < index; ++i) {
    fs_error = 0;
    n = rw_fat(c);
    if (fs_error) return 0;
    if (!valid(n)) {
      fail(E_INVALID);
      return 0;
    }
    c = n;
  }
  if (!valid(c)) {
    fail(E_INVALID);
    return 0;
  }
  return c;
}
int rw_overwrite(RwFile *f, U32 pos, const U8 FAR *data, U16 count) {
  U32 c, lba;
  unsigned offset, n;
  if (f->directory || (f->attr&1)) return fail(E_ACCESS);
  if (pos > f->size || count > f->size - pos)
    return fail(E_INVALID);
  if (!count) return 0;
  if (validate_file(f)) return -1;
  if (rw_begin()) return -1;
  /* Full validation above remains fresh. Walk forward only within this call;
   * no cluster-position proof survives a callback or mutation. */
  c=locate(f,pos); if (!c) return -1;
  while (count) {
    lba = address(c) + ((pos>>9)&(volume.spc-1U));
    offset = (unsigned)(pos % 512);
    n = 512 - offset;
    if (n > count)
      n = count;
    /* A full replacement has no bytes to preserve from the old sector. */
    if ((offset || n!=512) && read_sector(lba, block))
      return -1;
#ifndef HOST_TEST
    data=(const U8 far *)MK_FP(FP_SEG(data)+(FP_OFF(data)>>4),FP_OFF(data)&15);
#endif
    fs_copy(block+offset,data,n);
    if (store(lba, block))
      return -1;
    pos += n;
    data += n;
    count -= n;
    if (count && !(pos&(((U32)volume.spc<<9)-1UL))) {
      fs_error=0; c=rw_fat(c); if (fs_error) return -1;
      if (!valid(c)) return fail(E_INVALID);
    }
  }
  fs_error = 0;
  return 0;
}
int rw_append(RwFile *f, const U8 FAR *data, U16 count) {
  U32 c, lba;
  unsigned offset, n;
  U32 old_size = f->size;
  if (f->directory || (f->attr&1)) return fail(E_ACCESS);
  if (f->size > 0xffffffffUL - count)
    return fail(E_INVALID);
  if (!count) return 0;
  if (validate_file(f)) return -1;
  if (rw_begin()) return -1;
  /* validate_file captured the cluster at logical EOF, not physical EOC.
   * Unwritten allocation slack may contain old data. Store each incoming
   * byte (or explicit gap/extension zero) before publishing the new size;
   * reads stop at that size. Partial sectors preserve existing file bytes. */
  while (count) {
    if (!(f->size&(((U32)volume.spc<<9)-1UL))) {
      c=0;
      if (!f->size && f->first) c=f->first;
      else if (f->last) {
        fs_error=0; c=rw_fat(f->last); if (fs_error) return -1;
        if (c>=0x0ffffff8UL) c=0;
      }
      if (!c) {
        c = allocate(0);
        if (!c) {
          if (fs_error==E_FULL && f->size!=old_size) {
            if (publish(f)) return -1;
            return fail(E_FULL);
          }
          return -1;
        }
        if (f->last && setfat(f->last, c)) return -1;
      }
      if (!f->first)
        f->first = c;
      f->last = c;
    }
    lba = address(f->last) + ((f->size>>9)&(volume.spc-1U));
    offset = (unsigned)(f->size % 512);
    n = 512 - offset;
    if (n > count)
      n = count;
    if ((offset || n!=512) && read_sector(lba, block))
      return -1;
    if (data) {
#ifndef HOST_TEST
      data=(const U8 far *)MK_FP(FP_SEG(data)+(FP_OFF(data)>>4),FP_OFF(data)&15);
#endif
      fs_copy(block+offset,data,n);
    } else memset(block+offset,0,n);
    if (store(lba, block))
      return -1;
    f->size += n;
    if (data) data += n;
    count -= n;
  }
  if (f->size != old_size && publish(f))
    return -1;
  fs_error = 0;
  return 0;
}
int rw_resize(RwFile *f,U32 size) {
  U32 remaining;
  U16 count;
  if (size<=f->size) return rw_truncate(f,size);
  while (f->size<size) {
    remaining=size-f->size;
    count=remaining>65535UL?65535U:(U16)remaining;
    if (rw_append(f,0,count)) return -1;
  }
  return 0;
}
int rw_write(RwFile *f,U32 pos,const U8 FAR *data,U16 count,U16 *done) {
  /* DOS offsets are 32-bit but far pointer offsets are 16-bit. Normalize
   * between overwrite and append so addition cannot wrap at 64 KiB.
   * Disk-full append can publish a completed prefix, reported through done. */
  U16 n;
  U32 old_size;
  int result;
  *done=0;
  if (f->directory || (f->attr&1)) return fail(E_ACCESS);
  if (pos>0xffffffffUL-count) return fail(E_INVALID);
  if (!count) return rw_resize(f,pos);
  if (pos>f->size && rw_resize(f,pos)) return -1;
  if (pos<f->size) {
    n=f->size-pos<count?(U16)(f->size-pos):count;
    if (rw_overwrite(f,pos,data,n)) return -1;
    *done=n;
#ifndef HOST_TEST
    data=(const U8 far *)MK_FP(FP_SEG(data)+(FP_OFF(data)>>4)+(n>>4),
                              (FP_OFF(data)&15)+(n&15));
#else
    data+=n;
#endif
    count-=n;
  }
  if (count) {
    old_size=f->size;
    result=rw_append(f,data,count);
    *done+=(U16)(f->size-old_size);
    return result;
  }
  return 0;
}
int rw_truncate(RwFile *f, U32 size) {
  /* Publish the smaller size before reclaiming the tail. Delete likewise
   * hides the directory entry before freeing its chain. Interruptions can
   * leak clusters rather than leave a visible file pointing to freed data. */
  U32 c, next = 0;
  if (f->directory || (f->attr&1)) return fail(E_ACCESS);
  if (size > f->size)
    return fail(E_INVALID);
  if (validate_file(f))
    return -1;
  if (size == f->size)
    return 0;
  if (rw_begin()) return -1;
  c = size ? locate(f, size - 1) : 0;
  if (size && !c)
    return -1;
  if (c) {
    fs_error = 0;
    next = rw_fat(c);
    if (fs_error)
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
  fs_error = 0;
  return 0;
}
int rw_delete(RwFile *f) {
  if (f->directory || (f->attr&1))
    return fail(E_ACCESS);
  if (validate_file(f) || rw_begin() || erase_lfn(f) || read_sector(f->lba, block))
    return -1;
  block[f->offset] = 0xe5;
  if (store(f->lba, block) || release_chain(f->first))
    return -1;
  memset(f, 0, sizeof(*f));
  fs_error = 0;
  return 0;
}
int rw_rmdir(RwFile *f) {
  DirCursor cursor;
  U8 entry[32];
  int result;
  if (!f->directory || f->first==volume.root)
    return fail(E_INVALID);
  if (validate_file(f)) return -1;
  cursor.cluster = f->first;
  cursor.slot = cursor.hops = 0;
  fs_invalidate();
  while ((result = fs_next(&cursor, entry)) == 0)
    if ((memcmp(entry,".          ",11) && memcmp(entry,"..         ",11)) || entry[11]!=16)
      return fail(E_NOTEMPTY);
  if (result < 0)
    return -1;
  f->directory = 0;
  /* The directory was validated above. Hide its entry before reclamation;
   * the regular-file deletion entry point deliberately rejects directories. */
  if (rw_begin() || erase_lfn(f) || read_sector(f->lba,block)) return -1;
  block[f->offset]=229;
  if (store(f->lba,block) || release_chain(f->first)) return -1;
  memset(f,0,sizeof(*f)); fs_error=0; return 0;
}

/* File-level size clamp around the independently tested raw FAT reader. */
int rw_read(const RwFile *file, U32 pos, U8 FAR *data, U16 count, U16 *done) {
  FileCursor cursor;
  *done = 0;
  if (file->directory)
    return fail(E_INVALID);
  if (pos >= file->size || !count)
    return 0;
  if (file->size - pos < count)
    count = (U16)(file->size - pos);
  cursor.first = file->first;
  cursor.cluster = file->first;
  cursor.index = 0;
  return fs_read(&cursor, pos, data, count, done);
}
