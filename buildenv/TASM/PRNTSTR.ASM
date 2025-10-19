        DOSSEG
        .MODEL   SMALL
        .STACK   200h
        .DATA
WorldMessage     DB      'Hello, world!',0dh,0ah,0
SolarMessage     DB      'Hello, solar system!',0dh,0ah,0
UniverseMessage  DB      'Hello, universe!',0dh,0ah,0
        .CODE
ProgramStart     PROC    NEAR
        mov   ax,@data
        mov   ds,ax
        mov   bx,OFFSET WorldMessage
        call  PrintString                  ;print Hello, world!
        mov   bx,OFFSET SolarMessage
        call  PrintString                  ;print Hello, solar system!
        mov   bx,OFFSET UniverseMessage
        call  PrintString                  ;print Hello, universe!
        mov   ah,4ch                       ;DOS terminate program fn #
        int   21h                          ;...and done
ProgramStart  ENDP
;
; Subroutine to print a null-terminated string on the screen.
;
; Input:
;       DS:BX - pointer to string to print.
;
; Registers destroyed: AX, BX
;
PrintString      PROC    NEAR
PrintStringLoop:
        mov   dl,[bx]                      ;get the next character of the string
        and   dl,dl                        ;is the character's value zero?
        jz    EndPrintString               ;if so, then we're done with the
                                           ; string
        inc   bx                           ;point to the next character
        mov   ah,2                         ;DOS display output function
        int   21h                          ;invoke DOS to print the character
        jmp   PrintStringLoop              ;print the next character, if any
EndPrintString:
        ret                                ;return to calling program
        ENDP  PrintString
        END   ProgramStart
