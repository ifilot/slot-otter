#ifndef _CFG_H
#define _CFG_H

#include <stdio.h>
#include <string.h>
#include <ctype.h>

#define CFG_MAX_LINE    256
#define CFG_MAX_KEY     64
#define CFG_MAX_ENTRIES 100
#define CFG_MAX_VALUE   128

typedef struct {
    char key[CFG_MAX_KEY];
    char value[CFG_MAX_VALUE];
} CFGEntry;

extern CFGEntry cfg_entries[CFG_MAX_ENTRIES];
extern int cfg_entry_count;

char *trim(char *str);

void cfg_parse_file(const char* filename);

char *cfg_get_value(const char* key);

void cfg_set_value(const char* key, const char *value);

void cfg_write_file(const char* filename);

#endif