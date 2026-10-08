"""Independent file/volume checks for the alternative 500 MiB hardware image."""
from pathlib import Path
import sys
import tempfile
import unittest
from support import ROOT
from kit_fixture import prepare

sys.path.insert(0, str(ROOT))
from image import check, PARTITION_SECTORS


class LargeImageTests(unittest.TestCase):
    def test_sized_volume_keeps_test_patterns_and_installs_kit(self):
        with tempfile.TemporaryDirectory(prefix='otter500-test-') as directory:
            card = Path(directory) / 'card.img'
            files = {'TEST.TXT': b'large-cluster kit installation\r\n'}
            prepare(card, files, spc=8, resident=True, total_sectors=PARTITION_SECTORS)
            # mtools reads every original pattern and the supplied kit file;
            # fsck independently detects crosslinks, lost chains and bad hints.
            layout, report = check(card, files)
            self.assertGreaterEqual(layout['clusters'], 65525)
            self.assertIn(b'fsck.fat', report)
            # A falsely labelled, too-large cluster size must not be accepted
            # as our FAT32 release geometry, even with the FAT32 text intact.
            with card.open('r+b') as stream:
                stream.seek(2048 * 512 + 13)
                stream.write(bytes([16]))
            with self.assertRaises(AssertionError):
                check(card, files)

    def test_fat16_500_mib_image_geometry_and_files(self):
        from fat16_fixture import prepare as prepare16
        with tempfile.TemporaryDirectory(prefix='otter16-test-') as directory:
            card=Path(directory)/'card.img'
            files={'TEST.TXT':b'FAT16 kit installation\r\n'}
            prepare16(card,files,resident=True,total_sectors=PARTITION_SECTORS)
            layout,report=check(card,files,16)
            self.assertEqual(layout['spc'],32)
            self.assertEqual(layout['fat_bits'],16)
            self.assertEqual(layout['fatsz'],125)
            self.assertEqual(layout['clusters'],31991)
            self.assertIn(b'fsck.fat',report)

    def test_standard_eight_sector_fixture_also_keeps_supplied_kit(self):
        import subprocess
        with tempfile.TemporaryDirectory(prefix='otter4k-test-') as directory:
            card = Path(directory) / 'card.img'
            data = b'eight-sector kit\r\n'
            prepare(card, {'TEST.TXT': data}, spc=8)
            self.assertEqual(subprocess.check_output([
                'mtype', '-i', str(card) + '@@1048576', '::KIT/TEST.TXT']), data)


if __name__ == '__main__':
    unittest.main()
