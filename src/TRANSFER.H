/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    TRANSFER.H
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

#ifndef _TRANSFER_H
#define _TRANSFER_H

#include "fat32.h"
#include "hdnav.h"

/**
 *  transfer_sd_file_to_hd - Transfer a single file from SD to hard drive
 *
 *  Parameters:
 *      f    - Pointer to FAT32File* struct
 *      path - Path to store file in
 *
 *  Returns:
 *      0 on success
 */
int transfer_sd_file_to_hd(const struct FAT32File* f, const char* path);

/**
 *  transfer_sd_folder_to_hd - Recursively transfer a folder from SD to hard drive
 *
 *  Parameters:
 *      f    - Pointer to FAT32File* corresponding to a folder
 */
void transfer_sd_folder_to_hd(const struct FAT32File* f);

/**
 *  transfer_build_sd_path - Construct a subpath from a folder list using identifier
 *
 *  Parameters:
 *      folders    - Array of FAT32Folder to copy
 *      id         - Index of folder to construct path for
 *      path       - Subpath
 */
void transfer_build_sd_path(struct FAT32Folder folders[], unsigned id, char path[]);

/**
 *  transfer_sd_files_in_folder_to_hd - Copies all files in an SD folder
 *
 *  Parameters:
 *      f           - Pointer to FAT32Folder struct
 *      basepath    - Destination to copy folder to
 */
void transfer_sd_files_in_folder_to_hd(struct FAT32Folder* f, const char* basepath);

/**
 *  transfer_hd_file_to_sd - Transfer a single file from hard drive to SD
 *
 *  Parameters:
 *      f - Pointer to HDNavFile struct
 *
 *  Returns:
 *      0 on success
 */
int transfer_hd_file_to_sd(const struct HDNavFile* f);

/**
 *  transfer_hd_file_to_sd_ui - Transfer a file from hard drive to SD with UI
 *
 *  Parameters:
 *      f - Pointer to HDNavFile struct
 *
 *  Returns:
 *      0 on success
 */
int transfer_hd_file_to_sd_ui(const struct HDNavFile* f);

/**
 *  transfer_hd_folder_to_sd - Transfer a folder from hard drive to SD
 *
 *  Parameters:
 *      f - Pointer to HDNavFile struct
 *
 *  Returns:
 *      0 on success
 */
int transfer_hd_folder_to_sd(const struct HDNavFile* f);

#endif



