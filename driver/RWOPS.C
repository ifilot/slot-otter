/* Included by REDIR.C after its private helpers; do not compile separately.
 * DOS callbacks never invoke INT 21h. GPL-3.0-or-later. */
#define E_SHARE 32
#define E_LOCK 33
#define MAX_LOCKS 16
typedef struct {
    U8 FAR *sft;
    U32 lba, start, length;
    U16 offset;
} RegionLock;
static RegionLock locks[MAX_LOCKS];
#ifdef HOST_TEST
U32 rw_bios_ticks;
#endif
static int rw_result(int result) {
    return result ? filesystem_error() : success();
}
static int same_file(const RwFile *a,const RwFile *b) {
    /* Directory location is stable while open: rename/delete are refused. */
    return a->lba==b->lba && a->offset==b->offset;
}
static U16 access_bits(U16 mode) {
    return (mode&3)==0?1:(mode&3)==1?2:3;
}
static U16 denied_bits(U16 mode) {
    switch ((mode>>4)&7) {
    case 1: return 3;
    case 2: return 2;
    case 3: return 1;
    default: return 0;
    }
}
static int shared(const RwFile *f,U16 mode) {
    U16 i,old,owner=get16(dos_sda+0x10);
    for (i=0;i<MAX_OPEN;++i) {
        if (!files[i].sft || !same_file(f,&FILE_DISK(files+i))) continue;
        old=get16(files[i].sft+2);
        if (denied_bits(old)&access_bits(mode)) return 1;
        if (denied_bits(mode)&access_bits(old)) return 1;
        /* Compatibility opens may coexist within their opening process.
         * Across processes, a compatibility writer excludes other opens. */
        if (owner!=files[i].owner &&
            (!(old&0x70) || !(mode&0x70)) &&
            ((access_bits(old)|access_bits(mode))&2)) return 1;
    }
    return 0;
}
static int file_busy(const RwFile *f) {
    U16 i;
    for (i=0;i<MAX_OPEN;++i)
        if (files[i].sft && same_file(f,&FILE_DISK(files+i))) return 1;
    return 0;
}
static void timestamp(U16 *time,U16 *date) {
    /* Resident callbacks cannot ask DOS for the clock. DOS keeps the date in
     * SDA; BIOS ticks supply time. Sample high/low/high on the 16-bit CPU so
     * an IRQ increment between word reads cannot tear the 32-bit counter. */
    U16 off=dos_major==3?0x2e:0x30;
    U16 day=dos_sda[off],month=dos_sda[off+1],year=get16(dos_sda+off+2);
    U32 ticks,seconds;
#ifndef HOST_TEST
    U16 high,low;
    volatile U16 far *clock=(volatile U16 far *)MK_FP(0x40,0x6c);
#endif
#ifdef HOST_TEST
    ticks=rw_bios_ticks;
#else
    do { high=clock[1]; low=clock[0]; } while (high!=clock[1]);
    ticks=((U32)high<<16)|low;
#endif
    if (ticks>=1573040UL) ticks=0;
    /* Approximate 65536/1193180 seconds per tick within FAT's two-second
     * resolution, using a multiplier that cannot overflow over one day. */
    seconds=(ticks*1080UL)/19663UL;
    *time=(U16)(((seconds/3600)<<11)|(((seconds/60)%60)<<5)|((seconds%60)>>1));
    if (!day || day>31 || !month || month>12 || year>127) {
        year=0; month=day=1;
    }
    *date=(U16)((year<<9)|(month<<5)|day);
}
/* A differing SFT time/date is a pending DOS handle-time update. Preserve it
 * while refreshing metadata changed by another independently opened handle. */
static int refresh_file(OpenFile *file) {
    U16 time=get16(file->sft+13),date=get16(file->sft+15);
    int pending=time!=FILE_DISK(file).time || date!=FILE_DISK(file).date;
    if (rw_refresh(&FILE_DISK(file))) return -1;
    put32(file->sft+17,FILE_DISK(file).size); file->sft[4]=FILE_DISK(file).attr;
    if (!pending) { time=FILE_DISK(file).time; date=FILE_DISK(file).date; }
    put16(file->sft+13,time); put16(file->sft+15,date);
    return 0;
}
/* DOS caches EOF in each SFT, including for seek. Publish size immediately
 * to all independent handles without changing their individual positions. */
