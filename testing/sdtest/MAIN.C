#include "sd.h"
#include "crc16.h"

static unsigned char buffer[515];
static unsigned char wrbuf[515];

#define ADDR 0x00008001

int main() {
    unsigned checksum=0;
    unsigned ctr=0;
    unsigned i=0;
    unsigned res=0xFF;

    for(i=0; i<512; i++) {
	wrbuf[i] = i & 0xFF;
    }

    if(sd_boot() != 0) {
	sddis(BASEPORT);
	return 0;
    }
    buffer[512] = 0xFF;
    buffer[513] = 0xFF;
    ctr = 0;
    while(cmd17(BASEPORT, ADDR, buffer) != 0 && ctr < 10) {
	sddis(BASEPORT);
	printf("CMD17 command failed\n");
	ctr++;
    }
    printf("Number of attempts: %i\n", ctr);
    print_block(buffer);
    printf("%04X\n", *(const unsigned*)(&buffer[510]));

    /*checksum = crc16(buffer, 512);
    printf("%04X\n", checksum);*/

    /*printf("%04X\n", *(const unsigned*)(&buffer[512]));
    checksum = crc16_c(buffer, 512);
    printf("%04X\n", checksum);*/

    /* start writing */
    ctr = 0;
    while(cmd24(BASEPORT, ADDR, wrbuf) != 00 && ctr < 100) {
	printf(".");
	sddis(BASEPORT);
	ctr++;
    }
    printf("\n");
    sddis(BASEPORT);
    printf("Press any key to continue");
    getch();
    printf("\r");

    /* retrieve results */
    ctr = 0;
    while(cmd17(BASEPORT, ADDR, buffer) != 0x00 && ctr < 10) {
	printf("CMD17 failed.\n");
	sddis(BASEPORT);
	ctr++;
    }
    print_block(buffer);

    sddis(BASEPORT);
    return 0;
}