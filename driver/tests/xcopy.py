#!/usr/bin/env python3
"""Exercise the supplied genuine DOS XCOPY on a private BIOS FAT16 HDD and SD.

XCOPY/EXPAND come from separately supplied licensed media, never the release kit.
The compiler may use DOSBox's host shell; the copy always runs booted genuine DOS.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from kit_fixture import prepare


def run(cmd,**kw):
    return subprocess.run(cmd,check=True,**kw)


def extract_media(work,boot,expand_media):
    for media,name,target in ((boot,'XCOPY.EX_','XCOPY.EX_'),(expand_media,'EXPAND.EXE','EXPAND.EXE')):
        (work/target).write_bytes(subprocess.check_output(['mtype','-i',str(media),'::'+name]))
    for name in ('XCOPYT.C',): shutil.copyfile(ROOT/'tests'/name,work/name)
    for name in ('OTTER.H','RWSD.H'): shutil.copyfile(ROOT/name,work/name)
    for source in work.iterdir():
        if source.suffix.upper() in ('.C','.H'):
            b=source.read_bytes().replace(b'\r\n',b'\n').rstrip(b'\x1a')
            source.write_bytes(b.replace(b'\n',b'\r\n'))
    commands=[f'mount c "{Path(os.environ.get("TOOLCHAIN_DIR",ROOT.parent/"buildenv")).resolve()}"',
              f'mount d "{work}"',r'set PATH=C:\TC','d:',
              'expand XCOPY.EX_ XCOPY.EXE > EXPAND.TXT',
              'tcc -ms -O -eXCOPYT.EXE XCOPYT.C > BUILD.TXT','exit']
    with (work/'compiler.log').open('wb') as f:
        run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',
             *sum((['-c',c] for c in commands),[])],
            env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=f,stderr=f,timeout=60)
    assert (work/'XCOPY.EXE').read_bytes()[:2]==b'MZ'
    text=(work/'BUILD.TXT').read_text()
    assert (work/'XCOPYT.EXE').is_file() and not re.search(r'(?m)^(Error|Fatal|Warning)[ :]',text),text
    print('XCOPY media SHA256: '+hashlib.sha256((work/'XCOPY.EXE').read_bytes()).hexdigest(),flush=True)


def pattern(length,seed):
    return bytes(((i*7+3+(i>>8)*13+seed*31)^(i>>16))&255 for i in range(length))


def hdd_fixture(work):
    image=work/'hdd.img'; part=work/'hdd-part.img'
    run(['mkfs.fat','-C','-F','16','-g','16/63','-h','63','-n','COPYSOURCE',str(part),'32224'],stdout=subprocess.DEVNULL)
    image.write_bytes(bytes(64*16*63*512))
    with image.open('r+b') as f:
        mbr=bytearray(512)
        mbr[446:462]=struct.pack('<B3sB3sII',0,b'\x01\x01\x00',6,b'\x0f\x3e\x3f',63,64448)
        mbr[510:512]=b'\x55\xaa';f.write(mbr);f.seek(63*512);f.write(part.read_bytes())
    io=['-i',str(image)+'@@32256']
    for name in ('LARGE','TREE','TREE/NEST','TREE/NEST/EMPTY','CTRL'):
        run(['mmd',*io,'::'+name])
    files={'LARGE/BIG.BIN':pattern(409600,1)}
    for i,length in enumerate((0,1,511,512,513,4095,4096,4097,65535,65536)):
        files['TREE/B%02u.BIN'%i]=pattern(length,i+2)
    for i in range(20): files['TREE/NEST/F%02u.DAT'%i]=pattern(37+i,i)
    for path,data in files.items():
        local=work/'input.bin';local.write_bytes(data)
        run(['mcopy','-o',*io,str(local),'::'+path])
    return image,files


def file_metadata(image,offset,path):
    io=['-i',str(image)+'@@'+str(offset)]
    listing=subprocess.check_output(['mdir',*io,'::'+path]).decode('cp437')
    stem=Path(path).stem.upper()
    lines=[line.split() for line in listing.splitlines() if line.split() and line.split()[0].upper()==stem]
    assert len(lines)==1,(path,listing)
    attrs=subprocess.check_output(['mattrib',*io,'::'+path]).decode('cp437').split('::')[0].strip()
    return tuple(lines[0][2:]),attrs


def boot_run(a,work,card,hdd,phase,commands,access):
    boot=work/(phase+'.img');shutil.copyfile(a.boot_image,boot)
    keep={'IO.SYS','MSDOS.SYS','COMMAND.COM','IBMBIO.COM','IBMDOS.COM','DRVSPACE.BIN','DBLSPACE.BIN'}
    listing=subprocess.check_output(['mdir','-b','-i',str(boot),'::']).decode()
    for name in listing.splitlines():
        if not name.endswith('/') and Path(name).name.upper() not in keep: run(['mdel','-i',str(boot),name])
    (work/'CONFIG.SYS').write_bytes(b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n')
    batch='@echo off\nOTTERSD /DRIVE:S '+access+' > INSTALL.TXT\nif errorlevel 1 goto failed\n'
    for command in commands:
        # DOS5 XCOPY can leave exit=1 after an empty-directory traversal.
        # Compare it to the HDD->HDD control and check all bytes below.
        level=2 if ('TREE.TXT' in command or 'CTRL.TXT' in command) else 1
        batch+=command+'\nif errorlevel %u goto failed\n'%level
    batch+='echo 0 > CODE.TXT\ngoto finish\n:failed\necho 1 > CODE.TXT\n:finish\n'
    batch+='OTTERSD /UNMOUNT > UNMOUNT.TXT\necho XCOPY-DONE > DONE.TXT\ndir a:\\ > FLUSH.TXT\n'
    (work/'AUTOEXEC.BAT').write_bytes(batch.replace('\n','\r\n').encode())
    for name,source in [('CONFIG.SYS',work/'CONFIG.SYS'),('AUTOEXEC.BAT',work/'AUTOEXEC.BAT'),
                        ('OTTERSD.EXE',a.driver),('XCOPY.EXE',work/'XCOPY.EXE'),('XCOPYT.EXE',work/'XCOPYT.EXE')]:
        run(['mcopy','-o','-i',str(boot),str(source),'::'+name])
    conf=work/(phase+'.conf')
    conf.write_text(f'[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={card}\n[cpu]\ncore=normal\ncycles=fixed 3000000\n[midi]\nmpu401=none\n')
    env={k:v for k,v in os.environ.items() if not k.startswith(('OTTER_MODEL_','OTTER_TEST_'))}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',OTTER_MODEL_WRITE='1')
    with (work/(phase+'-emulator.log')).open('wb') as log:
        proc=subprocess.Popen([a.dosbox,'-conf',str(conf),'-c',f'imgmount 2 "{hdd}" -t hdd -fs none -size 512,63,16,64',
                               '-c',f'boot "{boot}"'],env=env,stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+a.timeout
            while time.monotonic()<deadline:
                done=subprocess.run(['mtype','-i',str(boot),'::DONE.TXT'],capture_output=True)
                if b'XCOPY-DONE' in done.stdout: break
                if proc.poll() is not None: raise RuntimeError('DOS exited before XCOPY completion')
                time.sleep(.3)
            else: raise RuntimeError('XCOPY timed out; artifacts '+str(work))
        finally:
            proc.terminate()
            try:proc.wait(timeout=5)
            except subprocess.TimeoutExpired:proc.kill();proc.wait()
    result={}
    for name in ('INSTALL.TXT','CTRL.TXT','BIG.TXT','TREE.TXT','LIVE.TXT','BACK.TXT','CODE.TXT','UNMOUNT.TXT'):
        r=subprocess.run(['mtype','-i',str(boot),'::'+name],capture_output=True)
        if r.returncode==0:
            result[name]=r.stdout;(work/(phase+'-'+name)).write_bytes(r.stdout)
            print(phase+' '+name+':\n'+r.stdout.decode('cp437'),flush=True)
    return result


def check_hdd(hdd,files,metadata,work):
    for path,data in files.items():
        assert subprocess.check_output(['mtype','-i',str(hdd)+'@@32256','::'+path])==data,('source changed',path)
        assert file_metadata(hdd,32256,path)==metadata[path],('source metadata changed',path)
    part=work/'checked-hdd.img';raw=hdd.read_bytes()
    part.write_bytes(raw[63*512:(63+64448)*512])
    result=subprocess.run(['fsck.fat','-n',str(part)],capture_output=True)
    (work/'HDD-FSCK.TXT').write_bytes(result.stdout+result.stderr)
    assert result.returncode==0,result.stdout+result.stderr


def counters(text):
    match=re.search(rb'XCOPY RESULT: exit=(-?\d+) ticks=(\d+) completed=(\d+) transmissions=(\d+) retries=(\d+) error=(\d+) poison=(\d+)',text)
    assert match,text
    return tuple(map(int,match.groups()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dosbox',required=True);p.add_argument('--boot-image',type=Path,required=True)
    p.add_argument('--expand-media',type=Path,required=True);p.add_argument('--driver',type=Path,required=True)
    p.add_argument('--spc',type=int,choices=(1,8,32),default=1)
    p.add_argument('--image',type=Path,help='Copy and test this exact supplied image; --spc must match')
    p.add_argument('--mode',choices=('verified','noverify','readonly'),default='verified')
    p.add_argument('--timeout',type=float,default=1200)
    a=p.parse_args();work=Path(tempfile.mkdtemp(prefix='otter-xcopy-'));print('Artifacts: '+str(work),flush=True)
    extract_media(work,a.boot_image,a.expand_media);hdd,files=hdd_fixture(work)
    card=work/'card.img'
    if a.image:
        shutil.copyfile(a.image,card)
        with card.open('rb') as f:
            f.seek(2048*512); boot=f.read(512)
        assert boot[13]==a.spc,'Supplied image cluster size differs from --spc'
        layout={'start':2048,'total':struct.unpack_from('<H',boot,19)[0] or struct.unpack_from('<I',boot,32)[0]}
    elif a.spc==32:
        from fat16_fixture import prepare as prepare16
        layout=prepare16(card)
    else: layout=prepare(card,spc=a.spc)
    for name in ('COPY','TREE'):run(['mmd','-i',str(card)+'@@1048576','::'+name])
    metadata={path:file_metadata(hdd,32256,path) for path in files}
    before=card.read_bytes()
    access='/RO' if a.mode=='readonly' else '/RW /NOVERIFY' if a.mode=='noverify' else '/RW'
    run(['mmd','-i',str(hdd)+'@@32256','::LIVE'])
    commands=[
        r'XCOPYT C:\TREE\*.* C:\CTRL /S /E > CTRL.TXT',
        r'XCOPYT C:\LARGE\*.* S:\COPY /S /E > BIG.TXT',
        r'XCOPYT C:\TREE\*.* S:\TREE /S /E > TREE.TXT']
    if a.mode!='readonly':
        commands.append(r'XCOPYT S:\COPY\*.* C:\LIVE /S /E > LIVE.TXT')
    result=boot_run(a,work,card,hdd,'first',commands,access)
    if a.mode=='readonly':
        assert result['CODE.TXT'].strip()==b'1'
        assert card.read_bytes()==before,'read-only XCOPY modified SD'
        assert counters(result['BIG.TXT'])[0]!=0
        assert b'drive is offline' in result['UNMOUNT.TXT']
        check_hdd(hdd,files,metadata,work)
        print('PASS: actual XCOPY read-only refusal; card byte-identical',flush=True);return
    assert result['CODE.TXT'].strip()==b'0','XCOPY returned a failure'
    control=counters(result['CTRL.TXT'])
    assert control[2:]==(0,0,0,0,0),'HDD-only copy touched SD'
    for name in ('BIG.TXT','TREE.TXT'):
        count=counters(result[name])
        assert count[2]>0 and count[3]==count[2] and count[4:]==(0,0,0),count
    assert counters(result['BIG.TXT'])[2]>=800
    assert counters(result['LIVE.TXT'])[0]==0
    assert counters(result['LIVE.TXT'])[2:]==(0,0,0,0,0),'Writable-mount read copied with unexpected SD writes/faults'
    assert subprocess.check_output(['mtype','-i',str(hdd)+'@@32256','::LIVE/BIG.BIN'])==files['LARGE/BIG.BIN']
    assert file_metadata(hdd,32256,'LIVE/BIG.BIN')==metadata['LARGE/BIG.BIN']
    check_hdd(hdd,files,metadata,work)
    assert b'drive is offline' in result['UNMOUNT.TXT']
    assert b'XCOPY RESULT: exit=0' in result['BIG.TXT']
    control_code=re.search(rb'XCOPY RESULT: exit=(\d+)',result['CTRL.TXT'])[1]
    tree_code=re.search(rb'XCOPY RESULT: exit=(\d+)',result['TREE.TXT'])[1]
    assert tree_code==control_code and int(tree_code) in (0,1),'SD tree copy differs from native HDD control'
    for name in ('BIG.TXT','TREE.TXT'):
        assert (b'readback=OFF' if a.mode=='noverify' else b'readback=ON') in result[name]
    for path,data in files.items():
        dest='COPY/BIG.BIN' if path.startswith('LARGE/') else path
        assert subprocess.check_output(['mtype','-i',str(card)+'@@1048576','::'+dest])==data,dest
        assert file_metadata(card,1048576,dest)==file_metadata(hdd,32256,path),('metadata',dest)
        if path.startswith('TREE/'):
            assert subprocess.check_output(['mtype','-i',str(hdd)+'@@32256','::CTRL/'+path[5:]])==data,path
    run(['mdir','-i',str(card)+'@@1048576','::TREE/NEST/EMPTY'],stdout=subprocess.DEVNULL)
    raw=card.read_bytes()
    # A fresh /RO mount copies results back to the BIOS HDD; no SD writes allowed.
    run(['mmd','-i',str(hdd)+'@@32256','::BACK'])
    second=boot_run(a,work,card,hdd,'reboot',[r'XCOPYT S:\COPY\*.* C:\BACK /S /E > BACK.TXT'],'/RO')
    assert second['CODE.TXT'].strip()==b'0'
    assert counters(second['BACK.TXT'])[0]==0
    assert counters(second['BACK.TXT'])[2:]==(0,0,0,0,0)
    assert b'drive is offline' in second['UNMOUNT.TXT']
    check_hdd(hdd,files,metadata,work)
    assert card.read_bytes()==raw,'fresh-boot XCOPY read altered card'
    assert subprocess.check_output(['mtype','-i',str(hdd)+'@@32256','::BACK/BIG.BIN'])==files['LARGE/BIG.BIN']
    part=work/'sd-part.img';part.write_bytes(raw[layout['start']*512:(layout['start']+layout['total'])*512])
    checked=subprocess.run(['fsck.fat','-n',str(part)],capture_output=True)
    (work/'FSCK.TXT').write_bytes(checked.stdout+checked.stderr)
    assert checked.returncode==0,checked.stdout+checked.stderr
    print('PASS: genuine DOS XCOPY HDD->SD, nested/boundary files, reboot SD->HDD, exact bytes/fsck',flush=True)

if __name__=='__main__':main()
