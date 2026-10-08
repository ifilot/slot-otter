#!/usr/bin/env python3
"""One entry point for consolidated host, DOS and release qualification.

Supply two genuine DOS boot floppies for --full (DOS 5 and 6.22 recommended).
Only private copies of boot/card images are written. Physical testing follows
docs/MANUAL.md; emulation does not qualify a particular physical card.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time

ROOT=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path)
    p.add_argument('--full',action='store_true')
    p.add_argument('--dosbox',help='ISA SD model emulator; compiler uses DOSBOX_BIN')
    p.add_argument('--boot-image',type=Path,action='append',default=[])
    p.add_argument('--xcopy-expand-media',type=Path,help='Licensed DOS media containing EXPAND.EXE; otherwise discovered among boot images')
    p.add_argument('--jobs',type=int,default=8,help='Concurrent independent native gates and mutation groups (default: 8)')
    a=p.parse_args()
    if a.jobs<1: p.error('--jobs must be positive')
    if a.full and (not a.dosbox or len(a.boot_image)<2):
        p.error('--full needs --dosbox and at least two --boot-image values')
    if a.full and not a.xcopy_expand_media:
        for boot in a.boot_image:
            if subprocess.run(['mdir','-i',str(boot),'::EXPAND.EXE'],capture_output=True).returncode==0:
                a.xcopy_expand_media=boot; break
        if not a.xcopy_expand_media: p.error('--full XCOPY gates require --xcopy-expand-media containing EXPAND.EXE')
    output=(a.output or Path(tempfile.mkdtemp(prefix='otter-qualified-'))).resolve()
    evidence=output/'EVIDENCE'; evidence.mkdir(parents=True,exist_ok=True)
    results=[]

    def run(name,command):
        print('GATE: '+name,flush=True); start=time.monotonic()
        # The bundler snapshots EVIDENCE. Its own live stdout must stay
        # outside that directory so no partially written log enters the ZIP.
        log=(output if name=='package-evidence' else evidence)/(name+'.log')
        with log.open('wb') as f:
            subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
        results.append({'gate':name,'seconds':round(time.monotonic()-start,2),
                        'log':log.name,'sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
        print('PASS: '+name,flush=True)

    # Only native gates are independent. Host/build, package, and evidence
    # publication retain their sequential dependency order.
    pool=ThreadPoolExecutor(max_workers=a.jobs) if a.full and a.jobs>1 else None
    pending=[]

    def queue(name,command):
        if pool: pending.append(pool.submit(run,name,command))
        else: run(name,command)

    def drain():
        for future in pending: future.result()
        pending.clear()

    py=sys.executable
    run('host',[py,str(ROOT/'tests/run.py'),'--coverage',str(output/'coverage'),'--mutations','--jobs',str(a.jobs)])
    run('build',['bash',str(ROOT/'build.sh'),str(output/'build')])
    driver=output/'build/OTTERSD.EXE'; tester=output/'build/HWRT.EXE'
    package=[py,str(ROOT/'package.py'),'--output',str(output),
             '--expect-driver',str(driver),'--expect-tester',str(tester)]
    if a.full:
        # Qualify legacy DOS API/EXEC and CLI behavior against the CURRENT
        # binary in /RO; no legacy driver is built or substituted here.
        for i,boot in enumerate(a.boot_image):
            native=['--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),'--driver',str(driver)]
            queue('fast-native-dos%d'%i,[py,str(ROOT/'tests/fast_native.py'),
                '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),
                *(['--mutations'] if i==0 else [])])
            queue('dos%d-readonly'%i,[py,str(ROOT/'tests/integration.py'),*native,
                                  '--swap','--max-resident','45000'])
        for i,boot in enumerate(a.boot_image):
            for mode in ('readonly','verified','noverify'):
                queue('unload-dos%d-%s'%(i,mode),[py,str(ROOT/'tests/unload.py'),
                    '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),
                    '--driver',str(driver),'--tester',str(tester),'--mode',mode])
        native=['--dosbox',a.dosbox,'--boot-image',str(a.boot_image[0].resolve()),'--driver',str(driver)]
        for profile in ('normal','strict','settle','slow','corrupt','reject','status','drop','bad-read'):
            queue('transport-'+profile,[py,str(ROOT/'tests/rw_integration.py'),*native,
                                      '--profile',profile,'--max-resident','45000'])
        for mode in ('swap','drop','readonly','default-ro','unmarked','no-erase'):
            queue('tester-'+mode,[py,str(ROOT/'tests/hardware.py'),*native,
                               '--tester',str(tester),'--mode',mode])
        queue('tester-noverify',[py,str(ROOT/'tests/hardware.py'),*native,
                              '--tester',str(tester),'--noverify'])
        for i,boot in enumerate(a.boot_image):
            queue('tester-skipfatcheck-dos%d'%i,[py,str(ROOT/'tests/hardware.py'),
                '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),'--driver',str(driver),
                '--tester',str(tester),'--skipfatcheck',*(['--noverify'] if i else [])])
        for i,boot in enumerate(a.boot_image):
            queue('unload-skipfatcheck-dos%d'%i,[py,str(ROOT/'tests/unload.py'),
                '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),'--driver',str(driver),
                '--tester',str(tester),'--skipfatcheck',
                '--mode','noverify' if i else 'verified'])
        for mode in ('init-timeout','init-cid','init-crc'):
            for policy in ('verified','noverify'):
                queue('tester-%s-%s'%(mode,policy),[py,str(ROOT/'tests/hardware.py'),*native,
                    '--tester',str(tester),'--mode',mode,
                    *(['--noverify'] if policy=='noverify' else [])])
        for i,boot in enumerate(a.boot_image):
            for spc in (1,8):
                for mode in ('verified','noverify','readonly'):
                    queue('xcopy-dos%d-spc%d-%s'%(i,spc,mode),[py,str(ROOT/'tests/xcopy.py'),
                        '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),
                        '--expand-media',str(a.xcopy_expand_media.resolve()),'--driver',str(driver),
                        '--spc',str(spc),'--mode',mode])
    drain()
    run('package',package)
    if a.full:
        # Exercise the exact distributed image, copying it before each run.
        # The harness also proves its KIT binaries equal the supplied ones.
        for i,boot in enumerate(a.boot_image):
            for policy in ('writable','readonly'):
                queue('disk-space-dos%d-%s'%(i,policy),[py,str(ROOT/'tests/disk_space.py'),
                    '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),
                    '--kit',str(output/'KIT'),'--image',str(output/'OTTERSD.IMG'),
                    *(['--readonly'] if policy=='readonly' else [])])
            queue('final-image-dos%d'%i,[py,str(ROOT/'tests/hardware.py'),
                '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),
                '--driver',str(driver),'--tester',str(tester),'--image',str(output/'OTTERSD.IMG')])
    drain()
    if pool: pool.shutdown(wait=True)
    record={'full':a.full,'gates':results,
            'boot_image_sha256':[hashlib.sha256(b.read_bytes()).hexdigest() for b in a.boot_image],
            'driver_sha256':hashlib.sha256(driver.read_bytes()).hexdigest(),
            'tester_sha256':hashlib.sha256(tester.read_bytes()).hexdigest(),
            'image_sha256':hashlib.sha256((output/'OTTERSD.IMG').read_bytes()).hexdigest(),
            'source_manifest_sha256':hashlib.sha256((output/'SOURCE.SHA').read_bytes()).hexdigest(),
            'physical_hardware_qualified':False}
    host_log=(evidence/'host.log').read_text()
    counts=re.findall(r'Ran (\d+) tests',host_log)
    assert counts and len(set(counts))==1,'Host suite changed during qualification'
    record['host_tests']=int(counts[0])
    record['behavioral_mutations']=sum(map(int,re.findall(
        r'PASS: (\d+) (?:targeted regressions|critical write regressions|resident transport mutations|resident filesystem mutations|writable redirector mutations|performance mutations)',host_log)))
    if a.full:
        emulator=Path(shutil.which(a.dosbox) or a.dosbox)
        record['emulator_sha256']=hashlib.sha256(emulator.read_bytes()).hexdigest()
        native_log=(evidence/'fast-native-dos0.log').read_text()
        record['native_asm_mutations']=int(re.search(r'; (\d+) assembly mutations detected',native_log)[1])
    (evidence/'QUALIFICATION.JSON').write_text(json.dumps(record,indent=2)+'\n')
    # Rebuild equality and source/image equality again, bundling final evidence.
    run('package-evidence',package+['--reuse-image'])
    assert hashlib.sha256((output/'OTTERSD.IMG').read_bytes()).hexdigest()==record['image_sha256'], 'Evidence bundling changed qualified image'
    print('PASS: consolidated qualification; artifacts '+str(output),flush=True)


if __name__=='__main__': main()
