/* SPDX-License-Identifier: GPL-3.0-or-later
 * Optional DOSBox-VirtIsa adapter using the same schematic-based model as 86Box.
 * Replace src/isa/isa.cpp in a separate checkout and copy slot_model.[ch] beside it.
 */
#include <string>
#include <cstdlib>
#include "dosbox.h"
#include "inout.h"
#include "setup.h"
extern "C" {
#include "slot_model.h"
}
static slot_model *card;
static std::string image_path;
#ifdef OTTER_MODEL_TEST
static Bitu chip_selected;
static unsigned settle_delay, pending, pending_offset, unfinished;
static uint8_t pending_value;
/* Test the board's delayed byte burst by register-access count. This is a
 * protocol guard, not a claim about electrical timing on a physical ISA bus. */
static void advance_burst(void) {
    if (pending && !--pending) slot_model_write(card,pending_offset,pending_value);
}
static Bitu test_cs(Bitu, Bitu) { return chip_selected; }
static Bitu test_unfinished(Bitu, Bitu) { return unfinished?1:0; }
static Bitu test_magic(Bitu, Bitu) { return 0xa5; }
#endif
static Bitu read_port(Bitu port, Bitu) {
#ifdef OTTER_MODEL_TEST
    advance_burst();
#endif
    return card ? slot_model_read(card, (unsigned)(port-0x330)) : 0xff;
}
#ifdef OTTER_MODEL_TEST
/* Test-only host socket controls; absent from production adapter builds. */
static void swap_port(Bitu, Bitu value, Bitu) {
    const char *second=std::getenv("OTTER_TEST_IMAGE2");
    const char *path=value==0?"":value==1?image_path.c_str():second;
    if (!card || !path || slot_model_replace(card,path)) return;
    pending=0;
    chip_selected=0;
    if (value==3) {
        /* Replace with a card already initialized by another host. */
        const unsigned char commands[3][6]={{0x40,0,0,0,0,0x95},
            {0x77,0,0,0,0,1},{0x69,0x40,0,0,0,1}};
        for(unsigned n=0;n<3;++n) {
            slot_model_write(card,2,255); slot_model_write(card,3,255);
            for(unsigned i=0;i<6;++i) slot_model_write(card,0,commands[n][i]);
            for(unsigned i=0;i<8;++i) slot_model_write(card,1,255);
        }
        slot_model_write(card,2,255);
    }
}
#endif
static void write_port(Bitu port, Bitu value, Bitu) {
#ifdef OTTER_MODEL_TEST
    advance_burst();
    if (pending) { ++unfinished; pending=0; }
    if(port==0x332) chip_selected=0;
    if(port==0x333) chip_selected=1;
    if (card && settle_delay && port<=0x331) {
        pending_offset=(unsigned)(port-0x330);
        pending_value=(uint8_t)value; pending=settle_delay;
        return;
    }
#endif
    if (card) slot_model_write(card, (unsigned)(port-0x330), (uint8_t)value);
}
static void destroy_card(Section *) {
    slot_model_close(card); card=0;
}
void ISA_Init(Section *sec) {
    Section_prop *section=static_cast<Section_prop *>(sec);
    const char *path=section->Get_string("isa_sd_image");
    if (path && *path) image_path=path;
    slot_model_close(card);
#ifdef OTTER_MODEL_TEST
    card=slot_model_open(std::getenv("OTTER_TEST_EMPTY")?"":image_path.c_str());
    chip_selected=0;
    pending=unfinished=0;
    const char *delay=std::getenv("OTTER_MODEL_SETTLE");
    settle_delay=delay?(unsigned)std::strtoul(delay,NULL,10):0;
    IO_RegisterWriteHandler(0x334,swap_port,IO_MB,1);
    IO_RegisterReadHandler(0x334,test_cs,IO_MB,1);
    IO_RegisterReadHandler(0x335,test_unfinished,IO_MB,1);
    IO_RegisterReadHandler(0x336,test_magic,IO_MB,1);
#else
    card=slot_model_open(image_path.c_str());
#endif
    if (std::getenv("OTTER_MODEL_WRITE")) {
        slot_model_close(card);
        unsigned flags=SLOT_WRITABLE | SLOT_COLD_START |
            (std::getenv("OTTER_MODEL_STRICT_DATA")?SLOT_STRICT_CRC:0) | (std::getenv("OTTER_MODEL_STRICT")?(SLOT_STRICT_CRC|SLOT_INIT_CRC):0);
        card=slot_model_open_ex(image_path.c_str(),flags);
        const char *options[]={"OTTER_MODEL_BUSY","OTTER_MODEL_REJECT","OTTER_MODEL_TIMEOUT",
            "OTTER_MODEL_BAD_READ","OTTER_MODEL_STATUS","OTTER_MODEL_NO_CRC",
            "OTTER_MODEL_DROP","OTTER_MODEL_CORRUPT","OTTER_MODEL_IGNORE_CMD0",
            "OTTER_MODEL_BAD_READ_LBA","OTTER_MODEL_IGNORE_OFF","OTTER_MODEL_GLITCH_READ",
            "OTTER_MODEL_READ_DELAY","OTTER_MODEL_READ_TOKEN","OTTER_MODEL_WRITE_RESPONSE",
            "OTTER_MODEL_RESPONSE_DELAY","OTTER_MODEL_STATUS_R1","OTTER_MODEL_REJECT_COMMAND",
            "OTTER_MODEL_MISSING_COMMAND","OTTER_MODEL_LATE_BUSY","OTTER_MODEL_REPEAT_CRC",
            "OTTER_MODEL_RESPONSE_HIGH","OTTER_MODEL_CMD55_READY",
            "OTTER_MODEL_ACMD41_IDLE","OTTER_MODEL_FF_CORRUPT","OTTER_MODEL_RECOVERY_STATUS",
            "OTTER_MODEL_PROBE_FAULT","OTTER_MODEL_REJECT_BUSY","OTTER_MODEL_BAD_REGISTER_CRC"};
        if(card) for(unsigned i=0;i<sizeof(options)/sizeof(options[0]);++i) {
            const char *value=std::getenv(options[i]);
            if(value) slot_model_config(card,i+1,(unsigned)std::strtoul(value,NULL,10));
        }
    }
    if (!card) LOG_MSG("Slot-otter: cannot open SD image '%s'",image_path.c_str());
    IO_RegisterReadHandler(0x330,read_port,IO_MB,4);
    IO_RegisterWriteHandler(0x330,write_port,IO_MB,4);
    sec->AddDestroyFunction(destroy_card,true);
}
