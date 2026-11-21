# Slot-otter Classic: "Eight Clocks" (movie script)

The visual script. The story itself, act by act, is in [STORY.md](STORY.md); the
narration in `scenes/narration.py` is its spoken form and **leads**: every scene is
timed around its narration lines.

**Length**: 10 min 9 s.

Cuts (one timeline, same pictures):

- `build/slot-otter-classic.mp4`: subtitles burned in, no audio.
- `build/slot-otter-classic-voiceover.mp4`: subtitles burned in, narration.
- `build/slot-otter-classic-voiceover-2160p-clean.mp4`: 4K, narration, subtitles as SRT/VTT.

The camera looks straight down on the Slot-otter Classic card. After a high-level
introduction (the PC writes and reads bytes at I/O ports, the SD card speaks SPI, the
card bridges the two) and a closer look at both sides' wires, we follow
**one byte out** (`OUT 330h, 51h`, the first byte of the SD command *read one
block*) from the ISA card edge to the microSD socket, then **one byte back**
(`EBh`, the first byte of a FAT boot sector) to the CPU, and end with a map of the
five jobs the fourteen chips do.

Format: 1920 × 1080, 60 fps (and a 4K render). Hardware statements were checked
against the netlist of `pcb/release/isa-sdcard.kicad_pcb`, driver statements
against `driver/SDRW.C`. Scene `scenes/sNN_*.py` implements section **SNN**. The
**Narration** blocks are generated from `scenes/narration.py` with
`render.py script`; edit the text there (or in STORY.md and ask for it to be
carried over).

---

## Visual language

Every cut is a 0.8 s cross-dissolve from the previous scene's last frame (drawn through the new scene's camera); `render.py check` verifies camera continuity and that nothing pops at a cut.

| Element | Look |
|

---

## S01 — Title and overview

Photo of the card in the `WIDE` shot. Title card **Slot-otter Classic** over the dimmed board; the board brightens as the second line starts. Then the overview, with panels either side of the card: **PC** on the left (8088 / 8086 CPU, *talks to hardware through I/O ports*; `OUT DX, AL` *write a byte* and `IN AL, DX` *read a byte* highlight as they are spoken; *port 330h*), wired to the card edge (J2 outlined): 51h travels to the card on OUT, EBh back on IN. **SD card** on the right (*speaks SPI*: a clock trace and bits moving one at a time into an SD glyph; *MOSI, MISO, SCK, /CS: four wires*), wired to the socket (J1 outlined). On *"Slot-otter sits in between"* a centre label **Slot-otter: bytes ⇄ bits**, while bytes go back and forth on the bus and bits run on the SPI lane. The panels fade and the camera pushes in to `FULL`.

<!-- narration:s01_title -->
**Narration** (scene time; 58 s of animation, 59.3 s on screen)
- 1.6 — *(title card)*
  - spoken: "Slot-otter Classic."
- 6.0 — It is an 8-bit ISA card that lets an old PC, even one of the very first 8088 machines, use an SD card as an ordinary DOS drive.
  - spoken: "It is an eight-bit I-S-A card that lets an old PC, even one of the very first eighty eighty-eight machines, use an S-D card as an ordinary DOS drive."
- 16.0 — To the PC, the card is simply a set of I/O ports. An 8088 or 8086 talks to its hardware through such ports: with one instruction it writes a byte to a port, and with another it reads a byte back.
  - spoken: "To the PC, the card is simply a set of I-O ports. An eighty eighty-eight or eighty eighty-six talks to its hardware through such ports: with one instruction it writes a byte to a port, and with another it reads a byte back."
- 30.5 — The SD card knows nothing about ports. In the simple mode used here, it speaks SPI: data travels one bit at a time, in step with a clock signal.
  - spoken: "The S-D card knows nothing about ports. In the simple mode used here, it speaks S-P-I: data travels one bit at a time, in step with a clock signal."
