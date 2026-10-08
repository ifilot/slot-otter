; Private native ABI probes, absent from the resident driver. GPL-3.0-or-later.
.8086
.model small,c
.code
extrn sd_crc16:near, fs_copy:near
public fast_crc_abi, fast_copy_abi

; Both wrappers save the C caller's registers, then use deliberate sentinels.
; DS is compared through SS:BP so even a broken DS restoration is detectable.
save_frame macro
    push bp
    mov bp,sp
    push bx
    push si
    push di
    push ds
    push es
    mov bx,1357h
    mov si,2468h
    mov di,369Ah
    mov ax,1234h
    mov es,ax
    std
endm

restore_frame macro
    cld
    pop es
    pop ds
    pop di
    pop si
    pop bx
    pop bp
    ret
endm

; DX selects expected DF: C CRC preserves it; fs_copy clears it.
check_frame proc near
    push dx
    xor ax,ax
    cmp bx,1357h
    je good_bx
    or ax,1
good_bx:
    cmp si,2468h
    je good_si
    or ax,2
good_si:
    cmp di,369Ah
    je good_di
    or ax,4
good_di:
    mov dx,ds
    cmp dx,[bp-8]
    je good_ds
    or ax,8
good_ds:
    mov dx,es
    cmp dx,1234h
    je good_es
    or ax,16
good_es:
    pushf
    pop cx
    test cx,200h
    jnz good_if
    or ax,32
good_if:
    and cx,400h
    pop dx
    cmp cx,dx
    je good_df
    or ax,64
good_df:
    ret
check_frame endp

fast_crc_abi proc near
    save_frame
    push word ptr [bp+6]
    push word ptr [bp+4]
    call sd_crc16
    add sp,4
    ; BX is caller-saved in Turbo C. The former hand-written CRC happened to
    ; preserve it, but the production C routine has no such ABI obligation.
    mov bx,1357h
    mov dx,400h
    call check_frame
    restore_frame
fast_crc_abi endp

fast_copy_abi proc near
    save_frame
    push word ptr [bp+12]
    push word ptr [bp+10]
    push word ptr [bp+8]
    push word ptr [bp+6]
    push word ptr [bp+4]
    call fs_copy
    add sp,10
    xor dx,dx
    call check_frame
    restore_frame
fast_copy_abi endp

end
