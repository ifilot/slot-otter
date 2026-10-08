"""Build standard FAT16 fixtures, including the 500 MiB / 16 KiB SD kit.

The root has 512 fixed entries. Both FATs, directory entries and fixture chains
are built here; mtools independently installs the kit and authorization files.
"""
from pathlib import Path
import struct
import subprocess
import tempfile
from fixture import entry, BIG, TEXT


def prepare(path, files=None, spc=32, resident=False, total_sectors=None,
            partitioned=True, root_entries=512):
    path=Path(path)
    total=total_sectors if total_sectors is not None else 80*1024*1024//512
    start=2048 if partitioned else 0
    roots=(root_entries+15)//16
    fatsz=1
    while True:
        clusters=(total-1-2*fatsz-roots)//spc
        needed=(clusters+2+255)//256
        if fatsz>=needed:
            break
        fatsz=needed
    if not 4085<=clusters<=65518 or spc not in (1,2,4,8,16,32,64):
        raise ValueError('Geometry does not produce supported FAT16')
    root=start+1+2*fatsz
    data=root+roots
    fat=bytearray(fatsz*512)
    struct.pack_into('<HH',fat,0,0xfff8,0xffff)
    entries=[entry('OTTERWRITE',8)]
    with path.open('wb') as disk:
        disk.truncate(((start+total+1023)//1024)*1024*512)
        def write(lba,content):
            disk.seek(lba*512);disk.write(content)
        if start:
            mbr=bytearray(512)
            mbr[447:450]=mbr[451:454]=b'\xfe\xff\xff'
            mbr[450]=0x0e
            struct.pack_into('<II',mbr,454,start,total)
            mbr[510:]=b'\x55\xaa';write(0,mbr)
        boot=bytearray(512)
        boot[:11]=b'\xeb\x3c\x90OTTERFS '
        struct.pack_into('<HBHBHHBHHH',boot,11,512,spc,1,2,root_entries,
                         total if total<65536 else 0,0xf8,fatsz,63,255)
        struct.pack_into('<II',boot,28,start,total if total>=65536 else 0)
        boot[36]=128;boot[38]=0x29
        struct.pack_into('<I',boot,39,0x57545231)
        boot[43:54]=b'OTTERWRITE ';boot[54:62]=b'FAT16   '
        boot[510:]=b'\x55\xaa';write(start,boot)
        def file(name,content,first,attr=32):
            count=max(1,(len(content)+spc*512-1)//(spc*512))
            for i in range(count):
                c=first+i*2
                struct.pack_into('<H',fat,c*2,c+2 if i+1<count else 0xffff)
                write(data+(c-2)*spc,content[i*spc*512:(i+1)*spc*512])
            return entry(name,attr,first,len(content))
        entries.append(file('README.TXT',TEXT,4))
        struct.pack_into('<H',fat,3*2,0xffff)
        entries.append(entry('SUBDIR',16,3))
        entries.append(file('FRAG.BIN',bytes(i%251 for i in range(1000)),5))
        entries.append(file('BIG.BIN',BIG,100))
        entries.append(file('HIGH.TXT',b'HIGH\n',4000))
        entries.append(file('HIDDEN.TXT',TEXT,1001,2))
        inner=file('INNER.TXT',TEXT,1000)
        write(data+spc,entry('.',16,3)+entry('..',16,0)+inner)
        # The same harmless 8086 executable as the FAT32 fixture.
        hello=b'\xba\x0c\x01\xb4\x09\xcd\x21\xb8\x00\x4c\xcd\x21OTTER EXEC OK\r\n$'
        entries.append(file('HELLO.COM',hello,2000))
        entries.append(file('WRITE.TAG',b'OTTER WRITE TEST v1\r\n',1500))
        write(root,b''.join(entries))
        for lba in (start+1,start+1+fatsz):write(lba,fat)
    content={}
    if files is not None:content.update(files)
    io=['-i',str(path)+('@@1048576' if partitioned else '')]
    with tempfile.TemporaryDirectory(prefix='otter-fat16-kit-') as directory:
        if files is not None:
            subprocess.run(['mmd',*io,'::KIT'],check=True)
            content['KIT.TAG']=b'OTTER HARDWARE KIT\r\n'
        if resident:content['RW.TAG']=b'OTTER RESIDENT WRITE KIT v1\r\n'
        for name,value in sorted(content.items()):
            local=Path(directory)/name;local.write_bytes(value)
            target='::'+name if name in ('KIT.TAG','RW.TAG') else '::KIT/'+name
            subprocess.run(['mcopy','-o',*io,str(local),target],check=True)
    return dict(start=start,total=total,data=data,fatsz=fatsz,clusters=clusters,
                spc=spc,root_lba=root,root_entries=root_entries,fat_bits=16)
