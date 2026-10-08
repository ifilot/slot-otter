#!/usr/bin/env python3
"""Build a 500 MiB FAT16 or FAT32 data image around an existing, qualified DOS kit.

No compiler or other program's source tree is needed. The driver/tester
executables remain byte-identical to the supplied kit. mtools independently
installs files; fsck.fat checks the completed volume without repairing it.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests'))
from kit_fixture import prepare
from fat16_fixture import prepare as prepare16
from fixture import BIG, TEXT
from package import sources

PARTITION_SECTORS = 500 * 1024 * 1024 // 512


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            checksum.update(chunk)
    return checksum.hexdigest()


def check(image, files, fat_bits=32):
    """Check actual on-disk geometry, independent file reads and fsck."""
    with image.open('rb') as stream:
        mbr = stream.read(512)
        assert mbr[510:] == b'\x55\xaa' and mbr[450] == (0x0e if fat_bits==16 else 0x0c)
        start, total = struct.unpack_from('<II', mbr, 454)
        assert (start, total) == (2048, PARTITION_SECTORS)
        stream.seek(start * 512)
        boot = stream.read(512)
        assert boot[510:] == b'\x55\xaa'
        assert struct.unpack_from('<H', boot, 11)[0] == 512
        assert boot[13] == (32 if fat_bits==16 else 8) and boot[16] == 2
        reserved = struct.unpack_from('<H', boot, 14)[0]
        fatsz = struct.unpack_from('<H', boot, 22)[0] if fat_bits==16 else struct.unpack_from('<I', boot, 36)[0]
        roots=(struct.unpack_from('<H',boot,17)[0]+15)//16
        assert struct.unpack_from('<II', boot, 28) == (start, total)
        clusters = (total - reserved - 2 * fatsz - roots) // boot[13]
        if fat_bits==16:
            assert 4085<=clusters<=65518 and fatsz*256>=clusters+2
            assert reserved==1 and roots==32 and boot[54:62]==b'FAT16   '
        else:
            assert clusters >= 65525 and fatsz * 128 >= clusters + 2
            assert (start + reserved + 2 * fatsz) % 2048 == 0, 'Data area is not 1 MiB aligned'
            stream.seek((start + 6) * 512)
            assert stream.read(512) == boot, 'Backup BPB differs'
        assert image.stat().st_size == 501 * 1024 * 1024
        with tempfile.TemporaryDirectory(prefix='otter500-fsck-') as directory:
            partition = Path(directory) / 'partition.img'
            stream.seek(start * 512)
            with partition.open('wb') as output:
                remaining = total * 512
                while remaining:
                    chunk = stream.read(min(remaining, 1024 * 1024))
                    assert chunk, 'Truncated partition'
                    output.write(chunk)
                    remaining -= len(chunk)
            result = subprocess.run(['fsck.fat', '-n', str(partition)], capture_output=True)
            assert result.returncode == 0, result.stdout + result.stderr
    expected = {'KIT/' + name: data for name, data in files.items()}
    expected.update({'RW.TAG': b'OTTER RESIDENT WRITE KIT v1\r\n',
                     'WRITE.TAG': b'OTTER WRITE TEST v1\r\n',
                     'README.TXT': TEXT, 'SUBDIR/INNER.TXT': TEXT,
                     'HIDDEN.TXT': TEXT, 'HIGH.TXT': b'HIGH\n', 'BIG.BIN': BIG,
                     'FRAG.BIN': bytes(i % 251 for i in range(1000))})
    for name, data in expected.items():
        actual = subprocess.check_output(['mtype', '-i', str(image) + '@@1048576', '::' + name])
        assert actual == data, 'Image file mismatch: ' + name
    return {'start': start, 'total': total, 'data': start + reserved + 2 * fatsz + roots, 'fat_bits':fat_bits,
            'spc': boot[13], 'fatsz': fatsz, 'clusters': clusters}, result.stdout + result.stderr


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--filesystem',choices=('FAT16','FAT32'),default='FAT32')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--kit', type=Path, required=True, help='Existing qualified KIT directory')
    parser.add_argument('--reuse-image', action='store_true', help='Bundle evidence; preserve the tested image')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    fat_bits=16 if args.filesystem=='FAT16' else 32
    stem='OTTER16' if fat_bits==16 else 'OTTER500'
    image = output / (stem+'.IMG')
    if image.exists() and not args.reuse_image:
        parser.error('Image already exists; choose a fresh output directory or --reuse-image')
    if args.reuse_image and not image.is_file():
        parser.error('--reuse-image requires the previously built image')
    original_hash = digest(image) if args.reuse_image else None
    src = sources()
    manifest = ''.join(f'{digest(path)}  driver/{path.relative_to(ROOT)}\n' for path in src)
    source_id = hashlib.sha256(manifest.encode()).hexdigest()
    kit = output / 'KIT'
    files = {name: (args.kit / name).read_bytes() for name in ('OTTERSD.EXE', 'HWRT.EXE', 'CONFIG.TXT')}
    for name in ('OTTERSD.EXE', 'HWRT.EXE'):
        assert files[name][:2] == b'MZ', 'Invalid supplied executable: ' + name
    overview = (ROOT / ('docs/FAT16_IMAGE.md' if fat_bits==16 else 'docs/LARGE_IMAGE.md')).read_text()
    manual = (ROOT / 'docs/MANUAL.md').read_text()
    # Preserve the complete test instructions, with the alternative image's
    # name/geometry stated consistently in the local DOS manual.
    manual = manual.replace('OTTERSD.IMG', stem+'.IMG').replace('OTTERSD.ZIP', stem+'.ZIP')
    manual = manual.replace('small FAT32 partition', ('500 MiB FAT16 partition with 16 KiB clusters' if fat_bits==16 else '500 MiB FAT32 partition with 4 KiB clusters'))
    manual = manual.replace('The test image uses\n512-byte clusters', 'The original small test image uses\n512-byte clusters')
    files['MANUAL.TXT'] = (overview + '\n\n' + manual).replace('\n', '\r\n').encode('ascii')
    files['SOURCE.SHA'] = (source_id + '  source manifest identifier\r\n').encode('ascii')
    files['FILES.SHA'] = ''.join(f'{hashlib.sha256(data).hexdigest()}  {name}\r\n'
                               for name, data in sorted(files.items())).encode('ascii')
    if args.reuse_image:
        for name, data in files.items():
            assert (kit / name).read_bytes() == data, 'Sources/kit changed since image qualification: ' + name
    else:
        kit.mkdir(exist_ok=True)
        for name, data in files.items():
            (kit / name).write_bytes(data)
        (prepare16 if fat_bits==16 else prepare)(image, files, spc=32 if fat_bits==16 else 8,
            resident=True, total_sectors=PARTITION_SECTORS)
    layout, fsck = check(image, files, fat_bits)
    (output / 'IMAGECHECK.TXT').write_bytes(fsck)
    (output / 'SOURCE.SHA').write_text(manifest)
    (output / 'README.TXT').write_text(overview)
    info = {'layout': layout, 'partition_mib': 500, 'image_bytes': image.stat().st_size,
            'sector_bytes': 512, 'cluster_bytes': 16384 if fat_bits==16 else 4096, 'source_manifest_sha256': source_id,
            'binary_sha256': {name: hashlib.sha256(files[name]).hexdigest()
                              for name in ('OTTERSD.EXE', 'HWRT.EXE')},
            'physical_hardware_qualified': False,
            'binary_provenance': 'Unmodified executables from supplied KIT; no driver rebuild'}
    (output / 'BUILDINFO.JSON').write_text(json.dumps(info, indent=2) + '\n')
    with zipfile.ZipFile(output / (stem+'.ZIP'), 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.write(image, image.name)
        for name in files:
            archive.write(kit / name, 'KIT/' + name)
        for path in src:
            archive.write(path, 'SOURCE/driver/' + str(path.relative_to(ROOT)))
        for name in ('BUILDINFO.JSON', 'SOURCE.SHA', 'IMAGECHECK.TXT', 'README.TXT'):
            archive.write(output / name, name)
        for path in sorted((output / 'EVIDENCE').glob('*')):
            if path.is_file():
                archive.write(path, 'EVIDENCE/' + path.name)
    with zipfile.ZipFile(output / (stem+'.ZIP')) as archive:
        for path in src:
            assert archive.read('SOURCE/driver/' + str(path.relative_to(ROOT))) == path.read_bytes()
        for name, data in files.items():
            assert archive.read('KIT/' + name) == data
    (output / 'SHA256.TXT').write_text(''.join(f'{digest(output / name)}  {name}\n'
        for name in (stem+'.IMG', stem+'.ZIP', 'SOURCE.SHA', 'BUILDINFO.JSON')))
    if original_hash:
        assert digest(image) == original_hash, 'Qualified image changed while bundling evidence'
    print(f'PASS: 500 MiB FAT{fat_bits}, {16 if fat_bits==16 else 4} KiB clusters, exact kit/read fixtures and fsck: {output}', flush=True)


if __name__ == '__main__':
    main()
