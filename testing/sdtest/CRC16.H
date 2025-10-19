#ifndef _CRC16_H
#define _CRC16_H

unsigned crc16(const unsigned char[], unsigned nrbytes);

unsigned crc16_c(const unsigned char *ptr, int count) {
    int crc;
    char i;

    crc = 0;
    while(--count >= 0) {
	crc = crc ^ (int) *ptr++ << 8;
	i = 8;
	do {
	     if(crc & 0x8000) {
		 crc = crc << 1 ^ 0x1021;
	     } else {
		 crc = crc << 1;
	     }
	} while(--i);
    }

    return crc;
}

#endif