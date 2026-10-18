#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve mad5160's legacy model paths in a temporary PCB and export GLB.

Requires KiCad 10 and its standard 3D model libraries. Supports Windows KiCad
from WSL. The checkout and hardware source are never edited.
"""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess

from compact_glb import compact

REVISION = 'bcaec68e9f62e65e4869585f8ae647f260c2ae55'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--models', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--kicad-cli', default='kicad-cli')
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    windows = args.kicad_cli.lower().endswith('.exe') and os.name != 'nt'

    def native(path):
        if windows:
            return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip().replace('\\', '/')
        return str(path)

    def replace(match):
        original = match[1]
        if re.match(r'\$\{KICAD\d+_3DMODEL_DIR\}', original):
            relative = Path(original.split('}/', 1)[1]).with_suffix('.step')
            model = args.models.resolve() / relative
        elif original.startswith('${KIPRJMOD}/'):
            model = source / original.split('}/', 1)[1]
        else:
            raise ValueError(f'Unexpected model path: {original}')
        if not model.is_file():
            raise FileNotFoundError(model)
        return '(model "' + native(model) + '"'

    actual = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
    if actual != REVISION:
        raise ValueError(f'Expected mad5160 revision {REVISION}, found {actual}')
    pcb = output / 'render.kicad_pcb'
    pcb.write_text(re.sub(r'\(model "([^"]+)"', replace,
                         (source / 'Mad5160.kicad_pcb').read_text()))
    subprocess.run([args.kicad_cli, 'pcb', 'export', 'glb', '--force',
                    '--subst-models', '--include-pads', '--include-silkscreen',
                    '--include-soldermask', '-o', native(output / 'populated.glb'),
                    native(pcb)], check=True)
    compact(output / 'populated.glb', output / 'compact.glb')
    (output / 'source.json').write_text(json.dumps({
        'repository': 'https://github.com/madcatse/mad5160',
        'revision': actual,
        'changes': 'Resolve model paths and replace standard VRML references with matching STEP models.'
    }, indent=2) + '\n')


if __name__ == '__main__':
    main()
