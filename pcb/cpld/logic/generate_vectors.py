#!/usr/bin/env python3
"""Generate WinCUPL functional vectors from byte-level SPI/ISA expectations."""
from pathlib import Path
import argparse


class Vectors:
    def __init__(self):
        self.inputs = dict(osc=0, nsel=1, nrd=1, nwr=1, a1=0, a0=0, miso=0)
        self.outputs = dict(mosi=0, ncs=1, sck=0, pull_high=0)
        self.data = 'Z' * 8
        self.received = 0
        self.rows = []
        self.transfers = 0
        self.emit()

    def emit(self, **changes):
        self.inputs.update(changes)
        self.rows.append(''.join(str(x) for x in self.inputs.values()) + self.data
                         + ''.join('H' if x else 'L' for x in self.outputs.values()))

    def tick(self, **expected):
        self.emit(osc=0)
        self.outputs.update(expected)
        self.emit(osc=1)
        self.emit(osc=0)

    def idle(self, clocks=4):
        for _ in range(clocks):
            self.tick()

    def address(self, offset, selected=True):
        self.emit(nsel=int(not selected), a1=offset >> 1, a0=offset & 1)

    def write(self, offset, value=0, selected=True):
        self.address(offset, selected)
        self.data = f'{value:08b}'
        self.emit(nwr=0)
        # Hold the strobe: one access must not create repeated requests.
        self.idle(4)
        if selected and offset >= 2:
            self.outputs['ncs'] = int(offset == 2)
        self.emit(nwr=1)
        self.data = 'Z' * 8
        self.emit(nsel=1)

    def read(self, offset, selected=True, hold=4):
        self.address(offset, selected)
        self.data = ''.join('H' if b == '1' else 'L'
                            for b in f'{self.received:08b}') if selected and offset < 2 else 'Z' * 8
        self.emit(nrd=0)
        self.idle(hold)
        self.data = 'Z' * 8
        if selected and offset >= 2:
            self.outputs['pull_high'] = offset & 1
        self.emit(nrd=1)
        self.emit(nsel=1)

    def transfer(self, sent, reply, previous_mosi):
        # End-of-strobe request crosses two synchronizer stages; the third
        # oscillator edge accepts it. No generated-clock model is involved.
        assert self.outputs['mosi'] == previous_mosi
        self.tick()
        self.tick()
        self.tick(mosi=(sent >> 7) & 1)
        for bit in range(7, -1, -1):
            self.emit(miso=(reply >> bit) & 1)
            self.tick(sck=1)
            self.tick(sck=0, mosi=((sent >> (bit - 1)) & 1) if bit else 1)
        self.received = reply
        self.transfers += 1
        self.idle(3)

    def suite(self):
        self.idle()
        # All control ports, with read controls independent of chip select.
        self.write(3)
        self.read(3)
        self.write(2)
        self.read(2)
        self.read(3)
        self.write(3)
        # Unselected accesses must not change controls or launch SPI.
        for offset in range(4):
            self.write(offset, 0xA5, selected=False)
            self.read(offset, selected=False)
        self.idle()
        # Every possible MOSI byte and every possible received byte, with
        # unrelated data in consecutive transactions to expose stale RX/TX.
        for byte in range(256):
            self.write(0, byte)
            self.transfer(byte, byte ^ 0xA5, previous_mosi=int(byte != 0))
            self.read(0)
            self.read(0)  # Repeated base reads have no side effects.
        # A completed U6-style TX shift register is filled with ones.
        self.write(1, 0x00)
        self.transfer(0xFF, 0x96, previous_mosi=1)
        self.read(0)
        # IN base+1 holds the OLD byte for the whole read, then launches.
        self.read(1, hold=30)
        self.transfer(0xFF, 0x69, previous_mosi=1)
        self.read(0)
        self.write(2)
        self.read(2)
        self.read(3)
        self.idle(20)

    def save(self, destination):
        header = '''Name slototter;
PartNo SLOTOTTER-CPLD;
Date 10/16/2026;
Revision 1.0;
Designer Ivo Filot;
Company Slot-otter;
Assembly CPLD;
Location U1;
Device f1504ispplcc44;
ORDER: osc,nsel,nrd,nwr,a1,a0,miso,db7,db6,db5,db4,db3,db2,db1,db0,mosi,ncs,sck,pull_high;
VECTORS:
'''
        destination.write_bytes((header + '\n'.join(self.rows) + '\n').replace('\n', '\r\n').encode('ascii'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?', type=Path,
                        default=Path(__file__).parent / 'build' / 'slototter.si')
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    vectors = Vectors()
    vectors.suite()
    vectors.save(args.output)
    print(f'{len(vectors.rows)} vectors, {vectors.transfers} transfers -> {args.output}')


if __name__ == '__main__':
    main()
