        DOSSEG
        .MODEL  SMALL
        .STACK  200h
        .DATA
OutputChar      DB   'B'
        .CODE
ProgramStart:
        mov   dx,@data
        mov   es,dx                  ;set ES to the .DATA segment
        mov   bx,OFFSET OutputChar   ;point BX to the offset of OutputChar
        mov   dl,es:[bx]             ;get the character to output from the
                                     ; segment pointed to by ES
        mov   ah,2                   ;DOS display output function #
        int   21h                    ;invoke DOS to print character
        mov   ah,4ch                 ;DOS terminate program function #
        int   21h                    ;invoke DOS to end program
        END   ProgramStart
