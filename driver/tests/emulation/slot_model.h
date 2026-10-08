/* SPDX-License-Identifier: GPL-3.0-or-later */
#ifndef SLOT_MODEL_H
#define SLOT_MODEL_H
#include <stdint.h>
typedef struct slot_model slot_model;
#define SLOT_WRITABLE 1
#define SLOT_STRICT_CRC 2
#define SLOT_INIT_CRC 4
#define SLOT_COLD_START 8
#define SLOT_BUSY 1
#define SLOT_REJECT_WRITE 2
#define SLOT_BUSY_FOREVER 3
#define SLOT_BAD_READ_CRC 4
#define SLOT_STATUS_ERROR 5
#define SLOT_NO_CMD59 6
#define SLOT_DROP_WRITE 7
#define SLOT_CORRUPT_WRITE 8
#define SLOT_IGNORE_CMD0 9
#define SLOT_BAD_READ_LBA 10
#define SLOT_IGNORE_OFF_WRITE 11
#define SLOT_GLITCH_READ 12
#define SLOT_READ_DELAY 13
#define SLOT_READ_TOKEN 14
#define SLOT_WRITE_RESPONSE 15
#define SLOT_RESPONSE_DELAY 16
#define SLOT_STATUS_R1 17
#define SLOT_REJECT_COMMAND 18
#define SLOT_MISSING_COMMAND 19
#define SLOT_LATE_BUSY 20
#define SLOT_REPEAT_CRC 21
#define SLOT_RESPONSE_HIGH 22
#define SLOT_CMD55_READY 23
#define SLOT_ACMD41_IDLE 24
#define SLOT_FF_CORRUPT 25
#define SLOT_RECOVERY_STATUS 26
#define SLOT_PROBE_FAULT 27
#define SLOT_REJECT_BUSY 28
/* command + 1 selects CID/CSD packet corruption; zero disables injection. */
#define SLOT_BAD_REGISTER_CRC 29
slot_model *slot_model_open(const char *image);
slot_model *slot_model_open_ex(const char *image, unsigned flags);
void slot_model_config(slot_model *card, unsigned option, unsigned value);
int slot_model_replace(slot_model *card, const char *image);
void slot_model_close(slot_model *card);
void slot_model_reset(slot_model *card);
uint8_t slot_model_read(slot_model *card, unsigned offset);
void slot_model_write(slot_model *card, unsigned offset, uint8_t value);
#endif
