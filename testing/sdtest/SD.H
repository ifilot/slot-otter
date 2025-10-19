#ifndef _SD_H
#define _SD_H

#define MAXTRIAL 1000

#include <dos.h>
#include "sdcmds.h"

int sd_boot();

void sd_set_miso_low(unsigned ioport);

void sd_set_miso_high(unsigned ioport);

void sd_disable(unsigned ioport);

#endif _SD_H