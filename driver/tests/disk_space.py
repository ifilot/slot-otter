#!/usr/bin/env python3
"""Compare genuine DOS disk-space answers with independent FAT allocation.

Test private copies of the supplied image. A writable run also proves that
querying synthesized DOS units does not change physical cluster allocation.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import hardware

ROOT=Path(__file__).resolve().parents[1]


def geometry(card):
    with card.open('rb') as stream:
        stream.seek(2048*512); boot=stream.read(512)
        reserved=struct.unpack_from('<H',boot,14)[0]
        fat16=bool(struct.unpack_from('<H',boot,22)[0])
        fatsz=struct.unpack_from('<H',boot,22)[0] if fat16 else struct.unpack_from('<I',boot,36)[0]
        total=struct.unpack_from('<H',boot,19)[0] or struct.unpack_from('<I',boot,32)[0]
        roots=(struct.unpack_from('<H',boot,17)[0]+15)//16
        spc=boot[13]
        clusters=(total-reserved-boot[16]*fatsz-roots)//spc
        stream.seek((2048+reserved)*512); fat=stream.read(fatsz*512)
        free=sum((struct.unpack_from('<H' if fat16 else '<I',fat,c*(2 if fat16 else 4))[0]&0x0fffffff)==0
                 for c in range(2,clusters+2))
    return boot,spc,clusters,free


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dosbox',required=True)
    p.add_argument('--boot-image',type=Path,required=True)
    p.add_argument('--kit',type=Path,required=True)
    p.add_argument('--image',type=Path,required=True)
    p.add_argument('--readonly',action='store_true')
    p.add_argument('--timeout',type=float,default=600)
    a=p.parse_args(); a.driver=a.kit/'OTTERSD.EXE'
    a.mode='readonly' if a.readonly else 'normal'; a.noverify=False
    work=Path(tempfile.mkdtemp(prefix='otter-dos-space-'))
    print('Artifacts: '+str(work),flush=True)
    # Turbo C's DOS text reader requires CRLF, as in the other native probes.
    source=(ROOT/'tests/SPACE.C').read_bytes().replace(b'\r\n',b'\n')
    (work/'SPACE.C').write_bytes(source.replace(b'\n',b'\r\n'))
    commands=[f'mount c "{Path(os.environ.get("TOOLCHAIN_DIR",ROOT.parent/"buildenv")).resolve()}"',
              f'mount d "{work}"',r'set PATH=C:\TC','d:',
              'tcc -ms -O -eSPACE.EXE SPACE.C > BUILD.TXT','exit']
    with (work/'compiler.log').open('wb') as log:
        subprocess.run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',
            *sum((['-c',c] for c in commands),[])],
            env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),
            stdout=log,stderr=log,check=True,timeout=60)
    text=(work/'BUILD.TXT').read_text()
    assert (work/'SPACE.EXE').is_file() and not re.search(
        r'(?m)^(Error|Fatal|Warning)[ :]|Undefined symbol',text),text
    card=work/'card.img'; shutil.copyfile(a.image,card)
    before=geometry(card)
    with card.open('rb') as stream:
        initial_hash=hashlib.file_digest(stream,'sha256').hexdigest()
    command='SPACE /RO > SPACE.TXT' if a.readonly else 'SPACE > SPACE.TXT'
    result=hardware.boot_run(a,work,card,a.kit,[command],'first',
                             extra_files=[(work/'SPACE.EXE','SPACE.EXE')])
    assert result['CODE.TXT'].strip()==b'0','DOS capacity probe failed'
    text=subprocess.check_output(['mtype','-i',str(work/'first.img'),'::SPACE.TXT'])
    (work/'SPACE.TXT').write_bytes(text); print(text.decode('cp437'),flush=True)
    answers=re.findall(rb'SPACE (before|after): sectors=(\d+) bytes=(\d+) total=(\d+) free=(\d+)',text)
    assert len(answers)==2 and b'SPACE PASS' in text,text
    after=geometry(card)
    assert before[:3]==after[:3],'DOS capacity query changed physical BPB geometry'
    for answer,physical in zip(answers,(before,after)):
        phase,sectors,bps,total,free=answer
        sectors,bps,total,free=map(int,(sectors,bps,total,free))
        spc,count,available=physical[1:]
        unit=sectors*bps
        assert bps==512 and sectors>=spc and sectors<=max(64,spc)
        assert 0<=count*spc*512-total*unit<unit,(phase,physical,answer)
        if a.readonly: assert free==0
        else: assert 0<=available*spc*512-free*unit<unit,(phase,physical,answer)
    if a.readonly:
        with card.open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==initial_hash,'Read-only query wrote card'
    else:
        expected=(5000+before[1]*512-1)//(before[1]*512)
        assert before[3]-after[3]==expected,'Allocator used DOS logical rather than physical clusters'
        data=subprocess.check_output(['mtype','-i',str(card)+'@@1048576','::SPACE.BIN'])
        assert data==bytes((i*7+3)&255 for i in range(5000)),'Native file content differs'
    print('PASS: genuine DOS capacity/free bytes match independent FAT; physical clusters preserved',flush=True)


if __name__=='__main__': main()
