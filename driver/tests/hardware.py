#!/usr/bin/env python3
"""Boot genuine DOS twice to validate the guarded hardware program and persistence."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import build_test as build
import struct


def boot_run(a,work,image,files,commands,phase,fault=None,extra_files=None):
    boot=work/f'{phase}.img'; shutil.copyfile(a.boot_image,boot)
    keep={'IO.SYS','MSDOS.SYS','COMMAND.COM','IBMBIO.COM','IBMDOS.COM','DBLSPACE.BIN','DRVSPACE.BIN'}
    listing=subprocess.check_output(['mdir','-b','-i',str(boot),'::']).decode()
    for name in listing.splitlines():
        if not name.endswith('/') and Path(name).name.upper() not in keep:
            subprocess.run(['mdel','-i',str(boot),name],check=True)
    config=work/'CONFIG.SYS'; config.write_bytes(b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n')
    access=' /RO' if a.mode=='readonly' else '' if a.mode=='default-ro' else ' /RW'
    if a.noverify: access+=' /NOVERIFY'
    if getattr(a,'required_fat',None): access+=' /'+a.required_fat
    if getattr(a,'skipfatcheck',False): access+=' /SKIPFATCHECK'
    batch='@echo off\nOTTERSD /DRIVE:S'+access+' > INSTALL.TXT\n'
    if a.mode.startswith('init-'):
        # Expected failures must not short-circuit collection of the next
        # diagnostic. No file API or raw writer is allowed in these modes.
        batch+='OTTERSD /STATUS > STATUS.TXT\nOTTERSD /MOUNT > MOUNT.TXT\n'
        batch+='if not errorlevel 1 goto failed\nHWRT /INFO\n'
        batch+='if not errorlevel 2 goto failed\nif errorlevel 3 goto failed\n'
    else:
        for command in commands:
            batch+=command+'\nif errorlevel 1 goto failed\n'
    batch+='echo 0 > CODE.TXT\ngoto finish\n:failed\necho 1 > CODE.TXT\n:finish\n'
    batch+='OTTERSD /UNMOUNT > UNMOUNT.TXT\necho HW-DONE > DONE.TXT\ndir a:\\ > FLUSH.TXT\n'
    auto=work/'AUTOEXEC.BAT'; auto.write_bytes(batch.replace('\n','\r\n').encode())
    boot_files=[(config,'CONFIG.SYS'),(auto,'AUTOEXEC.BAT'),(a.driver,'OTTERSD.EXE'),
                (files/'HWRT.EXE','HWRT.EXE')]
    boot_files.extend(extra_files or [])
    for source,target in boot_files:
        subprocess.run(['mcopy','-o','-i',str(boot),str(source),'::'+target],check=True)
    if a.mode=='swap':
        subprocess.run(['mcopy','-o','-i',str(boot),str(files/'HWSWAP.EXE'),'::HWSWAP.EXE'],check=True)
    conf=work/f'{phase}.conf'
    conf.write_text(f'[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={image}\n'
                    '[cpu]\ncore=normal\ncycles=fixed 3000000\n[midi]\nmpu401=none\n')
    env={k:v for k,v in os.environ.items() if not k.startswith(('OTTER_MODEL_','OTTER_TEST_'))}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',OTTER_MODEL_WRITE='1')
    if isinstance(fault,dict): env.update(fault)
    elif fault: env['OTTER_MODEL_'+fault]='1'
    with (work/f'{phase}-emulator.log').open('wb') as log:
        proc=subprocess.Popen([a.dosbox,'-conf',str(conf),'-c',f'boot "{boot}"'],env=env,stdout=log,stderr=log)
        try:
            deadline=time.monotonic()+a.timeout
            while time.monotonic()<deadline:
                done=subprocess.run(['mtype','-i',str(boot),'::DONE.TXT'],capture_output=True)
                if b'HW-DONE' in done.stdout: break
                if proc.poll() is not None: raise RuntimeError('DOS exited before completion')
                time.sleep(.3)
            else: raise RuntimeError(f'Timeout; inspect {boot}')
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    results={}
    for name in ('INSTALL.TXT','STATUS.TXT','MOUNT.TXT','CODE.TXT','GUARD.TXT','RWINFO.LOG','RWTEST.LOG','RWVERIFY.LOG','RWSTRESS.LOG','RWMEM.LOG','RWSWAP.LOG','UNMOUNT.TXT'):
        r=subprocess.run(['mtype','-i',str(boot),'::'+name],capture_output=True)
        if not r.returncode:
            results[name]=r.stdout; (work/f'{phase}-{name}').write_bytes(r.stdout)
            print(f'{phase} {name}:\n'+r.stdout.decode('cp437'),flush=True)
    return results


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot-image',type=Path,required=True)
    p.add_argument('--dosbox',required=True)
    p.add_argument('--driver',type=Path,required=True)
    p.add_argument('--tester',type=Path)
    p.add_argument('--image',type=Path,help='Copy a built kit image instead of generating an empty-kit fixture')
    p.add_argument('--timeout',type=float,default=1200)
    p.add_argument('--required-fat',choices=('FAT16','FAT32'))
    p.add_argument('--skipfatcheck',action='store_true',help='Skip only full mount FAT comparison')
    p.add_argument('--noverify',action='store_true',help='Exercise the explicit readback-disabled writable policy')
    p.add_argument('--mode',choices=('normal','swap','drop','readonly','default-ro','unmarked','no-erase','init-timeout','init-cid','init-crc'),default='normal')
    a=p.parse_args()
    if a.noverify and a.mode in ('readonly','default-ro'): p.error('--noverify requires writable installation')
    work=Path(tempfile.mkdtemp(prefix='otter-hwrt-dos-'))
    print(f'Artifacts: {work}',flush=True)
    if a.tester and a.mode!='swap':
        shutil.copyfile(a.tester,work/'HWRT.EXE')
    else: build.compile_test(work,swap_adapter=a.mode=='swap')
    image=work/'card.img'
    if a.image:
        shutil.copyfile(a.image,image)
        for name,source in [('OTTERSD.EXE',a.driver),('HWRT.EXE',work/'HWRT.EXE')]:
            kit=subprocess.check_output(['mtype','-i',str(image)+'@@1048576','::KIT/'+name])
            assert kit==source.read_bytes(),'Distributed KIT differs from tested binary: '+name
        with image.open('rb') as f:
            f.seek(2048*512); sector=f.read(512)
        layout={'total':struct.unpack_from('<I',sector,32)[0]}
    else: layout=build.prepare(image,{})
    if a.mode=='unmarked':
        subprocess.run(['mdel','-i',str(image)+'@@1048576','::RW.TAG'],check=True)
    before=image.read_bytes()
    commands=['HWRT /INFO','HWRT /TEST /ERASE','HWRT /VERIFY','HWRT /STRESS /ERASE','HWRT /MEMORY']
    if a.mode in ('drop','readonly','default-ro','unmarked'): commands=['HWRT /TEST /ERASE > GUARD.TXT']
    if a.mode=='no-erase': commands=['HWRT /TEST > GUARD.TXT']
    if a.mode=='swap': commands=['HWRT /TEST /ERASE','HWSWAP /SWAP','HWRT /VERIFY']
    faults={'init-timeout':{'OTTER_MODEL_MISSING_COMMAND':'1'},
            'init-cid':{'OTTER_MODEL_REJECT_COMMAND':'11'},
            'init-crc':{'OTTER_MODEL_BAD_REGISTER_CRC':'11'}}
    fault=faults.get(a.mode,'DROP' if a.mode=='drop' else None)
    result=boot_run(a,work,image,work,commands,'first',fault)
    if a.mode.startswith('init-'):
        assert result['CODE.TXT'].strip()==b'0','Initialization diagnostic failed to propagate'
        assert image.read_bytes()==before,'Initialization failure mutated SD image'
        fields={'init-timeout':b'error=106 stage=0','init-cid':b'error=106 stage=10',
                'init-crc':b'error=102 stage=10'}[a.mode]
        for name in ('INSTALL.TXT','STATUS.TXT','MOUNT.TXT','RWINFO.LOG'):
            assert fields in result[name],(name,result[name])
        assert b'Drive offline (DOS error 21)' in result['INSTALL.TXT']
        assert b'S: offline, 0 open files, port 330' in result['STATUS.TXT']
        assert b'Cannot mount card (DOS error 21)' in result['MOUNT.TXT']
        assert b'transmissions=0 retries=0' in result['RWINFO.LOG']
        assert b'query_CF=0' in result['RWINFO.LOG']
        assert b'ERRORLEVEL=2' in result['RWINFO.LOG']
        if a.mode=='init-crc':
            assert b'R1=00 token=FE' in result['RWINFO.LOG']
        if a.noverify: assert b'WITHOUT readback' in result['INSTALL.TXT']
        print(f'PASS: {a.mode} preserves install/status/remount/tester diagnostics without SD writes',flush=True)
        return
    if a.mode not in ('normal','swap'):
        assert result['CODE.TXT'].strip()==b'1', 'Guard/fault did not stop tester'
        if a.mode=='drop':
            assert b'transmissions=1 retries=0' in result['RWTEST.LOG']
            assert b'poison=1' in result['RWTEST.LOG']
        else:
            assert image.read_bytes()==before,'Guard failure mutated SD image'
            if a.mode in ('readonly','default-ro'):
                assert b'MODE: writable=0' in result['RWTEST.LOG']
                assert b'writing requires installation with /RW' in result['RWTEST.LOG']
                assert b'ERRORLEVEL=2' in result['RWTEST.LOG']
            elif a.mode=='unmarked':
                assert b'FAIL: supplied expendable resident-write image marker' in result['RWTEST.LOG']
                assert b'ERRORLEVEL=1' in result['RWTEST.LOG']
            else:
                assert b'STOP: /TEST and /STRESS require /ERASE' in result['GUARD.TXT']
        print(f'PASS: hardware tester {a.mode} stops safely',flush=True); return
    assert result['CODE.TXT'].strip()==b'0'
    if a.skipfatcheck:
        assert b'full mount FAT comparison is SKIPPED' in result['INSTALL.TXT']
        assert b'POLICY: mount_fat_check=SKIPPED' in result['RWTEST.LOG']
    if a.noverify:
        assert b'WITHOUT readback' in result['INSTALL.TXT']
        assert b'POLICY: write_readback=DISABLED' in result['RWTEST.LOG']
    assert b'drive is offline; card may be removed' in result['UNMOUNT.TXT']
    logs=('RWTEST.LOG','RWSWAP.LOG','RWVERIFY.LOG') if a.mode=='swap' else (
          'RWINFO.LOG','RWTEST.LOG','RWVERIFY.LOG','RWSTRESS.LOG','RWMEM.LOG')
    for name in logs:
        assert b'HWRT RESULT: PASS' in result[name],name
    raw=image.read_bytes()
    second=boot_run(a,work,image,work,['HWRT /VERIFY'],'reboot')
    assert second['CODE.TXT'].strip()==b'0'
    assert b'drive is offline; card may be removed' in second['UNMOUNT.TXT']
    assert image.read_bytes()==raw,'Fresh-boot verify wrote to card'
    for lba in (0,2048,2054): assert raw[lba*512:(lba+1)*512]==before[lba*512:(lba+1)*512]
    partition=work/'partition.img'; partition.write_bytes(raw[2048*512:(2048+layout['total'])*512])
    fsck=subprocess.run(['fsck.fat','-n',str(partition)],capture_output=True)
    (work/'FSCK.TXT').write_bytes(fsck.stdout+fsck.stderr); assert fsck.returncode==0,fsck.stdout+fsck.stderr
    for name,length,seed in [('ZERO.BIN',1025,0),('FF.BIN',1025,1),('LARGE.BIN',70000,2),('FRAG.BIN',8208,3)]:
        data=subprocess.check_output(['mtype','-i',str(image)+'@@1048576','::RWTEMP/'+name])
        expected=bytes(0 if seed==0 else 255 if seed==1 else
                       ((i*7+3+(i>>8)*13+seed*31)^(i>>16))&255 for i in range(length))
        assert data==expected,name
    print('PASS: guarded tester, stress/memory, fresh-boot verification, independent contents/fsck',flush=True)


if __name__=='__main__': main()
