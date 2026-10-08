; SPDX-License-Identifier: GPL-3.0-or-later
; Near Turbo C small-model far-copy helper. No 80186 instructions.
.8086
.model small, c
.code
public fs_copy

; Far destination/source/count at BP+4/+8/+12. Callers normalize original
; DOS pointers before each <=512-byte chunk, so neither offset can wrap.
; REP does not change the carry from SHR: the final byte handles odd counts.
; Preserve both segment registers and clear DF as required by C string code.
fs_copy proc near
    push bp
    mov bp,sp
    push ds
    push es
    push si
    push di
    les di,[bp+4]
    lds si,[bp+8]
    mov cx,[bp+12]
    cld
    shr cx,1
    rep movsw
    adc cx,cx
    rep movsb
    pop di
    pop si
    pop es
    pop ds
    pop bp
    ret
fs_copy endp
end
