#ifndef _CFG_H
#define _CFG_H

#include <stdio.h>

#define CFG_FILENAME "OTTERNAV.INI"
#define CFG_DEFAULT_BASE_PORT 0x330

/*
 *  cfg_init - Load configuration or create defaults
 *
 *  Parameters:
 *      filename - Path to INI file
 */
void cfg_init(const char* filename);

/*
 *  cfg_save - Persist configuration to disk
 *
 *  Parameters:
 *      filename - Path to INI file
 */
void cfg_save(const char* filename);

/*
 *  cfg_get_base_port - Get current base I/O port
 */
unsigned cfg_get_base_port();

/*
 *  cfg_set_base_port - Set current base I/O port
 *
 *  Parameters:
 *      base_port - New base port address
 */
void cfg_set_base_port(unsigned base_port);

#endif
