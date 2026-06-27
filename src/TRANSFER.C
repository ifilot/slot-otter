/* =====================================================================
 *  Project: SLOT-OTTER
 *  File:    TRANSFER.C
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

#include "transfer.h"
#include "helpers.h"
#include <conio.h>
#include <dir.h>
#include <stdio.h>
#include <string.h>
#include <time.h>

static unsigned char transfer_sdbuf[514];
static struct FAT32File transfer_folder_contents[F32MXFL];
static unsigned transfer_hd_overwrite_all;

static int transfer_find_sd_entry(const char fatname[11],
                                  struct FAT32File* out);
static int transfer_enter_sd_folder(const char* dirname,
                                    struct FAT32Folder* parent);
static int transfer_hd_folder_to_sd_inner(const struct HDNavFile* f);
static int transfer_hd_file_to_sd_prompt(const struct HDNavFile* f,
                                         unsigned* persistent);

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
int transfer_sd_file_to_hd(const struct FAT32File *f, const char* path) {
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
            fat32_read_sector_to(caddr, transfer_sdbuf);

            if((f->filesize - bcnt) > 512) {
                fwrite(transfer_sdbuf, sizeof(char), 512, outfile);
            } else {
                fwrite(transfer_sdbuf, sizeof(char), f->filesize - bcnt, outfile);
                break;
            }

            bcnt += 512;
            caddr++; /* next sector */
        }

        fat32_read_sector_to(fat32_partition.fat_begin_lba + (cluster >> 7),
                             transfer_sdbuf);
        item = (unsigned)(cluster & 0x7F);
        nextcluster = (*(unsigned long*)(transfer_sdbuf + item * 4)) & 0x0FFFFFFFUL;
        cluster = nextcluster;
    }

    fclose(outfile);

    return 0;
}

/**
 *  transfer_sd_folder_to_hd - Recursively transfer a folder from SD to hard drive
 *
 *  Parameters:
 *      f    - Pointer to FAT32File* corresponding to a folder
 */
