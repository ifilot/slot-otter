"""S10 — Into the 3.3 V world: regulator, level shifter and the four SPI wires."""
from otter.anim import prog, window
from otter.camera import CamPath, drift
from otter.config import C
from otter.scene import Scene
from .common import sig, lit

CLOCK_VIEW = (118.0, 64.0, 80.0)
SD_VIEW = (162.0, 58.5, 50.0)
# (J1 pad, card pin name, signal, net at J1, colour)
LANES = [('2', 'DAT3', '/CS', 'CS_LLS', C.spi), ('3', 'CMD', 'MOSI', 'DI_LLS', C.data),
         ('5', 'CLK', 'SCK', 'SCK_LLS', C.clock), ('7', 'DAT0', 'MISO', 'D0_LLS', C.spi)]


class SpiWires(Scene):
    name = 's10_spi_wires'
    title = 'Into the 3.3 V world'
    duration = 13.5
    cam = CamPath((0, CLOCK_VIEW), (3.0, SD_VIEW), (13.5, SD_VIEW))
    captions = [
        (0.6, 5.8, 'The SD card runs on 3.3 V, from a regulator; a 74LVC125 drives its pins.'),
        (6.2, 13.0, 'SPI uses four wires: a clock (SCK), data out (MOSI), data in (MISO) and select (/CS).'),
    ]

    def view(self, t):
        return drift(self.cam(t), t, amount=0.002, t1=self.duration)

    def draw(self, f, t):
        f.board(xray=1.0)
        f.spotlight(['U16', 'U21', 'J1', 'R8', 'R9', 'R10', 'R11'], 0.55 * prog(t, 1.5, 3.0))
        lit(f, '+3V3', t, 2.0, None, alpha=0.6, t_dim=6.2)
        a = window(t, 2.6, 13.4, 0.5, 0.3)
        f.outline('U16', C.focus, a * (1 - 0.5 * prog(t, 6.2, 6.8)), label='regulator 5 V → 3.3 V',
                  label_side='left')
        f.outline('U21', C.focus, a, label='74LVC125 buffer', label_side='left')
        f.outline('J1', C.focus, a, pad=0.3, label='microSD socket', label_side='top')
        for i, (pad, pin, signame, net, col) in enumerate(LANES):
            t0 = 6.6 + 0.9 * i
            sig(f, net, ('U21', {'CS_LLS': '8', 'DI_LLS': '3', 'SCK_LLS': '6'}.get(net, '11'))
                if net != 'D0_LLS' else ('J1', '7'), t, t0, None, speed=30, color=col)
            if net == 'D0_LLS':
                sig(f, 'Net-(R8-Pad2)', ('R8', '2'), t, t0 + 0.5, None, speed=30, color=col)
                sig(f, 'MISO', ('U21', '11'), t, t0 + 0.9, None, speed=30, color=col, alpha=0.6)
            la = window(t, t0, 13.4, 0.4, 0.3)
            f.tag(*f.s.pad_xy('J1', pad), f'{signame:<4s} → {pin}' if net != 'D0_LLS' else f'{pin} → {signame}',
                  col, la, dx=-150, dy=0, size=20, mono=True)


SCENE = SpiWires()
