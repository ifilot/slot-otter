#!/usr/bin/env python3
"""Create public DOS packages, driver-only floppies and empty SD images.

This release path never imports a hardware fixture builder. All images are
regular files in a new output directory; physical disks are never opened.
The developer hardware kit continues to use package.py and image.py.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent
SECTOR = 512
START = 2048
SD_FORMATS = (('FAT16', 500, 32), ('FAT32', 500, 8))
FLOPPIES = (360, 720, 1440)


def version():
    header = (ROOT / 'RWSD.H').read_text()
    text = re.search(r'^#define OTTER_VERSION_TEXT "([0-9]+\.[0-9]+\.[0-9]+)"$', header, re.M)
    number = re.search(r'^#define OTTER_VERSION (0x[0-9a-fA-F]+)$', header, re.M)
    if not text or not number:
        raise ValueError('Missing release version in RWSD.H')
    major, minor, patch = map(int, text[1].split('.'))
    if not (0 <= major <= 255 and 0 <= minor <= 15 and 0 <= patch <= 15):
        raise ValueError('Release version exceeds the 16-bit query encoding')
    if int(number[1], 16) != (major << 8 | minor << 4 | patch):
        raise ValueError('Display version and resident query version disagree')
    return text[1]


def check_tag(tag):
    if tag != 'v' + version():
        raise ValueError('Release tag must be v' + version() + ', got ' + tag)


def digest(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def run(*args):
    return subprocess.run(list(map(str, args)), check=True, capture_output=True).stdout


def build_empty_sd(path, filesystem, mib=500, spc=None):
    """Format a fresh, zero-filled MBR image without installing any files."""
    path = Path(path)
    if filesystem not in ('FAT16', 'FAT32'):
        raise ValueError('Only FAT16 and FAT32 images are supported')
    spc = spc if spc is not None else (32 if filesystem == 'FAT16' else 8)
    total = mib * 1024 * 1024 // SECTOR
    with path.open('xb') as stream:
        stream.truncate((START + total) * SECTOR)
        mbr = bytearray(SECTOR)
        # Saturated CHS values; the LBA fields describe the partition.
        mbr[447:450] = mbr[451:454] = b'\xfe\xff\xff'
        mbr[450] = 0x0e if filesystem == 'FAT16' else 0x0c
        struct.pack_into('<II', mbr, 454, START, total)
        mbr[510:] = b'\x55\xaa'
        stream.write(mbr)
    options = ['-T', total, '-h', 255, '-s', 63, '-H', START,
               '-c', spc, '-d', 2, '-N', '0x4f545331', '-v', 'OTTERSD']
    if filesystem == 'FAT32':
        options += ['-F', '-R', 32, '-K', 6]
    else:
        options += ['-r', 32]
    run('mformat', '-i', str(path) + '@@1048576', *options, '::')
    if filesystem == 'FAT32':
        # mtools writes the primary FSInfo but leaves its backup zeroed.
        # Supply the matching standard backup before exposing the image.
        with path.open('r+b') as stream:
            stream.seek((START + 1) * SECTOR)
            info = stream.read(SECTOR)
            stream.seek((START + 7) * SECTOR)
            stream.write(info)
    return verify_empty_sd(path, filesystem, mib, spc)


def verify_empty_sd(path, filesystem, mib=500, spc=None):
    """Independently check geometry, mirrors, root, allocation and fsck."""
    path = Path(path)
    spc = spc if spc is not None else (32 if filesystem == 'FAT16' else 8)
    total = mib * 1024 * 1024 // SECTOR
    if path.stat().st_size != (START + total) * SECTOR:
        raise ValueError('Unexpected SD image size')
    with path.open('rb') as stream:
        mbr = stream.read(SECTOR)
        expected_type = 0x0e if filesystem == 'FAT16' else 0x0c
        if (mbr[510:] != b'\x55\xaa' or mbr[446] != 0 or mbr[450] != expected_type or
                struct.unpack_from('<II', mbr, 454) != (START, total) or any(mbr[462:510])):
            raise ValueError('Invalid single-partition MBR')
        stream.seek(START * SECTOR)
        boot = stream.read(SECTOR)
        sectors = struct.unpack_from('<H', boot, 19)[0] or struct.unpack_from('<I', boot, 32)[0]
        if (boot[510:] != b'\x55\xaa' or struct.unpack_from('<H', boot, 11)[0] != SECTOR or
                boot[13] != spc or boot[16] != 2 or sectors != total or
                struct.unpack_from('<I', boot, 28)[0] != START):
            raise ValueError('Unexpected BPB geometry')
        reserved = struct.unpack_from('<H', boot, 14)[0]
        roots = struct.unpack_from('<H', boot, 17)[0]
        fatsz = struct.unpack_from('<H', boot, 22)[0] or struct.unpack_from('<I', boot, 36)[0]
        root_sectors = (roots * 32 + SECTOR - 1) // SECTOR
        clusters = (total - reserved - 2 * fatsz - root_sectors) // spc
        if filesystem == 'FAT16':
            if not 4085 <= clusters <= 65518 or roots != 512:
                raise ValueError('Not supported FAT16 geometry')
        elif clusters < 65525 or roots:
            raise ValueError('Not FAT32 geometry')
        fat_start = START + reserved
        stream.seek(fat_start * SECTOR)
        fat = stream.read(fatsz * SECTOR)
        if stream.read(fatsz * SECTOR) != fat:
            raise ValueError('FAT mirrors disagree')
        if filesystem == 'FAT16':
            if struct.unpack_from('<HH', fat) != (0xfff8, 0xffff) or any(fat[4:]):
                raise ValueError('FAT16 image has allocated data clusters or bad flags')
            root_start = fat_start + 2 * fatsz
            root_bytes = roots * 32
        else:
            entries = tuple(value & 0x0fffffff for value in struct.unpack_from('<III', fat))
            if entries != (0x0ffffff8, 0x0fffffff, 0x0fffffff) or any(fat[12:]):
                raise ValueError('FAT32 image has allocated file clusters or bad flags')
            if struct.unpack_from('<I', boot, 44)[0] != 2:
                raise ValueError('Unexpected FAT32 root cluster')
            root_start = fat_start + 2 * fatsz
            root_bytes = spc * SECTOR
            info_sector, backup = struct.unpack_from('<HH', boot, 48)
            if info_sector != 1 or backup != 6 or reserved <= backup + info_sector:
                raise ValueError('Unexpected FAT32 FSInfo/backup layout')
            stream.seek((START + backup) * SECTOR)
            if stream.read(SECTOR) != boot:
                raise ValueError('Backup boot sector differs')
            stream.seek((START + info_sector) * SECTOR)
            info = stream.read(SECTOR)
            if (struct.unpack_from('<I', info)[0] != 0x41615252 or
                    struct.unpack_from('<I', info, 484)[0] != 0x61417272 or
                    struct.unpack_from('<I', info, 508)[0] != 0xaa550000 or
                    struct.unpack_from('<I', info, 488)[0] not in (clusters - 1, 0xffffffff)):
                raise ValueError('Invalid empty-volume FSInfo')
            stream.seek((START + backup + info_sector) * SECTOR)
            if stream.read(SECTOR) != info:
                raise ValueError('Backup FSInfo differs')
        stream.seek(root_start * SECTOR)
        root = stream.read(root_bytes)
        # A volume-label entry is metadata. No files, folders or deleted
        # fixture remnants are permitted anywhere in the empty root.
        if root[11] != 8 or root[:11].rstrip() != b'OTTERSD' or any(root[32:]):
            raise ValueError('SD image is not an empty OTTERSD volume')
    listing = run('mdir', '-b', '-i', str(path) + '@@1048576', '::').strip()
    if listing:
        raise ValueError('SD image contains user-visible files: ' + listing.decode())
    with tempfile.TemporaryDirectory(prefix='otter-empty-fsck-') as folder:
        partition = Path(folder) / 'partition.img'
        with path.open('rb') as source, partition.open('wb') as target:
            source.seek(START * SECTOR)
            shutil.copyfileobj(source, target, 1024 * 1024)
        run('fsck.fat', '-n', partition)
    return dict(filesystem=filesystem, partition_mib=mib, sector_bytes=SECTOR,
                cluster_bytes=spc * SECTOR, clusters=clusters,
                partition_start=START, image_bytes=path.stat().st_size)


def public_files(driver):
    data = Path(driver).read_bytes()
    if data[:2] != b'MZ' or ('OTTERSD ' + version()).encode() not in data:
        raise ValueError('Driver is not an OTTERSD ' + version() + ' DOS executable')
    return {'OTTERSD.EXE': data,
            'README.TXT': (ROOT / 'docs/INSTALLATION.md').read_text().replace('\n', '\r\n').encode('ascii'),
            'CONFIG.TXT': b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n',
            'LICENSE.TXT': (ROOT / 'LICENSE').read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n')}


def write_zip(path, files):
    with zipfile.ZipFile(path, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, source in sorted(files.items()):
            if isinstance(source, bytes):
                archive.writestr(name, source)
            else:
                archive.write(source, name)
    with zipfile.ZipFile(path) as archive:
        if set(archive.namelist()) != set(files) or archive.testzip() is not None:
            raise ValueError('ZIP verification failed: ' + str(path))


def build_floppies(output, files):
    """Data/install floppies, not boot disks; only the public file allowlist."""
    if set(files) != {'OTTERSD.EXE', 'README.TXT', 'CONFIG.TXT', 'LICENSE.TXT'}:
        raise ValueError('Unexpected file in public floppy payload')
    with tempfile.TemporaryDirectory(prefix='otter-floppy-files-') as folder:
        for name, data in files.items():
            (Path(folder) / name).write_bytes(data)
        for size in FLOPPIES:
            image = Path(output) / ('floppy_%dk.img' % size)
            if image.exists():
                raise FileExistsError(image)
            run('mformat', '-f', size, '-C', '-v', 'OTTERSD', '-N', '0x4f545331', '-i', image, '::')
            for name in files:
                run('mcopy', '-i', image, Path(folder) / name, '::' + name)
            listing = run('mdir', '-b', '-i', image, '::').decode().splitlines()
            if {Path(name).name for name in listing} != set(files):
                raise ValueError('Unexpected public floppy contents')
            for name, data in files.items():
                if run('mtype', '-i', image, '::' + name) != data:
                    raise ValueError('Floppy file mismatch: ' + name)
            if image.stat().st_size != size * 1024:
                raise ValueError('Floppy geometry mismatch')
            run('fsck.fat', '-n', image)


def build_release(driver, output):
    output = Path(output)
    # Refuse reusing an output tree: old utilities must never be swept into
    # an upload or retained on an image by accident.
    output.mkdir(parents=True, exist_ok=False)
    files = public_files(driver)
    (output / 'OTTERSD.EXE').write_bytes(files['OTTERSD.EXE'])
    (output / 'README.TXT').write_bytes(files['README.TXT'])
    write_zip(output / 'OTTERSD-DOS.zip', files)
    build_floppies(output, files)
    layouts = []
    with tempfile.TemporaryDirectory(prefix='otter-public-sd-') as folder:
        for filesystem, mib, spc in SD_FORMATS:
            stem = 'OTTERSD-%s-%dMiB' % (filesystem, mib)
            image = Path(folder) / (stem + '.img')
            layout = build_empty_sd(image, filesystem, mib, spc)
            layout['image_sha256'] = digest(image)
            layouts.append(layout)
            guide = ('OTTERSD ' + version() + '\r\n\r\n' +
                     ('Recommended image.\r\n' if filesystem == 'FAT16' else 'FAT32 alternative.\r\n') +
                     'Empty %d MiB %s volume; %d KiB clusters; 512-byte sectors.\r\n' % (mib, filesystem, spc // 2) +
                     'Whole-disk image is %d MiB including the 1 MiB partition offset.\r\n' % (mib + 1) +
                     'Writing this image to an entire SD card replaces its partitions and files.\r\n' +
                     'Back up the card and select the correct removable device.\r\n' +
                     'Do not copy the IMG as a file or reformat the partition afterwards.\r\n' +
                     'These are data images, not DOS boot disks. Install OTTERSD separately.\r\n' +
                     'Extra capacity on larger cards is outside the supplied partition.\r\n').encode('ascii')
            write_zip(output / (stem + '.zip'), {image.name: image, 'README.TXT': guide,
                      'SHA256.TXT': (layout['image_sha256'] + '  ' + image.name + '\r\n').encode('ascii')})
    record = {'version': version(), 'recommended': 'OTTERSD-FAT16-500MiB.zip', 'sd_images': layouts}
    (output / 'RELEASE.JSON').write_text(json.dumps(record, indent=2) + '\n')
    checksums = ''.join(digest(path) + '  ' + path.name + '\n'
                        for path in sorted(output.iterdir()) if path.is_file())
    (output / 'SHA256.TXT').write_text(checksums)
    print('PASS: OTTERSD ' + version() + ' public packages; driver-only floppies and empty SD images: ' + str(output))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--driver', type=Path, help='Newly built OTTERSD.EXE')
    parser.add_argument('--output', type=Path, help='New directory for public assets')
    parser.add_argument('--check-tag', help='Require an exact v<version> release tag')
    args = parser.parse_args()
    if args.check_tag:
        check_tag(args.check_tag)
    if args.driver or args.output:
        if not args.driver or not args.output:
            parser.error('--driver and --output must be supplied together')
        build_release(args.driver, args.output)
    elif not args.check_tag:
        parser.error('Supply --driver/--output or --check-tag')


if __name__ == '__main__':
    main()
