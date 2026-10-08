/* Exercise actual SD.C and SDCMDS.ASM in DOS with guards and test-only CS latch. */
#include "OTTER.H"
#include <stdio.h>
#include <string.h>
static unsigned failures;
static struct { U8 before[8], data[512], after[8]; } block;
static void check(int ok, char *what) {
    printf("%s: %s\n",ok?"PASS":"FAIL",what); fflush(stdout);
    if(!ok) ++failures;
}
static int guards(void) {
    unsigned i;
    for(i=0;i<8;++i) if(block.before[i]!=0xa5 || block.after[i]!=0xa5) return 0;
    return 1;
}
int main(void) {
    int result;
    unsigned selected;
    /* Fixture README lives at partition2048+reserved32+2*FAT547+2. */
    check(sd_init()==0,"initialize standalone transport");
    memset(&block,0xa5,sizeof(block));
    result=sd_read(3176UL,block.data); selected=inportb(0x334);
    check(result==0 && !memcmp(block.data,"Hello from Slot-otter!\r\n",24),"read sector through actual CMD17 assembly");
    check(guards(),"CMD17 leaves destination guard bytes intact");
    check(selected==0,"successful CMD17 deselects card");
    memset(&block,0xa5,sizeof(block));
    result=sd_read(0xffffffffUL,block.data); selected=inportb(0x334);
    check(result==E_READ && guards(),"CMD17 failure preserves guard bytes");
    check(selected==0,"failed CMD17 deselects card");
    outportb(0x334,0);
    check(sd_read(0,block.data)==E_NOTREADY && guards(),"missing-card transport error");
    outportb(0x334,1); sd_release();
    printf("SD RESULT: %u failures\n",failures);
    return failures?1:0;
}
