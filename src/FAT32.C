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

/* buffer to store SDCARD sector data including CRC checksum */
static unsigned char sdbuf[514];
/* store linked list of cluster addresses */
static unsigned long fat32_linked_list[F32LLSZ];
/* total number of files in the currently active folder */
unsigned int fat32_nrfiles;

struct FAT32Partition fat32_partition;
struct FAT32Folder fat32_root_folder;
struct FAT32Folder fat32_current_folder;
struct FAT32File fat32_files[F32MXFL];
struct FAT32File fat32_folder_contents[F32MXFL];

/**
 *  fat32_open_partition - Open FAT32 partition
 *
 *  Tries to open the first partition on the SD-CARD as a FAT32 partition.
 *  Sets the ROOT directory as the current directory.
 */
void fat32_open_partition() {
    unsigned long lba = 0x00000000;
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
int fat32_transfer_file(const struct FAT32File *f, const char* path) {
    unsigned long caddr = 0;
    unsigned long cluster = 0;
    unsigned long nextcluster = 0;
    unsigned long bcnt = 0;
    int i;
    unsigned item = 0;
    FILE *outfile;

    if(f->attrib & MASK_DIR) {
	    return -1;
    }

    outfile = fopen(path, "wb");
    if(outfile == NULL) {
        return -1;
    }

    /* consume clusters and transfer file */
    cluster = f->cluster;
    while(cluster < 0x0FFFFFF8UL && cluster != 0 && bcnt < f->filesize) {
        caddr = fat32_calculate_sector_address(cluster, 0);

        /* consume sectors */
        for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
            fat32_read_sector(caddr);

            if((f->filesize - bcnt) > 512) {
                fwrite(sdbuf, sizeof(char), 512, outfile);
            } else {
                fwrite(sdbuf, sizeof(char), f->filesize - bcnt, outfile);
                break;
            }

            bcnt += 512;
            caddr++; /* next sector */
        }

        fat32_read_sector(fat32_partition.fat_begin_lba + (cluster >> 7));
        item = (unsigned)(cluster & 0x7F);
        nextcluster = (*(unsigned long*)(sdbuf + item * 4)) & 0x0FFFFFFFUL;
        cluster = nextcluster;
    }

    fclose(outfile);

    return 0;
}


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
void fat32_transfer_folder(const struct FAT32File* f) {
    static struct FAT32Folder folders[F32MXDIR];
    unsigned nrfolders = 1;
    unsigned newfolders = 1;
    unsigned startfolder = 0;
    unsigned i,j,k;
    const struct FAT32File* fptr;
    char path[MAXPATH];
    int ret;

    /* initialize iterative procedure */
    memcpy(folders[0].name, f->basename, 11);
    folders[0].cluster = f->cluster;
    folders[0].nrfiles = 0;
    folders[0].attrib = 0x00;
    folders[0].reference = -1;

    /* recursively go over the folders until no unscanned folders are found */
    while(newfolders != 0) {
        startfolder = nrfolders - newfolders;
        newfolders = 0;
        for(i=startfolder; i<nrfolders; ++i) {
            /* read folder contents */
            fat32_read_dir(&folders[i], fat32_folder_contents);

            /* loop over files and look for subfolders */
            for(j=0; j<folders[i].nrfiles; ++j) {
            fptr = &fat32_folder_contents[j];

            /* skip self and parent folder */
            if(memcmp(fptr->basename, ".       ", 8) == 0 ||
                memcmp(fptr->basename, "..      ", 8) == 0) {
                continue;
            }

            /* if entry is a folder, add it to the list */
            if(fat32_folder_contents[j].attrib & MASK_DIR) {
                memcpy(folders[nrfolders].name, fptr->basename, 11);
                folders[nrfolders].cluster = fptr->cluster;
                folders[nrfolders].attrib = 0x00;
                folders[nrfolders].nrfiles = 0;
                folders[nrfolders].reference = i;
                newfolders++;
                nrfolders++;
            }
            }
            /* tag folder as being scanned */
            folders[i].attrib = 0x01;
        }
    }

    store_screen();
    clrscr();
    gotoxy(1,1);
    printf("START TRANSFER...\n");
    
    for(i=0; i<nrfolders; ++i) {
        fat32_build_path(folders, i, path);
        printf(">> DIR: %s", path);

        if(folder_exists(path)) {
            printf(" [EXISTS]\n");
        } else {
            ret = mkdir(path);

            if(ret == 0) {
                printf(" [CREATED]\n");
            } else {
                printf(" [ERROR]\n");
                return;
            }
        }

        /* if no errors were encountered creating the folder, start
           transferring all the files */
        fat32_transfer_files_in_folder(&folders[i], path);
    }
    
    printf("-- Transfer complete, press any key to return to navigator. --");
    getch();
    restore_screen();
}

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
void fat32_build_path(struct FAT32Folder folders[], unsigned id, char path[]) {
    unsigned ll[20];
    unsigned i,N;
    unsigned n;
    const char* name;
    const char* p;

    /* construct linked list */
    ll[0] = id;
    i = 0;

    /* populate linked list */
    while(folders[ll[i]].reference != -1 && i<20) {
        i++;
        ll[i] = (unsigned)folders[ll[i-1]].reference;
    }

    N = i+1; /* number of path sections */

    /* build path */
    memset(path, 0x00, MAXPATH);
    n = 0;
    for(i=0; i<N; ++i) {
        name = folders[ll[N-i-1]].name;
        p = (const char*)strchr(name, (int)' ');
        memcpy(&path[n], name, (size_t)(p - name));
        n += (unsigned)(p - name);
        path[n++] = '\\';
    }

    path[--n] = 0; /* remove trailing slash */
}

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
void fat32_transfer_files_in_folder(struct FAT32Folder* f, const char *basepath) {
    unsigned i;
    const struct FAT32File* entry;
    char path[MAXPATH];
    char filename[13];
    char c;
    unsigned ok = 0;
    unsigned persistent = 0;
    clock_t tic, toc;

    /* read folder */
    fat32_read_dir(f, fat32_folder_contents);

    for(i=0; i<f->nrfiles; ++i) {
        entry = &fat32_folder_contents[i];
        if(entry->attrib & MASK_DIR) {
            continue;
        } else {
            ok = 1;
            strcpy(path, basepath);
            strcat(path, "\\");
            build_dos_filename(entry, filename);
            strcat(path, filename);
            cprintf(" + File: %s", path);
            if(file_exists(path)) {
                ok = 0;
                if(!persistent) {
                    cprintf("\n File exists; Overwrite? (y/n/a)");
                    while(1) {
                    c = getch();
                    if(c == 'y') {
                        putch(c);
                        ok = 1;
                        break;
                    } else if(c == 'n') {
                        putch(c);
                        printf(" [SKIP]\n");
                        break;
                    } else if(c == 'a') {
                        putch(c);
                        persistent = 1;
                        ok = 1;
                        break;
                    }
                    }
                } else {
                    printf(" (A) ");
                    ok = 1; /* ok is always true when persistent is 1 */
                }
            }

            if(ok == 1) {
                tic = clock();
                if(fat32_transfer_file(entry, path) == 0) {
                    toc = clock();
                    cprintf(" (%lu bytes; %.2f s) ", entry->filesize,(toc - tic) / CLK_TCK);
                    textcolor(LIGHTGREEN);
                    cprintf("[OK]");
                    textcolor(WHITE);
                    cprintf("\r\n");
                } else {
                    textcolor(RED);
                    cprintf(" [FAIL]");
                    textcolor(WHITE);
                    cprintf("\r\n");
                }
            }
        }
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
    unsigned item;
    unsigned long fatsector;
    unsigned long entry;
    unsigned long sectoraddr;
    unsigned long parentcluster;
    unsigned long parententrysector;
    unsigned parententryoffset;
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
    fatsector = newcluster >> 7;
    item = (unsigned)(newcluster & 0x7F);
    for(i=0; i<fat32_partition.number_of_fats; ++i) { /* loop over all FATs */
        fat32_read_sector(fat32_partition.fat_begin_lba +
                          ((unsigned long)i * fat32_partition.sectors_per_fat) +
                          fatsector);
        entry = *(unsigned long*)(sdbuf + item * 4);
        entry = (entry & 0xF0000000UL) | 0x0FFFFFFFUL;
        *(unsigned long*)(sdbuf + item * 4) = entry;
        fat32_write_sector(fat32_partition.fat_begin_lba +
                           ((unsigned long)i * fat32_partition.sectors_per_fat) +
                           fatsector);
    }

    /* zero the new directory cluster's sectors */
    sectoraddr = fat32_calculate_sector_address(newcluster, 0);
    memset(sdbuf, 0x00, 514);
    for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
        fat32_write_sector(sectoraddr + i);
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

    fat32_write_sector(sectoraddr);

    /* find a free 32-byte entry in the parent directory chain */
    if(fat32_find_free_dir_entry(&fat32_current_folder,
                                 &parententrysector,
                                 &parententryoffset) != 0) {
        return -1;
    }

    /* write the new directory entry */
    fat32_read_sector(parententrysector);
    locptr = sdbuf + parententryoffset;
    memset(locptr, 0x00, 32);
    memcpy(locptr, fatname, 11);
    *(locptr + 0x0B) = MASK_DIR;
    *(unsigned*)(locptr + 0x14) = (unsigned)(newcluster >> 16);
    *(unsigned*)(locptr + 0x1A) = (unsigned)(newcluster & 0xFFFF);
    fat32_write_sector(parententrysector);

    /* refresh current folder */
    fat32_read_current_folder();
    
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
 *  fat32_write_sector - Write sector to SD-CARD
 *
 *  Parameters:
 *      addr - SD-CARD sector address
 */
void fat32_write_sector(unsigned long addr) {
    cmd24(cfg_get_base_port(), addr, sdbuf);
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
 *  fat32_find_free_cluster - Find the first unused data cluster
 *
 *  Returns:
 *      Cluster number, or 0 if no free cluster was found
 */
unsigned long fat32_find_free_cluster() {
    unsigned long sector;
    unsigned long cluster;
    unsigned long entry;
    unsigned item;

    /* loop over all sectors in the FAT */
    for(sector=0; sector<fat32_partition.sectors_per_fat; ++sector) {

        /* read contents of the FAT sector */
        fat32_read_sector(fat32_partition.fat_begin_lba + sector);

        /* loop over all 128 x 8-byte entries in the FAT sector */
        for(item=0; item<128; ++item) {
            cluster = (sector << 7) + item;

            if(cluster < 2) {
                continue;
            }

            if(cluster >= fat32_partition.cluster_count + 2) {
                return 0;
            }

            entry = *(unsigned long*)(sdbuf + item * 4);
            if((entry & 0x0FFFFFFFUL) == 0) {
                return cluster;
            }
        }
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
    unsigned item;
    unsigned long caddr;
    unsigned long lastcluster;
    unsigned long newcluster;
    unsigned long fatsector;
    unsigned long entry;
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

    for(i=0; i<fat32_partition.number_of_fats; ++i) {
        fatsector = lastcluster >> 7;
        item = (unsigned)(lastcluster & 0x7F);
        fat32_read_sector(fat32_partition.fat_begin_lba +
                          ((unsigned long)i * fat32_partition.sectors_per_fat) +
                          fatsector);
        entry = *(unsigned long*)(sdbuf + item * 4);
        entry = (entry & 0xF0000000UL) | newcluster;
        *(unsigned long*)(sdbuf + item * 4) = entry;
        fat32_write_sector(fat32_partition.fat_begin_lba +
                           ((unsigned long)i * fat32_partition.sectors_per_fat) +
                           fatsector);

        fatsector = newcluster >> 7;
        item = (unsigned)(newcluster & 0x7F);
        fat32_read_sector(fat32_partition.fat_begin_lba +
                          ((unsigned long)i * fat32_partition.sectors_per_fat) +
                          fatsector);
        entry = *(unsigned long*)(sdbuf + item * 4);
        entry = (entry & 0xF0000000UL) | 0x0FFFFFFFUL;
        *(unsigned long*)(sdbuf + item * 4) = entry;
        fat32_write_sector(fat32_partition.fat_begin_lba +
                           ((unsigned long)i * fat32_partition.sectors_per_fat) +
                           fatsector);
    }

    caddr = fat32_calculate_sector_address(newcluster, 0);
    memset(sdbuf, 0x00, 514);
    for(i=0; i<fat32_partition.sectors_per_cluster; ++i) {
        fat32_write_sector(caddr + i);
    }

    *entrysector = caddr;
    *entryoffset = 0;

    return 0;
}




