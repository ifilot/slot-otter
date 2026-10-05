/* Host-only DOS memory adapter. Includes unchanged production dispatch code
 * so the reset fixture can reset private TSR state between independent tests. */
#include "../REDIR.C"
#include <stdlib.h>
static U8 memory[5][65536];
U8 *test_far_at(U16 seg, U16 off) {
    if (seg>=5) abort();
    return memory[seg]+off;
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
    fs_invalidate(); memset(&volume,0,sizeof(volume)); fs_error=0;
}
