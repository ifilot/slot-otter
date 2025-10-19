
; FROM_NEW.ASM

       extrn    PopMessage_0:far
       .model 	large,c
       .code 
       public   FROM_ASM

FROM_ASM     proc
       push  ds
       mov   ax, OFFSET DGROUP:mess1
       push  ax
       call  FAR PTR PopMessage_0
       pop   cx
       pop   cx
       ret
FROM_ASM     ENDP

       .data
mess1  DB       "Report: Condition Red",0
       END

 