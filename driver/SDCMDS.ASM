; =====================================================================
;  Project: SLOT-OTTER
;  File:    SDCMDS.ASM
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
;-------------------------------------------------------------------------
; Specify 6-byte command instructions; note that CMD17 is set for address
; 0x00000000, but will be updated once CMD17 is called.
;-------------------------------------------------------------------------
dcmd00  db 40h, 00h, 00h, 00h, 00h, 95h
dcmd08	db 48h, 00h, 00h, 01h,0AAh, 87h
dcmd55	db 77h, 00h, 00h, 00h, 00h, 65h
dacmd41	db 69h, 40h, 00h, 00h, 00h, 77h
dcmd58	db 7Ah, 00h, 00h, 00h, 00h, 01h
dcmd17  db 51h, 00h, 00h, 00h, 00h, 01h

;-------------------------------------------------------------------------
    .code
    public cmdclr           ; send 96 idle clocks to SD card
    public sddis            ; pull /CS high, deselecting SD card
    public cmd00            ; send command cmd00
    public cmd08            ; send command cmd08
    public cmd55            ; send command cmd55 (advanced command)
    public acmd41           ; send command acmd41
    public cmd58            ; send command cmd58
    public cmd17            ; send command cmd17


;-------------------------------------------------------------------------
; send 12 blank pulses to SD card
;-------------------------------------------------------------------------
cmdclr  proc
    push bp                 ; put bp on stack
    mov bp,sp               ; put stack in bp
    mov dx, [bp+4]          ; store base I/O port
    mov al, 0FFh
    out dx, al              ; set shift register
    inc dx    	            ; set startclk command
    mov cx, 12              ; number of iterations
l1:	out dx, al              ; keep pulsing clock
    loop l1
    pop bp
    ret
cmdclr  endp

;-------------------------------------------------------------------------
; SD command CMD00
;-------------------------------------------------------------------------
cmd00  	proc
    push bp
    mov bp,sp
    mov dx, [bp+4]
    push si
    mov si,OFFSET dcmd00    ; set pointer
    call sdopen
    call sendcmd
    call sdclose
    pop si
    pop bp
    ret
cmd00	endp

;-------------------------------------------------------------------------
; SD command CMD08
;-------------------------------------------------------------------------
cmd08  	proc
    push bp
    mov bp,sp
    push di
    push es
    mov dx, [bp+4]
    mov di, [bp+6]
    mov ax, ds
    mov es, ax
    push si
    mov si,OFFSET dcmd08    ; set pointer
    call sdopen
    call sendcmd
    call recv5
    call sdclose
    mov si,[bp+6]
    mov al,[si]                 ; return R1, not final R7/R3 byte
    pop si
    pop es
    pop di
    pop bp
    ret
cmd08	endp

;-------------------------------------------------------------------------
; SD command CMD55
;-------------------------------------------------------------------------
cmd55  	proc
    push bp
    mov bp,sp
    mov dx, [bp+4]
    push si
    mov si,OFFSET dcmd55    ; set pointer
    call sdopen
    call sendcmd
    call sdclose
    pop si
    pop bp
    ret
cmd55	endp

;-------------------------------------------------------------------------
; SD command ACMD41
;-------------------------------------------------------------------------
acmd41 	proc
    push bp
    mov bp,sp
    mov dx, [bp+4]
    push si
    mov si,OFFSET dacmd41    ; set pointer
    call sdopen
    call sendcmd
    call sdclose
    pop si
    pop bp
    ret
acmd41	endp

;-------------------------------------------------------------------------
; SD command CMD58
;-------------------------------------------------------------------------
cmd58  	proc
    push bp
    mov bp,sp
    push di
    push es
    mov dx, [bp+4]
    mov di, [bp+6]
    mov ax, ds
    mov es, ax
    push si
    mov si,OFFSET dcmd58    ; set pointer
    call sdopen
    call sendcmd
    call recv5
    call sdclose
    mov si,[bp+6]
    mov al,[si]                 ; return R1, not final R7/R3 byte
    pop si
    pop es
    pop di
    pop bp
    ret
cmd58	endp

