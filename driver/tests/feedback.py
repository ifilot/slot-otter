#!/usr/bin/env python3
"""Boot real DOS to verify console feedback, redirection and version output.

Uses private copies of boot/card images. Requires the shared model adapter.
"""
import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile

import hardware
import kit_fixture
import fat16_fixture

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dosbox',required=True)
    parser.add_argument('--boot-image',type=Path,required=True)
    parser.add_argument('--driver',type=Path,required=True)
    parser.add_argument('--tester',type=Path,required=True)
    parser.add_argument('--timeout',type=float,default=180)
    parser.add_argument('--filesystem',choices=('FAT16','FAT32'),default='FAT32')
    args=parser.parse_args()
    args.mode='normal'; args.noverify=False
    work=Path(tempfile.mkdtemp(prefix='otter-feedback-dos-'))
    print('Artifacts: '+str(work),flush=True)
    source=ROOT/'tests/FEEDVIEW.C'
    (work/source.name).write_bytes(source.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    with (work/'compiler.log').open('wb') as log:
        subprocess.run(['dosbox','-noconsole','-exit',
                        '-c',f'mount c "{ROOT.parent / "buildenv"}"',
                        '-c',f'mount d "{work}"','-c',r'set PATH=C:\TC',
                        '-c','d:','-c','tcc -ms -eFEEDVIEW.EXE FEEDVIEW.C > BUILD.TXT',
                        '-c','exit'],env=env,stdout=log,stderr=log,check=True,timeout=60)
    build=(work/'BUILD.TXT').read_text()
    assert not re.search(r'(?mi)^\s*(?:Error|Warning|Fatal)',build),build
    assert (work/'FEEDVIEW.EXE').exists(),build
    shutil.copyfile(args.tester,work/'HWRT.EXE')
    image=work/'card.img'
    if args.filesystem=='FAT16': fat16_fixture.prepare(image)
    else: kit_fixture.prepare(image,{})
    commands=[
        'OTTERSD /STATUS > STATUS.TXT',
        'OTTERSD /UNMOUNT > UNMOUNT.TXT',
        'CLS','OTTERSD /MOUNT > NUL','FEEDVIEW QUIET.SCR',
        'OTTERSD /UNMOUNT > UNMOUNT.TXT',
        'CLS','OTTERSD /MOUNT','FEEDVIEW MOUNT.SCR',
        r'echo safe feedback > S:\FEEDBACK.TXT',
        'CLS','OTTERSD /UNMOUNT','FEEDVIEW UNMOUNT.SCR',
        'OTTERSD /MOUNT > MOUNT.TXT',
        r'echo committed on unload > S:\UNLOAD.TXT',
        'CLS','OTTERSD /UNLOAD','FEEDVIEW UNLOAD.SCR',
        'CLS','OTTERSD /DRIVE:S /PORT:330 /RW','FEEDVIEW LOAD.SCR',
    ]
    results=hardware.boot_run(args,work,image,work,commands,'feedback',
                            extra_files=[(work/'FEEDVIEW.EXE','FEEDVIEW.EXE')])
    assert results['CODE.TXT'].strip()==b'0',results
    version=re.search(r'#define OTTER_VERSION_TEXT "([^"]+)"',(ROOT/'RWSD.H').read_text())[1]
    banner=('OTTERSD '+version+' - Slot-otter FAT16/FAT32 driver').encode()
    for name in ('INSTALL.TXT','STATUS.TXT','MOUNT.TXT','UNMOUNT.TXT'):
        text=results[name]
        assert banner in text,(name,text)
        assert b'Comparing FAT copies:' not in text,(name,text)
        assert b'\r' not in text.replace(b'\r\n',b''),(name,text)
    assert ('Resident driver version: '+version).encode() in results['STATUS.TXT']
    for name in ('LOAD','MOUNT','UNMOUNT','UNLOAD','QUIET'):
        raw=subprocess.check_output(['mtype','-i',str(work/'feedback.img'),'::'+name+'.SCR'])
        (work/(name+'.SCR')).write_bytes(raw)
        text='\n'.join(line.rstrip() for line in raw.decode('cp437').splitlines()).strip()
        print(name+' console:\n'+text,flush=True)
        if name=='QUIET':
            assert not text,'NUL redirection must not alter the screen'
        else:
            assert banner.decode() in text,(name,text)
            assert 'Comparing FAT copies: 100%' in text,(name,text)
    content=subprocess.check_output(['mtype','-i',str(image)+'@@1048576','::UNLOAD.TXT'])
    assert content.strip()==b'committed on unload',content
    partition=work/'partition.img'
    with image.open('rb') as src, partition.open('wb') as dest:
        src.seek(2048*512); shutil.copyfileobj(src,dest)
    check=subprocess.run(['fsck.fat','-n',str(partition)],capture_output=True)
    assert check.returncode==0,check.stdout+check.stderr
    print('PASS: real DOS console feedback, quiet redirection, version, commit persistence and fsck',flush=True)


if __name__=='__main__':
    main()
