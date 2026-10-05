"""Exhaustive 16-bit port range checks and DOS-compatible ASCII options."""
import ctypes as C
import pathlib
import tempfile
import unittest
from support import library


class PortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="otter-port-")
        cls.lib = C.CDLL(str(library(pathlib.Path(cls.tmp.name), "port", ["PORT.C"])))
        cls.lib.parse_port.argtypes = [C.c_char_p, C.POINTER(C.c_uint16)]
        cls.lib.option_upper.argtypes = [C.c_void_p]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def valid(self, value, expected):
        output = C.c_uint16(0xaaaa)
        self.assertEqual(self.lib.parse_port(value, C.byref(output)), 1, value)
        self.assertEqual(output.value, expected)

    def test_entire_16_bit_range(self):
        for number in range(65536):
            output = C.c_uint16(0xaaaa)
            valid = number >= 0x100 and number <= 0xfffc and number % 4 == 0
            self.assertEqual(bool(self.lib.parse_port(f"{number:x}".encode(), C.byref(output))), valid, number)
            self.assertEqual(output.value, number if valid else 0xaaaa)

    def test_prefixes_whitespace_case_and_leading_zeros(self):
        for value in [b"330", b"0330", b"0x330", b"0X330", b"+330", b"+0x330",
                      b" \t\r\n\v\f330", b"000000000000000000000330"]:
            self.valid(value, 0x330)
        self.valid(b"fFfC", 0xfffc)

    def test_invalid_input_and_overflow_does_not_change_output(self):
        for value in [b"", b" ", b"+", b"0x", b"+0x", b"330 ", b"3 30", b"0xx330",
                      b"330z", b"\xff330", b"ff", b"ffff", b"10000", b"100000330",
                      b"FFFFFFFF", b"0" * 100 + b"10000", b"-330", b"-0x330",
                      b"-fffffd00", b"-fffffffffffffd00", b"101", b"331", b"fffd"]:
            output = C.c_uint16(0xaaaa)
            self.assertEqual(self.lib.parse_port(value, C.byref(output)), 0, value)
            self.assertEqual(output.value, 0xaaaa)

    def test_ascii_option_uppercase_preserves_other_bytes(self):
        original = bytes(range(1, 256)) + b"\0"
        buffer = C.create_string_buffer(original)
        self.lib.option_upper(buffer)
        self.assertEqual(buffer.raw[:256], bytes(b - 32 if 97 <= b <= 122 else b for b in original))


if __name__ == "__main__":
    unittest.main(verbosity=2)
