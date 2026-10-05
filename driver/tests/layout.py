"""Validate the Turbo linker resident boundary, including all runtime segments."""
import pathlib
import re
import sys


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
    for start, size, name, kind in segments:
        if size and name != "_STACK" and start + size > end:
            raise RuntimeError(f"Resident boundary discards linked segment {name}")
    stack = re.search(r"^\s*([0-9A-F]+):([0-9A-F]+)\s+_resident_stack\s*$", text, re.M)
    if not stack or int(stack[1], 16) * 16 + int(stack[2], 16) + 2048 > end:
        raise RuntimeError("Resident boundary discards the private callback stack")
    print(f"Linker boundary verified: {end} image bytes; {(end + 15) // 16 * 16 + 256} resident bytes including PSP")
    return end


if __name__ == "__main__":
    verify(sys.argv[1])
