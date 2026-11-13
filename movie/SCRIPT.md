# Slot-otter Classic: "Eight Clocks" (movie script)

A short explainer, in two cuts:

- **Silent cut**: captions only, 5 min 4 s. Output: `build/slot-otter-classic.mp4`.
- **Voice-over cut**: the same pictures with a calm narration, subtitled. Each
  scene's clock slows down where a spoken line needs more room. Output:
  `build/voiceover/slot-otter-classic-voiceover.mp4`.

The camera looks straight down on the Slot-otter Classic card. We follow
**one byte out** (`OUT 330h, 51h`, the first byte of the SD command *read one
block*) from the ISA card edge to the microSD socket, then **one byte back**
(`EBh`, the first byte of a FAT boot sector) to the CPU.

Format: 1920 × 1080, 60 fps. All hardware statements were checked against the
netlist of `pcb/release/isa-sdcard.kicad_pcb` (the `.dsn` file is stale), and
driver statements against `driver/SDRW.C`. Scene `scenes/sNN_*.py` implements
section **SNN**. The **Captions** and **Voice-over** blocks below are generated
from the code with `render.py script`. Do not edit them here: edit
`captions` in the scene file or `scenes/narration.py` instead.

---

## Visual language

| Element | Look |
| --- | --- |
| Background | Near-black blue with a soft vignette; a dark band behind the captions at the bottom. |
| Photo mode | Orthographic Cycles render of `slot-otter-discrete.blend` (the *plate*), registered to KiCad millimetres. |
| X-ray mode | Vector board from the `.kicad_pcb`: outline, real copper (front bright, back dim), pads, chip bodies with part numbers. |
| Draw order | Board, then glowing nets, then chip bodies and part numbers, then spotlight shading, then tags. Glow never covers a part number. |
| Spotlight | Everything outside the subject dims; when the caption moves on, earlier nets step back to 35 %. |
| Signal colours | address amber, data cyan, control and derived pulses rose, real clocks lime (16 MHz, SCK), SPI/SD violet, power soft red. Neutral white marks "look at this chip". |
| Logic levels | A lit net is active (for active-low signals: the wire is low). Bits: `1` filled cell, `0` hollow cell. |
| Tags | One style: dark pill, at least 20 px, inside a 60 px safe margin, never in the caption band. |
| Type | Inter (captions, labels), DejaVu Sans Mono (hex, binary, signal names). |
| Motion | Slow ease-in-out camera moves, zoom interpolated logarithmically, a barely visible drift that is zero at every cut. Scenes hand over on the same camera position (`render.py check`). |

---

## S01 — Title (10 s)

Photo, drifting in from `WIDE` to `FULL`. The board is dimmed to ~25 % while
the title is up: **Slot-otter Classic** / *How a byte reaches an SD card: 14
logic chips, eight clocks at a time.* The board brightens at 5.6 s.

<!-- captions:s01_title -->
**Captions** (10 s silent cut)
- 6.0–9.9 — *An 8-bit ISA card that turns an SD card into an ordinary DOS drive.*

**Voice-over** (scene time → spoken)
- 1.6 — "Slot-otter Classic."
- 6.0 — "An eight-bit I-S-A card that turns an S-D card into an ordinary DOS drive."
<!-- /captions -->

## S02 — The x-ray (12 s)

The photo cross-fades into the x-ray (0.2–2.8 s). Seven functional blocks
outline themselves in neutral white, each with a label pill: card edge,
address match, register decode, data gate, clock burst, shift registers,
3.3 V side.

<!-- captions:s02_xray -->
**Captions** (12 s silent cut)
- 3.2–9.8 — *No microcontroller, no firmware: fourteen 74-series chips, an oscillator and a regulator.*

**Voice-over** (scene time → spoken)
- 3.2 — "There is no microcontroller, and no firmware. Just fourteen seventy-four series logic chips, an oscillator, and a regulator."
<!-- /captions -->

## S03 — The card edge (26 s)

The camera moves to the gold fingers (centre (117, 108.7), w 88), which sit
above the caption band. A CPU card shows `MOV DX,330h / MOV AL,51h / OUT DX,AL`.
Brackets label **A0 … A9**, **AEN** and **D0 … D7**. Seen from the component
side, bit 0 is on the *left*; a read-out panel gives the usual MSB-first
spelling (`11 0011 0000 = 330h`, `0101 0001 = 51h`). Bit tokens appear on
the fingers, the address at 6 s and the data at 10 s. From 13.8 s, ghosts of the rear
(B) fingers sit exactly over their positions: /IOW lit rose (= 0), /IOR
dashed (= 1). Then active-low is defined, and AEN = 0 is shown.

