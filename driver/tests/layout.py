"""Validate the Turbo linker resident boundary, including all runtime segments."""
import pathlib
import re
import sys
import struct


def verify(path):
    text = pathlib.Path(path).read_text()
    # These libraries are unused by the utility and would silently reintroduce
    # heap/stdio/parser/atexit machinery into a tail-reclaimed resident image.
    forbidden = {"_malloc", "_calloc", "_realloc", "_free", "_sbrk", "_brk",
                 "_printf", "_puts", "_fcloseall", "_strtoul", "_strupr", "_atexit"}
    symbols = set(re.findall(r"^\s*[0-9A-F]+:[0-9A-F]+\s+(\S+)", text, re.M))
    unwanted = symbols & forbidden
    if unwanted:
        raise RuntimeError(f"Unused resident runtime libraries reintroduced: {sorted(unwanted)}")
    segments = [(int(start, 16), int(size, 16), name, kind)
                for start, size, name, kind in re.findall(
                    r"^\s*([0-9A-F]+)H\s+[0-9A-F]+H\s+([0-9A-F]+)H\s+(\S+)\s+(\S+)", text, re.M)]
    boundaries = [start for start, size, name, kind in segments if name == "_BSSEND" and size == 0]
    marker = re.search(r"^\s*([0-9A-F]+):([0-9A-F]+)\s+_resident_end\s*$", text, re.M)
    if len(boundaries) != 1 or not marker:
        raise RuntimeError("Missing unambiguous resident boundary")
    end = int(marker[1], 16) * 16 + int(marker[2], 16)
    if end != boundaries[0]:
        raise RuntimeError("Resident marker does not coincide with _BSSEND")
    transient=[s for s in segments if s[2] in ('INITTAIL','INITDATA')]
    if transient:
        if {s[2] for s in transient}!={'INITTAIL','INITDATA'}:
            raise RuntimeError('Missing installer code/data segment')
        if any(start<end or kind!='INSTALL' for start,size,name,kind in transient):
            raise RuntimeError('Installer is not an explicitly discarded tail')
        binary=pathlib.Path(path).with_suffix('.EXE').read_bytes()
        if binary[:2]!=b'MZ': raise RuntimeError('Installer heap proof requires a DOS EXE')
        header=struct.unpack_from('<H',binary,8)[0]*16
        values={}
        group_base=None
        for symbol in ('__heaplen','__stklen'):
            m=re.search(r'^\s*([0-9A-F]+):([0-9A-F]+)\s+'+symbol+r'\s*$',text,re.M)
            if not m: raise RuntimeError('Missing startup reserve '+symbol)
            addr=int(m[1],16)*16+int(m[2],16)
            values[symbol]=struct.unpack_from('<H',binary,header+addr)[0]
            if symbol=='__heaplen': group_base=int(m[1],16)*16
        if values['__heaplen']==0 or values['__stklen']<2048:
            raise RuntimeError('Unsafe temporary startup allocation')
        if end-group_base+values['__heaplen']+values['__stklen']+32>65535:
            raise RuntimeError('Startup reserves exceed DGROUP address space')
        if max(start+size for start,size,name,kind in transient)>end+values['__heaplen']:
            raise RuntimeError('Installer overlaps the startup stack or freed memory')
        for segment,offset,symbol in re.findall(r'^\s*([0-9A-F]+):([0-9A-F]+)\s+(\S+)\s*$',text,re.M):
            addr=int(segment,16)*16+int(offset,16)
            if addr>end and symbol!='_installer':
                raise RuntimeError('Unexpected public beyond resident boundary: '+symbol)
        print('Installer tail verified inside temporary heap; startup stack retained during installation')
    for start, size, name, kind in segments:
        if transient and name in ('INITTAIL','INITDATA'): continue
        if size and name != "_STACK" and start + size > end:
            raise RuntimeError(f"Resident boundary discards linked segment {name}")
    stack = re.search(r"^\s*([0-9A-F]+):([0-9A-F]+)\s+_resident_stack\s*$", text, re.M)
    if not stack or int(stack[1], 16) * 16 + int(stack[2], 16) + 2048 > end:
        raise RuntimeError("Resident boundary discards the private callback stack")
    if (end+15)//16*16+256>65535:
        raise RuntimeError('Resident allocation exceeds installer formatter')
    print(f"Linker boundary verified: {end} image bytes; {(end + 15) // 16 * 16 + 256} resident bytes including PSP")
    return end


if __name__ == "__main__":
    verify(sys.argv[1])
