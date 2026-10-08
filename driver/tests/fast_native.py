#!/usr/bin/env python3
"""Boot genuine DOS for native C transport/CRC and 8086 copy/ABI tests and ASM mutations."""
import argparse
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
from kit_fixture import prepare

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dosbox', required=True)
    parser.add_argument('--boot-image', type=Path, required=True)
    parser.add_argument('--mutations', action='store_true')
    args = parser.parse_args()
    work = Path(tempfile.mkdtemp(prefix='otter-fast-native-'))
    print('Artifacts: ' + str(work), flush=True)
    for name in ('OTTER.H', 'RWSD.H', 'SDRW.C', 'tests/FASTTEST.C', 'tests/FASTABI.ASM'):
        content = (ROOT / name).read_bytes().replace(b'\r\n', b'\n').rstrip(b'\x1a')
        (work / Path(name).name).write_bytes(content.replace(b'\n', b'\r\n'))
    asm = (ROOT / 'FASTIO.ASM').read_text()
    variants = {'BASE': asm}
    if args.mutations:
        variants.update(ODDBAD=asm.replace('    adc cx,cx', '    xor cx,cx', 1),
                        DIRBAD=asm.replace('    les di,[bp+4]\n    lds si,[bp+8]',
                                           '    les di,[bp+8]\n    lds si,[bp+4]', 1))
        assert all(text != asm for name, text in variants.items() if name != 'BASE')
    commands = ['tcc -ms -O -c SDRW.C FASTTEST.C > BUILD.TXT',
                'tasm /mx FASTABI.ASM >> BUILD.TXT']
    for name, text in variants.items():
        (work / (name + '.ASM')).write_bytes(text.replace('\n', '\r\n').encode())
        commands += ['tasm /mx ' + name + '.ASM >> BUILD.TXT',
                     'tcc -ms -e' + name + '.EXE FASTTEST.OBJ SDRW.OBJ FASTABI.OBJ ' + name + '.OBJ >> BUILD.TXT']
    toolchain = Path(os.environ.get('TOOLCHAIN_DIR', ROOT.parent / 'buildenv')).resolve()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('OTTER_MODEL_', 'OTTER_TEST_'))}
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    compiler_conf = work / 'compiler.conf'
    compiler_conf.write_text('[cpu]\ncore=normal\ncycles=fixed 100000\n[midi]\nmpu401=none\n')
    # Classic DOSBox executes at most eleven -c options. A batch file keeps
    # the mutation builds and final exit from being silently dropped.
    (work / 'BUILDASM.BAT').write_bytes(('\r\n'.join(commands) + '\r\n').encode())
    with (work / 'compiler.log').open('wb') as log:
        subprocess.run(['dosbox', '-conf', str(compiler_conf), '-noconsole', '-exit', '-c', f'mount c "{toolchain}"',
                        '-c', f'mount d "{work}"', '-c', r'set PATH=C:\TC;C:\TASM', '-c', 'd:',
                        '-c', 'call BUILDASM.BAT', '-c', 'exit'],
                       env=env, stdout=log, stderr=log, timeout=90, check=True)
    build_log = (work / 'BUILD.TXT').read_text()
    print(build_log, flush=True)
    assert not re.search(r'(?m)^(Error [^m]|Error:|Fatal:|Warning [^m]|Warning:)', build_log), build_log
    assert all((work / (name + '.EXE')).is_file() for name in variants), 'Native probes did not build'
    for name in variants:
        boot = work / (name + '-boot.img')
        shutil.copyfile(args.boot_image, boot)
        keep = {'IO.SYS', 'MSDOS.SYS', 'COMMAND.COM', 'IBMBIO.COM', 'IBMDOS.COM', 'DRVSPACE.BIN', 'DBLSPACE.BIN'}
        names = subprocess.check_output(['mdir', '-b', '-i', str(boot), '::']).decode().splitlines()
        for entry in names:
            if not entry.endswith('/') and Path(entry).name.upper() not in keep:
                subprocess.run(['mdel', '-i', str(boot), entry], check=True)
        (work / 'AUTOEXEC.BAT').write_bytes(
            b'@echo off\r\nFASTTEST > RESULT.TXT\r\nif errorlevel 1 goto fail\r\n'
            b'echo 0 > CODE.TXT\r\ngoto done\r\n:fail\r\necho 1 > CODE.TXT\r\n'
            b':done\r\necho FAST-DONE > DONE.TXT\r\ndir a:\\ > FLUSH.TXT\r\n')
        subprocess.run(['mcopy', '-i', str(boot), str(work / 'AUTOEXEC.BAT'), '::AUTOEXEC.BAT'], check=True)
        subprocess.run(['mcopy', '-i', str(boot), str(work / (name + '.EXE')), '::FASTTEST.EXE'], check=True)
        card = work / (name + '-card.img')
        prepare(card)
        before = hashlib.sha256(card.read_bytes()).digest()
        # Avoid DOS 6.22 floppy-boot delays at an excessive cycle budget.
        # This functional CRC/ABI gate is not a hardware timing benchmark.
        conf = work / (name + '.conf')
        conf.write_text(f'[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={card}\n'
                        '[cpu]\ncore=normal\ncycles=fixed 300000\n[midi]\nmpu401=none\n')
        test_env = dict(env, OTTER_MODEL_WRITE='1', OTTER_MODEL_STRICT='1', OTTER_MODEL_SETTLE='3')
        with (work / (name + '-emulator.log')).open('wb') as log:
            proc = subprocess.Popen([args.dosbox, '-conf', str(conf), '-c', f'boot "{boot}"'],
                                    env=test_env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + 120
                while time.monotonic() < deadline:
                    result = subprocess.run(['mtype', '-i', str(boot), '::DONE.TXT'], capture_output=True)
                    if b'FAST-DONE' in result.stdout:
                        break
                    if proc.poll() is not None:
                        raise RuntimeError('Native fast probe exited early')
                    time.sleep(.3)
                else:
                    raise RuntimeError('Native fast probe timed out: ' + name)
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        result = subprocess.check_output(['mtype', '-i', str(boot), '::RESULT.TXT'])
        code = subprocess.check_output(['mtype', '-i', str(boot), '::CODE.TXT']).strip()
        (work / (name + '-RESULT.TXT')).write_bytes(result)
        print(name + ':\n' + result.decode('cp437'), flush=True)
        if name == 'BASE':
            assert code == b'0' and b'FAST RESULT: 0 failures' in result
            assert hashlib.sha256(card.read_bytes()).digest() == before, 'Native raw probe did not restore the image'
        else:
            assert code == b'1' and b'FAIL:' in result, 'Assembly regression was not detected: ' + name
    print('PASS: native C CRC/transport and assembly copy/ABI, strict SD and three-access settling' +
          ('; %d assembly mutations detected' % (len(variants) - 1) if args.mutations else ''), flush=True)


if __name__ == '__main__':
    main()