<!-- captions:s03_edge -->
**Captions** (26 s silent cut)
- 1.0–5.6 — *The CPU executes one instruction: write the byte 51h to I/O port 330h.*
- 6.0–9.8 — *For a moment the bus carries an address and a byte…*
- 10.0–13.6 — *51h is not random: it starts the SD command "read one block".*
- 13.8–17.6 — *…and a "write" strobe, /IOW, on the back of the card.*
- 17.8–21.6 — *A slash means "active low": /IOW acts when its wire is at 0 V.*
- 21.8–25.6 — *AEN low means the CPU, not DMA, is driving the bus.*

**Voice-over** (scene time → spoken)
- 1.0 — "Let us follow one instruction. The CPU writes the byte fifty-one hex to I/O port three-thirty hex."
- 6.0 — "For a moment, the bus carries an address, and a byte."
- 10.0 — "Fifty-one hex is not a random choice. It is the first byte of the S-D command: read one block."
- 13.8 — "And on the back of the card, a write strobe: I-O-W."
- 17.8 — "The slash means active low. I-O-W does its job when its wire is at zero volts."
- 21.8 — "A-E-N is low too. That means the CPU, not D-M-A, is driving the bus."
<!-- /captions -->

## S04 — Is this for me? 74HCT688 (22 s)

Address lines A9..A2 travel along their real copper to U8; the lines at logic 0
are dim. SW1 is redrawn as slide switches above the tracks, with a legend
strip (`200 100 80 40 20 10 8 4` / `A9 … A2`) and ON/OFF. Comparator panel:
P = address, Q = switches, column-by-column check marks, then
*all equal and AEN = 0 → /PORTSEL = 0*, and /PORTSEL spreads to U2 and U9.
From 13.8 to 17.6 s, under the heading *What if: OUT 300h*, the board dims and
two columns fail. Finally: four ports, 330h–333h.

<!-- captions:s04_comparator -->
**Captions** (22 s silent cut)
- 0.8–5.2 — *Address lines A9 to A2 run to a 74HCT688, an 8-bit equality comparator.*
- 5.5–10.5 — *The DIP switch sets the card's address: ON means 1.*
- 10.8–13.6 — *All bits match and AEN is low: /PORTSEL goes low.*
- 13.8–17.6 — *Any other address leaves /PORTSEL high, and the card ignores it.*
- 17.8–21.6 — *A1 and A0 aren't compared: the card owns four ports, 330h to 333h.*

**Voice-over** (scene time → spoken)
- 0.8 — "Address lines A-nine down to A-two run to a seventy-four H-C-T six eighty-eight: an eight-bit equality comparator."
- 5.5 — "The DIP switch holds the card's address. A switch that is on, means a one."
- 10.8 — "All bits match, and A-E-N is low. So port-select goes low."
- 13.8 — "Any other address leaves port-select high, and the card simply ignores it."
- 17.8 — "A-one and A-zero are not compared. So the card owns four ports: three-thirty to three-thirty-three hex."
<!-- /captions -->

## S05 — Which register? '32 + '139 (24 s)

/PORTSEL and /IOW meet at U2 (OR gates; with active-low inputs this works as
an AND). The write half of U3 is enabled; A1 = A0 = 0 selects 2Y0 =
**/SER_WR**. A register map builds row by row:

| Port | IN (read, /IOR) | OUT (write, /IOW) |
| --- | --- | --- |
| 330h | read received byte | load byte + 8 clocks |
| 331h | read byte + 8 clocks | 8 clocks (sends FFh) |
| 332h | release /CS | (MISO pull, unused) |
| 333h | assert /CS | (MISO pull, unused) |

The "330h / OUT" cell glows; later "333h / IN" glows as U5 (the /CS latch) is
highlighted. The MISO-pull latch (U5 A/B, R1) has no effect on Classic, because
U21 drives MISO push-pull. That is why the table marks it as unused and the
captions do not mention it.

