# CPLD component models

`MicroSD_Socket.step` is the microSD socket model previously included in the
repository, now attached to J1. Its KiCad model rotation is X=-90, Y=0, Z=0.

`PLCC44_socket_populated.wrl` represents the socket with a CPLD installed.
`R_Array_Convex_4x0612.wrl` represents the 1.6 by 3.2 mm resistor arrays.
These two models are simplified visualizations based on the PCB fabrication
outlines and pad positions, not manufacturer mechanical CAD. Their editable
source is `generate_models.py`; regenerate them with:

```sh
python3 pcb/cpld/components/3d/generate_models.py
```

The generated visualization models use CERN-OHL-S-2.0 and the generator uses
GPL-3.0-or-later, following the repository licensing statement.

To reproduce the upright index image with KiCad 10:

```sh
kicad-cli pcb render --side top --rotate 0,0,0 --quality high \
  --width 1500 --height 1300 --background transparent \
  --output img/slot-otter-cpld-rev1-rendered.png pcb/cpld/cpld.kicad_pcb
```
