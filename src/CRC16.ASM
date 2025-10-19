; =====================================================================
;  Project: SLOT-OTTER
;  File:    CRC16.ASM
;  Author:  Ivo Filot <ivo@ivofilot.nl>
;
;  This program is free software: you can redistribute it and/or modify
;  it under the terms of the GNU General Public License as published by
;  the Free Software Foundation, either version 3 of the License, or
;  (at your option) any later version.
;
;  This program is distributed in the hope that it will be useful,
;  but WITHOUT ANY WARRANTY; without even the implied warranty of
;  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
;  GNU General Public License for more details.
;
;  You should have received a copy of the GNU General Public License
;  along with this program.  If not, see <https://www.gnu.org/licenses/>.
; =====================================================================

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