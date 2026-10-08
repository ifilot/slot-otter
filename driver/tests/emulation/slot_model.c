/* SPDX-License-Identifier: GPL-3.0-or-later
 * SDHC model (read-only unless explicitly enabled) and Slot-otter's four schematic-defined ISA registers.
 * Each byte exchange completes synchronously; electrical timing is not modeled.
 */
#define _FILE_OFFSET_BITS 64
#define _POSIX_C_SOURCE 200809L
#include "slot_model.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#define seek_file _fseeki64
#define tell_file _ftelli64
#else
#define seek_file fseeko
#define tell_file ftello
#endif

struct slot_model {
    FILE *image;
    uint64_t sectors;
    uint8_t cid[16];
    uint8_t command[6], queue[520], tx, rx;
    unsigned command_length, head, tail;
    int selected, idle, application, pull_high;
    unsigned flags, crc_enabled, write_phase, write_count, busy, busy_count;
    unsigned reject_at, timeout_at, bad_read_crc, status_at, no_cmd59, drop_at, corrupt_at;
    uint32_t pending_lba, bad_read_lba;
    unsigned ignore_off_write, glitch_read;
    unsigned read_delay, read_token, write_response, response_delay, status_r1;
    unsigned reject_command, missing_command, late_busy, late_pending, repeat_crc;
    unsigned token_wait, token_head, response_high;
    unsigned cmd55_ready, acmd41_idle, ff_corrupt, negative_seen, recovery_status, negative_r1;
    unsigned probe_fault, probe_seen, reject_busy, rejection_aborted;
    unsigned bad_register_crc;
    uint8_t write_data[514];
    unsigned status_pending, ignore_cmd0, spi_mode, idle_clocks;
};
static void enqueue(slot_model *c, uint8_t b) {
    if (c->tail<sizeof(c->queue)) c->queue[c->tail++]=b;
}
static uint16_t crc16(const uint8_t *p, unsigned n) {
    uint16_t crc=0;
    unsigned i;
    while(n--) {
        crc^=(uint16_t)*p++<<8;
        for(i=0;i<8;++i) crc=(uint16_t)((crc<<1)^((crc&0x8000)?0x1021:0));
    }
    return crc;
}
static uint8_t crc7(const uint8_t *p,unsigned n) {
    uint8_t crc=0,b; unsigned i;
    while(n--) { b=*p++; for(i=0;i<8;++i) { crc<<=1; if((b^crc)&128) crc^=9; b<<=1; } }
    return (uint8_t)((crc<<1)|1);
}
static void execute(slot_model *c) {
    unsigned command=c->command[0]&63, i;
    uint32_t arg=((uint32_t)c->command[1]<<24)|((uint32_t)c->command[2]<<16)|
                 ((uint32_t)c->command[3]<<8)|c->command[4];
    uint8_t block[512];
    uint16_t crc;
    int app=c->application;
    c->application=0; c->head=c->tail=0;
    enqueue(c,0xff); /* one response-latency byte */
    if ((c->crc_enabled || (c->flags&SLOT_STRICT_CRC) || command==0 || command==8) &&
        c->command[5]!=crc7(c->command,5)) {
        c->negative_seen=1; c->probe_seen|=1;
        if(c->recovery_status==128) c->negative_r1=8;
        else if(c->recovery_status) c->status_pending=c->recovery_status;
        enqueue(c,(uint8_t)(c->idle|8)); return;
    }
    if ((c->flags&SLOT_COLD_START) && !c->spi_mode && command!=0) return;
    if(c->missing_command==command+1) return;
    if(c->reject_command==command+1) { enqueue(c,4); return; }
    switch(command) {
    case 0:
        if((c->flags&SLOT_COLD_START) && c->idle_clocks<10) break;
        if(c->ignore_cmd0) { --c->ignore_cmd0; break; }
        c->spi_mode=1; c->idle=1; c->crc_enabled=0; enqueue(c,1); break;
    case 8:
        enqueue(c,(uint8_t)c->idle); enqueue(c,0); enqueue(c,0);
        enqueue(c,1); enqueue(c,0xaa); break;
    case 55: c->application=1; enqueue(c,c->cmd55_ready ? 0 : (uint8_t)c->idle); break;
    case 41:
        if((c->flags&SLOT_INIT_CRC) && !c->crc_enabled) { enqueue(c,(uint8_t)(c->idle|8)); break; }
        if (!app) { enqueue(c,(uint8_t)(c->idle|4)); break; }
        if(c->acmd41_idle) { --c->acmd41_idle; enqueue(c,1); break; }
        c->idle=0; enqueue(c,0); break;
    case 58:
        enqueue(c,(uint8_t)c->idle); enqueue(c,c->idle?0x40:0xc0);
        enqueue(c,0xff); enqueue(c,0x80); enqueue(c,0); break;
    case 59:
        if(c->no_cmd59==1 || (c->no_cmd59==2 && !arg)) { enqueue(c,4); break; }
        c->crc_enabled=arg&1; enqueue(c,(uint8_t)c->idle); break;
    case 13:
        if(c->negative_r1) { enqueue(c,(uint8_t)c->negative_r1); c->negative_r1=0; break; }
        enqueue(c,(uint8_t)(c->status_r1?c->status_r1:(unsigned)c->idle));
        enqueue(c,(uint8_t)c->status_pending); c->status_pending=0; break;
    case 9:
        if(c->idle) { enqueue(c,1); break; }
        memset(block,0,16); block[0]=0x40; block[5]=9;
        { uint32_t size=(uint32_t)((c->sectors+1023)/1024-1);
          block[7]=(uint8_t)((size>>16)&63); block[8]=(uint8_t)(size>>8); block[9]=(uint8_t)size; }
        block[12]=2; block[13]=0x40;
        enqueue(c,0); enqueue(c,255); enqueue(c,254);
        for(i=0;i<16;++i) enqueue(c,block[i]);
        crc=crc16(block,16); if(c->bad_register_crc==command+1) crc^=1;
        enqueue(c,(uint8_t)(crc>>8)); enqueue(c,(uint8_t)crc); break;
    case 24:
        if(!(c->flags&SLOT_WRITABLE)) { enqueue(c,(uint8_t)(c->idle|4)); break; }
        if(c->idle || arg>=c->sectors) { enqueue(c,c->idle?1:0x20); break; }
        c->pending_lba=arg; c->write_phase=1; c->write_count=0; enqueue(c,0); break;
    case 10:
        if (c->idle) { enqueue(c,1); break; }
        enqueue(c,0); enqueue(c,0xff); enqueue(c,0xfe);
        for(i=0;i<16;++i) enqueue(c,c->cid[i]);
        crc=crc16(c->cid,16); if(c->bad_register_crc==command+1) crc^=1;
        enqueue(c,(uint8_t)(crc>>8)); enqueue(c,(uint8_t)crc);
        break;
    case 17:
        if(c->rejection_aborted || (c->probe_fault<=2 && c->probe_fault &&
           (c->probe_seen & (c->probe_fault==1 ? 1 : 2)))) { enqueue(c,0); break; }
        if (c->idle) { enqueue(c,1); break; }
        if (arg>=c->sectors || seek_file(c->image,(int64_t)arg*512,SEEK_SET) ||
            fread(block,1,512,c->image)!=512) { enqueue(c,0x20); break; }
        if(c->read_token) {
            enqueue(c,0);
            if(c->read_token==2) enqueue(c,0x0d);
            break;
        }
        if(c->read_delay) { c->token_wait=c->read_delay; c->token_head=2; }
        if((c->probe_fault==5 || c->probe_fault==6) &&
           (c->probe_seen & (c->probe_fault==5 ? 1 : 2))) block[0]^=1;
        if(c->glitch_read) { --c->glitch_read; block[0]^=1; if(c->repeat_crc) c->repeat_crc=2; }
        enqueue(c,0); enqueue(c,0xff); enqueue(c,0xfe);
        for(i=0;i<512;++i) enqueue(c,block[i]);
        crc=crc16(block,512); if(c->bad_read_lba && arg==c->bad_read_lba) crc^=1;
        if(c->bad_read_crc) { --c->bad_read_crc; crc^=1; }
        enqueue(c,(uint8_t)(crc>>8)); enqueue(c,(uint8_t)crc);
        if(c->repeat_crc==2) { c->repeat_crc=0; c->bad_read_crc=1; }
        break;
    default: enqueue(c,(uint8_t)(c->idle|4)); break;
    }
}
static void commit(slot_model *c) {
    uint16_t supplied=((uint16_t)c->write_data[512]<<8)|c->write_data[513];
    uint8_t token=5;
    c->write_phase=0; c->head=c->tail=0;
    if((c->crc_enabled || (c->flags&SLOT_STRICT_CRC)) && supplied!=crc16(c->write_data,512)) {
        token=11; c->negative_seen=1; c->probe_seen|=2;
        if(c->recovery_status==128) c->negative_r1=8;
        else if(c->recovery_status) c->status_pending=c->recovery_status;
    }
    else if(c->reject_at==1) token=13;
    else if((c->probe_fault==3 || c->probe_fault==4) &&
            (c->probe_seen & (c->probe_fault==3 ? 1 : 2))) { /* accepted, not programmed */ }
    else if(c->ignore_off_write && !c->crc_enabled &&
            (c->ignore_off_write==1 || supplied!=crc16(c->write_data,512))) { /* accepted, not programmed */ }
    else if(seek_file(c->image,(int64_t)c->pending_lba*512,SEEK_SET) ||
            fwrite(c->write_data,1,512,c->image)!=512 || fflush(c->image)) token=13;
    if(c->reject_at) --c->reject_at;
    /* Removal occurs after programming, before completion can be verified.
     * The first target may change; subsequent writes must stop. */
    if(c->drop_at && --c->drop_at==0) { fclose(c->image); c->image=NULL; return; }
    if(token==5) {
        if(c->ff_corrupt && (c->ff_corrupt==1 || c->negative_seen)) {
            unsigned i;
            for(i=0;i<512 && c->write_data[i]==255;++i) {}
            if(i==512) {
                /* Recorded SanDisk signature: accepted, clean status, stable
                 * CRC-valid readback of 508 zero bytes and four FF bytes. */
                memset(c->write_data,0,508);
                seek_file(c->image,(int64_t)c->pending_lba*512,SEEK_SET);
                fwrite(c->write_data,1,512,c->image); fflush(c->image);
            }
        }
        if(c->corrupt_at && --c->corrupt_at==0) {
            c->write_data[0]^=1; seek_file(c->image,(int64_t)c->pending_lba*512,SEEK_SET);
            fwrite(c->write_data,1,512,c->image); fflush(c->image);
        }
        c->busy_count=c->busy;
        if(c->timeout_at && --c->timeout_at==0) c->busy_count=0xffffffffU;
        if(c->status_at && --c->status_at==0) c->status_pending=0x20;
    }
    if(token==11 && c->reject_busy) c->busy_count=c->reject_busy;
    c->late_pending=c->late_busy;
    if(c->write_response==1) { c->busy_count=0; return; }
    if(c->write_response==2) token=0;
    if(c->response_delay) { c->token_wait=c->response_delay; c->token_head=1; }
    enqueue(c,255); enqueue(c,(uint8_t)(token | (c->response_high & 0xe0)));
}
static void pulse(slot_model *c) {
    uint8_t tx=c->tx;
    c->tx=0xff;
    if (!c->image) { c->rx=c->pull_high?0xff:0; return; }
    if (!c->selected) {
        if(tx==255 && c->idle_clocks<1000) ++c->idle_clocks;
        c->rx=0xff; return;
    }
    if(c->token_wait && c->head==c->token_head) {
        --c->token_wait; c->rx=255; return;
    }
    if(c->head>=c->tail && c->busy_count && c->late_pending) {
        --c->late_pending; c->rx=255; return;
    }
    if(c->head>=c->tail && c->busy_count) {
        c->rx=0; if(c->busy_count!=0xffffffffU) --c->busy_count; return;
    }
    c->rx=c->head<c->tail?c->queue[c->head++]:((c->flags&SLOT_COLD_START) && !c->spi_mode?0:0xff);
    /* MOSI is ignored while clocking a queued response/data block. */
    if (c->head<c->tail) return;
    if(c->write_phase) {
        if(c->write_phase==1) { if(tx==0xfe) { c->write_phase=2; c->write_count=0; } return; }
        c->write_data[c->write_count++]=tx;
        if(c->write_count==514) commit(c);
        return;
    }
    if (!c->command_length && (tx&0xc0)!=0x40) return;
    c->command[c->command_length++]=tx;
    if (c->command_length==6) { c->command_length=0; execute(c); }
}
void slot_model_reset(slot_model *c) {
    c->selected=0; c->idle=1; c->application=0; c->pull_high=1;
    c->spi_mode=c->idle_clocks=c->negative_seen=c->negative_r1=c->probe_seen=c->rejection_aborted=0;
    c->command_length=c->head=c->tail=0; c->tx=c->rx=0xff;
    c->crc_enabled=c->write_phase=c->write_count=c->busy_count=c->status_pending=0;
}
slot_model *slot_model_open_ex(const char *path,unsigned flags) {
    slot_model *c=calloc(1,sizeof(*c));
    int64_t size;
    uint32_t identity=2166136261U;
    const unsigned char *p;
    if (!c) return NULL;
    slot_model_reset(c); c->flags=flags;
    /* Cold fixture also starts with board CS/pull/RX not prepared by a utility. */
    if(flags&SLOT_COLD_START) { c->selected=1; c->pull_high=0; c->rx=0; }
    if (!path || !*path) return c; /* absent-card testing */
    c->image=fopen(path,(flags&SLOT_WRITABLE)?"r+b":"rb");
    if (!c->image) { free(c); return NULL; }
    /* Host fault fixtures may alter sectors between commands. Never let a
     * stdio read buffer substitute stale bytes for the image's current data. */
    (void)setvbuf(c->image,NULL,_IONBF,0);
    if (seek_file(c->image,0,SEEK_END) || (size=tell_file(c->image))<512 || size%512) {
        slot_model_close(c); return NULL;
    }
    c->sectors=(uint64_t)size/512;
    /* Stable synthetic serial per image path, independent of FAT geometry. */
    for(p=(const unsigned char *)path;*p;++p) identity=(identity^*p)*16777619U;
    memcpy(c->cid,"OTTERSD MODEL",13);
    c->cid[9]=(uint8_t)(identity>>24); c->cid[10]=(uint8_t)(identity>>16);
    c->cid[11]=(uint8_t)(identity>>8); c->cid[12]=(uint8_t)identity;
    return c;
}
slot_model *slot_model_open(const char *path) { return slot_model_open_ex(path,0); }
void slot_model_config(slot_model *c,unsigned option,unsigned value) {
    /* *_WRITE, BUSY_FOREVER and STATUS_ERROR select an occurrence countdown;
     * BAD_READ_CRC/GLITCH_READ count affected reads. Token/response/command
     * modes persist until changed. These are digital protocol faults only. */
    switch(option) {
    case SLOT_BUSY: c->busy=value; break;
    case SLOT_REJECT_WRITE: c->reject_at=value; break;
    case SLOT_BUSY_FOREVER: c->timeout_at=value; break;
    case SLOT_BAD_READ_CRC: c->bad_read_crc=value; break;
    case SLOT_STATUS_ERROR: c->status_at=value; break;
    case SLOT_NO_CMD59: c->no_cmd59=value; break;
    case SLOT_DROP_WRITE: c->drop_at=value; break;
    case SLOT_CORRUPT_WRITE: c->corrupt_at=value; break;
    case SLOT_IGNORE_CMD0: c->ignore_cmd0=value; break;
    case SLOT_BAD_READ_LBA: c->bad_read_lba=value; break;
    case SLOT_IGNORE_OFF_WRITE: c->ignore_off_write=value; break;
    case SLOT_GLITCH_READ: c->glitch_read=value; break;
    case SLOT_READ_DELAY: c->read_delay=value; break;
    case SLOT_READ_TOKEN: c->read_token=value; break;
    case SLOT_WRITE_RESPONSE: c->write_response=value; break;
    case SLOT_RESPONSE_DELAY: c->response_delay=value; break;
    case SLOT_STATUS_R1: c->status_r1=value; break;
    case SLOT_REJECT_COMMAND: c->reject_command=value; break;
    case SLOT_MISSING_COMMAND: c->missing_command=value; break;
    case SLOT_LATE_BUSY: c->late_busy=value; break;
    case SLOT_REPEAT_CRC: c->repeat_crc=value; break;
    case SLOT_RESPONSE_HIGH: c->response_high=value; break;
    case SLOT_CMD55_READY: c->cmd55_ready=value; break;
    case SLOT_ACMD41_IDLE: c->acmd41_idle=value; break;
    case SLOT_FF_CORRUPT: c->ff_corrupt=value; break;
    case SLOT_RECOVERY_STATUS: c->recovery_status=value; break;
    case SLOT_PROBE_FAULT: c->probe_fault=value; break;
    case SLOT_REJECT_BUSY: c->reject_busy=value; break;
    case SLOT_BAD_REGISTER_CRC: c->bad_register_crc=value; break;
    }
}
int slot_model_replace(slot_model *c, const char *path) {
    slot_model *replacement=slot_model_open_ex(path,c->flags);
    if (!replacement) return -1;
    if (c->image) fclose(c->image);
    *c=*replacement; free(replacement); return 0;
}
void slot_model_close(slot_model *c) {
    if (!c) return;
    if (c->image) fclose(c->image);
    free(c);
}
uint8_t slot_model_read(slot_model *c, unsigned offset) {
    uint8_t value=c->rx;
    switch(offset&3) {
    case 0: return value;
    case 1: pulse(c); return value;
    case 2: c->pull_high=0; return 0xff;
    case 3: c->pull_high=1; return 0xff;
    }
    return 0xff;
}
void slot_model_write(slot_model *c, unsigned offset, uint8_t value) {
    switch(offset&3) {
    case 0: c->tx=value; pulse(c); break;
    case 1: pulse(c); break;
    case 2:
        if(c->probe_fault==7 && (c->probe_seen&2) && c->busy_count)
            c->rejection_aborted=1;
        c->selected=0; c->write_phase=0; c->command_length=c->head=c->tail=0; break;
    case 3: c->selected=1; break;
    }
}
