#!/usr/bin/env python3
"""Build standalone WTTEST and a separate, explicitly marked expendable image."""
from pathlib import Path
import hashlib
import importlib.util
import os
import struct
import subprocess
import sys
import tempfile
import zipfile
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
sys.path.insert(0,str(ROOT/'tests'))
from fixture import FATSZ, RESERVED, CLUSTERS, entry
spec=importlib.util.spec_from_file_location('hw_build',ROOT/'hardware/build.py')
hw=importlib.util.module_from_spec(spec); spec.loader.exec_module(hw)


def prepare(path,files=None,spc=1):
    # The hardware builder fixes aliasing, FSInfo, backup boot and the original fixtures.
    if spc==1:
        layout=hw.image(path,files or {})
    else:
        # Build the same image geometry with eight sectors/cluster, using mtools
        # only to install test-kit files; original root fixtures remain fragmented.
        from fixture import create
        layout=create(path,spc=spc)
        with path.open('r+b') as f:
            data=layout['data']; start=layout['start']
            f.seek((start+RESERVED)*512); fat=bytearray(f.read(FATSZ*512))
            struct.pack_into('<I',fat,5*4,0xfffffff); struct.pack_into('<I',fat,8*4,0)
            f.seek((data+3*spc)*512); f.write(bytes(i%251 for i in range(1000)))
            for c,content in ((1000,b'Hello from Slot-otter!\r\n'),(1001,b'Hello from Slot-otter!\r\n')):
                struct.pack_into('<I',fat,c*4,0xfffffff)
                f.seek((data+(c-2)*spc)*512); f.write(content)
            f.seek((data+spc)*512+64); f.write(entry('INNER.TXT',32,1000,24))
            f.seek(data*512+7*32); f.write(entry('HIDDEN.TXT',2,1001,24))
            f.seek(data*512+8*32); f.write(b'\xe5'+bytes(31))
            for lba in (start+RESERVED,start+RESERVED+FATSZ): f.seek(lba*512); f.write(fat)
            f.seek(start*512); boot=bytearray(f.read(512)); struct.pack_into('<HH',boot,24,63,255); boot[64]=128
            for lba in (start,start+6): f.seek(lba*512); f.write(boot)
    start,data=layout['start'],layout['data']
    marker=b'OTTER WRITE TEST v1\r\n'
    with path.open('r+b') as f:
        f.seek((start+RESERVED)*512); fat=bytearray(f.read(FATSZ*512))
        c=1500
        assert struct.unpack_from('<I',fat,c*4)[0]==0
        struct.pack_into('<I',fat,c*4,0xfffffff)
        f.seek((data+(c-2)*spc)*512); f.write(marker)
        f.seek((data+8*spc)*512+(96 if spc==1 else 32)); f.write(entry('WRITE.TAG',32,c,len(marker))+bytes(32))
        for lba in (start+RESERVED,start+RESERVED+FATSZ): f.seek(lba*512); f.write(fat)
        for lba in (start,start+6):
            f.seek(lba*512); boot=bytearray(f.read(512)); struct.pack_into('<I',boot,67,0x57545231)
            boot[71:82]=b'OTTERWRITE '; f.seek(lba*512); f.write(boot)
        f.seek(data*512); f.write(entry('OTTERWRITE',8))
        info=bytearray(512); struct.pack_into('<I',info,0,0x41615252)
        free=sum(struct.unpack_from('<I',fat,c*4)[0]==0 for c in range(2,CLUSTERS+2))
        struct.pack_into('<III',info,484,0x61417272,free,1501); struct.pack_into('<I',info,508,0xaa550000)
        for lba in (start+1,start+7): f.seek(lba*512); f.write(info)
        # CSD v2 capacity has 1024-sector granularity, including harmless trailing space.
        sectors=(start+layout['total']+1023)//1024*1024; f.truncate(sectors*512)
    return layout


def main():
    work=Path(tempfile.mkdtemp(prefix='otter-write-build-')); dist=HERE/'dist'; dist.mkdir(exist_ok=True)
    for source in [HERE/n for n in ('WRITE.H','WTEST.C','WSD.C','WFS.C')]+[ROOT/n for n in ('OTTER.H','FAT32.C','PORT.C')]:
        (work/source.name).write_bytes(source.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    toolchain=Path(os.environ.get('TOOLCHAIN_DIR',ROOT.parent/'buildenv')).resolve()
    commands=[f'mount c "{toolchain}"',f'mount d "{work}"',r'set PATH=C:\TC;C:\TASM','d:',
              'tcc -ms -O -M -eWTTEST.EXE WTEST.C WSD.C WFS.C FAT32.C PORT.C > BUILD.TXT','exit']
    with (work/'compiler.log').open('wb') as log:
        subprocess.run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',*sum((['-c',c] for c in commands),[])],
                       env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=log,stderr=log,check=True,timeout=60)
    print((work/'BUILD.TXT').read_text())
    if not (work/'WTTEST.EXE').exists(): raise RuntimeError(f'Compilation failed: {work}')
    files={'WTTEST.EXE':(work/'WTTEST.EXE').read_bytes(),
           'WMANUAL.TXT':(HERE/'MANUAL.md').read_text().replace('\n','\r\n').encode('ascii')}
    kit=dist/'KIT'; kit.mkdir(exist_ok=True)
    for n,b in files.items(): (kit/n).write_bytes(b)
    prepare(dist/'WRITE.IMG',files)
    with zipfile.ZipFile(dist/'WRITE.ZIP','w',zipfile.ZIP_DEFLATED) as z:
        z.write(dist/'WRITE.IMG','WRITE.IMG')
        for n in files: z.write(kit/n,'KIT/'+n)
        for p in ROOT.rglob('*'):
            if p.is_file() and 'dist' not in p.parts and p.suffix.upper() in ('.C','.CPP','.H','.ASM','.SH','.PY','.MD','.BAT'):
                z.write(p,'SOURCE/driver/'+str(p.relative_to(ROOT)))
        z.write(ROOT/'MAKEFILE','SOURCE/driver/MAKEFILE')
    (dist/'SHA256.TXT').write_text(''.join(f'{hashlib.sha256((dist/n).read_bytes()).hexdigest()}  {n}\n' for n in ('WRITE.IMG','WRITE.ZIP')))
    print(f'Write kit: {dist}; compiler files: {work}')

if __name__=='__main__': main()
