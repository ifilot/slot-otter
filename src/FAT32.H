/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    FAT32.H
 *  Author:  Ivo Filot <ivo@ivofilot.nl>
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <https://www.gnu.org/licenses/>.
 * ===================================================================== */

#ifndef _FAT32_H
#define _FAT32_H

#include <stdio.h>
#include <time.h>

#include "fatstruc.h"
#include "sdcmds.h"
#include "cfg.h"

#define F32LLSZ  2048  	/* maximum linked list size */
#define F32MXFL  512  	/* maximum number of files in folder to parse */
#define F32MXDIR 256  	/* maximum number of folders that can be copied */
#define MAXPATH   80  	/* maximum number of characters in path */

#define MASK_DIR (1 << 4)
#define FILE_ENTRY 0
#define FOLDER_ENTRY 1

extern struct FAT32Partition fat32_partition;
extern struct FAT32File fat32_files[F32MXFL];
extern unsigned int fat32_nrfiles;

/**
 *  fat32_open_partition - Open FAT32 partition
 *
 *  Tries to open the first partition on the SD-CARD as a FAT32 partition.
 *  Sets the ROOT directory as the current directory.
 */
void fat32_open_partition();

/**
 *  fat32_print_partition_info - Print the current partition info
 *
 *  Prints relevant partition information.
 */
void fat32_print_partition_info();

/**
 *  fat32_read_current_folder - Read the currently active folder
 *
 *  Grabs all the files and folders present in the currently active folder
 *  and sorts them. The result will be stored in fat32_files which is an array
 *  of FAT32File structures. After reading, the files can be displayed on the 
 *  screen.
 */
void fat32_read_current_folder();

/**
 *  fat32_read_dir - Read a folder
 *
 *  Parameters:
 *      folder - Pointer to FAT32Folder struct
 *      buffer - Array of FAT32File objects to store results in
 *
 *  Reads the folder indicated by the FAT32Folder pointer and store all the
 *  files in the buffer. The buffer should be pre-allocated and is set to the
 *  maximum capacity. This function terminates early when the maximum number
 *  of files are being read.
 */
void fat32_read_dir(struct FAT32Folder* folder, struct FAT32File buffer[]);

/**
 *  fat32_set_current_folder - Set the current folder
 *
 *  Parameters:
 *      entry - FAT32File pointer
 *
 *  Using a FAT32File pointer, the current active folder is being set. After
 *  setting the folder, the folder is automatically being read and the buffer
 *  is populated. When the entry's cluster points to 0x00000000, it is
 *  automatically being recognized as the ROOT folder and set accordingly.
 */
void fat32_set_current_folder(const struct FAT32File* entry);

/*
 *  fat32_get_current_folder - Copy the current folder state
 *
 *  Parameters:
 *      folder - Destination folder state
 */
void fat32_get_current_folder(struct FAT32Folder* folder);

/*
 *  fat32_set_current_folder_state - Restore the current folder state
 *
 *  Parameters:
 *      folder - Folder state to restore
 */
void fat32_set_current_folder_state(const struct FAT32Folder* folder);

/**
 *  fat32_list_dir - Prints all files in folder to screen
 */
void fat32_list_dir();

/**
 *  fat32_mkdir - Create a new directory on SD card
 *
 *  Parameters:
 *      dirname - Name of the directory to create
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_mkdir(const char* dirname);

/*
 *  fat32_calculate_sector_address - Calculate sector address from cluster and sector
 *
 *  Parameters:
 *      cluster - cluster address
 *      sector  - sector id
 *
 *  Returns:
 *      Returns SD-CARD sector address
 */
unsigned long fat32_calculate_sector_address(unsigned long cluster,
					     unsigned char sector);

/*
 *  fat32_read_sector - Reads sector from SD-CARD
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 */
void fat32_read_sector(unsigned long);

/*
 *  fat32_read_sector_to - Reads sector from SD-CARD into caller buffer
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 *      buf  - Buffer to store sector data
 */
void fat32_read_sector_to(unsigned long, unsigned char*);

/*
 *  fat32_write_sector - Write sector to SD-CARD
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 */
int fat32_write_sector(unsigned long);

