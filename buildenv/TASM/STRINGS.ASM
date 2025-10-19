        DOSSEG
        .MODEL  SMALL
        .STACK  200h
        .DATA
String1 DB      'Line1','$'
String2 DB      'Line2','$'
String3 DB      'Line3','$'
        .CODE
ProgramStart:
        mov   ax,@data
        mov   ds,ax
        mov   ah,9                  ;DOS print string function #
        mov   dx,OFFSET String1     ;string to print
        int   21h                   ;invoke DOS to print string
        mov   dx,OFFSET String2     ;string to print
        int   21h                   ;invoke DOS to print string
        mov   dx,OFFSET String3     ;string to print
        int   21h                   ;invoke DOS to print string
        mov   ah,4ch                ;DOS terminate program function
        int   21h
        END   ProgramStart