<!-- captions:s05_registers -->
**Captions** (24 s silent cut)
- 1.0–6.4 — *Both signals are active low, so an OR gate means "this card AND write".*
- 7.0–12.6 — *A1 and A0 select one of four actions. Reads and writes each have their own decoder.*
- 13.0–16.6 — *OUT 330h: load a byte and send it.*
- 17.0–23.4 — *A NAND latch remembers whether the SD card is selected.*

**Voice-over** (scene time → spoken)
- 1.0 — "Both signals are active low. So here, an OR gate really means: this card, and write."
- 7.0 — "A-one and A-zero then select one of four actions. Reads and writes each have their own decoder."
- 13.0 — "Writing to three-thirty means: load a byte, and send it."
- 17.0 — "And a small NAND latch remembers whether the S-D card is selected."
<!-- /captions -->

## S06 — Flashback: selecting the card (9 s)

Same view, picture slightly darker, with an **EARLIER · IN AL, 333h** pill.
/IOR and A1 = A0 = 1 reach U3; 1Y3 (/SDCS_RESET) flips the U5 latch; /CS
goes low and stays low. An LED inset shows D1 (/CS) lighting up. OTTERSD's
`initialize()` reads 333h once, so on Classic /CS stays asserted. (Forge swaps
the roles of IN and OUT at 332h/333h; the driver works on both.)

<!-- captions:s06_select -->
**Captions** (9 s silent cut)
- 0.4–4.2 — *Earlier, the driver selected the card by reading port 333h.*
- 4.4–8.6 — *The read is just a trigger: the latch now holds /CS low.*

**Voice-over** (scene time → spoken)
- 0.4 — "Earlier, the driver selected the card by reading port three-thirty-three."
- 4.4 — "The read is only a trigger. The latch now holds chip-select low."
<!-- /captions -->

## S07 — Through the gate, into the '165 (24 s)

The camera moves from the logic column to the bus area. U9 (74HCT245): /OE =
/PORTSEL, DIR = /SER_RD = 1, with an arrow labelled *A → B: bus → card*. The
bits of 51h travel DB → U9 → D bus; U7 is tagged *595 outputs off*. Panel:
the byte card 51h splits into eight tokens that drop into the '165 cells H..A
while /SER_WR (SH/LD = 0) is low. Then bit 7 is shown on MOSI, and SER is tied to
5 V.

<!-- captions:s07_load -->
**Captions** (24 s silent cut)
- 1.0–7.4 — *A 74HCT245 gates the bus into the card; DIR sets the direction.*
- 9.0–13.0 — *While /IOW is low, the 165 copies all eight bits at once.*
- 13.4–17.4 — *Bit 7 is already on MOSI, waiting for the first clock.*
- 17.8–23.4 — *Its serial input is tied to 5 V: once the byte is out, MOSI rests high.*

**Voice-over** (scene time → spoken)
- 1.0 — "Back to our byte. A seventy-four H-C-T two forty-five opens the gate to the inside of the card. Its direction depends on whether the CPU reads or writes."
- 9.0 — "While I-O-W is low, the one-sixty-five shift register copies all eight bits at once."
- 13.4 — "Bit seven is already waiting on the Mosi line, for the first clock."
- 17.8 — "Its serial input is tied to five volts. So once the byte has gone, Mosi rests high."
<!-- /captions -->

## S08 — Wait for the CPU to let go (20 s)

U13 (two D flip-flops, both clocked at 16 MHz). Timing panel: 16 MHz, the /IOW
strobe, the strobe as seen by flip-flop 2, and the pulse. The pulse rises the
moment the CPU releases the strobe and lasts one to two ticks (62.5–125 ns).
The wide view then follows the pulse (all in rose): U11 gate D → U2 gate C
(OR) → U12 (NOT) → U11 gate A (AND /PULSE) → **/CLKSTART** at U1.

<!-- captions:s08_edge_detect -->
**Captions** (20 s silent cut)
- 0.8–5.8 — *Clocking must wait until the CPU releases /IOW. Only then is the byte final.*
- 6.0–12.4 — *Two flip-flops follow the strobe one to two ticks late. "Released" AND "not yet seen" gives a short pulse.*
- 12.8–19.2 — *The pulse starts at the release, lasts about 100 ns, and becomes /CLKSTART.*

**Voice-over** (scene time → spoken)
- 0.8 — "The clock must wait until the CPU releases I-O-W. Only then is the byte final."
- 6.0 — "Two flip-flops follow the strobe, one or two clock ticks late. Released, and not yet seen, gives a short pulse."
- 12.8 — "The pulse starts the moment the strobe is released, and lasts about a hundred nanoseconds. It becomes clock-start."
<!-- /captions -->