/*
 *  fat32_write_sector_from - Write sector to SD-CARD from caller buffer
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 *      buf  - Buffer containing sector data
 */
int fat32_write_sector_from(unsigned long, unsigned char*);

/*
 *  fat32_get_file_entry - Get file from buffer identified by id
 *
 *  Parameters:
 *      id - Identifier
 *
 *  Retrieves pointer to FAT32File* struct identified by ID
 */
const struct FAT32File* fat32_get_file_entry(unsigned int id);

/*
 *  fat32_sort_files - Sort files encountered in folder
 */
void fat32_sort_files();

/*
 *  fat32_file_compare - Compare two FAT32File* file entries
 *
 *  Parameters:
 *      item 1 -  FAT32File pointer to file1
 *      item 2 -  FAT32File pointer to file2
 *
 *  Returns:
 *      -1 if file1 < file2
 *      +1 if file1 > file2
 */
int fat32_file_compare(const void* item1, const void* item2);

/*
 *  fat32_build_linked_list - Build linked list of clusters
 *
 *  Parameters:
 *      nextcluster - starting cluster in the linked list
 */
void fat32_build_linked_list(unsigned long nextcluster);

/*
 *  fat32_grab_cluster_address_from_fileblock - Grab cluster address from sector data
 *
 *  Parameters:
 *      loc - Starting location of raw file entry in SD-CARD buffer
 *
 *  Returns:
 *      Starting cluster address of file
 */
unsigned long fat32_grab_cluster_address_from_fileblock(unsigned char* loc);

/*
 *  fat32_normalize_name_83 - Convert a filename to FAT 8.3 raw format
 *
 *  Parameters:
 *      input - User-facing name
 *      out   - 11-byte FAT 8.3 name buffer
 *
 *  Returns:
 *      0 if the name is valid, -1 otherwise
 */
int fat32_normalize_name_83(const char* input, char out[11]);

/*
 *  fat32_normalize_file_83 - Convert a filename to FAT 8.3 raw format
 *
 *  Parameters:
 *      input - User-facing filename
 *      out   - 11-byte FAT 8.3 name buffer
 *
 *  Returns:
 *      0 if the name is valid, -1 otherwise
 */
int fat32_normalize_file_83(const char* input, char out[11]);

/*
 *  fat32_find_free_cluster - Find the first unused data cluster
 *
 *  Returns:
 *      Cluster number, or 0 if no free cluster was found
 */
unsigned long fat32_find_free_cluster();

/*
 *  fat32_write_fat_entry - Write a FAT entry to all FAT copies
 *
 *  Parameters:
 *      cluster - Cluster whose FAT entry should be written
 *      value   - New low-28-bit FAT value
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_write_fat_entry(unsigned long cluster, unsigned long value);

/*
 *  fat32_zero_cluster - Write zeroes to all sectors in a cluster
 *
 *  Parameters:
 *      cluster - Cluster to clear
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_zero_cluster(unsigned long cluster);

/*
 *  fat32_create_dir_entry - Create an entry in the current directory
 *
 *  Parameters:
 *      name         - 11-byte FAT 8.3 name
 *      attrib       - FAT attribute byte
 *      firstcluster - First cluster of the file or directory
 *      filesize     - File size in bytes
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_create_dir_entry(const char name[11],
                           unsigned char attrib,
                           unsigned long firstcluster,
                           unsigned long filesize);

/*
 *  fat32_delete_file_entry - Delete a file entry from the current directory
 *
 *  Parameters:
 *      name - 11-byte FAT 8.3 name
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_delete_file_entry(const char name[11]);

/*
 *  fat32_delete_entry - Delete an entry from the current directory
 *
 *  Parameters:
 *      name - 11-byte FAT 8.3 name
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_delete_entry(const char name[11]);

/*
 *  fat32_find_free_dir_entry - Find or create a free directory entry
 *
 *  Parameters:
 *      folder      - Folder whose directory chain should be searched
 *      entrysector - Sector address containing the free entry
 *      entryoffset - Byte offset of the free entry within that sector
 *
 *  Returns:
 *      0 if a free entry was found or created, -1 otherwise
 */
int fat32_find_free_dir_entry(struct FAT32Folder* folder,
                              unsigned long* entrysector,
                              unsigned* entryoffset);

#endif










