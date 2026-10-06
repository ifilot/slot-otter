/* Small-model resident bootstrap and far gates. Turbo C 2.0 / 8086.
 * The temporary heap fences the discarded installer below the startup stack.
 * The linker verifier proves that fence; keep releases it after installation.
 */
#include "INSTALL.H"
#include <process.h>
unsigned _stklen=2048;
unsigned _heaplen=8192;
int main(int argc,char **argv) { return installer(argc,argv); }
int FAR i_int86(int n,union REGS *in,union REGS *out) { return int86(n,in,out); }
int FAR i_int86x(int n,union REGS *in,union REGS *out,struct SREGS *s) {
    return int86x(n,in,out,s);
}
void FAR i_segread(struct SREGS *s) { segread(s); }
void interrupt FAR (* FAR i_getvect(int n))(void) { return getvect(n); }
void FAR i_setvect(int n,void interrupt FAR (*handler)(void)) { setvect(n,handler); }
U16 FAR i_mount(void) { return media_mount(); }
void FAR i_bridge(void interrupt FAR (*previous)(void)) { bridge_init(previous); }
void FAR i_keep(int code,U16 paragraphs) { keep(code,paragraphs); }
U16 FAR i_get16(const U8 FAR *p) { return get16(p); }
void FAR i_put16(U8 FAR *p,U16 value) { put16(p,value); }
void FAR i_put32(U8 FAR *p,U32 value) { put32(p,value); }