- 42.0 — Slot-otter sits in between. Every byte the PC writes becomes a stream of bits for the SD card, and the bits that come back are gathered into a byte the PC can read.
  - spoken: "Slot-otter sits in between. Every byte the PC writes becomes a stream of bits for the S-D card, and the bits that come back are gathered into a byte the PC can read."
<!-- /narration -->

## S02 — The x-ray

The photo cross-fades into the x-ray. As the narration names them, the parts are pointed at: the fourteen logic chips outline themselves one after another while a margin label counts *1 … 14 logic chips*; then *oscillator · 16 MHz* and *regulator · 3.3 V*, each a margin label with a leader line. On *"meet each of these chips along the way"* the five groups light up one by one in their S15 colours, each labelled with its job: *listen to the bus*, *gate to the bus*, *bytes to bits*, *make the clock*, *bridge to 3.3 V*. Everything fades before the cut.

<!-- narration:s02_xray -->
**Narration** (scene time; 28 s of animation, 29.9 s on screen)
- 3.0 — What makes this card unusual is how it does that. There is no microcontroller on it and no firmware, just fourteen 74-series logic chips, an oscillator and a voltage regulator.
  - spoken: "What makes this card unusual is how it does that. There is no microcontroller on it and no firmware, just fourteen seventy-four series logic chips, an oscillator and a voltage regulator."
- 14.0 — So how can a handful of logic chips talk to an SD card? To find out, we will follow a single byte from the PC to the SD card, and another one on its way back, and meet each of these chips along the way.
  - spoken: "So how can a handful of logic chips talk to an S-D card? To find out, we will follow a single byte from the PC to the S-D card, and another one on its way back, and meet each of these chips along the way."
<!-- /narration -->

## S03 — Two worlds

Two schematic panels over the dimmed board. **PC**: a CPU, an address band (330h) and eight data wires; the bits of 51h travel along all eight at once. **SD card**: four lanes into the card. The bits of 51h travel one by one on MOSI, each riding on its own SCK pulse; the card's register fills (MSB first) and reads 51h. MISO bits leave the card; /CS lights up as *low (0 V): listening*. Then *this card: bytes → bits → bytes*, and the panels give way to the real board: card edge = *bytes · ISA bus*, microSD socket = *bits · SPI*, the logic chips faintly outlined in between.

<!-- narration:s03_worlds -->
**Narration** (scene time; 52 s of animation, 55.0 s on screen)
- 0.4 — But first, let's take a closer look at both sides, starting with the PC.
  - spoken: "But first, let's take a closer look at both sides, starting with the PC."
- 4.4 — On the ISA bus, the PC puts all eight bits of a byte on eight wires at once, together with an address that says where the byte should go.
  - spoken: "On the I-S-A bus, the PC puts all eight bits of a byte on eight wires at once, together with an address that says where the byte should go."
- 15.2 — The SD card, by contrast, takes in one bit at a time, on a single wire called MOSI.
  - spoken: "The S-D card, by contrast, takes in one bit at a time, on a single wire called Mosi."
- 21.8 — A second wire, the clock SCK, tells the card when to read each bit, so eight clock pulses carry one byte.
  - spoken: "A second wire, the clock S-C-K, tells the card when to read each bit, so eight clock pulses carry one byte."
- 28.8 — The card's answers come back the same way, bit by bit, on a third wire called MISO.
  - spoken: "The card's answers come back the same way, bit by bit, on a third wire called Miso."
- 34.4 — And a fourth wire, chip select, has to be held low, at zero volts, for the card to listen at all.
  - spoken: "And a fourth wire, chip select, has to be held low, at zero volts, for the card to listen at all."
- 40.4 — That is the translation this card performs: bytes into bits, and bits back into bytes.
  - spoken: "That is the translation this card performs: bytes into bits, and bits back into bytes."
- 45.8 — On the board, bytes arrive at the card edge, and leave as bits through the SD socket.
  - spoken: "On the board, bytes arrive at the card edge, and leave as bits through the S-D socket."
<!-- /narration -->

## S04 — The card edge

