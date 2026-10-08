"""Public packages must not expose developer utilities or fixture contents."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from support import ROOT

sys.path.insert(0, str(ROOT))
import release


class PublicReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='otter-public-test-')
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.driver = self.work / 'OTTERSD.EXE'
        # Packaging copies opaque bytes; actual executable behavior is tested
        # by the native DOS gates, not by a fabricated program here.
        self.payload = b'MZ' + bytes(26) + b'OTTERSD 1.0.0\0package test payload'
        self.driver.write_bytes(self.payload)

    def test_semantic_version_and_tag_agree(self):
        self.assertEqual(release.version(), '1.0.0')
        release.check_tag('v1.0.0')
        for tag in ('v0.15', '1.0.0', 'v1.0', 'v1.0.1'):
            with self.subTest(tag=tag), self.assertRaises(ValueError):
                release.check_tag(tag)

    def test_mismatched_resident_version_is_refused(self):
        (self.work / 'RWSD.H').write_text('#define OTTER_VERSION 0x000f\n#define OTTER_VERSION_TEXT "1.0.0"\n')
        with patch.object(release, 'ROOT', self.work), self.assertRaises(ValueError):
            release.version()

    def test_old_driver_is_refused(self):
        self.driver.write_bytes(b'MZ' + bytes(26) + b'OTTERSD 0.15\0')
        with self.assertRaises(ValueError):
            release.public_files(self.driver)

    def test_all_floppy_sizes_have_only_driver_and_user_files(self):
        files = release.public_files(self.driver)
        self.assertEqual(set(files), {'OTTERSD.EXE', 'README.TXT', 'CONFIG.TXT', 'LICENSE.TXT'})
        release.build_floppies(self.work, files)
        for size in (360, 720, 1440):
            image = self.work / ('floppy_%dk.img' % size)
            self.assertEqual(image.stat().st_size, size * 1024)
            names = subprocess.check_output(['mdir', '-b', '-i', str(image), '::']).decode().splitlines()
            self.assertEqual({Path(n).name for n in names}, set(files))
            self.assertEqual(subprocess.check_output(['mtype', '-i', str(image), '::OTTERSD.EXE']), self.payload)
            with image.open('rb') as stream:
                boot = stream.read(512)
            self.assertEqual(struct.unpack_from('<H', boot, 11)[0], 512)
            self.assertEqual(boot[510:], b'\x55\xaa')

    def test_floppy_payload_rejects_test_utilities(self):
        files = release.public_files(self.driver)
        files['HWRT.EXE'] = self.payload
        with self.assertRaises(ValueError):
            release.build_floppies(self.work, files)
        self.assertFalse(any(self.work.glob('floppy_*.img')))

    def test_empty_fat16_has_500_mib_and_16_kib_clusters(self):
        image = self.work / 'card.img'
        result = release.build_empty_sd(image, 'FAT16')
        self.assertEqual(result['partition_mib'], 500)
        self.assertEqual(result['cluster_bytes'], 16384)
        self.assertEqual(result['clusters'], 31991)
        self.assertEqual(result['image_bytes'], 501 * 1024 * 1024)
        self.assertEqual(subprocess.check_output(['mdir', '-b', '-i', str(image)+'@@1048576', '::']), b'')

    def test_empty_fat32_has_valid_backups_and_4_kib_clusters(self):
        image = self.work / 'card.img'
        result = release.build_empty_sd(image, 'FAT32')
        self.assertEqual(result['partition_mib'], 500)
        self.assertEqual(result['cluster_bytes'], 4096)
        self.assertGreaterEqual(result['clusters'], 65525)
        with image.open('r+b') as stream:
            stream.seek(2055 * 512)
            stream.write(bytes(512))
        with self.assertRaisesRegex(ValueError, 'Backup FSInfo'):
            release.verify_empty_sd(image, 'FAT32')

    def test_geometry_corruption_is_refused(self):
        image = self.work / 'card.img'
        release.build_empty_sd(image, 'FAT16')
        with image.open('r+b') as stream:
            stream.seek(1048576 + 13)
            stream.write(b'\x08')
        with self.assertRaisesRegex(ValueError, 'BPB'):
            release.verify_empty_sd(image, 'FAT16')

    def test_mirror_corruption_is_refused(self):
        image = self.work / 'card.img'
        release.build_empty_sd(image, 'FAT16')
        with image.open('r+b') as stream:
            stream.seek(1048576 + 22)
            fatsz = struct.unpack('<H', stream.read(2))[0]
            stream.seek((2048 + 1 + fatsz) * 512 + 8)
            stream.write(b'\xff')
        with self.assertRaisesRegex(ValueError, 'mirrors'):
            release.verify_empty_sd(image, 'FAT16')

    def test_populated_volume_is_not_accepted_as_empty(self):
        image = self.work / 'card.img'
        release.build_empty_sd(image, 'FAT16')
        subprocess.run(['mcopy', '-i', str(image)+'@@1048576', str(self.driver), '::HWRT.EXE'], check=True)
        with self.assertRaises(ValueError):
            release.verify_empty_sd(image, 'FAT16')

    def test_public_zips_are_driver_only_and_images_empty(self):
        output = self.work / 'public'
        release.build_release(self.driver, output)
        expected = {'OTTERSD.EXE', 'README.TXT', 'RELEASE.JSON', 'SHA256.TXT', 'OTTERSD-DOS.zip',
                    'OTTERSD-FAT16-500MiB.zip', 'OTTERSD-FAT32-500MiB.zip',
                    'floppy_360k.img', 'floppy_720k.img', 'floppy_1440k.img'}
        self.assertEqual({p.name for p in output.iterdir()}, expected)
        with zipfile.ZipFile(output / 'OTTERSD-DOS.zip') as archive:
            self.assertEqual(set(archive.namelist()), {'OTTERSD.EXE', 'README.TXT', 'CONFIG.TXT', 'LICENSE.TXT'})
            self.assertEqual(archive.read('OTTERSD.EXE'), self.payload)
        for fs in ('FAT16', 'FAT32'):
            stem = 'OTTERSD-%s-500MiB' % fs
            with zipfile.ZipFile(output / (stem + '.zip')) as archive:
                self.assertEqual(set(archive.namelist()), {stem+'.img', 'README.TXT', 'SHA256.TXT'})
                image = self.work / (stem + '.img')
                with archive.open(image.name) as source, image.open('wb') as target:
                    import shutil
                    shutil.copyfileobj(source, target)
                release.verify_empty_sd(image, fs)
                self.assertEqual(archive.read('SHA256.TXT').decode().split()[0], release.digest(image))
        self.assertEqual(json.loads((output / 'RELEASE.JSON').read_text())['recommended'], 'OTTERSD-FAT16-500MiB.zip')
        for line in (output / 'SHA256.TXT').read_text().splitlines():
            checksum, name = line.split('  ')
            self.assertEqual(release.digest(output / name), checksum)

    def test_existing_output_is_refused_without_modifying_it(self):
        output = self.work / 'public'
        output.mkdir()
        marker = output / 'HWRT.EXE'
        marker.write_bytes(b'old output')
        with self.assertRaises(FileExistsError):
            release.build_release(self.driver, output)
        self.assertEqual(marker.read_bytes(), b'old output')
        self.assertEqual(list(output.iterdir()), [marker])


if __name__ == '__main__':
    unittest.main()
