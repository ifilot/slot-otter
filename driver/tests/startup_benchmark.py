#!/usr/bin/env python3
"""Compare two driver startup times under the same booted DOS/model/cycle rate.

This is an emulated CPU comparison, not a physical SD speed prediction.
Only private boot/card images are modified. No benchmark executable is shipped.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT=Path(__file__).resolve().parents[1]
TIMER=r'''#include <dos.h>
#include <stdio.h>
static unsigned long ticks(void) {
  volatile unsigned far *p=(volatile unsigned far *)MK_FP(0x40,0x6c);
  unsigned hi,lo;
  do { hi=p[1]; lo=p[0]; } while (hi!=p[1]);
  return ((unsigned long)hi<<16)|lo;
}
int main(int argc,char **argv) {
  unsigned long now=ticks(),start;
  FILE *f;
  if(argc!=2) return 1;
  if(argv[1][1]=='S') {
    f=fopen("CLOCK.DAT","wb"); if(!f) return 1;
    if(fwrite(&now,sizeof(now),1,f)!=1) return 1;
    return fclose(f)?1:0;
  }
  f=fopen("CLOCK.DAT","rb"); if(!f) return 1;
  if(fread(&start,sizeof(start),1,f)!=1) return 1;
  if(fclose(f)) return 1;
  printf("STARTUP TICKS=%lu\n",now>=start?now-start:now+0x1800b0UL-start);
  return 0;
}
'''


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','current','boot-image','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--dosbox',required=True)
    p.add_argument('--cycles',type=int,default=300000)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    work=Path(tempfile.mkdtemp(prefix='otter-startup-'))
    print('Artifacts: '+str(work),flush=True)
    (work/'TIMER.C').write_bytes(TIMER.replace('\n','\r\n').encode())
    env={k:v for k,v in os.environ.items() if not k.startswith(('OTTER_MODEL_','OTTER_TEST_'))}
    env.update(SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    with (work/'compiler.log').open('wb') as log:
        subprocess.run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',
            '-c',f'mount c "{ROOT.parent / "buildenv"}"','-c',f'mount d "{work}"',
            '-c',r'set PATH=C:\TC','-c','d:','-c','tcc -ms -eTIMER.EXE TIMER.C > BUILD.TXT',
            '-c','exit'],env=env,stdout=log,stderr=log,check=True,timeout=60)
    assert (work/'TIMER.EXE').is_file()
    spec=importlib.util.spec_from_file_location('kit_fixture',ROOT/'rwhardware/build.py')
    builder=importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    rows=[]
    for label,driver in [('baseline',a.baseline),('current',a.current)]:
        card=work/(label+'-card.img'); builder.prepare(card,{})
        before=hashlib.sha256(card.read_bytes()).hexdigest()
        boot=work/(label+'-boot.img'); shutil.copyfile(a.boot_image,boot)
        keep={'IO.SYS','MSDOS.SYS','COMMAND.COM','IBMBIO.COM','IBMDOS.COM','DBLSPACE.BIN','DRVSPACE.BIN'}
        for name in subprocess.check_output(['mdir','-b','-i',str(boot),'::']).decode().splitlines():
            if not name.endswith('/') and Path(name).name.upper() not in keep:
                subprocess.run(['mdel','-i',str(boot),name],check=True)
        (work/'CONFIG.SYS').write_bytes(b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n')
        (work/'AUTOEXEC.BAT').write_bytes(b'@echo off\r\nTIMER /S\r\n'
            b'OTTERWR /DRIVE:S /RW > INSTALL.TXT\r\nTIMER /E > TIME.TXT\r\n'
            b'OTTERWR /STATUS > STATUS.TXT\r\nOTTERWR /UNMOUNT > UNMOUNT.TXT\r\n'
            b'echo BENCH-DONE > DONE.TXT\r\ndir a:\\ > FLUSH.TXT\r\n')
        for source,name in [(driver,'OTTERWR.EXE'),(work/'TIMER.EXE','TIMER.EXE'),
                            (work/'CONFIG.SYS','CONFIG.SYS'),(work/'AUTOEXEC.BAT','AUTOEXEC.BAT')]:
            subprocess.run(['mcopy','-o','-i',str(boot),str(source),'::'+name],check=True)
        conf=work/(label+'.conf'); conf.write_text('[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n'
            f'isa_sd_image={card}\n[cpu]\ncore=normal\ncycles=fixed {a.cycles}\n[midi]\nmpu401=none\n')
        with (work/(label+'-emulator.log')).open('wb') as log:
            proc=subprocess.Popen([a.dosbox,'-conf',str(conf),'-c',f'boot "{boot}"'],
                                  env=dict(env,OTTER_MODEL_WRITE='1'),stdout=log,stderr=log)
            try:
                deadline=time.monotonic()+240
                while time.monotonic()<deadline:
                    if b'BENCH-DONE' in subprocess.run(['mtype','-i',str(boot),'::DONE.TXT'],capture_output=True).stdout: break
                    if proc.poll() is not None: raise RuntimeError('Emulator exited early')
                    time.sleep(.3)
                else: raise RuntimeError('Startup timed out')
            finally:
                proc.terminate()
                try: proc.wait(timeout=5)
                except subprocess.TimeoutExpired: proc.kill(); proc.wait()
        logs={n:subprocess.check_output(['mtype','-i',str(boot),'::'+n]).decode('cp437')
              for n in ('INSTALL.TXT','STATUS.TXT','UNMOUNT.TXT','TIME.TXT')}
        assert 'S: mounted' in logs['STATUS.TXT']
        assert 'offline; card may be removed' in logs['UNMOUNT.TXT']
        assert hashlib.sha256(card.read_bytes()).hexdigest()==before
        count=int(logs['TIME.TXT'].split('=')[1].strip())
        row={'build':label,'driver_sha256':hashlib.sha256(driver.read_bytes()).hexdigest(),
             'ticks':count,'seconds':round(count/18.2065,3),'logs':logs}; rows.append(row)
        print(label+': '+str(count)+' BIOS ticks',flush=True)
    record={'cycles':a.cycles,'scope':'emulated CPU comparison; physical timing remains unqualified',
            'results':rows,'tick_ratio':rows[0]['ticks']/max(1,rows[1]['ticks'])}
    (a.output/'STARTUP.JSON').write_text(json.dumps(record,indent=2)+'\n')


if __name__=='__main__': main()
