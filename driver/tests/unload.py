#!/usr/bin/env python3
"""Prove real DOS unloading reclaims every byte, restores hooks/CDS, and reloads.

Uses only private boot/card images. A third-party chain hook and unrelated
allocation exercise refusal and fragmentation; FAT/file checks are independent.
"""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import hardware
import kit_fixture

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dosbox',required=True)
    p.add_argument('--boot-image',type=Path,required=True)
    p.add_argument('--driver',type=Path,required=True)
    p.add_argument('--tester',type=Path,required=True)
    p.add_argument('--skipfatcheck',action='store_true')
    p.add_argument('--mode',choices=('readonly','verified','noverify'),default='verified')
    p.add_argument('--image',type=Path)
    p.add_argument('--timeout',type=float,default=600)
    a=p.parse_args()
    work=Path(tempfile.mkdtemp(prefix='otter-unload-dos-')); print('Artifacts: '+str(work),flush=True)
    for name in ('UNLOAD.C','ULHOOK.ASM'):
        data=(ROOT/'tests'/name).read_bytes().replace(b'\r\n',b'\n')
        (work/name).write_bytes(data.replace(b'\n',b'\r\n'))
    commands=[f'mount c "{Path(os.environ.get("TOOLCHAIN_DIR",ROOT.parent/"buildenv")).resolve()}"',
              f'mount d "{work}"',r'set PATH=C:\TC;C:\TASM','d:',
              'tasm /mx ULHOOK.ASM > ASM.TXT',
              'tcc -ms -O -eUNLOAD.EXE UNLOAD.C ULHOOK.OBJ > BUILD.TXT','exit']
    with (work/'compiler.log').open('wb') as log:
        subprocess.run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',
            *sum((['-c',c] for c in commands),[])],
            env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),
            stdout=log,stderr=log,check=True,timeout=60)
    text=(work/'BUILD.TXT').read_text()+(work/'ASM.TXT').read_text()
    assert (work/'UNLOAD.EXE').is_file() and not re.search(
        r'(?m)^(?:Error [^ ]+ [0-9]+|Error:|Fatal:|Warning [^ ]+ [0-9]+|Warning:|(?:Error|Warning) messages:\s*[1-9])|Undefined symbol',text),text
    card=work/'card.img'
    if a.image: shutil.copyfile(a.image,card)
    else: kit_fixture.prepare(card,{},resident=True)
    with card.open('rb') as stream: before=hashlib.file_digest(stream,'sha256').hexdigest()
    shutil.copyfile(a.tester,work/'HWRT.EXE')
    policy={'readonly':'/RO','verified':'/RW','noverify':'/NV'}[a.mode]
    if a.skipfatcheck:
        assert a.mode!='readonly','/SKIPFATCHECK requires /RW'
        policy='/FNV' if a.mode=='noverify' else '/FAST'
    # boot_run installs first; remove that instance before taking the probe's
    # baseline. Its final /UNMOUNT is expected to find no resident driver.
    a.noverify=a.mode=='noverify'
    result=hardware.boot_run(a,work,card,work,
        ['OTTERSD /UNLOAD > FIRST.TXT','UNLOAD '+policy+' > UNLOAD.LOG'],
        'unload',extra_files=[(work/'UNLOAD.EXE','UNLOAD.EXE')])
    text=subprocess.check_output(['mtype','-i',str(work/'unload.img'),'::UNLOAD.LOG'])
    (work/'UNLOAD.LOG').write_bytes(text); print(text.decode('cp437'),flush=True)
    assert result['CODE.TXT'].strip()==b'0' and b'UNLOAD RESULT: 0 failures' in text,text
    assert text.count(b'all resident memory reclaimed without leaks')==3
    assert text.count(b'largest executable DOS block restored')==3
    if a.mode=='readonly':
        with card.open('rb') as stream:
            assert hashlib.file_digest(stream,'sha256').hexdigest()==before,'Read-only unload wrote card'
    else:
        data=subprocess.check_output(['mtype','-i',str(card)+'@@1048576','::UNLOAD.BIN'])
        assert data==bytes((i*7+3)&255 for i in range(512))*8,'Commit/unload lost file data'
    partition=work/'partition.img'
    with card.open('rb') as source, partition.open('wb') as out:
        source.seek(2048*512); shutil.copyfileobj(source,out)
    result=subprocess.run(['fsck.fat','-n',str(partition)],capture_output=True)
    (work/'FSCK.TXT').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr
    print('PASS: unload refusals, exact memory/vector/CDS recovery, three reloads, independent file/fsck',flush=True)


if __name__=='__main__': main()
