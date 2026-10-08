"""Shared FAT32 fixtures for host tests, DOS probes and the one SD test kit.

One-sector and eight-sector clusters preserve the original independent test
patterns. resident=True additionally installs the HWRT authorization marker.
No legacy program builder or released kit is imported.
"""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parent))
from fixture import create, FATSZ, RESERVED, CLUSTERS, entry

def _base_image(path, files):
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


def prepare(path,files=None,spc=1,resident=False,total_sectors=None):
    # The hardware builder fixes aliasing, FSInfo, backup boot and the original fixtures.
    if spc==1:
        if total_sectors is not None:
            raise ValueError('Sized kit images require eight-sector clusters')
        layout=_base_image(path,files or {})
    else:
        # Build the same image geometry with eight sectors/cluster, using mtools
        # only to install test-kit files; original root fixtures remain fragmented.
        from fixture import create
        layout=create(path,spc=spc,total_sectors=total_sectors)
        fatsz=layout['fatsz']
        with path.open('r+b') as f:
            data=layout['data']; start=layout['start']
            f.seek((start+RESERVED)*512); fat=bytearray(f.read(fatsz*512))
            struct.pack_into('<I',fat,5*4,0xfffffff); struct.pack_into('<I',fat,8*4,0)
            f.seek((data+3*spc)*512); f.write(bytes(i%251 for i in range(1000)))
            for c,content in ((1000,b'Hello from Slot-otter!\r\n'),(1001,b'Hello from Slot-otter!\r\n')):
                struct.pack_into('<I',fat,c*4,0xfffffff)
                f.seek((data+(c-2)*spc)*512); f.write(content)
            f.seek((data+spc)*512+64); f.write(entry('INNER.TXT',32,1000,24))
            f.seek(data*512+7*32); f.write(entry('HIDDEN.TXT',2,1001,24))
            f.seek(data*512+8*32); f.write(b'\xe5'+bytes(31))
            for lba in (start+RESERVED,start+RESERVED+fatsz): f.seek(lba*512); f.write(fat)
            f.seek(start*512); boot=bytearray(f.read(512)); struct.pack_into('<HH',boot,24,63,255); boot[64]=128
            for lba in (start,start+6): f.seek(lba*512); f.write(boot)
            f.seek(447); f.write(b'\xfe\xff\xff')
            f.seek(451); f.write(b'\xfe\xff\xff')
    start,data=layout['start'],layout['data']
    fatsz,clusters=layout['fatsz'],layout['clusters']
    marker=b'OTTER WRITE TEST v1\r\n'
    with path.open('r+b') as f:
        f.seek((start+RESERVED)*512); fat=bytearray(f.read(fatsz*512))
        c=1500
        assert struct.unpack_from('<I',fat,c*4)[0]==0
        struct.pack_into('<I',fat,c*4,0xfffffff)
        f.seek((data+(c-2)*spc)*512); f.write(marker)
        f.seek((data+8*spc)*512+(96 if spc==1 else 32)); f.write(entry('WRITE.TAG',32,c,len(marker))+bytes(32))
        for lba in (start+RESERVED,start+RESERVED+fatsz): f.seek(lba*512); f.write(fat)
        for lba in (start,start+6):
            f.seek(lba*512); boot=bytearray(f.read(512)); struct.pack_into('<I',boot,67,0x57545231)
            boot[71:82]=b'OTTERWRITE '; f.seek(lba*512); f.write(boot)
        f.seek(data*512); f.write(entry('OTTERWRITE',8))
        info=bytearray(512); struct.pack_into('<I',info,0,0x41615252)
        free=sum(struct.unpack_from('<I',fat,c*4)[0]==0 for c in range(2,clusters+2))
        struct.pack_into('<III',info,484,0x61417272,free,1501); struct.pack_into('<I',info,508,0xaa550000)
        for lba in (start+1,start+7): f.seek(lba*512); f.write(info)
        # CSD v2 capacity has 1024-sector granularity, including harmless trailing space.
        sectors=(start+layout['total']+1023)//1024*1024; f.truncate(sectors*512)
    if spc!=1 and files is not None:
        # The larger-cluster fixture uses the same read patterns. Install kit
        # files only after both FAT copies and FSInfo are consistent, so mtools
        # provides an independent writer for the shipped executables/manual.
        with tempfile.TemporaryDirectory(prefix='otter-sd-kit-') as directory:
            io=['-i',str(path)+'@@1048576']
            subprocess.run(['mmd',*io,'::KIT'],check=True)
            content=dict(files, **{'KIT.TAG':b'OTTER HARDWARE KIT\r\n'})
            for name,data in sorted(content.items()):
                local=Path(directory)/name; local.write_bytes(data)
                target='::KIT.TAG' if name=='KIT.TAG' else '::KIT/'+name
                subprocess.run(['mcopy','-o',*io,str(local),target],check=True)
    if resident:
        with tempfile.TemporaryDirectory(prefix='otter-sd-tag-') as directory:
            marker=Path(directory)/'RW.TAG'
            marker.write_bytes(b'OTTER RESIDENT WRITE KIT v1\r\n')
            subprocess.run(['mcopy','-o','-i',str(path)+'@@1048576',str(marker),'::RW.TAG'],check=True)
    return layout
