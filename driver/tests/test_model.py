"""Validate card protocol, schematic I/O directions, CRC, and write protection."""
import binascii
import ctypes as C
import hashlib
import pathlib
import subprocess
import tempfile
import unittest
from fixture import create
from support import library

ROOT = pathlib.Path(__file__).resolve().parents[1]


class ModelTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="otter-model-tests-")
        cls.work = pathlib.Path(cls.tmp.name)
        so = library(cls.work, "model", ["emulation/slot_model.c"], ["-std=c99"])
        cls.lib = C.CDLL(str(so))
        cls.lib.slot_model_open.argtypes = [C.c_char_p]
        cls.lib.slot_model_open.restype = C.c_void_p
        cls.lib.slot_model_replace.argtypes = [C.c_void_p, C.c_char_p]
        cls.lib.slot_model_replace.restype = C.c_int
        cls.lib.slot_model_close.argtypes = [C.c_void_p]
        cls.lib.slot_model_read.argtypes = [C.c_void_p, C.c_uint]
        cls.lib.slot_model_read.restype = C.c_uint8
        cls.lib.slot_model_write.argtypes = [C.c_void_p, C.c_uint, C.c_uint8]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def setUp(self):
        self.image = self.work / "card.img"
        self.layout = create(self.image)
        self.card = self.lib.slot_model_open(str(self.image).encode())
        self.assertTrue(self.card)

    def tearDown(self):
        self.lib.slot_model_close(self.card)

    def write(self, port, value=255):
        self.lib.slot_model_write(self.card, port, value)

    def read(self, port):
        return self.lib.slot_model_read(self.card, port)

    def command(self, number, arg=0):
        self.write(2)  # OUT base+2 deasserts chip select
        self.write(3)  # OUT base+3 asserts chip select
        for b in bytes([0x40 | number]) + arg.to_bytes(4, "big") + (b"\x87" if number == 8 else b"\x95"):
            self.write(0, b)
        for _ in range(100):
            self.write(1)
            reply = self.read(0)
            if reply != 255:
                return reply
        self.fail("no SD response")

    def receive(self, count):
        self.write(1)
        return bytes(self.read(1) for _ in range(count))

    def initialize(self):
        self.assertEqual(self.command(0), 1)
        self.assertEqual(self.command(8, 0x1AA), 1)
        self.assertEqual(self.receive(4), b"\0\0\x01\xaa")
        self.assertEqual(self.command(55), 1)
        self.assertEqual(self.command(41, 0x40000000), 0)
        self.assertEqual(self.command(58), 0)
        self.assertEqual(self.receive(4), b"\xc0\xff\x80\0")

    def test_initialization_sector_pipeline_and_crc(self):
        self.initialize()
        self.assertEqual(self.command(17, self.layout["data"] + 2), 0)
        packet = self.receive(516)
        self.assertEqual(packet[:2], b"\xff\xfe")
        payload = packet[2:514]
        self.assertTrue(payload.startswith(b"Hello from Slot-otter!\r\n"))
        self.assertEqual(int.from_bytes(packet[514:], "big"), binascii.crc_hqx(payload, 0))

    def test_chip_select_and_read_have_no_unrequested_clocks(self):
        self.write(2)
        for b in b"\x40\0\0\0\0\x95":
            self.write(0, b)
        self.assertEqual(self.read(0), 255)
        self.assertEqual(self.read(0), 255)
        self.assertEqual(self.command(0), 1)
        self.assertEqual(self.read(0), 1)  # same received byte until a pulse

    def test_absent_card_pull_latch(self):
        self.lib.slot_model_close(self.card)
        self.card = self.lib.slot_model_open(b"")
        self.read(2); self.write(1)
        self.assertEqual(self.read(0), 0)
        self.read(3); self.write(1)
        self.assertEqual(self.read(0), 255)

    def cid(self):
        self.assertEqual(self.command(10), 0)
        packet = self.receive(20)
        self.assertEqual(packet[:2], b"\xff\xfe")
        self.assertEqual(int.from_bytes(packet[18:], "big"), binascii.crc_hqx(packet[2:18], 0))
        return packet[2:18]

    def test_identity_and_socket_replacement(self):
        self.initialize()
        original = self.cid()
        self.assertEqual(self.cid(), original)
        self.assertEqual(self.lib.slot_model_replace(self.card, b"/no/such/card"), -1)
        self.assertEqual(self.cid(), original)
        other = self.work / "other.img"
        create(other)
        self.assertEqual(self.lib.slot_model_replace(self.card, str(other).encode()), 0)
        self.assertEqual(self.command(10), 1)  # inserted card starts idle
        self.initialize()
        self.assertNotEqual(self.cid(), original)
        self.assertEqual(self.lib.slot_model_replace(self.card, b""), 0)
        self.read(2); self.write(1)
        self.assertEqual(self.read(0), 0)

    def test_writes_and_out_of_range_reads(self):
        before = hashlib.sha256(self.image.read_bytes()).digest()
        self.initialize()
        self.assertEqual(self.command(24, 0), 4)
        self.assertEqual(self.command(17, 0xFFFFFFFF), 0x20)
        self.assertEqual(hashlib.sha256(self.image.read_bytes()).digest(), before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
