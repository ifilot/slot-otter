#include "cfg.h"

CFGEntry cfg_entries[CFG_MAX_ENTRIES];
int cfg_entry_count = 0;

char *trim(char *str) {
    char *end;
    while(isspace(*str)) str++;
    if(*str == 0) return str;
    end = str + strlen(str) - 1;
    while(end > str && isspace(*end)) end--;
    *(end + 1) = 0;
    return str;
}

void cfg_parse_ini(const char *filename) {
    char *trimmed;
    char *eq;
    char line[CFG_MAX_LINE];

    FILE *f = fopen(filename, "r");
    if(!f) {
	printf("Could not open %s\n", filename);
	return;
    }

    while(fgets(line, sizeof(line), f)) {
	trimmed = trim(line);

	if(*trimmed == ';' || *trimmed == '#' || *trimmed == '\0') {
	    continue;
	}

	eq = strchr(trimmed, '=');
	if(eq && cfg_entry_count < CFG_MAX_ENTRIES) {
	    *eq = '\0';
	    strncopy(cfg_entries[cfg_entry_count].key, trim(trimmed), CFG_MAX_KEY);
	    strncopy(cfg_entries[cfg_entry_count].value, trim(eq+1), CFG_MAX_VALUE);
	    cfg_entry_count++;
	}
    }

    fclose(f);
}

char* cfg_get_value(const char* key) {
    int i;
    for(i=0; i<cfg_entry_count; ++i) {
	if(strcmp(cfg_entries[i].key, key) == 0) {
	    return cfg_entries[i].value;
	}
    }

    return NULL;
}

void cfg_set_value(const char *key, const char *value) {
    int i;
    for(i=0; i<cfg_entry_count; ++i) {
	if(strcmp(cfg_entries[i].key, key) == 0) {

	}
    }
}