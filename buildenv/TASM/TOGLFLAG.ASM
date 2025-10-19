        DOSSEG
        .MODEL  SMALL
        .DATA
        EXTRN   _Flag:word
        .CODE
        PUBLIC  _ToggleFlag
_ToggleFlag     PROC
        cmp     [_Flag],0              ;is the flag reset?
        jz      SetFlag                ;yes, set it
        mov     [_Flag],0              ;no, reset it
        jmp     short EndToggleFlag    ;done
SetFlag:
        mov     [_Flag],1              ;set flag
EndToggleFlag:
        ret
_ToggleFlag     ENDP
        END
