     DOSSEG                         ;segment-order directive
     .MODEL  SMALL                  ;near code and data models
     .STACK  200h                   ;512-byte stack
     .DATA                          ;start of the data segment
DisplayString  DB   13,10           ;carriage-return/linefeed pair
                                    ; to start a new line
ThreeChars     DB   3 DUP (?)       ;storage for three characters
                                    ; typed at the keyboard
               DB   '$'             ;a trailing "$" to tell DOS when
                                    ; to stop printing DisplayString
                                    ; when function 9 is executed
     .CODE                          ;start of the code segment
Begin:
     mov  ax,@data
     mov  ds,ax                     ;point DS to the data segment
     mov  bx,OFFSET ThreeChars      ;point to the storage location
                                    ; for first character
     mov  ah,1                      ;DOS keyboard input function #
     int  21h                       ;get the next key pressed
     dec  al                        ;subtract 1 from the character
     mov  [bx],al                   ;store the modified character
     inc  bx                        ;point to the storage location
                                    ; for the next character
     int  21h                       ;get the next key pressed
     dec  al                        ;subtract 1 from the character
     mov  [bx],al                   ;store the modified character
     inc  bx                        ;point to the storage location
                                    ; for the next character
     int  21h                       ;get the next key pressed
     dec  al                        ;subtract 1 from the character
     mov  [bx],al                   ;store the modified character
     mov  dx,OFFSET DisplayString   ;point to the string of
                                    ; modified characters
     mov  ah,9                      ;DOS print string function #
     int  21h                       ;print the modified characters
     mov  ah,4ch                    ;DOS end program function #
     int  21h                       ;end the program
     END  Begin                     ;directive to mark the end of the source
                                    ; code and to indicate where to start
                                    ; execution when the program is run