The gold fingers. CPU card `MOV DX,330h / MOV AL,51h / OUT DX,AL`. A read-out panel: *0101 0001 = 51h, SD command: read one block*; then the bit tokens appear on the address and data fingers and the panel adds *11 0011 0000 = 330h*. Ghosts of the rear (B) fingers: /IOW lit (= 0), /IOR dim (= 1); the pill *"/ = active when low (0 V)"* and the tag *"/IOW = 0: write"*.

<!-- narration:s04_edge -->
**Narration** (scene time; 29 s of animation, 32.0 s on screen)
- 1.0 — Now let's follow our byte. The CPU writes 51h to I/O port 330h.
  - spoken: "Now let's follow our byte. The CPU writes fifty-one hex to I-O port three-thirty hex."
- 6.4 — That value is no accident: 51h is the first byte of the SD card's command to read one block.
  - spoken: "That value is no accident: fifty-one hex is the first byte of the S-D card's command to read one block."
- 13.8 — For a brief moment, the bus carries both the address and the byte.
  - spoken: "For a brief moment, the bus carries both the address and the byte."
- 17.2 — At the same time, the CPU pulls a wire called /IOW low. The slash means the wire is active when it is low, and here it tells the cards on the bus that this is a write.
  - spoken: "At the same time, the CPU pulls a wire called I-O-W low. The slash means the wire is active when it is low, and here it tells the cards on the bus that this is a write."
<!-- /narration -->

## S05 — Is this for me?

Address lines A9..A2 travel to the 74HCT688 (lines at 0 are dim). Comparator panel: P = address. The DIP switch is redrawn as slide switches with a value legend; Q = switch row; column checks; *all equal → card addressed* (tag on the board too). *What if: OUT 300h*: two columns fail, *not for us*. Finally the four ports 330h–333h.

<!-- narration:s05_comparator -->
**Narration** (scene time; 37 s of animation, 40.3 s on screen)
- 0.6 — Every card in the PC sees this address, so our card first has to ask: is this meant for me?
  - spoken: "Every card in the PC sees this address, so our card first has to ask: is this meant for me?"
- 6.6 — I/O addresses use ten lines. Eight of them, A9 down to A2, run to a 74HCT688, a chip that compares two 8-bit numbers.
  - spoken: "I-O addresses use ten lines. Eight of them, A-nine down to A-two, run to a seventy-four H-C-T six eighty-eight, a chip that compares two eight-bit numbers."
- 16.8 — Its second number comes from a DIP switch, where you set the address the card should answer to.
  - spoken: "Its second number comes from a dip switch, where you set the address the card should answer to."
- 22.0 — When all eight bits match, the card knows it is being addressed.
  - spoken: "When all eight bits match, the card knows it is being addressed."
- 25.4 — Any other address fails, and the card ignores it.
  - spoken: "Any other address fails, and the card ignores it."
- 28.8 — A1 and A0 are not compared at all, so the card answers to four ports in a row: 330h to 333h.
  - spoken: "A-one and A-zero are not compared at all, so the card answers to four ports in a row: three-thirty to three-thirty-three hex."
<!-- /narration -->

## S06 — What does the CPU want?

The 74HCT32 (outline only) takes *addressed* and */IOW: write*; the 74HCT139 decoder takes A1 = A0 = 0. A port table builds: 330h *fetch the card's reply* / *send a byte*; 331h–333h in plain words (dimmed while the two 330h actions glow: first *send a byte* in rose, then *fetch the card's reply* in cyan). On the board: *action: send a byte*.

<!-- narration:s06_registers -->
**Narration** (scene time; 25.5 s of animation, 29.0 s on screen)
- 1.0 — Next, the card works out what the CPU wants: a read or a write, and on which of its four ports.
  - spoken: "Next, the card works out what the CPU wants: a read or a write, and on which of its four ports."
- 6.4 — A decoder combines A1 and A0 with the read and write signals, and turns them into a single action.
  - spoken: "A decoder combines A-one and A-zero with the read and write signals, and turns them into a single action."
- 12.6 — Only two of these actions matter for our story. Writing to 330h sends a byte to the SD card,
  - spoken: "Only two of these actions matter for our story. Writing to three-thirty sends a byte to the S-D card,"
