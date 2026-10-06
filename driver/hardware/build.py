#!/usr/bin/env python3
"""Build the standalone hardware kit with user-supplied Turbo C/TASM."""
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests'))
from fixture import create, entry, FATSZ, RESERVED, CLUSTERS


def image(path, files):
    layout = create(path)
    start, data = layout['start'], layout['data']
    with path.open('r+b') as f:
        f.seek((start + RESERVED) * 512)
        fat = bytearray(f.read(FATSZ * 512))
        next_cluster = 1000

        def allocate(content):
            nonlocal next_cluster
            count = max(1, (len(content) + 511) // 512)
            first = next_cluster
            for i in range(count):
                cluster = next_cluster
                next_cluster += 1
                assert cluster < 66000
                struct.pack_into('<I', fat, cluster * 4,
                                 cluster + 1 if i + 1 < count else 0x0fffffff)
                f.seek((data + cluster - 2) * 512)
                f.write(content[i*512:(i+1)*512].ljust(512, b'\0'))
            return first

        # Preserve read-test fragmentation but remove aliasing of fixture data.
        inner = allocate(b'Hello from Slot-otter!\r\n')
        hidden = allocate(b'Hello from Slot-otter!\r\n')
        f.seek((data + 1)*512 + 64)
        f.write(entry('INNER.TXT', 0x20, inner, 24))
        f.seek(data*512 + 7*32)
        f.write(entry('HIDDEN.TXT', 2, hidden, 24))
        f.seek(data*512 + 8*32)
        f.write(b'\xe5' + bytes(31))  # No deliberately malformed LFN on hardware.
        tag = b'OTTER HARDWARE KIT\r\n'
        tag_cluster = allocate(tag)
        directory = bytearray(entry('.',16, next_cluster) + entry('..',16,0))
        # Reserve directory clusters before file allocations.
        directory_count = (32*(2 + len(files)) + 511)//512
        kit_cluster = allocate(bytes(directory_count*512))
        for name, content in sorted(files.items()):
            directory += entry(name, 0x20, allocate(content), len(content))
        f.seek((data + kit_cluster - 2)*512)
        f.write(directory.ljust(directory_count*512,b'\0'))
        f.seek((data + 8)*512 + 32)
        f.write(entry('KIT',16,kit_cluster) + entry('KIT.TAG',0x20,tag_cluster,len(tag)) + bytes(32))
        for offset in (start+RESERVED, start+RESERVED+FATSZ):
            f.seek(offset*512); f.write(fat)
        # Valid FSInfo and backup boot sectors, with accurate allocation hints.
        free = sum(struct.unpack_from('<I',fat,c*4)[0] == 0 for c in range(2,CLUSTERS+2))
        info = bytearray(512)
        struct.pack_into('<I',info,0,0x41615252)
        struct.pack_into('<III',info,484,0x61417272,free,next_cluster)
        struct.pack_into('<I',info,508,0xaa550000)
        for offset in (start+1,start+7):
            f.seek(offset*512); f.write(info)
        f.seek(start*512); boot=bytearray(f.read(512))
        struct.pack_into('<HH',boot,24,63,255)
        boot[64]=0x80
        struct.pack_into('<I',boot,67,0x4f545431)
        for offset in (start,start+6):
            f.seek(offset*512); f.write(boot)
        # Saturated CHS fields; LBA fields carry the actual partition geometry.
        f.seek(447); f.write(b'\xfe\xff\xff')
        f.seek(451); f.write(b'\xfe\xff\xff')
    return layout


def main():
    hardware = ROOT / 'hardware'
    dist = hardware / 'dist'
    dist.mkdir(exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix='otter-hardware-build-'))
    toolchain = Path(os.environ.get('TOOLCHAIN_DIR', ROOT.parent/'buildenv')).resolve()
    subprocess.run(['bash',str(ROOT/'build.sh')],check=True)
    for source in [hardware/'HWTEST.C', ROOT/'tests/PROBE.C',
                   *[ROOT/name for name in ('OTTER.H','SD.C','FAT32.C','PORT.C','PORTBODY.H','SDCMDS.ASM')]]:
        work.joinpath(source.name).write_bytes(source.read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n'))
    env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
    commands = [f'mount c "{toolchain}"',f'mount d "{work}"',r'set PATH=C:\TC;C:\TASM','d:',
                'tasm /mx SDCMDS.ASM > ASM.TXT',
                'tcc -ms -M -eHWTEST.EXE HWTEST.C SD.C FAT32.C PORT.C SDCMDS.OBJ > BUILD.TXT','exit']
    with (work/'compiler.log').open('wb') as log:
        subprocess.run([os.environ.get('DOSBOX_BIN','dosbox'),'-noconsole','-exit',
                        *sum((['-c',c] for c in commands),[])],env=env,stdout=log,stderr=log,check=True,timeout=60)
    print((work/'BUILD.TXT').read_text())
    if not (work/'HWTEST.EXE').exists():
        raise RuntimeError(f'Hardware runner compilation failed: {work}')
    files={'OTTERFS.EXE':(ROOT/'OTTERFS.EXE').read_bytes(),
           'HWTEST.EXE':(work/'HWTEST.EXE').read_bytes(),
           'MANUAL.TXT':(hardware/'MANUAL.md').read_text().replace('\n','\r\n').encode('ascii'),
           'CONFIG.TXT':b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n',
           'RUNTEST.BAT':(hardware/'RUNTEST.BAT').read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\r\n')}
    files['FILES.SHA']=''.join(f'{hashlib.sha256(v).hexdigest()}  {n}\r\n' for n,v in sorted(files.items())).encode()
    kit=dist/'KIT'; kit.mkdir(exist_ok=True)
    for name,content in files.items(): (kit/name).write_bytes(content)
    image(dist/'OTTERHW.IMG',files)
    with zipfile.ZipFile(dist/'OTTERHW.ZIP','w',compression=zipfile.ZIP_DEFLATED) as z:
        for name in files: z.write(kit/name,'KIT/'+name)
        z.write(dist/'OTTERHW.IMG','OTTERHW.IMG')
        for source in ROOT.rglob('*'):
            if source.is_file() and source.suffix.upper() in ('.C','.CPP','.H','.ASM','.PY','.SH','.MD','.BAT') and 'dist' not in source.parts:
                z.write(source,'SOURCE/driver/'+str(source.relative_to(ROOT)))
        z.write(ROOT/'MAKEFILE','SOURCE/driver/MAKEFILE')
    (dist/'SHA256.TXT').write_text(''.join(f'{hashlib.sha256((dist/name).read_bytes()).hexdigest()}  {name}\n'
                                        for name in ('OTTERHW.IMG','OTTERHW.ZIP')))
    print(f'Kit built in {dist}; compiler artifacts: {work}')

if __name__=='__main__': main()
