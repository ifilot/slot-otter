#!/usr/bin/env python3
"""Validate the built kit under booted MS-DOS, on private disk copies."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot-image',type=Path,required=True)
    p.add_argument('--dosbox',required=True,help='DOSBox-VirtIsa with Slot-otter model')
    p.add_argument('--timeout',type=int,default=100)
    p.add_argument('--fault',choices=('tag','data'),help='Inject a private fixture fault; expect clear failure/refusal')
    a=p.parse_args()
    work=Path(tempfile.mkdtemp(prefix='otter-hardware-validation-'))
    print(f'Validation artifacts: {work}',flush=True)
    image=work/'card.img'; shutil.copyfile(HERE/'dist/OTTERHW.IMG',image)
    # Extract the shipped binaries FROM the image, not a parallel build folder.
    source=f'{image}@@1048576'
    for name in ('OTTERFS.EXE','HWTEST.EXE','RUNTEST.BAT','MANUAL.TXT','CONFIG.TXT','FILES.SHA'):
        content=subprocess.check_output(['mtype','-i',source,f'::/KIT/{name}'])
        assert content==(HERE/'dist/KIT'/name).read_bytes()
        (work/name).write_bytes(content)
    if a.fault=='tag':
        bad=work/'BAD.TAG'; bad.write_bytes(b'WRONG CARD\r\n')
        subprocess.run(['mcopy','-o','-i',source,str(bad),'::KIT.TAG'],check=True)
    elif a.fault=='data':
        # First data byte of BIG.BIN (cluster 100); fixture layout is fixed.
        with image.open('r+b') as f:
            f.seek((2048+32+2*547+98)*512); f.write(b'\xff')
    before=hashlib.sha256(image.read_bytes()).digest()
    # fsck on a partition-only copy must be clean and must never modify it.
    partition=work/'fat32.img'
    with image.open('rb') as f:
        f.seek(1048576); partition.write_bytes(f.read())
    subprocess.run(['fsck.fat','-n',str(partition)],check=True)
    boot=work/'boot.img'; shutil.copyfile(a.boot_image,boot)
    keep={'IO.SYS','MSDOS.SYS','COMMAND.COM','IBMBIO.COM','IBMDOS.COM',
          'DRBIOS.SYS','DRDOS.SYS','DRVSPACE.BIN','DBLSPACE.BIN'}
    listing=subprocess.check_output(['mdir','-b','-i',str(boot),'::']).decode()
    for name in listing.splitlines():
        if not name.endswith('/') and Path(name).name.upper() not in keep:
            subprocess.run(['mdel','-i',str(boot),name],check=True)
    (work/'CONFIG.SYS').write_bytes(b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n')
    (work/'AUTOEXEC.BAT').write_bytes(
        b'@echo off\r\nHWTEST\r\nif not errorlevel 2 goto bad\r\n'
        b'copy HWTEST.LOG NORES.LOG > NUL\r\nHWTEST /PREP\r\n'
        b'copy PREP.LOG GOODPREP.LOG > NUL\r\nOTTERFS /DRIVE:S /PORT:330 > INSTALL.LOG\r\n'
        b'HWTEST /PREP\r\nif not errorlevel 2 goto bad\r\n'
        b'copy PREP.LOG RESPREP.LOG > NUL\r\ncopy GOODPREP.LOG PREP.LOG > NUL\r\n'
        b'HWTEST /PORT:338\r\nif not errorlevel 2 goto bad\r\n'
        b'copy HWTEST.LOG PORT.LOG > NUL\r\n'
        b'OTTERFS /STATUS > STATUS.LOG\r\nCALL RUNTEST\r\nHWTEST /STRESS\r\n'
        b'echo OTTER-DONE > DONE.TXT\r\ngoto end\r\n:bad\r\necho BAD > DONE.TXT\r\n:end\r\ndir a:\\ > FLUSH.TXT\r\n')
    for name in ('OTTERFS.EXE','HWTEST.EXE','RUNTEST.BAT','CONFIG.SYS','AUTOEXEC.BAT'):
        subprocess.run(['mcopy','-o','-i',str(boot),str(work/name),'::'+name],check=True)
    config=work/'dosbox.conf'
    config.write_text(f'[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={image}\n'
                      '[cpu]\ncore=normal\ncycles=fixed 15000\n[midi]\nmpu401=none\n')
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    env.pop('OTTER_TEST_EMPTY',None); env.pop('OTTER_TEST_IMAGE2',None)
    with (work/'emulator.log').open('wb') as log:
        proc=subprocess.Popen([a.dosbox,'-conf',str(config),'-c',f'boot "{boot}"'],env=env,stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+a.timeout
            while time.monotonic()<deadline:
                result=subprocess.run(['mtype','-i',str(boot),'::DONE.TXT'],capture_output=True)
                if b'BAD' in result.stdout: raise RuntimeError('Expected setup refusal failed')
                if b'OTTER-DONE' in result.stdout: break
                if proc.poll() is not None: raise RuntimeError('Emulator exited early')
                time.sleep(.3)
            else: raise RuntimeError('Hardware kit validation timed out')
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    if a.fault:
        content=subprocess.check_output(['mtype','-i',str(boot),'::HWTEST.LOG'])
        (work/'HWTEST.LOG').write_bytes(content)
        print(content.decode('cp437'),flush=True)
        if a.fault=='tag':
            assert b'STOP:' in content and b'PASS:' not in content and b'No mutation tests ran.' in content
        else:
            assert b'FAIL: read 70000 bytes' in content and b'first_bad_offset=0' in content
            assert b'ERRORLEVEL=1' in content and b'DOS=' in content and b'extended=' in content
        assert hashlib.sha256(image.read_bytes()).digest()==before,'SD image was modified'
        print(f'PASS: injected {a.fault} fault clearly diagnosed, SD unchanged')
        return
    for name in ('PREP.LOG','INSTALL.LOG','STATUS.LOG','HWTEST.LOG','EXEC.LOG','COPY.LOG','EXTRA.LOG','STRESS.LOG'):
        content=subprocess.check_output(['mtype','-i',str(boot),'::'+name])
        (work/name).write_bytes(content)
        print(f'{name}:\n{content.decode("cp437")}',flush=True)
        if name in ('PREP.LOG','HWTEST.LOG','EXTRA.LOG','STRESS.LOG'):
            assert b'HARDWARE RESULT: 0 failures' in content, name
            assert b'FAIL:' not in content and b'STOP:' not in content, name
    for name,reason in (('NORES.LOG',b'expected mounted'),('RESPREP.LOG',b'fresh boot'),('PORT.LOG',b'matching port')):
        content=subprocess.check_output(['mtype','-i',str(boot),'::'+name])
        (work/name).write_bytes(content)
        assert b'STOP:' in content and reason in content and b'PASS:' not in content,name
    assert b'RESIDENT MCB: 17632 bytes' in (work/'STRESS.LOG').read_bytes()
    assert hashlib.sha256(image.read_bytes()).digest()==before,'SD image was modified'
    print('PASS: shipped image clean FAT32, exact kit files, booted-DOS PREP/filesystem/COPY/EXEC/STRESS; SD unchanged')

if __name__=='__main__': main()
