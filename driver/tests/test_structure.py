"""Keep one active product tree and one independent, usable fixture builder."""
import ast
from pathlib import Path
import subprocess
import tempfile
import unittest
from support import ROOT
from kit_fixture import prepare


class ConsolidatedTreeTests(unittest.TestCase):
    def test_legacy_product_folders_and_targets_are_absent(self):
        for name in ('hardware','write','rwhardware','emulation','build-rw.sh',
                     'OTTERFS.EXE','OTTERWR.EXE','tests/legacy-build.sh',
                     'tests/MAINRO.C','tests/MAKERO'):
            self.assertFalse((ROOT/name).exists(),name)
        make=(ROOT/'MAKEFILE').read_text()
        self.assertTrue(make.startswith('OTTERSD.EXE:'))
        self.assertNotIn('OTTERWR.EXE:',make)
        self.assertNotIn('OTTERFS.EXE:',make)

    def test_python_tools_do_not_import_obsolete_program_builders(self):
        obsolete=('rwhardware/','hardware/build.py','write/build.py','write/sensitivity.py')
        for file in ROOT.rglob('*.py'):
            if file.resolve()==Path(__file__).resolve(): continue
            if 'dist' in file.relative_to(ROOT).parts: continue
            for node in ast.walk(ast.parse(file.read_text())):
                if isinstance(node,ast.Constant) and isinstance(node.value,str):
                    self.assertFalse(any(old in node.value for old in obsolete),str(file))

    def test_shared_resident_fixture_contains_kit_and_valid_filesystem(self):
        with tempfile.TemporaryDirectory(prefix='ottersd-fixture-') as folder:
            image=Path(folder)/'card.img'
            layout=prepare(image,{'TEST.TXT':b'one shared builder\r\n'},resident=True)
            for path,expected in [('RW.TAG',b'OTTER RESIDENT WRITE KIT v1\r\n'),
                                  ('KIT/TEST.TXT',b'one shared builder\r\n')]:
                self.assertEqual(subprocess.check_output(['mtype','-i',str(image)+'@@1048576','::'+path]),expected)
            partition=Path(folder)/'partition.img'
            raw=image.read_bytes()
            partition.write_bytes(raw[layout['start']*512:(layout['start']+layout['total'])*512])
            result=subprocess.run(['fsck.fat','-n',str(partition)],capture_output=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__': unittest.main()
