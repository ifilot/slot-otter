	.model small,C
	.data
;-------------------------------------------------------------------------
dcmd00  db 40h, 00h, 00h, 00h, 00h, 95h
dcmd08	db 48h, 00h, 00h, 01h,0AAh, 87h
dcmd55	db 77h, 00h, 00h, 00h, 00h, 65h
dacmd41	db 69h, 40h, 00h, 00h, 00h, 77h
dcmd58	db 7Ah, 00h, 00h, 00h, 00h, 01h
dcmd17  db 51h, 00h, 00h, 00h, 00h, 01h
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
	public sdrecvf		; receive single byte from SD

;-------------------------------------------------------------------------
; send 12 blank pulses to SD card
;-------------------------------------------------------------------------
cmdclr  proc
	push bp			; put bp on stack
	mov bp,sp		; put stack in bp
	mov dx, [bp+4]		; store base I/O port
	mov al, 0FFh
	out dx, al		; set shift register
	inc dx			; set startclk command
	mov cx, 12		; number of iterations
l1:	out dx, al		; keep pulsing clock
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
	mov si,OFFSET dcmd00		; set pointer
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
	mov dx, [bp+4]
	mov di, [bp+6]
	mov ax, ds
	mov es, ax
	push si
	mov si,OFFSET dcmd08		; set pointer
	call sdopen
	call sendcmd
	call recv5
	call sdclose
	pop si
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
	mov si,OFFSET dcmd55		; set pointer
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
	mov si,OFFSET dacmd41		; set pointer
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
	mov dx, [bp+4]
	mov di, [bp+6]
	mov ax, ds
	mov es, ax
	push si
	mov si,OFFSET dcmd58		; set pointer
	call sdopen
	call sendcmd
	call recv5
	call sdclose
	pop si
	pop di
	pop bp
	ret
cmd58	endp
;-------------------------------------------------------------------------
; CMD17: Retrieve block at address
;-------------------------------------------------------------------------
cmd17	proc
	push bp
	mov bp,sp
	mov dx, [bp+4]			; retrieve port
	push di
	push si

	; Set a DI pointer to dcmd17 (resides in memory) and copy
	; over bytes 01-04 corresponding to the address with the
	; MSB first and the LSB last. Set the SI pointer to the last
	; byte of the address on the stack and decrement over SI as
	; the address is stored in lower endian format.
	mov di, OFFSET dcmd17		; set command array
	inc di				; first position for address
	mov si, bp			; works because DS=SS in SMALL
	add si, 9
	mov cx, 4			; copy 4 bytes
	cld  				; set increment direction
lpaddr: mov al,[si]
	stosb
	dec si
	loop lpaddr			; copy 4 bytes

	; print address (for debugging purposes)
;	mov cx,4
;	mov si, OFFSET dcmd17
;	inc si
;paddr:  mov al,[si]
;	call puthex
;	inc si
;	loop paddr

	; The address is now copied from the stack and stored in the
	; command array. Next, we need to grab the destination pointer
	; to the buffer where we are going to store the block.
	mov di, [bp+10]			; grab destination pointer
	mov ax, ds
	mov es, ax			; ensure ES = DS

	; Set the SI pointer to the start of the command array and send
	; the command to the SD card.
	mov si, OFFSET dcmd17		; set pointer to command
	call sdopen
	call sendcmd			; run command, leaves DX to BASEPORT
	cmp al,0			; check whether 0x00 response was found
	jnz fail17			; if not, stop, fix stack and return

	mov cx,1000			; number of attempts
trtk:	inc dx				; SDBASE+1
	out dx,al			; pulse
	dec dx				; SDBASE
	in al,dx			; retrieve byte
	cmp al,0FEh			; check for token
	jz rdbuf			; if found, go read buffer
	dec cx				; decrement attempt counter
	jz fail17			; if not found within attempts, exit
	jmp trtk			; else next attempt

rdbuf:  mov cx,514			; number of bytes + checksum
	cld				; set stosb to increment
	inc dx				; kickstart read cycle with a pulse
	out dx,al			; send the pulse
rdlp:	in al,dx			; retrieve byte, followed by pulse
	stosb				; store byte in DI and increment
	loop rdlp
	mov al,00h
	jmp st17

fail17:	mov al,0FFh
st17:   call sdclose
	pop si
	pop di
	pop bp
	ret
cmd17	endp
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
;
;
;
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