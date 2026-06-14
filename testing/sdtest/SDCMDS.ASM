	.model small,C
	.data
;-------------------------------------------------------------------------
; SD-CARD interface
; The SD-CARD listens on SDBASE base address, typically corresponding
; to 0x330.
; OUT 00 -> Write AL to shift register
; OUT 01 -> Exchange byte with SD-CARD
; OUT 02 -> Set /CS high, deactivating SD-CARD
; OUT 03 -> Set /CS low, activating SD-CARD
; IN  00 -> Read from shift register
; IN  01 -> Read from shift register and send 0xFF pulse
; IN  02 -> Pull MISO low via 10k resistor
; IN  03 -> Pull MISO high via 10k resistor
;-------------------------------------------------------------------------
dcmd00  db 40h, 00h, 00h, 00h, 00h, 95h
dcmd08	db 48h, 00h, 00h, 01h,0AAh, 87h
dcmd55	db 77h, 00h, 00h, 00h, 00h, 65h
dacmd41	db 69h, 40h, 00h, 00h, 00h, 77h
dcmd58	db 7Ah, 00h, 00h, 00h, 00h, 01h
dcmd17  db 51h, 00h, 00h, 00h, 00h, 01h
dcmd24  db 58h, 00h, 00h, 00h, 00h, 01h
;-------------------------------------------------------------------------
	.code
	public cmdclr           ; send 10 blank pulses to SD card
	public sden		; pull /CS low, selecting SD card
	public sddis		; pull /CS high, deselecting SD card
	public cmd00		; send command cmd00
	public cmd08		; send command cmd08
	public cmd55		; send command cmd55 (advanced command)
	public acmd41		; send command acmd41
	public cmd58		; send command cmd58
	public cmd17		; send command cmd17
	public cmd24		; send command cmd24
	public sdrecvf		; receive single byte from SD

;-------------------------------------------------------------------------
; Note on calling conventions
;
; When a C-style function is called, the caller first pushes the arguments
; onto the stack in reverse order. CALL then pushes the return address.
; At function entry, the callee saves the caller's BP and sets BP = SP.
;
; The 8086 stack grows downward, toward lower addresses. Therefore, items
; pushed earlier are found at higher addresses than items pushed later.
;
; Example: unsigned char cmd17(unsigned, unsigned long, unsigned char *);
;
; Stack frame after:
;     push bp
;     mov  bp, sp
;
; *-- higher address --*
;   argument unsigned char * : 16 bits [BP+10]
;   argument unsigned long   : 32 bits [BP+6]
;   argument unsigned        : 16 bits [BP+4]
;   return address           : 16 bits [BP+2]
;   saved caller BP          : 16 bits [BP]
; *-- lower address --*
;
; 8086 stores multi-byte values little-endian: the least-significant byte
; is stored at the lowest address. For example, a 32-bit value at [BP+6]
; has its bytes stored as:
;
;   [BP+6] = bits  7..0
;   [BP+7] = bits 15..8
;   [BP+8] = bits 23..16
;   [BP+9] = bits 31..24
;
; SD command arguments, however, are transmitted big-endian / MSB-first.
; Therefore a 32-bit address stored in memory must be sent to the SD card
; starting with [BP+9], then [BP+8], [BP+7], and finally [BP+6].
;-------------------------------------------------------------------------

;-------------------------------------------------------------------------
; send 12 blank pulses to SD card
;-------------------------------------------------------------------------
cmdclr  proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	mov dx, [bp+4]		; store base I/O port
	mov al, 0FFh
	out dx, al		; set shift register
	inc dx			; set startclk command
	mov cx, 12		; number of iterations
l1:	out dx, al		; keep pulsing clock
	loop l1			; loop for CX=12 iterations
	pop bp			; retrieve BP
	ret
cmdclr  endp
;-------------------------------------------------------------------------
; SD command CMD00
; Resets the SD card and puts it into idle state.
;-------------------------------------------------------------------------
cmd00  	proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	mov dx, [bp+4]		; store base I/O address
	push si			; put SI on stack
	mov si,OFFSET dcmd00	; set pointer
	call sdopen		; open SD card
	call sendcmd		; send command
	call sdclose		; close SD card
	pop si			; restore SI
	pop bp			; restore BP
	ret
cmd00	endp
;-------------------------------------------------------------------------
; SD command CMD08
; Checks whether the card supports the supplied voltage range and helps
; identify SD version 2.0 or later cards.
;-------------------------------------------------------------------------
cmd08  	proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	push di			; put DI on stack
	mov dx, [bp+4]		; load base I/O in DX
	mov di, [bp+6]		; load response pointer in DI
	mov ax, ds		; put DS in AX
	mov es, ax		; set ES = DS (needed for stosb in recv5)
	push si			; put SI on stack
	mov si, OFFSET dcmd08	; set SI to CMD08 array
	call sdopen		; open SD card
	call sendcmd		; send command
	call recv5		; receive R5 response
	call sdclose		; close SD card
	pop si			; restore SI
	pop di			; restore DI
	pop bp			; restore BP
	ret
