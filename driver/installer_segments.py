#!/usr/bin/env python3
"""Place Turbo C's far installer after the retained core, checking its calls."""
from pathlib import Path
import re
import sys


def transform(path):
    path=Path(path)
    text=path.read_text().rstrip('\x1a')
    code=re.findall(r"(?m)^INITTAIL\s+segment\s+([^\n]+)",text)
    data=re.findall(r"(?m)^_DATA\s+segment\s+([^\n]+)",text)
    if not code or any(c.strip()!="byte public 'CODE'" for c in code):
        raise RuntimeError('Unexpected compiler code segment')
    if not data or any(d.strip()!="word public 'DATA'" for d in data):
        raise RuntimeError('Unexpected compiler data segment')
    local=set(re.findall(r'(?m)^(\w+)\s+proc\s+far\b',text,re.I))
    gates={'_i_'+name for name in ('int86','int86x','segread','getvect','setvect',
                                 'mount','bridge','keep','get16','put16','put32')}
    # Turbo C shortens a same-segment far call to PUSH CS / CALL NEAR.
    # That has the required far return frame, and its target must be local.
    for instruction in re.finditer(r'(?m)^\s*call\s+([^\n]+)',text):
        call=instruction[1]
        far=re.fullmatch(r'far\s+ptr\s+(\w+)\s*',call,re.I)
        if far and far[1] in local|gates: continue
        match=re.fullmatch(r'near\s+ptr\s+(\w+)\s*',call,re.I)
        before=text[:instruction.start()].rstrip().splitlines()
        previous=before[-1] if before else ''
        if not match or match[1] not in local or not re.fullmatch(r'\s*push\s+cs\s*',previous,re.I):
            raise RuntimeError('Installer contains an external near/runtime call: '+call)
    if re.search(r'\bproc\s+near\b',text,re.I):
        raise RuntimeError('Installer contains a near function')
    text=text.replace('_DATA','INITDATA')
    text=re.sub(r"(INITTAIL\s+segment\s+byte public )'CODE'",r"\1'INSTALL'",text)
    text=re.sub(r"(INITDATA\s+segment\s+word public )'DATA'",r"\1'INSTALL'",text)
    path.write_bytes(text.replace('\n','\r\n').encode('ascii'))


if __name__=='__main__': transform(sys.argv[1])
