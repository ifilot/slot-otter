#!/usr/bin/env python3
"""Install the public floppy driver and use an empty public SD image in DOS.

Only private image copies are changed. No hardware tester or authorization
marker is used: the first boot writes through ordinary DOS COPY/MD, and a
fresh read-only boot verifies persistence and proves that no writes occurred.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from release import verify_empty_sd, version, digest


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--assets', type=Path, required=True)
    p.add_argument('--filesystem', choices=('FAT16', 'FAT32'), required=True)
    p.add_argument('--boot-image', type=Path, required=True)
    p.add_argument('--dosbox', required=True)
    p.add_argument('--timeout', type=float, default=240)
    a = p.parse_args()
    work = Path(tempfile.mkdtemp(prefix='otter-public-dos-'))
    print('Artifacts: ' + str(work), flush=True)
    stem = 'OTTERSD-%s-500MiB' % a.filesystem
    image = work / (stem + '.img')
    with zipfile.ZipFile(a.assets / (stem + '.zip')) as archive:
        with archive.open(image.name) as source, image.open('wb') as target:
            shutil.copyfileobj(source, target, 1024 * 1024)
    verify_empty_sd(image, a.filesystem)
    driver = subprocess.check_output(['mtype', '-i', str(a.assets / 'floppy_360k.img'), '::OTTERSD.EXE'])
    assert driver == (a.assets / 'OTTERSD.EXE').read_bytes(), 'Public floppy driver differs'
    (work / 'OTTERSD.EXE').write_bytes(driver)
    env = {k: v for k, v in os.environ.items() if not k.startswith(('OTTER_MODEL_', 'OTTER_TEST_'))}
    env.update(SDL_VIDEODRIVER='dummy', SDL_AUDIODRIVER='dummy', OTTER_MODEL_WRITE='1')
    config = work / 'dosbox.conf'
    config.write_text('[sdl]\nfullscreen=false\n[dosbox]\nmemsize=1\n'
                      'isa_sd_image=%s\n[cpu]\ncore=normal\ncycles=fixed 300000\n'
                      '[midi]\nmpu401=none\n' % image)
    keep = {'IO.SYS', 'MSDOS.SYS', 'COMMAND.COM', 'IBMBIO.COM', 'IBMDOS.COM',
            'DRVSPACE.BIN', 'DBLSPACE.BIN'}
    for phase, mode, commands, copied in (
        ('write', '/RW', ['MD S:\\GAMES', 'COPY /B A:\\OTTERSD.EXE S:\\GAMES\\DRIVER.BIN > WRITE.TXT',
                          'COPY /B S:\\GAMES\\DRIVER.BIN A:\\BACK.BIN > READ.TXT'], 'BACK.BIN'),
        ('reboot', '/RO', ['COPY /B S:\\GAMES\\DRIVER.BIN A:\\BACK.BIN > READ.TXT'], 'BACK.BIN')):
        before = digest(image)
        boot = work / (phase + '.img')
        shutil.copyfile(a.boot_image, boot)
        for name in subprocess.check_output(['mdir', '-b', '-i', str(boot), '::']).decode().splitlines():
            if not name.endswith('/') and Path(name).name.upper() not in keep:
                subprocess.run(['mdel', '-i', str(boot), name], check=True)
        (work / 'CONFIG.SYS').write_bytes(b'LASTDRIVE=S\r\nFILES=40\r\nBUFFERS=10\r\n')
        batch = ['@echo off', 'OTTERSD /? > VERSION.TXT', 'OTTERSD /DRIVE:S /PORT:330 ' + mode + ' > INSTALL.TXT',
                 'OTTERSD /STATUS > STATUS.TXT', *commands, 'DIR S:\\GAMES > DIR.TXT',
                 'OTTERSD /UNLOAD > UNLOAD.TXT', 'echo PUBLIC-DONE > DONE.TXT',
                 'dir a:\\ > FLUSH.TXT']
        (work / 'AUTOEXEC.BAT').write_bytes(('\r\n'.join(batch) + '\r\n').encode('ascii'))
        for name in ('CONFIG.SYS', 'AUTOEXEC.BAT', 'OTTERSD.EXE'):
            subprocess.run(['mcopy', '-o', '-i', str(boot), str(work / name), '::' + name], check=True)
        with (work / (phase + '-emulator.log')).open('wb') as log:
            proc = subprocess.Popen([a.dosbox, '-conf', str(config), '-c', 'boot "%s"' % boot],
                                    env=env, stdout=log, stderr=log)
            try:
                deadline = time.monotonic() + a.timeout
                while time.monotonic() < deadline:
                    result = subprocess.run(['mtype', '-i', str(boot), '::DONE.TXT'], capture_output=True)
                    if b'PUBLIC-DONE' in result.stdout:
                        break
                    if proc.poll() is not None:
                        raise RuntimeError('Public-image DOS test exited early')
                    time.sleep(.3)
                else:
                    raise RuntimeError('Public-image DOS test timed out: ' + str(work))
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
        logs = {}
        for name in ('VERSION.TXT', 'INSTALL.TXT', 'STATUS.TXT', 'UNLOAD.TXT', 'DIR.TXT', 'READ.TXT'):
            data = subprocess.check_output(['mtype', '-i', str(boot), '::' + name])
            (work / (phase + '-' + name)).write_bytes(data)
            logs[name] = data
            print(phase + ' ' + name + ':\n' + data.decode('cp437'), flush=True)
        assert ('OTTERSD ' + version()).encode() in logs['VERSION.TXT']
        assert ('Card mounted: ' + a.filesystem).encode() in logs['INSTALL.TXT']
        assert b'S: mounted' in logs['STATUS.TXT']
        assert b'resident memory released' in logs['UNLOAD.TXT']
        assert subprocess.check_output(['mtype', '-i', str(boot), '::' + copied]) == driver
        assert subprocess.check_output(['mtype', '-i', str(image) + '@@1048576', '::GAMES/DRIVER.BIN']) == driver
        if phase == 'reboot':
            assert digest(image) == before, 'Read-only public-image boot wrote the card'
    partition = work / 'partition.img'
    with image.open('rb') as source, partition.open('wb') as target:
        source.seek(1048576)
        shutil.copyfileobj(source, target, 1024 * 1024)
    result = subprocess.run(['fsck.fat', '-n', str(partition)], capture_output=True)
    (work / 'FSCK.TXT').write_bytes(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    print('PASS: public floppy driver, empty ' + a.filesystem + ' mount, DOS writes, unload, fresh-boot read-only persistence/fsck', flush=True)


if __name__ == '__main__':
    main()
