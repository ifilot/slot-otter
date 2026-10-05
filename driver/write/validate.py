#!/usr/bin/env python3
"""Boot actual DOS and validate writable-card profiles on disposable private copies."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
from build import prepare
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot-image',type=Path,required=True)
    p.add_argument('--dosbox',required=True)
    p.add_argument('--profile',choices=('tolerant','strict','slow','reject','timeout','status','corrupt','read-crc','no-crc','drop','resident','wrong-tag','fixed-crc','cold-start','fsinfo-mismatch','ignore-off','ignore-off-bad','strict-data','response-delay','missing-response','invalid-response','status-r1','late-busy','late-busy-status','late-busy-interference','ready-cmd55','ff-before','ff-after','recovery-crc','recovery-error','command-read','data-read','command-discard','data-discard','crc-reject-busy','crc-reject-timeout'),default='tolerant')
    p.add_argument('--spc',type=int,choices=(1,8),default=1)
    p.add_argument('--no-crc',action='store_true')
    p.add_argument('--crc-only',action='store_true')
    p.add_argument('--normal',action='store_true')
    p.add_argument('--probe',choices=('command','data'))
    p.add_argument('--cli-checks',action='store_true')
    p.add_argument('--info',action='store_true')
    p.add_argument('--diagnostic',action='store_true')
    p.add_argument('--allow-hints',action='store_true')
    p.add_argument('--timeout',type=int,default=180)
    a=p.parse_args()
    if a.profile=='strict-data' and not a.no_crc: p.error('strict-data requires --no-crc')
    if sum((a.no_crc,a.crc_only,a.normal,bool(a.probe)))>1: p.error('CRC modes are mutually exclusive')
    if a.info and (a.diagnostic or a.allow_hints): p.error('--info cannot combine with diagnostic/write override')
    work=Path(tempfile.mkdtemp(prefix=f'otter-write-{a.profile}-'))
    print(f'Artifacts: {work}',flush=True)
    image=work/'card.img'
    if a.spc==1:
        shutil.copyfile(HERE/'dist/WRITE.IMG',image)
        exe=subprocess.check_output(['mtype','-i',f'{image}@@1048576','::KIT/WTTEST.EXE'])
        assert exe==(HERE/'dist/KIT/WTTEST.EXE').read_bytes()
        layout={'start':2048,'total':71126,'data':3174,'spc':1}
    else:
        layout=prepare(image,spc=8); exe=(HERE/'dist/KIT/WTTEST.EXE').read_bytes()
    if a.profile=='wrong-tag':
        with image.open('r+b') as f: f.seek((layout['data']+1498*a.spc)*512); f.write(b'WRONG')
    if a.profile=='fsinfo-mismatch':
        if not (a.diagnostic or a.allow_hints): p.error('fsinfo-mismatch needs --diagnostic or --allow-hints')
        with image.open('r+b') as f: f.seek(2055*512+488); f.write(b'\xff'*4)
    before=image.read_bytes()
    before_hash=hashlib.sha256(before).digest()
    (work/'WTTEST.EXE').write_bytes(exe)
    boot=work/'boot.img'; shutil.copyfile(a.boot_image,boot)
    keep={'IO.SYS','MSDOS.SYS','COMMAND.COM','IBMBIO.COM','IBMDOS.COM','DRVSPACE.BIN','DBLSPACE.BIN'}
    listing=subprocess.check_output(['mdir','-b','-i',str(boot),'::']).decode()
    for name in listing.splitlines():
        if not name.endswith('/') and Path(name).name.upper() not in keep:
            subprocess.run(['mdel','-i',str(boot),name],check=True)
    (work/'CONFIG.SYS').write_bytes(b'FILES=40\r\nBUFFERS=10\r\nLASTDRIVE=S\r\n')
    for name in ('CONFIG.SYS','WTTEST.EXE'):
        subprocess.run(['mcopy','-o','-i',str(boot),str(work/name),'::'+name],check=True)
    if a.profile=='resident':
        subprocess.run(['mcopy','-o','-i',str(boot),str(ROOT/'OTTERFS.EXE'),'::OTTERFS.EXE'],check=True)
    config=work/'dosbox.conf'
    config.write_text(f'[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={image}\n'
                      '[cpu]\ncore=normal\ncycles=fixed 3000000\n[midi]\nmpu401=none\n')
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy',OTTER_MODEL_WRITE='1')
    for name in list(env):
        if name.startswith('OTTER_MODEL_') and name!='OTTER_MODEL_WRITE': env.pop(name)
    env.pop('OTTER_TEST_EMPTY',None); env.pop('OTTER_TEST_IMAGE2',None)
    if a.profile=='strict': env['OTTER_MODEL_STRICT']='1'
    if a.profile=='strict-data': env['OTTER_MODEL_STRICT_DATA']='1'
    faults={'slow':('BUSY','4096'),'reject':('REJECT','140'),'timeout':('TIMEOUT','140'),
            'status':('STATUS','140'),'corrupt':('CORRUPT','140'),'read-crc':('BAD_READ','1'),
            'no-crc':('NO_CRC','1'),'drop':('DROP','140'),'fixed-crc':('NO_CRC','2'),'cold-start':('IGNORE_CMD0','3'),'ignore-off':('IGNORE_OFF','1'),'ignore-off-bad':('IGNORE_OFF','2'),
            'response-delay':('RESPONSE_DELAY','25'),'missing-response':('WRITE_RESPONSE','1'),
            'invalid-response':('WRITE_RESPONSE','2'),'status-r1':('STATUS_R1','4'),'late-busy':('LATE_BUSY','3'),
            'ready-cmd55':('CMD55_READY','1'),'ff-before':('FF_CORRUPT','1'),
            'ff-after':('FF_CORRUPT','2'),'recovery-crc':('RECOVERY_STATUS','128'),
            'recovery-error':('RECOVERY_STATUS','32'),
            'command-read':('PROBE_FAULT','1'),'data-read':('PROBE_FAULT','2'),
            'command-discard':('PROBE_FAULT','3'),'data-discard':('PROBE_FAULT','4'),
            'crc-reject-busy':('REJECT_BUSY','64'),'crc-reject-timeout':('REJECT_BUSY','4294967295')}
    if a.profile in faults:
        key,value=faults[a.profile]; env['OTTER_MODEL_'+key]=value

    if a.profile=='crc-reject-busy': env['OTTER_MODEL_PROBE_FAULT']='7'
    if a.profile in ('ignore-off-bad','ff-before','ff-after','command-discard','data-discard'): env['OTTER_MODEL_RESPONSE_HIGH']='224'
    if a.profile=='ready-cmd55': env['OTTER_MODEL_ACMD41_IDLE']='3'
    if a.profile=='late-busy': env['OTTER_MODEL_BUSY']='4096'
    if a.profile in ('late-busy-status','late-busy-interference'):
        env['OTTER_MODEL_BUSY']='4096'
        env['OTTER_MODEL_LATE_BUSY']='3' if a.profile=='late-busy-status' else '4'
        if a.profile=='late-busy-status': env['OTTER_MODEL_STATUS']='1'

    def boot_run(commands,phase):
        (work/'AUTOEXEC.BAT').write_bytes(b'@echo off\r\n'+commands+
            b'if errorlevel 2 goto code2\r\nif errorlevel 1 goto code1\r\necho 0 > CODE.TXT\r\ngoto done\r\n'
            b':code2\r\necho 2 > CODE.TXT\r\ngoto done\r\n:code1\r\necho 1 > CODE.TXT\r\n'
            b':done\r\necho WRITE-DONE > DONE.TXT\r\ndir a:\\ > FLUSH.TXT\r\n')
        for name in ('DONE.TXT','CODE.TXT'):
            subprocess.run(['mdel','-i',str(boot),'::'+name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        subprocess.run(['mcopy','-o','-i',str(boot),str(work/'AUTOEXEC.BAT'),'::AUTOEXEC.BAT'],check=True)
        with (work/f'{phase}-emulator.log').open('wb') as log:
            proc=subprocess.Popen([a.dosbox,'-conf',str(config),'-c',f'boot "{boot}"'],env=env,stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+a.timeout
                while time.monotonic()<deadline:
                    marker=subprocess.run(['mtype','-i',str(boot),'::DONE.TXT'],capture_output=True)
                    if b'WRITE-DONE' in marker.stdout: break
                    if proc.poll() is not None: raise RuntimeError('Emulator exited early')
                    time.sleep(.3)
                else: raise RuntimeError(f'{phase} timed out')
            finally:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        return int(subprocess.check_output(['mtype','-i',str(boot),'::CODE.TXT']).strip())

    if a.cli_checks:
        invalid=(b'/INFO /WRITE /BATCH',b'/WRITE /BATCH /INFO',
                 b'/INFO /VERIFY',b'/VERIFY /INFO',b'/INFO /DIAG',b'/DIAG /INFO',
                 b'/WRITE /VERIFY /BATCH',b'/WRITE /DIAG /BATCH',
                 b'/WRITE /BATCH /NOCRC /CRCONLY',b'/ALLOWHINTS /INFO',
                 b'/BATCH /INFO',b'/PORT:000',b'/UNKNOWN',b'/NORMAL /INFO',
                 b'/WRITE /BATCH /NORMAL /NOCRC',b'/WRITE /BATCH /NORMAL /CRCONLY',
                 b'/CMDCRC /INFO',b'/DATACRC /VERIFY',b'/WRITE /BATCH /CMDCRC /DATACRC',
                 b'/WRITE /BATCH /DATACRC /CMDCRC',b'/WRITE /BATCH /CMDCRC /NORMAL',
                 b'/WRITE /BATCH /DATACRC /NORMAL',b'/WRITE /BATCH /CMDCRC /NOCRC',
                 b'/WRITE /BATCH /DATACRC /NOCRC',b'/WRITE /BATCH /CMDCRC /CRCONLY',
                 b'/WRITE /BATCH /DATACRC /CRCONLY')
        commands=b''
        for i,args in enumerate(invalid):
            commands+=b'WTTEST '+args+b' > CLI'+str(i).encode()+b'.TXT\r\nif errorlevel 3 goto badcli\r\nif not errorlevel 2 goto badcli\r\n'
        commands+=b'echo CLI-PASS > CLI.OK\r\nverify on\r\ngoto clidone\r\n:badcli\r\nWTTEST /UNKNOWN\r\n:clidone\r\n'
        assert boot_run(commands,'cli')==2
        assert b'CLI-PASS' in subprocess.check_output(['mtype','-i',str(boot),'::CLI.OK'])
        listing=subprocess.check_output(['mdir','-b','-i',str(boot),'::']).upper()
        for logname in (b'WRITE.LOG',b'WINFO.LOG',b'WVERIFY.LOG',b'WDIAG.LOG'):
            assert logname not in listing
        for i in range(len(invalid)):
            output=subprocess.check_output(['mtype','-i',str(boot),'::CLI'+str(i)+'.TXT'])
            assert b'STARTUP:' not in output
        assert hashlib.sha256(image.read_bytes()).digest()==before_hash
        print(f'PASS: {len(invalid)} DOS CLI conflicts rejected with exit 2 before initialization; no logs or SD writes')
        return

    mode=b'/INFO' if a.info else b'/DIAG' if a.diagnostic else b'/WRITE /BATCH'+(b' /ALLOWHINTS' if a.allow_hints else b'')
    if a.no_crc: mode+=b' /NOCRC'
    if a.crc_only: mode+=b' /CRCONLY'
    if a.normal: mode+=b' /NORMAL'
    if a.probe: mode+=b' /CMDCRC' if a.probe=='command' else b' /DATACRC'
    commands=(b'OTTERFS /DRIVE:S > INSTALL.LOG\r\n' if a.profile=='resident' else b'')+b'WTTEST '+mode+b' > CONSOLE.LOG\r\n'
    code=boot_run(commands,'write')
    console=subprocess.check_output(['mtype','-i',str(boot),'::CONSOLE.LOG']); (work/'CONSOLE.LOG').write_bytes(console)
    if a.profile=='resident':
        assert code==2 and b'STOP: reboot without OTTERFS' in console
        assert hashlib.sha256(image.read_bytes()).digest()==before_hash
        print('PASS: resident guard refused before card I/O; SD unchanged'); return
    logname='WINFO.LOG' if a.info else 'WDIAG.LOG' if a.diagnostic else 'WRITE.LOG'
    log=subprocess.check_output(['mtype','-i',str(boot),'::'+logname]); (work/logname).write_bytes(log)
    print(log.decode('cp437'),flush=True)
    if a.info:
        assert code==0 and b'INFO ONLY: no block writes issued.' in log
        assert b'initial_MISO=00' in log and b'packets=1' in log
        assert hashlib.sha256(image.read_bytes()).digest()==before_hash
        print('PASS: DOS INFO starts cold/nonready without HWTEST; SD unchanged'); return
    if a.diagnostic:
        expected=1 if a.profile=='fsinfo-mismatch' else 0
        assert code==expected and b'DIAG RESULT:' in log and b'accepted_writes=0' in log
        assert b'FSINFO primary:' in log and b'FSINFO backup:' in log
        if expected:
            assert b'ALLOWHINTS ELIGIBLE: YES' in log and b'other_bytes=0' in log
        assert hashlib.sha256(image.read_bytes()).digest()==before_hash
        print(f'PASS: DOS diagnostic {a.profile}: precise FSInfo report; SD unchanged'); return
    success=a.profile in ('tolerant','strict','slow','fixed-crc','cold-start','fsinfo-mismatch','response-delay','late-busy','ready-cmd55','recovery-crc','crc-reject-busy') or ((a.normal or a.no_crc) and a.profile in ('ff-after','recovery-error')) or (a.no_crc and a.profile=='no-crc') or ((a.crc_only or a.normal or a.probe) and a.profile in ('ignore-off','ignore-off-bad'))
    if a.profile in ('command-read','data-read','command-discard','data-discard'):
        trigger='command' if a.profile.startswith('command') else 'data'
        success=a.normal or a.no_crc or (a.probe and a.probe!=trigger)
    if a.profile=='crc-reject-timeout': success=a.normal or a.no_crc or a.probe=='command'
    if not success:
        assert code==1 and b'FAIL:' in log
        if a.profile!='no-crc' or a.no_crc: assert b'WRITE RESULT: 1 failures' in log
        else: assert b'error=102 stage=59' in log
        if a.profile in ('read-crc','no-crc','wrong-tag'):
            assert hashlib.sha256(image.read_bytes()).digest()==before_hash
        else:
            assert b'poison=1' in log,'ambiguous or rejected write did not stop session'
        # Faults may deliberately leave metadata incomplete; never run a repair.
        for lba in (0,2048,2054):
            assert image.read_bytes()[lba*512:(lba+1)*512]==before[lba*512:(lba+1)*512]
        if a.profile in ('ignore-off','ignore-off-bad'):
            assert b'WRITE TRACE:' in log and b'error=105' in log
            assert b'matches_original_scratch=YES' in log and b'HEX repeat 496:' in log
            assert b'WRITE BUSY:' in log and b'STATUS READY:' in log
            if a.profile=='ignore-off-bad':
                assert b'PASS: CRC-OFF valid-data-CRC control' in log
                assert b'PROBE: CRC-OFF with INVALID data CRC' in log
                assert b'accepted_writes=57' in log
            else:
                assert b'FAIL: CRC-OFF valid-data-CRC control' in log
                assert b'PROBE: CRC-OFF with INVALID data CRC' not in log
        if a.profile in ('ff-before','ff-after'):
            phase=b'PRE-FAULT' if a.profile=='ff-before' else b'AFTER-DATA-CRC' if a.probe=='data' else b'AFTER-COMMAND-CRC'
            assert b'phase='+phase+b' index=1 kind=FF' in log
            assert b'differing_bytes=508' in log and b'error=105' in log
            assert b'response=E5 CMD13_R1=00 status=00' in log
            assert b'matches_expected=NO matches_first=YES' in log
            assert b'PHASE: FILESYSTEM' not in log
            if a.profile=='ff-before': assert b'PHASE: FAULT-PROBES' not in log
        if a.profile=='recovery-error':
            assert b'error=104' in log and b'RECOVERY STATUS: read=0 R1=00 R2=20' in log
            assert b'PHASE: FILESYSTEM' not in log
        if a.profile in ('command-read','data-read','command-discard','data-discard'):
            trigger=b'bad-command-CRC' if a.profile.startswith('command') else b'bad-data-CRC'
            assert b'ACCESS CHECK: after='+trigger in log
            assert b'PHASE: FILESYSTEM' not in log and b'allocated=0 freed=0' in log
            if a.profile.endswith('read'): assert b'error=101 stage=17' in log
            else:
                assert b'error=105 stage=17' in log
                assert b'differing_bytes=512 matches_original_scratch=YES' in log
                assert b'matches_expected=NO matches_first=YES' in log
        if a.profile=='crc-reject-timeout':
            assert b'error=101 stage=324 poison=1' in log and b'response=0B' in log
            assert b'PHASE: FILESYSTEM' not in log
        if a.profile=='missing-response': assert b'error=101 stage=124' in log and b'WRITE RESPONSE: polls=100' in log
        if a.profile=='invalid-response': assert b'error=103 stage=124' in log and b'response=00' in log
        if a.profile=='late-busy-status':
            assert b'error=104 stage=13' in log and b'status=20' in log
            assert b'CMD13 TRANSMIT RX: FF FF FF FF FF FF' in log
        if a.profile=='late-busy-interference':
            assert b'error=101 stage=13' in log
            assert b'card not ready during CMD13 transmission' in log
            assert b'CMD13 TRANSMIT RX: 00' in log
        if a.profile=='status-r1': assert b'error=104 stage=13' in log and b'CMD13_R1=04' in log
        if a.profile=='strict-data':
            assert b'error=102' in log and b'response=0B' in log
            assert b'accepted_writes=0' in log and hashlib.sha256(image.read_bytes()).digest()==before_hash
        print(f'PASS: {a.profile} fault diagnosed and writes stopped; MBR/boot protected'); return
    assert code==0 and b'WRITE RESULT: 0 failures' in log and b'FAIL:' not in log
    if a.profile=='cold-start': assert b'STARTUP: CMD0 attempts=4' in log
    if a.profile=='ready-cmd55':
        assert log.count(b'CMD=55 arg=00000000 R1=00 error=0')==4
        assert log.count(b'CMD=41 arg=40000000 R1=01 error=0')==3
    if a.profile=='recovery-crc': assert b'R1=08 R2=FF (no R2 for command error)' in log
    if a.profile=='crc-reject-busy' and not (a.normal or a.no_crc or a.probe=='command'):
        assert b'PROBE DATA RESULT: return=-1 error=102 stage=324 poison=0' in log
        assert b'nonready_polls=64' in log
    if a.probe=='command': assert b'PROBE DATA RESULT:' not in log
    if a.probe=='data': assert b'PROBE COMMAND:' not in log
    assert b'PROGRESS: append bytes=70000/70000' in log
    if a.normal:
        assert b'PHASE: FAULT-PROBES'  not in log and b'PHASE: POST-FAULT' not in log
    # Independent checker and filesystem implementation inspect the result.
    raw=image.read_bytes(); partition=work/'partition.img'
    partition.write_bytes(raw[2048*512:(2048+layout['total'])*512])
    checked=subprocess.run(['fsck.fat','-n',str(partition)],capture_output=True)
    (work/'FSCK.TXT').write_bytes(checked.stdout+checked.stderr)
    print(checked.stdout.decode(),flush=True); assert checked.returncode==0,checked.stdout
    source=f'{image}@@1048576'
    for n,size,seed in [('Z0.BIN',0,3),('B1.BIN',1,4),('B511.BIN',511,5),('B512.BIN',512,6),
                        ('B513.BIN',513,7),('B4096.BIN',4096,8),('BIG.BIN',70000,9),
                        ('FRAGNEW.BIN',a.spc*512*4,59),('HIGHNEW.BIN',1537,79),('SHORT.BIN',17,39),('SUB/NOTE.BIN',1025,19)]:
        result=subprocess.check_output(['mtype','-i',source,'::WTEST/'+n])
        assert result==bytes((i*7+seed+(i>>9)*13+(i>>17)*19)%256 for i in range(size)),n
    appended=bytearray((i*7+29+(i>>9)*13+(i>>17)*19)%256 for i in range(1535)); appended[510:514]=b'\xe7'*4
    assert subprocess.check_output(['mtype','-i',source,'::WTEST/APPEND.BIN'])==appended
    for lba in (0,2048,2054,2056):
        assert raw[lba*512:(lba+1)*512]==before[lba*512:(lba+1)*512],'protected/scratch sector changed'
    # Preserve every originally allocated DATA cluster, including kit, marker and old files.
    oldfat=before[(2048+32)*512:(2048+32+547)*512]
    newfat=raw[(2048+32)*512:(2048+32+547)*512]
    root=layout['data']*512
    assert raw[root:root+8*32]==before[root:root+8*32]
    assert raw[root+9*32:root+a.spc*512]==before[root+9*32:root+a.spc*512]
    root_tail=(layout['data']+8*a.spc)*512
    assert raw[root_tail:root_tail+a.spc*512]==before[root_tail:root_tail+a.spc*512]
    for c in range(70002):
        old=struct.unpack_from('<I',oldfat,c*4)[0]
        if old: assert struct.unpack_from('<I',newfat,c*4)[0]==old,f'original FAT entry changed: {c}'
        if c>=2 and struct.unpack_from('<I',oldfat,c*4)[0] and c not in (2,10):
            offset=(layout['data']+(c-2)*a.spc)*512
            assert raw[offset:offset+a.spc*512]==before[offset:offset+a.spc*512],f'original cluster changed: {c}'
    written_hash=hashlib.sha256(raw).digest()
    # New emulator process/card initialization proves persistence, and VERIFY is read-only.
    for k in list(env):
        if k.startswith('OTTER_MODEL_') and k not in ('OTTER_MODEL_WRITE','OTTER_MODEL_STRICT'): env.pop(k)
    assert boot_run(b'WTTEST /VERIFY'+(b' /NOCRC' if a.no_crc else b'')+b' > VCONSOLE.LOG\r\n','fresh-verify')==0
    verify=subprocess.check_output(['mtype','-i',str(boot),'::WVERIFY.LOG']); (work/'WVERIFY.LOG').write_bytes(verify)
    print(verify.decode('cp437'),flush=True)
    assert b'VERIFY RESULT: 0 failures' in verify and b'accepted_writes=0' in verify
    assert hashlib.sha256(image.read_bytes()).digest()==written_hash
    print(f'PASS: DOS {a.profile} spc={a.spc}: writes, independent content/fsck, protected clusters, fresh-boot persistence; VERIFY unchanged')

if __name__=='__main__': main()
