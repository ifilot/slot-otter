/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    FAT32.C
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

#include "fat32.h"
#include <conio.h>
#include <string.h>

#define FAT32_WRITE_RETRIES 3

/* buffer to store SDCARD sector data including CRC checksum */
static unsigned char sdbuf[514];
static unsigned char verifybuf[514];
/* store linked list of cluster addresses */
static unsigned long fat32_linked_list[F32LLSZ];
/* total number of files in the currently active folder */
unsigned int fat32_nrfiles;

struct FAT32Partition fat32_partition;
struct FAT32Folder fat32_root_folder;
struct FAT32Folder fat32_current_folder;
struct FAT32File fat32_files[F32MXFL];

static int fat32_delete_named_in_folder(struct FAT32Folder* folder,
                                        const char name[11],
                                        unsigned allowdir);
static int fat32_find_first_deletable_entry(struct FAT32Folder* folder,
                                            char name[11]);
static int fat32_free_cluster_chain(unsigned long cluster);

/**
 *  fat32_open_partition - Open FAT32 partition
 *
 *  Tries to open the first partition on the SD-CARD as a FAT32 partition.
 *  Sets the ROOT directory as the current directory.
 */
void fat32_open_partition() {
    unsigned long lba = 0x00000000;
    unsigned fsinfo_sector = 0;
    unsigned long fsinfo_hint = 0;
    char partname[12];

    /* read boot sector */
    cmd17(cfg_get_base_port(), 0x00000000, sdbuf);
    /*print_block(sdbuf);*/

    /* check for magic bytes */
    if(sdbuf[510] != 0x55 || sdbuf[511] != 0xAA) {
		printf("Could not read SD-card. Try to reinsert.\n");
		sddis(cfg_get_base_port());
		return;
    }

    /* grab start address of first partition */
    lba = *(unsigned long*)(sdbuf + 0x1C6);
    /*printf("LBA: %08X\n", lba);*/

    /* read the partition information */
    fat32_read_sector(lba);

    /* store partition information */
    fat32_partition.bytes_per_sector = *(unsigned*)(sdbuf + 0x0B);
    fat32_partition.sectors_per_cluster = sdbuf[0x0D];
    fat32_partition.reserved_sectors = *(unsigned*)(sdbuf + 0x0E);
    fat32_partition.number_of_fats = sdbuf[0x10];
    fsinfo_sector = *(unsigned*)(sdbuf + 0x30);
    fat32_partition.total_sectors = *(unsigned long*)(sdbuf + 0x20);
    fat32_partition.sectors_per_fat = *(unsigned long*)(sdbuf + 0x24);
    fat32_partition.cluster_count =
        (fat32_partition.total_sectors - fat32_partition.reserved_sectors -
        (fat32_partition.number_of_fats * fat32_partition.sectors_per_fat)) /
        fat32_partition.sectors_per_cluster;
    fat32_partition.root_dir_first_cluster = *(unsigned long*)(sdbuf + 0x2C);
    fat32_partition.fat_begin_lba = lba + fat32_partition.reserved_sectors;
    fat32_partition.sector_begin_lba = fat32_partition.fat_begin_lba +
	(fat32_partition.number_of_fats * fat32_partition.sectors_per_fat);
    fat32_partition.lba_addr_root_dir = fat32_calculate_sector_address(fat32_partition.root_dir_first_cluster, 0);
    fat32_partition.next_free_cluster_hint = 2;

    if(fsinfo_sector != 0) {
        fat32_read_sector(lba + fsinfo_sector);
        if(*(unsigned long*)(sdbuf + 0x000) == 0x41615252UL &&
           *(unsigned long*)(sdbuf + 0x1E4) == 0x61417272UL) {
            fsinfo_hint = *(unsigned long*)(sdbuf + 0x1EC);
            if(fsinfo_hint >= 2 &&
               fsinfo_hint < fat32_partition.cluster_count + 2) {
                fat32_partition.next_free_cluster_hint = fsinfo_hint;
            }
        }
    }

    /* grab information from root folder */
    cmd17(cfg_get_base_port(), fat32_partition.lba_addr_root_dir, sdbuf);
    memcpy(fat32_partition.volume_label, sdbuf, 11);
    /*printf("Partition name: %11s\n", fat32_partition.volume_label); */

    /* set both current folder and root folder */
    fat32_current_folder.cluster = fat32_partition.root_dir_first_cluster;
    fat32_current_folder.nrfiles = 0;
    memset(fat32_current_folder.name, 0x00, 11);
    fat32_root_folder = fat32_current_folder;
}

