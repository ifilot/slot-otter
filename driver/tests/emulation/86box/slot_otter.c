/* SPDX-License-Identifier: GPL-3.0-or-later
 * 86Box adapter for the schematic-defined Slot-otter ISA interface.
 */
#include <stdint.h>
#include <stdlib.h>
#include <86box/device.h>
#include <86box/io.h>
#include "slot_model.h"

typedef struct { slot_model *card; uint16_t base; } otter_device;
static uint8_t otter_in(uint16_t port, void *priv) {
    otter_device *d=priv;
    return slot_model_read(d->card,port-d->base);
}
static void otter_out(uint16_t port, uint8_t value, void *priv) {
    otter_device *d=priv;
    slot_model_write(d->card,port-d->base,value);
}
static void *otter_init(const device_t *device) {
    otter_device *d=calloc(1,sizeof(*d));
    const char *path=device_get_config_string("image");
    (void)device;
    if (!d) return NULL;
    d->base=(uint16_t)device_get_config_hex16("base");
    if ((d->base&3) || d->base<0x100 || d->base>0xfffc) { free(d); return NULL; }
    d->card=slot_model_open(path);
    if (!d->card) { free(d); return NULL; }
    io_sethandler(d->base,4,otter_in,NULL,NULL,otter_out,NULL,NULL,d);
    return d;
}
static void otter_reset(void *priv) {
    otter_device *d=priv;
    slot_model_reset(d->card);
}
static void otter_close(void *priv) {
    otter_device *d=priv;
    if (!d) return;
    io_removehandler(d->base,4,otter_in,NULL,NULL,otter_out,NULL,NULL,d);
    slot_model_close(d->card); free(d);
}
static const device_config_t otter_config[] = {
    {.name="base", .description="Base I/O address", .type=CONFIG_HEX16,
     .default_int=0x330},
    {.name="image", .description="Read-only SD image", .type=CONFIG_FNAME,
     .default_string="", .file_filter="Raw disk images (*.img)"},
    {.name="", .type=CONFIG_END}
};
const device_t slot_otter_device = {
    .name="Slot-otter", .internal_name="slot_otter", .flags=DEVICE_ISA,
    .init=otter_init, .close=otter_close, .reset=otter_reset, .config=otter_config
};
