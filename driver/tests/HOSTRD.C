/* Host-only DOS memory adapter. Includes unchanged production dispatch code
 * so the reset fixture can reset private TSR state between independent tests. */
#include "../REDIR.C"
#include <stdlib.h>
static U8 memory[5][65536];
U8 *test_far_at(U16 seg, U16 off) {
    if (seg>=5) abort();
    return memory[seg]+off;
}
/* Boundary tests invoke the production formatter with synthetic counts;
 * integration tests still obtain free counts through the actual FAT reader. */
void test_disk_space(U32 total, U16 spc, U32 free) {
    Volume saved=volume;
    volume.clusters=total; volume.spc=(U8)spc;
    disk_space(free);
    volume=saved;
}
void test_reset(void) {
    memset(memory,0,sizeof(memory)); memset(files,0,sizeof(files));
    memset(searches,0,sizeof(searches)); memset(&regs,0,sizeof(regs));
    media_epoch=1; next_search=0; search_serial=0; media_online=0;
    drive_number=18; dos_major=6; dos_sda=memory[1]; drive_cds=memory[2];
    dos_name_offset=0x9e; dos_attr_offset=0x24d;
    dos_search_offset=0x19e; dos_found_offset=0x1b3;
    memcpy(drive_cds,"S:\\",4); put16(drive_cds+0x43,0xc080);
    put16(dos_sda+12,0); put16(dos_sda+14,4);
#ifdef RW_DRIVER
    memset(locks,0,sizeof(locks)); rw_bios_ticks=0; rw_invalidate();
    rw_error_function=rw_error_code=0; unload_blocked=0; rw_skip_fat_check=0;
    unload_state[0]=1; unload_state[1]=0x100; unload_state[2]=3;
    unload_state[3]=0x200; unload_state[4]=2;
    put16(memory[0]+0x2f*4,0x100); put16(memory[0]+0x2f*4+2,3);
    { U16 i; for (i=0;i<sizeof(saved_cds);++i) saved_cds[i]=(U8)(i*7+1); }
    memset(resident_stack,0xa5,sizeof(resident_stack));
#endif
    fs_invalidate(); memset(&volume,0,sizeof(volume)); fs_error=0;
}