/**
 *  fat32_print_partition_info - Print the current partition info
 *
 *  Prints relevant partition information.
 */
void fat32_print_partition_info() {
    printf("Bytes per sector: %i\n", fat32_partition.bytes_per_sector);
    printf("Sectors per cluster: %i\n", fat32_partition.sectors_per_cluster);
    printf("Reserved sectors: %i\n", fat32_partition.reserved_sectors);
    printf("Number of FATs: %i\n", fat32_partition.number_of_fats);
    printf("Total sectors: %lu\n", fat32_partition.total_sectors);
    printf("Root directory first cluster: %08X\n", fat32_partition.root_dir_first_cluster);
    printf("Data clusters: %lu\n", fat32_partition.cluster_count);
    printf("FAT begin LBA: %08X\n", fat32_partition.fat_begin_lba);
    printf("Root directory sector: %08X\n", fat32_partition.lba_addr_root_dir);
}

/**
 *  fat32_read_current_folder - Read the currently active folder
 *
 *  Grabs all the files and folders present in the currently active folder
 *  and sorts them. The result will be stored in fat32_files which is an array
 *  of FAT32File structures. After reading, the files can be displayed on the 
 *  screen.
 */
void fat32_read_current_folder() {
    fat32_read_dir(&fat32_current_folder, fat32_files);
    fat32_sort_files();
    fat32_nrfiles = fat32_current_folder.nrfiles;
}

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
void fat32_read_dir(struct FAT32Folder* folder, struct FAT32File buffer[]) {
    unsigned ctr = 0;
    unsigned fctr = 0;
    unsigned i,j;
    unsigned char* locptr = 0;
    struct FAT32File *file = 0;
    unsigned long caddr = 0;

    /* build linked list */
    fat32_build_linked_list(folder->cluster);

    while(fat32_linked_list[ctr] != 0xFFFFFFFF && ctr < F32LLSZ) {
	caddr = fat32_calculate_sector_address(fat32_linked_list[ctr], 0);

	for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
	    fat32_read_sector(caddr);           /* read sector in memory */
	    locptr = (unsigned char*)(sdbuf);	/* set pointer to sector data */
	    for(j=0; j<16; ++j) { /* consume 16 files entries per sector */
            /* continue if an unused entry is encountered */
            if(*locptr == 0xE5) {
                locptr += 32;
                continue;
            }

            /* early exit is a zero is read */
            if(*locptr == 0x00) {
                folder->nrfiles = fctr;
                return;
            }

            /* check if we are reading a file or a folder, if so, add it */
            if((*(locptr + 0x0B) & 0x0F) == 0x00) {
                file = &buffer[fctr];
                memcpy(file->basename, locptr, 11); /* file name */
                file->termbyte = 0;	/* by definition */
                file->attrib = *(locptr + 0x0B);
                file->cluster = fat32_grab_cluster_address_from_fileblock(locptr);
                file->filesize = *(unsigned long*)(locptr + 0x1C);
                fctr++;
                /* printf("%i: %s %u bytes\n", fctr, file->basename, file->filesize); */

                /* throw error message if we exceed buffer size */
                if(fctr > F32MXFL) {
                    printf("ERROR: Too many files in folder; cannot parse.");
                    return;
                }
            }
            locptr += 32; /* next file entry */
	    }
	    caddr++; /* next sector */
	}
	ctr++; /* next cluster */
    }
    folder->nrfiles = fctr;
}

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
void fat32_set_current_folder(const struct FAT32File* entry) {
    if(entry->cluster == 0x00000000) { /* check for ROOT */
	    fat32_current_folder = fat32_root_folder;
    } else {
        fat32_current_folder.cluster = entry->cluster;
        fat32_current_folder.nrfiles = 0;
        memcpy(fat32_current_folder.name, entry->basename, 11);
    }

    fat32_read_current_folder();
}

/*
 *  fat32_get_current_folder - Copy the current folder state
 *
 *  Parameters:
 *      folder - Destination folder state
 */
