#include "sd.h"
#include "crc16.h"
#include <dos.h>

static unsigned char buffer[515];
static unsigned char wrbuf[515];

#define ADDR 0x00008081

int main() {
    unsigned checksum=0;
    unsigned ctr=0;
    unsigned i=0;
    unsigned char res;

    /* Populate buffer to write to SD card */
    for(i=0; i<512; i++) {
	wrbuf[i] = i & 0xFF;
    }

    /* Try to open SD card, if not, bail out */
    if(sd_boot() != 0) {
	sddis(BASEPORT);
	printf("Failed to open SD card, terminating...\n");
	return 0;
    }
    buffer[512] = 0xFF;
    buffer[513] = 0xFF;

    /* Read sector from SD card */
    ctr = 0;
    while(cmd17(BASEPORT, ADDR, buffer) != 0 && ctr < 10) {
	sddis(BASEPORT);
	printf("CMD17 command failed\n");
	ctr++;
    }
    printf("Number of attempts: %i\n", ctr);
    print_block(buffer);

    /* Calculate checksum */
    checksum = crc16(buffer, 512);
    printf("Calculated checksum: %04X\n", checksum);
    checksum = ((unsigned)buffer[512] << 8) | (unsigned)buffer[513];
    printf("Retrieved checksum: %04X\n", checksum);
    checksum = crc16_c(buffer, 512);
    printf("C-calculated checksum: %04X\n", checksum);

    printf("Press any key to continue");
    getch();
    printf("\rAttempt to write sector to SD card\n");

    /* start writing */
    ctr = 0;
    res = 0xFF;
    while(res != 00 && ctr < 100) {
	res = cmd24(BASEPORT, ADDR, wrbuf);
	printf("%02X ", res);
	sddis(BASEPORT);
	delay(10);
	ctr++;
    }
    printf("\n");
    printf("Written block after %i attempts", ctr);
    sddis(BASEPORT);

    /* retrieve results */
    ctr = 0;
    while(cmd17(BASEPORT, ADDR, buffer) != 0x00 && ctr < 100) {
	sddis(BASEPORT);
	printf(".");
	delay(100);
	ctr++;
    }
    printf("\n");
    printf("Read block after %i attempts\n", ctr);
    print_block(buffer);

    checksum = crc16_c(buffer, 512);
    printf("C-calculated checksum: %04X\n", checksum);
    checksum = ((unsigned)buffer[512] << 8) | (unsigned)buffer[513];
    printf("Retrieved checksum: %04X\n", checksum);
    sddis(BASEPORT);
    return 0;
}