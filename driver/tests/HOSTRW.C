/* Test-only bridge to the byte-level card model; not resident. */
#include "RWSD.H"
#include "../emulation/slot_model.h"
#include <string.h>
static slot_model *card;
static U32 clocks;
static U8 selected, command_bytes[6], command_count, command_done;
static U16 repeat_option, repeat_value;
static U16 flip_crc;
static char replacement[256];
static int replace_pending;
static U8 *mutate_buffer;
static U16 delay, pending, pending_offset;
static U8 pending_value;
unsigned rw_host_writes, rw_host_resets, rw_host_unfinished;
/* Capture the first eight payload+CRC packets. writes counts observed CMD24
 * commands, unlike sd_diag.transmissions, which requires command acceptance. */
U32 rw_host_lbas[8];
U8 rw_host_packets[8][514];
static unsigned packet_index, packet_count;
int rw_host_open(const char *path, unsigned flags) {
    if (card) slot_model_close(card);
    card=slot_model_open_ex(path,flags);
    clocks=0; selected=command_count=command_done=0;
    repeat_option=repeat_value=delay=pending=flip_crc=0;
    replace_pending=0; mutate_buffer=0;
    rw_host_writes=rw_host_resets=rw_host_unfinished=packet_count=0;
    memset(rw_host_lbas,0,sizeof(rw_host_lbas));
    memset(rw_host_packets,0,sizeof(rw_host_packets));
    return card?0:-1;
}
void rw_host_close(void) { if (card) slot_model_close(card); card=0; }
void rw_host_config(unsigned option,unsigned value) { slot_model_config(card,option,value); }
int rw_host_replace(const char *path) { return slot_model_replace(card,path); }
void rw_host_repeat(U16 option,U16 value) { repeat_option=option; repeat_value=value; }
void rw_host_replace_on_reset(const char *path) {
    strncpy(replacement,path,sizeof(replacement)-1);
    replacement[sizeof(replacement)-1]=0; replace_pending=1;
}
void rw_host_mutate_on_reset(U8 *p) { mutate_buffer=p; }
void rw_host_timing(U16 accesses) { delay=accesses; }
void rw_host_flip_crc(U16 count) { flip_crc=count; }
static void exchange(U16 offset,U8 value) {
    /* Reset injection tests identity replacement and caller-buffer mutation;
     * repeat_option is reapplied at each CMD24 to create persistent faults. */
    if (offset<=1) {
        ++clocks;
        if (selected && offset==0) {
            if (!command_done && (command_count || (value&192)==64)) {
                command_bytes[command_count++]=value;
                if (command_count==6) {
                    command_done=1;
                    if ((command_bytes[0]&63)==0) {
                        ++rw_host_resets;
                        if (rw_host_writes && replace_pending) {
                            (void)slot_model_replace(card,replacement); replace_pending=0;
                        }
                        if (rw_host_writes && mutate_buffer) {
                            memset(mutate_buffer,0x73,512); mutate_buffer=0;
                        }
                    }
                    if ((command_bytes[0]&63)==24) {
                        U32 lba=((U32)command_bytes[1]<<24)|((U32)command_bytes[2]<<16)|
                            ((U32)command_bytes[3]<<8)|command_bytes[4];
                        if (rw_host_writes<8) rw_host_lbas[rw_host_writes]=lba;
                        packet_index=rw_host_writes++; packet_count=0;
                        if (repeat_option) slot_model_config(card,repeat_option,repeat_value);
                    }
                }
            } else if (command_done && (command_bytes[0]&63)==24 && packet_index<8) {
                if (!packet_count) { if (value==254) packet_count=1; }
                else if (packet_count<=514) {
                    if (packet_count==514 && flip_crc) { value^=1; --flip_crc; }
                    rw_host_packets[packet_index][packet_count++-1]=value;
                }
            }
        }
    }
    slot_model_write(card,offset,value);
}
/* Delayed completion advances by register accesses, not electrical time. */
static void advance(void) { if (pending && !--pending) exchange(pending_offset,pending_value); }
void rw_reg_write(U16 offset,U8 value) {
    advance();
    if (pending) { ++rw_host_unfinished; pending=0; }
    if (offset==2 || offset==3) {
        selected=(U8)(offset==3); command_count=command_done=0;
    }
    if (offset<=1 && delay) { pending_offset=offset; pending_value=value; pending=delay; }
    else exchange(offset,value);
}
U8 rw_reg_read(U16 offset) { advance(); return slot_model_read(card,offset); }
/* Synthetic ticks count byte exchanges; they are not hardware speed evidence. */
U16 rw_ticks(void) { return (U16)(clocks/2048UL); }