void fat32_get_current_folder(struct FAT32Folder* folder) {
    *folder = fat32_current_folder;
}

/*
 *  fat32_set_current_folder_state - Restore the current folder state
 *
 *  Parameters:
 *      folder - Folder state to restore
 */
void fat32_set_current_folder_state(const struct FAT32Folder* folder) {
    fat32_current_folder = *folder;
    fat32_read_current_folder();
}

/**
 *  fat32_list_dir - Prints all files in folder to screen
 */
void fat32_list_dir() {
    unsigned int i=0;
    struct FAT32File *file = fat32_files;
    for(i=0; i<fat32_current_folder.nrfiles; ++i) {
        if(file->attrib & MASK_DIR) {
            printf("%.8s %.3s %08lX DIR\n", file->basename, file->extension, file->cluster);
        } else {
            printf("%.8s %.3s %08lX %lu\n", file->basename, file->extension, file->cluster, file->filesize);
        }
        file++;
    }
}

/**
 *  fat32_mkdir - Create a new directory on SD card
 *
 *  Parameters:
 *      dirname - Name of the directory to create
 */
int fat32_mkdir(const char* dirname) {
    unsigned i;
    unsigned long sectoraddr;
    unsigned long parentcluster;
    unsigned char* locptr;
    char fatname[11];
    unsigned long newcluster;

    /* build linked list */
    fat32_build_linked_list(fat32_current_folder.cluster);

    /* validate name */
    if(fat32_normalize_name_83(dirname, fatname) != 0) {
        return -1;
    }

    /* check the current directory for a matching entry */
    fat32_read_current_folder();
    for(i=0; i<fat32_nrfiles; ++i) {
        if(memcmp(fat32_files[i].basename, fatname, 11) == 0) {
            return -1;
        }
    }

    /* find a free cluster for the new directory's contents */
    newcluster = fat32_find_free_cluster();
    if(newcluster == 0) {
        return -1;
    }

    /* mark that new cluster as end of chain */
    if(fat32_write_fat_entry(newcluster, 0x0FFFFFFFUL) != 0) {
        return -1;
    }

    /* zero the new directory cluster's sectors */
    sectoraddr = fat32_calculate_sector_address(newcluster, 0);
    if(fat32_zero_cluster(newcluster) != 0) {
        return -1;
    }

    /* write its first two entries */
    parentcluster = fat32_current_folder.cluster;
    if(parentcluster == fat32_partition.root_dir_first_cluster) {
        parentcluster = 0;
    }

    locptr = sdbuf;
    memcpy(locptr, ".          ", 11); /* "." entry */
    *(locptr + 0x0B) = MASK_DIR;
    *(unsigned*)(locptr + 0x14) = (unsigned)(newcluster >> 16);
    *(unsigned*)(locptr + 0x1A) = (unsigned)(newcluster & 0xFFFF);

    locptr = sdbuf + 32;
    memcpy(locptr, "..         ", 11); /* ".." entry */
    *(locptr + 0x0B) = MASK_DIR;
    *(unsigned*)(locptr + 0x14) = (unsigned)(parentcluster >> 16);
    *(unsigned*)(locptr + 0x1A) = (unsigned)(parentcluster & 0xFFFF);

    if(fat32_write_sector(sectoraddr) != 0) {
        return -1;
    }

    /* write the new directory entry and refresh current folder */
    if(fat32_create_dir_entry(fatname, MASK_DIR, newcluster, 0) != 0) {
        return -1;
    }

    return 0;
}

/*
 *  fat32_get_file_entry - Get file from buffer identified by id
 *
 *  Parameters:
 *      id - Identifier
 *
 *  Retrieves pointer to FAT32File* struct identified by ID
 */
const struct FAT32File* fat32_get_file_entry(unsigned int id) {
    if(id < fat32_current_folder.nrfiles) {
	    return &fat32_files[id];
    } else {
	    return 0;
    }
}

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
					     unsigned char sector) {
    return fat32_partition.sector_begin_lba + (cluster - 2) *
	   fat32_partition.sectors_per_cluster + sector;
}

/*
 *  fat32_read_sector - Reads sector from SD-CARD
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 */
void fat32_read_sector(unsigned long addr) {
    cmd17(cfg_get_base_port(), addr, sdbuf);
}

