"""Reject linker layouts that would release live code, data or callback stack."""
import contextlib
import io
import pathlib
import tempfile
import unittest
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
    def check_map(self, text, valid=False):
        with tempfile.TemporaryDirectory(prefix="otter-layout-") as directory:
            path = pathlib.Path(directory) / "test.map"
            path.write_text(text)
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


if __name__ == "__main__":
    unittest.main(verbosity=2)
