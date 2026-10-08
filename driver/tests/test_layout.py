"""Reject linker layouts that would release live code, data or callback stack."""
import contextlib
import io
import pathlib
import tempfile
import unittest
import struct
import importlib.util
from layout import verify

MAP = """
 00000H 00FFFH 01000H _TEXT CODE
 01000H 01FFFH 01000H _DATA DATA
 02000H 02FFFH 01000H _BSS BSS
 03000H 03000H 00000H _BSSEND STACK
 03000H 0307FH 00080H _STACK STACK
 0100:2000 _resident_end
 0100:1800 _resident_stack
"""


class LayoutTests(unittest.TestCase):
    def check_map(self, text, valid=False, binary=None):
        with tempfile.TemporaryDirectory(prefix="otter-layout-") as directory:
            path = pathlib.Path(directory) / "test.map"
            path.write_text(text)
            if binary is not None: path.with_suffix('.EXE').write_bytes(binary)
            with contextlib.redirect_stdout(io.StringIO()):
                if valid:
                    self.assertEqual(verify(path), 0x3000)
                else:
                    with self.assertRaises(RuntimeError):
                        verify(path)

    def test_retains_all_static_segments_and_private_stack(self):
        self.check_map(MAP, valid=True)

    def test_missing_or_misplaced_marker(self):
        self.check_map(MAP.replace("0100:2000 _resident_end", ""))
        self.check_map(MAP.replace("0100:2000 _resident_end", "0100:1FFF _resident_end"))

    def test_library_code_or_data_past_marker(self):
        for kind in ("CODE", "DATA", "BSS"):
            self.check_map(MAP + f" 03080H 030FFH 00080H _LIB {kind}\n")

    def test_stack_straddles_boundary(self):
        self.check_map(MAP.replace("0100:1800 _resident_stack", "0100:1801 _resident_stack"))

    def test_unused_runtime_dependencies_are_rejected(self):
        for name in ("_malloc", "_calloc", "_strtoul", "_printf", "_atexit"):
            self.check_map(MAP + f" 0000:0050 {name}\n")

    def test_missing_or_ambiguous_bss_boundary(self):
        self.check_map(MAP.replace("_BSSEND", "_OTHER"))
        self.check_map(MAP + " 04000H 04000H 00000H _BSSEND STACK\n")

    def test_installer_tail_must_fit_below_startup_stack(self):
        text=MAP+''' 03080H 0317FH 00100H INITTAIL INSTALL
 03180H 0327FH 00100H INITDATA INSTALL
 0308:0000 _installer
 0100:0000 __heaplen
 0100:0002 __stklen
'''
        binary=bytearray(0x4000); binary[:2]=b'MZ'
        struct.pack_into('<H',binary,8,2)
        struct.pack_into('<HH',binary,32+0x1000,8192,2048)
        self.check_map(text,valid=True,binary=binary)
        struct.pack_into('<H',binary,32+0x1000,512)
        self.check_map(text,binary=binary)
        struct.pack_into('<H',binary,32+0x1000,8192)
        self.check_map(text.replace('INITTAIL INSTALL','INITTAIL CODE'),binary=binary)
        self.check_map(text+' 0308:0001 _live_callback\n',binary=binary)
        # A linker marker's own paragraph frame says nothing about DGROUP.
        # Force a huge group offset with the same physical heaplen address.
        struct.pack_into('<H',binary,32+0x1000,60000)
        self.check_map(text.replace('0100:2000 _resident_end',
                                    '0300:0000 _resident_end'),binary=binary)


class InstallerAssemblyTests(unittest.TestCase):
    def test_only_local_far_frames_and_external_far_gates_are_allowed(self):
        path=pathlib.Path(__file__).resolve().parents[1]/'installer_segments.py'
        spec=importlib.util.spec_from_file_location('installer_segments',path)
        module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        asm="""INITTAIL segment byte public 'CODE'
DGROUP group _DATA,_BSS
_DATA segment word public 'DATA'
_DATA ends
local proc far
 ret
local endp
 push cs
 call near ptr local
 call far ptr _i_keep
INITTAIL ends
"""
        with tempfile.TemporaryDirectory() as directory:
            output=pathlib.Path(directory)/'INSTALL.ASM'
            output.write_text(asm); module.transform(output)
            self.assertIn("INITDATA segment word public 'INSTALL'",output.read_text())
            self.assertIn("INITTAIL segment byte public 'INSTALL'",output.read_text())
            for bad in (asm.replace('call near ptr local','call near ptr LUDIV@'),
                        asm.replace(' push cs\n',''),
                        asm+' call near ptr local\n',asm.replace('proc far','proc near'),
                        asm.replace('_i_keep','_printf'),
                        asm.replace("public 'DATA'","public 'BSS'")):
                output.write_text(bad)
                with self.assertRaises(RuntimeError): module.transform(output)


if __name__ == "__main__":
    unittest.main(verbosity=2)
