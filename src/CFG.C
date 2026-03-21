#include "cfg.h"

#include <stdlib.h>
#include <string.h>
#include <ctype.h>

static unsigned cfg_base_port = CFG_DEFAULT_BASE_PORT;

static char* trim(char* str) {
    char* end;

    while(*str && isspace((unsigned char)*str)) {
        str++;
    }

    if(*str == '\0') {
        return str;
    }

    end = str + strlen(str) - 1;
    while(end > str && isspace((unsigned char)*end)) {
        end--;
    }

    *(end + 1) = '\0';
    return str;
}

static int parse_hex_value(const char* value, unsigned* out) {
    unsigned long v;
    char* endptr;

    if(value == NULL || out == NULL) {
        return 0;
    }

    v = strtoul(value, &endptr, 0);
    if(endptr == value) {
        return 0;
    }

    while(*endptr) {
        if(!isspace((unsigned char)*endptr)) {
            return 0;
        }
        endptr++;
    }

    *out = (unsigned)v;
    return 1;
}

static void cfg_set_defaults() {
    cfg_base_port = CFG_DEFAULT_BASE_PORT;
}

void cfg_save(const char* filename) {
    FILE* f = fopen(filename, "w");
    if(!f) {
        return;
    }

    fprintf(f, "; OTTERNAV configuration\n");
    fprintf(f, "BASE_PORT=0x%X\n", cfg_base_port);
    fclose(f);
}

void cfg_init(const char* filename) {
    FILE* f;
    char line[128];

    cfg_set_defaults();

    f = fopen(filename, "r");
    if(!f) {
        cfg_save(filename);
        return;
    }

    while(fgets(line, sizeof(line), f)) {
        char* trimmed = trim(line);
        char* eq;
        unsigned value;

        if(*trimmed == ';' || *trimmed == '#' || *trimmed == '\0') {
            continue;
        }

        eq = strchr(trimmed, '=');
        if(!eq) {
            continue;
        }

        *eq = '\0';
        trimmed = trim(trimmed);
        eq = trim(eq + 1);

        if(strcmp(trimmed, "BASE_PORT") == 0 && parse_hex_value(eq, &value)) {
            cfg_base_port = value;
        }
    }

    fclose(f);
}

unsigned cfg_get_base_port() {
    return cfg_base_port;
}

void cfg_set_base_port(unsigned base_port) {
    cfg_base_port = base_port;
}
