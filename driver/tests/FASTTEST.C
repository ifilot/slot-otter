/* Private native oracle for the actual FASTIO.OBJ. GPL-3.0-or-later. */
#include "RWSD.H"
#include <stdio.h>
#include <string.h>
static U8 source[1030], target[1030];
static U8 original[512];
extern U16 fast_crc_abi(const U8 *p,U16 count);
extern U16 fast_copy_abi(U8 FAR *dest,const U8 FAR *src,U16 count);
static U16 failures;
static U16 oracle(const U8 *p,U16 count) {
    U16 crc=0,i;
    while (count--) {
        crc^=(U16)*p++<<8;
        for (i=0;i<8;++i) crc=(U16)((crc<<1)^((crc&0x8000)?0x1021:0));
    }
    return crc;
}
static void check(int yes,const char *name) {
    if (!yes) { printf("FAIL: %s\n",name); ++failures; }
}
int main(void) {
    U16 i,a,b,n,offset,j,bad;
    U32 value;
    static U16 counts[]={0,1,2,3,16,31,255,511,512,513,1024};
    memcpy(source+1,"123456789",9);
    check(sd_crc16(source+1,9)==0x31c3,"known CCITT vector at odd address");
    for (value=0;value<65536UL;++value) {
        source[1]=(U8)value; source[2]=(U8)(value>>8);
        if (sd_crc16(source+1,2)!=oracle(source+1,2)) {
            check(0,"all 65536 two-byte CRC vectors"); break;
        }
    }
    for (i=0;i<sizeof(source);++i) source[i]=(U8)(i*37U+(i>>3));
    for (offset=0;offset<2;++offset) for (i=0;i<sizeof(counts)/sizeof(counts[0]);++i) {
        n=counts[i];
        check(sd_crc16(source+offset,n)==oracle(source+offset,n),"CRC packet lengths");
        check(fast_crc_abi(source+offset,n)==0,"CRC preserved registers/segments/DF/IF");
    }
    for (a=0;a<2;++a) for (b=0;b<2;++b)
      for (i=0;i<sizeof(counts)/sizeof(counts[0]);++i) {
        n=counts[i]; memset(target,0x73,sizeof(target));
        check(fast_copy_abi(target+1+b,source+a,n)==0,"far copy ABI/DF/IF");
        check(!memcmp(target+1+b,source+a,n),"far copy exact bytes and odd tail");
        check(target[b]==0x73 && target[1+b+n]==0x73,"far copy guards and zero length");
        bad=0;
        for (j=0;j<sizeof(source);++j)
            if (source[j]!=(U8)(j*37U+(j>>3))) bad=1;
        check(!bad,"far copy preserves every source byte");
      }
    sd_write_enabled=1;
    if (sd_init()) check(0,"C transport initializes strict cold card");
    else if (sd_read(2064UL,original)) check(0,"C sector receive and CRC");
    else {
        check(sd_write_arm(2064UL,2065UL)==0,"arm private reserved scratch");
        check(sd_write(2064UL,source+1)==0,"C transmit, readback and status");
        check(sd_read(2064UL,target)==0 && !memcmp(target,source+1,512),"independent receive after write");
        check(sd_write(2064UL,original)==0,"restore exact original reserved sector");
    }
    check(inportb(0x336)==0xa5 && inportb(0x335)==0,"native delayed burst completed before next OUT");
    printf("FAST RESULT: %u failures; exhaustive CRC, odd copy guards and ABI\n",failures);
    return failures?1:0;
}