- 18.8 — and reading from the same port fetches the card's reply.
  - spoken: "and reading from the same port fetches the card's reply."
- 22.2 — The other ports handle housekeeping.
  - spoken: "The other ports handle housekeeping."
<!-- /narration -->

## S07 — Two shift registers

The bits of 51h flow from the fingers through the 74HCT245 (*the gate: bus → card*) onto the internal bus. Both shift registers are outlined. Panel: the 74HC165 (*byte in at once, bits out one by one*): the byte card splits into cells H..A while /IOW is low (*/IOW low: load*); MOSI lights, *bit 7 → MOSI*. Then the 74HCT595 joins the panel (*bits in one by one, byte out at once*), its cells empty, *waiting for bits on MISO*; MISO lights into U7. Finally *clock?* tags on both chips' clock inputs.

<!-- narration:s07_load -->
**Narration** (scene time; 56.5 s of animation, 61.2 s on screen)
- 1.0 — First, the byte has to get onto the card. It enters through a 74HCT245, the card's gate to the bus, which lets data in when the CPU writes, and out when it reads.
  - spoken: "First, the byte has to get onto the card. It enters through a seventy-four H-C-T two forty-five, the card's gate to the bus, which lets data in when the CPU writes, and out when it reads."
- 12.4 — Behind the gate, the actual translation is done by two shift registers.
  - spoken: "Behind the gate, the actual translation is done by two shift registers."
- 16.6 — The first, a 74HC165, has eight cells that load a whole byte at once and then hand it out one bit at a time. While /IOW is still low, our byte is copied in.
  - spoken: "The first, a seventy-four H-C one sixty-five, has eight cells that load a whole byte at once and then hand it out one bit at a time. While I-O-W is still low, our byte is copied in."
- 29.2 — Every clock pulse then pushes the next bit onto MOSI. Bit 7 goes first, and it is already waiting there.
  - spoken: "Every clock pulse then pushes the next bit onto Mosi. Bit seven goes first, and it is already waiting there."
- 36.6 — Next to it sits its mirror image, a 74HCT595, which collects the bits coming back from the SD card one at a time, and holds them as a byte.
  - spoken: "Next to it sits its mirror image, a seventy-four H-C-T five ninety-five, which collects the bits coming back from the S-D card one at a time, and holds them as a byte."
- 46.8 — Both registers need clock pulses, and the PC doesn't provide them. The card has to make its own clock, and it has to know exactly when to start.
  - spoken: "Both registers need clock pulses, and the PC doesn't provide them. The card has to make its own clock, and it has to know exactly when to start."
<!-- /narration -->

## S08 — Waiting for the CPU to let go

Near the two 74HC74s. Tag */IOW low: the 165 is loading*. The flip-flops are outlined (*two flip-flops*) and a timing diagram *waiting for /IOW to end* shows 16 MHz, /IOW, the strobe as seen by the second flip-flop, and the pulse (*CPU lets go* mark). The pulse then travels through the glue gates to the start/stop latch: *start pulse*. Camera widens.

<!-- narration:s08_edge_detect -->
**Narration** (scene time; 22.5 s of animation, 23.5 s on screen)
- 0.8 — Starting too early would spoil everything: as long as /IOW is low, the 165 keeps loading, and cannot shift.
  - spoken: "Starting too early would spoil everything: as long as I-O-W is low, the one sixty-five keeps loading, and cannot shift."
- 9.0 — So the card waits for the CPU to let go. Two flip-flops watch /IOW, and the moment it is released, they produce a single short pulse.
  - spoken: "So the card waits for the CPU to let go. Two flip-flops watch I-O-W, and the moment it is released, they produce a single short pulse."
- 18.6 — That pulse is what starts the clock.
  - spoken: "That pulse is what starts the clock."
<!-- /narration -->

## S09 — Exactly eight clocks

