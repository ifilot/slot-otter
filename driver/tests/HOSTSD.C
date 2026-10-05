/* Test-only disk transport; not linked into the DOS utility. */
#include "OTTER.H"
#include <stdio.h>
static FILE *image;
U32 fault_lba = 0xffffffffU;
unsigned reads;
int fault_code=-1;
int test_present=1, test_changed;
U16 sd_port=0x330;
int sd_init(void) { test_changed=0; return test_present?0:-1; }
int sd_check_media(void) { return test_present && !test_changed?0:-1; }
void sd_release(void) { }
int test_open(const char *path) {
    if (image) fclose(image);
    image=fopen(path,"rb"); fault_lba=0xffffffffU; reads=0; fault_code=-1;
    test_present=1; test_changed=0;
    if (image) setvbuf(image,0,_IONBF,0);
    return image ? 0 : -1;
}
int sd_read(U32 lba, U8 *buffer) {
    ++reads;
    if (lba==fault_lba) return fault_code;
    if (fseek(image,(long)lba*512,SEEK_SET)) return -1;
    return fread(buffer,1,512,image)==512 ? 0 : -1;
}
