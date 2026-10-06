; SPDX-License-Identifier: GPL-3.0-or-later
; 8086 interrupt bridge. C runs on its own stack and DGROUP, never DOS's stack.
.8086
; C0 places this zero-length segment after all CODE/DATA/BSS. Startup
; heap and stack follow it, and may be released once installation finishes.
_BSSEND segment byte public 'STACK'
public _resident_end
_resident_end label byte
_BSSEND ends
.model small, c
.data
extrn regs:byte, resident_stack:byte
.code
extrn dispatch:near
public redirect_entry, bridge_init
previous dd 0
groupseg dw 0
saved_ss dw 0
saved_sp dw 0
busy db 0

bridge_init proc near
    push bp
    mov bp,sp
    mov ax,[bp+4]
    mov word ptr cs:previous,ax
    mov ax,[bp+6]
    mov word ptr cs:previous+2,ax
    mov ax,ds
    mov cs:groupseg,ax
    pop bp
    ret
bridge_init endp

redirect_entry proc far
    cmp ah,11h
    je eligible
    cmp ax,0D74Fh                 ; private installation query
    je eligible
    jmp chain_direct
eligible:
    cmp cs:busy,0
    je available
    jmp chain_direct
available:
    ; Saved frame matches Registers: AX BX CX DX SI DI ES DS BP,
    ; then interrupt IP CS FLAGS, then the caller's extra parameter word.
    push bp
    push ds
    push es
    push di
    push si
    push dx
    push cx
    push bx
    push ax
    mov bp,sp
    mov cs:saved_sp,sp
    mov cs:saved_ss,ss
    mov ax,cs:groupseg
    mov es,ax
    mov ax,ss
    mov ds,ax
    mov si,bp
    mov di,offset regs
    mov cx,13                    ; includes extra WORD above interrupt frame
    cld
    rep movsw
    mov ax,cs:groupseg
    cli
    mov ss,ax
    mov sp,offset resident_stack+2048
    mov ds,ax
    mov cs:busy,1
    ; Set busy before enabling IRQs. IRQ handlers can use this private stack;
    ; nested redirector calls chain rather than reusing C's static scratch.
    sti
    call dispatch
    cli
    or ax,ax
    jz unhandled
    mov si,offset regs
    mov ax,cs:saved_ss
    mov es,ax
    mov di,cs:saved_sp
    mov cx,12                    ; do not overwrite caller's extra parameter
    cld
    rep movsw
    mov ax,cs:saved_ss
    mov ss,ax
    mov sp,cs:saved_sp
    mov cs:busy,0
    pop ax
    pop bx
    pop cx
    pop dx
    pop si
    pop di
    pop es
    pop ds
    pop bp
    iret
unhandled:
    ; dispatch returned zero: restore the original caller frame unchanged.
    mov ax,cs:saved_ss
    mov ss,ax
    mov sp,cs:saved_sp
    mov cs:busy,0
    pop ax
    pop bx
    pop cx
    pop dx
    pop si
    pop di
    pop es
    pop ds
    pop bp
chain_direct:
    jmp dword ptr cs:previous
redirect_entry endp
end
