#!/usr/bin/env python3
"""One entry point for consolidated host, DOS and release qualification.

Supply two genuine DOS boot floppies for --full (DOS 5 and 6.22 recommended).
Only private copies of boot/card images are written. Physical testing follows
rwhardware/MANUAL.md; emulation does not qualify a particular physical card.
"""
import argparse
import hashlib
import json
from pathlib import Path
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
    a=p.parse_args()
    if a.full and (not a.dosbox or len(a.boot_image)<2):
        p.error('--full needs --dosbox and at least two --boot-image values')
    output=(a.output or Path(tempfile.mkdtemp(prefix='otter-qualified-'))).resolve()
    evidence=output/'EVIDENCE'; evidence.mkdir(parents=True,exist_ok=True)
    results=[]

    def run(name,command):
        print('GATE: '+name,flush=True); start=time.monotonic()
        log=evidence/(name+'.log')
        with log.open('wb') as f:
            subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,check=True)
        results.append({'gate':name,'seconds':round(time.monotonic()-start,2),
                        'log':log.name,'sha256':hashlib.sha256(log.read_bytes()).hexdigest()})
        print('PASS: '+name,flush=True)

    py=sys.executable
    run('host',[py,str(ROOT/'tests/run.py'),'--coverage',str(output/'coverage'),'--mutations'])
    run('driver-build',['bash',str(ROOT/'build.sh'),str(output/'build')])
    run('tester-build',[py,str(ROOT/'rwhardware/build.py'),'--output',str(output/'build')])
    driver=output/'build/OTTERWR.EXE'; tester=output/'build/HWRT.EXE'
    package=[py,str(ROOT/'rwhardware/package.py'),'--output',str(output),
             '--expect-driver',str(driver),'--expect-tester',str(tester)]
    if a.full:
        # Qualify legacy DOS API/EXEC and CLI behavior against the CURRENT
        # binary in /RO; no legacy driver is built or substituted here.
        for i,boot in enumerate(a.boot_image):
            native=['--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),'--driver',str(driver)]
            run('dos%d-readonly'%i,[py,str(ROOT/'tests/integration.py'),*native,
                                  '--consolidated','--swap','--max-resident','37000'])
        native=['--dosbox',a.dosbox,'--boot-image',str(a.boot_image[0].resolve()),'--driver',str(driver)]
        for profile in ('normal','strict','slow','corrupt','reject','status','drop','bad-read'):
            run('transport-'+profile,[py,str(ROOT/'tests/rw_integration.py'),*native,
                                      '--profile',profile,'--max-resident','37000'])
        for mode in ('swap','drop','readonly','default-ro','unmarked','no-erase'):
            run('tester-'+mode,[py,str(ROOT/'rwhardware/validate.py'),*native,
                               '--tester',str(tester),'--mode',mode])
    run('package',package)
    if a.full:
        # Exercise the exact distributed image, copying it before each run.
        # The harness also proves its KIT binaries equal the supplied ones.
        for i,boot in enumerate(a.boot_image):
            run('final-image-dos%d'%i,[py,str(ROOT/'rwhardware/validate.py'),
                '--dosbox',a.dosbox,'--boot-image',str(boot.resolve()),
                '--driver',str(driver),'--tester',str(tester),'--image',str(output/'RESWRITE.IMG')])
    record={'full':a.full,'gates':results,
            'boot_image_sha256':[hashlib.sha256(b.read_bytes()).hexdigest() for b in a.boot_image],
            'driver_sha256':hashlib.sha256(driver.read_bytes()).hexdigest(),
            'tester_sha256':hashlib.sha256(tester.read_bytes()).hexdigest(),
            'image_sha256':hashlib.sha256((output/'RESWRITE.IMG').read_bytes()).hexdigest(),
            'physical_hardware_qualified':False}
    (evidence/'QUALIFICATION.JSON').write_text(json.dumps(record,indent=2)+'\n')
    # Rebuild equality and source/image equality again, bundling final evidence.
    run('package-evidence',package+['--reuse-image'])
    assert hashlib.sha256((output/'RESWRITE.IMG').read_bytes()).hexdigest()==record['image_sha256'], 'Evidence bundling changed qualified image'
    print('PASS: consolidated qualification; artifacts '+str(output),flush=True)


if __name__=='__main__': main()