/*
 *  fat32_read_sector_to - Reads sector from SD-CARD into caller buffer
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 *      buf  - Buffer to store sector data
 */
void fat32_read_sector_to(unsigned long addr, unsigned char* buf) {
    cmd17(cfg_get_base_port(), addr, buf);
}

/*
 *  fat32_write_sector - Write sector to SD-CARD
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 */
int fat32_write_sector(unsigned long addr) {
    unsigned char res;
    unsigned attempt;

    for(attempt=0; attempt<=FAT32_WRITE_RETRIES; ++attempt) {
        res = cmd24(cfg_get_base_port(), addr, sdbuf);
        if(res != 0) {
            continue;
        }

        res = cmd17(cfg_get_base_port(), addr, verifybuf);
        if(res != 0) {
            continue;
        }

        if(memcmp(sdbuf, verifybuf, 512) == 0) {
            return 0;
        }
    }

    return -1;
}

/*
 *  fat32_write_sector_from - Write sector to SD-CARD from caller buffer
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 *      buf  - Buffer containing sector data
 */
int fat32_write_sector_from(unsigned long addr, unsigned char* buf) {
    unsigned char res;
    unsigned attempt;

    for(attempt=0; attempt<=FAT32_WRITE_RETRIES; ++attempt) {
        res = cmd24(cfg_get_base_port(), addr, buf);
        if(res != 0) {
            continue;
        }

        res = cmd17(cfg_get_base_port(), addr, verifybuf);
        if(res != 0) {
            continue;
        }

        if(memcmp(buf, verifybuf, 512) == 0) {
            return 0;
        }
    }

    return -1;
}

/*
 *  fat32_sort_files - Sort files encountered in folder
 */
void fat32_sort_files() {
    qsort(fat32_files, fat32_current_folder.nrfiles, sizeof(struct FAT32File), fat32_file_compare);
}

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
int fat32_file_compare(const void* item1, const void* item2) {
    const struct FAT32File *file1 = (const struct FAT32File*)item1;
    const struct FAT32File *file2 = (const struct FAT32File*)item2;

    unsigned char is_dir1 = (file1->attrib & MASK_DIR) != 0;
    unsigned char is_dir2 = (file2->attrib & MASK_DIR) != 0;

    if(is_dir1 && !is_dir2) {
	    return -1;
    } else if(!is_dir1 && is_dir2) {
	    return 1;
    }

    return strcmp(file1->basename, file2->basename);
}

/*
 *  fat32_build_linked_list - Build linked list of clusters
 *
 *  Parameters:
 *      nextcluster - starting cluster in the linked list
 */
void fat32_build_linked_list(unsigned long nextcluster) {
    unsigned ctr = 0;
    unsigned item = 0;

    /* clear previous linked list */
    memset(fat32_linked_list, 0xFF, F32LLSZ * sizeof(unsigned long));

    while(nextcluster < 0x0FFFFFF8 && nextcluster != 0 && ctr < F32LLSZ) {
        fat32_linked_list[ctr] = nextcluster;
        fat32_read_sector(fat32_partition.fat_begin_lba + (nextcluster >> 7));
        item = nextcluster & 0x7F;
        nextcluster = *(unsigned long*)(sdbuf + item * 4);
        ctr++;
    }
}

/*
 *  fat32_grab_cluster_address_from_fileblock - Grab cluster address from sector data
 *
 *  Parameters:
 *      loc - Starting location of raw file entry in SD-CARD buffer
 *
 *  Returns:
 *      Starting cluster address of file
 */