void transfer_sd_folder_to_hd(const struct FAT32File* f) {
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
            fat32_read_dir(&folders[i], transfer_folder_contents);

            /* loop over files and look for subfolders */
            for(j=0; j<folders[i].nrfiles; ++j) {
            fptr = &transfer_folder_contents[j];

            /* skip self and parent folder */
            if(memcmp(fptr->basename, ".       ", 8) == 0 ||
                memcmp(fptr->basename, "..      ", 8) == 0) {
                continue;
            }

            /* if entry is a folder, add it to the list */
            if(transfer_folder_contents[j].attrib & MASK_DIR) {
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
        transfer_build_sd_path(folders, i, path);
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
        transfer_sd_files_in_folder_to_hd(&folders[i], path);
    }

    printf("-- Transfer complete, press any key to return to navigator. --");
    getch();
    restore_screen();
}

/**
 *  transfer_build_sd_path - Construct a subpath from a folder list using identifier
 *
 *  Parameters:
 *      folders    - Array of FAT32Folder to copy
 *      id         - Index of folder to construct path for
 *      path       - Subpath
 */
void transfer_build_sd_path(struct FAT32Folder folders[], unsigned id, char path[]) {
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
 *  transfer_sd_files_in_folder_to_hd - Copies all files in an SD folder
 *
 *  Parameters:
 *      f           - Pointer to FAT32Folder struct
 *      basepath    - Destination to copy folder to
 */
void transfer_sd_files_in_folder_to_hd(struct FAT32Folder* f, const char *basepath) {
    unsigned i;
    const struct FAT32File* entry;
    char path[MAXPATH];
    char filename[13];
    char c;
    unsigned ok = 0;
    unsigned persistent = 0;
    clock_t tic, toc;

    /* read folder */
    fat32_read_dir(f, transfer_folder_contents);

    for(i=0; i<f->nrfiles; ++i) {
        entry = &transfer_folder_contents[i];
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
                if(transfer_sd_file_to_hd(entry, path) == 0) {
                    toc = clock();
                    cprintf(" (%lu bytes; %.2f s) ", entry->filesize,
                            (float)(toc - tic) / CLK_TCK);
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
 *  transfer_hd_file_to_sd - Transfer a single file from hard drive to SD
 *
 *  Parameters:
 *      f - Pointer to HDNavFile struct
 *
 *  Returns:
 *      0 on success
 */
int transfer_hd_file_to_sd(const struct HDNavFile* f) {
    FILE* infile;
    char fatname[11];
    unsigned i;
    unsigned sector;
    unsigned long remaining;
    unsigned long firstcluster;
    unsigned long currentcluster;
    unsigned long nextcluster;
    unsigned long caddr;
    unsigned long nread;
    const struct FAT32File* entry;

    if(f->attrib & HDNAV_MASK_DIR) {
        return -1;
    }

    if(fat32_normalize_file_83(f->filename, fatname) != 0) {
        return -1;
    }

    fat32_read_current_folder();
    for(i=0; i<fat32_nrfiles; ++i) {
        entry = fat32_get_file_entry(i);
        if(entry != 0 && memcmp(entry->basename, fatname, 11) == 0) {
            return -1;
        }
    }

    infile = fopen(f->filename, "rb");
    if(infile == NULL) {
        return -1;
    }

    if(f->filesize == 0) {
        fclose(infile);
        return fat32_create_dir_entry(fatname, 0x20, 0, 0);
    }

    firstcluster = fat32_find_free_cluster();
    if(firstcluster == 0) {
        fclose(infile);
        return -1;
    }

    if(fat32_write_fat_entry(firstcluster, 0x0FFFFFFFUL) != 0) {
        fclose(infile);
        return -1;
    }

    currentcluster = firstcluster;
    remaining = f->filesize;

    while(remaining > 0) {
        caddr = fat32_calculate_sector_address(currentcluster, 0);

        for(sector=0; sector<fat32_partition.sectors_per_cluster && remaining>0; ++sector) {
            memset(transfer_sdbuf, 0x00, 514);

            if(remaining > 512) {
                nread = 512;
            } else {
                nread = remaining;
            }

            if(fread(transfer_sdbuf, sizeof(char), nread, infile) != nread) {
                fclose(infile);
                return -1;
            }

            if(fat32_write_sector_from(caddr + sector, transfer_sdbuf) != 0) {
                fclose(infile);
                return -1;
            }
            remaining -= nread;
        }

        if(remaining > 0) {
            nextcluster = fat32_find_free_cluster();
            if(nextcluster == 0) {
                fclose(infile);
                return -1;
            }

            if(fat32_write_fat_entry(currentcluster, nextcluster) != 0) {
                fclose(infile);
                return -1;
            }

            if(fat32_write_fat_entry(nextcluster, 0x0FFFFFFFUL) != 0) {
                fclose(infile);
                return -1;
            }

            currentcluster = nextcluster;
        }
    }

    fclose(infile);

    return fat32_create_dir_entry(fatname, 0x20, firstcluster, f->filesize);
}

/*
 *  transfer_hd_file_to_sd_ui - Transfer a file from hard drive to SD with UI
 *
 *  Parameters:
 *      f - Pointer to HDNavFile struct
 *
 *  Returns:
 *      0 on success
 */
int transfer_hd_file_to_sd_ui(const struct HDNavFile* f) {
    unsigned persistent = 0;
    int ret;

    store_screen();
    clrscr();
    gotoxy(1,1);
    cprintf("START TRANSFER...\r\n");

    ret = transfer_hd_file_to_sd_prompt(f, &persistent);

    if(ret < 0) {
        cprintf("-- Transfer failed, press any key to return to navigator. --");
    } else {
        cprintf("-- Transfer complete, press any key to return to navigator. --");
    }
    getch();
    restore_screen();

    return ret < 0 ? -1 : 0;
}

/*
 *  transfer_hd_folder_to_sd - Transfer a folder from hard drive to SD
 *
 *  Parameters:
 *      f - Pointer to HDNavFile struct
 *
 *  Returns:
 *      0 on success
 */
int transfer_hd_folder_to_sd(const struct HDNavFile* f) {
    char cwd[128];
    struct FAT32Folder sdfolder;
    int ret;

    if(!(f->attrib & HDNAV_MASK_DIR)) {
        return -1;
    }

    getcwd(cwd, sizeof(cwd));
    fat32_get_current_folder(&sdfolder);

    store_screen();
    clrscr();
    gotoxy(1,1);
    cprintf("START TRANSFER...\r\n");

    transfer_hd_overwrite_all = 0;
    ret = transfer_hd_folder_to_sd_inner(f);

    chdir(cwd);
    fat32_set_current_folder_state(&sdfolder);

    if(ret == 0) {
        cprintf("-- Transfer complete, press any key to return to navigator. --");
    } else {
        cprintf("-- Transfer failed, press any key to return to navigator. --");
    }
    getch();
    restore_screen();

    return ret;
}

/*
 *  transfer_hd_folder_to_sd_inner - Recursive HD to SD folder transfer
 *
 *  Parameters:
 *      f - Folder entry in the current hard-drive folder
 *
 *  Returns:
 *      0 on success
 */
static int transfer_hd_folder_to_sd_inner(const struct HDNavFile* f) {
    struct FAT32Folder parentsd;
    struct ffblk file;
    struct HDNavFile child;
    int done;
    int ret = 0;

    if(transfer_enter_sd_folder(f->filename, &parentsd) != 0) {
        cprintf(">> DIR: %s [FAIL]\r\n", f->filename);
        return -1;
    }

    cprintf(">> DIR: %s [OK]\r\n", f->filename);

    if(chdir(f->filename) != 0) {
        fat32_set_current_folder_state(&parentsd);
        return -1;
    }

    done = findfirst("*.*", &file, FA_NORMAL | FA_DIREC);
    while(!done) {
        if(strcmp(file.ff_name, ".") != 0 &&
           strcmp(file.ff_name, "..") != 0) {
            strcpy(child.filename, file.ff_name);
            child.attrib = file.ff_attrib;
            child.filesize = file.ff_fsize;

            if(child.attrib & HDNAV_MASK_DIR) {
                if(transfer_hd_folder_to_sd_inner(&child) != 0) {
                    ret = -1;
                    break;
                }
            } else {
                if(transfer_hd_file_to_sd_prompt(&child,
                                                 &transfer_hd_overwrite_all) < 0) {
                    ret = -1;
                    break;
                }
            }
        }

        done = findnext(&file);
    }

    chdir("..");
    fat32_set_current_folder_state(&parentsd);

    return ret;
}

/*
 *  transfer_hd_file_to_sd_prompt - Copy one HD file to SD with prompt/timing
 *
 *  Parameters:
 *      f          - File to copy
 *      persistent - Overwrite-all flag shared by a folder transfer
 *
 *  Returns:
 *      0 on copied, 1 on skipped, -1 on failure
 */
static int transfer_hd_file_to_sd_prompt(const struct HDNavFile* f,
                                         unsigned* persistent) {
    char fatname[11];
    struct FAT32File entry;
    char c;
    unsigned ok = 1;
    clock_t tic, toc;

    cprintf(" + File: %s", f->filename);

    if(fat32_normalize_file_83(f->filename, fatname) != 0) {
        textcolor(RED);
        cprintf(" [FAIL]");
        textcolor(WHITE);
        cprintf("\r\n");
        return -1;
    }

    if(transfer_find_sd_entry(fatname, &entry) == 0) {
        ok = 0;
        if(entry.attrib & MASK_DIR) {
            textcolor(RED);
            cprintf(" [FAIL]");
            textcolor(WHITE);
            cprintf("\r\n");
            return -1;
        }

        if(!*persistent) {
            cprintf("\r\n File exists; Overwrite? (y/n/a)");
            while(1) {
                c = getch();
                if(c == 'y') {
                    putch(c);
                    ok = 1;
                    break;
                } else if(c == 'n') {
                    putch(c);
                    cprintf(" [SKIP]\r\n");
                    return 1;
                } else if(c == 'a') {
                    putch(c);
                    *persistent = 1;
                    ok = 1;
                    break;
                }
            }
        } else {
            cprintf(" (A) ");
            ok = 1;
        }

        if(ok && fat32_delete_file_entry(fatname) != 0) {
            textcolor(RED);
            cprintf(" [FAIL]");
            textcolor(WHITE);
            cprintf("\r\n");
            return -1;
        }
    }

    tic = clock();
    if(transfer_hd_file_to_sd(f) == 0) {
        toc = clock();
        cprintf(" (%lu bytes; %.2f s) ", f->filesize,
                (float)(toc - tic) / CLK_TCK);
        textcolor(LIGHTGREEN);
        cprintf("[OK]");
        textcolor(WHITE);
        cprintf("\r\n");
        return 0;
    }

    textcolor(RED);
    cprintf(" [FAIL]");
    textcolor(WHITE);
    cprintf("\r\n");

    return -1;
}

/*
 *  transfer_find_sd_entry - Find an SD entry by raw 8.3 name
 *
 *  Parameters:
 *      fatname - 11-byte FAT 8.3 name
 *      out     - Destination entry if found
 *
 *  Returns:
 *      0 if found
 */
static int transfer_find_sd_entry(const char fatname[11],
                                  struct FAT32File* out) {
    unsigned i;
    const struct FAT32File* entry;

    fat32_read_current_folder();
    for(i=0; i<fat32_nrfiles; ++i) {
        entry = fat32_get_file_entry(i);
        if(entry != 0 && memcmp(entry->basename, fatname, 11) == 0) {
            *out = *entry;
            return 0;
        }
    }

    return -1;
}

/*
 *  transfer_enter_sd_folder - Create or enter a matching SD folder
 *
 *  Parameters:
 *      dirname - DOS folder name
 *      parent  - Destination for saved parent SD folder state
 *
 *  Returns:
 *      0 on success
 */
static int transfer_enter_sd_folder(const char* dirname,
                                    struct FAT32Folder* parent) {
    char fatname[11];
    struct FAT32File entry;

    if(fat32_normalize_name_83(dirname, fatname) != 0) {
        return -1;
    }

    fat32_get_current_folder(parent);

    if(transfer_find_sd_entry(fatname, &entry) == 0) {
        if(!(entry.attrib & MASK_DIR)) {
            return -1;
        }
    } else {
        if(fat32_mkdir(dirname) != 0) {
            return -1;
        }
        if(transfer_find_sd_entry(fatname, &entry) != 0) {
            return -1;
        }
    }

    fat32_set_current_folder(&entry);

    return 0;
}