The 16 MHz oscillator and the start/stop latch are outlined; *run* on the counter. Counter panel: lamps Q3..Q0, the count, a timing plot (16 MHz, Q0 = SCK, stop). The count runs 0..15 at two ticks per second, *SCK pulses* counts up to 8, *16 ticks → 8 pulses*; at 15 *stop* lights (and *stop at 15* on the board), the next tick clears and the plot runs on into silence. *up* / *down* marks on SCK for the two edges.

<!-- narration:s09_counter -->
**Narration** (scene time; 38 s of animation, 41.7 s on screen)
- 0.6 — The clock itself comes from a 16 MHz oscillator and a 4-bit counter, which starts to run as soon as that pulse arrives.
  - spoken: "The clock itself comes from a sixteen megahertz oscillator and a four-bit counter, which starts to run as soon as that pulse arrives."
- 9.0 — The counter's lowest bit flips between 0 and 1 on every tick of the oscillator, which gives an 8 MHz clock, SCK. Sixteen ticks make eight pulses.
  - spoken: "The counter's lowest bit flips between zero and one on every tick of the oscillator, which gives an eight megahertz clock, S-C-K. Sixteen ticks make eight pulses."
- 19.4 — When the count reaches fifteen, the counter stops itself: eight clock pulses, and then silence.
  - spoken: "When the count reaches fifteen, the counter stops itself: eight clock pulses, and then silence."
- 25.4 — Each pulse has two edges, one where the clock goes up and one where it comes down again, and as we will see, the card uses both.
  - spoken: "Each pulse has two edges, one where the clock goes up and one where it comes down again, and as we will see, the card uses both."
- 32.6 — Before those pulses can reach the SD card, though, there is one more problem to solve.
  - spoken: "Before those pulses can reach the S-D card, though, there is one more problem to solve."
<!-- /narration -->

## S10 — Into the 3.3 V world

The SD corner. Regulator, 74LVC125 and socket outlined. A panel *74LVC125: four buffers, powered at 3.3 V*: /CS, MOSI, SCK `5 V → ▷ → 3.3 V`, then the MISO row `3.3 V ← ◁ ← 3.3 V` into the 595 (*reads anything above 2 V as a 1*), then the /CS row again (*already low, set once at start-up*). The four lanes light with pills /CS → DAT3, MOSI → CMD, SCK → CLK, DAT0 → MISO; the lane being talked about stays bright.

<!-- narration:s10_spi_wires -->
**Narration** (scene time; 34.5 s of animation, 37.3 s on screen)
- 0.6 — The SD card runs on 3.3 V, and the PC's 5 V signals would damage it.
  - spoken: "The S-D card runs on three point three volts, and the PC's five volt signals would damage it."
- 7.0 — That is why a 74LVC125 buffer sits in between. It runs on 3.3 V itself but accepts 5 V inputs, so the card only ever sees 3.3 V.
  - spoken: "That is why a seventy-four L-V-C one twenty-five buffer sits in between. It runs on three point three volts itself but accepts five volt inputs, so the card only ever sees three point three volts."
- 20.2 — In the other direction, MISO comes back at 3.3 V, which the 595 still reads as a 1.
  - spoken: "In the other direction, Miso comes back at three point three volts, which the five ninety-five still reads as a one."
- 26.4 — And chip select is already low: the driver set it once at start-up, by reading port 333h.
  - spoken: "And chip select is already low: the driver set it once at start-up, by reading port three-thirty-three."
<!-- /narration -->

## S11 — Bits out, bits in

The SPI ring over the dimmed board: 74HC165 → MOSI → SD card → MISO → 74HCT595, SCK on top. Slow motion: clocks 1–2 take 4 s each, 3–4 take 2 s, 5–8 take 0.8 s. On the rising edge the card and the 595 take a bit; on the falling edge the 165 shifts and a 1 enters. Result: the card holds 51h, the 595 FFh (*card received 51h and sent FFh*). Then comets run along the real MOSI, SCK and MISO copper with an LED inset, and *8 clocks = 1 µs*. (Simplification: a real card changes MISO on the falling edge; the film shows the bit leaving when the 595 samples it.)