## S09 — Exactly eight clocks (26 s)

/CLKSTART sets the U1 NAND latch; /MR goes high (rose). The 74HC163 counts
16 MHz ticks at two per second: lamps Q3..Q0, a decimal count, and a timing
panel with Q0 = SCK and TC. At **15 the counter holds for 1.5 s** with the TC lamp lit
while CLKSTOP → U1C → /CLKSTOP → latch reset lights up on the board; the next
tick clears the counter to 0. Tally: 8 rising edges, *16 ticks × 62.5 ns = 1 µs
per byte*. U1D makes /CLK: the '165 shifts and the '595 latches on falling SCK.

<!-- captions:s09_counter -->
**Captions** (26 s silent cut)
- 0.6–4.0 — */CLKSTART sets a latch, which releases a 4-bit counter.*
- 4.2–11.4 — *The counter's lowest bit flips on every 16 MHz tick: an 8 MHz clock, called SCK.*
- 11.6–15.6 — *At 15, "terminal count" resets the latch; the counter clears and stops.*
- 16.0–20.0 — *Eight clock pulses, then silence. One byte takes one microsecond.*
- 20.4–25.6 — *The last NAND gate inverts the clock: the 165 shifts on the falling edge.*

**Voice-over** (scene time → spoken)
- 0.6 — "Clock-start sets a latch, which releases a four-bit counter."
- 4.2 — "The counter's lowest bit flips on every tick of the sixteen megahertz oscillator. That makes an eight megahertz clock, called S-C-K."
- 11.6 — "At fifteen, the terminal count output resets the latch. The counter clears, and stops."
- 16.0 — "Eight clock pulses, then silence. One byte takes one microsecond."
- 20.4 — "The last NAND gate inverts the clock, because the one-sixty-five shifts on the falling edge."
<!-- /captions -->

## S10 — Into the 3.3 V world (13.5 s)

Camera to the SD corner (centre (162, 58.5), w 50). +3V3 lights up; U16 is labelled
*regulator 5 V → 3.3 V*, U21 *74LVC125 buffer* (powered at 3.3 V, 5 V-tolerant
inputs), J1 *microSD socket*. The four SPI lanes light one by one, each with a
pill: /CS → DAT3, MOSI → CMD, SCK → CLK, DAT0 → MISO.

<!-- captions:s10_spi_wires -->
**Captions** (13.5 s silent cut)
- 0.6–5.8 — *The SD card runs on 3.3 V, from a regulator; a 74LVC125 drives its pins.*
- 6.2–13.0 — *SPI uses four wires: a clock (SCK), data out (MOSI), data in (MISO) and select (/CS).*

**Voice-over** (scene time → spoken)
- 0.6 — "The S-D card runs on three point three volts, from a regulator. A seventy-four L-V-C one twenty-five drives its pins."
- 6.2 — "The card speaks S-P-I, over four wires: a clock, data out called Mosi, data in called Miso, and chip-select."
<!-- /captions -->

## S11 — Bits out, bits in (32 s), the centrepiece

The **SPI ring** panel covers the dimmed board. Everything shifts *left*, so
every register reads MSB first, and SPI shows as one ring of shift registers:

```
 SCK  _|‾|_|‾|_ ...                                  (cursor, cycle numbers)

 [ SD card: its own register ]  <- MOSI <-  [ 74HC165  H … A ]  <- 1 (SER = 5 V)
   |
   +-> MISO --------------------------------------------+
                               [ 74HC595  QH … QA ]  <--+      [ 595 output latch ]
```

Slow motion: cycles 1–2 take 3 s each, 3–4 take 1.5 s, 5–8 take 0.6 s. Per cycle: on the rising edge
a copy of the '165's H bit glides into the card, the card shifts, and its MSB
travels the MISO lane into the '595. On the falling edge the '165 shifts and a `1`
enters. The '595 output latch copies, shown dimmed while the byte is still
incomplete. Result: the card has 51h, the latch FFh. From 22.4 s the panel
leaves and comets run along the real MOSI, SCK and MISO copper, with an LED inset.

Simplification: a real SD card changes MISO on the falling edge. The movie
shows the bit leaving at the rising edge, when the '595 samples it.