unsigned long fat32_grab_cluster_address_from_fileblock(unsigned char* loc) {
    return ((unsigned long)*(unsigned*)(loc + 0x14)) << 16 |
           *(unsigned*)(loc + 0x1A);
}

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
int fat32_normalize_name_83(const char* input, char out[11]) {
    unsigned i;
    char c;

    if(input == 0 || input[0] == 0) {
        return -1;
    }

    memset(out, ' ', 11);

    for(i=0; input[i] != 0; ++i) {
        if(i >= 8) {
            return -1;
        }

        c = input[i];
        if(c >= 'a' && c <= 'z') {
            c -= 'a' - 'A';
        }

        if(!((c >= 'A' && c <= 'Z') ||
             (c >= '0' && c <= '9') ||
             c == '_' || c == '-' || c == '$' || c == '~')) {
            return -1;
        }

        out[i] = c;
    }

    if(out[0] == '.') {
        return -1;
    }

    return 0;
}

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
int fat32_normalize_file_83(const char* input, char out[11]) {
    unsigned i;
    unsigned o;
    unsigned ext;
    char c;

    if(input == 0 || input[0] == 0 || input[0] == '.') {
        return -1;
    }

    memset(out, ' ', 11);
    o = 0;
    ext = 0;

    for(i=0; input[i] != 0; ++i) {
        c = input[i];

        if(c == '.') {
            if(ext || o == 0 || input[i+1] == 0) {
                return -1;
            }
            ext = 1;
            o = 8;
            continue;
        }

        if(c >= 'a' && c <= 'z') {
            c -= 'a' - 'A';
        }

        if(!((c >= 'A' && c <= 'Z') ||
             (c >= '0' && c <= '9') ||
             c == '_' || c == '-' || c == '$' || c == '~')) {
            return -1;
        }

        if((!ext && o >= 8) || (ext && o >= 11)) {
            return -1;
        }

        out[o++] = c;
    }

    return 0;
}

/*
 *  fat32_find_free_cluster - Find the first unused data cluster
 *
 *  Returns:
 *      Cluster number, or 0 if no free cluster was found
 */
unsigned long fat32_find_free_cluster() {
    unsigned pass;
    unsigned long startcluster;
    unsigned long endcluster;
    unsigned long sector;
    unsigned long firstsector;
    unsigned long lastsector;
    unsigned long cluster;
    unsigned long entry;
    unsigned item;

    if(fat32_partition.next_free_cluster_hint < 2 ||
       fat32_partition.next_free_cluster_hint >= fat32_partition.cluster_count + 2) {
        fat32_partition.next_free_cluster_hint = 2;
    }

    startcluster = fat32_partition.next_free_cluster_hint;
    endcluster = fat32_partition.cluster_count + 2;

    for(pass=0; pass<2; ++pass) {
        if(pass == 0) {
            firstsector = startcluster >> 7;
            lastsector = (endcluster - 1) >> 7;
        } else {
            firstsector = 0;
            lastsector = (startcluster - 1) >> 7;
        }

        for(sector=firstsector; sector<=lastsector; ++sector) {

            /* read contents of the FAT sector */
            fat32_read_sector(fat32_partition.fat_begin_lba + sector);

            /* loop over all 128 4-byte entries in the FAT sector */
            for(item=0; item<128; ++item) {
                cluster = (sector << 7) + item;

                if(cluster < 2) {
                    continue;
                }

                if(pass == 0 && cluster < startcluster) {
                    continue;
                }

                if(pass == 1 && cluster >= startcluster) {
                    return 0;
                }

                if(cluster >= endcluster) {
                    break;
                }

                entry = *(unsigned long*)(sdbuf + item * 4);
                if((entry & 0x0FFFFFFFUL) == 0) {
                    fat32_partition.next_free_cluster_hint = cluster + 1;
                    if(fat32_partition.next_free_cluster_hint >= endcluster) {
                        fat32_partition.next_free_cluster_hint = 2;
                    }
                    return cluster;
                }
            }
        }
    }

    return 0;
}

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
int fat32_write_fat_entry(unsigned long cluster, unsigned long value) {
    unsigned i;
    unsigned item;
    unsigned long fatsector;
    unsigned long entry;
    unsigned long addr;

    if(cluster < 2 || cluster >= fat32_partition.cluster_count + 2) {
        return -1;
    }

    fatsector = cluster >> 7;
    item = (unsigned)(cluster & 0x7F);

    for(i=0; i<fat32_partition.number_of_fats; ++i) {
        addr = fat32_partition.fat_begin_lba +
               ((unsigned long)i * fat32_partition.sectors_per_fat) +
               fatsector;
        fat32_read_sector(addr);
        entry = *(unsigned long*)(sdbuf + item * 4);
        entry = (entry & 0xF0000000UL) | (value & 0x0FFFFFFFUL);
        *(unsigned long*)(sdbuf + item * 4) = entry;
        if(fat32_write_sector(addr) != 0) {
            return -1;
        }
    }

    if((value & 0x0FFFFFFFUL) == 0 &&
       cluster < fat32_partition.next_free_cluster_hint) {
        fat32_partition.next_free_cluster_hint = cluster;
    }

    return 0;
}

