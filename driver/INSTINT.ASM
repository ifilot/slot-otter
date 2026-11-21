; SPDX-License-Identifier: GPL-3.0-or-later
; Installer-only interrupt helpers in the discarded INITTAIL segment, so that
; Turbo C's int86/int86x/segread/getvect/setvect modules (and the errno code
; they pull in) need not stay resident. Far Turbo C cdecl calls; DS is DGROUP
; on entry and REGS/SREGS are near DGROUP pointers. No 80186 instructions.
; Not reentrant: installation and control commands are single-threaded.
.8086
INITTAIL segment byte public 'INSTALL'
assume cs:INITTAIL, ds:nothing, es:nothing
public _inst_int86x, _inst_segread
target dd 0
saved_bp dw 0

; int far inst_int86x(int n, union REGS *in, union REGS *out, struct SREGS *s)
; Turbo C int86x semantics: AX-DI from in, and with s nonzero DS/ES from s.
; INT n is emulated as PUSHF, CLI and a far call through the vector table,
; so any vector works without modifying code. Stores AX-DI, cflag and flags
; to out (in may equal out); with s nonzero the returned ES/DS go to s.
; Returns the result AX. BP is reloaded from CS storage, not trusted to the
; handler. Preserves SI, DI, BP and DS for the caller.
_inst_int86x proc far
    push bp
    mov bp,sp
    push si
    push di
    push ds
    mov cs:saved_bp,bp
    xor ax,ax
    mov es,ax
    mov bx,[bp+6]
    and bx,255
    shl bx,1
    shl bx,1
    mov ax,es:[bx]
    mov word ptr cs:target,ax
    mov ax,es:[bx+2]
    mov word ptr cs:target+2,ax
    mov si,[bp+8]
    mov di,[bp+12]
    or di,di
    jz keep_segments
    mov es,[di]
    push word ptr [di+6]
    jmp short load
keep_segments:
    push ds
load:
    mov ax,[si]
    mov bx,[si+2]
    mov cx,[si+4]
    mov dx,[si+6]
    mov di,[si+10]
    mov si,[si+8]
    pop ds
    pushf
    cli
    call dword ptr cs:target
    pushf
    push bx
    push ds
    push es
    push si
    push di
    mov bp,cs:saved_bp
    mov ds,[bp-6]
    mov bx,[bp+10]
    pop word ptr [bx+10]
    pop word ptr [bx+8]
    mov si,[bp+12]
    or si,si
    jz drop_segments
    pop word ptr [si]
    pop word ptr [si+6]
    jmp short store
drop_segments:
    add sp,4
store:
    pop word ptr [bx+2]
    mov [bx],ax
    mov [bx+4],cx
    mov [bx+6],dx
    pop ax
    mov [bx+14],ax
    and ax,1
    mov [bx+12],ax
    mov ax,[bx]
    pop ds
    pop di
    pop si
    pop bp
    ret
_inst_int86x endp

; void far inst_segread(struct SREGS *s)
_inst_segread proc far
    push bp
    mov bp,sp
    mov bx,[bp+6]
    mov [bx],es
    mov [bx+2],cs
    mov [bx+4],ss
    mov [bx+6],ds
    pop bp
    ret
_inst_segread endp
INITTAIL ends
end
