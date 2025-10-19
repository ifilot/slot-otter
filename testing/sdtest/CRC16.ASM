	.model small,C
	.data
	.code
	public crc16
;---------------------------------------------------------------------------
;
;---------------------------------------------------------------------------
crc16   proc
	push bp
	mov bp,sp
	push si
	mov si,[bp+4]                   ; data pointer
	mov cx,[bp+6]			; number of bytes
	mov ax, ds			; ensure ES = DS
	mov es, ax
	cld
	xor dx,dx			; reset dx
	mov ax, 1021h
.next:	jcxz .done
	lodsb				; load byte into AL
	dec cx
	xor dh,al			; crc ^= (byte << 8)
	mov bl,8
.bitl:  shl dx,1			; MSB first
	jnc .nxor
	xor dx,ax			; polynomial
.nxor:  dec bl
	jnz .bitl
	jmp .next
.done:	mov ax,dx			; put result in AX
	pop si
	pop bp
	ret
crc16   endp

	end