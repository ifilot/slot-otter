#include "sd.h"
#include "crc16.h"

static unsigned char buffer[515];

int main() {
    unsigned checksum = 0;
    unsigned ctr;

    if(sd_boot() != 0) {
	sddis(BASEPORT);
	return 0;
    }
    buffer[512] = 0xFF;
    buffer[513] = 0xFF;
    ctr = 0;
    while(cmd17(BASEPORT, 0x00000000, buffer) != 0 && ctr < 100) {
	sddis(BASEPORT);
	printf("CMD17 command failed");
	ctr++;
    }
    print_block(buffer);
    printf("%04X\n", *(const unsigned*)(&buffer[510]));

    /*checksum = crc16(buffer, 512);
    printf("%04X\n", checksum);*/
    printf("%04X\n", *(const unsigned*)(&buffer[512]));
    checksum = crc16_c(buffer, 512);
    printf("%04X\n", checksum);

    sddis(BASEPORT);
    return 0;
}