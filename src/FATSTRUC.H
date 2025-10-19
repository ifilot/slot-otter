/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    FATSTRUC.H
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

#ifndef _FATSTRUC_H
#define _FATSTRUC_H

/* ---------------------------------------------------------------------
   FAT32Partition
   ---------------------------------------------------------------------
   Describes the general layout and parameters of a FAT32 partition.
   Used for locating FAT tables, root directory, and cluster regions.
   --------------------------------------------------------------------- */
struct FAT32Partition {
    unsigned bytes_per_sector;              /* Number of bytes in one sector   */
    unsigned char sectors_per_cluster;      /* Sectors that make up a cluster  */
    unsigned reserved_sectors;              /* Reserved sectors before FAT area*/
    unsigned char number_of_fats;           /* Number of FAT tables present    */
    unsigned long sectors_per_fat;          /* Sectors used by one FAT         */
    unsigned long root_dir_first_cluster;   /* First cluster of root dir       */
    unsigned long fat_begin_lba;            /* LBA address of first FAT sector */
    unsigned long lba_addr_root_dir;        /* LBA address of root directory   */
    unsigned long sector_begin_lba;         /* LBA of data region start        */
    char volume_label[11];                  /* Volume label in ASCII (no null) */
};

/* ---------------------------------------------------------------------
   FAT32Folder
   ---------------------------------------------------------------------
   Represents a directory (folder) entry in FAT32.
   Holds basic metadata and location for subdirectories.
   ---------------------------------------------------------------------   */
struct FAT32Folder {
    char name[11];                   /* Directory name (8.3 format)        */
    unsigned long cluster;           /* Starting cluster of this folder    */
    unsigned nrfiles;                /* Number of files inside this folder */
    unsigned char attrib;            /* Attribute byte (e.g., 0x10 = DIR)  */
    int reference;                   /* Optional internal reference ID     */
};

/* ---------------------------------------------------------------------
   FAT32File
   ---------------------------------------------------------------------
   Represents an individual file entry in FAT32.
   Contains basic file name, type, location, and size information.
   ---------------------------------------------------------------------   */
struct FAT32File {
    char basename[8];                /* Base name (8 chars, space padded)  */
    char extension[3];               /* Extension (3 chars, space padded)  */
    unsigned char termbyte;          /* Terminator byte (0x00)             */
    unsigned char attrib;            /* File attribute flags               */
    unsigned long cluster;           /* First cluster of the file          */
    unsigned long filesize;          /* File size in bytes                 */
};

#endif