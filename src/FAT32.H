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

#define F32LLSZ  128  /* maximum linked list size */
#define F32MXFL  256  /* maximum number of files in folder to parse */
#define F32MXDIR 256  /* maximum number of folders that can be copied */
#define MAXPATH   80  /* maximum number of characters in path */

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

/**
 *  fat32_list_dir - Prints all files in folder to screen
 */
void fat32_list_dir();

/**
 *  fat32_transfer_file - Transfer a single file
 *
 *  Parameters:
 *      f    - Pointer to FAT32File* struct
 *      path - Path to store file in
 *
 *  Returns:
 *      0 on success
 *
 *  Transfers a single file from the SD-CARD to the hard drive. Uses MS-DOS
 *  write functions to store the file.
 */
int fat32_transfer_file(const struct FAT32File* f, const char* path);

/**
 *  fat32_transfer_folder - Recursively transfer a folder from the SD-CARD
 *
 *  Parameters:
 *      f    - Pointer to FAT32File* corresponding to a folder
 *
 *  Recursively copies all the files and folders to the currently active folder
 *  in the MS-DOS environment. The currently active folder is assumed to already
 *  be set in the file navigator.
 */
void fat32_transfer_folder(const struct FAT32File* f);

/**
 *  fat32_build_path - Construct a subpath from a folder list using identifier
 *
 *  Parameters:
 *      folders    - Array of FAT32Folder to copy
 *      id         - Index of folder to construct path for
 *      path       - Subpath
 *
 *  Construct a subpath given the folder in the array of folders to be copied
 *  and which is identified by id. Used in `fat32_transfer_folder`.
 */
void fat32_build_path(struct FAT32Folder folders[], unsigned id, char path[]);

/**
 *  fat32_transfer_files_in_folder - Copies all files in folder
 *
 *  Parameters:
 *      f           - Pointer to FAT32Folder struct
 *      basepath    - Destination to copy folder to
 *
 *  Reads all files in folder, loops over these files and copies all files
 *  one-by-one to the MS-DOS filesystem. If a file exists, the user is prompted
 *  to overwrite (y/n/a).
 */
void fat32_transfer_files_in_folder(struct FAT32Folder* f, const char* basepath);

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

#endif