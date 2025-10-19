#include "helpers.h"

static char screenbuf[80*25*2];

static void print_line(unsigned char *ptr,
		       unsigned char *asciiptr,
		       unsigned addr) {
    int j;
    unsigned char v;

    /* print address in hex format */
    printf("%04X | ", addr);

    /* print each byte in hex format */
    for(j=0; j<16; ++j) {
	printf("%02X ", *(ptr++));
    }

    /* show ASCII representation */
    printf(" | ");
    for(j=0; j<16; ++j) {
	v = *(asciiptr++);
	if(v >= 0x20 && v <= 0x7E) {
	    putchar((char)v);
	} else {
	    putchar('.');
	}
    }
    printf(" | \n");
}

void print_block(unsigned char buf[]) {
    int i,j;
    unsigned char *ptr = buf;
    unsigned char *asciiptr = buf;
    unsigned addr = 0;

    for(i=0; i<16; ++i) {
	print_line(ptr, asciiptr, addr);
	addr += 16;
	ptr += 16;
	asciiptr += 16;
    }
    printf("Press any key to continue to next 256 bytes.");
    getch();
    printf("\r");
    for(i=0; i<16; ++i) {
	print_line(ptr, asciiptr, addr);
	addr += 16;
	ptr += 16;
	asciiptr += 16;
    }
}
