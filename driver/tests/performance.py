#!/usr/bin/env python3
"""Count actual SPI commands for identical workloads; host seconds are not DOS timing."""
import argparse
import ctypes as C
import json
import time
from test_rw_fs import ResidentFilesystemTests, File, builder
from test_fs import FileCursor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--label', required=True)
    args = parser.parse_args()
    case = ResidentFilesystemTests()
    case.setUpClass()
    lib = case.lib
    lib.rw_read.argtypes = [C.POINTER(File), C.c_uint32, C.c_void_p,
                           C.c_uint16, C.POINTER(C.c_uint16)]
    lib.fs_read.argtypes = [C.POINTER(FileCursor), C.c_uint32, C.c_void_p,
                           C.c_uint16, C.POINTER(C.c_uint16)]
    commands = (C.c_uint32 * 64).in_dll(lib, 'rw_host_commands')
    rows = []

    def measure(name, action):
        before = list(commands)
        start = time.monotonic()
        action()
        rows.append({'workload': name, 'spc': spc,
                     'commands': {str(i): n - before[i] for i, n in enumerate(commands)
                                  if n != before[i]},
                     'seconds_host': round(time.monotonic() - start, 3)})

    try:
        for spc in (1, 8):
            case.setUp()
            if spc != 1:
                lib.rw_host_close()
                case.layout = builder.prepare(case.image, spc=spc)
                case.assertEqual(lib.rw_host_open(str(case.image).encode(), 3), 0)
                case.assertEqual(lib.sd_init(), 0)
                case.assertEqual(lib.rw_mount(), 0)
            f = case.create_file('PERF.BIN')
            chunk = bytes(i % 251 for i in range(4096))

            def append():
                for unused in range(100):
                    case.assertEqual(lib.rw_refresh(C.byref(f)), 0)
                    case.assertEqual(lib.rw_append(C.byref(f), chunk, len(chunk)), 0)
                    case.assertEqual(lib.rw_metadata(C.byref(f), f.attr | 32, 0, 0), 0)
            measure('append-400-KiB', append)
            original = case.content('PERF.BIN')
            case.assertEqual(original, chunk * 100)
            output, done = C.create_string_buffer(4096), C.c_uint16()

            def read():
                for pos in range(0, len(original), 4096):
                    case.assertEqual(lib.rw_refresh(C.byref(f)), 0)
                    case.assertEqual(lib.rw_read(C.byref(f), pos, output, 4096, C.byref(done)), 0)
                    case.assertEqual(done.value, 4096)
                    case.assertEqual(output.raw, original[pos:pos + 4096])
            measure('read-400-KiB-writable-mount', read)
            cursor = FileCursor(f.first, f.first, 0)
            lib.fs_invalidate()

            def read_cursor():
                for pos in range(0, len(original), 4096):
                    case.assertEqual(lib.fs_read(C.byref(cursor), pos, output, 4096, C.byref(done)), 0)
                    case.assertEqual(done.value, 4096)
                    case.assertEqual(output.raw, original[pos:pos + 4096])
            measure('read-400-KiB-readonly-cursor', read_cursor)

            def overwrite():
                case.assertEqual(lib.rw_overwrite(C.byref(f), len(original) - 4096, b'Z' * 4096, 4096), 0)
            measure('overwrite-last-4-KiB', overwrite)
            case.assertEqual(case.content('PERF.BIN'), original[:-4096] + b'Z' * 4096)
            case.finish()
            case.tearDown()
        print(json.dumps({'label': args.label, 'measurements': rows}, indent=2))
    finally:
        lib.rw_host_close()
        case.tearDownClass()


if __name__ == '__main__':
    main()