/*
 *  fat32_zero_cluster - Write zeroes to all sectors in a cluster
 *
 *  Parameters:
 *      cluster - Cluster to clear
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_zero_cluster(unsigned long cluster) {
    unsigned i;
    unsigned long caddr;

    if(cluster < 2 || cluster >= fat32_partition.cluster_count + 2) {
        return -1;
    }

    caddr = fat32_calculate_sector_address(cluster, 0);
    memset(sdbuf, 0x00, 514);

    for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
        if(fat32_write_sector(caddr + i) != 0) {
            return -1;
        }
    }

    return 0;
}

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
                           unsigned long filesize) {
    unsigned long entrysector;
    unsigned entryoffset;
    unsigned char* locptr;

    if(fat32_find_free_dir_entry(&fat32_current_folder,
                                 &entrysector,
                                 &entryoffset) != 0) {
        return -1;
    }

    fat32_read_sector(entrysector);
    locptr = sdbuf + entryoffset;
    memset(locptr, 0x00, 32);
    memcpy(locptr, name, 11);
    *(locptr + 0x0B) = attrib;
    *(unsigned*)(locptr + 0x14) = (unsigned)(firstcluster >> 16);
    *(unsigned*)(locptr + 0x1A) = (unsigned)(firstcluster & 0xFFFF);
    *(unsigned long*)(locptr + 0x1C) = filesize;
    if(fat32_write_sector(entrysector) != 0) {
        return -1;
    }

    fat32_read_current_folder();

    return 0;
}

/*
 *  fat32_delete_file_entry - Delete a file entry from the current directory
 *
 *  Parameters:
 *      name - 11-byte FAT 8.3 name
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_delete_file_entry(const char name[11]) {
    return fat32_delete_named_in_folder(&fat32_current_folder, name, 0);
}

/*
 *  fat32_delete_entry - Delete an entry from the current directory
 *
 *  Parameters:
 *      name - 11-byte FAT 8.3 name
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
int fat32_delete_entry(const char name[11]) {
    return fat32_delete_named_in_folder(&fat32_current_folder, name, 1);
}

/*
 *  fat32_delete_named_in_folder - Delete an entry from a folder
 *
 *  Parameters:
 *      folder   - Folder that contains the entry
 *      name     - 11-byte FAT 8.3 name
 *      allowdir - Nonzero to allow recursive folder deletion
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
static int fat32_delete_named_in_folder(struct FAT32Folder* folder,
                                        const char name[11],
                                        unsigned allowdir) {
    unsigned ctr;
    unsigned i;
    unsigned j;
    unsigned long caddr;
    unsigned long entrysector;
    unsigned entryoffset;
    unsigned long cluster;
    unsigned char* locptr;
    struct FAT32Folder child;
    char childname[11];

    fat32_build_linked_list(folder->cluster);

    ctr = 0;
    while(fat32_linked_list[ctr] != 0xFFFFFFFF && ctr < F32LLSZ) {
        caddr = fat32_calculate_sector_address(fat32_linked_list[ctr], 0);

        for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
            fat32_read_sector(caddr + i);
            locptr = sdbuf;

            for(j=0; j<16; ++j) {
                if(*locptr == 0x00) {
                    return -1;
                }

                if(*locptr != 0xE5 &&
                   (*(locptr + 0x0B) & 0x0F) == 0x00 &&
                   memcmp(locptr, name, 11) == 0) {
                    entrysector = caddr + i;
                    entryoffset = j * 32;
                    cluster = fat32_grab_cluster_address_from_fileblock(locptr);

                    if(*(locptr + 0x0B) & MASK_DIR) {
                        if(!allowdir) {
                            return -1;
                        }

                        memset(&child, 0x00, sizeof(struct FAT32Folder));
                        memcpy(child.name, locptr, 11);
                        child.cluster = cluster;

                        while(fat32_find_first_deletable_entry(&child,
                                                               childname) == 0) {
                            if(fat32_delete_named_in_folder(&child,
                                                            childname,
                                                            1) != 0) {
                                return -1;
                            }
                        }
                    }

                    fat32_read_sector(entrysector);
                    locptr = sdbuf + entryoffset;
                    *locptr = 0xE5;
                    if(fat32_write_sector(entrysector) != 0) {
                        return -1;
                    }

                    if(fat32_free_cluster_chain(cluster) != 0) {
                        return -1;
                    }

                    fat32_read_current_folder();
                    return 0;
                }

                locptr += 32;
            }
        }

        ctr++;
    }

    return -1;
}

/*
 *  fat32_find_first_deletable_entry - Find first child entry in a folder
 *
 *  Parameters:
 *      folder - Folder to scan
 *      name   - 11-byte FAT 8.3 name destination
 *
 *  Returns:
 *      0 if an entry was found, -1 otherwise
 */
