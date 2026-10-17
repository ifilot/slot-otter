#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
"""Draft DOS-style driver screenshots using messages from driver/INSTALL.C.

These are illustrations, not emulator captures or hardware evidence. Timing
and resident memory values are illustrative. Run from any directory:
  python3 tools/render_driver_screenshots.py
Requires Pillow and an 8x16 PSF1 VGA font (Debian's console-setup provides the
default); use --font to select another compatible font. No font is bundled.
"""
import argparse
import gzip
import json
from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MEMORY = 43536  # Example allocation; actual size depends on the build.
PROMPT = 'C:\\OTTERSD>'
VERSION = re.search(r'#define OTTER_VERSION_TEXT "([^"]+)"',
                    (ROOT / 'driver/RWSD.H').read_text())[1]
BANNER = f'OTTERSD {VERSION} - Slot-otter FAT16/FAT32 driver'


def examples():
    return [
        ('load', 'Load the driver', [
            PROMPT + 'OTTERSD /DRIVE:S /PORT:330 /RW',
            BANNER,
            'Initializing SD card and checking filesystem; FAT comparison may take time.',
            'Comparing FAT copies: 100%',
            'Mount timing: SD 9, filesystem 36 BIOS ticks (about 18.2 ticks/second).',
            f'OTTERSD: S: verified read/write, port 330, resident {MEMORY} bytes.',
            'Card mounted: FAT16, 16384 bytes per physical cluster.',
            'Run OTTERSD /UNMOUNT before removing it or running OTTERNAV.',
            '', PROMPT,
        ]),
        ('unmount', 'Unmount before removing the card', [
            PROMPT + 'OTTERSD /UNMOUNT',
            BANNER,
            'Unmounting card; checking pending changes. Please wait...',
            'Comparing FAT copies: 100%',
            'OTTERSD drive is offline; card may be removed.',
            '', PROMPT,
        ]),
        ('mount', 'Mount an inserted card', [
            PROMPT + 'OTTERSD /MOUNT',
            BANNER,
            'Mounting card; initializing SD and checking filesystem. Please wait...',
            'Comparing FAT copies: 100%',
            'OTTERSD card mounted in its installed access mode.',
            '', PROMPT,
        ]),
        ('unload', 'Unload and release resident memory', [
            PROMPT + 'OTTERSD /UNLOAD',
            BANNER,
            'Unloading OTTERSD; checking pending changes. Please wait...',
            'Comparing FAT copies: 100%',
            f'OTTERSD unloaded; resident memory released: {MEMORY} bytes. SD drive is no longer available.',
            '', PROMPT,
        ]),
    ]


def screen(lines, font):
    # Full 80x25 text screen, with DOS wrapping at the right edge.
    data = gzip.open(font, 'rb').read() if font.suffix == '.gz' else font.read_bytes()
    if data[:2] != b'\x36\x04' or data[3] != 16:
        raise ValueError('Expected an 8x16 PSF1 font')
    output = Image.new('RGB', (640, 400), 'black')
    pixels = output.load()
    row = 0
    column = 0
    for line in lines:
        for char in line:
            if column == 80:
                column = 0
                row += 1
            if row >= 25:
                raise ValueError('Example exceeds a DOS screen')
            glyph = data[4 + ord(char) * 16:4 + (ord(char) + 1) * 16]
            for y, bits in enumerate(glyph):
                for x in range(8):
                    if bits & (128 >> x):
                        pixels[column * 8 + x, row * 16 + y] = (170, 170, 170)
            column += 1
        row += 1
        column = 0
    # A captured underline cursor at the final command prompt.
    draw = ImageDraw.Draw(output)
    x = len(lines[-1]) * 8
    draw.rectangle((x, (row - 1) * 16 + 14, x + 7, (row - 1) * 16 + 15),
                   fill=(170, 170, 170))
    # Crop empty lower rows for documentation while keeping 80-column layout.
    return output.crop((0, 0, 640, 192))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font', type=Path,
                        default=Path('/usr/share/consolefonts/Lat15-VGA16.psf.gz'))
    parser.add_argument('--output', type=Path, default=ROOT / 'img/driver-drafts')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    overview = Image.new('RGB', (1328, 524), '#e9edf1')
    draw = ImageDraw.Draw(overview)
    heading_font = ImageFont.truetype('DejaVuSans.ttf', 18)
    small_font = ImageFont.truetype('DejaVuSans.ttf', 14)
    draw.text((16, 10), 'OTTERSD user flow — illustrative drafts', font=heading_font, fill='#17212b')
    draw.text((16, 37), 'Exact driver messages; sample timing and memory figures. Not hardware captures.',
              font=small_font, fill='#455363')
    for index, (name, title, lines) in enumerate(examples()):
        image = screen(lines, args.font)
        image.resize((1280, 384), Image.Resampling.NEAREST).save(args.output / f'{name}.png')
        (args.output / f'{name}.txt').write_text('\n'.join(lines) + '\n')
        x = 16 + (index % 2) * 656
        y = 72 + (index // 2) * 224
        draw.text((x, y), title, font=heading_font, fill='#17212b')
        overview.paste(image, (x, y + 26))
    overview.save(args.output / 'overview.png')
    (args.output / 'metadata.json').write_text(json.dumps({
        'kind': 'illustrative drafts, not emulator or hardware captures',
        'message_source': 'driver/INSTALL.C',
        'version': VERSION,
        'progress': 'Final comparison frame; unmount/unload examples have pending changes',
        'scenario': 'Successful FAT16 mount, 16 KiB clusters, S:, port 330h, verified read/write',
        'sample_values': {'resident_bytes': MEMORY, 'sd_ticks': 9, 'filesystem_ticks': 36},
        'text_mode': '80x25 with empty lower rows cropped to 12; 8x16 VGA glyphs; 2x output',
    }, indent=2) + '\n')
    print(args.output / 'overview.png')


if __name__ == '__main__':
    main()
