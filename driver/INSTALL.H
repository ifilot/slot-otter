/* Far installer gates: all underlying near code remains in resident _TEXT. */
#ifndef INSTALL_H
#define INSTALL_H
#include "OTTER.H"
int FAR installer(int argc,char **argv);
int FAR i_int86(int n,union REGS *in,union REGS *out);
int FAR i_int86x(int n,union REGS *in,union REGS *out,struct SREGS *s);
void FAR i_segread(struct SREGS *s);
void interrupt FAR (* FAR i_getvect(int n))(void);
void FAR i_setvect(int n,void interrupt FAR (*handler)(void));
U16 FAR i_mount(void);
void FAR i_bridge(void interrupt FAR (*previous)(void));
void FAR i_keep(int code,U16 paragraphs);
U16 FAR i_get16(const U8 FAR *p);
void FAR i_put16(U8 FAR *p,U16 value);
void FAR i_put32(U8 FAR *p,U32 value);
#ifdef INSTALL_BUILD
#define int86 i_int86
#define int86x i_int86x
#define segread i_segread
#define getvect i_getvect
#define setvect i_setvect
#define media_mount i_mount
#define bridge_init i_bridge
#define keep i_keep
#define get16 i_get16
#define put16 i_put16
#define put32 i_put32
#endif
#endif