static void sync_files(OpenFile *file) {
    U16 i,time,date;
    for (i=0;i<MAX_OPEN;++i) {
        if (!files[i].sft || !same_file(&FILE_DISK(file),&FILE_DISK(files+i))) continue;
        time=get16(files[i].sft+13); date=get16(files[i].sft+15);
        if (time==FILE_DISK(files+i).time && date==FILE_DISK(files+i).date) {
            time=FILE_DISK(file).time; date=FILE_DISK(file).date;
        }
        FILE_DISK(files+i)=FILE_DISK(file);
        put32(files[i].sft+17,FILE_DISK(file).size); files[i].sft[4]=FILE_DISK(file).attr;
        put16(files[i].sft+13,time); put16(files[i].sft+15,date);
    }
}
static int rw_open_file(U8 FAR *sft,U16 mode,U16 action,U8 attr) {
    U16 i,branch,time,date;
    U32 parent;
    char leaf[13];
    U8 name[11];
    RwFile f;
    int exists;
    if ((mode&0xff0c) || (mode&3)==3 || ((mode>>4)&7)>4) return error(12);
    if ((action&~0x13) || (action&3)>2) return error(12);
    if (attr&0xd8) return error(E_ACCESS);
    for (i=0;i<MAX_OPEN;++i) if (!files[i].sft) break;
    if (i==MAX_OPEN) return error(E_HANDLES);
    exists=rw_lookup(path,&f)==0;
    if (!exists && fs_error!=E_NOTFOUND) return filesystem_error();
    if (exists) {
        if (f.directory) return error(E_ACCESS);
        if (!(action&3)) return error(E_EXISTS);
        if (shared(&f,mode)) return error(E_SHARE);
        if ((f.attr&1) && ((mode&3) || (action&3)==2)) return error(E_ACCESS);
        branch=(action&3)==2?3:1;
        if (branch==3 && rw_truncate(&f,0)) return filesystem_error();
    } else {
        if (!(action&0x10)) return error(E_NOTFOUND);
        if (fs_parent(path,&parent,leaf)) return filesystem_error();
        if (rw_create(parent,leaf,&f)) return filesystem_error();
        branch=2;
    }
    if (branch!=1) {
        timestamp(&time,&date);
        if (rw_metadata(&f,attr|32,time,date)) return filesystem_error();
    }
    if (fs_parent(path,&parent,leaf) || fs_pattern(leaf,name,0)) return filesystem_error();
    files[i].sft=sft; FILE_DISK(files+i)=f; files[i].owner=get16(dos_sda+0x10);
    files[i].created_ro=(U8)(branch!=1 && (attr&1));
    /* DOS owns SFT reference count at +0 and sharing/PSP fields at +43 onward.
     * Open fills our fields only; final-close reference cleanup is below. */
    put16(sft+2,mode); sft[4]=f.attr;
    put16(sft+5,0xc000|drive_number|((mode&0x80)?0x1000:0));
    put32(sft+7,0); put16(sft+11,0);
    put16(sft+13,f.time); put16(sft+15,f.date);
    put32(sft+17,f.size); put32(sft+21,0); put32(sft+25,0);
    sft[29]=sft[30]=sft[31]=0;
    for (i=0;i<11;++i) sft[32+i]=name[i];
    sync_files(find_file(sft));
    success(); regs.cx=branch; return 1;
}
static int overlap(U32 start,U32 length,U32 a,U32 n) {
    /* Overflow-free half-open interval comparison. */
    return length && n && (start>=a ? start-a<n : a-start<length);
}
static int locked(OpenFile *file,U32 start,U32 length) {
    U16 i;
    for (i=0;i<MAX_LOCKS;++i)
        if (locks[i].sft && locks[i].sft!=file->sft &&
            locks[i].lba==FILE_DISK(file).lba && locks[i].offset==FILE_DISK(file).offset &&
            overlap(start,length,locks[i].start,locks[i].length)) return 1;
    return 0;
}
static void unlock_file(U8 FAR *sft) {
    U16 i;
    for (i=0;i<MAX_LOCKS;++i) if (locks[i].sft==sft) locks[i].sft=0;
}
static int rw_lock_file(U8 FAR *sft,U8 fn) {
    OpenFile *file=find_file(sft);
    U8 FAR *p;
    U32 start,length;
    U16 i,slot=MAX_LOCKS;
    int unlock;
    if (!file) return error(6);
    /* DOS 3: CX:DX position, SI:caller-stack-word length. DOS 4-6: DS:DX
     * points to two DWORDs, CX=1, BL selects unlock. Unlock is an exact match. */
    if (dos_major==3) {
        start=((U32)regs.cx<<16)|regs.dx;
        length=((U32)regs.si<<16)|regs.param; unlock=fn==0x0b;
    } else {
        if (fn!=0x0a || regs.cx!=1 || (regs.bx&255)>1) return error(1);
        p=far_at(regs.ds,regs.dx); start=get32(p); length=get32(p+4);
        unlock=(regs.bx&255)==1;
    }
    if (!length || length-1>0xffffffffUL-start) return error(E_LOCK);
    for (i=0;i<MAX_LOCKS;++i) {
        if (!locks[i].sft) { if (slot==MAX_LOCKS) slot=i; continue; }
        if (locks[i].lba!=FILE_DISK(file).lba || locks[i].offset!=FILE_DISK(file).offset) continue;
        if (unlock && locks[i].sft==sft && locks[i].start==start && locks[i].length==length) {
            locks[i].sft=0; return success();
        }
        if (!unlock && overlap(start,length,locks[i].start,locks[i].length)) return error(E_LOCK);
    }
    if (unlock) return error(E_LOCK);
    if (slot==MAX_LOCKS) return error(36);
    locks[slot].sft=sft; locks[slot].lba=FILE_DISK(file).lba; locks[slot].offset=FILE_DISK(file).offset;
    locks[slot].start=start; locks[slot].length=length; return success();
}
static int rw_write_file(U8 FAR *sft) {
    OpenFile *file=find_file(sft);
    U32 position,old_size,range_start,range_length;
    U16 done,time,date,count=regs.cx;
    U8 attr;
    int result;
    regs.cx=0;
    if (!file) return error(6);
    if (!(get16(sft+2)&3)) return error(E_ACCESS);
    if (refresh_file(file)) return filesystem_error();
    position=get32(sft+21); old_size=FILE_DISK(file).size;
    range_start=position; range_length=count;
    if (!count || position>old_size) {
        range_start=position<old_size?position:old_size;
        range_length=position>old_size?position-old_size:old_size-position;
        if (range_length>0xffffffffUL-count) return error(E_INVALID);
        range_length+=count;
    }
    if (locked(file,range_start,range_length)) return error(E_LOCK);
    attr=FILE_DISK(file).attr;
    if (file->created_ro) FILE_DISK(file).attr&=~1;
    result=rw_write(&FILE_DISK(file),position,pointer_at(dos_sda+12),count,&done);
    FILE_DISK(file).attr|=attr&1;
    put32(sft+21,position+done); put32(sft+17,FILE_DISK(file).size); regs.cx=done;
    if (!result || fs_error==E_FULL) {
        U16 code=fs_error;
        timestamp(&time,&date);
        if ((done || old_size!=FILE_DISK(file).size) &&
            rw_metadata(&FILE_DISK(file),FILE_DISK(file).attr|32,time,date)) return filesystem_error();
        put16(sft+13,FILE_DISK(file).time); put16(sft+15,FILE_DISK(file).date);
        sync_files(file);
        /* DOS reports disk full as a successful short write; zero-count
         * resize has no short-count channel and returns disk-full instead. */
        if (result && !count) return error(code);
        return success();
    }
    return filesystem_error();
}
static int rw_commit_file(U8 FAR *sft,int closing) {
    /* Commit failure must not strand a final close: release our slot/locks
     * even with removed/poisoned media. Duplicate handles share an SFT, so
     * locks survive until its last DOS reference has closed. */
    OpenFile *file=find_file(sft);
    U16 code=0,time,date;
    int was_online=media_online;
    if (!file) { if (!closing) return error(6); }
    else if (media_online && ready()) {
        time=get16(sft+13); date=get16(sft+15);
        if (time!=FILE_DISK(file).time || date!=FILE_DISK(file).date) {
            if (!(get16(sft+2)&3)) code=E_ACCESS;
            else if (rw_refresh(&FILE_DISK(file)) ||
                     rw_metadata(&FILE_DISK(file),FILE_DISK(file).attr,time,date)) code=fs_error;
            else sync_files(file);
        }
        /* All file bytes and pending metadata are synchronously verified.
         * Ordinary close releases its reference without publishing clean state.
         * Explicit commit/global flush/unmount retain the full FAT comparison. */
        if (!code && !closing && rw_flush()) code=fs_error;
    } else if (!closing || was_online) code=E_NOTREADY;
    if (closing) {
        if (get16(sft)) put16(sft,get16(sft)-1);
        if (!get16(sft)) { unlock_file(sft); if (file) file->sft=0; }
    }
    if (code) { fs_error=code; return filesystem_error(); }
    return success();
}
static int cwd_busy(void) {
    U16 i;
    if (!drive_cds) return 0;
    for (i=0;path[i] && path[i]==drive_cds[i];++i) ;
    return !path[i] && (!drive_cds[i] || drive_cds[i]=='\\');
}
static int delete_pattern(void) {
    DirCursor cursor;
    RwFile f;
    U32 parent;
    U16 i,found=0;
    U8 pattern[11],e[32];
    char leaf[13];
    int result,match;
    if (fs_parent(path,&parent,leaf) || fs_pattern(leaf,pattern,1))
        return filesystem_error();
    cursor.cluster=parent; cursor.slot=cursor.hops=0;
    while ((result=fs_next(&cursor,e))==0) {
        if ((e[11]&24) || (e[11]&6&~dos_sda[dos_attr_offset])) continue;
        match=1;
        for (i=0;i<11;++i) if (pattern[i]!='?' && pattern[i]!=e[i]) { match=0; break; }
        if (!match) continue;
        memset(&f,0,sizeof(f)); f.first=fs_entry_cluster(e); f.size=get32(e+28);
        f.parent=parent; f.attr=e[11]; f.time=get16(e+22); f.date=get16(e+24);
        f.lba=volume.data+(cursor.cluster-2)*volume.spc+(cursor.slot-1)/16;
        f.offset=(U16)((cursor.slot-1)%16)*32;
        if (file_busy(&f)) return error(E_SHARE);
        if (rw_delete(&f)) return filesystem_error();
        found=1;
    }
    if (result<0) return filesystem_error();
    return found?success():error(E_NOTFOUND);
}
static int rw_path_operation(U8 fn,U8 FAR *sft) {
    RwFile f;
    U32 parent;
    U16 i,time,date,action,mode;
    char leaf[13];
    U8 FAR *destination;
    if (fn==0x17 || fn==0x18) {
        if ((regs.param>>8)>1) return error(12);
        return rw_open_file(sft,2,(regs.param&0x100)?0x10:0x12,(U8)regs.param);
    }
    if (fn==0x2e) {
        if (dos_major<4) return error(1);
        action=get16(dos_sda+0x2dd)&255; mode=get16(dos_sda+0x2e1);
        return rw_open_file(sft,mode,action,(U8)get16(dos_sda+0x2df));
    }
    if (fn==3 || fn==4) {
        if (fs_parent(path,&parent,leaf)) return filesystem_error();
        if (rw_mkdir(parent,leaf,&f)) return filesystem_error();
        timestamp(&time,&date);
        return rw_result(rw_metadata(&f,f.attr,time,date));
    }
    if (fn==0x13 && (strchr(path,'*') || strchr(path,'?'))) return delete_pattern();
    if (rw_lookup(path,&f)) return filesystem_error();
    if (fn==0x0e) return rw_result(rw_metadata(&f,(U8)regs.param,f.time,f.date));
    if (file_busy(&f)) return error(E_SHARE);
    if (fn==1 || fn==2) {
        if (cwd_busy()) return error(16);
        return rw_result(rw_rmdir(&f));
    }
    if (fn==0x13) return rw_result(rw_delete(&f));
    if (fn==0x11) {
        if (f.directory && cwd_busy()) return error(E_ACCESS);
        destination=dos_sda+dos_name_offset+128;
        if (destination[0]!='A'+drive_number || destination[1]!=':') return error(17);
        for (i=0;i<PATH_MAX;++i) { path[i]=destination[i]; if (!path[i]) break; }
        if (i==PATH_MAX) return error(E_PATH);
        return rw_result(rw_rename(&f,path));
    }
    return error(E_ACCESS);
}
