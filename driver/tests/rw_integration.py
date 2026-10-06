#!/usr/bin/env python3
"""Boot actual MS-DOS for the writable redirector API development probe.

All card/floppy writes are to newly created private test images. This is a
development integration gate, not physical hardware qualification.
"""
import argparse
import importlib.util
import os
import re
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--boot-image', type=Path, required=True)
    p.add_argument('--dosbox', required=True)
    p.add_argument('--driver', type=Path, required=True)
    p.add_argument('--timeout', type=float, default=180)
    p.add_argument('--profile', choices=('normal', 'strict', 'slow', 'corrupt',
                                        'reject', 'status', 'drop', 'bad-read'), default='normal')
    p.add_argument('--max-resident', type=int, default=40064)
    a = p.parse_args()
    work = Path(tempfile.mkdtemp(prefix='otter-rw-dos-'))
    print(f'Artifacts: {work}', flush=True)
    spec = importlib.util.spec_from_file_location('rwfixture', ROOT/'write/build.py')
    builder = importlib.util.module_from_spec(spec); spec.loader.exec_module(builder)
    image = work/'card.img'; layout = builder.prepare(image)
    before = image.read_bytes()
    source = (ROOT/'tests/RWPROBE.C').read_bytes().replace(b'\r\n', b'\n')
    (work/'RWPROBE.C').write_bytes(source.replace(b'\n', b'\r\n'))
    for name in ('OTTER.H', 'RWSD.H'):
        (work/name).write_bytes((ROOT/name).read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
    env = dict(os.environ, SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy')
    with (work/'compiler.log').open('wb') as log:
        subprocess.run(['dosbox', '-noconsole', '-exit',
                        '-c', f'mount c "{ROOT.parent / "buildenv"}"',
                        '-c', f'mount d "{work}"', '-c', r'set PATH=C:\TC',
                        '-c', 'd:', '-c', 'tcc -ms -eRWPROBE.EXE RWPROBE.C > BUILD.TXT',
                        '-c', 'exit'], env=env, stdout=log, stderr=log,
                       check=True, timeout=60)
    print((work/'BUILD.TXT').read_text(), flush=True)
    assert (work/'RWPROBE.EXE').is_file(), 'DOS probe did not compile'
    boot = work/'boot.img'; shutil.copyfile(a.boot_image, boot)
    keep = {'IO.SYS', 'MSDOS.SYS', 'COMMAND.COM', 'IBMBIO.COM', 'IBMDOS.COM',
            'DRVSPACE.BIN', 'DBLSPACE.BIN'}
    listing = subprocess.check_output(['mdir', '-b', '-i', str(boot), '::']).decode()
    for name in listing.splitlines():
        if not name.endswith('/') and Path(name).name.upper() not in keep:
            subprocess.run(['mdel', '-i', str(boot), name], check=True)
    (work/'CONFIG.SYS').write_bytes(b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n')
    (work/'AUTOEXEC.BAT').write_bytes(
        b'@echo off\r\nOTTERWR /DRIVE:S /RW > INSTALL.TXT\r\n'
        b'OTTERWR /STATUS > STATUS.TXT\r\nRWPROBE > RESULT.TXT\r\n'
        b'if errorlevel 1 goto failed\r\necho 0 > CODE.TXT\r\ngoto finish\r\n'
        b':failed\r\necho 1 > CODE.TXT\r\n:finish\r\n'
        b'echo CMDDEL > S:\\RWTEMP\\CLI.TMP\r\n'
        b'del S:\\RWTEMP\\CLI*.TMP > DEL.TXT\r\n'
        b'OTTERWR /UNMOUNT > UNMOUNT.TXT\r\necho RW-DONE > DONE.TXT\r\n'
        b'dir a:\\ > FLUSH.TXT\r\n')
    for name in ('CONFIG.SYS', 'AUTOEXEC.BAT', 'RWPROBE.EXE'):
        subprocess.run(['mcopy', '-o', '-i', str(boot), str(work/name), '::'+name], check=True)
    subprocess.run(['mcopy', '-o', '-i', str(boot), str(a.driver), '::OTTERWR.EXE'], check=True)
    config = work/'dosbox.conf'
    config.write_text(f'[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\nisa_sd_image={image}\n'
                      '[cpu]\ncore=normal\ncycles=fixed 3000000\n[midi]\nmpu401=none\n')
    for name in list(env):
        if name.startswith(('OTTER_MODEL_', 'OTTER_TEST_')): env.pop(name)
    env['OTTER_MODEL_WRITE'] = '1'
    if a.profile=='strict': env['OTTER_MODEL_STRICT']='1'
    faults = {'slow': ('BUSY', '4096'), 'corrupt': ('CORRUPT', '1'),
              'reject': ('REJECT', '1'), 'status': ('STATUS', '1'),
              'drop': ('DROP', '1'), 'bad-read': ('BAD_READ', '1')}
    if a.profile in faults:
        name, value = faults[a.profile]; env['OTTER_MODEL_'+name]=value
    if a.profile=='reject':
        env['OTTER_MODEL_REJECT_BUSY']='64'; env['OTTER_MODEL_PROBE_FAULT']='7'
    with (work/'emulator.log').open('wb') as log:
        proc = subprocess.Popen([a.dosbox, '-conf', str(config), '-c', f'boot "{boot}"'],
                                env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic()+a.timeout
            while time.monotonic()<deadline:
                marker = subprocess.run(['mtype', '-i', str(boot), '::DONE.TXT'], capture_output=True)
                if b'RW-DONE' in marker.stdout: break
                if proc.poll() is not None: raise RuntimeError('Emulator exited before completion')
                time.sleep(.3)
            else: raise RuntimeError('Booted DOS probe timed out')
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait()
    results = {}
    for name in ('INSTALL.TXT', 'STATUS.TXT', 'RESULT.TXT', 'UNMOUNT.TXT', 'CODE.TXT', 'DEL.TXT'):
        results[name] = subprocess.check_output(['mtype', '-i', str(boot), '::'+name])
        (work/name).write_bytes(results[name]); print(results[name].decode('cp437'), flush=True)
    if a.profile in ('drop', 'bad-read'):
        assert results['CODE.TXT'].strip()==b'1', 'Fault was not reported to DOS application'
        assert b'FAIL:' in results['RESULT.TXT']
        if a.profile=='drop':
            assert b'verified=0 transmissions=1 retries=0' in results['RESULT.TXT']
            assert b'poison=1' in results['RESULT.TXT']
            raw=image.read_bytes()
            first_fat=(2048+32)*512
            assert raw[:first_fat]==before[:first_fat]
            assert raw[first_fat+512:]==before[first_fat+512:]
            dirty=bytearray(before[first_fat:first_fat+512])
            dirty[7]&=0xf7
            assert raw[first_fat:first_fat+512]==dirty, 'Unexpected mutation after removal'
        else:
            assert b'verified=0 transmissions=0 retries=0' in results['RESULT.TXT']
            assert image.read_bytes()==before, 'Pre-mutation read fault changed card contents'
        print(f'PASS: booted DOS {a.profile} fault reported and further mutations stopped')
        return
    assert results['CODE.TXT'].strip()==b'0', 'DOS API probe returned failure'
    assert b'RW PROBE RESULT: 0 failures' in results['RESULT.TXT']
    assert b'FAIL:' not in results['RESULT.TXT']
    assert b'verified read/write' in results['INSTALL.TXT']
    assert b'mounted' in results['STATUS.TXT']
    reported = re.search(rb'resident (\d+) bytes', results['INSTALL.TXT'])
    allocated = re.search(rb'RESIDENT MCB: (\d+) bytes', results['RESULT.TXT'])
    assert reported and allocated and reported[1]==allocated[1], 'Resident MCB differs from linker allocation'
    assert int(allocated[1])<=a.max_resident, 'Writable resident allocation exceeded ceiling'
    (work/'MEMORY.TXT').write_bytes(allocated[0]+b'\n')
    if a.profile in ('corrupt', 'reject', 'status'):
        counters = re.search(rb'TRANSPORT phase=WRITE verified=(\d+) transmissions=(\d+) retries=(\d+)',
                             results['RESULT.TXT'])
        assert counters, 'Missing recovery statistics before memory-pressure remount'
        verified, transmitted, retries = map(int, counters.groups())
        assert transmitted==verified+1 and retries==1, 'Fault did not recover with exactly one bounded sector retry'
    raw = image.read_bytes()
    for lba in (0, 2048, 2054):
        assert raw[lba*512:(lba+1)*512]==before[lba*512:(lba+1)*512]
    part = work/'partition.img'
    part.write_bytes(raw[2048*512:(2048+layout['total'])*512])
    checked = subprocess.run(['fsck.fat', '-n', str(part)], capture_output=True)
    (work/'FSCK.TXT').write_bytes(checked.stdout+checked.stderr)
    print(checked.stdout.decode(), flush=True)
    assert checked.returncode==0, checked.stdout+checked.stderr
    data = subprocess.check_output(['mtype', '-i', str(image)+'@@1048576', '::RWTEMP/DATA.BIN'])
    expected = bytearray(i%251 for i in range(513))+bytearray(387)
    expected[511:513] = b'OV'
    expected.extend(i%251 for i in range(1024))
    assert data==expected, 'Independent DOS-written file comparison failed'
    deleted = subprocess.run(['mtype', '-i', str(image)+'@@1048576',
                              '::RWTEMP/CLI.TMP'], capture_output=True)
    assert deleted.returncode!=0, 'COMMAND.COM DEL left the matching file'
    print('PASS: actual DOS write APIs, segmented buffer, content/fsck, protected boot sectors')


if __name__ == '__main__':
    main()
