#!/usr/bin/env python3
"""Build the standalone resident DOS API tester on a private output directory."""
import argparse
import hashlib
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import sys

ROOT=Path(__file__).resolve().parent
HERE=Path(__file__).resolve().parent


def compile_test(output,swap_adapter=False):
    output=Path(output); output.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='otter-hwrt-build-'))
    sources=[HERE/'HWRT.C',HERE/'TESTCHLD.C',ROOT/'tests/RWPROBE.C',ROOT/'OTTER.H',ROOT/'RWSD.H',ROOT/'PORT.C',ROOT/'PORTBODY.H']
    source_hash=hashlib.sha256(b''.join(p.name.encode()+b'\0'+p.read_bytes() for p in sources)).hexdigest()
    for p in sources:
        (work/p.name).write_bytes(p.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    (work/'KITHASH.H').write_text('#define KIT_SOURCE "'+source_hash[:16]+'"\n')
    toolchain=Path(os.environ.get('TOOLCHAIN_DIR',ROOT.parent/'buildenv')).resolve()
    commands=[f'mount c "{toolchain}"',f'mount d "{work}"',r'set PATH=C:\TC','d:',
              'tcc -ms -O -M -eHWRT.EXE HWRT.C PORT.C > BUILD.TXT','exit']
    if swap_adapter:
        # Only this private wrapper drives the emulator's test port. The
        # physical executable above has no emulator control or input shim.
        wrapper=(
            '#include <stdio.h>\n#include <dos.h>\n'
            'static int swap_input(void) { static unsigned phase; '
            'outportb(0x334,phase++?1:0); return 10; }\n'
            '#undef getchar\n#define getchar swap_input\n#include "HWRT.C"\n')
        (work/'HWSWAP.C').write_bytes(wrapper.replace('\n','\r\n').encode())
        commands.insert(-1,'tcc -ms -O -eHWSWAP.EXE HWSWAP.C PORT.C > SWAP.TXT')
    with (work/'compiler.log').open('wb') as log:
        subprocess.run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',
                        *sum((['-c',c] for c in commands),[])],
                       env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),
                       stdout=log,stderr=log,check=True,timeout=60)
    text=(work/'BUILD.TXT').read_text(); print(text,flush=True)
    if not (work/'HWRT.EXE').is_file() or re.search(r'(?m)^(Error|Fatal|Warning)[ :]|Undefined symbol',text):
        raise RuntimeError(f'Compilation failed or warned: {work}')
    for name in ('HWRT.EXE','HWRT.MAP','KITHASH.H'):
        shutil.copyfile(work/name,output/name)
    if swap_adapter:
        text=(work/'SWAP.TXT').read_text(); print(text,flush=True)
        if not (work/'HWSWAP.EXE').is_file() or re.search(r'(?m)^(Error|Fatal|Warning)[ :]|Undefined symbol',text):
            raise RuntimeError(f'Swap wrapper failed: {work}')
        shutil.copyfile(work/'HWSWAP.EXE',output/'HWSWAP.EXE')
    (output/'TESTSOURCE.SHA').write_text(source_hash+'\n')
    print(f'Tester: {output}; compiler artifacts: {work}',flush=True)
    return output/'HWRT.EXE'


def prepare(image,files):
    sys.path.insert(0,str(ROOT/'tests'))
    from kit_fixture import prepare as fixture
    return fixture(image,files,resident=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    a=parser.parse_args(); compile_test(a.output)


if __name__=='__main__': main()
