; Test-only later TSR hook: chain without changing any interrupt register.
.8086
.model small
.code
public _ulhook, _hook_init
previous dd 0
_hook_init proc near
 push bp
 mov bp,sp
 mov ax,[bp+4]
 mov word ptr cs:previous,ax
 mov ax,[bp+6]
 mov word ptr cs:previous+2,ax
 pop bp
 ret
_hook_init endp
_ulhook proc far
 jmp dword ptr cs:previous
_ulhook endp
end
