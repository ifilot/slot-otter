     DOSSEG
     .MODEL  SMALL
     .STACK  200h
     .CODE
Delay:
     mov   cx,0
DelayLoop:
     loop  DelayLoop
     ret

ProgramStart:
     call  Delay         ;pause for the time required to
                         ; execute 64K loops
     mov   ah,4ch
     int   21h
     END   ProgramStart