<!-- captions:s11_shift -->
**Captions** (32 s silent cut)
- 1.6–8.0 — *On each rising edge the SD card reads a bit from MOSI, and the 595 a bit from MISO.*
- 8.2–13.6 — *On each falling edge the 165 moves the next bit into place. Most significant bit first.*
- 14.0–21.6 — *While a command goes out, the card has nothing to say: it answers with ones.*
- 23.6–31.4 — *Sending and receiving are the same eight clocks. SPI simply swaps two bytes.*

**Voice-over** (scene time → spoken)
- 1.6 — "Now, in slow motion. On each rising edge, the S-D card reads one bit from Mosi, and the five-ninety-five reads one bit from Miso."
- 8.2 — "On each falling edge, the one-sixty-five moves the next bit into place. The most significant bit goes first."
- 14.0 — "While a command goes out, the card has nothing to say. It answers with ones."
- 23.6 — "Sending and receiving happen in the same eight clocks. S-P-I simply swaps two bytes."
<!-- /captions -->

## S12 — The card answers (28 s)

The same ring panel. The rest of CMD17 (`00 00 08 00` = sector 2048 on SDHC, CRC7
`E5`) goes out at one byte per second, with a breakdown under the title. The driver then
listens by sending FFh (`OUT 330h, FFh`, as OTTERSD's `io(255)` does). The replies
`FF 00 FF FF FE` arrive (R1 = 00h OK, FEh data token), then `EBh` in slow motion
(1.2 s per clock), and the latch shows EBh.

<!-- captions:s12_answer -->
**Captions** (28 s silent cut)
- 0.4–5.4 — *Next comes the sector number, 2048, where a partition usually starts, then a checksum.*
- 5.8–8.8 — *To listen, the driver simply sends FFh.*
- 9.0–11.9 — *The card answers 00h (OK), then FEh (data starts now).*
- 12.2–21.6 — *Out comes the sector's first byte, EBh, the start of a FAT boot sector.*
- 22.0–27.4 — *The byte now waits in the 595's output latch.*

**Voice-over** (scene time → spoken)
- 0.4 — "Next comes the sector number: twenty forty-eight, where a partition usually starts. Then a checksum."
- 5.8 — "To listen, the driver simply sends F-F."
- 9.0 — "The card answers zero zero, meaning OK. Then F-E: the data starts now."
- 12.2 — "Out comes the sector's first byte: E-B hex, the start of a FAT boot sector."
- 22.0 — "The byte now waits in the five-ninety-five's output latch."
<!-- /captions -->

## S13 — Back to the CPU (24 s)

`IN AL, DX` with DX = 330h. /IOR → U2A → U3 1Y0 (/RQ_SER_RD) → U11 gate B →
**/SER_RD** = 0, which enables the U7 outputs (/OE) and turns U9 around (DIR = 0,
B → A). EBh travels U7 → D bus → U9 → DB fingers (bit tokens); the CPU card shows
`AL = EBh`. Note: per byte, OTTERSD does `OUT 330h, FFh`, two dummy reads
while the burst runs, then `IN 330h`; 512 times per sector.

<!-- captions:s13_readback -->
**Captions** (24 s silent cut)
- 0.5–5.0 — *The CPU reads port 330h. The read decoder pulls /SER_RD low.*
- 5.2–11.6 — *The 595 drives the internal bus, and the 245 turns around to face the CPU.*
- 12.0–15.8 — *EBh arrives in register AL.*
- 16.2–23.4 — *OTTERSD repeats this for every byte: send FFh, then read the answer.*

**Voice-over** (scene time → spoken)
- 0.5 — "The CPU reads port three-thirty. The read decoder pulls serial-read low."
- 5.2 — "The five-ninety-five drives the internal bus, and the two forty-five turns around to face the CPU."
- 12.0 — "E-B hex arrives in register A-L."
- 16.2 — "The Otter-S-D driver repeats this for every byte. Send F-F, then read the answer."
<!-- /captions -->

## S14 — A whole sector (22 s)

Wide x-ray view. A frame strip, centred above the board: `51 00 00 08 00 E5` ·
`FF … 00` · `FF … FE` · `512 data bytes` · `CRC16`. The active phase is bright,
received parts are violet. A byte counter runs from 0 to 512 while comets loop along J1 →
R8 → U21 → U7 → U9 → J2, ever faster. Note: about 520 bursts; each byte costs
the driver four I/O cycles, and the 1 µs burst is the quick part.

<!-- captions:s14_sector -->
**Captions** (22 s silent cut)
- 0.2–6.0 — *A complete read: six bytes out, a short wait, a start token, 512 data bytes and a checksum.*
- 16.4–21.4 — *Every one of them takes the path you have just seen.*

**Voice-over** (scene time → spoken)
- 0.2 — "A complete read is six bytes out, a short wait, a start token, five hundred and twelve data bytes, and a checksum."
- 14.6 — "Every one of them takes the path you have just seen."
<!-- /captions -->

## S15 — Outro (12 s)

X-ray back to photo (its part numbers fade first). End card over a dimmed board:
**Slot-otter** · `github.com/ifilot/slot-otter` · licences. Fade to black.

<!-- captions:s15_outro -->
**Captions** (12 s silent cut)
- none

**Voice-over** (scene time → spoken)
- 3.6 — "Slot-otter. Open hardware, eight clocks at a time."
<!-- /captions -->

---

## Technical cross-reference (Classic, from the PCB netlist)

| Function | Parts and nets |
| --- | --- |
| Logic count | 14 logic ICs: U1–U13 and U21. U16 is the regulator, X1 the oscillator. |
| Address match | U8 74HCT688: P0..P7 = A2..A9, Q0..Q7 = SW1 (ON = 1; RN1/RN3 pull-downs), /G = AEN, /(P=Q) = **/PORTSEL** |
| Strobe qualify | U2 74HCT32: A = /PORTSEL + /IOR → U3 1/E; B = /PORTSEL + /IOW → U3 2/E; C = OR of the two edge-detector pulses |
| Decoders | U3 74HCT139 read half: 1Y0 /RQ_SER_RD, 1Y1 /SER_RD_AND_PULSE, 1Y2 /SDCS_SET, 1Y3 /SDCS_RESET. Write half: 2Y0 /SER_WR, 2Y1 /PULSE, 2Y2 /SDOUT_SET, 2Y3 /SDOUT_RESET |
| Latches | U5 74HC00: gates C/D = /CS latch (IN 332h release, IN 333h assert); gates A/B = MISO-pull latch → R1 10 k → MISO (no effect: U21 drives MISO) |
| Data gate | U9 74HCT245: A = ISA DB0..7, B = internal D0..7, /OE = /PORTSEL, DIR = /SER_RD |
| Edge detectors | U13 (write) and U10 (read) 74HC74, both stages at 16 MHz; U11 gates D/C AND the strobe with /Q2. The pulse starts at the release and lasts 62.5–125 ns |
| Clock start | U12 gate 1 inverts U2C; U11 gate A ANDs it with /PULSE → /CLKSTART |
| Burst | U1 74HC00 gates A/B: SR latch (set /CLKSTART, reset /CLKSTOP) → U4 /MR. U1C: CLKSTOP → /CLKSTOP. U1D: CLK → /CLK |
| Counter | U4 74HC163, 16 MHz, P inputs grounded, Q0 = **CLK** (SCK, 8 MHz). TC goes high at count 15; the synchronous clear on tick 16 gives the 8th falling edge |
| Out shift | U6 74HC165: SH/LD = /SER_WR, CLK = /CLK, SER = 5 V, QH = **MOSI**, H..A = D7..D0 |
| In shift | U7 74HC595: SER = MISO, SRCLK = CLK, RCLK = /CLK, /OE = /SER_RD, QH..QA = D7..D0 |
| Read strobe | U11 gate B: /RQ_SER_RD AND /SER_RD_AND_PULSE = /SER_RD |
| 3.3 V side | U16 AMS1117-3.3; U21 74LVC125 at 3.3 V (all /OE grounded) via R8–R11 3.3 k: MOSI→CMD, CLK→SCK, /CS→DAT3, DAT0→MISO. MISO returns at 3.3 V into 5 V HC inputs (works, but below the HC V_IH spec) |
| LEDs | U12 inverters: D1 lit while /CS is asserted, D2 while MOSI is low, D3 while MISO is low |
| Driver (OTTERSD) | per byte: OUT base+0 (byte or FFh), two settle reads of base+0, IN base+0. OUT base+1 only for the 12 wake-up bursts; IN base+3 once at start-up. CRC checking on (CMD17 CRC7 = E5 for sector 2048) |

SPI mode 0, MSB first: the card and the '595 sample on the rising SCK edge; the
'165 shifts and the '595 output latch updates on the falling edge.
