#!/usr/bin/env python3
"""Build a candidate standalone image/ZIP and verify source/binary/file equality."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile
import build

ROOT=build.ROOT


def sources():
    suffixes={'.c','.cpp','.h','.asm','.sh','.py','.md','.bat'}
    return sorted(p for p in ROOT.rglob('*') if p.is_file() and
                  not any(x in p.parts for x in ('dist','__pycache__','logs')) and
                  (p.suffix.lower() in suffixes or p.name in ('MAKEFILE','MAKERW','.gitignore')))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--expect-driver',type=Path,required=True)
    p.add_argument('--expect-tester',type=Path,required=True)
    a=p.parse_args(); output=a.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    stage=Path(tempfile.mkdtemp(prefix='otter-reswrite-package-'))
    subprocess.run(['bash',str(ROOT/'build-rw.sh'),str(stage)],check=True)
    build.compile_test(stage)
    spec=importlib.util.spec_from_file_location('resident_layout',ROOT/'tests/layout.py')
    maps=importlib.util.module_from_spec(spec); spec.loader.exec_module(maps)
    resident=(maps.verify(stage/'OTTERWR.MAP')+15)//16*16+256
    assert resident<=39888,'Resident footprint increased before publication'
    for actual,expected in [(stage/'OTTERWR.EXE',a.expect_driver),
                            (stage/'HWRT.EXE',a.expect_tester),
                            (stage/'RWCHILD.EXE',a.expect_tester.parent/'RWCHILD.EXE')]:
        assert actual.read_bytes()==expected.read_bytes(),f'Unvalidated binary: {actual}'
    src=sources()
    manifest=''.join(f'{hashlib.sha256(f.read_bytes()).hexdigest()}  driver/{f.relative_to(ROOT)}\n' for f in src)
    source_id=hashlib.sha256(manifest.encode()).hexdigest()
    (output/'SOURCE.SHA').write_text(manifest)
    files={n:(stage/n).read_bytes() for n in ('OTTERWR.EXE','HWRT.EXE','RWCHILD.EXE')}
    files['MANUAL.TXT']=(ROOT/'rwhardware/MANUAL.md').read_text().replace('\n','\r\n').encode('ascii')
    files['CONFIG.TXT']=b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n'
    files['SOURCE.SHA']=(source_id+'  source manifest identifier\r\n').encode()
    files['FILES.SHA']=''.join(f'{hashlib.sha256(v).hexdigest()}  {n}\r\n' for n,v in sorted(files.items())).encode()
    kit=output/'KIT'; kit.mkdir(exist_ok=True)
    for n,data in files.items(): (kit/n).write_bytes(data)
    image=output/'RESWRITE.IMG'; layout=build.prepare(image,files)
    for n,data in files.items():
        copied=subprocess.check_output(['mtype','-i',str(image)+'@@1048576','::KIT/'+n])
        assert copied==data,n
    raw=image.read_bytes(); partition=stage/'partition.img'
    partition.write_bytes(raw[2048*512:(2048+layout['total'])*512])
    fsck=subprocess.run(['fsck.fat','-n',str(partition)],capture_output=True)
    (output/'IMAGECHECK.TXT').write_bytes(fsck.stdout+fsck.stderr)
    assert fsck.returncode==0,fsck.stdout+fsck.stderr
    (output/'BUILDINFO.JSON').write_text(json.dumps({
        'source_manifest_sha256':source_id,'tester_sources_sha256':(stage/'TESTSOURCE.SHA').read_text().strip(),
        'resident_bytes':resident,'read_only_resident_bytes':17632,
        'layout':layout,'image_bytes':len(raw),'compiler_work':str(stage),
        'physical_hardware_qualified':False,'physical_8088_testing':'deferred'},indent=2)+'\n')
    with zipfile.ZipFile(output/'RESWRITE.ZIP','w',zipfile.ZIP_DEFLATED) as z:
        z.write(image,'RESWRITE.IMG')
        for n in files: z.write(kit/n,'KIT/'+n)
        for f in src: z.write(f,'SOURCE/driver/'+str(f.relative_to(ROOT)))
        for n in ('SOURCE.SHA','BUILDINFO.JSON','IMAGECHECK.TXT'): z.write(output/n,n)
        for evidence in sorted((output/'EVIDENCE').glob('*')):
            if evidence.is_file(): z.write(evidence,'EVIDENCE/'+evidence.name)
    with zipfile.ZipFile(output/'RESWRITE.ZIP') as z:
        for f in src: assert z.read('SOURCE/driver/'+str(f.relative_to(ROOT)))==f.read_bytes(),f
        for n,data in files.items(): assert z.read('KIT/'+n)==data,n
    (output/'SHA256.TXT').write_text(''.join(
        f'{hashlib.sha256((output/n).read_bytes()).hexdigest()}  {n}\n' for n in ('RESWRITE.IMG','RESWRITE.ZIP','SOURCE.SHA','BUILDINFO.JSON')))
    print(f'Candidate kit: {output}; build equality, image files/fsck and source ZIP verified',flush=True)


if __name__=='__main__': main()
