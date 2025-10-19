   DOSSEG
   .MODEL SMALL
   .STACK 100h
   .CODE
EchoLoop:
   mov  ah,1             ;DOS keyboard input function #
   int  21h              ;get the next key
   cmp  al,13            ;was the key the Enter key?
   jz   EchoDone         ;yes, so we're done echoing
   mov  dl,al            ;put the character into DL
   mov  ah,2             ;DOS display output function
   int  21h              ;display the character
   jmp  EchoLoop         ;echo the next character
EchoDone:
   mov  ah,4ch           ;DOS terminate program function #
   int  21h              ;terminate the program
   END
