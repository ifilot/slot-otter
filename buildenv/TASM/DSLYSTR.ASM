        DOSSEG
        .MODEL  SMALL
        .STACK  200h
        .DATA
DataString      DB  'This text is in the data segment$'
        .CODE
ProgramStart:
        mov     bx,@data
        mov     ds,bx                  ;set DS to the .DATA segment
        mov     dx,OFFSET DataString   ;point DX to the offset of DataString
                                       ; in the .DATA segment
        mov     ah,9                   ;DOS print string function #
        int     21h                    ;invoke DOS to print string
        mov     ah,4ch                 ;DOS terminate program function #
        int     21h                    ;invoke DOS to end program
        END     ProgramStart