cmd08	endp
;-------------------------------------------------------------------------
; SD command CMD55
; Tells the SD card that the next command is an application-specific 
; command, also called an ACMD.
;-------------------------------------------------------------------------
cmd55  	proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	mov dx, [bp+4]		; load base I/O in DX
	push si			; put SI on stack
	mov si, OFFSET dcmd55	; set SI to CMD55 array
	call sdopen		; open SD card
	call sendcmd		; send command
	call sdclose		; close SD card
	pop si			; retrieve SI
	pop bp			; retrieve BP
	ret
cmd55	endp
;-------------------------------------------------------------------------
; SD command ACMD41
; Starts or continues SD card initialization. It is repeatedly sent 
; after CMD55 until the card leaves idle state.
;-------------------------------------------------------------------------
acmd41 	proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	mov dx, [bp+4]		; load base I/O in DX
	push si			; put SI on stack
	mov si, OFFSET dacmd41	; set SI to ACMD41 array
	call sdopen		; open SD card
	call sendcmd		; send command
	call sdclose		; close SD card
	pop si			; retrieve SI
	pop bp			; retrieve BP
	ret
acmd41	endp
;-------------------------------------------------------------------------
; SD command CMD58
; Reads the OCR, or Operating Conditions Register. Used to check voltage 
; range and whether the card is standard-capacity or high-capacity.
;-------------------------------------------------------------------------
cmd58  	proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	push di			; store DI on stack
	mov dx, [bp+4]		; load base I/O in DX
	mov di, [bp+6]		; load response pointer in DI
	mov ax, ds		; put DS in AX
	mov es, ax		; set ES = DS (needed for stosb in recv5)
	push si			; push SI on stack
	mov si, OFFSET dcmd58	; set SI to CMD58 array
	call sdopen		; open SD card
	call sendcmd		; send command
	call recv5		; retrieve R5 response
	call sdclose		; close SD card
	pop si			; restore SI
	pop di			; restore DI
	pop bp			; restore BP
	ret
cmd58	endp
;-------------------------------------------------------------------------
; CMD17: Retrieve block at address
; Reads one 512-byte block from the SD card.
;
; unsigned char cmd17(unsigned baseio, unsigned long addr, unsigned char* buf);
;    base io -> base port like 0x330
;    addr    -> 32 bit address
;    buf     -> 514 byte buffer (payload + 16 bit crc)
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

	mov cx,1000			; number of attempts
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
	mov cx, 514			; number of bytes + checksum
	cld				; set stosb to increment
	inc dx				; set BASEPORT+1
	out dx, al			; exchange byte with SD-card
rdlp:	in al, dx			; retrieve byte, followed by pulse
	stosb				; store byte in DI and increment
	loop rdlp			; continue for CX=514 bytes
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
; CMD24: Write block at address
; Writes one 512-byte block to the SD card.
;
; unsigned char cmd24(unsigned baseio, unsigned long addr, unsigned char* buf);
;    base io -> base port like 0x330
;    addr    -> 32 bit address
;    buf     -> 514 byte buffer (payload + 16 bit crc)
;-------------------------------------------------------------------------
cmd24 	proc
	push bp			; save caller's BP
	mov bp, sp		; establish stack frame for accessing arguments
	mov dx, [bp+4]		; retrieve port (SDBASE)
	push di			; save DI on stack
	push si			; save SI on stack
	push es			; save ES on stack

	; Set DI to the address field inside the CMD24 command buffer.
	; The 32-bit address argument is stored little-endian on the 8086 stack:
	;
	;   [BP+6] = bits  7..0
	;   [BP+7] = bits 15..8
	;   [BP+8] = bits 23..16
	;   [BP+9] = bits 31..24
	;
	; SD command arguments are transmitted big-endian / MSB first, so copy
	; the address bytes into the command buffer from high byte to low byte.
	mov di, OFFSET dcmd24	; set pointer to command array
	mov ax, ds		; load DS in AX
	mov es, ax		; ensure ES = DS
	inc di			; first position of sector address
	mov al, [bp+9]		; address bits 31..24
	stosb
	mov al, [bp+8]		; address bits 23..16
	stosb
	mov al, [bp+7]		; address bits 15..8
	stosb
	mov al, [bp+6]		; address bits 7..0
	stosb

	; set the SI pointer to the start of the command array and
	; send the command to the SD card.
	mov si, OFFSET dcmd24	; set pointer to command
	call sdopen		; open SD card
	call sendcmd		; send command
	cmp al,0		; check acknowledge command
	jnz st24		; fail mode

wdbuf:  mov al,0FEh		; set block token
	out dx,al		; put block token in shift register
	inc dx			; SDBASE+1
	out dx,al		; send block token to SD-CARD

	mov cx, 514		; 512 data bytes + 2 CRC/dummy bytes
	cld			; set lodsb to increment
	mov si, [bp+10]		; place address pointer into source index