;-------------------------------------------------------------------------
; CMD17: Retrieve block at address
; Reads one 512-byte block from the SD card.
;
; unsigned char cmd17(unsigned baseio, unsigned long addr, unsigned char* buf);
;    base io -> base port like 0x330
;    addr    -> 32 bit address
;    buf     -> 512 byte payload buffer; CRC bytes are consumed separately.
;-------------------------------------------------------------------------
cmd17	proc
	push bp				; save caller's BP
	mov  bp, sp			; establish stack frame for accessing arguments
	mov dx, [bp+4]			; load base I/O in DX
	push di				; store DI on stack
	push si				; store SI on stack
	push es				; store ES on stack

	; Set DI to the address field inside the CMD17 command buffer
	; The 32-bit address argument is stored little-endian on the 8086 stack
	;
	;   [BP+6] = bits  7..0
	;   [BP+7] = bits 15..8
	;   [BP+8] = bits 23..16
	;   [BP+9] = bits 31..24
	;
        ; SD command arguments are transmitted big-endian / MSB first, so copy
        ; the address bytes into the command buffer from high byte to low byte.
	mov ax, ds			; load DS into AX
	mov es, ax			; STOSB writes to ES:DI, so set ES = DS
	mov di, OFFSET dcmd17		; set pointer to command array
	inc di				; first position of sector address
	mov al, [bp+9]			; address bits 31..24
	stosb
	mov al, [bp+8]			; address bits 23..16
	stosb
	mov al, [bp+7]			; address bits 15..8
	stosb
	mov al, [bp+6]			; address bits 7..0
	stosb

	; Set the SI pointer to the start of the command array and send
	; the command to the SD card.
	mov si, OFFSET dcmd17		; set pointer to command
	call sdopen			; open SD card
	call sendcmd			; send command
	cmp al,0			; check whether 0x00 response was found
	jnz st17			; if not, stop, fix stack and return

	mov cx,65535			; number of attempts
trtk:	inc dx				; SDBASE+1
	out dx, al			; pulse
	dec dx				; SDBASE
	in al, dx			; retrieve byte
	cmp al, 0FEh			; check for response token
	jz rdbuf			; if found, go read buffer
	dec cx				; decrement attempt counter
	jz fail17			; if not found within attempts, exit
	jmp trtk			; else next attempt

rdbuf:  mov di, [bp+10]			; destination buffer pointer for received data
	mov cx, 512			; number of payload bytes
	cld				; set stosb to increment
	inc dx				; set BASEPORT+1
	out dx, al			; exchange byte with SD-card
rdlp:	in al, dx			; retrieve byte, followed by pulse
	stosb				; store byte in DI and increment
	loop rdlp			; continue for CX=512 bytes
	in al, dx			; consume CRC high byte without storing
	in al, dx			; consume CRC low byte without storing
	dec dx				; sdclose requires BASE, not BASE+1
	mov al, 00h			; set return byte (0x00 = success)
	jmp st17			; jump to end of routine

fail17: mov al, 0FFh			; set 0FFh to indicate fail
st17:   call sdclose			; close SD card
	pop es				; restore ES
	pop si				; restore SI
	pop di				; restore DI
	pop bp				; restore BP
	ret
cmd17	endp



;-------------------------------------------------------------------------
; General send command, assumes DX contains BASE I/O address
; After sending the command, DX is kept to BASE I/O address
;-------------------------------------------------------------------------
sendcmd	proc
    cld    	                    ; set incrementing direction
    mov cx, 6                   ; set number of bytes
l2:	lodsb    	                ; load byte from SI into AL and incr SI
    out dx, al                  ; put value in register and pulse
    loop l2
    mov cx, 100                 ; set counter
check:  inc dx                  ; BASE+1
    out dx,al                   ; give pulse
    dec dx    	                ; BASE
    in al, dx                   ; retrieve byte
    cmp al,0FFh                 ; check if equal to 0xFF
    jne endrun                  ; if not, return value
    dec cx    	                ; if so, decrement trial counter
    jz endrun                   ; end if trial counter equal to zero
    jmp check                   ; else try again
endrun: ret
sendcmd	endp

;-------------------------------------------------------------------------
; Open SD card
;-------------------------------------------------------------------------
sdopen  proc
    push dx
    mov al,0FFh
    out dx,al                   ; send 0xFF while SD card disabled
    add dx,3
    out dx,al                   ; pull /CS low
    pop dx
    ret
sdopen  endp

;-------------------------------------------------------------------------
; Close SD card
;-------------------------------------------------------------------------
sdclose proc
    push ax
    push dx
    mov al,0FFh
    out dx,al                   ; send 0xFF while SD card active
    add dx,2
    out dx,al                   ; pull /CS high
    pop dx
    pop ax
    ret
sdclose endp

;-------------------------------------------------------------------------
; Receive R5 response; assumes first byte is already retrieved via 
; prior SENDCMD routine
;-------------------------------------------------------------------------
recv5	proc
    stosb    	                ; store initial value in AL
    mov cx,4
    inc dx    	                ; set to BASE+1
    out dx,al                   ; regular pulse
.nb:    in al,dx                ; read followed by pulse
    stosb    	                ; store other values in AL
    loop .nb
    dec dx    	                ; set to BASE
    ret
recv5	endp

;-------------------------------------------------------------------------
; Disable SD card: OUT base+2 deasserts /CS (see card schematic).
;-------------------------------------------------------------------------
sddis   proc
    push bp
    mov bp,sp
    mov dx, [bp+4]              ; set base I/O port
    add dx, 2                   ; set deact port BASE+2
    mov al, 0FFh                ; some dummy value
    out dx, al                   ; deassert chip select
    pop bp
    ret
sddis   endp

end