<!-- narration:s11_shift -->
**Narration** (scene time; 43.5 s of animation, 44.8 s on screen)
- 0.4 — Now the eight clocks run, and bits move both ways at once.
  - spoken: "Now the eight clocks run, and bits move both ways at once."
- 4.4 — Each time the clock goes up, the SD card reads a bit from MOSI, and the 595 picks up a bit from MISO.
  - spoken: "Each time the clock goes up, the S-D card reads a bit from Mosi, and the five ninety-five picks up a bit from Miso."
- 11.6 — And each time it comes down, the 165 moves its next bit into place, so a bit never changes while someone is reading it.
  - spoken: "And each time it comes down, the one sixty-five moves its next bit into place, so a bit never changes while someone is reading it."
- 20.0 — While a command is going out, the card has nothing to say yet, so it simply answers with ones.
  - spoken: "While a command is going out, the card has nothing to say yet, so it simply answers with ones."
- 25.4 — After eight clocks, the SD card has our byte, 51h, and the 595 holds the card's reply. Sending and receiving happen on the very same clocks: SPI simply swaps two bytes.
  - spoken: "After eight clocks, the S-D card has our byte, fifty-one hex, and the five ninety-five holds the card's reply. Sending and receiving happen on the very same clocks: S-P-I simply swaps two bytes."
- 39.4 — And all of this takes just one microsecond.
  - spoken: "And all of this takes just one microsecond."
<!-- /narration -->

## S12 — The card answers

The same ring. The rest of the command (`00 00 08 00 E5`: *which block*, *check*) goes out at one byte per second. Then *OUT 330h, FFh (listening)*: FF polls, *00h: OK*, more FF, *FEh: here comes the data*, then EBh in slow motion; the 595 output latch shows EBh (*first byte of the sector*). A byte log shows sent/received.

<!-- narration:s12_answer -->
**Narration** (scene time; 35.5 s of animation, 38.0 s on screen)
- 0.4 — The rest of the command follows in exactly the same way: five more bytes, which include the number of the block to read.
  - spoken: "The rest of the command follows in exactly the same way: five more bytes, which include the number of the block to read."
- 7.5 — The card then needs a moment. To hear its answer, the driver keeps sending FFh, a byte of all ones, and reads port 330h after each one to see what came back.
  - spoken: "The card then needs a moment. To hear its answer, the driver keeps sending F-F hex, a byte of all ones, and reads port three-thirty after each one to see what came back."
- 17.9 — First the card replies "OK", and then "here comes the data".
  - spoken: "First the card replies: OK, and then: here comes the data."
- 22.3 — Then the first byte of the block arrives: EBh, the start of a FAT boot sector.
  - spoken: "Then the first byte of the block arrives: E-B hex, the start of a FAT boot sector."
- 31.2 — It now waits in the 595, ready for the CPU to collect.
  - spoken: "It now waits in the five ninety-five, ready for the CPU to collect."
<!-- /narration -->

## S13 — Back to the CPU

`IN AL, DX` with DX = 330h. The read decoder lights (*read 330h*), the 595 outputs switch on (*595 outputs on*), EBh goes onto the internal bus; the 245 turns around (*the gate: card → bus*) and the bit tokens reach the fingers; the CPU card shows `AL = EBh`.

<!-- narration:s13_readback -->
**Narration** (scene time; 21 s of animation, 23.5 s on screen)
- 0.5 — To collect it, the CPU reads port 330h. The decoder recognises the read, and the 595 puts its byte onto the card's internal bus.
  - spoken: "To collect it, the CPU reads port three-thirty. The decoder recognises the read, and the five ninety-five puts its byte onto the card's internal bus."
- 9.9 — The 245, our gate, now turns around to face the CPU, and the byte flows out onto the ISA bus.
  - spoken: "The two forty-five, our gate, now turns around to face the CPU, and the byte flows out onto the I-S-A bus."
- 16.9 — And there it is: EBh, in the CPU's register AL.
  - spoken: "And there it is: E-B hex, in the CPU's register A-L."