static int fat32_find_first_deletable_entry(struct FAT32Folder* folder,
                                            char name[11]) {
    unsigned ctr;
    unsigned i;
    unsigned j;
    unsigned long caddr;
    unsigned char* locptr;

    fat32_build_linked_list(folder->cluster);

    ctr = 0;
    while(fat32_linked_list[ctr] != 0xFFFFFFFF && ctr < F32LLSZ) {
        caddr = fat32_calculate_sector_address(fat32_linked_list[ctr], 0);

        for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
            fat32_read_sector(caddr + i);
            locptr = sdbuf;

            for(j=0; j<16; ++j) {
                if(*locptr == 0x00) {
                    return -1;
                }

                if(*locptr != 0xE5 &&
                   (*(locptr + 0x0B) & 0x0F) == 0x00 &&
                   memcmp(locptr, ".          ", 11) != 0 &&
                   memcmp(locptr, "..         ", 11) != 0) {
                    memcpy(name, locptr, 11);
                    return 0;
                }

                locptr += 32;
            }
        }

        ctr++;
    }

    return -1;
}

/*
 *  fat32_free_cluster_chain - Mark all clusters in a chain free
 *
 *  Parameters:
 *      cluster - First cluster in the chain
 *
 *  Returns:
 *      0 on success, -1 otherwise
 */
static int fat32_free_cluster_chain(unsigned long cluster) {
    unsigned item;
    unsigned long nextcluster;
    unsigned long entry;

    while(cluster >= 2 && cluster < 0x0FFFFFF8UL) {
        fat32_read_sector(fat32_partition.fat_begin_lba + (cluster >> 7));
        item = (unsigned)(cluster & 0x7F);
        entry = *(unsigned long*)(sdbuf + item * 4);
        nextcluster = entry & 0x0FFFFFFFUL;

        if(fat32_write_fat_entry(cluster, 0) != 0) {
            return -1;
        }

        cluster = nextcluster;
    }

    return 0;
}

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
                              unsigned* entryoffset) {
    unsigned ctr;
    unsigned i;
    unsigned j;
    unsigned long caddr;
    unsigned long lastcluster;
    unsigned long newcluster;
    unsigned char* locptr;

    fat32_build_linked_list(folder->cluster);

    ctr = 0;
    lastcluster = 0;
    while(fat32_linked_list[ctr] != 0xFFFFFFFF && ctr < F32LLSZ) {
        lastcluster = fat32_linked_list[ctr];
        caddr = fat32_calculate_sector_address(lastcluster, 0);

        for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
            fat32_read_sector(caddr + i);
            locptr = sdbuf;

            for(j=0; j<16; ++j) {
                if(*locptr == 0xE5 || *locptr == 0x00) {
                    *entrysector = caddr + i;
                    *entryoffset = j * 32;
                    return 0;
                }
                locptr += 32;
            }
        }

        ctr++;
    }

    if(lastcluster == 0) {
        return -1;
    }

    newcluster = fat32_find_free_cluster();
    if(newcluster == 0) {
        return -1;
    }

    if(fat32_write_fat_entry(lastcluster, newcluster) != 0) {
        return -1;
    }

    if(fat32_write_fat_entry(newcluster, 0x0FFFFFFFUL) != 0) {
        return -1;
    }

    caddr = fat32_calculate_sector_address(newcluster, 0);
    if(fat32_zero_cluster(newcluster) != 0) {
        return -1;
    }

    *entrysector = caddr;
    *entryoffset = 0;

    return 0;
}














