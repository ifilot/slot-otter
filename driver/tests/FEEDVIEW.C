/* Test-only active text-page capture, run after foreground driver commands.
 * SPDX-License-Identifier: GPL-3.0-or-later */
#include <dos.h>
#include <stdio.h>
int main(int argc,char **argv) {
    union REGS r;
    unsigned page, segment, stride, row, col;
    unsigned char far *video;
    char line[80];
    FILE *out;
    if (argc!=2) return 1;
    r.h.ah=0x0f; int86(0x10,&r,&r);
    if (r.h.ah!=80) return 2;
    segment=r.h.al==7?0xb000:0xb800; page=r.h.bh;
    stride=*(unsigned far *)MK_FP(0x40,0x4c);
    video=(unsigned char far *)MK_FP(segment,page*stride);
    out=fopen(argv[1],"wb");
    if (!out) return 3;
    for (row=0;row<25;++row) {
        for (col=0;col<80;++col) line[col]=video[(row*80+col)*2];
        if (fwrite(line,1,80,out)!=80 || fwrite("\r\n",1,2,out)!=2) {
            fclose(out); return 4;
        }
    }
    return fclose(out)?5:0;
}
