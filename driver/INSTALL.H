/* Far installer gates: all underlying near code remains in resident _TEXT.
 * Interrupt calls use INSTINT.ASM, which is discarded with the installer. */
#ifndef INSTALL_H
#define INSTALL_H
#include "OTTER.H"
int FAR installer(void);
U16 FAR i_mount(void);
void FAR i_feedback(U16 enabled);
void FAR i_bridge(void interrupt FAR (*previous)(void));
void FAR i_keep(int code,U16 paragraphs);
U16 FAR i_get16(const U8 FAR *p);
void FAR i_put16(U8 FAR *p,U16 value);
void FAR i_put32(U8 FAR *p,U32 value);
#ifdef INSTALL_BUILD
int FAR inst_int86x(int n,union REGS *in,union REGS *out,struct SREGS *s);
void FAR inst_segread(struct SREGS *s);
#define int86(n,in,out) inst_int86x((n),(in),(out),0)
#define int86x inst_int86x
#define segread inst_segread
#define getvect vector_get
#define setvect vector_set
#define media_mount i_mount
#define rw_feedback i_feedback
#define bridge_init i_bridge
#define keep i_keep
#define get16 i_get16
#define put16 i_put16
#define put32 i_put32
#endif
#endif
