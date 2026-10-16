#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Regenerate CPLD documentation and fabrication files with KiCad 10."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kicad-cli', default='kicad-cli')
    args = parser.parse_args()
    cli = args.kicad_cli
    windows_cli = cli.lower().endswith('.exe') and os.name != 'nt'

    def native(path):
        if isinstance(path, Path):
            if windows_cli:
                return subprocess.check_output(['wslpath', '-w', str(path)], text=True).strip()
            return str(path)
        return path

    def run(*argv):
        subprocess.run([cli, *map(native, argv)], check=True)

    board, schematic = ROOT / 'cpld.kicad_pcb', ROOT / 'cpld.kicad_sch'
    # Stage outputs on the same filesystem; replace published exports only after
    # every export command succeeds. DRC refills and saves source copper zones.
    with tempfile.TemporaryDirectory(prefix='.export-', dir=ROOT) as temporary:
        stage = Path(temporary)
        production, gerbers = stage / 'production', stage / 'GERBERS'
        production.mkdir()
        gerbers.mkdir()
        run('pcb', 'drc', '--refill-zones', '--save-board', '--schematic-parity',
            '--format', 'json', '-o', production / 'drc.json', board)
        run('sch', 'erc', '--format', 'json', '-o', production / 'erc.json', schematic)
        run('sch', 'export', 'netlist', '--format', 'kicadxml',
            '-o', production / 'netlist.xml', schematic)
        run('sch', 'export', 'bom', '--fields',
            'Reference,Footprint,QUANTITY,Value,LCSC Part #,Datasheet',
            '--labels', 'Designator,Footprint,Quantity,Value,LCSC Part #,Datasheet',
            '--group-by', 'Value,Footprint,LCSC Part #,Datasheet', '--exclude-dnp',
            '-o', production / 'bom.csv', schematic)
        run('pcb', 'export', 'pos', '--format', 'csv', '--units', 'mm',
            '--side', 'both', '--exclude-dnp', '-o', production / 'positions.csv', board)
        run('pcb', 'export', 'ipcd356', '-o', production / 'netlist.ipc', board)
        run('sch', 'export', 'pdf', '-o', stage / 'cpld.pdf', schematic)
        svg_dir = stage / 'schematic-svg'
        svg_dir.mkdir()
        run('sch', 'export', 'svg', '-o', svg_dir, schematic)
        svgs = list(svg_dir.glob('*.svg'))
        if len(svgs) != 1:
            raise RuntimeError('Expected one SVG for the single-sheet schematic')
        svg_text = '\n'.join(line.rstrip() for line in svgs[0].read_text().splitlines()) + '\n'
        (stage / 'cpld.svg').write_text(svg_text)
        run('pcb', 'export', 'gerbers', '--layers',
            'F.Cu,B.Cu,F.Paste,B.Paste,F.Silkscreen,B.Silkscreen,F.Mask,B.Mask,Edge.Cuts',
            '--no-protel-ext', '-o', gerbers, board)
        run('pcb', 'export', 'drill', '--excellon-separate-th', '-o', gerbers, board)
        # Keep a compact assembly reference alongside the machine placement CSV.
        with (production / 'positions.csv').open(newline='', encoding='utf-8-sig') as stream:
            positions = list(csv.DictReader(stream))
        with (production / 'designators.csv').open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['Designator', 'Value', 'Footprint'])
            for row in positions:
                writer.writerow([row['Ref'], row['Val'], row['Package']])
        drc = json.loads((production / 'drc.json').read_text())
        erc = json.loads((production / 'erc.json').read_text())
        error_count = sum(x.get('severity') == 'error' for x in drc['violations'])
        parity_errors = sum(x.get('severity') == 'error' for x in drc['schematic_parity'])
        erc_errors = sum(x.get('severity') == 'error' for sheet in erc['sheets']
                         for x in sheet['violations'])
        unconnected = len(drc['unconnected_items'])
        hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in [board, schematic, ROOT / 'logic/slototter.pld']}
        manifest = {
            'hardware': 'Slot-otter CPLD', 'revision': '1.0',
            'kicad_version': subprocess.check_output([cli, 'version'], text=True).strip(),
            'source_sha256': hashes, 'drc_errors': error_count,
            'schematic_parity_errors': parity_errors, 'erc_errors': erc_errors,
            'drc_warnings': sum(x.get('severity') == 'warning' for x in drc['violations']),
            'schematic_parity_warnings': sum(x.get('severity') == 'warning'
                                             for x in drc['schematic_parity']),
            'erc_warnings': sum(x.get('severity') == 'warning' for sheet in erc['sheets']
                                for x in sheet['violations']),
            'unconnected_items': unconnected,
            'manufacturing_ready': error_count == parity_errors == erc_errors == unconnected == 0,
            'oshwa_certified': False,
        }
        (production / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        for directory in [production, gerbers]:
            target = ROOT / directory.name
            target.mkdir(exist_ok=True)
            # Only clear generated file types; leave source documentation intact.
            for existing in target.iterdir():
                if existing.is_file() and existing.suffix.lower() in {
                    '.csv', '.json', '.xml', '.ipc', '.gbr', '.gbrjob', '.drl'}:
                    existing.unlink()
            for output in directory.iterdir():
                shutil.copyfile(output, target / output.name)
        for name in ['cpld.pdf', 'cpld.svg']:
            shutil.copyfile(stage / name, ROOT / name)
        print(json.dumps(manifest, indent=2))
        if not manifest['manufacturing_ready']:
            print('Exports generated for review. Resolve the recorded errors before fabrication.')


if __name__ == '__main__':
    main()
