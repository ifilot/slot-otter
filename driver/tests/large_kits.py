#!/usr/bin/env python3
"""Qualify both 500 MiB formats with exact released binaries under real DOS.

Each gate writes private copies. Builds/images are sequential dependencies;
independent DOS runs may execute concurrently. Evidence is bundled only after
all gates pass. Physical hardware qualification is always a separate step.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True,help='Qualified main output directory')
    p.add_argument('--dosbox',required=True)
    p.add_argument('--boot-image',type=Path,action='append',required=True)
    p.add_argument('--expand-media',type=Path,required=True)
    p.add_argument('--jobs',type=int,default=8)
    a=p.parse_args()
    if len(a.boot_image)<2 or a.jobs<1:p.error('Two DOS boot images and positive --jobs required')
    py=sys.executable;results=[]
    driver=a.output/'KIT/OTTERSD.EXE';tester=a.output/'KIT/HWRT.EXE'
    def digest(path):
        with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
    def run(folder,name,command):
        print('GATE: '+folder.name+'/'+name,flush=True);start=time.monotonic()
        evidence=folder/'EVIDENCE';evidence.mkdir(exist_ok=True)
        log=evidence/(name+'.log')
        with log.open('wb') as stream:subprocess.run(command,stdout=stream,stderr=subprocess.STDOUT,check=True)
        result={'gate':name,'format':folder.name,'seconds':round(time.monotonic()-start,2),
                'log':log.name,'sha256':digest(log)}
        results.append(result);print('PASS: '+folder.name+'/'+name,flush=True)
    formats=[('FAT16','FAT16','OTTER16',32),('FAT32','500M','OTTER500',8)]
    for filesystem,subdir,stem,spc in formats:
        subprocess.run([py,str(ROOT/'image.py'),'--filesystem',filesystem,
            '--output',str(a.output/subdir),'--kit',str(a.output/'KIT')],check=True)
    with ThreadPoolExecutor(max_workers=a.jobs) as pool:
        pending=[]
        for filesystem,subdir,stem,spc in formats:
            folder=a.output/subdir;image=folder/(stem+'.IMG');kit=folder/'KIT'
            for i,boot in enumerate(a.boot_image):
                base=['--dosbox',a.dosbox,'--boot-image',str(boot)]
                pending.append(pool.submit(run,folder,'hardware-dos%d'%i,
                    [py,str(ROOT/'tests/hardware.py'),*base,'--driver',str(driver),
                     '--tester',str(tester),'--image',str(image),'--required-fat',filesystem]))
                pending.append(pool.submit(run,folder,'unload-dos%d'%i,
                    [py,str(ROOT/'tests/unload.py'),*base,'--driver',str(driver),
                     '--tester',str(tester),'--image',str(image),'--mode','verified']))
                for mode in ('verified','noverify','readonly'):
                    pending.append(pool.submit(run,folder,'xcopy-dos%d-%s'%(i,mode),
                        [py,str(ROOT/'tests/xcopy.py'),*base,'--driver',str(driver),
                         '--image',str(image),'--spc',str(spc),'--mode',mode,
                         '--expand-media',str(a.expand_media)]))
                for mode in ('writable','readonly'):
                    pending.append(pool.submit(run,folder,'space-dos%d-%s'%(i,mode),
                        [py,str(ROOT/'tests/disk_space.py'),*base,'--kit',str(kit),
                         '--image',str(image),*(['--readonly'] if mode=='readonly' else [])]))
        for future in pending:future.result()
    for filesystem,subdir,stem,spc in formats:
        folder=a.output/subdir
        record={'filesystem':filesystem,'gates':[r for r in results if r['format']==subdir],
                'image_sha256':digest(folder/(stem+'.IMG')),
                'driver_sha256':digest(driver),'tester_sha256':digest(tester),
                'source_manifest_sha256':digest(folder/'SOURCE.SHA'),
                'boot_image_sha256':[digest(b) for b in a.boot_image],
                'physical_hardware_qualified':False}
        (folder/'EVIDENCE/QUALIFICATION.JSON').write_text(json.dumps(record,indent=2)+'\n')
        subprocess.run([py,str(ROOT/'image.py'),'--filesystem',filesystem,
            '--output',str(folder),'--kit',str(a.output/'KIT'),'--reuse-image'],check=True)
        assert digest(folder/(stem+'.IMG'))==record['image_sha256']
    print('PASS: '+str(len(results))+' exact-image DOS gates across FAT16 and FAT32',flush=True)


if __name__=='__main__':main()