<!-- /narration -->

## S14 — A whole sector

Wide view. A strip: command · OK · data starts · 512 data bytes · check, the active phase bright. Bytes stream in, ever faster: one comet on the serial path (J1 → R8 → U21 → MISO → U7), eight comets on D0–D7 → U9 → DB0–DB7 (1 bits bright, 0 bits dim; the first bytes are the boot sector's `EB 3C 90 'MSDOS5.0'`); a counter runs to 512. *≈ 38 KB/s, including the PC's own work* (README figure), then *a file = a list of sectors*. Camera to `FULL`.

<!-- narration:s14_sector -->
**Narration** (scene time; 27 s of animation, 29.6 s on screen)
- 0.2 — That was a single byte. A block, or sector, holds 512 of them, plus a few extra bytes for the command, the replies and a checksum.
  - spoken: "That was a single byte. A block, or sector, holds five hundred and twelve of them, plus a few extra bytes for the command, the replies and a checksum."
- 9.0 — Every one of them takes the path you have just seen, eight clocks at a time. Including the work the PC itself has to do, that adds up to about 38 kilobytes per second.
  - spoken: "Every one of them takes the path you have just seen, eight clocks at a time. Including the work the PC itself has to do, that adds up to about thirty-eight kilobytes per second."
- 19.4 — A file, in the end, is just a list of sectors, and the driver turns them into an ordinary DOS drive.
  - spoken: "A file, in the end, is just a list of sectors, and the driver turns them into an ordinary DOS drive."
<!-- /narration -->

## S15 — Fourteen chips, five jobs

The same view as S02. The five groups return; one by one each lights up in its own colour with a label, then stays lit softer: **listeners** (74HCT688, 74HCT32, 74HCT139, chip-select latch 74HC00 U5; amber), **gate** (74HCT245; cyan), **translators** (74HC165, 74HCT595; violet), **clock makers** (2× 74HC74, 74HC08, 74HCT04, 74HC00 U1, 74HC163, with the oscillator; lime), **bridge to 3.3 V** (74LVC125, with the regulator; coral). Within a group, each chip flares as it is named, with its own small label (*688*, *32*, *139*, *CS latch*; *flip-flops*, *counter*, *gates* with leader lines), which fades when the line ends; the oscillator, DIP switch and regulator are outlined with their groups. On *"Fourteen chips, five jobs"* all five glow together. 4 + 1 + 2 + 6 + 1 = 14.

<!-- narration:s15_recap -->
**Narration** (scene time; 45 s of animation, 48.2 s on screen)
- 0.6 — Now that we know what every part does, let's look at the card one last time.
  - spoken: "Now that we know what every part does, let's look at the card one last time."
- 4.8 — The 688, the 32 and the 139 listen to the bus: together they recognise our address and work out what the CPU wants, while a small latch next to them holds chip select.
  - spoken: "The six eighty-eight, the thirty-two and the one thirty-nine listen to the bus: together they recognise our address and work out what the CPU wants, while a small latch next to them holds chip select."
- 16.4 — The 245 is the gate that lets bytes in and out.
  - spoken: "The two forty-five is the gate that lets bytes in and out."
- 20.6 — The 165 and the 595 are the translators, turning bytes into bits and bits back into bytes.
  - spoken: "The one sixty-five and the five ninety-five are the translators, turning bytes into bits and bits back into bytes."
- 27.2 — Two flip-flops, a counter and a few gates make the clock: exactly eight pulses, started at exactly the right moment.
  - spoken: "Two flip-flops, a counter and a few gates make the clock: exactly eight pulses, started at exactly the right moment."
- 35.0 — And the 125 is the bridge to the SD card's 3.3 V world.
  - spoken: "And the one twenty-five is the bridge to the S-D card's three point three volt world."
- 40.2 — Fourteen chips, five jobs.
  - spoken: "Fourteen chips, five jobs."
<!-- /narration -->

## S16 — Outro

X-ray back to photo (part numbers fade first). End card over a dimmed board: **Slot-otter** · `github.com/ifilot/slot-otter` · licences. Fade to black.

<!-- narration:s16_outro -->
**Narration** (scene time; 15.5 s of animation, 15.8 s on screen)
- 1.0 — No processor and no firmware: just logic, turning bytes into bits and bits back into bytes.
  - spoken: "No processor and no firmware: just logic, turning bytes into bits and bits back into bytes."
- 7.4 — Slot-otter is open hardware, and its schematics, board and driver are all on GitHub.
  - spoken: "Slot-otter is open hardware, and its schematics, board and driver are all on GitHub."
<!-- /narration -->

---

## Technical cross-reference (Classic, from the PCB netlist)

| Function | Parts and nets |
| --- | --- |
| Logic count | 14 logic ICs: U1–U13 and U21. U16 is the regulator, X1 the oscillator. |
| Address match | U8 74HCT688: P0..P7 = A2..A9, Q0..Q7 = SW1 (ON = 1; RN1/RN3 pull-downs), /G = AEN, /(P=Q) = **/PORTSEL** |
| Strobe qualify | U2 74HCT32: A = /PORTSEL + /IOR → U3 1/E; B = /PORTSEL + /IOW → U3 2/E; C = OR of the two edge-detector pulses |
| Decoders | U3 74HCT139 read half: 1Y0 /RQ_SER_RD, 1Y1 /SER_RD_AND_PULSE, 1Y2 /SDCS_SET, 1Y3 /SDCS_RESET. Write half: 2Y0 /SER_WR, 2Y1 /PULSE, 2Y2 /SDOUT_SET, 2Y3 /SDOUT_RESET |
| Latch | U5 74HC00 gates C/D: /CS latch (IN 332h release, IN 333h assert) |
| Data gate | U9 74HCT245: A = ISA DB0..7, B = internal D0..7, /OE = /PORTSEL, DIR = /SER_RD |
| Edge detectors | U13 (write) and U10 (read) 74HC74, both stages at 16 MHz; U11 gates D/C AND the strobe with /Q2. The pulse starts at the release and lasts 62.5–125 ns |
| Clock start | U12 gate 1 inverts U2C; U11 gate A ANDs it with /PULSE → /CLKSTART |
| Burst | U1 74HC00 gates A/B: SR latch (set /CLKSTART, reset /CLKSTOP) → U4 /MR. U1C: CLKSTOP → /CLKSTOP. U1D: CLK → /CLK |
| Counter | U4 74HC163, 16 MHz, P inputs grounded, Q0 = **CLK** (SCK, 8 MHz). TC goes high at count 15; the synchronous clear on tick 16 gives the 8th falling edge |
| Out shift | U6 74HC165: SH/LD = /SER_WR, CLK = /CLK, SER = 5 V, QH = **MOSI**, H..A = D7..D0 |
| In shift | U7 74HCT595: SER = MISO, SRCLK = CLK, RCLK = /CLK, /OE = /SER_RD, QH..QA = D7..D0 |
| Read strobe | U11 gate B: /RQ_SER_RD AND /SER_RD_AND_PULSE = /SER_RD |
| 3.3 V side | U16 AMS1117-3.3; U21 74LVC125 at 3.3 V (all /OE grounded) via R8–R11 3.3 k: MOSI→CMD, CLK→SCK, /CS→DAT3, DAT0→MISO. MISO returns at 3.3 V into the 74HCT595 and 74HCT04 (HCT inputs: high from 2.0 V; rev3, previously HC parts that worked by margin) |
| LEDs | U12 74HCT04 inverters: D1 lit while /CS is asserted, D2 while MOSI is low, D3 while MISO is low |
| Driver (OTTERSD) | per byte: OUT base+0 (byte or FFh), two settle reads of base+0, IN base+0. OUT base+1 only for the 12 wake-up bursts; IN base+3 once at start-up. CRC checking on (CMD17 CRC7 = E5 for sector 2048) |

SPI mode 0, MSB first: the card and the '595 sample on the rising SCK edge; the
'165 shifts and the '595 output latch updates on the falling edge.