wrlp:   dec dx			; SDBASE
	lodsb			; grab value from SI and store in AL, inc SI
	out dx,al		; store byte in shift register
	inc dx			; SDBASE+1
	out dx,al		; send byte from shift register to SD-CARD
	loop wrlp		; continue until CX=514 bytes are sent

	; after sending the block, the SD card sends a data response token.
	; the lower 5 bits should equal 00101b, indicating "data accepted".
	in al, dx		; read response byte
	and al,01Fh		; keep lower 5 bits
	cmp al,5		; check if equal to five
	jnz st24		; fail mode response

	; wait until SD card is done writing
	mov cx,1000		; set wait counter
waitr1:	out dx, al		; send dummy byte while polling busy
	in al, dx		; retrieve response token and send pulse
	cmp al,0FFh		; check if idle token?
	jz rd24			; card is ready again -> done
	dec cx			; else, decrement wait counter
	jnz waitr1		; is wait counter not 0, try again
	mov al,0FFh		; set fail return value
	jmp st24		; number of attempts exceeded, fail

rd24:   mov al, 00h
st24:	call sdclose		; close SD card
	pop es			; restore ES
	pop si			; restore SI
	pop di			; restore DI
	pop bp			; restore BP
	ret
cmd24 	endp
;-------------------------------------------------------------------------
; General send command, assumes DX contains BASE I/O address
; After sending the command, DX is kept to BASE I/O address
;-------------------------------------------------------------------------
sendcmd	proc
	cld			; set incrementing direction
	mov cx, 6		; set number of bytes
l2:	lodsb			; load byte from SI into AL and incr SI
	out dx, al		; put value in register and pulse
	loop l2
	mov cx, 100		; set counter
check:  inc dx			; BASE+1
	out dx,al		; give pulse
	dec dx			; BASE
	in al, dx		; retrieve byte
	cmp al,0FFh		; check if equal to 0xFF
	jne endrun		; if not, return value
	dec cx			; if so, decrement trial counter
	jz endrun		; end if trial counter equal to zero
	jmp check		; else try again
endrun: ret
sendcmd	endp
;-------------------------------------------------------------------------
; Open SD card
;-------------------------------------------------------------------------
sdopen  proc
	push dx
	mov al,0FFh
	out dx,al		; send 0xFF while SD card disabled
	add dx,3
	out dx,al		; pull /CS low
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
	out dx,al		; send 0xFF while SD card active
	add dx,2
	out dx,al		; pull /CS high
	pop dx
	pop ax
	ret
sdclose endp
;-------------------------------------------------------------------------
; R5 response
;-------------------------------------------------------------------------
recv5	proc
	stosb			; store initial value in AL
	mov cx,4
	inc dx			; set to BASE+1
	out dx,al		; regular pulse
.nb:    in al,dx		; read followed by pulse
	stosb			; store other values in AL
	loop .nb
	dec dx			; set to BASE
	ret
recv5	endp
;-------------------------------------------------------------------------
; Receive byte from SD card; assumes register has 0xFF
;-------------------------------------------------------------------------
sdrecvf	proc
	push bp
	mov bp,sp
	mov dx, [bp+4]
	mov bx, 0
l3:	inc dx
	out dx, al		; send empty bytes
	dec dx
	in al, dx		; receive byte
	cmp al, 0FFh
	jne endrcv
	inc bx
	cmp bx, 10
	jne l3
endrcv:	pop bp
	ret
sdrecvf	endp
;-------------------------------------------------------------------------
; enable SD card by pulling /CS low
;-------------------------------------------------------------------------
sden    proc
	push bp
	mov bp,sp
	mov dx, [bp+4]		; set base I/O port
	add dx, 2		; set act port BASE | 02
	mov al, 0FFh		; some dummy value
	out dx, al              ; and send I/O instruction
	pop bp
	ret
sden    endp
;-------------------------------------------------------------------------
; disable SD card by puling /CS high
;-------------------------------------------------------------------------
sddis   proc
	push bp
	mov bp,sp
	mov dx, [bp+4]		; set base I/O port
	add dx, 3		; set deact port BASE | 03
	mov al, 0FFh		; some dummy value
	out dx, al		; and send I/O instruction
	pop bp
	ret
sddis   endp
;-------------------------------------------------------------------------
; Output value in AL to the screen
; Conserves all
;-------------------------------------------------------------------------
puthex  proc
	push ax
	push dx
	mov dh,al	; store copy
	shr al,1	; shift upper nibble
	shr al,1
	shr al,1
	shr al,1
	call putnib
	mov al,dh
	and al,0Fh
	call putnib
	mov dl,' '
	mov ah,02h
	int 21h
	pop dx
	pop ax
	ret
puthex  endp
putnib  proc
	add al,'0'	; set 0-9 range
	cmp al,'9'	; check if in range
	jbe skip	; if so, print it
	add al,7	; else set A-F range
skip:	mov dl,al
	mov ah,02h
	int 21h
	ret
putnib  endp

newline proc
	push ax
	push dx
	mov dl,13
	mov ah,02
	int 21h
	mov dl,10
	mov ah,02
	int 21h
	pop dx
	pop ax
	ret
newline endp

	end
